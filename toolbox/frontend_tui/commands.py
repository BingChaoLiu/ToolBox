"""Command Palette providers — scripts, pipelines, and history search."""
from __future__ import annotations

from textual.command import Provider, Hit, Hits


class ScriptCommandProvider(Provider):
    """Search scripts and execute."""

    async def search(self, query: str) -> Hits:
        """Search scripts by name and description."""
        app = self.app
        from toolbox.frontend_tui.app import ToolBoxTUI
        if not isinstance(app, ToolBoxTUI):
            return

        matcher = self.matcher(query)
        for script in app.core.list_scripts():
            score = matcher.match(script.name)
            if score > 0:
                yield Hit(
                    score,
                    matcher.highlight(script.name),
                    lambda s=script: app._on_menu_select("script", s.name),
                    text=script.description or script.name,
                    help=script.description or "Run script",
                )
            elif query.lower() in (script.description or "").lower():
                # Secondary match on description
                yield Hit(
                    0.5,
                    script.name,
                    lambda s=script: app._on_menu_select("script", s.name),
                    text=script.description or script.name,
                    help=script.description or "Run script",
                )


class PipelineCommandProvider(Provider):
    """Search pipelines and execute."""

    async def search(self, query: str) -> Hits:
        """Search pipelines by name and description."""
        app = self.app
        from toolbox.frontend_tui.app import ToolBoxTUI
        if not isinstance(app, ToolBoxTUI):
            return

        matcher = self.matcher(query)
        for pipeline in app.core.list_pipelines():
            score = matcher.match(pipeline.name)
            if score > 0:
                yield Hit(
                    score,
                    matcher.highlight(pipeline.name),
                    lambda p=pipeline: app._on_menu_select("pipeline", p.name),
                    text=pipeline.description or pipeline.name,
                    help=pipeline.description or "Run pipeline",
                )
            elif query.lower() in (pipeline.description or "").lower():
                # Secondary match on description
                yield Hit(
                    0.5,
                    pipeline.name,
                    lambda p=pipeline: app._on_menu_select("pipeline", p.name),
                    text=pipeline.description or pipeline.name,
                    help=pipeline.description or "Run pipeline",
                )


class HistoryCommandProvider(Provider):
    """Search execution history."""

    async def search(self, query: str) -> Hits:
        """Search history by task name."""
        app = self.app
        from toolbox.frontend_tui.app import ToolBoxTUI
        if not isinstance(app, ToolBoxTUI):
            return

        matcher = self.matcher(query)
        records = sorted(
            app._records.values(),
            key=lambda r: r.timestamp,
            reverse=True,
        )
        for record in records:
            score = matcher.match(record.name)
            if score > 0:
                status_icon = {
                    "running": "🔄",
                    "completed": "✅",
                    "failed": "❌",
                    "cancelled": "⏹️",
                }.get(record.status, "•")
                time_str = record.timestamp.strftime("%H:%M:%S")
                yield Hit(
                    score,
                    matcher.highlight(record.name),
                    lambda tid=record.tid: app._select_record(tid),
                    text=f"{status_icon} {record.name}",
                    help=f"{record.status} — {time_str}",
                )
