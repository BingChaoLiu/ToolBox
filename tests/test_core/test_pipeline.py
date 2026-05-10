import asyncio
import threading

from toolbox.core.events import (
    ScriptStarted, ScriptOutput, ScriptCompleted, ExecutionEnded,
    PromptRequired, PipelineCompleted,
)
from toolbox.core.pipeline import PipelineEngine


def _make_scripts_dir(tmp_dir):
    sd = tmp_dir / "scripts"
    sd.mkdir()
    (sd / "step1.py").write_text(
        "def main():\n    print('step1')\n    return {'value': 42}\n", encoding="utf-8"
    )
    (sd / "step2.py").write_text(
        "def main(count=None):\n    print(f'step2 got {count}')\n    return {'doubled': int(count) * 2}\n", encoding="utf-8"
    )
    (sd / "echo.py").write_text(
        "def main(msg=None):\n    print(msg or 'echo')\n    return {'msg': msg}\n", encoding="utf-8"
    )
    return sd


def _run_pipeline_collect(steps, scripts_dir, respond_fn=None):
    loop = asyncio.new_event_loop()
    queue = asyncio.Queue()
    collector = []
    engine = PipelineEngine(
        steps=steps,
        scripts_dir=str(scripts_dir),
        project_root=str(scripts_dir.parent),
    )

    async def _collect():
        while True:
            event = await queue.get()
            collector.append(event)
            if isinstance(event, (ExecutionEnded, PipelineCompleted)):
                break
            if isinstance(event, PromptRequired) and respond_fn:
                respond_fn(engine, event)

    def _run():
        engine.run(loop, queue)

    t = threading.Thread(target=_run)
    t.start()
    loop.run_until_complete(_collect())
    t.join(timeout=10)
    loop.close()
    return collector


class TestPipelineSequential:
    def test_runs_steps_in_order(self, tmp_dir):
        scripts_dir = _make_scripts_dir(tmp_dir)
        steps = [
            {"id": "s1", "script": "step1"},
            {"id": "s2", "script": "step2", "mapping": {"count": "${steps.s1.value}"}},
            {"id": "end", "type": "end"},
        ]
        events = _run_pipeline_collect(steps, scripts_dir)
        outputs = [e for e in events if isinstance(e, ScriptOutput)]
        texts = [e.line for e in outputs]
        assert "step1" in texts
        assert "step2 got 42" in texts

    def test_mapping_preserves_type(self, tmp_dir):
        scripts_dir = _make_scripts_dir(tmp_dir)
        steps = [
            {"id": "s1", "script": "step1"},
            {"id": "s2", "script": "step2", "mapping": {"count": "${steps.s1.value}"}},
            {"id": "end", "type": "end"},
        ]
        events = _run_pipeline_collect(steps, scripts_dir)
        completed = [e for e in events if isinstance(e, ScriptCompleted) and e.script_name == "step2"]
        assert completed[0].output["doubled"] == 84


class TestPipelineEnd:
    def test_end_step_stops_pipeline(self, tmp_dir):
        scripts_dir = _make_scripts_dir(tmp_dir)
        steps = [
            {"id": "s1", "script": "step1"},
            {"id": "end", "type": "end"},
            {"id": "s2", "script": "step2"},
        ]
        events = _run_pipeline_collect(steps, scripts_dir)
        names = [e.script_name for e in events if isinstance(e, ScriptStarted)]
        assert "step2" not in names


class TestPipelinePrompt:
    def test_prompt_emits_prompt_required(self, tmp_dir):
        scripts_dir = _make_scripts_dir(tmp_dir)
        steps = [
            {"id": "choose", "type": "prompt", "message": "选一个", "choices": [
                {"label": "Echo Hello", "goto": "echo"},
                {"label": "End", "goto": "end"},
            ]},
            {"id": "echo", "script": "echo", "mapping": {"msg": "${choice}"}},
            {"id": "end", "type": "end"},
        ]

        def respond(engine, event):
            engine.respond_prompt(event.step_id, "Echo Hello")

        events = _run_pipeline_collect(steps, scripts_dir, respond_fn=respond)
        prompt_events = [e for e in events if isinstance(e, PromptRequired)]
        assert len(prompt_events) == 1
        assert "Echo Hello" in prompt_events[0].choices
