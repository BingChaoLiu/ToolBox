from __future__ import annotations

import asyncio
import concurrent.futures
import importlib.util
import io
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Callable

import psutil

from lib.cancel import reset as reset_cancel
from lib.logger import logger
from toolbox.core.events import (
    ScriptStarted, ScriptOutput, ScriptCompleted, ScriptFailed, ExecutionEnded,
    ResourceUpdate
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

    def run_script(self, script_path: str, params: dict, loop: asyncio.AbstractEventLoop | None, 
                   event_queue: asyncio.Queue | None, emit_fn: Callable | None = None, 
                   timeout: int | None = None):
        self._current_script = Path(script_path).stem
        reset_cancel()
        
        logger.info(f"开始执行脚本: {self._current_script} (timeout={timeout})")

        if emit_fn:
            emit = emit_fn
        else:
            def emit(event):
                if loop and event_queue:
                    try:
                        loop.call_soon_threadsafe(event_queue.put_nowait, event)
                    except Exception:
                        pass # 容错处理，防止 loop 关闭后报错

        emit(ScriptStarted(script_name=self._current_script))

        capture = OutputCapture(lambda line: emit(ScriptOutput(
            script_name=self._current_script, line=line,
        )))

        # 资源监控逻辑
        cpu_peak = 0.0
        mem_peak = 0.0
        monitor_stop = threading.Event()
        
        def resource_monitor():
            nonlocal cpu_peak, mem_peak
            try:
                process = psutil.Process()
                # 预热第一次调用，避免首次返回 0
                psutil.cpu_percent(interval=None)
                while not monitor_stop.is_set():
                    cpu = psutil.cpu_percent(interval=None)
                    mem_info = process.memory_info()
                    mem_mb = mem_info.rss / (1024 * 1024)
                    mem_p = psutil.virtual_memory().percent
                    
                    cpu_peak = max(cpu_peak, cpu)
                    mem_peak = max(mem_peak, mem_mb)
                    
                    emit(ResourceUpdate(
                        cpu_percent=cpu,
                        memory_percent=mem_p,
                        memory_mb=mem_mb
                    ))
                    time.sleep(1.0)
            except Exception as e:
                logger.debug(f"资源监控线程异常: {e}")

        monitor_thread = threading.Thread(target=resource_monitor, name=f"Monitor-{self._current_script}", daemon=True)
        monitor_thread.start()

        original_stdout = sys.stdout
        sys.stdout = capture
        start = time.time()
        
        try:
            main_fn = self.load_script(script_path)
            
            if timeout is None:
                result = main_fn(**params)
            else:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as thread_pool:
                    future = thread_pool.submit(main_fn, **params)
                    try:
                        result = future.result(timeout=timeout)
                    except concurrent.futures.TimeoutError:
                        error_msg = f"脚本执行超时 (>{timeout}s)"
                        logger.error(f"{self._current_script}: {error_msg}")
                        emit(ScriptFailed(
                            script_name=self._current_script,
                            error=error_msg,
                            traceback=f"TimeoutError: Execution exceeded {timeout} seconds",
                        ))
                        return

            if result is None:
                result = {}
            elif not isinstance(result, dict):
                result = {"result": result}
            
            duration = time.time() - start
            logger.info(f"脚本执行成功: {self._current_script} (耗时 {duration:.2f}s, CPU峰值: {cpu_peak}%, 内存峰值: {mem_peak:.1f}MB)")
            emit(ScriptCompleted(
                script_name=self._current_script,
                output=result,
                duration=duration,
                cpu_peak=cpu_peak,
                mem_peak=mem_peak
            ))
        except Exception as e:
            tb = traceback.format_exc()
            logger.error(f"脚本执行失败: {self._current_script}\n错误: {e}\n{tb}")
            emit(ScriptFailed(
                script_name=self._current_script,
                error=str(e),
                traceback=tb,
            ))
        finally:
            monitor_stop.set()
            capture.flush_remaining()
            sys.stdout = original_stdout
            emit(ExecutionEnded())
