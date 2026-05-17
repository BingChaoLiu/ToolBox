from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual import events
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
    Button,
    TextArea,
    RichLog,
)
from textual.containers import Horizontal, Vertical, VerticalScroll

from toolbox import __version__
from toolbox.core.events import (
    ScriptStarted, ScriptOutput, ScriptCompleted, ScriptFailed,
    PromptRequired, ConfirmRequired, PipelineCompleted, ExecutionEnded,
    ResourceUpdate
)
from toolbox.core.events import ScriptMeta
from toolbox.frontend_base import FrontendBase

from lib.formatter import format_line


def _clipboard_copy(text: str):
    from lib.clipboard import write as clip_write
    clip_write(text)


def _clipboard_read() -> str | None:
    from lib.clipboard import read as clip_read
    return clip_read()


class ClipboardInput(Input):
    """支持右键复制/粘贴的输入框。"""

    async def _on_mouse_down(self, event: events.MouseDown) -> None:
        if event.button == 3:
            self._handle_right_click()
            event.stop()
            event._no_default_action = True  # 阻止 Input._on_mouse_down 再次执行
            return
        await super()._on_mouse_down(event)

    def _handle_right_click(self):
        try:
            selected = self.selected_text
            if selected:
                _clipboard_copy(selected)
                self.app.notify(f"已复制 {len(selected)} 个字符", title="复制成功")
                return
        except Exception:
            pass

        try:
            text = _clipboard_read()
            if text:
                self.value = text.splitlines()[0].strip()
                self.app.notify("已粘贴文本", title="粘贴成功")
        except Exception:
            pass


class ClipboardTextArea(TextArea):
    """支持右键复制/粘贴的文本区域。"""

    async def _on_mouse_down(self, event: events.MouseDown) -> None:
        if event.button == 3:
            self._handle_right_click()
            event.stop()
            event._no_default_action = True  # 阻止 TextArea._on_mouse_down 再次执行
            return
        await super()._on_mouse_down(event)

    def _handle_right_click(self):
        try:
            selected = self.selected_text
            if selected:
                _clipboard_copy(selected)
                self.app.notify(f"已复制 {len(selected)} 个字符", title="复制成功")
                return
        except Exception:
            pass

        try:
            text = _clipboard_read()
            if text:
                self.load_text(text)
                self.scroll_cursor_visible()
                self.app.notify(f"已粘贴 {len(text.splitlines())} 行文本", title="粘贴成功")
        except Exception:
            pass


_next_widget_id = 0


def _fresh_id(prefix="w"):
    global _next_widget_id
    _next_widget_id += 1
    return f"{prefix}-{_next_widget_id}"


_STATUS_ICONS = {
    "running": "⏳",
    "completed": "✅",
    "failed": "❌",
    "cancelled": "🚫",
}

_CATEGORY_ICONS = {
    "工具": "🛠️",
    "Git": "🌿",
    "编译": "🏗️",
    "分析": "🔍",
    "未分类": "📄",
}


class ExecutionRecord:
    def __init__(self, tid: int, name: str):
        self.tid = tid
        self.name = name
        self.timestamp = datetime.now()
        self.lines: list[str] = []
        self.status = "running"
        self.item_widget: HistoryItem | None = None
        self.pending_interaction: dict | None = None

    def add_line(self, line: str):
        self.lines.append(line)

    def get_text(self) -> str:
        return "\n".join(self.lines)

    def get_line_count(self) -> int:
        return len(self.lines)

    def export(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.get_text())


class HistoryItem(ListItem):
    def __init__(self, record: ExecutionRecord):
        super().__init__(id=f"history-{record.tid}", classes="history-item")
        self._record_tid = record.tid
        self.label = Label("")
        self.refresh_display(record)

    def compose(self) -> ComposeResult:
        yield self.label

    def refresh_display(self, record: ExecutionRecord):
        icon = _STATUS_ICONS.get(record.status, "•")
        time_str = record.timestamp.strftime("%H:%M:%S")
        self.label.update(f"{icon} {record.name} [dim]({time_str})[/]")
        for cls in ["status-running", "status-completed", "status-failed", "status-cancelled"]:
            if self.has_class(cls) and cls != f"status-{record.status}":
                self.remove_class(cls)
        self.add_class(f"status-{record.status}")

    def on_click(self):
        app = self.app
        if isinstance(app, ToolBoxTUI):
            app._select_record(self._record_tid)


