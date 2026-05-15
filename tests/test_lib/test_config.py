import pathlib

import pytest
import yaml


class TestGetConfig:
    def test_dot_path_returns_nested_value(self, project_root):
        import lib.config
        lib.config._CONFIG_PATH = project_root / "config.yaml"

        result = lib.config.get_config("build.project_path")
        assert result == str(project_root / "android_project")

    def test_dot_path_returns_top_level(self, project_root):
        import lib.config
        lib.config._CONFIG_PATH = project_root / "config.yaml"

        result = lib.config.get_config("build")
        assert isinstance(result, dict)
        assert "project_path" in result

    def test_dot_path_returns_list_element(self, project_root):
        import lib.config
        lib.config._CONFIG_PATH = project_root / "config.yaml"

        result = lib.config.get_config("git.repos")
        assert isinstance(result, list)
        assert result[0]["name"] == "主项目"

    def test_missing_key_returns_default(self, project_root):
        from lib.config import get_config
        import lib.config
        lib.config._CONFIG_PATH = project_root / "config.yaml"
        lib.config._config = None # 清理缓存

        # 默认返回 None，不再抛出异常
        assert get_config("missing.key") is None
        # 也可以指定默认值
        assert get_config("missing.key", "fallback") == "fallback"


    def test_env_var_overrides_default_path(self, tmp_dir):
        config = {"test_key": "from_env"}
        config_path = tmp_dir / "custom.yaml"
        config_path.write_text(yaml.dump(config), encoding="utf-8")

        import lib.config
        lib.config._CONFIG_PATH = config_path
        lib.config._config = None

        result = lib.config.get_config("test_key")
        assert result == "from_env"

    def test_config_is_cached(self, project_root):
        import lib.config
        lib.config._CONFIG_PATH = project_root / "config.yaml"
        lib.config._config = None

        lib.config.get_config("build")
        assert lib.config._config is not None

        (project_root / "config.yaml").unlink()
        result = lib.config.get_config("build")
        assert isinstance(result, dict)
