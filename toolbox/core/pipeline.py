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


class PipelineEngine:
    def __init__(self, steps: list[dict], scripts_dir: str, project_root: str):
        self._steps = steps
        self._scripts_dir = Path(scripts_dir)
        self._project_root = project_root
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

        self._run_steps(emit)

    def _run_steps(self, emit):
        idx = 0
        while idx < len(self._steps):
            step = self._steps[idx]
            sid = step.get("id", f"step_{idx}")

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

                emit(PromptRequired(step_id=sid, message=message, choices=choices))

                wait_event = threading.Event()
                self._prompt_events[sid] = wait_event
                wait_event.wait()

                choice_label = self._prompt_responses.get(sid, "")

                if "goto_template" in step:
                    self._current_choice = choice_label
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
                emit(ConfirmRequired(step_id=sid, message=message))

                wait_event = threading.Event()
                self._prompt_events[sid] = wait_event
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
            result[key] = resolve_value(
                expr,
                self._step_outputs,
                is_step_outputs=True,
            )
        return result

    def _resolve_message(self, message: str) -> str:
        if "${" not in message:
            return message
        return resolve_value(message, self._step_outputs, is_step_outputs=True)
