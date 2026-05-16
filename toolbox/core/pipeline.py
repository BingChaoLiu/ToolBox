from __future__ import annotations

import asyncio
import operator
import re as _re
import threading
from pathlib import Path

from toolbox.core.events import (
    ScriptCompleted, ScriptFailed,
    PromptRequired, ConfirmRequired, PipelineCompleted, ExecutionEnded,
)
from toolbox.core.executor import Executor
from toolbox.core.config_loader import resolve_value
from lib.logger import logger

# ---------------------------------------------------------------------------
# 安全的条件表达式解析器，替代 eval()
# ---------------------------------------------------------------------------

_COMPARISON_OPS = {
    "==": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
}

_BOOL_MAP = {"true": True, "false": False, "yes": True, "no": False}


def _safe_eval_condition(expr: str) -> bool:
    """解析简单的条件表达式，不使用 eval。

    支持的格式：
    - 纯布尔值: "true", "false"
    - 比较运算: "value == 0", "count > 5", "name != ''"
    - 逻辑运算: "expr1 and expr2", "expr1 or expr2", "not expr"
    """
    expr = expr.strip()

    # 纯布尔值
    if expr.lower() in _BOOL_MAP:
        return _BOOL_MAP[expr.lower()]

    # 处理 "or"
    for part in _split_logical(expr, " or "):
        if _eval_and(part.strip()):
            return True
    return False


def _eval_and(expr: str) -> bool:
    """处理 and 逻辑运算。"""
    parts = _split_logical(expr, " and ")
    return all(_eval_not(p.strip()) for p in parts)


def _eval_not(expr: str) -> bool:
    """处理 not 逻辑运算。"""
    if expr.startswith("not "):
        return not _eval_not(expr[4:].strip())
    return _eval_comparison(expr)


def _eval_comparison(expr: str) -> bool:
    """处理比较运算。长操作符优先匹配。"""
    # 按操作符长度降序排列，确保 >= 在 > 之前匹配
    sorted_ops = sorted(_COMPARISON_OPS.items(), key=lambda x: len(x[0]), reverse=True)
    for op_str, op_fn in sorted_ops:
        idx = expr.rfind(op_str)
        if idx > 0:
            # 确保匹配的不是更长操作符的子串
            # 例如 '42 >= 42' 中 rfind('>') 找到的位置，
            # 需要检查后面一个字符是否是 '='
            if op_str == ">" and idx + 1 < len(expr) and expr[idx + 1] == "=":
                continue
            if op_str == "<" and idx + 1 < len(expr) and expr[idx + 1] == "=":
                continue
            left = expr[:idx].strip()
            right = expr[idx + len(op_str):].strip()
            left_val = _parse_value(left)
            right_val = _parse_value(right)
            try:
                return op_fn(left_val, right_val)
            except TypeError:
                return False
    return bool(_parse_value(expr))


def _parse_value(s: str):
    """将字符串解析为 Python 值。"""
    s = s.strip()
    if not s:
        return s
    if s.lower() in _BOOL_MAP:
        return _BOOL_MAP[s.lower()]
    try:
        if "." in s:
            return float(s)
        return int(s)
    except ValueError:
        pass
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    return s


def _split_logical(expr: str, sep: str) -> list:
    """按逻辑运算符拆分，但不拆分引号内的内容。"""
    parts = []
    current = []
    in_quote = None
    i = 0
    while i < len(expr):
        ch = expr[i]
        if ch in ('"', "'") and in_quote is None:
            in_quote = ch
            current.append(ch)
        elif ch == in_quote:
            in_quote = None
            current.append(ch)
        elif in_quote is None and expr[i:i + len(sep)] == sep:
            parts.append("".join(current))
            current = []
            i += len(sep)
            continue
        else:
            current.append(ch)
        i += 1
    parts.append("".join(current))
    return parts


# ---------------------------------------------------------------------------
# PipelineEngine
# ---------------------------------------------------------------------------


