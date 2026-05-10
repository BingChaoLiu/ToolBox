import os
import shutil
import subprocess
import sys
from pathlib import Path

# 将当前目录加入 path 方便读取版本
sys.path.insert(0, os.path.abspath("."))
try:
    from toolbox import __version__
except ImportError:
    __version__ = "unknown"

# 打包配置
APP_NAME = "ToolBox"
ENTRY_POINT = "main.py"
DIST_DIR = "dist"
BUILD_DIR = "build"
RELEASE_NAME = f"{APP_NAME}_v{__version__}"


def clean():
    """清理旧的构建文件"""
    print("清理旧的构建目录...")
    for folder in [DIST_DIR, BUILD_DIR]:
        if os.path.exists(folder):
            shutil.rmtree(folder)
    spec_file = f"{APP_NAME}.spec"
    if os.path.exists(spec_file):
        os.remove(spec_file)


def build():
    """执行 PyInstaller 打包"""
    print(f"开始打包 {APP_NAME} (Onedir 模式)...")

    # 基础命令 - 使用 python -m PyInstaller 提高兼容性
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--name", APP_NAME,
        "--console",  # TUI 程序通常需要控制台
        # 核心依赖处理
        "--collect-all", "textual",
        "--collect-all", "rich",
        # 包含项目资源
        "--add-data", f"scripts{os.pathsep}scripts",
        "--add-data", f"pipelines{os.pathsep}pipelines",
        "--add-data", f"config.example.yaml{os.pathsep}.",
        # 入口文件
        ENTRY_POINT
    ]

    try:
        subprocess.check_call(cmd)
        print("\n打包成功！")
        print(f"可执行文件位于: {os.path.join(DIST_DIR, APP_NAME, APP_NAME + '.exe')}")
    except subprocess.CalledProcessError as e:
        print(f"\n打包失败: {e}")
        sys.exit(1)


def post_build():
    """打包后的处理"""
    # 如果根目录有 config.yaml，也可以考虑复制一份过去作为默认配置
    # 但通常建议用户根据 config.example.yaml 自行创建
    pass


if __name__ == "__main__":
    # 检查是否安装了 pyinstaller
    try:
        import PyInstaller
    except ImportError:
        print("错误: 未安装 PyInstaller。请运行 'pip install pyinstaller'")
        sys.exit(1)

    clean()
    build()
    post_build()
