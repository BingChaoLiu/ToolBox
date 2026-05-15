"""
Launcher group scripts utility module.
Contains common functions for git operations and script handling.
"""

import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from lib.launcher_config import UPDATE_BRANCHES, get_update_branch, is_launcher_module
from lib.process import run as process_run


class GitError(Exception):
    """Custom exception for git errors."""
    pass


class ScriptError(Exception):
    """Custom exception for script errors."""
    pass


def run_git_command(
    args: List[str],
    cwd: Optional[Path] = None,
    check: bool = True,
    capture_output: bool = True
) -> subprocess.CompletedProcess:
    """
    Run a git command.
    """
    cmd = ["git"] + args
    try:
        # If we don't need to capture output, use lib.process.run for real-time display
        if not capture_output:
            returncode = process_run(cmd, cwd=cwd)
            if check and returncode != 0:
                raise GitError(f"Git command failed with exit code {returncode}: {' '.join(cmd)}")
            # Return a mock CompletedProcess
            return subprocess.CompletedProcess(cmd, returncode)

        result = subprocess.run(
            cmd,
            cwd=cwd,
            check=check,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        return result
    except subprocess.CalledProcessError as e:
        raise GitError(f"Git command failed: {' '.join(cmd)}\n{e.stderr}") from e
    except FileNotFoundError as e:
        raise GitError("Git not found. Please ensure Git is installed.") from e


def get_git_remote_url(cwd: Optional[Path] = None, remote: str = "origin") -> Optional[str]:
    """
    Get the URL of a git remote.
    """
    try:
        result = run_git_command(["remote", "get-url", remote], cwd=cwd, check=False)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return None
    except GitError:
        return None


def fetch_remote(cwd: Path, remote: str = "origin", realtime: bool = False) -> None:
    """
    Fetch updates from a remote.
    """
    run_git_command(["fetch", remote], cwd=cwd, capture_output=not realtime)


def checkout_branch(cwd: Path, branch: str) -> None:
    """
    Checkout a branch.
    """
    run_git_command(["checkout", branch], cwd=cwd)


def reset_hard(cwd: Path, ref: str) -> None:
    """
    Hard reset to a reference.
    """
    run_git_command(["reset", "--hard", ref], cwd=cwd)


def get_commit_id(cwd: Path, ref: str) -> Optional[str]:
    """
    Get the commit ID for a reference.
    """
    try:
        result = run_git_command(["rev-parse", "--short", ref], cwd=cwd, check=False)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return None
    except GitError:
        return None


def has_remote_updates(cwd: Path, branch: str) -> Tuple[bool, Optional[str], Optional[str], List[str]]:
    """
    Check if a module has updates from remote and get commit log.
    """
    try:
        # Fetch latest from origin
        fetch_remote(cwd, "origin")

        # Get commit IDs
        local_commit = get_commit_id(cwd, "HEAD")
        remote_commit = get_commit_id(cwd, f"origin/{branch}")

        if not local_commit or not remote_commit:
            return False, local_commit, remote_commit, []

        if local_commit == remote_commit:
            return False, local_commit, remote_commit, []

        # Get commit log: HEAD..origin/branch
        try:
            result = run_git_command(
                ["log", f"HEAD..origin/{branch}", "--oneline", "--no-decorate"],
                cwd=cwd,
                check=False
            )
            if result.returncode == 0 and result.stdout:
                commit_titles = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
            else:
                commit_titles = []
        except GitError:
            commit_titles = []

        return True, local_commit, remote_commit, commit_titles

    except GitError:
        return False, None, None, []


def set_remote_url(cwd: Path, remote: str, url: str) -> None:
    """
    Set the URL of a git remote.
    """
    run_git_command(["remote", "set-url", remote, url], cwd=cwd)


def print_success(message: str) -> None:
    """Print a success message."""
    print(message, flush=True)


def print_error(message: str) -> None:
    """Print an error message."""
    print(message, flush=True)


def print_warning(message: str) -> None:
    """Print a warning message."""
    print(message, flush=True)


def print_info(message: str) -> None:
    """Print an info message."""
    print(message, flush=True)


def find_all_modules(root: Path) -> List[str]:
    """
    Find all git repositories in the project root.
    """
    modules = []
    for item in root.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            if (item / ".git").exists():
                modules.append(item.name)
    return sorted(modules)


def parse_ps1_hashtable(content: str, var_name: str) -> Dict[str, str]:
    """
    Parse a PowerShell hashtable from a .ps1 file.
    """
    import re

    # Find the hashtable definition
    pattern = rf'\${var_name}\s*=\s*@\{{([^}}]+)\}}'
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        return {}

    result = {}
    hashtable_content = match.group(1)

    # Parse entries like "key" = "value";
    # Also handle arrays: "key" = @("val1", "val2");
    entry_pattern = r'"([^"]+)"\s*=\s*@\(\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\)\s*;|' \
                    r'"([^"]+)"\s*=\s*"([^"]+)"\s*;'

    for entry_match in re.finditer(entry_pattern, hashtable_content):
        if entry_match.group(1):  # Array format: @("val1", "val2")
            key = entry_match.group(1)
            value = entry_match.group(2)  # Use first value
        elif entry_match.group(4):  # Simple format: "value"
            key = entry_match.group(4)
            value = entry_match.group(5)
        else:
            continue

        result[key] = value

    return result


def generate_ps1_entry(module: str, branch_or_tuple, is_sync: bool = False) -> str:
    """
    Generate a PowerShell hashtable entry line.
    """
    if is_sync:
        if isinstance(branch_or_tuple, tuple):
            server_branch, local_branch = branch_or_tuple
        else:
            server_branch, local_branch = "main", branch_or_tuple
        return f'    "{module}" = @("{server_branch}", "{local_branch}");'
    else:
        branch = branch_or_tuple[0] if isinstance(branch_or_tuple, tuple) else branch_or_tuple
        return f'    "{module}" = "{branch}";'


# Comment marker for STB extend module dependency
STB_EXTEND_COMMENT = "this line is for stb extend module jenkins compile,do not delete and change it"
STB_EXTEND_DEPENDENCY = "implementation project(path: ':stb_extend_module')"


def add_stb_extend_dependency(module_path: Path, module_name: str) -> bool:
    """
    Add stb_extend_module dependency to build.gradle if the comment exists.
    """
    build_gradle = module_path / "build.gradle"

    if not build_gradle.exists():
        return False

    try:
        content = build_gradle.read_text(encoding="utf-8")
        lines = content.splitlines(keepends=True)

        comment_line_idx = -1
        has_dependency = False

        for i, line in enumerate(lines):
            if STB_EXTEND_COMMENT in line:
                comment_line_idx = i
            if comment_line_idx >= 0 and i > comment_line_idx:
                if STB_EXTEND_DEPENDENCY in line:
                    has_dependency = True
                    break

        if comment_line_idx >= 0 and not has_dependency:
            comment_line = lines[comment_line_idx]
            indent = ""
            for char in comment_line:
                if char in (' ', '\t'):
                    indent += char
                else:
                    break
            dependency_line = f"{indent}    {STB_EXTEND_DEPENDENCY}\n"
            insert_idx = comment_line_idx + 1
            lines.insert(insert_idx, dependency_line)
            build_gradle.write_text("".join(lines), encoding="utf-8")
            return True
        return False
    except Exception as e:
        raise ScriptError(f"Failed to update build.gradle for {module_name}: {e}")
