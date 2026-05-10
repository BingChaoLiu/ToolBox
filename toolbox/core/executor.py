from __future__ import annotations

import asyncio
import importlib.util
import io
import sys
import time
import traceback
from pathlib import Path

from lib.cancel import reset as reset_cancel
from toolbox.core.events import (
    ScriptStarted, ScriptOutput, ScriptCompleted, ScriptFailed, ExecutionEnded,
)


class OutputCapture(io.TextIOBase):
    def __init__(self, callback):
        self._callback = callback
        self._buffer = ""

    def write(self, text):
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self._callback(line)
        return len(text)

    def flush(self):
        pass

    def flush_remaining(self):
        if self._buffer:
            self._callback(self._buffer)
            self._buffer = ""

    @property
    def encoding(self):
        return "utf-8"


class Executor:
    def __init__(self, project_root: str | None = None):
        self._project_root = Path(project_root) if project_root else Path(".")
        self._current_script = ""

    def load_script(self, script_path: str):
        path = Path(script_path)
        spec = importlib.util.spec_from_file_location(
            f"toolbox_script_{path.stem}",
            path,
        )
        mod = importlib.util.module_from_spec(spec)
        root = str(self._project_root)
        if root not in sys.path:
            sys.path.insert(0, root)
        spec.loader.exec_module(mod)
        return mod.main

    def run_script(self, script_path: str, params: dict, loop: asyncio.AbstractEventLoop, event_queue: asyncio.Queue):
        self._current_script = Path(script_path).stem
        reset_cancel()

        def emit(event):
            loop.call_soon_threadsafe(event_queue.put_nowait, event)

        emit(ScriptStarted(script_name=self._current_script))

        capture = OutputCapture(lambda line: emit(ScriptOutput(
            script_name=self._current_script, line=line,
        )))

        original_stdout = sys.stdout
        sys.stdout = capture
        start = time.time()
        try:
            main_fn = self.load_script(script_path)
            result = main_fn(**params)
            if result is None:
                result = {}
            elif not isinstance(result, dict):
                result = {"result": result}
            duration = time.time() - start
            emit(ScriptCompleted(
                script_name=self._current_script,
                output=result,
                duration=duration,
            ))
        except Exception as e:
            emit(ScriptFailed(
                script_name=self._current_script,
                error=str(e),
                traceback=traceback.format_exc(),
            ))
        finally:
            capture.flush_remaining()
            sys.stdout = original_stdout
            emit(ExecutionEnded())