class PipelineEngine:
    def __init__(self, steps: list[dict], scripts_dir: str, project_root: str, tid: int = 0):
        self._steps = steps
        self._scripts_dir = Path(scripts_dir)
        self._project_root = project_root
        self._tid = tid
        self._executor = Executor(project_root=project_root)
        self._step_outputs: dict[str, dict] = {}
        self._prompt_events: dict[str, threading.Event] = {}
        self._prompt_responses: dict[str, str] = {}
        self._current_choice = None
        self._cancelled = False

    def respond_prompt(self, step_id: str, choice: str):
        self._prompt_responses[step_id] = choice
        self._current_choice = choice
        if step_id in self._prompt_events:
            self._prompt_events[step_id].set()

    def respond_confirm(self, step_id: str, confirmed: bool):
        self._prompt_responses[step_id] = "yes" if confirmed else "no"
        if step_id in self._prompt_events:
            self._prompt_events[step_id].set()

    def cancel(self):
        """标记流水线为已取消，唤醒所有等待中的 prompt/confirm。"""
        self._cancelled = True
        for event in self._prompt_events.values():
            event.set()

    def run(self, loop: asyncio.AbstractEventLoop, event_queue: asyncio.Queue):
        def emit(event):
            loop.call_soon_threadsafe(event_queue.put_nowait, event)

        logger.info(f"流水线引擎启动 (tid={self._tid})")
        self._run_steps(emit)

    def _run_steps(self, emit):
        idx = 0
        while idx < len(self._steps):
            # 取消检查
            if self._cancelled:
                logger.info(f"流水线已取消 (tid={self._tid})")
                return

            step = self._steps[idx]
            sid = step.get("id", f"step_{idx}")

            # Check condition
            condition = step.get("if")
            if condition:
                resolved_cond = resolve_value(condition, self._step_outputs, is_step_outputs=True)
                try:
                    if isinstance(resolved_cond, str):
                        should_run = _safe_eval_condition(resolved_cond)
                    else:
                        should_run = bool(resolved_cond)
                except Exception as e:
                    logger.error(f"步骤 '{sid}' 条件解析失败: {condition} -> {resolved_cond}, 错误: {e}")
                    should_run = True

                if not should_run:
                    logger.info(f"步骤 '{sid}' 跳过 (条件不满足: {condition})")
                    idx += 1
                    continue

            if step.get("type") == "end":
                emit(PipelineCompleted(
                    pipeline_name="",
                    outputs=list(self._step_outputs.values()),
                ))
                return

            if step.get("type") == "prompt":
                message = step.get("message", "")
                message = self._resolve_message(message)
                choices = [c["label"] for c in step.get("choices", [])]

                wait_event = threading.Event()
                self._prompt_events[sid] = wait_event

                emit(PromptRequired(tid=self._tid, step_id=sid, message=message, choices=choices))

                wait_event.wait()

                choice_label = self._prompt_responses.get(sid, "")
                self._current_choice = choice_label

                if "goto_template" in step:
                    template = step["goto_template"]
                    script_name = template["script"]
                    mapping = template.get("mapping", {})
                    params = self._resolve_mapping(mapping)
                    script_path = self._scripts_dir / f"{script_name}.py"

                    self._run_script_step(str(script_path), params, emit)
                    self._step_outputs[sid] = {"choice": choice_label}

                    emit(PipelineCompleted(
                        pipeline_name="",
                        outputs=list(self._step_outputs.values()),
                    ))
                    return

                for c in step.get("choices", []):
                    if c["label"] == choice_label:
                        goto_id = c.get("goto", "end")
                        if goto_id == "end":
                            emit(PipelineCompleted(
                                pipeline_name="",
                                outputs=list(self._step_outputs.values()),
                            ))
                            return
                        for i, s in enumerate(self._steps):
                            if s.get("id") == goto_id:
                                idx = i
                                break
                        else:
                            idx += 1
                        break
                else:
                    idx += 1
                continue

            if step.get("type") == "confirm":
                message = step.get("message", "")

                wait_event = threading.Event()
                self._prompt_events[sid] = wait_event

                emit(ConfirmRequired(tid=self._tid, step_id=sid, message=message))

                wait_event.wait()

                response = self._prompt_responses.get(sid, "no")
                goto = step.get("yes_goto" if response == "yes" else "no_goto", "end")
                if goto == "end":
                    emit(PipelineCompleted(
                        pipeline_name="",
                        outputs=list(self._step_outputs.values()),
                    ))
                    return
                for i, s in enumerate(self._steps):
                    if s.get("id") == goto:
                        idx = i
                        break
                else:
                    idx += 1
                continue

            # Script step
            script_name = step.get("script", "")
            mapping = step.get("mapping", {})
            params = self._resolve_mapping(mapping)
            script_path = self._scripts_dir / f"{script_name}.py"

            completed_output = self._run_script_step(str(script_path), params, emit)
            self._step_outputs[sid] = completed_output or {}

            idx += 1

        emit(PipelineCompleted(
            pipeline_name="",
            outputs=list(self._step_outputs.values()),
        ))

    def _run_script_step(self, script_path: str, params: dict, emit) -> dict | None:
        output = None

        def local_emit(event):
            if isinstance(event, ExecutionEnded):
                return
            emit(event)
            nonlocal output
            if isinstance(event, ScriptCompleted):
                output = event.output

        self._executor.run_script(script_path, params, None, None, emit_fn=local_emit)
        return output

    def _resolve_mapping(self, mapping: dict) -> dict:
        result = {}
        for key, expr in mapping.items():
            val = resolve_value(
                expr,
                self._step_outputs,
                is_step_outputs=True,
            )
            if val == "${choice}" and self._current_choice is not None:
                val = self._current_choice
            elif isinstance(val, str) and "${choice}" in val and self._current_choice is not None:
                val = val.replace("${choice}", str(self._current_choice))
            result[key] = val
        return result

    def _resolve_message(self, message: str) -> str:
        if "${" not in message:
            return message
        return resolve_value(message, self._step_outputs, is_step_outputs=True)
