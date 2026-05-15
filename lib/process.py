import subprocess


def run(cmd, cwd=None, env=None):
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=cwd,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",  # 遇到无法解码的字符时进行替换而非崩溃
    )
    for line in proc.stdout:
        print(line, end="")
    proc.wait()
    return proc.returncode
