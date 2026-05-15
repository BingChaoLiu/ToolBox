import os
import pathlib

import yaml

_CONFIG_PATH = pathlib.Path(
    os.environ.get("TOOLBOX_CONFIG", "")
) if os.environ.get("TOOLBOX_CONFIG") else (
    pathlib.Path(__file__).parent.parent / "config.yaml"
)

_config = None


def get_config(dot_path: str, default=None):
    global _config
    if _config is None:
        if not _CONFIG_PATH.exists():
            return default
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            _config = yaml.safe_load(f) or {}
    
    keys = dot_path.split(".")
    value = _config
    try:
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value
    except (KeyError, TypeError):
        return default
