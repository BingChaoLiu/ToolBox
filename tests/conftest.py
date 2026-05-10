import pathlib
import tempfile

import pytest


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield pathlib.Path(d)


@pytest.fixture(autouse=True)
def reset_lib_config():
    import lib.config
    lib.config._config = None
    yield
    lib.config._config = None


@pytest.fixture
def project_root(tmp_dir):
    config_content = {
        "build": {
            "project_path": str(tmp_dir / "android_project"),
            "gradlew": "gradlew.bat",
        },
        "git": {
            "repos": [
                {"name": "主项目", "path": str(tmp_dir / "repo"), "branch": "main"},
            ]
        },
    }
    import yaml
    config_path = tmp_dir / "config.yaml"
    config_path.write_text(yaml.dump(config_content), encoding="utf-8")
    return tmp_dir
