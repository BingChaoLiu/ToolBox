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
    Select,
    Checkbox,
)

from toolbox.core.events import (
    ScriptStarted, ScriptOutput, ScriptCompleted, ScriptFailed,
    PromptRequired, ConfirmRequired, PipelineCompleted, ExecutionEnded,
)
from toolbox.core.events import ScriptMeta
from toolbox.frontend_base import FrontendBase

_next_widget_id = 0


def _fresh_id(prefix="w"):
    global _next_widget_id
    _next_widget_id += 1
    return f"{prefix}-{_next_widget_id}"


_STATUS_ICONS = {
    "running": "●",
    "completed": "✔",
    "failed": "✘",
    "cancelled": "⊘",
}


class ExecutionRecord:
    def __init__(self, tid: int, name: str):
        self.tid = tid
        self.name = name
        self.timestamp = datetime.now()
        self.lines: list[str] = []
        self.status = "running"
        self.item_widget: HistoryItem | None = None

    def add_line(self, line: str):
        self.lines.append(line)

    def get_text(self) -> str:
        return "\n".join(self.lines[-500:])

    def get_line_count(self) -> int:
        return len(self.lines)

    def export(self, path: str):
        Path(path).write_text("\n".join(self.lines), encoding="utf-8")


class HistoryItem(Static):
    def __init__(self, record: ExecutionRecord):
        self._record_tid = record.tid
        super().__init__(self._fmt(record), classes=f"history-item status-{record.status}")

    @staticmethod
    def _fmt(record: ExecutionRecord) -> str:
        icon = _STATUS_ICONS.get(record.status, "?")
        time_str = record.timestamp.strftime("%H:%M:%S")
        return f"{icon} {time_str}\n  {record.name}"

    def refresh_display(self, record: ExecutionRecord):
        self.update(self._fmt(record))
        for cls in list(self.classes):
            if cls.startswith("status-"):
                self.remove_class(cls)
        self.add_class(f"status-{record.status}")

    def on_click(self):
        app = self.app
        if isinstance(app, ToolBoxTUI):
            app._select_record(self._record_tid)


