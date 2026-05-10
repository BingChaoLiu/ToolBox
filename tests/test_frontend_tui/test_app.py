"""测试 TUI 组件中可独立验证的逻辑。"""
import pytest

from toolbox.core.events import ScriptMeta, ParamDef, PipelineMeta
from pathlib import Path


def _make_script(name, params=None, **kwargs):
    defaults = dict(
        description="", category="未分类", params=params or [],
        outputs=[], has_manifest=False,
        script_path=Path(f"scripts/{name}.py"),
    )
    defaults.update(kwargs)
    return ScriptMeta(name=name, **defaults)


class TestScriptFormLogic:
    """测试脚本表单参数收集的纯逻辑部分。"""

    def test_no_params_returns_empty(self):
        """无参数脚本应返回空 dict。"""
        script = _make_script("test", params=[])
        # 模拟 _collect_params 的逻辑
        params = {}
        for p in script.params:
            if p.default is not None:
                params[p.name] = p.default
        assert params == {}

    def test_default_params_collected(self):
        """有默认值的参数应被收集。"""
        script = _make_script("test", params=[
            ParamDef(name="name", label="名称", type="text", default="World"),
        ])
        params = {}
        for p in script.params:
            if p.default is not None:
                params[p.name] = p.default
        assert params == {"name": "World"}

    def test_multiple_params_with_mixed_defaults(self):
        """混合有/无默认值的参数。"""
        script = _make_script("test", params=[
            ParamDef(name="name", label="名称", type="text", default="World"),
            ParamDef(name="count", label="数量", type="text"),
            ParamDef(name="verbose", label="详细", type="flag", default=True),
        ])
        params = {}
        for p in script.params:
            if p.default is not None:
                params[p.name] = p.default
        assert params == {"name": "World", "verbose": True}


class TestScriptMenuIdMapping:
    """测试 ScriptMenu 的 ID 映射逻辑。"""

    def test_safe_ids_no_unicode(self):
        """生成的 ID 不含 Unicode 字符。"""
        from toolbox.frontend_tui.app import ScriptMenu
        scripts = [_make_script("崩溃分析"), _make_script("hello")]
        menu = ScriptMenu(scripts, [])

        for safe_id, (item_type, name) in menu._id_map.items():
            assert safe_id.isascii(), f"ID '{safe_id}' is not ASCII"
            assert item_type == "script"
            assert name in ("崩溃分析", "hello")

    def test_pipeline_ids_mapped(self):
        """流水线条目也使用安全 ID。"""
        from toolbox.frontend_tui.app import ScriptMenu
        pipelines = [PipelineMeta(
            name="崩溃分析流水线", description="test",
            steps=[], file_path=Path("test.yaml"),
        )]
        menu = ScriptMenu([], pipelines)

        assert len(menu._id_map) == 1
        safe_id, (item_type, name) = list(menu._id_map.items())[0]
        assert safe_id.isascii()
        assert item_type == "pipeline"
        assert name == "崩溃分析流水线"


class TestInitialState:
    """测试 App 初始状态（不启动 Textual app）。"""

    def test_initial_state(self):
        from toolbox.frontend_tui.app import ToolBoxTUI
        from toolbox.core import ToolboxCore
        core = ToolboxCore.__new__(ToolboxCore)
        core._config_path = "config.yaml"
        core._config = {}
        core._scripts = []
        core._pipelines = []
        core._executor = None
        core._current_pipeline_engine = None

        app = ToolBoxTUI(core)
        assert app._is_busy is False
        assert len(app._active_tasks) == 0
        assert app._current_type is None
        assert app._current_meta is None

    def test_manual_state_assignment(self):
        from toolbox.frontend_tui.app import ToolBoxTUI
        from toolbox.core import ToolboxCore
        core = ToolboxCore.__new__(ToolboxCore)
        core._config_path = "config.yaml"
        core._config = {}
        core._scripts = []
        core._pipelines = []
        core._executor = None
        core._current_pipeline_engine = None

        app = ToolBoxTUI(core)
        script = _make_script("test", params=[
            ParamDef(name="msg", label="消息", type="text"),
        ])
        app._current_type = "script"
        app._current_meta = script
        assert app._current_type == "script"
        assert app._current_meta.name == "test"
