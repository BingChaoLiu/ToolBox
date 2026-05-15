import pytest
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

# 测试核心提取逻辑，模拟 scripts/addr2line.py 中的正则表达式流程
def extract_addresses_simulated(crash_log, module_base):
    # 1. Strict pattern: #00 pc <addr> <module>
    pattern_strict = rf'#\d+\s+pc\s+([0-9a-fA-F]{{4,16}})\s+.*{re.escape(module_base)}'
    addresses = re.findall(pattern_strict, crash_log)
    
    if not addresses:
        # 2. Fallback 1: pc <addr> <module> (no # prefix)
        pattern_fallback = rf'pc\s+([0-9a-fA-F]{{4,16}})\s+.*{re.escape(module_base)}'
        addresses = re.findall(pattern_fallback, crash_log)

    if not addresses:
        # 3. Fallback 2: any pc <addr>
        addresses = re.findall(r'pc\s+([0-9a-fA-F]{4,16})', crash_log)

    # 去重并保持顺序
    seen = set()
    unique_addresses = []
    for a in addresses:
        clean_addr = a.replace("0x", "").lower()
        if clean_addr not in seen:
            unique_addresses.append(clean_addr)
            seen.add(clean_addr)
    return unique_addresses

@pytest.fixture
def sample_log():
    return """05-14 12:57:53.529  2126  2126 F DEBUG   : pid: 2119, tid: 2119, name: dvbstack  >>> /system/bin/dvbstack <<<
05-14 12:57:53.536  2126  2126 F DEBUG   :     ip b1408860  sp be9087e0  lr b2e7996b  pc b2e48ff6  cpsr 600f0030
05-14 12:57:53.544  2126  2126 F DEBUG   : backtrace:
05-14 12:57:53.545  2126  2126 F DEBUG   :     #00 pc 00024ff6  /system/bin/dvbstack
05-14 12:57:53.545  2126  2126 F DEBUG   :     #01 pc 0000d30b  /system/bin/dvbstack
05-14 12:57:53.545  2126  2126 F DEBUG   :     #02 pc 0000d09b  /system/bin/dvbstack
05-14 12:57:53.545  2126  2126 F DEBUG   :     #03 pc 00016c3d  /system/lib/libc.so (__libc_init+48)
05-14 12:57:53.545  2126  2126 F DEBUG   :     #04 pc 0000a968  /system/bin/dvbstack"""

def test_extract_addresses_precision(sample_log):
    # 精准提取：应排除寄存器行 (b2e48ff6) 和 libc (00016c3d)
    addrs = extract_addresses_simulated(sample_log, "dvbstack")
    expected = ["00024ff6", "0000d30b", "0000d09b", "0000a968"]
    assert addrs == expected

def test_extract_addresses_fallback_simple(sample_log):
    # 测试如果没有 # 号但有模块名的情况
    log_simple = "pc 00024ff6 /system/bin/dvbstack\npc 0000d30b /system/bin/dvbstack"
    addrs = extract_addresses_simulated(log_simple, "dvbstack")
    assert addrs == ["00024ff6", "0000d30b"]

def test_main_integration(sample_log, tmp_path):
    from scripts.addr2line import main
    
    # 模拟 SO 文件
    fake_so = tmp_path / "dvbstack"
    fake_so.write_text("fake-elf")
    
    with patch("scripts.addr2line.get_config") as mock_get_config, \
         patch("subprocess.run") as mock_run:
        
        mock_get_config.return_value = "llvm-addr2line.exe"
        mock_run.return_value = MagicMock(stdout="func\nsrc.c:1", returncode=0)
        
        result = main(crash_log=sample_log, so_file=str(fake_so))
        
        assert "results" in result
        # 验证返回了正确的结果（字符串形式）
        assert "func" in result["results"]