class ScriptMenu(ListView):
    def __init__(self, scripts, pipelines, on_select=None):
        self._on_select = on_select
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

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if self._on_select is None:
            return
        item = event.item
        item_id = item.id
        if not item_id:
            return
        entry = self._id_map.get(item_id)
        if entry:
            self._on_select(entry[0], entry[1])


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
        height: auto;
        padding: 0 1;
    }

    #history-panel {
        width: 30;
        border-left: solid green;
        background: $surface;
        padding: 1 0;
    }

    #history-title {
        text-style: bold;
        padding: 0 1;
        margin-bottom: 1;
    }

    .history-item {
        padding: 0 1;
        height: auto;
        border-bottom: dashed $border;
    }

    .history-item:hover {
        text-style: bold;
        background: $surface-darken-1;
    }

    .history-item.selected {
        background: $primary-darken-3;
    }

    .status-running {
        color: $warning;
    }

    .status-completed {
        color: $success;
    }

    .status-failed {
        color: $error;
    }

    .status-cancelled {
        color: $text-muted;
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

    .form-hint {
        color: $text-muted;
    }

    .hidden {
        display: none;
    }

    .choice-input {
        dock: bottom;
        height: 3;
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("f5", "refresh_menu", "刷新菜单"),
        Binding("f9", "execute", "执行"),
        Binding("f11", "toggle_fullscreen", "全屏输出"),
        Binding("f12", "toggle_history", "执行记录"),
        Binding("ctrl+s", "export_log", "导出日志"),
        Binding("ctrl+c", "cancel_execution", "中止"),
        Binding("slash", "input_choice", "输入选项"),
    ]

    def __init__(self, core):
        super().__init__()
        self.core = core
        self._current_meta = None
        self._current_type = None
        self._last_prompt_step_id = None
        self._last_prompt_choices: list[str] = []
        self._choice_input = None
        self._param_widget_ids: dict[str, str] = {}
        self._active_tasks: dict[int, tuple[str, asyncio.Task]] = {}
        self._task_seq = 0
        self._records: dict[int, ExecutionRecord] = {}
        self._current_view_tid: int | None = None

    @property
    def _is_busy(self):
        return any(not t.done() for _, t in self._active_tasks.values())

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="sidebar"):
                yield ScriptMenu(
                    self.core.list_scripts(),
                    self.core.list_pipelines(),
                    on_select=self._on_menu_select,
                )
            with Vertical(id="main-area"):
                with VerticalScroll(id="form-container"):
                    yield Static(
                        "欢迎使用 ToolBox\n\n"
                        "选择左侧脚本或流水线开始操作\n\n"
                        "F5 刷新 | F9 执行 | F11 全屏\n"
                        "F12 执行记录",
                        classes="form-title",
                    )
                with VerticalScroll(id="output-container", classes="hidden"):
                    yield Static(id="output-panel")
            with VerticalScroll(id="history-panel", classes="hidden"):
                yield Static("执行记录", id="history-title")
        yield Footer()

    # ── Menu & form ──────────────────────────────────────────────

    def _on_menu_select(self, item_type: str, name: str):
        if item_type == "script":
            script = next((s for s in self.core.list_scripts() if s.name == name), None)
            if script:
                self._show_form(script)
        elif item_type == "pipeline":
            pipeline = next((p for p in self.core.list_pipelines() if p.name == name), None)
            if pipeline:
                self._current_type = "pipeline"
                self._current_meta = pipeline
                self._show_pipeline_info(pipeline)

    def _clear_form(self):
        fc = self.query_one("#form-container")
        for child in list(fc.children):
            child.remove()

    def _show_form(self, script: ScriptMeta):
        self._current_type = "script"
        self._current_meta = script
        self._clear_form()
        self._param_widget_ids = {}
        fc = self.query_one("#form-container")
        oc = self.query_one("#output-container")
        fc.remove_class("hidden")
        oc.add_class("hidden")

        fc.mount(Static(script.name, classes="form-title"))
        if script.description:
            fc.mount(Static(script.description))

        if not script.params:
            fc.mount(Static("无参数，按 F9 执行", classes="form-hint"))
        else:
            for p in script.params:
                clip = "  [剪贴板]" if p.clipboard else ""
                fc.mount(Static(f"{p.label} ({p.type}){clip}", classes="form-label"))
                wid = _fresh_id("p")
                self._param_widget_ids[p.name] = wid
                if p.type == "choice" and p.options:
                    opts = [(str(o), str(o)) for o in p.options]
                    fc.mount(Select(opts, id=wid, classes="form-input"))
                elif p.type == "flag":
                    fc.mount(Checkbox(p.label, id=wid, classes="form-input",
                                       value=bool(p.default) if p.default is not None else False))
                else:
                    fc.mount(Input(
                        id=wid, classes="form-input",
                        placeholder=f"默认: {p.default}" if p.default is not None else "",
                        value=str(p.default) if p.default is not None else "",
                    ))

        fc.mount(Static("\n按 F9 执行", classes="form-hint"))

    def _show_pipeline_info(self, pipeline):
        self._clear_form()
        fc = self.query_one("#form-container")
        oc = self.query_one("#output-container")
        fc.remove_class("hidden")
        oc.add_class("hidden")

        lines = [pipeline.name, ""]
        if pipeline.description:
            lines.append(pipeline.description)
        lines.append("")
        for s in pipeline.steps:
            if "script" in s:
                lines.append(f"  -> {s.get('script', '?')}")
            elif "type" in s:
                lines.append(f"  * {s['type']}")
        lines.append("")
        lines.append("按 F9 执行")
        fc.mount(Static("\n".join(lines)))

    def _collect_params(self, script: ScriptMeta) -> dict:
        params = {}
        for p in script.params:
            wid = self._param_widget_ids.get(p.name)
            if not wid:
                if p.default is not None:
                    params[p.name] = p.default
                continue
            try:
                widget = self.query_one(f"#{wid}")
            except Exception:
                if p.default is not None:
                    params[p.name] = p.default
                continue

            if isinstance(widget, Input):
                val = widget.value.strip()
                params[p.name] = val if val else (p.default if p.default is not None else val)
            elif isinstance(widget, Select):
                val = widget.value
                params[p.name] = val if val is not None else p.default
            elif isinstance(widget, Checkbox):
                params[p.name] = widget.value
            else:
                params[p.name] = p.default
        return params

    # ── Output display ───────────────────────────────────────────

    def _show_output(self):
        fc = self.query_one("#form-container")
        oc = self.query_one("#output-container")
        fc.add_class("hidden")
        oc.remove_class("hidden")

    def _select_record(self, tid: int):
        record = self._records.get(tid)
        if not record:
            return
        self._current_view_tid = tid
        self._show_output()

        self.query_one("#output-panel").update(record.get_text())

        panel = self.query_one("#history-panel")
        for child in panel.children:
            if isinstance(child, HistoryItem):
                if child._record_tid == tid:
                    child.add_class("selected")
                else:
                    child.remove_class("selected")

        if record.status == "running":
            try:
                self.query_one("#output-container").scroll_end(animate=False)
            except Exception:
                pass

    def _update_output_if_viewing(self, tid: int, record: ExecutionRecord):
        if self._current_view_tid != tid:
            return
        self.query_one("#output-panel").update(record.get_text())
        if record.status == "running":
            try:
                self.query_one("#output-container").scroll_end(animate=False)
            except Exception:
                pass

    def _update_history_item(self, record: ExecutionRecord):
        if record.item_widget:
            record.item_widget.refresh_display(record)

    # ── Actions ──────────────────────────────────────────────────

    def action_refresh_menu(self):
        self.core.reload()
        sidebar = self.query_one("#sidebar")
        old_menu = sidebar.query_one(ScriptMenu)
        old_menu.remove()
        sidebar.mount(ScriptMenu(
            self.core.list_scripts(),
            self.core.list_pipelines(),
            on_select=self._on_menu_select,
        ))

    def _refresh_status(self):
        running = [n for n, t in self._active_tasks.values() if not t.done()]
        if running:
            self.sub_title = " | ".join(running) + " · 执行中"
        else:
            self.sub_title = ""

    async def action_execute(self):
        if self._current_meta is None:
            return

        name = self._current_meta.name

        if self._current_type == "script":
            params = self._collect_params(self._current_meta)
            queue = self.core.run_script(name, params)
        elif self._current_type == "pipeline":
            queue = self.core.run_pipeline(name)
        else:
            return

        self._task_seq += 1
        tid = self._task_seq

        record = ExecutionRecord(tid, name)
        self._records[tid] = record
        record.add_line(f"━━ 执行: {name} ━━\n")

        item = HistoryItem(record)
        record.item_widget = item
        panel = self.query_one("#history-panel")
        panel.mount(item)
        try:
            panel.scroll_end(animate=False)
        except Exception:
            pass

        self._select_record(tid)

        task = asyncio.create_task(self._consume_events(tid, name, queue))
        self._active_tasks[tid] = (name, task)
        self._refresh_status()

    def action_toggle_fullscreen(self):
        self.query_one("#sidebar").toggle_class("hidden")

    def action_toggle_history(self):
        self.query_one("#history-panel").toggle_class("hidden")

    def action_export_log(self):
        record = self._records.get(self._current_view_tid) if self._current_view_tid else None
        if not record or record.get_line_count() == 0:
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = f"toolbox_output_{record.name}_{ts}.log"
        record.export(log_path)
        record.add_line(f"\n已导出到: {log_path}")
        self._update_output_if_viewing(record.tid, record)

    def action_cancel_execution(self):
        for tid, (name, task) in list(self._active_tasks.items()):
            if not task.done():
                task.cancel()
        self._active_tasks.clear()
        self.core.cancel()
        self._refresh_status()

    async def action_input_choice(self):
        if not self._is_busy:
            return
        if self._choice_input is not None:
            try:
                self._choice_input.remove()
            except Exception:
                pass
            self._choice_input = None

        inp = Input(placeholder="输入选项序号...", classes="choice-input")
        self._choice_input = inp
        oc = self.query_one("#output-container")
        oc.mount(inp)
        inp.focus()

        def on_input_submit(message):
            text = message.value.strip()
            self._handle_user_choice(text)
            try:
                inp.remove()
            except Exception:
                pass
            self._choice_input = None

        inp.on_submit = on_input_submit

    def _handle_user_choice(self, text: str):
        if not text or not self._last_prompt_step_id:
            return
        if text.isdigit():
            idx = int(text) - 1
            if self._last_prompt_choices and 0 <= idx < len(self._last_prompt_choices):
                self.core.respond_prompt(self._last_prompt_step_id, self._last_prompt_choices[idx])
                return
        self.core.respond_prompt(self._last_prompt_step_id, text)

    # ── Event consumption (background task) ──────────────────────

    async def _consume_events(self, tid: int, name: str, queue: asyncio.Queue):
        record = self._records.get(tid)
        if not record:
            return
        try:
            while True:
                event = await queue.get()
                match event:
                    case ScriptStarted():
                        pass
                    case ScriptOutput(line=line):
                        record.add_line(line)
                        self._update_output_if_viewing(tid, record)
                    case ScriptCompleted(output=out, duration=duration):
                        record.add_line(f"\n-- {name} 完成 ({duration:.1f}s) --")
                        if out:
                            for k, v in out.items():
                                record.add_line(f"  {k}: {v}")
                        record.status = "completed"
                        self._update_history_item(record)
                        self._update_output_if_viewing(tid, record)
                    case ScriptFailed(error=error, traceback=tb):
                        record.add_line(f"\n-- {name} 失败 --")
                        record.add_line(f"错误: {error}")
                        if tb:
                            for line in tb.strip().split("\n"):
                                record.add_line(f"  {line}")
                        record.status = "failed"
                        self._update_history_item(record)
                        self._update_output_if_viewing(tid, record)
                    case PromptRequired(step_id=step_id, message=message, choices=choices):
                        self._last_prompt_step_id = step_id
                        self._last_prompt_choices = choices or []
                        record.add_line(f"\n{message}")
                        if choices:
                            for i, c in enumerate(choices):
                                record.add_line(f"  [{i + 1}] {c}")
                        record.add_line("\n按 / 输入序号选择")
                        self._update_output_if_viewing(tid, record)
                    case ConfirmRequired(step_id=step_id, message=message):
                        self._last_prompt_step_id = step_id
                        self._last_prompt_choices = ["yes", "no"]
                        record.add_line(f"\n{message}")
                        record.add_line("  [1] 确认")
                        record.add_line("  [2] 取消")
                        record.add_line("\n按 / 输入选项")
                        self._update_output_if_viewing(tid, record)
                    case PipelineCompleted():
                        record.add_line(f"\n-- {name} 流水线完成 --")
                        record.status = "completed"
                        self._update_history_item(record)
                        self._update_output_if_viewing(tid, record)
                        break
                    case ExecutionEnded():
                        if record.status == "running":
                            record.status = "completed"
                            self._update_history_item(record)
                        break
        except asyncio.CancelledError:
            record.add_line(f"\n-- {name} 已取消 --")
            record.status = "cancelled"
            self._update_history_item(record)
            self._update_output_if_viewing(tid, record)
        finally:
            self._active_tasks.pop(tid, None)
            self._refresh_status()

    def on_unmount(self) -> None:
        for tid, (name, task) in list(self._active_tasks.items()):
            if not task.done():
                task.cancel()
        self._active_tasks.clear()


class TUIFrontend(FrontendBase):
    def run(self):
        app = ToolBoxTUI(self.core)
        app.run()
