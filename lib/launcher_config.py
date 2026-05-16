"""
Launcher group scripts configuration module.
Contains all module definitions and their branch configurations.
"""

from typing import Dict, List, Tuple, Optional

from lib.config import get_config

# Git remote configuration
ORIGIN_REMOTE = "origin"
SERVER_REMOTE = "server"


def get_server_url_base() -> str:
    """从 config.yaml 读取 server URL，避免凭据硬编码。"""
    return get_config("launcher_group.server.url_base", "")


def get_remote_name() -> str:
    """从 config.yaml 读取 server remote 名称。"""
    return get_config("launcher_group.server.remote_name", "server")


# Modules that have a 'server' remote configured
MODULES_WITH_SERVER = {
    "airyethereal_launcher",
    "aurora",
    "aurum",
    "aurum_launcher",
    "cheese",
    "dvb_common",
    "dvbservice",
    "Ethereal_Launcher",
    "epic_launcher",
    "epg_pro",
    "ethereal",
    "glamour_launcher",
    "glide",
    "glide_launcher",
    "grain",
    "grain_launcher",
    "gulf",
    "iolite",
    "iolite_launcher",
    "joycolor",
    "lake",
    "lake_launcher",
    "lost",
    "lustrous",
    "OttLauncherCore",
    "presenterlib",
    "pvr_pro",
    "qviart",
    "qviart_launcher",
    "reflect",
    "reflect_launcher",
    "sand_launcher",
    "shine",
    "spotless",
    "spotless_launcher",
    "tide_launcher",
    "twilight",
    "twilight_launcher",
    "vitality",
    "vitality_launcher",
    "Verve_Launcher",
    "zing",
    "common_for_view",
    "commonutils",
    "platform_utils"
}

# Branch configuration for update.py
UPDATE_BRANCHES: Dict[str, str] = {
    "vitality": "main",
    "gulf": "master",
    "lake": "master",
    "reflect": "main",
    "shine": "master",
    "qviart": "master",
    "aurora": "master",
    "cheese": "master",
    "grafitti": "master",
    "twilight": "master",
    "ethereal": "master",
    "spotless": "master",
    "aurum": "main",
    "glide": "main",
    "grain": "master",
    "iolite": "main",
    "lost": "main",
    "chmax": "refactor",
    "vitality_launcher": "main",
    "epic_launcher": "main",
    "sand_launcher": "main",
    "lake_launcher": "master",
    "glamour_launcher": "main",
    "reflect_launcher": "main",
    "qviart_launcher": "master",
    "spotless_launcher": "master",
    "Ethereal_Launcher": "master",
    "twilight_launcher": "master",
    "twilight_sample": "main",
    "aurum_launcher": "main",
    "glide_launcher": "main",
    "grain_launcher": "master",
    "iolite_launcher": "main",
    "tide_launcher": "main",
    "Verve_Launcher": "main",
    "lustrous": "main",
    "airyethereal_launcher": "main",
    "dvbservice": "master",
    "presenterlib": "master",
    "common_for_view": "master",
    "epg_pro": "master",
    "platform_utils": "master",
    "commonutils": "master",
    "zing": "master",
    "weather": "master",
    "dvb_common": "main",
    "TosmartDataInterface": "main",
    "OttLauncherCore": "master",
    "joycolor": "master",
    "pvr_pro": "master",
    "aars": "services",
    "center_platform": "refactor",
    "stb_extend_module": "main",
    "stb_message": "refactor",
}

# Branch configuration for sync.py
SYNC_BRANCHES: Dict[str, Tuple[str, str]] = {
    "vitality": ("main", "main"),
    "gulf": ("main", "master"),
    "lake": ("main", "master"),
    "reflect": ("main", "main"),
    "shine": ("main", "master"),
    "qviart": ("main", "master"),
    "aurora": ("main", "master"),
    "cheese": ("main", "master"),
    "grafitti": ("main", "master"),
    "twilight": ("main", "master"),
    "ethereal": ("main", "master"),
    "spotless": ("main", "master"),
    "aurum": ("main", "main"),
    "glide": ("main", "main"),
    "grain": ("main", "master"),
    "iolite": ("main", "main"),
    "lost": ("main", "main"),
    "joycolor": ("main", "master"),
    "pvr_pro": ("main", "master"),
    "zing": ("main", "master"),
    "vitality_launcher": ("main", "main"),
    "epic_launcher": ("main", "main"),
    "sand_launcher": ("main", "main"),
    "lake_launcher": ("main", "master"),
    "glamour_launcher": ("main", "main"),
    "reflect_launcher": ("main", "main"),
    "qviart_launcher": ("main", "master"),
    "spotless_launcher": ("main", "master"),
    "Ethereal_Launcher": ("main", "master"),
    "twilight_launcher": ("main", "master"),
    "aurum_launcher": ("main", "main"),
    "glide_launcher": ("main", "main"),
    "grain_launcher": ("main", "master"),
    "airyethereal_launcher": ("main", "main"),
    "iolite_launcher": ("main", "main"),
    "tide_launcher": ("main", "main"),
    "Verve_Launcher": ("main", "main"),
    "lustrous": ("main", "main"),
    "dvbservice": ("main", "master"),
    "presenterlib": ("main", "master"),
    "common_for_view": ("main", "master"),
    "epg_pro": ("main", "master"),
    "platform_utils": ("main", "master"),
    "commonutils": ("main", "master"),
    "dvb_common": ("main", "main"),
    "OttLauncherCore": ("main", "master"),
}


def is_launcher_module(module_name: str) -> bool:
    return module_name.endswith("_launcher")


def is_submodule_only(module_name: str) -> bool:
    submodules_only = {
        "aars", "center_platform", "chmax", "stb_extend_module",
        "stb_message", "weather", "TosmartDataInterface", "twilight_sample"
    }
    return module_name in submodules_only


def get_all_submodules() -> List[str]:
    return [m for m in UPDATE_BRANCHES.keys()
            if is_launcher_module(m) or is_submodule_only(m)]


def get_all_main_modules() -> List[str]:
    return [m for m in UPDATE_BRANCHES.keys()
            if not is_launcher_module(m) and not is_submodule_only(m)]


def get_syncable_modules() -> List[str]:
    return [m for m in UPDATE_BRANCHES.keys() if m in MODULES_WITH_SERVER]


def get_update_branch(module_name: str) -> str:
    return UPDATE_BRANCHES.get(module_name, "master")


def get_sync_branches(module_name: str) -> Optional[Tuple[str, str]]:
    if module_name not in SYNC_BRANCHES:
        return None
    return SYNC_BRANCHES[module_name]


# Legacy alias for backward compatibility
MODULE_BRANCHES = UPDATE_BRANCHES
get_branch = get_update_branch
