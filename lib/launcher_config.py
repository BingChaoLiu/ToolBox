"""
Launcher group scripts configuration module.
Contains all module definitions and their branch configurations.
"""

from typing import Dict, List, Tuple, Optional

# Git remote configuration
ORIGIN_REMOTE = "origin"
SERVER_REMOTE = "server"

# Server URL base
SERVER_URL_BASE = "http://rink:mktech2023@192.168.0.20:6789/RefactorLauncher/"

# Modules that have a 'server' remote configured
# These are used in sync.ps1 to push to server
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
# Format: {module_name: origin_branch}
# update.py 将本地重置到 origin/<branch>
UPDATE_BRANCHES: Dict[str, str] = {
    # Main modules
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

    # Launcher submodules (end with _launcher)
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

    # Common submodules
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
# Format: {module_name: (server_branch, local_branch)}
# sync.py 将本地的 local_branch 分支推送到 server 的 server_branch
SYNC_BRANCHES: Dict[str, Tuple[str, str]] = {
    # Main modules
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

    # Launcher submodules (end with _launcher)
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

    # Common submodules (only those with server remote)
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
    """Check if a module is a launcher module (ends with _launcher)."""
    return module_name.endswith("_launcher")


def is_submodule_only(module_name: str) -> bool:
    """Check if a module is a submodule-only module (no server remote)."""
    submodules_only = {
        "aars", "center_platform", "chmax", "stb_extend_module",
        "stb_message", "weather", "TosmartDataInterface", "twilight_sample"
    }
    return module_name in submodules_only


def get_all_submodules() -> List[str]:
    """Get list of all submodules (launcher modules + submodule-only modules)."""
    return [m for m in UPDATE_BRANCHES.keys()
            if is_launcher_module(m) or is_submodule_only(m)]


def get_all_main_modules() -> List[str]:
    """Get list of all main modules."""
    return [m for m in UPDATE_BRANCHES.keys()
            if not is_launcher_module(m) and not is_submodule_only(m)]


def get_syncable_modules() -> List[str]:
    """Get list of modules that have a server remote for sync."""
    return [m for m in UPDATE_BRANCHES.keys() if m in MODULES_WITH_SERVER]


def get_update_branch(module_name: str) -> str:
    """
    Get the origin branch for update.py.
    Returns the branch that local should be reset to from origin.
    """
    return UPDATE_BRANCHES.get(module_name, "master")


def get_sync_branches(module_name: str) -> Optional[Tuple[str, str]]:
    """
    Get the (server_branch, local_branch) tuple for sync.py.
    Returns None if module cannot be synced (no server remote).
    """
    if module_name not in SYNC_BRANCHES:
        return None
    return SYNC_BRANCHES[module_name]


# Legacy alias for backward compatibility
MODULE_BRANCHES = UPDATE_BRANCHES
get_branch = get_update_branch
