"""TUI 自动化测试 — 使用 Textual 的 run_test() 驱动整个界面。"""
import asyncio
import pytest

from toolbox.core import ToolboxCore
from toolbox.core.events import PipelineMeta
from toolbox.frontend_tui.app import (
    ToolBoxTUI, ScriptMenu, ExecutionRecord, HistoryItem, InteractionPanel,
)
from textual.widgets import Button


def _make_core():
    """从实际 config.yaml 加载的 ToolboxCore。"""
    import pathlib
    config_path = str(pathlib.Path(__file__).parent.parent.parent / "config.yaml")
    core = ToolboxCore(config_path)
    try:
        core.load()
    except Exception:
        core = ToolboxCore.__new__(ToolboxCore)
        core._config_path = "config.yaml"
        core._config = {}
        core._scripts = []
        core._pipelines = []
        core._executor = None
        core._current_pipeline_engine = None
    return core


@pytest.fixture
def core():
    return _make_core()


def _output_text(app) -> str:
    widget = app.query_one("#output-panel")
    return widget.content if isinstance(widget.content, str) else str(widget.content)


# ── Basic UI ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_app_starts_and_shows_welcome(core):
    """TUI 启动后应显示欢迎信息。"""
    app = ToolBoxTUI(core)
    async with app.run_test() as pilot:
        await pilot.pause()
        fc = app.query_one("#form-container")
        assert not fc.has_class("hidden")
        oc = app.query_one("#output-container")
        assert oc.has_class("hidden")


@pytest.mark.asyncio
async def test_menu_contains_script_items(core):
    """侧边栏菜单应包含脚本条目。"""
    app = ToolBoxTUI(core)
    async with app.run_test() as pilot:
        await pilot.pause()
        menu = app.query_one(ScriptMenu)
        assert len(menu._id_map) > 0
        for safe_id, (item_type, name) in menu._id_map.items():
            assert safe_id.isascii()
            assert item_type in ("script", "pipeline")


# ── Form display ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_click_script_shows_form(core):
    app = ToolBoxTUI(core)
    async with app.run_test() as pilot:
        await pilot.pause()
        scripts = core.list_scripts()
        if not scripts:
            pytest.skip("没有可用的脚本")
        app._show_form(scripts[0])
        await pilot.pause()
        assert app._current_type == "script"
        fc = app.query_one("#form-container")
        assert not fc.has_class("hidden")


@pytest.mark.asyncio
async def test_callback_selects_script(core):
    app = ToolBoxTUI(core)
    async with app.run_test() as pilot:
        await pilot.pause()
        scripts = core.list_scripts()
        if not scripts:
            pytest.skip("没有可用的脚本")
        app._on_menu_select("script", scripts[0].name)
        await pilot.pause()
        assert app._current_type == "script"
        assert app._current_meta.name == scripts[0].name


@pytest.mark.asyncio
async def test_callback_selects_pipeline(core):
    app = ToolBoxTUI(core)
    async with app.run_test() as pilot:
        await pilot.pause()
        pipelines = core.list_pipelines()
        if not pipelines:
            pytest.skip("没有可用的流水线")
        app._on_menu_select("pipeline", pipelines[0].name)
        await pilot.pause()
        assert app._current_type == "pipeline"


# ── Execution ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_f9_executes_script(core):
    """按 F9 应执行脚本并创建执行记录。"""
    app = ToolBoxTUI(core)
    async with app.run_test() as pilot:
        await pilot.pause()
        scripts = core.list_scripts()
        target = next((s for s in scripts if not s.params), None)
        if target is None:
            pytest.skip("没有无参数脚本")

        app._on_menu_select("script", target.name)
        await pilot.pause()
        await pilot.press("f9")
        for _ in range(20):
            await pilot.pause(0.1)

        assert len(app._records) == 1
        record = list(app._records.values())[0]
        assert record.name == target.name
        assert record.get_line_count() > 0
        assert record.status in ("completed", "failed")


