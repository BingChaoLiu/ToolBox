import subprocess
import re
import os
from pathlib import Path
from lib.config import get_config


def main(crash_log=None, so_file=None):
    """
    崩溃日志分析脚本 (调试增强版)。
    """
    if not crash_log or not so_file:
        print("错误: 需要填写崩溃日志和 SO 文件路径")
        return {"error": "missing params"}

    so_path = Path(so_file).absolute()
    if not so_path.exists():
        print(f"错误: 库文件不存在: {so_path}")
        return {"error": "so_file_not_found"}

    # 打印文件信息以供对比
    try:
        file_size = so_path.stat().st_size
        print(f"库文件: {so_path}")
        print(f"文件大小: {file_size} 字节")
    except Exception as e:
        print(f"无法读取文件状态: {e}")

    # 从配置获取 addr2line 工具路径
    tool_path = get_config("addr2line.tool_path", "addr2line")
    
    # 提取模块名
    module_base = so_path.stem if so_path.suffix == '.so' else so_path.name
    print(f"分析模块: {module_base}")

    # 提取日志中的十六进制地址
    # 1. 优先匹配标准的 backtrace 行
    pattern_strict = rf'#\d+\s+pc\s+([0-9a-fA-F]{{4,16}})\s+.*{re.escape(module_base)}'
    addresses = re.findall(pattern_strict, crash_log)
    
    if not addresses:
        # 2. 降级方案 1
        pattern_fallback = rf'pc\s+([0-9a-fA-F]{{4,16}})\s+.*{re.escape(module_base)}'
        addresses = re.findall(pattern_fallback, crash_log)

    if not addresses:
        # 3. 降级方案 2
        addresses = re.findall(r'pc\s+([0-9a-fA-F]{4,16})', crash_log)

    if not addresses:
        print("错误: 未在日志中找到有效的崩溃地址")
        return {"error": "no_addresses_found"}

    # 去重并保持顺序
    seen = set()
    unique_addresses = []
    for a in addresses:
        clean_addr = a.replace("0x", "").lower()
        if clean_addr not in seen:
            unique_addresses.append(clean_addr)
            seen.add(clean_addr)

    print(f"提取地址: {', '.join(unique_addresses)}\n")

    # 构建单条批量解析命令
    cmd = [tool_path, "-C", "-f", "-e", str(so_path)] + unique_addresses
    
    # 打印完整命令供用户手动对比
    print("执行命令:")
    print(" ".join([f'"{c}"' if " " in c else c for c in cmd]))
    print()

    try:
        # 执行批量查询
        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        
        raw_output = process.stdout.strip()
        
        if process.returncode != 0:
            print(f"错误: 工具执行失败 (Exit Code {process.returncode})")
            if process.stderr:
                print(f"标准错误:\n{process.stderr}")
            return {"error": "tool_failed"}

        if not raw_output:
            print("警告: 工具未返回任何结果")
            return {"results": []}

        # 直接输出原始解析结果
        print("--- 解析结果 ---")
        lines = raw_output.splitlines()
        
        # 按照 2 行一组进行对齐显示 (函数名 + 源码位置)
        for i, addr in enumerate(unique_addresses):
            print(f"[{addr}]")
            f_idx = i * 2
            s_idx = i * 2 + 1
            
            func = lines[f_idx] if f_idx < len(lines) else "??"
            src = lines[s_idx] if s_idx < len(lines) else "??:0"
            
            print(f"  函数: {func}")
            print(f"  源码: {src}\n")

        print("---------------")

        return {"results": raw_output}

    except FileNotFoundError:
        print(f"错误: 找不到工具 '{tool_path}'，请检查 config.yaml")
        return {"error": "tool_not_found"}
    except Exception as e:
        print(f"执行异常: {e}")
        return {"error": str(e)}
