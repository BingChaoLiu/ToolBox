"""显示系统信息"""
import platform
import os


def main():
    print(f"系统: {platform.system()} {platform.release()}")
    print(f"主机名: {platform.node()}")
    print(f"Python: {platform.python_version()}")
    print(f"架构: {platform.machine()}")
    print(f"处理器: {platform.processor() or 'N/A'}")
    print(f"当前用户: {os.getenv('USERNAME', os.getenv('USER', 'unknown'))}")
    print(f"工作目录: {os.getcwd()}")

    import sys
    print(f"\nPython 路径: {sys.executable}")
    print(f"Python 搜索路径:")
    for p in sys.path[:5]:
        print(f"  {p}")

    return {"platform": platform.system(), "python": platform.python_version()}
