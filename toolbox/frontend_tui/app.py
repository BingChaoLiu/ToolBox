from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Footer,
    Header,
    Static,
    ListView,
    ListItem,
    Label,
    Input,
)

from toolbox.core.events import (
    ScriptStarted, ScriptOutput, ScriptCompleted, ScriptFailed,
    PromptRequired, ConfirmRequired, PipelineCompleted, ExecutionEnded,
)
from toolbox.frontend_base import FrontendBase


class ScriptMenu(ListView):
    def __init__(self, scripts, pipelines):
        items = []
        self._id_map: dict[str, tuple[str, str]] = {}  # safe_id → (type, name)
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


class ContentPanel(Static):
    def __init__(self):
        super().__init__(id="content-panel")
        self._output_lines: list[str] = []
        self._auto_scroll = True

    def show_welcome(self):
        self.update(Text.from_markup(
            "[bold]ToolBox[/bold]\n\n"
            "选择左侧脚本或流水线开始操作\n\n"
            "快捷键：\n"
            "  F5  刷新菜单\n"
            "  F9  执行\n"
            "  F11 全屏输出\n"
            "  Ctrl+S 导出日志\n"
            "  / 输入选项（流水线交互时）\n"
        ))

    def clear_output(self):
        self._output_lines = []

    def write_line(self, line: str):
        self._output_lines.append(line)
        if self._auto_scroll:
            self._render_output()

    def _render_output(self):
        content = "\n".join(self._output_lines[-500:])
        self.update(content)

    def set_auto_scroll(self, enabled: bool):
        self._auto_scroll = enabled
        if enabled:
            self._render_output()

    def get_output_text(self) -> str:
        return "\n".join(self._output_lines)

    def search(self, keyword: str) -> list[int]:
        matches = []
        for i, line in enumerate(self._output_lines):
            if keyword.lower() in line.lower():
                matches.append(i)
        return matches

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

    #content-panel {
        height: 1fr;
        padding: 0 1;
        overflow-y: auto;
    }

    #choice-input {
        dock: bottom;
        height: 3;
        margin: 0 1;
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

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="sidebar"):
                yield ScriptMenu(
                    self.core.list_scripts(),
                    self.core.list_pipelines(),
                )
            with Vertical(id="main-area"):
                yield ContentPanel()
        yield Footer()

    def on_mount(self):
        content = self.query_one(ContentPanel)
        content.show_welcome()

    def on_list_view_selected(self, event: ListView.Selected):
        item = event.item
        item_id = item.id
        if not item_id:
            return

        menu = self.query_one(ScriptMenu)
        entry = menu._id_map.get(item_id)
        if not entry:
            return

        item_type, name = entry

        if item_type == "script":
            self._current_type = "script"
            script = next((s for s in self.core.list_scripts() if s.name == name), None)
            if script:
                self._current_meta = script
                self._show_script_form(script)

        elif item_type == "pipeline":
            self._current_type = "pipeline"
            pipeline = next((p for p in self.core.list_pipelines() if p.name == name), None)
            if pipeline:
                self._current_meta = pipeline
                self._show_pipeline_info(pipeline)

    def _show_script_form(self, script):
        content = self.query_one(ContentPanel)
        lines = [f"[bold]{script.name}[/bold]\n"]

        if not script.params:
            lines.append("[dim]无参数，直接按 F9 执行[/dim]")
        else:
            lines.append("[bold]参数（手动输入后按 F9 执行）:[/]\n")
            for p in script.params:
                suffix = ""
                if p.clipboard:
                    suffix += " [dim][剪贴板][/dim]"
                if p.type == "choice":
                    if p.options:
                        opts = ", ".join(str(o) for o in p.options)
                        lines.append(f"  {p.label} ({p.type}) 选项: {opts}{suffix}")
                    else:
                        lines.append(f"  {p.label} ({p.type}) (从配置加载){suffix}")
                elif p.type == "flag":
                    default_val = p.default if p.default is not None else False
                    lines.append(f"  {p.label} ({p.type}) 默认: {default_val}{suffix}")
                else:
                    default_hint = f" 默认: {p.default}" if p.default is not None else ""
                    lines.append(f"  {p.label} ({p.type}){default_hint}{suffix}")

        content.update(Text.from_markup("\n".join(lines)))

    def _show_pipeline_info(self, pipeline):
        content = self.query_one(ContentPanel)
        lines = [f"[bold]{pipeline.name}[/bold] (流水线)"]
        if pipeline.description:
            lines.append(f"\n{pipeline.description}")
        step_names = []
        for s in pipeline.steps:
            if "script" in s:
                step_names.append(f"  → {s.get('script', '?')}")
            elif "type" in s:
                step_names.append(f"  ◆ {s['type']}")
        if step_names:
            lines.append("\n[bold]步骤:[/]")
            lines.extend(step_names)
        lines.append("\n[dim]按 F9 执行[/dim]")
        content.update(Text.from_markup("\n".join(lines)))

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
        content = self.query_one(ContentPanel)
        content.clear_output()
        content.write_line(f"── 执行: {script.name} ──\n")

        params = {}
        for p in script.params:
            if p.default is not None:
                params[p.name] = p.default

        self._running = True
        queue = self.core.run_script(script.name, params)
        await self._consume_events(queue)

    async def _execute_pipeline(self, pipeline):
        content = self.query_one(ContentPanel)
        content.clear_output()
        content.write_line(f"── 流水线: {pipeline.name} ──\n")

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
        content = self.query_one(ContentPanel)
        if content.get_line_count() == 0:
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = f"toolbox_output_{timestamp}.log"
        content.export_log(log_path)
        content.write_line(f"\n[dim]已导出到: {log_path}[/dim]")

    def action_cancel_execution(self):
        if self._running:
            self.core.cancel()

    async def action_input_choice(self):
        if not self._running:
            return
        input_widget = Input(placeholder="输入选项序号...", id="choice-input")
        mount_target = self.query_one("#main-area")
        mount_target.mount(input_widget)
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
        content = self.query_one(ContentPanel)
        while True:
            event = await queue.get()
            match event:
                case ScriptOutput(line=line):
                    content.write_line(line)
                case ScriptCompleted(output=output, duration=duration):
                    content.write_line(f"\n── 执行完成 ({duration:.1f}s) ──")
                    if output:
                        for k, v in output.items():
                            content.write_line(f"  {k}: {v}")
                case ScriptFailed(error=error, traceback=traceback_str):
                    content.write_line(f"\n── 执行失败 ──")
                    content.write_line(f"错误: {error}")
                    if traceback_str:
                        for line in traceback_str.strip().split("\n"):
                            content.write_line(f"  {line}")
                case PromptRequired(step_id=step_id, message=message, choices=choices):
                    self._last_prompt_step_id = step_id
                    self._last_prompt_choices = choices or []
                    content.write_line(f"\n[bold]{message}[/]")
                    if choices:
                        for i, c in enumerate(choices):
                            content.write_line(f"  [{i + 1}] {c}")
                        content.write_line("\n[dim]按 / 输入序号选择[/dim]")
                case ConfirmRequired(step_id=step_id, message=message):
                    content.write_line(f"\n[bold]{message}[/]")
                    content.write_line("  [1] 确认")
                    content.write_line("  [2] 取消")
                    content.write_line("\n[dim]按 / 输入选项[/dim]")
                case PipelineCompleted(pipeline_name=pipeline_name):
                    content.write_line(f"\n── 流水线完成 ──")
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
