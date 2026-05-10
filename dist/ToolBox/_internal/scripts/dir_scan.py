"""扫描目录，统计文件类型和数量"""
import os


def main(path=".", pattern=""):
    target = os.path.expanduser(path)
    if not os.path.isdir(target):
        print(f"路径不存在: {target}")
        return {"error": "path not found"}

    print(f"扫描目录: {target}")
    print(f"过滤: {pattern or '(无)'}")
    print()

    extensions = {}
    total_files = 0
    total_dirs = 0

    for root, dirs, files in os.walk(target):
        total_dirs += len(dirs)
        for f in files:
            if pattern and pattern.lower() not in f.lower():
                continue
            total_files += 1
            ext = os.path.splitext(f)[1].lower() or "(无扩展名)"
            extensions[ext] = extensions.get(ext, 0) + 1

    print(f"目录数: {total_dirs}")
    print(f"文件数: {total_files}")
    print()
    print("文件类型分布:")
    for ext, count in sorted(extensions.items(), key=lambda x: -x[1])[:15]:
        bar = "█" * min(count, 40)
        print(f"  {ext:12s} {count:4d}  {bar}")

    return {"files": total_files, "dirs": total_dirs, "types": len(extensions)}
