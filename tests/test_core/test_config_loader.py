import pytest
import yaml

from toolbox.core.config_loader import load_config, resolve_value


class TestLoadConfig:
    def test_loads_yaml_file(self, tmp_dir):
        config_file = tmp_dir / "test.yaml"
        config_file.write_text(yaml.dump({"a": {"b": 1}}), encoding="utf-8")
        result = load_config(str(config_file))
        assert result == {"a": {"b": 1}}

    def test_raises_on_missing_file(self, tmp_dir):
        with pytest.raises(FileNotFoundError):
            load_config(str(tmp_dir / "missing.yaml"))


class TestResolveReferences:
    def test_resolves_dollar_brace_reference(self, tmp_dir):
        config_file = tmp_dir / "test.yaml"
        raw = {
            "base": {"path": "/tmp/project"},
            "derived": {"path": "${base.path}"},
        }
        config_file.write_text(yaml.dump(raw), encoding="utf-8")
        result = load_config(str(config_file))
        assert result["derived"]["path"] == "/tmp/project"

    def test_resolves_nested_reference(self, tmp_dir):
        config_file = tmp_dir / "test.yaml"
        raw = {
            "level1": {"val": "hello"},
            "level2": {"val": "${level1.val}"},
            "level3": {"val": "${level2.val}"},
        }
        config_file.write_text(yaml.dump(raw), encoding="utf-8")
        result = load_config(str(config_file))
        assert result["level3"]["val"] == "hello"

    def test_detects_circular_reference(self, tmp_dir):
        config_file = tmp_dir / "test.yaml"
        raw = {
            "a": {"val": "${b.val}"},
            "b": {"val": "${a.val}"},
        }
        config_file.write_text(yaml.dump(raw), encoding="utf-8")
        with pytest.raises(ValueError, match="circular"):
            load_config(str(config_file))

    def test_preserves_non_string_values(self, tmp_dir):
        config_file = tmp_dir / "test.yaml"
        raw = {"count": 42, "flag": True, "items": [1, 2, 3]}
        config_file.write_text(yaml.dump(raw), encoding="utf-8")
        result = load_config(str(config_file))
        assert result["count"] == 42
        assert result["flag"] is True
        assert result["items"] == [1, 2, 3]


class TestResolveValue:
    def test_resolves_config_prefix(self, tmp_dir):
        config_file = tmp_dir / "test.yaml"
        raw = {"addr2line": {"default_so": "/tmp/libapp.so"}}
        config_file.write_text(yaml.dump(raw), encoding="utf-8")
        config = load_config(str(config_file))
        result = resolve_value("config:addr2line.default_so", config)
        assert result == "/tmp/libapp.so"

    def test_returns_literal_when_no_prefix(self):
        result = resolve_value("hello world", {})
        assert result == "hello world"

    def test_resolves_steps_prefix(self):
        step_outputs = {"check_remote": {"new_commits": 5}}
        result = resolve_value("${steps.check_remote.new_commits}", step_outputs, is_step_outputs=True)
        assert result == 5

    def test_string_interpolation_preserves_type_for_pure_expression(self):
        step_outputs = {"check": {"count": 5}}
        result = resolve_value("${steps.check.count}", step_outputs, is_step_outputs=True)
        assert result == 5
        assert isinstance(result, int)

    def test_string_interpolation_converts_when_embedded(self):
        step_outputs = {"check": {"count": 5}}
        result = resolve_value("total: ${steps.check.count}", step_outputs, is_step_outputs=True)
        assert result == "total: 5"
        assert isinstance(result, str)
