import shutil
from pathlib import Path


def main():
    from lib.config import get_config

    project = get_config("build.project_path")
    project_path = Path(project)

    dirs_to_clean = ["build", ".gradle", "app/build"]
    for d in dirs_to_clean:
        target = project_path / d
        if target.exists():
            print(f"清理: {target}")
            shutil.rmtree(target, ignore_errors=True)
        else:
            print(f"跳过: {target} (不存在)")

    print("清理完成")
