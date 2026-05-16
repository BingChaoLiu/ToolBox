from __future__ import annotations

import asyncio
import threading
from pathlib import Path

from toolbox.core.config_loader import load_config
from toolbox.core.discovery import discover_scripts, discover_pipelines, validate_pipeline
from toolbox.core.executor import Executor
from toolbox.core.pipeline import PipelineEngine
from toolbox.core.events import ScriptMeta, PipelineMeta
from lib.logger import logger


class ToolboxCore:
    def __init__(self, config_path: str):
        self._config_path = config_path
        self._config = {}
        self._scripts: list[ScriptMeta] = []
        self._pipelines: list[PipelineMeta] = []
        self._executor = Executor()
        self._active_engines: dict[int, PipelineEngine] = {}
        logger.info(f"ToolboxCore 初始化，配置路径: {config_path}")

    def load(self):
        try:
            self._config = load_config(self._config_path)
            self._reload_discovery()
            logger.info("配置与脚本加载完成")
        except Exception as e:
            logger.error(f"加载失败: {e}")
            raise

    def reload(self):
        logger.info("手动刷新菜单 (Reload)")
        self._reload_discovery()

    def _reload_discovery(self):
        root = Path(self._config_path).parent
        self._scripts = discover_scripts(str(root / "scripts"))
        self._pipelines = discover_pipelines(str(root / "pipelines"))
        script_names = [s.name for s in self._scripts]
        script_names += [s.script_path.stem for s in self._scripts]
        for p in self._pipelines:
            p._warnings = validate_pipeline(p.steps, script_names)
        logger.info(f"发现 {len(self._scripts)} 个脚本，{len(self._pipelines)} 条流水线")

    def list_scripts(self) -> list[ScriptMeta]:
        return self._scripts

    def list_pipelines(self) -> list[PipelineMeta]:
        return self._pipelines

    def get_config(self) -> dict:
        return self._config

    def run_script(self, name: str, params: dict) -> asyncio.Queue:
        queue = asyncio.Queue()
        script_meta = next((s for s in self._scripts if s.name == name), None)
        if script_meta is None:
            script_meta = next((s for s in self._scripts if s.script_path.stem == name), None)

        if script_meta is None:
            loop = asyncio.get_event_loop()
            from toolbox.core.events import ScriptFailed, ExecutionEnded
            loop.call_soon_threadsafe(queue.put_nowait, ScriptFailed(
                script_name=name, error=f"脚本 '{name}' 不存在",
            ))
            loop.call_soon_threadsafe(queue.put_nowait, ExecutionEnded())
            return queue

        loop = asyncio.get_event_loop()
        root = Path(self._config_path).parent
        self._executor = Executor(project_root=str(root))
        thread = threading.Thread(
            target=self._executor.run_script,
            args=(str(script_meta.script_path), params, loop, queue),
            kwargs={"timeout": script_meta.timeout},
            daemon=True,
        )
        thread.start()
        return queue

    def run_pipeline(self, name: str, tid: int = 0) -> asyncio.Queue:
        queue = asyncio.Queue()
        pipeline_meta = next((p for p in self._pipelines if p.name == name), None)
        if pipeline_meta is None:
            loop = asyncio.get_event_loop()
            from toolbox.core.events import ScriptFailed, ExecutionEnded
            loop.call_soon_threadsafe(queue.put_nowait, ScriptFailed(
                script_name=name, error=f"流水线 '{name}' 不存在",
            ))
            loop.call_soon_threadsafe(queue.put_nowait, ExecutionEnded())
            return queue

        loop = asyncio.get_event_loop()
        root = Path(self._config_path).parent
        engine = PipelineEngine(
            steps=pipeline_meta.steps,
            scripts_dir=str(root / "scripts"),
            project_root=str(root),
            tid=tid
        )
        self._active_engines[tid] = engine
        thread = threading.Thread(
            target=engine.run,
            args=(loop, queue),
            daemon=True,
        )
        thread.start()
        return queue

    def respond_prompt(self, tid: int, step_id: str, choice: str):
        engine = self._active_engines.get(tid)
        if engine:
            engine.respond_prompt(step_id, choice)

    def respond_confirm(self, tid: int, step_id: str, confirmed: bool):
        engine = self._active_engines.get(tid)
        if engine:
            engine.respond_confirm(step_id, confirmed)

    def cleanup_engine(self, tid: int):
        """流水线执行结束后清理对应的引擎引用。"""
        self._active_engines.pop(tid, None)

    def cancel(self):
        from lib.cancel import request_cancel
        request_cancel()
        # 通知所有活跃的流水线引擎中止
        for tid, engine in list(self._active_engines.items()):
            engine.cancel()
        self._active_engines.clear()
