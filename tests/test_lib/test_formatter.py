# tests/test_lib/test_formatter.py
"""formatter 单元测试 — 行级内容识别与高亮"""
from rich.text import Text
from lib.formatter import format_line


class TestAndroidLog:
    def test_verbose(self):
        t = format_line("V/Tag: hello")
        assert "V/Tag: hello" in t.plain

    def test_error_red(self):
        t = format_line("E/Crash: oops")
        assert "E/Crash: oops" in t.plain
        assert any("red" in str(s.style) for s in t.spans)

    def test_fatal(self):
        t = format_line("F/System: die")
        assert "F/System: die" in t.plain
        assert len(t.spans) > 0

    def test_non_log_passthrough(self):
        t = format_line("just text")
        assert t.plain == "just text"
        assert len(t.spans) == 0


class TestPythonLog:
    def test_error(self):
        t = format_line("ERROR: something broke")
        assert "ERROR: " in t.plain
        assert any("red" in str(s.style) for s in t.spans)

    def test_warning(self):
        t = format_line("WARNING: careful")
        assert "WARNING: " in t.plain
        assert any("yellow" in str(s.style) for s in t.spans)


class TestJSON:
    def test_valid_object(self):
        t = format_line('{"name":"test","count":1}')
        assert '"name"' in t.plain
        # pretty-printed → has newline
        assert "\n" in t.plain

    def test_invalid_json_passthrough(self):
        t = format_line("{not json}")
        assert t.plain == "{not json}"


class TestTimestamp:
    def test_timestamp_styled(self):
        t = format_line("2024-01-15 10:30:00 event")
        assert "2024-01-15 10:30:00" in t.plain
        assert len(t.spans) > 0

    def test_no_timestamp(self):
        t = format_line("no time here")
        assert len(t.spans) == 0


class TestStackTrace:
    def test_java_stack(self):
        t = format_line("    at com.example.MyClass.method(MyClass.java:42)")
        assert len(t.spans) > 0

    def test_python_stack(self):
        t = format_line('  File "test.py", line 10, in <module>')
        assert len(t.spans) > 0


class TestHighlight:
    def test_single_match(self):
        t = format_line("hello world foo bar", highlight="foo")
        spans = [s for s in t.spans if "yellow" in str(s.style)]
        assert len(spans) >= 1

    def test_case_insensitive(self):
        t = format_line("Hello WORLD", highlight="world")
        spans = [s for s in t.spans if "yellow" in str(s.style)]
        assert len(spans) >= 1

    def test_multiple_matches(self):
        t = format_line("foo and foo and foo", highlight="foo")
        spans = [s for s in t.spans if "yellow" in str(s.style)]
        assert len(spans) == 3

    def test_no_highlight(self):
        t = format_line("hello", highlight=None)
        assert t.plain == "hello"

    def test_empty_keyword(self):
        t = format_line("hello", highlight="")
        assert t.plain == "hello"