@pytest.mark.asyncio
async def test_execute_is_nonblocking(core):
    """执行应异步，F9 按下后 UI 保持响应。"""
    app = ToolBoxTUI(core)
    async with app.run_test() as pilot:
        await pilot.pause()
        scripts = core.list_scripts()
        target = next((s for s in scripts if not s.params), None)
        if target is None:
            pytest.skip("没有无参数脚本")

        app._on_menu_select("script", target.name)
        await pilot.pause()
        await pilot.press("f9")
        await pilot.pause()

        # UI still responds to F11 while running
        await pilot.press("f11")
        await pilot.pause()

        for _ in range(20):
            if not app._is_busy:
                break
            await pilot.pause(0.1)


@pytest.mark.asyncio
async def test_menu_navigation_during_execution(core):
    """执行期间菜单导航不被阻止。"""
    app = ToolBoxTUI(core)
    async with app.run_test() as pilot:
        await pilot.pause()
        scripts = core.list_scripts()
        if len(scripts) < 2:
            pytest.skip("需要至少两个脚本")

        app._on_menu_select("script", scripts[0].name)
        await pilot.pause()
        await pilot.press("f9")
        await pilot.pause(0.05)

        app._on_menu_select("script", scripts[1].name)
        await pilot.pause()
        assert app._current_meta.name == scripts[1].name

        for _ in range(20):
            if not app._is_busy:
                break
            await pilot.pause(0.1)


@pytest.mark.asyncio
async def test_execute_guard_without_selection(core):
    """未选择脚本时按 F9 不应执行。"""
    app = ToolBoxTUI(core)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app._current_meta is None
        await pilot.press("f9")
        await pilot.pause()
        assert len(app._records) == 0


@pytest.mark.asyncio
async def test_pipeline_interaction(core, tmp_dir):
    """验证流水线交互流程：显示 InteractionPanel -> 点击按钮 -> 继续执行。"""
    # 准备 Mock 环境
    scripts_dir = tmp_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / "hello.py").write_text("def main(): print('hello')\n", encoding="utf-8")
    
    # 注入一个 Mock 流水线
    mock_pipeline = PipelineMeta(
        name="MockInteraction",
        description="Test pipeline",
        steps=[
            {"id": "choose", "type": "prompt", "message": "选一个", "choices": [
                {"label": "Yes", "goto": "end"},
            ]},
            {"id": "end", "type": "end"},
        ],
        file_path=tmp_dir / "mock_pipe.yaml"
    )
    core._pipelines.append(mock_pipeline)

    app = ToolBoxTUI(core)
    async with app.run_test() as pilot:
        await pilot.pause()
        
        app._on_menu_select("pipeline", "MockInteraction")
        await pilot.pause()
        await pilot.press("f9")
        
        # 等待交互面板显示
        ip = app.query_one(InteractionPanel)
        for _ in range(50):
            if not ip.has_class("hidden"):
                break
            await pilot.pause(0.1)
        
        assert not ip.has_class("hidden")
        
        # 查找按钮并点击
        # Button ID 格式在 app.py 中定义为 f"choice-{i}"
        btn = ip.query(Button).first()
        await pilot.click(f"#{btn.id}")
        await pilot.pause()
        
        # 验证面板隐藏并任务完成
        for _ in range(30):
            if ip.has_class("hidden"):
                break
            await pilot.pause(0.1)
        
        assert ip.has_class("hidden")
        
        for _ in range(50):
            if not app._is_busy:
                break
            await pilot.pause(0.1)
        
        assert app._is_busy is False


# ── Execution records & history ──────────────────────────────────

