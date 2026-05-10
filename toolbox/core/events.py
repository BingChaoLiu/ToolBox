from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class Event:
    pass


@dataclass
class ScriptStarted(Event):
    script_name: str
    step_info: str | None = None


@dataclass
class ScriptOutput(Event):
    script_name: str
    line: str


@dataclass
class ResourceUpdate(Event):
    cpu_percent: float
    memory_percent: float
    memory_mb: float


@dataclass
class ScriptCompleted(Event):
    script_name: str
    output: dict | None = None
    duration: float = 0.0
    cpu_peak: float = 0.0
    mem_peak: float = 0.0


@dataclass
class ScriptFailed(Event):
    script_name: str
    error: str = ""
    traceback: str = ""


@dataclass
class PromptRequired(Event):
    tid: int
    step_id: str
    message: str = ""
    choices: list[str] | None = None


@dataclass
class ConfirmRequired(Event):
    tid: int
    step_id: str
    message: str = ""


@dataclass
class PipelineCompleted(Event):
    pipeline_name: str
    outputs: list[dict] | None = None


@dataclass
class ExecutionEnded(Event):
    pass


@dataclass
class ParamDef:
    name: str
    label: str
    type: str = "text"
    default: Any = None
    multiline: bool = False
    clipboard: bool = False
    options: list | None = None
    options_from: dict | None = None


@dataclass
class ScriptMeta:
    name: str
    description: str
    category: str
    params: list[ParamDef]
    outputs: list[str]
    has_manifest: bool
    script_path: Path
    timeout: int | None = None


@dataclass
class PipelineMeta:
    name: str
    description: str
    steps: list[dict]
    file_path: Path
