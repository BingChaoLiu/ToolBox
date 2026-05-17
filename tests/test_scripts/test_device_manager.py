# tests/test_scripts/test_device_manager.py
"""测试 device_manager 纯逻辑函数"""
from scripts.device_manager import _adb_prefix


class TestAdbPrefix:
    def test_no_serial(self):
        assert _adb_prefix("") == ["adb"]

    def test_with_serial(self):
        assert _adb_prefix("ABC123") == ["adb", "-s", "ABC123"]
