# toolbox/frontend_tui/themes.py
"""主题定义 — 预设颜色方案。"""
from __future__ import annotations

# 每个主题是一组 Textual CSS 变量覆盖
THEMES: dict[str, dict[str, str]] = {
    "dark": {
        # 默认暗色 (Textual 默认，留空表示不覆盖)
    },
    "light": {
        "background": "#f5f5f5",
        "surface": "#ffffff",
        "surface-darken-1": "#eeeeee",
        "surface-darken-2": "#e0e0e0",
        "surface-darken-3": "#d0d0d0",
        "surface-lighten-1": "#fafafa",
        "primary": "#1565c0",
        "primary-darken-1": "#0d47a1",
        "primary-darken-2": "#0a3880",
        "primary-darken-3": "#082e66",
        "secondary": "#00897b",
        "text": "#1a1a1a",
        "text-muted": "#666666",
        "success": "#2e7d32",
        "warning": "#e65100",
        "error": "#c62828",
    },
    "high-contrast": {
        "background": "#000000",
        "surface": "#0a0a0a",
        "surface-darken-1": "#141414",
        "surface-darken-2": "#1e1e1e",
        "surface-darken-3": "#282828",
        "surface-lighten-1": "#050505",
        "primary": "#4fc3f7",
        "primary-darken-1": "#29b6f6",
        "primary-darken-2": "#039be5",
        "primary-darken-3": "#0277bd",
        "secondary": "#69f0ae",
        "text": "#ffffff",
        "text-muted": "#b0b0b0",
        "success": "#76ff03",
        "warning": "#ffab00",
        "error": "#ff1744",
    },
}

DEFAULT_THEME = "dark"

AVAILABLE_THEMES = list(THEMES.keys())


def get_theme_css(theme_name: str) -> str:
    """Generate CSS that overrides Textual variables for the given theme.

    Returns a CSS rule that sets Textual CSS variables ($surface, $primary, etc.)
    on the Screen element.
    """
    theme = THEMES.get(theme_name, {})
    if not theme:
        return ""
    lines = []
    lines.append("Screen {")
    for var, value in theme.items():
        lines.append(f"    ${var}: {value};")
    lines.append("}")
    return "\n".join(lines)


def get_theme_names() -> list[str]:
    """Return list of available theme names."""
    return AVAILABLE_THEMES
