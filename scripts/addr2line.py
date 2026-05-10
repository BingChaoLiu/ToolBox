import subprocess


def main(address=None, so_file=None):
    if not address or not so_file:
        print("用法: 需要 address 和 so_file 参数")
        return {"error": "missing params"}

    addresses = [a.strip() for a in address.strip().split("\n") if a.strip()]

    results = []
    for addr in addresses:
        try:
            r = subprocess.run(
                ["addr2line", "-e", so_file, addr],
                capture_output=True, text=True, encoding="utf-8",
            )
            line = r.stdout.strip()
            print(f"  {addr} → {line}")
            results.append({"address": addr, "location": line})
        except FileNotFoundError:
            print(f"  addr2line 工具未找到，请检查 config 中 tool_path")
            return {"error": "addr2line not found"}

    return {"results": results}
