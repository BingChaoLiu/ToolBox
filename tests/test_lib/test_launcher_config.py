import pytest
from lib.launcher_config import (
    is_launcher_module, is_submodule_only, 
    get_all_submodules, get_all_main_modules,
    get_update_branch
)

class TestLauncherConfig:
    def test_is_launcher_module(self):
        assert is_launcher_module("vitality_launcher") is True
        assert is_launcher_module("vitality") is False

    def test_is_submodule_only(self):
        assert is_submodule_only("stb_extend_module") is True
        assert is_submodule_only("vitality") is False

    def test_get_all_submodules(self):
        subs = get_all_submodules()
        assert "vitality_launcher" in subs
        assert "stb_extend_module" in subs
        assert "vitality" not in subs

    def test_get_all_main_modules(self):
        mains = get_all_main_modules()
        assert "vitality" in mains
        assert "gulf" in mains
        assert "vitality_launcher" not in mains

    def test_get_update_branch(self):
        assert get_update_branch("vitality") == "main"
        assert get_update_branch("gulf") == "master"
        assert get_update_branch("unknown") == "master" # Default fallback
