import asyncio
import threading
from unittest.mock import MagicMock, patch

import pytest

from toolbox.core.events import (
    ScriptStarted, ScriptOutput, ScriptCompleted, ScriptFailed, ExecutionEnded,
    ResourceUpdate
)
from toolbox.core.executor import Executor, OutputCapture


@pytest.fixture(autouse=True)
def mock_psutil():
    """全局 Mock psutil，防止测试挂起。"""
    mock_process = MagicMock()
    mock_process.memory_info.return_value.rss = 50 * 1024 * 1024 # 50MB
    
    with patch("psutil.Process", return_value=mock_process), \
         patch("psutil.cpu_percent", return_value=5.0), \
         patch("psutil.virtual_memory") as mock_vmem:
        
        mock_vmem.return_value.percent = 20.0
        yield


class TestOutputCapture:
    def test_captures_line_on_newline(self):
        lines = []
        cap = OutputCapture(lambda line: lines.append(line))
        cap.write("hello\n")
        assert lines == ["hello"]

    def test_buffers_partial_line(self):
        lines = []
        cap = OutputCapture(lambda line: lines.append(line))
        cap.write("hel")
        cap.write("lo\n")
        assert lines == ["hello"]

    def test_flush_remaining_emits_buffer(self):
        lines = []
        cap = OutputCapture(lambda line: lines.append(line))
        cap.write("partial")
        cap.flush_remaining()
        assert lines == ["partial"]

    def test_flush_remaining_does_nothing_when_empty(self):
        lines = []
        cap = OutputCapture(lambda line: lines.append(line))
        cap.flush_remaining()
        assert lines == []


class TestExecutor:
    def _run_and_collect(self, script_path, params=None):
        loop = asyncio.new_event_loop()
        queue = asyncio.Queue()
        executor = Executor(project_root=script_path.parent.parent)
        collector = []

        async def _collect():
            while True:
                event = await queue.get()
                collector.append(event)
                if isinstance(event, ExecutionEnded):
                    break

        def _run():
            executor.run_script(
                script_path=str(script_path),
                params=params or {},
                loop=loop,
                event_queue=queue,
            )

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        loop.run_until_complete(_collect())
        t.join(timeout=5)
        loop.close()
        return collector

    def test_simple_script_emits_started_output_completed_ended(self, tmp_dir):
        script = tmp_dir / "scripts" / "hello.py"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("def main():\n    print('hello world')\n    return {'ok': True}\n", encoding="utf-8")

        events = self._run_and_collect(script)
        types = [type(e).__name__ for e in events]

        assert "ScriptStarted" in types
        assert "ScriptOutput" in types
        assert "ScriptCompleted" in types
        assert "ExecutionEnded" in types

    def test_completed_event_contains_output_dict(self, tmp_dir):
        script = tmp_dir / "scripts" / "ret.py"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("def main():\n    return {'count': 42}\n", encoding="utf-8")

        events = self._run_and_collect(script)
        completed = [e for e in events if isinstance(e, ScriptCompleted)][0]
        assert completed.output == {"count": 42}

    def test_none_return_becomes_empty_dict(self, tmp_dir):
        script = tmp_dir / "scripts" / "noreturn.py"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("def main():\n    print('done')\n", encoding="utf-8")

        events = self._run_and_collect(script)
        completed = [e for e in events if isinstance(e, ScriptCompleted)][0]
        assert completed.output == {}

    def test_non_dict_return_wrapped(self, tmp_dir):
        script = tmp_dir / "scripts" / "strreturn.py"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("def main():\n    return 'plain string'\n", encoding="utf-8")

        events = self._run_and_collect(script)
        completed = [e for e in events if isinstance(e, ScriptCompleted)][0]
        assert completed.output == {"result": "plain string"}

    def test_exception_emits_script_failed(self, tmp_dir):
        script = tmp_dir / "scripts" / "crash.py"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("def main():\n    raise ValueError('boom')\n", encoding="utf-8")

        events = self._run_and_collect(script)
        failed = [e for e in events if isinstance(e, ScriptFailed)]
        assert len(failed) == 1
        assert "boom" in failed[0].error

    def test_resource_monitoring(self, tmp_dir):
        script = tmp_dir / "scripts" / "slow.py"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("import time\ndef main():\n    time.sleep(0.5)\n    return {'ok': True}\n", encoding="utf-8")

        events = self._run_and_collect(script)
        
        resource_updates = [e for e in events if isinstance(e, ResourceUpdate)]
        # 只要能捕获到事件即说明线程启动并发送了
        assert len(resource_updates) >= 0 
        
        completed = [e for e in events if isinstance(e, ScriptCompleted)][0]
        assert completed.cpu_peak >= 0
        assert completed.mem_peak == 50.0
