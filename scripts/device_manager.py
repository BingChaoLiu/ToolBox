# scripts/device_manager.py
"""ADB 设备管理 — 列出设备、安装/卸载 APK、推拉文件、截图"""
import shutil
import subprocess
from datetime import datetime
from pathlib import Path


def main(operation: str = "list", target: str = "", serial: str = ""):
    if not shutil.which("adb"):
        print("错误: 未找到 adb，请安装 Android SDK Platform Tools")
        return {"error": "adb_not_found"}

    adb = _adb_prefix(serial)

    if operation == "list":
        return _list_devices()
    elif operation == "install":
        return _install(adb, target)
    elif operation == "uninstall":
        return _uninstall(adb, target)
    elif operation == "push":
        return _push(adb, target)
    elif operation == "pull":
        return _pull(adb, target)
    elif operation == "screenshot":
        return _screenshot(adb)
    else:
        print(f"未知操作: {operation}")
        return {"error": "unknown_operation"}


def _adb_prefix(serial: str) -> list[str]:
    cmd = ["adb"]
    if serial:
        cmd.extend(["-s", serial])
    return cmd


def _run(cmd, check=True):
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(
        cmd, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    if result.stdout:
        print(result.stdout.rstrip())
    if result.returncode != 0 and result.stderr:
        print(f"  stderr: {result.stderr.rstrip()}")
    if check and result.returncode != 0:
        return None
    return result


def _list_devices():
    print("📱 已连接设备:\n")
    result = _run(["adb", "devices", "-l"])
    if result is None:
        return {"error": "adb_failed"}
    return {"operation": "list"}


def _install(adb, target):
    if not target:
        print("错误: 请输入 APK 文件路径")
        return {"error": "missing_target"}
    if not Path(target).exists():
        print(f"错误: 文件不存在: {target}")
        return {"error": "file_not_found"}
    print(f"📦 安装 APK: {target}\n")
    result = _run(adb + ["install", "-r", target])
    if result is None:
        return {"error": "install_failed"}
    print("\n安装完成")
    return {"operation": "install", "target": target}


def _uninstall(adb, target):
    if not target:
        print("错误: 请输入包名")
        return {"error": "missing_target"}
    print(f"🗑 卸载: {target}\n")
    result = _run(adb + ["uninstall", target])
    if result is None:
        return {"error": "uninstall_failed"}
    print("\n卸载完成")
    return {"operation": "uninstall", "target": target}


def _push(adb, target):
    if not target or ":" not in target:
        print("错误: 请输入格式: 本地路径:远程路径")
        return {"error": "missing_target"}
    local, remote = target.split(":", 1)
    if not Path(local).exists():
        print(f"错误: 文件不存在: {local}")
        return {"error": "file_not_found"}
    print(f"📤 推送: {local} → {remote}\n")
    result = _run(adb + ["push", local, remote])
    if result is None:
        return {"error": "push_failed"}
    print("\n推送完成")
    return {"operation": "push"}


def _pull(adb, target):
    if not target or ":" not in target:
        print("错误: 请输入格式: 远程路径:本地路径")
        return {"error": "missing_target"}
    remote, local = target.split(":", 1)
    print(f"📥 拉取: {remote} → {local}\n")
    result = _run(adb + ["pull", remote, local])
    if result is None:
        return {"error": "pull_failed"}
    print("\n拉取完成")
    return {"operation": "pull"}


def _screenshot(adb):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    device_path = "/sdcard/screenshot_toolbox.png"
    local_path = f"screenshot_{ts}.png"
    print("📸 截图中...\n")
    _run(adb + ["shell", "screencap", "-p", device_path])
    _run(adb + ["pull", device_path, local_path])
    _run(adb + ["shell", "rm", device_path])
    print(f"\n截图已保存: {local_path}")
    return {"operation": "screenshot", "file": local_path}
