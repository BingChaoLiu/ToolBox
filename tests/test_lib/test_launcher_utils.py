import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from lib.launcher_utils import (
    run_git_command, get_git_remote_url, has_remote_updates, 
    parse_ps1_hashtable, GitError
)

class TestLauncherUtils:
    def test_run_git_command_success(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="success", stderr="")
            result = run_git_command(["status"])
            assert result.stdout == "success"
            mock_run.assert_called_once()

    def test_run_git_command_failure(self):
        with patch("subprocess.run") as mock_run:
            from subprocess import CalledProcessError
            mock_run.side_effect = CalledProcessError(1, ["git", "status"], stderr="error")
            with pytest.raises(GitError) as excinfo:
                run_git_command(["status"])
            assert "Git command failed" in str(excinfo.value)

    def test_get_git_remote_url(self):
        with patch("lib.launcher_utils.run_git_command") as mock_git:
            mock_git.return_value = MagicMock(returncode=0, stdout="http://github.com/test.git")
            url = get_git_remote_url(Path("/tmp"), "origin")
            assert url == "http://github.com/test.git"

    def test_has_remote_updates_no_updates(self):
        with patch("lib.launcher_utils.fetch_remote"), \
             patch("lib.launcher_utils.get_commit_id") as mock_id:
            # Same commit ID for local and remote
            mock_id.side_effect = ["abc1234", "abc1234"]
            has_update, local, remote, log = has_remote_updates(Path("/tmp"), "main")
            assert has_update is False
            assert local == "abc1234"
            assert remote == "abc1234"

    def test_has_remote_updates_with_updates(self):
        with patch("lib.launcher_utils.fetch_remote"), \
             patch("lib.launcher_utils.get_commit_id") as mock_id, \
             patch("lib.launcher_utils.run_git_command") as mock_git:
            # Different commit IDs
            mock_id.side_effect = ["local123", "remote456"]
            mock_git.return_value = MagicMock(returncode=0, stdout="feat: new feature\nfix: bug fix")
            
            has_update, local, remote, log = has_remote_updates(Path("/tmp"), "main")
            assert has_update is True
            assert local == "local123"
            assert remote == "remote456"
            assert len(log) == 2
            assert log[0] == "feat: new feature"

    def test_parse_ps1_hashtable_simple(self):
        content = '$submodules = @{\n    "zing" = "master";\n    "epg_pro" = "master";\n}'
        result = parse_ps1_hashtable(content, "submodules")
        assert result == {"zing": "master", "epg_pro": "master"}

    def test_parse_ps1_hashtable_array(self):
        content = '$sync_branches = @{\n    "vitality" = @("main", "main");\n    "gulf" = @("main", "master");\n}'
        result = parse_ps1_hashtable(content, "sync_branches")
        assert result == {"vitality": "main", "gulf": "main"}
