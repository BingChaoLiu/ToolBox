import subprocess


def _git(repo_path, *args):
    result = subprocess.run(
        ["git"] + list(args),
        cwd=repo_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result


def fetch(repo_path, remote="origin"):
    result = _git(repo_path, "fetch", remote)
    return result.returncode == 0


def get_new_commits(repo_path, branch, remote="origin"):
    _git(repo_path, "fetch", remote)
    result = _git(repo_path, "log", f"HEAD..{remote}/{branch}", "--oneline")
    if result.returncode != 0:
        return []
    lines = result.stdout.strip().split("\n")
    if not lines or lines[0] == "":
        return []
    commits = []
    for line in lines:
        parts = line.split(" ", 1)
        commits.append({
            "hash": parts[0],
            "message": parts[1] if len(parts) > 1 else "",
        })
    return commits


def get_status(repo_path):
    result = _git(repo_path, "status", "--porcelain")
    if result.returncode != 0:
        return {"clean": False, "files": []}
    lines = result.stdout.strip().split("\n")
    if not lines or lines[0] == "":
        return {"clean": True, "files": []}
    files = []
    for line in lines:
        status = line[:2].strip()
        filepath = line[3:]
        files.append({"status": status, "path": filepath})
    return {"clean": False, "files": files}