@pytest.mark.asyncio
async def test_record_has_timestamp(core):
    """执行记录应有时间戳。"""
    from datetime import datetime
    app = ToolBoxTUI(core)
    async with app.run_test() as pilot:
        await pilot.pause()
        scripts = core.list_scripts()
        target = next((s for s in scripts if not s.params), None)
        if target is None:
            pytest.skip("没有无参数脚本")

        app._on_menu_select("script", target.name)
        await pilot.pause()
        await pilot.press("f9")
        for _ in range(20):
            await pilot.pause(0.1)

        record = list(app._records.values())[0]
        assert isinstance(record.timestamp, datetime)


@pytest.mark.asyncio
async def test_multiple_executions_create_records(core):
    """多次执行应创建多条记录。"""
    app = ToolBoxTUI(core)
    async with app.run_test() as pilot:
        await pilot.pause()
        scripts = core.list_scripts()
        target = next((s for s in scripts if not s.params), None)
        if target is None:
            pytest.skip("没有无参数脚本")

        for _ in range(2):
            app._on_menu_select("script", target.name)
            await pilot.pause()
            await pilot.press("f9")
            for i in range(20):
                if not app._is_busy:
                    break
                await pilot.pause(0.1)

        assert len(app._records) >= 2


@pytest.mark.asyncio
async def test_select_record_shows_output(core):
    """点击历史记录应显示对应输出。"""
    app = ToolBoxTUI(core)
    async with app.run_test() as pilot:
        await pilot.pause()
        scripts = core.list_scripts()
        target = next((s for s in scripts if not s.params), None)
        if target is None:
            pytest.skip("没有无参数脚本")

        app._on_menu_select("script", target.name)
        await pilot.pause()
        await pilot.press("f9")
        for _ in range(20):
            await pilot.pause(0.1)

        tid = list(app._records.keys())[0]
        record = app._records[tid]

        # Switch away then switch back
        app._on_menu_select("script", scripts[0].name)
        await pilot.pause()

        app._select_record(tid)
        text = _output_text(app)
        assert target.name in text


@pytest.mark.asyncio
async def test_history_items_in_panel(core):
    """执行后历史面板应有对应条目。"""
    app = ToolBoxTUI(core)
    async with app.run_test() as pilot:
        await pilot.pause()
        scripts = core.list_scripts()
        target = next((s for s in scripts if not s.params), None)
        if target is None:
            pytest.skip("没有无参数脚本")

        app._on_menu_select("script", target.name)
        await pilot.pause()
        await pilot.press("f9")
        for _ in range(20):
            await pilot.pause(0.1)

        panel = app.query_one("#history-panel")
        items = [c for c in panel.children if isinstance(c, HistoryItem)]
        assert len(items) == 1
        assert items[0]._record_tid == list(app._records.keys())[0]


# ── Keyboard shortcuts ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_f5_refreshes_menu(core):
    app = ToolBoxTUI(core)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("f5")
        await pilot.pause()
        menu = app.query_one(ScriptMenu)
        assert len(menu._id_map) > 0


@pytest.mark.asyncio
async def test_f11_fullscreen_toggle(core):
    app = ToolBoxTUI(core)
    async with app.run_test() as pilot:
        await pilot.pause()
        sidebar = app.query_one("#sidebar")
        assert not sidebar.has_class("hidden")
        await pilot.press("f11")
        await pilot.pause()
        assert sidebar.has_class("hidden")
        await pilot.press("f11")
        await pilot.pause()
        assert not sidebar.has_class("hidden")


@pytest.mark.asyncio
async def test_f12_toggles_history(core):
    """F12 应切换历史记录面板。"""
    app = ToolBoxTUI(core)
    async with app.run_test() as pilot:
        await pilot.pause()
        panel = app.query_one("#history-panel")
        assert panel.has_class("hidden")
        await pilot.press("f12")
        await pilot.pause()
        assert not panel.has_class("hidden")
        await pilot.press("f12")
        await pilot.pause()
        assert panel.has_class("hidden")


