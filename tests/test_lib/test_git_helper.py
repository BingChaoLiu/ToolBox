import subprocess

import pytest

from lib.git_helper import fetch, get_new_commits, get_status


@pytest.fixture
def git_repo(tmp_dir):
    repo = tmp_dir / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=str(repo), capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(repo), capture_output=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=str(repo), capture_output=True)
    (repo / "readme.txt").write_text("init", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(repo), capture_output=True)
    return repo


class TestFetch:
    def test_fetch_nonexistent_remote_returns_false(self, git_repo):
        result = fetch(str(git_repo), remote="origin")
        assert result is False

    def test_fetch_valid_repo_does_not_crash(self, git_repo):
        result = fetch(str(git_repo))
        assert isinstance(result, bool)


class TestGetNewCommits:
    def test_no_remote_returns_empty(self, git_repo):
        commits = get_new_commits(str(git_repo), "main")
        assert commits == []


class TestGetStatus:
    def test_clean_repo(self, git_repo):
        status = get_status(str(git_repo))
        assert isinstance(status, dict)