class ResourceMonitor(Static):
    def __init__(self):
        super().__init__("📊 CPU: 0% | 🧠 MEM: 0% (0MB)", id="resource-monitor")
        self.add_class("hidden")

    def update_stats(self, cpu: float, mem_p: float, mem_mb: float):
        self.update(f"📊 CPU: [cyan]{cpu:>3.1f}%[/] | 🧠 MEM: [magenta]{mem_p:>3.1f}% ({mem_mb:>4.1f}MB)[/]")


class InteractionPanel(Static):
    def __init__(self):
        super().__init__(id="interaction-panel")
        self.add_class("hidden")
        self._tid = None
        self._step_id = None
        self._choices: list[str] | None = None

    def show_prompt(self, tid: int, step_id: str, message: str, choices: list[str] | None):
        self._tid = tid
        self._step_id = step_id
        self._choices = choices
        self.remove_class("hidden")
        for child in list(self.children):
            child.remove()
        
        self.mount(Label(f"[bold yellow]交互请求:[/]\n{message}"))
        if choices:
            container = Horizontal(classes="choice-buttons")
            self.mount(container)
            for i, c in enumerate(choices):
                btn = Button(c, id=f"choice-{i}")
                btn._choice_val = c
                container.mount(btn)
        else:
            inp = ClipboardInput(placeholder="请输入...")
            inp.id = "prompt-input"
            self.mount(inp)
            inp.focus()

    def show_confirm(self, tid: int, step_id: str, message: str):
        self._tid = tid
        self._step_id = step_id
        self.remove_class("hidden")
        for child in list(self.children):
            child.remove()
        
        self.mount(Label(f"[bold yellow]确认请求:[/]\n{message}"))
        container = Horizontal(classes="choice-buttons")
        self.mount(container)
        container.mount(Button("确认", variant="success", id="confirm-yes"))
        container.mount(Button("取消", variant="error", id="confirm-no"))

    def hide(self):
        self.add_class("hidden")
        self._tid = None
        self._step_id = None


class ScriptMenu(ListView):
    def __init__(self, scripts, pipelines, on_select):
        self._on_select = on_select
        self._id_map = {}
        self._scripts = {s.name: s for s in scripts}
        self._pipelines = {p.name: p for p in pipelines}
        self._all_scripts = list(scripts)
        self._all_pipelines = list(pipelines)
        items = self._build_items(scripts, pipelines)
        super().__init__(*items)

    def _build_items(self, scripts, pipelines, filter_text: str = "") -> list[ListItem]:
        items = []
        self._id_map = {}
        idx = 0
        ft = filter_text.lower()

        categories = {}
        for s in scripts:
            cat = s.category or "未分类"
            categories.setdefault(cat, []).append(s)

        for cat, cat_scripts in categories.items():
            icon = _CATEGORY_ICONS.get(cat, "📄")
            items.append(ListItem(Label(Text(f"{icon} {cat}", style="bold cyan"))))
            for s in cat_scripts:
                safe_id = f"item-{idx}"
                self._id_map[safe_id] = ("script", s.name)
                items.append(ListItem(Label(f"  {s.name}"), id=safe_id))
                idx += 1

        if pipelines:
            items.append(ListItem(Label(Text("⛓️ 流水线", style="bold cyan"))))
            for p in pipelines:
                safe_id = f"item-{idx}"
                self._id_map[safe_id] = ("pipeline", p.name)
                items.append(ListItem(Label(f"  {p.name}"), id=safe_id))
                idx += 1

        return items

    def filter(self, text: str):
        """按关键词过滤脚本和流水线。"""
        ft = text.lower().strip()
        if not ft:
            filtered_scripts = self._all_scripts
            filtered_pipelines = self._all_pipelines
        else:
            filtered_scripts = [
                s for s in self._all_scripts
                if ft in s.name.lower() or ft in (s.description or "").lower()
            ]
            filtered_pipelines = [
                p for p in self._all_pipelines
                if ft in p.name.lower() or ft in (p.description or "").lower()
            ]

        new_items = self._build_items(filtered_scripts, filtered_pipelines, ft)
        # 清空并重建列表
        for child in list(self.children):
            child.remove()
        for item in new_items:
            self.mount(item)

    def on_list_view_selected(self, event: ListView.Selected):
        item_id = event.item.id
        if not item_id:
            return
        entry = self._id_map.get(item_id)
        if entry:
            self._on_select(entry[0], entry[1])