# ── Cancel & export ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cancel_stops_tasks(core):
    app = ToolBoxTUI(core)
    async with app.run_test() as pilot:
        await pilot.pause()
        scripts = core.list_scripts()
        if not scripts:
            pytest.skip("没有可用的脚本")
        app._on_menu_select("script", scripts[0].name)
        await pilot.pause()
        await pilot.press("f9")
        await pilot.pause(0.05)
        await pilot.press("ctrl+c")
        await pilot.pause(0.1)
        assert app._is_busy is False
        assert len(app._active_tasks) == 0


@pytest.mark.asyncio
async def test_cancel_during_idle(core):
    app = ToolBoxTUI(core)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app._is_busy is False
        app.action_cancel_execution()
        await pilot.pause()
        assert app._is_busy is False


@pytest.mark.asyncio
async def test_export_log(core):
    import os, glob
    app = ToolBoxTUI(core)
    async with app.run_test() as pilot:
        await pilot.pause()
        scripts = core.list_scripts()
        target = next((s for s in scripts if not s.params), None)
        if target is None:
            pytest.skip("没有无参数脚本")

        app._on_menu_select("script", target.name)
        await pilot.pause()
        await pilot.press("f9")
        for _ in range(20):
            await pilot.pause(0.1)

        app.action_export_log()
        await pilot.pause()

        record = list(app._records.values())[0]
        assert "已导出到" in record.get_text()

        for f in glob.glob("toolbox_output_*.log"):
            os.remove(f)


# ── Status & widget IDs ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_switch_script_no_duplicate_ids(core):
    app = ToolBoxTUI(core)
    async with app.run_test() as pilot:
        await pilot.pause()
        scripts = core.list_scripts()
        if len(scripts) < 2:
            pytest.skip("需要至少两个脚本")
        for s in scripts:
            app._on_menu_select("script", s.name)
            await pilot.pause()
        assert app._current_meta.name == scripts[-1].name


@pytest.mark.asyncio
async def test_param_widget_ids_are_unique(core):
    app = ToolBoxTUI(core)
    async with app.run_test() as pilot:
        await pilot.pause()
        scripts = core.list_scripts()
        if not scripts:
            pytest.skip("没有可用的脚本")
        app._show_form(scripts[0])
        await pilot.pause()
        ids_1 = dict(app._param_widget_ids)
        app._show_form(scripts[0])
        await pilot.pause()
        ids_2 = dict(app._param_widget_ids)
        for key in ids_1:
            if key in ids_2:
                assert ids_1[key] != ids_2[key]


@pytest.mark.asyncio
async def test_status_refresh(core):
    async def _hang():
        await asyncio.sleep(9999)

    app = ToolBoxTUI(core)
    async with app.run_test() as pilot:
        await pilot.pause()
        app._task_seq += 1
        tid = app._task_seq
        mock_task = asyncio.create_task(_hang())
        app._active_tasks[tid] = ("test_script", mock_task)
        app._refresh_status()
        assert app._is_busy is True
        assert "test_script" in app.sub_title
        mock_task.cancel()
        try:
            await mock_task
        except asyncio.CancelledError:
            pass
        app._active_tasks.pop(tid, None)
        app._refresh_status()
        assert app._is_busy is False


# ── ExecutionRecord unit tests ───────────────────────────────────

def test_record_tracks_lines():
    from datetime import datetime
    r = ExecutionRecord(1, "test")
    assert r.get_line_count() == 0
    assert r.status == "running"
    r.add_line("hello")
    r.add_line("world")
    assert r.get_line_count() == 2
    assert "hello" in r.get_text()
    assert "world" in r.get_text()
    assert isinstance(r.timestamp, datetime)


def test_record_export(tmp_path):
    r = ExecutionRecord(1, "test")
    r.add_line("line 1")
    r.add_line("line 2")
    p = str(tmp_path / "out.log")
    r.export(p)
    with open(p, encoding="utf-8") as f:
        assert "line 1" in f.read()
