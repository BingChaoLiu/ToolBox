import pytest
import yaml

from toolbox.core.discovery import discover_scripts, discover_pipelines, validate_pipeline


class TestDiscoverScripts:
    def test_finds_py_files(self, tmp_dir):
        scripts = tmp_dir / "scripts"
        scripts.mkdir()
        (scripts / "hello.py").write_text("def main(): pass", encoding="utf-8")
        (scripts / "world.py").write_text("def main(): pass", encoding="utf-8")
        (scripts / "ignored.txt").write_text("not a script", encoding="utf-8")

        result = discover_scripts(str(scripts))
        names = [m.name for m in result]
        assert "hello" in names
        assert "world" in names
        assert len(result) == 2

    def test_script_without_manifest_is_tier1(self, tmp_dir):
        scripts = tmp_dir / "scripts"
        scripts.mkdir()
        (scripts / "bare.py").write_text("def main(): pass", encoding="utf-8")

        result = discover_scripts(str(scripts))
        meta = result[0]
        assert meta.name == "bare"
        assert meta.has_manifest is False
        assert meta.params == []

    def test_script_with_manifest_parses_params(self, tmp_dir):
        scripts = tmp_dir / "scripts"
        scripts.mkdir()
        (scripts / "addr2line.py").write_text("def main(address=None): pass", encoding="utf-8")
        manifest = {
            "name": "崩溃地址分析",
            "category": "调试",
            "params": [
                {"name": "address", "label": "崩溃地址", "type": "text", "clipboard": True},
            ],
            "outputs": ["result"],
        }
        (scripts / "addr2line.yaml").write_text(yaml.dump(manifest), encoding="utf-8")

        result = discover_scripts(str(scripts))
        meta = result[0]
        assert meta.name == "崩溃地址分析"
        assert meta.category == "调试"
        assert meta.has_manifest is True
        assert len(meta.params) == 1
        assert meta.params[0].name == "address"
        assert meta.params[0].clipboard is True
        assert meta.outputs == ["result"]

    def test_empty_scripts_dir_returns_empty(self, tmp_dir):
        scripts = tmp_dir / "scripts"
        scripts.mkdir()
        result = discover_scripts(str(scripts))
        assert result == []


class TestDiscoverPipelines:
    def test_finds_yaml_files(self, tmp_dir):
        pipelines = tmp_dir / "pipelines"
        pipelines.mkdir()
        pipeline_def = {
            "name": "测试流水线",
            "steps": [
                {"id": "step1", "script": "hello"},
                {"id": "end", "type": "end"},
            ],
        }
        (pipelines / "test.yaml").write_text(yaml.dump(pipeline_def), encoding="utf-8")

        result = discover_pipelines(str(pipelines))
        assert len(result) == 1
        assert result[0].name == "测试流水线"

    def test_empty_dir_returns_empty(self, tmp_dir):
        pipelines = tmp_dir / "pipelines"
        pipelines.mkdir()
        result = discover_pipelines(str(pipelines))
        assert result == []


class TestValidatePipeline:
    def test_valid_pipeline_no_warnings(self):
        steps = [
            {"id": "check", "script": "git_check"},
            {"id": "end", "type": "end"},
        ]
        available_scripts = ["git_check"]
        warnings = validate_pipeline(steps, available_scripts)
        assert warnings == []

    def test_warns_on_missing_script(self):
        steps = [
            {"id": "check", "script": "nonexistent_script"},
            {"id": "end", "type": "end"},
        ]
        available_scripts = ["git_check"]
        warnings = validate_pipeline(steps, available_scripts)
        assert any("nonexistent_script" in w for w in warnings)

    def test_warns_on_script_and_type_together(self):
        steps = [
            {"id": "bad", "script": "git_check", "type": "prompt"},
        ]
        available_scripts = ["git_check"]
        warnings = validate_pipeline(steps, available_scripts)
        assert any("互斥" in w for w in warnings)

    def test_warns_on_invalid_goto(self):
        steps = [
            {"id": "choose", "type": "prompt", "choices": [
                {"label": "Go", "goto": "nonexistent_step"},
            ]},
        ]
        available_scripts = []
        warnings = validate_pipeline(steps, available_scripts)
        assert any("nonexistent_step" in w for w in warnings)
