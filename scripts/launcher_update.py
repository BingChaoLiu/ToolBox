"""
launcher_update.py - Update launcher group modules from origin remote.
"""

import re
from pathlib import Path
from typing import Optional, List, Tuple

from lib.launcher_config import UPDATE_BRANCHES, get_all_submodules, get_all_main_modules
from lib.launcher_utils import (
    get_git_remote_url,
    set_remote_url,
    fetch_remote,
    checkout_branch,
    reset_hard,
    has_remote_updates,
    print_success,
    print_error,
    print_warning,
    print_info,
    add_stb_extend_dependency,
    GitError
)
from lib.config import get_config

# URL conversion patterns
URL_PATTERNS = [
    (r'^http://192\.168\.0\.20:6789', 'http://bingchao.liu:12345678@112.91.80.106:23911'),
    (r'^http://112\.91\.80\.106:23911', 'http://bingchao.liu:12345678@112.91.80.106:23911'),
    (r'^git@192\.168\.1\.232:', 'http://bingchao.liu:12345678@112.91.80.106:23911/'),
]


def update_git_remote_url(module_path: Path, module_name: str) -> bool:
    """
    Update git remote URL from old internal to new external.
    """
    try:
        current_url = get_git_remote_url(module_path, "origin")
        if not current_url:
            print_warning(f"  {module_name}: No origin remote found")
            return False

        # Check if URL needs conversion
        new_url = None
        for pattern, replacement in URL_PATTERNS:
            if re.match(pattern, current_url):
                new_url = re.sub(pattern, replacement, current_url)
                break

        if new_url and new_url != current_url:
            print_info(f"  {module_name}:")
            print_info(f"    {current_url}")
            print_info(f"    → {new_url}")
            set_remote_url(module_path, "origin", new_url)
            print_success(f"  {module_name}: URL updated")
            return True
        else:
            print_info(f"  {module_name}: URL already correct")
            return False

    except GitError as e:
        print_error(f"  {module_name}: URL update failed - {e}")
        return False


def update_module(module_name: str, modules_root: Path) -> bool:
    """
    Update a single module from origin.
    """
    module_path = modules_root / module_name
    branch = UPDATE_BRANCHES.get(module_name, "master")

    print_info(f"  {module_name} ({branch})")

    try:
        # Fetch from origin (realtime output)
        fetch_remote(module_path, "origin", realtime=True)

        # Checkout branch
        checkout_branch(module_path, branch)

        # Hard reset to origin/branch
        reset_hard(module_path, f"origin/{branch}")

        print_success(f"  {module_name}: Updated to origin/{branch}")

        # Automatically add stb_extend_module dependency after update
        try:
            added = add_stb_extend_dependency(module_path, module_name)
            if added:
                print_info(f"  {module_name}: Added stb_extend_module dependency")
        except Exception as dep_error:
            print_warning(f"  {module_name}: Could not add dependency - {dep_error}")

        return True

    except GitError as e:
        print_error(f"  {module_name}: Update failed - {e}")
        return False


def check_module_updates(module_name: str, modules_root: Path) -> Tuple[bool, str, Optional[str], Optional[str], List[str]]:
    """
    Check if a module has remote updates.
    """
    module_path = modules_root / module_name
    branch = UPDATE_BRANCHES.get(module_name, "master")

    try:
        has_update, local_commit, remote_commit, commit_titles = has_remote_updates(module_path, branch)
        return has_update, module_name, local_commit, remote_commit, commit_titles
    except GitError as e:
        print_error(f"  {module_name}: Check failed - {e}")
        return False, module_name, None, None, []


def main(modules: str = None, check: bool = False, update_url: bool = False, 
         submodules_only: bool = False, main_modules_only: bool = False):
    """
    Main entry point for ToolBox.
    
    Args:
        modules: Comma-separated list of modules to process (default: all)
        check: Check which modules have remote updates (without updating)
        update_url: Update Git remote URLs from old internal to new external
        submodules_only: Only process submodules
        main_modules_only: Only process main modules
    """
    # Get project root from config
    modules_root = Path(get_config("launcher_group.path"))
    if not modules_root.exists():
        print_error(f"Project path does not exist: {modules_root}")
        return {"error": "Path not found"}

    # Determine which modules to process
    if modules:
        modules_to_process = [m.strip() for m in modules.split(",")]
    elif submodules_only:
        modules_to_process = get_all_submodules()
    elif main_modules_only:
        modules_to_process = get_all_main_modules()
    else:
        modules_to_process = list(UPDATE_BRANCHES.keys())

    # Organize into submodules and main_modules
    submodules = [m for m in modules_to_process if m in get_all_submodules()]
    main_modules = [m for m in modules_to_process if m in get_all_main_modules()]

    # Handle check mode
    if check:
        print_success("\n=== 检查远程更新 ===\n")
        modules_with_updates = []
        all_modules = submodules + main_modules
        print_info(f"正在检查 {len(all_modules)} 个模块...\n")

        for module in all_modules:
            has_update, _, local_commit, remote_commit, commit_titles = check_module_updates(module, modules_root)
            if has_update:
                branch = UPDATE_BRANCHES.get(module, "master")
                modules_with_updates.append({
                    "name": module,
                    "branch": branch,
                    "local": local_commit,
                    "remote": remote_commit,
                    "commits": commit_titles
                })

        if modules_with_updates:
            print_success(f"\n发现 {len(modules_with_updates)} 个模块有更新：\n")
            for m in modules_with_updates:
                num_commits = len(m["commits"])
                print(f"  {m['name']} ({m['branch']}) - 落后 {num_commits} 个 commit")
                print(f"    本地: {m['local']} → 远程: {m['remote']}")
                if m["commits"]:
                    for title in reversed(m["commits"]):
                        print(f"      • {title}")
                print()

            module_names = ','.join(m['name'] for m in modules_with_updates)
            print_warning(f"运行以下命令更新这些模块：")
            
            return {f"  python Scripts/update.py -m {module_names}"}
        else:
            print_success("\n所有模块都是最新的，无需更新。")

        return {"modules_with_updates": len(all_modules)}

    # Handle update-url mode
    if update_url:
        print_success("\n=== 更新 Git URL ===\n")
        all_modules = submodules + main_modules
        print_info(f"正在检查 {len(all_modules)} 个模块的 URL...\n")
        updated_count = 0
        for module in all_modules:
            module_path = modules_root / module
            if update_git_remote_url(module_path, module):
                updated_count += 1
        return {"updated_count": updated_count}

    # Normal update mode
    print_success("\n=== 更新模块 ===\n")
    all_modules = submodules + main_modules
    print_info(f"准备更新 {len(all_modules)} 个模块\n")

    success_count = 0
    failed_count = 0

    if submodules:
        print_info("子模块:")
        for module in submodules:
            if update_module(module, modules_root):
                success_count += 1
            else:
                failed_count += 1
        print()

    if main_modules:
        print_info("主模块:")
        for module in main_modules:
            if update_module(module, modules_root):
                success_count += 1
            else:
                failed_count += 1
        print()

    if failed_count == 0:
        print_success(f"✓ 所有 {success_count} 个模块更新成功！")
    else:
        print_warning(f"✓ {success_count} 个模块成功，✗ {failed_count} 个模块失败")

    return {
        "success_count": success_count,
        "failed_count": failed_count
    }
