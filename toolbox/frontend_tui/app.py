from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Footer,
    Header,
    Static,
    ListView,
    ListItem,
    Label,
    Input,
    Button,
    Select,
    Checkbox,
)

from toolbox.core.events import (
    ScriptStarted, ScriptOutput, ScriptCompleted, ScriptFailed,
    PromptRequired, ConfirmRequired, PipelineCompleted, ExecutionEnded,
)
from toolbox.core.events import ScriptMeta
from toolbox.frontend_base import FrontendBase


class ScriptMenu(ListView):
    def __init__(self, scripts, pipelines):
        items = []
        self._id_map: dict[str, tuple[str, str]] = {}
        categories: dict[str, list] = {}
        for s in scripts:
            cat = s.category or "未分类"
            categories.setdefault(cat, []).append(s)

        idx = 0
        for cat, cat_scripts in categories.items():
            items.append(ListItem(Label(Text(f"── {cat} ──", style="bold cyan"))))
            for s in cat_scripts:
                safe_id = f"item-{idx}"
                self._id_map[safe_id] = ("script", s.name)
                items.append(ListItem(Label(s.name), id=safe_id))
                idx += 1

        if pipelines:
            items.append(ListItem(Label(Text("── 流水线 ──", style="bold cyan"))))
            for p in pipelines:
                safe_id = f"item-{idx}"
                self._id_map[safe_id] = ("pipeline", p.name)
                items.append(ListItem(Label(p.name), id=safe_id))
                idx += 1

        super().__init__(*items)
        self._scripts = {s.name: s for s in scripts}
        self._pipelines = {p.name: p for p in pipelines}


class OutputPanel(Static):
    def __init__(self):
        super().__init__(id="output-panel")
        self._output_lines: list[str] = []
        self._auto_scroll = True

    def clear_output(self):
        self._output_lines = []

    def write_line(self, line: str):
        self._output_lines.append(line)
        if self._auto_scroll:
            self._render_output()

    def _render_output(self):
        content = "\n".join(self._output_lines[-500:])
        self.update(content)

    def get_output_text(self) -> str:
        return "\n".join(self._output_lines)

    def export_log(self, path: str):
        Path(path).write_text(
            "\n".join(self._output_lines),
            encoding="utf-8",
        )

    def get_line_count(self) -> int:
        return len(self._output_lines)


