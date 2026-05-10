from __future__ import annotations

import asyncio
import threading
from pathlib import Path

from toolbox.core.events import (
    ScriptCompleted, ScriptFailed,
    PromptRequired, ConfirmRequired, PipelineCompleted, ExecutionEnded,
)
from toolbox.core.executor import Executor
from toolbox.core.config_loader import resolve_value
from lib.logger import logger


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

    def respond_prompt(self, step_id: str, choice: str):
        self._prompt_responses[step_id] = choice
        self._current_choice = choice
        if step_id in self._prompt_events:
            self._prompt_events[step_id].set()

    def respond_confirm(self, step_id: str, confirmed: bool):
        self._prompt_responses[step_id] = "yes" if confirmed else "no"
        if step_id in self._prompt_events:
            self._prompt_events[step_id].set()

    def run(self, loop: asyncio.AbstractEventLoop, event_queue: asyncio.Queue):
        def emit(event):
            loop.call_soon_threadsafe(event_queue.put_nowait, event)

        logger.info(f"流水线引擎启动 (tid={self._tid})")
        self._run_steps(emit)

    def _run_steps(self, emit):
        idx = 0
        while idx < len(self._steps):
            step = self._steps[idx]
            sid = step.get("id", f"step_{idx}")

            # Check condition
            condition = step.get("if")
            if condition:
                resolved_cond = resolve_value(condition, self._step_outputs, is_step_outputs=True)
                try:
                    # 如果 resolve_value 返回的是 bool 以外的类型（比如字符串表达式），尝试 eval
                    if isinstance(resolved_cond, str):
                        # 简单安全检查：只允许基本的比较运算和逻辑运算
                        # 这里为了灵活性暂时使用 eval，但在生产商业版中建议使用专用的表达式解析器
                        should_run = eval(resolved_cond, {"__builtins__": {}}, {})
                    else:
                        should_run = bool(resolved_cond)
                except Exception as e:
                    logger.error(f"步骤 '{sid}' 条件解析失败: {condition} -> {resolved_cond}, 错误: {e}")
                    should_run = True # 默认执行

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

                # 先创建 Event，防止 respond_prompt 先于 wait() 执行导致死锁
                wait_event = threading.Event()
                self._prompt_events[sid] = wait_event

                emit(PromptRequired(tid=self._tid, step_id=sid, message=message, choices=choices))

                wait_event.wait()

                choice_label = self._prompt_responses.get(sid, "")
                self._current_choice = choice_label # 确保当前选择被记录

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
            # 处理特殊的 ${choice} 变量
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
