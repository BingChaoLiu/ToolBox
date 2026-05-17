# tests/test_scripts/test_logcat_filter.py
"""测试 logcat_filter 纯逻辑函数"""
from scripts.logcat_filter import _should_show


class TestShouldShow:
    def test_no_filter_shows_all(self):
        assert _should_show("D/Tag: hello", 0, "") is True

    def test_level_filter_blocks_lower(self):
        assert _should_show("D/Tag: debug", 3, "") is False   # D(1) < W(3)
        assert _should_show("W/Tag: warn", 3, "") is True     # W(3) >= W(3)
        assert _should_show("E/Tag: error", 3, "") is True    # E(4) >= W(3)

    def test_keyword_filter(self):
        assert _should_show("E/Crash: NullPointerException", 0, "null") is True
        assert _should_show("D/Tag: hello", 0, "world") is False

    def test_combined_filter(self):
        # E(4) >= F(5) is False → blocked by level
        assert _should_show("E/Crash: fatal error", 5, "fatal") is False

    def test_non_log_line_passes_level(self):
        assert _should_show("some random output", 3, "") is True

    def test_non_log_line_filtered_by_keyword(self):
        assert _should_show("some random output", 3, "missing") is False