class ToolBoxTUI(App):
    TITLE = "ToolBox"

    CSS = """
    Screen {
        layout: horizontal;
    }

    #sidebar {
        width: 24;
        border-right: solid green;
        background: $surface;
    }

    #main-area {
        width: 1fr;
    }

    #form-container {
        height: auto;
        padding: 1 2;
    }

    #output-container {
        height: 1fr;
    }

    #output-panel {
        height: 1fr;
        padding: 0 1;
        overflow-y: auto;
    }

    #choice-input {
        dock: bottom;
        height: 3;
        margin: 0 1;
    }

    .form-title {
        text-style: bold;
        margin-bottom: 1;
    }

    .form-label {
        margin-top: 1;
        color: $text-muted;
    }

    .form-input {
        margin-bottom: 1;
    }

    .hidden {
        display: none;
    }
    """

    BINDINGS = [
        Binding("f5", "refresh_menu", "刷新菜单"),
        Binding("f9", "execute", "执行"),
        Binding("f11", "toggle_fullscreen", "全屏输出"),
        Binding("ctrl+s", "export_log", "导出日志"),
        Binding("ctrl+c", "cancel_execution", "中止"),
        Binding("slash", "input_choice", "输入选项"),
    ]

    def __init__(self, core):
        super().__init__()
        self.core = core
        self._current_meta = None
        self._current_type = None
        self._running = False
        self._last_prompt_step_id = None
        self._last_prompt_choices: list[str] = []
        self._mode = "welcome"  # welcome | form | output

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="sidebar"):
                yield ScriptMenu(
                    self.core.list_scripts(),
                    self.core.list_pipelines(),
                )
            with Vertical(id="main-area"):
                with VerticalScroll(id="form-container"):
                    pass
                with Vertical(id="output-container", classes="hidden"):
                    yield OutputPanel()
        yield Footer()

    def on_mount(self):
        self._show_welcome()

    def _show_welcome(self):
        self._mode = "welcome"
        fc = self.query_one("#form-container")
        oc = self.query_one("#output-container")
        fc.remove_class("hidden")
        oc.add_class("hidden")
        fc.query("Static, Input, Select, Checkbox, Button").remove()
        fc.mount(Static(
            "欢迎使用 ToolBox\n\n"
            "选择左侧脚本或流水线开始操作\n\n"
            "快捷键：\n"
            "  F5  刷新菜单\n"
            "  F9  执行\n"
            "  F11 全屏输出\n"
            "  Ctrl+S 导出日志\n"
            "  / 输入选项（流水线交互时）",
            classes="form-title",
        ))

    def _show_form(self, script: ScriptMeta):
        self._mode = "form"
        self._current_type = "script"
        self._current_meta = script
        fc = self.query_one("#form-container")
        oc = self.query_one("#output-container")
        fc.remove_class("hidden")
        oc.add_class("hidden")

        fc.query("Static, Input, Select, Checkbox, Button").remove()

        fc.mount(Static(script.name, classes="form-title"))

        if script.description:
            fc.mount(Static(script.description))

        if not script.params:
            fc.mount(Static("无参数，直接按 F9 执行", classes="form-hint"))
        else:
            for p in script.params:
                fc.mount(Static(f"{p.label} ({p.type}){'  [剪贴板]' if p.clipboard else ''}", classes="form-label"))
                if p.type == "choice" and p.options:
                    opts = [(str(o), str(o)) for o in p.options]
                    fc.mount(Select(opts, id=f"param-{p.name}", classes="form-input"))
                elif p.type == "flag":
                    fc.mount(Checkbox(p.label, id=f"param-{p.name}", classes="form-input",
                                       value=bool(p.default) if p.default is not None else False))
                else:
                    placeholder = f"默认: {p.default}" if p.default is not None else ""
                    fc.mount(Input(
                        id=f"param-{p.name}",
                        classes="form-input",
                        placeholder=placeholder,
                        value=str(p.default) if p.default is not None else "",
                    ))

        fc.mount(Static("\n按 F9 执行", classes="form-hint"))

    def _show_output(self):
        self._mode = "output"
        fc = self.query_one("#form-container")
        oc = self.query_one("#output-container")
        fc.add_class("hidden")
        oc.remove_class("hidden")
        output = self.query_one(OutputPanel)
        output.clear_output()

    def _collect_params(self, script: ScriptMeta) -> dict:
        params = {}
        for p in script.params:
            input_id = f"param-{p.name}"
            try:
                widget = self.query_one(f"#{input_id}")
            except Exception:
                if p.default is not None:
                    params[p.name] = p.default
                continue

            if isinstance(widget, Input):
                val = widget.value.strip()
                if val:
                    params[p.name] = val
                elif p.default is not None:
                    params[p.name] = p.default
            elif isinstance(widget, Select):
                val = widget.value
                if val is not None:
                    params[p.name] = val
                elif p.default is not None:
                    params[p.name] = p.default
            elif isinstance(widget, Checkbox):
                params[p.name] = widget.value
            else:
                if p.default is not None:
                    params[p.name] = p.default
        return params

    def on_list_view_selected(self, event: ListView.Selected):
        item = event.item
        item_id = item.id
        if not item_id:
            return
        if self._running:
            return

        menu = self.query_one(ScriptMenu)
        entry = menu._id_map.get(item_id)
        if not entry:
            return

        item_type, name = entry

        if item_type == "script":
            script = next((s for s in self.core.list_scripts() if s.name == name), None)
            if script:
                self._show_form(script)

        elif item_type == "pipeline":
            self._current_type = "pipeline"
            pipeline = next((p for p in self.core.list_pipelines() if p.name == name), None)
            if pipeline:
                self._current_meta = pipeline
                self._show_pipeline_info(pipeline)

    def _show_pipeline_info(self, pipeline):
        self._mode = "form"
        fc = self.query_one("#form-container")
        oc = self.query_one("#output-container")
        fc.remove_class("hidden")
        oc.add_class("hidden")

        fc.query("Static, Input, Select, Checkbox, Button").remove()

        lines = [pipeline.name, ""]
        if pipeline.description:
            lines.append(pipeline.description)
        lines.append("")
        for s in pipeline.steps:
            if "script" in s:
                lines.append(f"  → {s.get('script', '?')}")
            elif "type" in s:
                lines.append(f"  ◆ {s['type']}")
        lines.append("")
        lines.append("按 F9 执行")
        fc.mount(Static("\n".join(lines)))

    def action_refresh_menu(self):
        self.core.reload()
        sidebar = self.query_one("#sidebar")
        old_menu = sidebar.query_one(ScriptMenu)
        old_menu.remove()
        new_menu = ScriptMenu(
            self.core.list_scripts(),
            self.core.list_pipelines(),
        )
        sidebar.mount(new_menu)

    async def action_execute(self):
        if self._running:
            return
        if self._current_meta is None:
            return

        if self._current_type == "script":
            await self._execute_script(self._current_meta)
        elif self._current_type == "pipeline":
            await self._execute_pipeline(self._current_meta)

    async def _execute_script(self, script):
        self._show_output()
        output = self.query_one(OutputPanel)
        output.write_line(f"── 执行: {script.name} ──\n")

        params = self._collect_params(script)
        self._running = True
        queue = self.core.run_script(script.name, params)
        await self._consume_events(queue)

    async def _execute_pipeline(self, pipeline):
        self._show_output()
        output = self.query_one(OutputPanel)
        output.write_line(f"── 流水线: {pipeline.name} ──\n")

        self._running = True
        queue = self.core.run_pipeline(pipeline.name)
        await self._consume_events(queue)

    def action_toggle_fullscreen(self):
        sidebar = self.query_one("#sidebar")
        if sidebar.styles.display == "none":
            sidebar.styles.display = "block"
        else:
            sidebar.styles.display = "none"

    def action_export_log(self):
        output = self.query_one(OutputPanel)
        if output.get_line_count() == 0:
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = f"toolbox_output_{timestamp}.log"
        output.export_log(log_path)
        output.write_line(f"\n已导出到: {log_path}")

    def action_cancel_execution(self):
        if self._running:
            self.core.cancel()

    async def action_input_choice(self):
        if not self._running:
            return
        try:
            self.query_one("#choice-input").remove()
        except Exception:
            pass
        input_widget = Input(placeholder="输入选项序号...", id="choice-input")
        oc = self.query_one("#output-container")
        oc.mount(input_widget)
        input_widget.focus()

        def on_submit(message):
            text = message.value.strip()
            self._handle_user_choice(text)
            input_widget.remove()

        input_widget.on_submit = on_submit

    def _handle_user_choice(self, text: str):
        if not text:
            return
        if text.isdigit():
            idx = int(text) - 1
            if self._last_prompt_choices and 0 <= idx < len(self._last_prompt_choices):
                self.core.respond_prompt(self._last_prompt_step_id, self._last_prompt_choices[idx])
                return
        self.core.respond_prompt(self._last_prompt_step_id, text)

    async def _consume_events(self, queue: asyncio.Queue):
        output = self.query_one(OutputPanel)
        while True:
            event = await queue.get()
            match event:
                case ScriptOutput(line=line):
                    output.write_line(line)
                case ScriptCompleted(output=out, duration=duration):
                    output.write_line(f"\n── 执行完成 ({duration:.1f}s) ──")
                    if out:
                        for k, v in out.items():
                            output.write_line(f"  {k}: {v}")
                case ScriptFailed(error=error, traceback=tb):
                    output.write_line(f"\n── 执行失败 ──")
                    output.write_line(f"错误: {error}")
                    if tb:
                        for line in tb.strip().split("\n"):
                            output.write_line(f"  {line}")
                case PromptRequired(step_id=step_id, message=message, choices=choices):
                    self._last_prompt_step_id = step_id
                    self._last_prompt_choices = choices or []
                    output.write_line(f"\n{message}")
                    if choices:
                        for i, c in enumerate(choices):
                            output.write_line(f"  [{i + 1}] {c}")
                        output.write_line("\n按 / 输入序号选择")
                case ConfirmRequired(step_id=step_id, message=message):
                    output.write_line(f"\n{message}")
                    output.write_line("  [1] 确认")
                    output.write_line("  [2] 取消")
                    output.write_line("\n按 / 输入选项")
                case PipelineCompleted():
                    output.write_line(f"\n── 流水线完成 ──")
                    self._running = False
                    break
                case ExecutionEnded():
                    self._running = False
                    break
        self._running = False


class TUIFrontend(FrontendBase):
    def run(self):
        app = ToolBoxTUI(self.core)
        app.run()