class ToolBoxTUI(App):
    TITLE = "ToolBox"

    # CSS 样式定义：调整此处可以改变软件的视觉外观
    CSS = """
    /* 基础屏幕背景 */
    Screen {
        background: $surface;
    }

    /* 顶部标题栏 */
    #app-title {
        background: $primary-darken-3;
        color: $text;
        height: 1;
        content-align: center middle;
        text-style: bold;
        dock: top;
        width: 100%;
    }

    /* 搜索框 */
    #menu-search {
        dock: top;
        height: 3;
        padding: 0 1;
        border: none;
        background: $surface-darken-1;
        margin-bottom: 1;
    }

    /* 左侧侧边栏：包含脚本和流水线列表 */
    #sidebar {
        width: 30;
        background: $surface-darken-2;
        border-right: solid $surface;
    }

    /* 中间主操作区 */
    #main-area {
        width: 1fr;
        background: $surface;
    }

    /* 修复 Command Palette (F1) 样式为居中 Modal */
    CommandPalette {
        background: rgba(0, 0, 0, 0.5);
        align: center middle;
    }
    
    CommandPalette > Vertical {
        width: 60;
        height: auto;
        max-height: 20;
        border: solid $primary;
        background: $surface;
    }

    /* 资源监控栏：显示在主区域顶部 */
    #resource-monitor {
        background: transparent;
        color: $text-muted;
        padding: 0 2;
        dock: top;
        height: 1;
        text-align: right;
        text-style: italic;
        opacity: 0.6;
    }

    /* 底部交互面板：用于 Prompt 和 Confirm */
    #interaction-panel {
        background: $surface-lighten-1;
        padding: 1 4;
        height: auto;
        dock: bottom;
        border-top: solid $primary-darken-2;
    }

    /* 交互面板内的按钮容器 */
    .choice-buttons {
        margin-top: 1;
        height: 3;
    }

    /* 交互面板内的通用按钮样式 */
    .choice-buttons Button {
        border: none;
        background: $primary-darken-2;
        color: $text;
        min-width: 12;
        margin-right: 2;
        padding: 0 2;
    }

    .choice-buttons Button:hover {
        background: $primary;
        text-style: bold;
    }

    /* 脚本参数表单容器 */
    #form-container {
        height: auto;
        padding: 2 4;
    }

    /* 脚本运行输出容器 */
    #output-container {
        height: 1fr;
        margin: 0;
    }

    /* 输出面板 (RichLog) */
    #output-panel {
        padding: 1 2;
        color: $text;
        height: 1fr;
    }

    /* 输出面板工具栏 */
    #output-toolbar {
        height: 3;
        padding: 0 1;
        background: $surface-darken-2;
        border-bottom: solid $surface;
    }

    #output-toolbar Button {
        min-width: 0;
        height: 1;
        margin-right: 1;
        padding: 0 2;
        border: none;
        background: transparent;
    }

    #output-toolbar Button:hover {
        background: $primary-darken-2;
    }

    #output-toolbar Button:focus {
        background: $primary;
    }

    /* 右侧历史记录面板 */
    #history-panel {
        width: 32;
        background: $surface-darken-2;
        border-left: solid $surface;
    }

    /* 历史面板标题 */
    #history-title {
        text-style: bold;
        padding: 1 2;
        color: $secondary;
        background: $surface-darken-3;
    }

    /* 单个历史条目样式 */
    .history-item {
        padding: 1 2;
        height: auto;
        border: none;
    }

    .history-item:hover {
        background: $surface-darken-1;
    }

    /* 选中时的历史条目高亮 */
    .history-item.selected {
        background: $primary-darken-3;
        border-left: solid $primary;
    }

    /* 状态颜色定义 */
    .status-running { color: $warning; }
    .status-completed { color: $success; }
    .status-failed { color: $error; }
    .status-cancelled { color: $text-muted; }

    /* 表单中的标题（脚本名） */
    .form-title {
        text-style: bold;
        color: $primary;
        margin-bottom: 2;
    }

    /* 表单中的参数标签 */
    .form-label {
        margin-top: 1;
        color: $secondary;
        text-style: bold;
    }

    /* 表单中的输入框/下拉框样式 */
    .form-input {
        margin-bottom: 1;
        content-align: left middle;
        height: 3;
        padding: 0 1;
        border: none;
        background: $surface-darken-1;
    }

    /* 通用隐藏样式 */
    .hidden {
        display: none;
    }
    """

    BINDINGS = [
        Binding("f5", "refresh_menu", "刷新菜单"),
        Binding("f9", "execute", "执行"),
        Binding("f11", "toggle_fullscreen", "全屏输出"),
        Binding("f12", "toggle_history", "执行记录"),
        Binding("ctrl+s", "export_log", "导出日志"),
        Binding("ctrl+c", "cancel_execution", "中止"),
        Binding("slash", "focus_search", "搜索"),
        Binding("ctrl+q", "quit", "退出"),
    ]

    def __init__(self, core):
        super().__init__()
        self.core = core
        self._current_meta = None
        self._current_type = None
        self._param_widget_ids: dict[str, str] = {}
        self._active_tasks: dict[int, tuple[str, asyncio.Task]] = {}
        self._task_seq = 0
        self._records: dict[int, ExecutionRecord] = {}
        self._current_view_tid: int | None = None
        self._lines_displayed: int = 0

    @property
    def _is_busy(self):
        return any(not t.done() for _, t in self._active_tasks.values())

    def compose(self) -> ComposeResult:
        yield Static(f"ToolBox v{__version__} — 开发者工作流利器", id="app-title")
        with Horizontal():
            with Vertical(id="sidebar"):
                yield Input(placeholder="🔍 搜索脚本/流水线...", id="menu-search")
                yield ScriptMenu(
                    self.core.list_scripts(),
                    self.core.list_pipelines(),
                    on_select=self._on_menu_select,
                )
            with Vertical(id="main-area"):
                yield ResourceMonitor()
                with VerticalScroll(id="form-container"):
                    yield Static(
                        "🚀 [bold]ToolBox[/]\n\n"
                        "💡 [italic]选择左侧脚本或流水线开始操作[/]\n\n"
                        "⌨️  快捷键指南:\n"
                        "   • [reverse]F5[/]  刷新菜单\n"
                        "   • [reverse]F9[/]  执行当前任务\n"
                        "   • [reverse]F11[/] 切换全屏视图\n"
                        "   • [reverse]F12[/] 展开/隐藏历史记录\n"
                        "   • [reverse]/[/]    搜索脚本/流水线\n"
                        "   • [reverse]^S[/]  导出当前日志\n"
                        "   • [reverse]^C[/]  中止任务\n"
                        "   • [reverse]^Q[/]  退出程序",
                        classes="form-title",
                    )
                with Vertical(id="output-container", classes="hidden"):
                    yield Horizontal(
                        Button("🔍", id="btn-search", variant="default"),
                        Button("📋 复制", id="btn-copy", variant="default"),
                        Button("💾 导出", id="btn-export", variant="default"),
                        Button("🗑 清屏", id="btn-clear", variant="default"),
                        id="output-toolbar",
                    )
                    yield RichLog(id="output-panel", highlight=True, markup=True)
                yield InteractionPanel()
            with VerticalScroll(id="history-panel", classes="hidden"):
                yield Static("📜 执行历史", id="history-title")
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
        try:
            fc = self.query_one("#form-container")
            for child in list(fc.children):
                child.remove()
        except Exception:
            pass

    def _show_form(self, script: ScriptMeta):
        self._current_type = "script"
        self._current_meta = script
        self._clear_form()
        self._param_widget_ids = {}
        
        fc = self.query_one("#form-container")
        oc = self.query_one("#output-container")
        fc.remove_class("hidden")
        oc.add_class("hidden")

        fc.mount(Static(f"📝 {script.name}", classes="form-title"))
        if script.description:
            fc.mount(Static(f"{script.description}\n", classes="form-hint"))

        for p in script.params:
            fc.mount(Label(f"{p.label or p.name}:", classes="form-label"))
            widget_id = _fresh_id("param")
            self._param_widget_ids[p.name] = widget_id

            if p.type == "choice":
                options = []
                if p.options:
                    options = [(str(c), str(c)) for c in p.options]
                elif p.options_from:
                    from toolbox.core.config_loader import resolve_value
                    # 支持两种格式：
                    # 1. dict 格式: options_from: {source: "config:xxx", label_field: ..., value_field: ...}
                    # 2. 简写格式: options_from: "config:xxx" (直接传字符串)
                    if isinstance(p.options_from, str):
                        # 简写格式
                        resolved_options = resolve_value(p.options_from, self.core.get_config())
                        if isinstance(resolved_options, list):
                            for opt in resolved_options:
                                options.append((str(opt), str(opt)))
                    elif isinstance(p.options_from, dict):
                        source = p.options_from.get("source")
                        if source:
                            resolved_options = resolve_value(source, self.core.get_config())
                            if isinstance(resolved_options, list):
                                label_field = p.options_from.get("label_field")
                                value_field = p.options_from.get("value_field")
                                for opt in resolved_options:
                                    if isinstance(opt, dict) and label_field and value_field:
                                        options.append((str(opt.get(label_field, "")), str(opt.get(value_field, ""))))
                                    else:
                                        options.append((str(opt), str(opt)))
                
                # 确保 value 合法，如果 options 为空或 value 不在 options 中，使用 Select.NULL 或 Select.BLANK
                # Textual 不同版本的 sentinel 名称不同 (NULL 或 BLANK)
                sentinel = getattr(Select, "NULL", getattr(Select, "BLANK", None))
                default_val = str(p.default) if p.default is not None else None
                valid_value = sentinel
                
                if default_val is not None:
                    if any(str(opt[1]) == default_val for opt in options):
                        valid_value = default_val

                fc.mount(Select(
                    options,
                    value=valid_value,
                    id=widget_id,
                    classes="form-input",
                    allow_blank=True,
                ))
            elif p.type == "bool" or p.type == "flag":
                fc.mount(Checkbox(
                    p.label or p.name,
                    value=bool(p.default),
                    id=widget_id,
                    classes="form-input",
                ))
            else:
                if getattr(p, "multiline", False):
                    widget = ClipboardTextArea(
                        text=str(p.default) if p.default is not None else "",
                        id=widget_id,
                        classes="form-input",
                    )
                    widget.styles.height = 10  # 多行文本框默认高度
                    fc.mount(widget)
                else:
                    fc.mount(ClipboardInput(
                        value=str(p.default) if p.default is not None else "",
                        placeholder=p.description or "",
                        id=widget_id,
                        classes="form-input",
                    ))

    def _show_pipeline_info(self, pipeline: PipelineMeta):
        self._clear_form()
        fc = self.query_one("#form-container")
        oc = self.query_one("#output-container")
        fc.remove_class("hidden")
        oc.add_class("hidden")

        fc.mount(Static(f"⛓️ {pipeline.name}", classes="form-title"))
        if pipeline.description:
            fc.mount(Static(f"{pipeline.description}\n", classes="form-hint"))

        fc.mount(Label("流水线步骤:", classes="form-label"))
        for i, step in enumerate(pipeline.steps):
            sid = step.get("id", f"step_{i}")
            stype = step.get("type", "script")
            fc.mount(Static(f"  {i+1}. [{stype}] {sid}", classes="form-hint"))

    def _collect_params(self, script: ScriptMeta) -> dict:
        params = {}
        for p in script.params:
            widget_id = self._param_widget_ids.get(p.name)
            if widget_id:
                try:
                    widget = self.query_one(f"#{widget_id}")
                    if isinstance(widget, Input):
                        params[p.name] = widget.value
                    elif isinstance(widget, Select):
                        val = widget.value
                        # 处理 Textual 的 sentinel (NULL 或 BLANK)
                        sentinel = getattr(Select, "NULL", getattr(Select, "BLANK", None))
                        params[p.name] = None if val == sentinel else val
                    elif isinstance(widget, Checkbox):
                        params[p.name] = widget.value
                    elif isinstance(widget, TextArea):
                        params[p.name] = widget.text
                except Exception:
                    params[p.name] = p.default
        return params

    def _show_output(self):
        try:
            fc = self.query_one("#form-container")
            oc = self.query_one("#output-container")
            fc.add_class("hidden")
            oc.remove_class("hidden")
            oc.focus()
        except Exception:
            pass

    def _select_record(self, tid: int):
        record = self._records.get(tid)
        if not record:
            return
        self._current_view_tid = tid
        self._show_output()

        try:
            rich_log = self.query_one("#output-panel", RichLog)
            rich_log.clear()
            for line in record.lines:
                rich_log.write(format_line(line))
            self._lines_displayed = len(record.lines)

            # 更新交互面板
            ip = self.query_one(InteractionPanel)
            if record.pending_interaction:
                pi = record.pending_interaction
                if pi["type"] == "prompt":
                    ip.show_prompt(tid, pi["step_id"], pi["message"], pi["choices"])
                else:
                    ip.show_confirm(tid, pi["step_id"], pi["message"])
            else:
                ip.hide()

            panel = self.query_one("#history-panel")
            for child in panel.children:
                if isinstance(child, HistoryItem):
                    if child._record_tid == tid:
                        child.add_class("selected")
                    else:
                        child.remove_class("selected")

            if record.status in ("running", "completed"):
                try:
                    rich_log.scroll_end(animate=False)
                except Exception:
                    pass
        except Exception:
            pass

    def _update_output_if_viewing(self, tid: int, record: ExecutionRecord):
        if self._current_view_tid != tid:
            return
        try:
            rich_log = self.query_one("#output-panel", RichLog)
            for line in record.lines[self._lines_displayed:]:
                rich_log.write(format_line(line))
            self._lines_displayed = len(record.lines)
        except Exception:
            pass

    def _update_history_item(self, record: ExecutionRecord):
        if record.item_widget:
            record.item_widget.refresh_display(record)

    def _refresh_status(self):
        try:
            busy = [name for name, t in self._active_tasks.values() if not t.done()]
            title_widget = self.query_one("#app-title")
            if busy:
                self.sub_title = f"正在运行: {', '.join(busy)}"
                title_widget.update(f"ToolBox — {self.sub_title}")
            else:
                self.sub_title = ""
                title_widget.update("ToolBox — 开发者工作流利器")
        except Exception:
            pass

    # ── Actions ──────────────────────────────────────────────────

    def action_refresh_menu(self):
        self.core.reload()
        try:
            sidebar = self.query_one("#sidebar")
            old_menu = sidebar.query_one(ScriptMenu)
            old_menu.remove()

            new_menu = ScriptMenu(
                self.core.list_scripts(),
                self.core.list_pipelines(),
                on_select=self._on_menu_select,
            )
            sidebar.mount(new_menu)

            search = self.query_one("#menu-search")
            search.value = ""
            self.notify("菜单已刷新", title="刷新成功")
        except Exception as e:
            self.notify(f"刷新失败: {e}", title="错误", severity="error")

    def action_focus_search(self):
        """聚焦到搜索框。"""
        try:
            self.query_one("#menu-search").focus()
        except Exception:
            pass

    async def action_execute(self):
        if not self._current_meta:
            return
        
        name = self._current_meta.name
        queue = None

        if self._current_type == "script":
            params = self._collect_params(self._current_meta)
            queue = self.core.run_script(name, params)
        elif self._current_type == "pipeline":
            self._task_seq += 1
            tid = self._task_seq
            queue = self.core.run_pipeline(name, tid=tid)
        else:
            return

        if self._current_type == "script":
            self._task_seq += 1
            tid = self._task_seq

        record = ExecutionRecord(tid, name)
        self._records[tid] = record
        record.add_line(f"━━ 执行: {name} ━━\n")

        self._current_view_tid = tid
        self._show_output()

        # 添加到历史面板
        try:
            history_panel = self.query_one("#history-panel")
            item = HistoryItem(record)
            record.item_widget = item
            history_panel.mount(item)
            self._select_record(tid)
        except Exception:
            pass

        # 启动事件消费任务
        task = asyncio.create_task(self._consume_events(tid, name, queue))
        self._active_tasks[tid] = (name, task)
        self._refresh_status()

    def action_toggle_fullscreen(self):
        try:
            self.query_one("#sidebar").toggle_class("hidden")
        except Exception:
            pass

    def action_toggle_history(self):
        try:
            self.query_one("#history-panel").toggle_class("hidden")
        except Exception:
            pass

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
                record = self._records.get(tid)
                if record:
                    record.add_line("\n[!] 正在中止任务...")
                    self._update_output_if_viewing(tid, record)
                task.cancel()
        self._active_tasks.clear()
        self.core.cancel()
        self._refresh_status()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id

        # 工具栏按钮
        if btn_id and btn_id.startswith("btn-"):
            self._on_toolbar_button(btn_id)
            return

        # 交互面板按钮
        try:
            ip = self.query_one(InteractionPanel)
            if ip._tid is None or ip._step_id is None:
                return

            if btn_id == "confirm-yes":
                self.core.respond_confirm(ip._tid, ip._step_id, True)
            elif btn_id == "confirm-no":
                self.core.respond_confirm(ip._tid, ip._step_id, False)
            elif btn_id and btn_id.startswith("choice-"):
                val = getattr(event.button, "_choice_val", "")
                self.core.respond_prompt(ip._tid, ip._step_id, val)
            else:
                return

            record = self._records.get(ip._tid)
            if record:
                record.pending_interaction = None
            ip.hide()
        except Exception:
            pass

    def _on_toolbar_button(self, btn_id: str):
        record = self._records.get(self._current_view_tid) if self._current_view_tid else None
        if btn_id == "btn-search":
            self.action_toggle_search()
        elif btn_id == "btn-copy":
            if record and record.get_line_count() > 0:
                _clipboard_copy(record.get_text())
                self.notify("已复制到剪贴板")
        elif btn_id == "btn-export":
            self.action_export_log()
        elif btn_id == "btn-clear":
            if record:
                record.lines.clear()
                self._lines_displayed = 0
                try:
                    self.query_one("#output-panel", RichLog).clear()
                except Exception:
                    pass

    def action_toggle_search(self):
        """Ctrl+F 切换搜索栏（Task 4 完整实现）。"""
        pass

    def on_input_submitted(self, event: Input.Submitted) -> None:
        try:
            # 搜索框回车 → 聚焦到菜单
            if event.input.id == "menu-search":
                try:
                    self.query_one(ScriptMenu).focus()
                except Exception:
                    pass
                return

            ip = self.query_one(InteractionPanel)
            if ip._tid is None or ip._step_id is None:
                return
            if event.input.id == "prompt-input":
                val = event.value.strip()
                self.core.respond_prompt(ip._tid, ip._step_id, val)
                record = self._records.get(ip._tid)
                if record:
                    record.pending_interaction = None
                ip.hide()
        except Exception:
            pass

    def on_input_changed(self, event: Input.Changed) -> None:
        """搜索框输入变化时实时过滤菜单。"""
        if event.input.id == "menu-search":
            try:
                menu = self.query_one(ScriptMenu)
                menu.filter(event.value)
            except Exception:
                pass

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
                        try:
                            self.query_one(ResourceMonitor).remove_class("hidden")
                        except Exception:
                            pass
                    case ResourceUpdate(cpu_percent=cpu, memory_percent=mem_p, memory_mb=mem_mb):
                        try:
                            self.query_one(ResourceMonitor).update_stats(cpu, mem_p, mem_mb)
                        except Exception:
                            pass
                    case ScriptOutput(line=line):
                        record.add_line(line)
                        self._update_output_if_viewing(tid, record)
                    case ScriptCompleted(output=out, duration=duration, cpu_peak=cpu_p, mem_peak=mem_p):
                        record.add_line(f"\n-- {name} 完成 ({duration:.1f}s) --")
                        record.add_line(f"  资源峰值: CPU {cpu_p:.1f}% | MEM {mem_p:.1f}MB")
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
                    case PromptRequired(tid=e_tid, step_id=step_id, message=message, choices=choices):
                        record.pending_interaction = {
                            "type": "prompt",
                            "step_id": step_id,
                            "message": message,
                            "choices": choices
                        }
                        if self._current_view_tid == tid:
                            try:
                                self.query_one(InteractionPanel).show_prompt(tid, step_id, message, choices)
                            except Exception:
                                pass
                        record.add_line(f"\n[?] 等待输入: {message}")
                        self._update_output_if_viewing(tid, record)
                    case ConfirmRequired(tid=e_tid, step_id=step_id, message=message):
                        record.pending_interaction = {
                            "type": "confirm",
                            "step_id": step_id,
                            "message": message
                        }
                        if self._current_view_tid == tid:
                            try:
                                self.query_one(InteractionPanel).show_confirm(tid, step_id, message)
                            except Exception:
                                pass
                        record.add_line(f"\n[!] 等待确认: {message}")
                        self._update_output_if_viewing(tid, record)
                    case PipelineCompleted():
                        try:
                            self.query_one(ResourceMonitor).add_class("hidden")
                        except Exception:
                            pass
                        record.add_line(f"\n-- {name} 流水线完成 --")
                        record.status = "completed"
                        self._update_history_item(record)
                        self._update_output_if_viewing(tid, record)
                        self.core.cleanup_engine(tid)
                        break
                    case ExecutionEnded():
                        try:
                            self.query_one(ResourceMonitor).add_class("hidden")
                        except Exception:
                            pass
                        if record.status == "running":
                            record.status = "completed"
                            self._update_history_item(record)
                        self.core.cleanup_engine(tid)
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
