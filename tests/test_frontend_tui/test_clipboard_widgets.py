"""测试 ClipboardInput / ClipboardTextArea 右键复制粘贴逻辑。"""
import pytest
from unittest.mock import patch, MagicMock

from textual.app import App, ComposeResult
from textual.widgets import Input, TextArea

from toolbox.frontend_tui.app import ClipboardInput, ClipboardTextArea


class _InputApp(App):
    """测试用最小 App — 含一个 ClipboardInput。"""

    def compose(self) -> ComposeResult:
        yield ClipboardInput(value="hello world", id="ci")


class _TextAreaApp(App):
    """测试用最小 App — 含一个 ClipboardTextArea。"""

    def compose(self) -> ComposeResult:
        yield ClipboardTextArea(text="line1\nline2\nline3", id="cta")


# ── ClipboardInput 测试 ────────────────────────────────────────────


class TestClipboardInputCopy:
    """选中文字时右键复制。"""

    @pytest.mark.asyncio
    async def test_copy_selected_text(self):
        with patch("toolbox.frontend_tui.app._clipboard_copy") as mock_copy, \
             patch("toolbox.frontend_tui.app._clipboard_read") as mock_read:
            app = _InputApp()
            async with app.run_test() as pilot:
                inp = app.query_one(ClipboardInput)
                # 选中 "hello"（前5个字符）
                inp.selection = (0, 5)
                inp._handle_right_click()

                mock_copy.assert_called_once_with("hello")
                mock_read.assert_not_called()

    @pytest.mark.asyncio
    async def test_copy_shows_notification(self):
        with patch("toolbox.frontend_tui.app._clipboard_copy"), \
             patch("toolbox.frontend_tui.app._clipboard_read"):
            app = _InputApp()
            async with app.run_test() as pilot:
                inp = app.query_one(ClipboardInput)
                inp.selection = (0, 5)

                with patch.object(app, "notify") as mock_notify:
                    inp._handle_right_click()
                    mock_notify.assert_called_once()
                    assert "复制" in mock_notify.call_args[1].get("title", mock_notify.call_args[0][1] if len(mock_notify.call_args[0]) > 1 else "")


class TestClipboardInputPaste:
    """无选中文字时右键粘贴。"""

    @pytest.mark.asyncio
    async def test_paste_from_clipboard(self):
        with patch("toolbox.frontend_tui.app._clipboard_read", return_value="pasted"):
            app = _InputApp()
            async with app.run_test() as pilot:
                inp = app.query_one(ClipboardInput)
                inp.value = ""
                inp._handle_right_click()

                assert inp.value == "pasted"

    @pytest.mark.asyncio
    async def test_paste_takes_first_line_only(self):
        with patch("toolbox.frontend_tui.app._clipboard_read", return_value="  abc  \ndef"):
            app = _InputApp()
            async with app.run_test() as pilot:
                inp = app.query_one(ClipboardInput)
                # 确保无选中文字
                inp.selection = (0, 0)
                inp._handle_right_click()

                assert inp.value == "abc"

    @pytest.mark.asyncio
    async def test_no_change_when_clipboard_empty(self):
        with patch("toolbox.frontend_tui.app._clipboard_read", return_value=""):
            app = _InputApp()
            async with app.run_test() as pilot:
                inp = app.query_one(ClipboardInput)
                original = inp.value
                inp._handle_right_click()

                assert inp.value == original

    @pytest.mark.asyncio
    async def test_no_change_when_clipboard_none(self):
        with patch("toolbox.frontend_tui.app._clipboard_read", return_value=None):
            app = _InputApp()
            async with app.run_test() as pilot:
                inp = app.query_one(ClipboardInput)
                original = inp.value
                inp._handle_right_click()

                assert inp.value == original


# ── ClipboardTextArea 测试 ─────────────────────────────────────────


class TestClipboardTextAreaCopy:
    """选中文字时右键复制。"""

    @pytest.mark.asyncio
    async def test_copy_selected_text(self):
        with patch("toolbox.frontend_tui.app._clipboard_copy") as mock_copy, \
             patch("toolbox.frontend_tui.app._clipboard_read") as mock_read:
            app = _TextAreaApp()
            async with app.run_test() as pilot:
                ta = app.query_one(ClipboardTextArea)
                # 选中第一行 "line1"
                ta.selection = ta.selection.__class__((0, 0), (0, 5))
                ta._handle_right_click()

                mock_copy.assert_called_once()
                mock_read.assert_not_called()


class TestClipboardTextAreaPaste:
    """无选中文字时右键粘贴。"""

    @pytest.mark.asyncio
    async def test_paste_multiline(self):
        with patch("toolbox.frontend_tui.app._clipboard_read", return_value="aaa\nbbb\nccc"):
            app = _TextAreaApp()
            async with app.run_test() as pilot:
                ta = app.query_one(ClipboardTextArea)
                ta._handle_right_click()

                assert ta.text == "aaa\nbbb\nccc"

    @pytest.mark.asyncio
    async def test_paste_replaces_content(self):
        with patch("toolbox.frontend_tui.app._clipboard_read", return_value="new"):
            app = _TextAreaApp()
            async with app.run_test() as pilot:
                ta = app.query_one(ClipboardTextArea)
                ta._handle_right_click()

                assert ta.text == "new"


# ── 子类继承关系测试 ────────────────────────────────────────────────


class TestSubclassInheritance:
    """确保子类关系正确，_collect_params 的 isinstance 检查仍有效。"""

    def test_clipboard_input_is_input(self):
        assert issubclass(ClipboardInput, Input)

    def test_clipboard_textarea_is_textarea(self):
        assert issubclass(ClipboardTextArea, TextArea)


class TestButtonNumber:
    """验证右键按钮号：Textual XTermParser 映射后右键 = button 3。"""

    @pytest.mark.asyncio
    async def test_right_click_is_button_3(self):
        """右键应匹配 button==3，而非 button==2（中键）。"""
        with patch("toolbox.frontend_tui.app._clipboard_read", return_value="hello"):
            app = _InputApp()
            async with app.run_test() as pilot:
                inp = app.query_one(ClipboardInput)
                inp.value = ""
                # 构造右键 MouseDown 事件 (button=3)
                from textual import events
                right_click = events.MouseDown(None, 0, 0, 0, 0, 3, False, False, False)
                await inp._on_mouse_down(right_click)

                assert inp.value == "hello"

    @pytest.mark.asyncio
    async def test_button_2_does_not_trigger(self):
        """button==2（中键）不应触发剪贴板操作。"""
        with patch("toolbox.frontend_tui.app._clipboard_read", return_value="should_not_appear"):
            app = _InputApp()
            async with app.run_test() as pilot:
                inp = app.query_one(ClipboardInput)
                inp.value = "original"
                from textual import events
                middle_click = events.MouseDown(None, 0, 0, 0, 0, 2, False, False, False)
                await inp._on_mouse_down(middle_click)

                # button 2 走 super()._on_mouse_down，不触发剪贴板
                assert inp.value == "original"
