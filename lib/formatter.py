# lib/formatter.py
"""输出行智能格式化 — 日志着色、JSON 高亮、搜索高亮"""
from __future__ import annotations

import json
import re

from rich.text import Text

# ── 正则模式 ──────────────────────────────────────────────

# Android logcat: E/Tag: message
_ANDROID_LOG = re.compile(r'^([VDIWEF])/(.+?):\s(.*)$')

# Python/general: ERROR: msg
_PYTHON_LOG = re.compile(
    r'^(ERROR|CRITICAL|WARNING|WARN|INFO|DEBUG)\s*[:：]\s*(.*)$',
    re.IGNORECASE,
)

# Timestamp: 2024-01-01 12:00:00[.123]
_TIMESTAMP = re.compile(r'(\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2}(?:\.\d+)?)')

# JSON brackets
_JSON_START = re.compile(r'^\s*[\{\[]')
_JSON_END = re.compile(r'[\}\]]\s*$')

# Stack traces
_JAVA_TRACE = re.compile(r'^\s+at\s+')
_PYTHON_TRACE = re.compile(r'^\s+File\s+"')

# ── 样式映射 ──────────────────────────────────────────────

_LEVEL_STYLES: dict[str, str] = {
    'V': 'dim',
    'D': 'cyan',
    'I': 'green',
    'W': 'yellow',
    'E': 'bold red',
    'F': 'bold white on red',
    'ERROR': 'bold red',
    'CRITICAL': 'bold white on red',
    'WARNING': 'yellow',
    'WARN': 'yellow',
    'INFO': 'green',
    'DEBUG': 'cyan',
}

# ── Public API ────────────────────────────────────────────


def format_line(line: str, highlight: str | None = None) -> Text:
    """格式化单行输出。返回带样式的 Rich Text 对象。

    Args:
        line: 原始文本行。
        highlight: 搜索关键词（不区分大小写），匹配部分黄色高亮。
    """
    text = _format_content(line)
    if highlight:
        text = _apply_highlight(text, highlight)
    return text


# ── 内部实现 ──────────────────────────────────────────────


def _format_content(line: str) -> Text:
    # Android log
    m = _ANDROID_LOG.match(line)
    if m:
        level, tag, msg = m.groups()
        style = _LEVEL_STYLES.get(level, '')
        t = Text()
        t.append(f"{level}/{tag}: ", style=style)
        t.append(msg)
        return t

    # Python/general log
    m = _PYTHON_LOG.match(line)
    if m:
        level, msg = m.groups()
        style = _LEVEL_STYLES.get(level.upper(), '')
        t = Text()
        t.append(f"{level}: ", style=style)
        t.append(msg)
        return t

    # Stack traces (dim italic) - check before JSON since stack traces may have brackets
    if _JAVA_TRACE.match(line) or _PYTHON_TRACE.match(line):
        t = Text(line)
        t.stylize("dim italic")
        return t

    # JSON (try pretty-print)
    stripped = line.strip()
    if _JSON_START.match(stripped) and _JSON_END.search(stripped):
        try:
            parsed = json.loads(stripped)
            formatted = json.dumps(parsed, indent=2, ensure_ascii=False)
            return Text(formatted, style="cyan")
        except (json.JSONDecodeError, ValueError):
            pass

    # Timestamps within line
    if _TIMESTAMP.search(line):
        t = Text(line)
        for m in _TIMESTAMP.finditer(line):
            t.stylize("green", m.start(1), m.end(1))
        return t

    return Text(line)


def _apply_highlight(text: Text, keyword: str) -> Text:
    """对 Text 对象中所有匹配关键词的区间应用黄色背景高亮。"""
    plain = text.plain.lower()
    kw = keyword.lower()
    start = 0
    while True:
        idx = plain.find(kw, start)
        if idx == -1:
            break
        text.stylize("bold black on yellow", idx, idx + len(keyword))
        start = idx + len(keyword)
    return text
