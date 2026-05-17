# toolbox/frontend_tui/themes.py
"""主题定义 — 使用 Textual 原生 Theme API 注册预设主题。"""
from __future__ import annotations

from textual.theme import Theme

# ── 主题定义 ──────────────────────────────────────────────
# Textual Theme 构造函数:
#   Theme(name, primary, secondary=None, warning=None, error=None,
#         success=None, accent=None, foreground=None, background=None,
#         surface=None, panel=None, dark=True, variables={})

TOOLBOX_THEMES: dict[str, Theme] = {
    "toolbox-light": Theme(
        name="toolbox-light",
        primary="#1565c0",
        secondary="#00897b",
        warning="#e65100",
        error="#c62828",
        success="#2e7d32",
        foreground="#1a1a1a",
        background="#f5f5f5",
        surface="#ffffff",
        panel="#eeeeee",
        dark=False,
    ),
    "toolbox-high-contrast": Theme(
        name="toolbox-high-contrast",
        primary="#4fc3f7",
        secondary="#69f0ae",
        warning="#ffab00",
        error="#ff1744",
        success="#76ff03",
        foreground="#ffffff",
        background="#000000",
        surface="#0a0a0a",
        panel="#141414",
        dark=True,
    ),
}

DEFAULT_THEME = "textual-dark"

AVAILABLE_THEMES = ["textual-dark", "toolbox-light", "toolbox-high-contrast"]

THEME_DISPLAY_NAMES: dict[str, str] = {
    "textual-dark": "暗色",
    "toolbox-light": "亮色",
    "toolbox-high-contrast": "高对比度",
}


def get_theme_names() -> list[str]:
    """Return list of available theme names."""
    return AVAILABLE_THEMES


def get_theme_display_name(theme_name: str) -> str:
    """Return user-friendly display name for a theme."""
    return THEME_DISPLAY_NAMES.get(theme_name, theme_name)
