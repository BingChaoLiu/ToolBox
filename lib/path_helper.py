import pathlib
import sys


def get_project_root() -> pathlib.Path:
    """获取项目根目录。兼容开发环境和 PyInstaller 打包后的环境。"""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # PyInstaller 打包后的路径
        return pathlib.Path(sys._MEIPASS)
    # 开发环境路径 (当前文件在 lib/path_helper.py，向上两级是项目根目录)
    return pathlib.Path(__file__).parent.parent


def ensure_dir(path):
    pathlib.Path(path).mkdir(parents=True, exist_ok=True)


def resolve(base, *parts):
    return str(pathlib.Path(base).joinpath(*parts))
