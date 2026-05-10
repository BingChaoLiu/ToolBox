import os
import pathlib

import yaml

_CONFIG_PATH = pathlib.Path(
    os.environ.get("TOOLBOX_CONFIG", "")
) if os.environ.get("TOOLBOX_CONFIG") else (
    pathlib.Path(__file__).parent.parent / "config.yaml"
)

_config = None


def get_config(dot_path: str):
    global _config
    if _config is None:
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            _config = yaml.safe_load(f)
    keys = dot_path.split(".")
    value = _config
    for key in keys:
        value = value[key]
    return value
