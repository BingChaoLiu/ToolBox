# scripts/logcat_filter.py
"""Logcat 日志过滤 — 实时捕获 adb logcat 并按关键词/级别过滤"""
import re
import shutil
import subprocess


_LEVEL_ORDER = {"V": 0, "D": 1, "I": 2, "W": 3, "E": 4, "F": 5}
_LOG_RE = re.compile(r'^([VDIWEF])/')


def main(filter: str = "", level: str = "V", serial: str = ""):
    if not shutil.which("adb"):
        print("错误: 未找到 adb，请安装 Android SDK Platform Tools")
        return {"error": "adb_not_found"}

    min_level = _LEVEL_ORDER.get(level.upper(), 0)
    filter_lower = filter.lower()

    cmd = ["adb"]
    if serial:
        cmd.extend(["-s", serial])
    cmd.extend(["logcat", "-v", "brief"])

    print(f"🔍 开始捕获 logcat (级别≥{level}, 关键词='{filter}')...")
    print(f"   命令: {' '.join(cmd)}")
    print("   Ctrl+C 停止捕获\n")

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
    )

    count = 0
    try:
        for line in proc.stdout:
            line = line.rstrip("\n")
            if not _should_show(line, min_level, filter_lower):
                continue
            print(line)
            count += 1
            if count >= 500:
                print("\n--- 已达到 500 行上限，停止捕获 ---")
                proc.terminate()
                break
    except KeyboardInterrupt:
        print("\n--- 用户中断 ---")
    finally:
        proc.terminate()

    print(f"\n捕获完成，共 {count} 行匹配日志")
    return {"matched_lines": count}


def _should_show(line: str, min_level: int, filter_lower: str) -> bool:
    """判断一行日志是否应显示。"""
    m = _LOG_RE.match(line)
    if m:
        line_level = _LEVEL_ORDER.get(m.group(1), 0)
        if line_level < min_level:
            return False
    if filter_lower and filter_lower not in line.lower():
        return False
    return True
