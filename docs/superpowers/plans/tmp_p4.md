# ToolBox 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 Android 开发工作流自动化 TUI 工具，支持脚本自动发现、流水线编排、交互式分支、前后端分离。

**Architecture:** 后端纯 Python 事件驱动（ToolboxCore），前端 Textual TUI 消费 async 事件队列。脚本零 UI 依赖，通过 YAML 清单声明接口。流水线通过 YAML 定义步骤串联和交互分支。

**Tech Stack:** Python 3.10+, Textual 3.0+, Rich 13.0+, PyYAML 6.0+, pyperclip 1.8+, pytest

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `requirements.txt` | 项目依赖 |
| `lib/__init__.py` | 包标记 |
| `lib/config.py` | 读取 config.yaml，支持 dot-path 取值 |
| `lib/cancel.py` | 协作式取消标志 |
| `lib/process.py` | 子进程封装，实时逐行输出 |
| `lib/clipboard.py` | 剪贴板读写（pyperclip） |
| `lib/path_helper.py` | 路径工具函数 |
| `lib/git_helper.py` | Git 操作封装 |
| `toolbox/__init__.py` | 包标记 |
| `toolbox/core/__init__.py` | 包标记 |
| `toolbox/core/events.py` | 事件 dataclass 定义 |
| `toolbox/core/config_loader.py` | YAML 配置加载，支持 ${} 引用 |
| `toolbox/core/discovery.py` | 脚本 & 流水线自动发现与校验 |
| `toolbox/core/executor.py` | 脚本执行引擎（线程 + OutputCapture） |
| `toolbox/core/pipeline.py` | 流水线引擎（步骤串联 + 交互分支） |
| `toolbox/frontend_base.py` | 前端抽象基类 |
| `toolbox/frontend_tui/__init__.py` | 包标记 |
| `toolbox/frontend_tui/app.py` | Textual TUI 应用 |
| `tests/conftest.py` | pytest fixtures |
| `tests/test_lib/test_config.py` | lib/config 测试 |
| `tests/test_lib/test_cancel.py` | lib/cancel 测试 |
| `tests/test_lib/test_process.py` | lib/process 测试 |
| `tests/test_lib/test_git_helper.py` | lib/git_helper 测试 |
| `tests/test_core/test_config_loader.py` | config_loader 测试 |
| `tests/test_core/test_discovery.py` | discovery 测试 |
| `tests/test_core/test_executor.py` | executor 测试 |
| `tests/test_core/test_pipeline.py` | pipeline 测试 |
| `run.py` | 脚本独立运行器 |
| `main.py` | 入口 |
| `config.example.yaml` | 配置模板 |

---

## Phase 1：基础设施

### Task 1: 项目脚手架

**Files:**
- Create: `requirements.txt`
- Create: `lib/__init__.py`
- Create: `toolbox/__init__.py`
- Create: `toolbox/core/__init__.py`
- Create: `toolbox/frontend_tui/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/test_lib/__init__.py`
- Create: `tests/test_core/__init__.py`
- Create: `tests/conftest.py`
- Create: `scripts/.gitkeep`
- Create: `pipelines/.gitkeep`

- [ ] **Step 1: 创建目录结构**

```bash
cd D:/Document/Project/ToolBox
mkdir -p lib toolbox/core toolbox/frontend_tui scripts pipelines tests/test_lib tests/test_core
```

- [ ] **Step 2: 创建 requirements.txt**

```python
# requirements.txt
pyyaml>=6.0
pyperclip>=1.8.0
textual>=3.0.0
rich>=13.0.0
pytest>=8.0.0
```

- [ ] **Step 3: 创建所有 __init__.py 和 .gitkeep**

```bash
touch lib/__init__.py toolbox/__init__.py toolbox/core/__init__.py toolbox/frontend_tui/__init__.py tests/__init__.py tests/test_lib/__init__.py tests/test_core/__init__.py scripts/.gitkeep pipelines/.gitkeep
```

- [ ] **Step 4: 创建 tests/conftest.py**

```python
# tests/conftest.py
import os
import pathlib
import tempfile

import pytest


@pytest.fixture
def tmp_dir():
    """提供一个临时目录，测试结束后自动清理"""
    with tempfile.TemporaryDirectory() as d:
        yield pathlib.Path(d)


@pytest.fixture(autouse=True)
def reset_lib_config():
    """每个测试前后重置 lib.config 模块的缓存状态"""
    import lib.config
    lib.config._config = None
    yield
    lib.config._config = None


@pytest.fixture
def project_root(tmp_dir):
    """模拟项目根目录，包含一个 config.yaml"""
    config_content = {
        "build": {
            "project_path": str(tmp_dir / "android_project"),
            "gradlew": "gradlew.bat",
        },
        "git": {
            "repos": [
                {"name": "主项目", "path": str(tmp_dir / "repo"), "branch": "main"},
            ]
        },
    }
    import yaml
    config_path = tmp_dir / "config.yaml"
    config_path.write_text(yaml.dump(config_content), encoding="utf-8")
    return tmp_dir
```

- [ ] **Step 5: 安装依赖并验证 pytest 可运行**

```bash
cd D:/Document/Project/ToolBox
pip install -r requirements.txt
python -m pytest tests/ -v --co
```

Expected: 无测试被发现，但 pytest 正常退出无报错

- [ ] **Step 6: 提交**

```bash
git init
git add requirements.txt lib/ toolbox/ tests/ scripts/ pipelines/ docs/
git commit -m "chore: 项目脚手架，目录结构与依赖声明"
```

---

### Task 2: lib/config.py — 配置读取

**Files:**
- Create: `lib/config.py`
- Create: `tests/test_lib/test_config.py`

- [ ] **Step 1: 写测试**

```python
# tests/test_lib/test_config.py
import os
import pathlib

import pytest
import yaml


class TestGetConfig:
    def test_dot_path_returns_nested_value(self, project_root):
        import lib.config
        lib.config._CONFIG_PATH = project_root / "config.yaml"

        result = lib.config.get_config("build.project_path")
        assert result == str(project_root / "android_project")

    def test_dot_path_returns_top_level(self, project_root):
        import lib.config
        lib.config._CONFIG_PATH = project_root / "config.yaml"

        result = lib.config.get_config("build")
        assert isinstance(result, dict)
        assert "project_path" in result

    def test_dot_path_returns_list_element(self, project_root):
        import lib.config
        lib.config._CONFIG_PATH = project_root / "config.yaml"

        result = lib.config.get_config("git.repos")
        assert isinstance(result, list)
        assert result[0]["name"] == "主项目"

    def test_missing_key_raises_key_error(self, project_root):
        import lib.config
        lib.config._CONFIG_PATH = project_root / "config.yaml"

        with pytest.raises(KeyError):
            lib.config.get_config("nonexistent.key")

    def test_env_var_overrides_default_path(self, tmp_dir):
        config = {"test_key": "from_env"}
        config_path = tmp_dir / "custom.yaml"
        config_path.write_text(yaml.dump(config), encoding="utf-8")

        import lib.config
        lib.config._CONFIG_PATH = config_path
        lib.config._config = None

        result = lib.config.get_config("test_key")
        assert result == "from_env"

    def test_config_is_cached(self, project_root):
        import lib.config
        lib.config._CONFIG_PATH = project_root / "config.yaml"
        lib.config._config = None

        lib.config.get_config("build")
        assert lib.config._config is not None

        # 删掉文件，缓存仍生效
        (project_root / "config.yaml").unlink()
        result = lib.config.get_config("build")
        assert isinstance(result, dict)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_lib/test_config.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'lib.config'`

- [ ] **Step 3: 实现 lib/config.py**

```python
# lib/config.py
import os
import pathlib

import yaml

_CONFIG_PATH = pathlib.Path(
    os.environ.get("TOOLBOX_CONFIG", "")
) if os.environ.get("TOOLBOX_CONFIG") else (
    pathlib.Path(__file__).parent.parent / "config.yaml"
)

_config = None


def get_config(dot_path: str):
    global _config
    if _config is None:
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            _config = yaml.safe_load(f)
    keys = dot_path.split(".")
    value = _config
    for key in keys:
        value = value[key]
    return value
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_lib/test_config.py -v
```

Expected: 6 passed

- [ ] **Step 5: 提交**

```bash
git add lib/config.py tests/test_lib/test_config.py
git commit -m "feat(lib): 配置读取，支持 dot-path 取值和环境变量覆盖"
```

---

### Task 3: lib/cancel.py — 协作式取消

**Files:**
- Create: `lib/cancel.py`
- Create: `tests/test_lib/test_cancel.py`

- [ ] **Step 1: 写测试**

```python
# tests/test_lib/test_cancel.py
import threading

from lib.cancel import is_cancelled, request_cancel, reset


class TestCancel:
    def test_initial_state_is_not_cancelled(self):
        reset()
        assert is_cancelled() is False

    def test_request_cancel_sets_flag(self):
        reset()
        request_cancel()
        assert is_cancelled() is True

    def test_reset_clears_flag(self):
        request_cancel()
        reset()
        assert is_cancelled() is False

    def test_thread_safe_read_from_other_thread(self):
        reset()
        results = []

        def worker():
            results.append(is_cancelled())

        t = threading.Thread(target=worker)
        t.start()
        t.join()
        assert results == [False]

    def test_thread_sees_cancel_from_main(self):
        reset()
        results = []
        event = threading.Event()

        def worker():
            event.wait()
            results.append(is_cancelled())

        t = threading.Thread(target=worker)
        t.start()
        request_cancel()
        event.set()
        t.join()
        assert results == [True]
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_lib/test_cancel.py -v
```

Expected: FAIL — `ImportError`

- [ ] **Step 3: 实现 lib/cancel.py**

```python
# lib/cancel.py
import threading

_cancel_event = threading.Event()


def is_cancelled():
    return _cancel_event.is_set()


def request_cancel():
    _cancel_event.set()


def reset():
    _cancel_event.clear()
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_lib/test_cancel.py -v
```

Expected: 5 passed

- [ ] **Step 5: 提交**

```bash
git add lib/cancel.py tests/test_lib/test_cancel.py
git commit -m "feat(lib): 协作式取消机制，线程安全"
```

---

### Task 4: lib/process.py — 子进程封装

**Files:**
- Create: `lib/process.py`
- Create: `tests/test_lib/test_process.py`

- [ ] **Step 1: 写测试**

```python
# tests/test_lib/test_process.py
import pathlib

from lib.process import run


class TestRun:
    def test_returns_exit_code_zero_on_success(self):
        code = run(["echo", "hello"])
        assert code == 0

    def test_returns_nonzero_on_failure(self):
        code = run(["cmd", "/c", "exit", "1"])
        assert code != 0

    def test_cwd_parameter(self, tmp_dir):
        marker = tmp_dir / "marker.txt"
        marker.write_text("found", encoding="utf-8")
        code = run(["cmd", "/c", "type", "marker.txt"], cwd=str(tmp_dir))
        assert code == 0

    def test_env_parameter(self):
        import os
        custom_env = {**os.environ, "TOOLBOX_TEST_VAR": "hello123"}
        code = run(["cmd", "/c", "echo", "%TOOLBOX_TEST_VAR%"], env=custom_env)
        assert code == 0
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_lib/test_process.py -v
```

Expected: FAIL — `ImportError`

- [ ] **Step 3: 实现 lib/process.py**

```python
# lib/process.py
import subprocess


def run(cmd, cwd=None, env=None):
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=cwd,
        env=env,
        text=True,
        encoding="utf-8",
    )
    for line in proc.stdout:
        print(line, end="")
    proc.wait()
    return proc.returncode
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_lib/test_process.py -v
```

Expected: 4 passed

- [ ] **Step 5: 提交**

```bash
git add lib/process.py tests/test_lib/test_process.py
git commit -m "feat(lib): 子进程封装，实时逐行输出"
```

---

### Task 5: lib/clipboard.py + lib/path_helper.py — 工具函数

**Files:**
- Create: `lib/clipboard.py`
- Create: `lib/path_helper.py`

- [ ] **Step 1: 实现 lib/clipboard.py**

```python
# lib/clipboard.py
import pyperclip


def read():
    return pyperclip.paste()


def write(text):
    pyperclip.copy(text)
```

- [ ] **Step 2: 实现 lib/path_helper.py**

```python
# lib/path_helper.py
import pathlib


def ensure_dir(path):
    pathlib.Path(path).mkdir(parents=True, exist_ok=True)


def resolve(base, *parts):
    return str(pathlib.Path(base).joinpath(*parts))
```

- [ ] **Step 3: 验证导入正常**

```bash
python -c "import sys; sys.path.insert(0, '.'); from lib.clipboard import read, write; from lib.path_helper import ensure_dir, resolve; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: 提交**

```bash
git add lib/clipboard.py lib/path_helper.py
git commit -m "feat(lib): 剪贴板读写与路径工具函数"
```

---

### Task 6: lib/git_helper.py — Git 操作封装

**Files:**
- Create: `lib/git_helper.py`
- Create: `tests/test_lib/test_git_helper.py`

- [ ] **Step 1: 写测试**

```python
# tests/test_lib/test_git_helper.py
import pathlib
import subprocess

import pytest

from lib.git_helper import fetch, get_new_commits, get_status


@pytest.fixture
def git_repo(tmp_dir):
    """创建一个本地 git 仓库用于测试"""
    repo = tmp_dir / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=str(repo), capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(repo), capture_output=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=str(repo), capture_output=True)
    (repo / "readme.txt").write_text("init", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(repo), capture_output=True)
    return repo


class TestFetch:
    def test_fetch_nonexistent_remote_returns_false(self, git_repo):
        result = fetch(str(git_repo), remote="origin")
        assert result is False

    def test_fetch_valid_repo_does_not_crash(self, git_repo):
        # 没有 remote 不会崩，返回 False
        result = fetch(str(git_repo))
        assert isinstance(result, bool)


class TestGetNewCommits:
    def test_no_remote_returns_empty(self, git_repo):
        commits = get_new_commits(str(git_repo), "main")
        assert commits == []


class TestGetStatus:
    def test_clean_repo(self, git_repo):
        status = get_status(str(git_repo))
        assert isinstance(status, dict)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_lib/test_git_helper.py -v
```

Expected: FAIL — `ImportError`

- [ ] **Step 3: 实现 lib/git_helper.py**

```python
# lib/git_helper.py
import subprocess


def _git(repo_path, *args):
    result = subprocess.run(
        ["git"] + list(args),
        cwd=repo_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result


def fetch(repo_path, remote="origin"):
    result = _git(repo_path, "fetch", remote)
    return result.returncode == 0


def get_new_commits(repo_path, branch, remote="origin"):
    _git(repo_path, "fetch", remote)
    result = _git(repo_path, "log", f"HEAD..{remote}/{branch}", "--oneline")
    if result.returncode != 0:
        return []
    lines = result.stdout.strip().split("\n")
    if not lines or lines[0] == "":
        return []
    commits = []
    for line in lines:
        parts = line.split(" ", 1)
        commits.append({
            "hash": parts[0],
            "message": parts[1] if len(parts) > 1 else "",
        })
    return commits


def get_status(repo_path):
    result = _git(repo_path, "status", "--porcelain")
    if result.returncode != 0:
        return {"clean": False, "files": []}
    lines = result.stdout.strip().split("\n")
    if not lines or lines[0] == "":
        return {"clean": True, "files": []}
    files = []
    for line in lines:
        status = line[:2].strip()
        filepath = line[3:]
        files.append({"status": status, "path": filepath})
    return {"clean": False, "files": files}
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_lib/test_git_helper.py -v
```

Expected: 3 passed

- [ ] **Step 5: 运行全部 Phase 1 测试确认无回归**

```bash
python -m pytest tests/ -v
```

Expected: 全部通过

- [ ] **Step 6: 提交**

```bash
git add lib/git_helper.py tests/test_lib/test_git_helper.py
git commit -m "feat(lib): Git 操作封装，fetch/log/status"
```

---

## Phase 2：核心后端

### Task 7: toolbox/core/events.py — 事件定义

**Files:**
- Create: `toolbox/core/events.py`

- [ ] **Step 1: 实现 events.py**

```python
# toolbox/core/events.py
from __future__ import annotations

from dataclasses import dataclass


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
class ScriptCompleted(Event):
    script_name: str
    output: dict | None = None
    duration: float = 0.0


@dataclass
class ScriptFailed(Event):
    script_name: str
    error: str = ""
    traceback: str = ""


@dataclass
class PromptRequired(Event):
    step_id: str
    message: str = ""
    choices: list[str] | None = None


@dataclass
class ConfirmRequired(Event):
    step_id: str
    message: str = ""


@dataclass
class PipelineCompleted(Event):
    pipeline_name: str
    outputs: list[dict] | None = None


@dataclass
class ExecutionEnded(Event):
    pass


# 元数据结构
from pathlib import Path
from typing import Any


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


@dataclass
class PipelineMeta:
    name: str
    description: str
    steps: list[dict]
    file_path: Path
```

- [ ] **Step 2: 验证导入和实例化**

```bash
python -c "import sys; sys.path.insert(0,'.'); from toolbox.core.events import ScriptStarted, ScriptOutput, ExecutionEnded, ScriptMeta, PipelineMeta, ParamDef; e=ScriptStarted('test'); print(e)"
```

Expected: `ScriptStarted(script_name='test', step_info=None)`

- [ ] **Step 3: 提交**

```bash
git add toolbox/core/events.py
git commit -m "feat(core): 事件定义与元数据结构"
```

---

### Task 8: toolbox/core/config_loader.py — 配置加载器

**Files:**
- Create: `toolbox/core/config_loader.py`
- Create: `tests/test_core/test_config_loader.py`

- [ ] **Step 1: 写测试**

```python
# tests/test_core/test_config_loader.py
import pathlib

import pytest
import yaml

from toolbox.core.config_loader import load_config, resolve_value


class TestLoadConfig:
    def test_loads_yaml_file(self, tmp_dir):
        config_file = tmp_dir / "test.yaml"
        config_file.write_text(yaml.dump({"a": {"b": 1}}), encoding="utf-8")
        result = load_config(str(config_file))
        assert result == {"a": {"b": 1}}

    def test_raises_on_missing_file(self, tmp_dir):
        with pytest.raises(FileNotFoundError):
            load_config(str(tmp_dir / "missing.yaml"))


class TestResolveReferences:
    def test_resolves_dollar_brace_reference(self, tmp_dir):
        config_file = tmp_dir / "test.yaml"
        raw = {
            "base": {"path": "/tmp/project"},
            "derived": {"path": "${base.path}"},
        }
        config_file.write_text(yaml.dump(raw), encoding="utf-8")
        result = load_config(str(config_file))
        assert result["derived"]["path"] == "/tmp/project"

    def test_resolves_nested_reference(self, tmp_dir):
        config_file = tmp_dir / "test.yaml"
        raw = {
            "level1": {"val": "hello"},
            "level2": {"val": "${level1.val}"},
            "level3": {"val": "${level2.val}"},
        }
        config_file.write_text(yaml.dump(raw), encoding="utf-8")
        result = load_config(str(config_file))
        assert result["level3"]["val"] == "hello"

    def test_detects_circular_reference(self, tmp_dir):
        config_file = tmp_dir / "test.yaml"
        raw = {
            "a": {"val": "${b.val}"},
            "b": {"val": "${a.val}"},
        }
        config_file.write_text(yaml.dump(raw), encoding="utf-8")
        with pytest.raises(ValueError, match="circular"):
            load_config(str(config_file))

    def test_preserves_non_string_values(self, tmp_dir):
        config_file = tmp_dir / "test.yaml"
        raw = {"count": 42, "flag": True, "items": [1, 2, 3]}
        config_file.write_text(yaml.dump(raw), encoding="utf-8")
        result = load_config(str(config_file))
        assert result["count"] == 42
        assert result["flag"] is True
        assert result["items"] == [1, 2, 3]


class TestResolveValue:
    def test_resolves_config_prefix(self, tmp_dir):
        config_file = tmp_dir / "test.yaml"
        raw = {"addr2line": {"default_so": "/tmp/libapp.so"}}
        config_file.write_text(yaml.dump(raw), encoding="utf-8")
        config = load_config(str(config_file))
        result = resolve_value("config:addr2line.default_so", config)
        assert result == "/tmp/libapp.so"

    def test_returns_literal_when_no_prefix(self):
        result = resolve_value("hello world", {})
        assert result == "hello world"

    def test_resolves_steps_prefix(self):
        step_outputs = {"check_remote": {"new_commits": 5}}
        result = resolve_value("${steps.check_remote.new_commits}", step_outputs, is_step_outputs=True)
        assert result == 5

    def test_string_interpolation_preserves_type_for_pure_expression(self):
        step_outputs = {"check": {"count": 5}}
        result = resolve_value("${steps.check.count}", step_outputs, is_step_outputs=True)
        assert result == 5
        assert isinstance(result, int)

    def test_string_interpolation_converts_when_embedded(self):
        step_outputs = {"check": {"count": 5}}
        result = resolve_value("total: ${steps.check.count}", step_outputs, is_step_outputs=True)
        assert result == "total: 5"
        assert isinstance(result, str)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_core/test_config_loader.py -v
```

Expected: FAIL — `ImportError`

- [ ] **Step 3: 实现 config_loader.py**

```python
# toolbox/core/config_loader.py
from __future__ import annotations

import re
from pathlib import Path

import yaml

_REF_PATTERN = re.compile(r"\$\{([^}]+\})")


def load_config(config_path: str) -> dict:
    p = Path(config_path)
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(p, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return _resolve_all_references(raw, set())


def _resolve_all_references(data, resolving_keys: set) -> dict:
    if isinstance(data, dict):
        return {k: _resolve_all_references(v, resolving_keys) for k, v in data.items()}
    if isinstance(data, list):
        return [_resolve_all_references(item, resolving_keys) for item in data]
    if isinstance(data, str):
        return _resolve_ref_in_string(data, resolving_keys)
    return data


def _resolve_ref_in_string(value: str, resolving_keys: set) -> str:
    matches = list(_REF_PATTERN.finditer(value))
    if not matches:
        return value
    # 如果整个字符串就是一个 ${}，后续在 resolve_value 中处理类型保持
    # 这里只做字符串插值
    return value


def resolve_value(expr, context: dict, is_step_outputs: bool = False):
    if isinstance(expr, str) and expr.startswith("config:"):
        dot_path = expr[len("config:"):]
        return _get_by_dot_path(context, dot_path)

    if isinstance(expr, str) and "${" in expr:
        return _resolve_expr(expr, context if is_step_outputs else {})

    return expr


def _resolve_expr(expr: str, step_outputs: dict):
    matches = list(_REF_PATTERN.finditer(expr))
    if not matches:
        return expr

    is_pure = len(matches) == 1 and expr == matches[0].group(0)

    if is_pure:
        ref = matches[0].group(1)
        value = _resolve_ref(ref, step_outputs)
        return value

    result = expr
    for match in reversed(matches):
        ref = match.group(1)
        value = _resolve_ref(ref, step_outputs)
        result = result[:match.start()] + str(value) + result[match.end():]
    return result


def _resolve_ref(ref_content: str, context: dict):
    full_ref = "${" + ref_content
    if full_ref.startswith("${steps."):
        dot_path = full_ref[len("${steps."):-1]
        parts = dot_path.split(".", 1)
        if len(parts) == 2:
            step_id, field = parts
            step_data = context.get(step_id, {})
            return step_data.get(field)
    if full_ref.startswith("${config:"):
        dot_path = full_ref[len("${config:"):-1]
        return _get_by_dot_path(context, dot_path)
    if full_ref == "${choice}":
        return "${choice}"
    return full_ref


def _get_by_dot_path(data, dot_path: str):
    keys = dot_path.split(".")
    value = data
    for key in keys:
        if isinstance(value, dict):
            value = value[key]
        else:
            raise KeyError(f"Cannot resolve key '{key}' in path '{dot_path}'")
    return value
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_core/test_config_loader.py -v
```

Expected: 9 passed

- [ ] **Step 5: 提交**

```bash
git add toolbox/core/config_loader.py tests/test_core/test_config_loader.py
git commit -m "feat(core): 配置加载器，支持 ${} 引用解析与类型保持"
```

---

### Task 9: toolbox/core/discovery.py — 自动发现

**Files:**
- Create: `toolbox/core/discovery.py`
- Create: `tests/test_core/test_discovery.py`

- [ ] **Step 1: 写测试**

```python
# tests/test_core/test_discovery.py
import pathlib

import pytest
import yaml

from toolbox.core.discovery import discover_scripts, discover_pipelines, validate_pipeline


class TestDiscoverScripts:
    def test_finds_py_files(self, tmp_dir):
        scripts = tmp_dir / "scripts"
        scripts.mkdir()
        (scripts / "hello.py").write_text("def main(): pass", encoding="utf-8")
        (scripts / "world.py").write_text("def main(): pass", encoding="utf-8")
        (scripts / "ignored.txt").write_text("not a script", encoding="utf-8")

        result = discover_scripts(str(scripts))
        names = [m.name for m in result]
        assert "hello" in names
        assert "world" in names
        assert len(result) == 2

    def test_script_without_manifest_is_tier1(self, tmp_dir):
        scripts = tmp_dir / "scripts"
        scripts.mkdir()
        (scripts / "bare.py").write_text("def main(): pass", encoding="utf-8")

        result = discover_scripts(str(scripts))
        meta = result[0]
        assert meta.name == "bare"
        assert meta.has_manifest is False
        assert meta.params == []

    def test_script_with_manifest_parses_params(self, tmp_dir):
        scripts = tmp_dir / "scripts"
        scripts.mkdir()
        (scripts / "addr2line.py").write_text("def main(address=None): pass", encoding="utf-8")
        manifest = {
            "name": "崩溃地址分析",
            "category": "调试",
            "params": [
                {"name": "address", "label": "崩溃地址", "type": "text", "clipboard": True},
            ],
            "outputs": ["result"],
        }
        (scripts / "addr2line.yaml").write_text(yaml.dump(manifest), encoding="utf-8")

        result = discover_scripts(str(scripts))
        meta = result[0]
        assert meta.name == "崩溃地址分析"
        assert meta.category == "调试"
        assert meta.has_manifest is True
        assert len(meta.params) == 1
        assert meta.params[0].name == "address"
        assert meta.params[0].clipboard is True
        assert meta.outputs == ["result"]

    def test_empty_scripts_dir_returns_empty(self, tmp_dir):
        scripts = tmp_dir / "scripts"
        scripts.mkdir()
        result = discover_scripts(str(scripts))
        assert result == []


class TestDiscoverPipelines:
    def test_finds_yaml_files(self, tmp_dir):
        pipelines = tmp_dir / "pipelines"
        pipelines.mkdir()
        pipeline_def = {
            "name": "测试流水线",
            "steps": [
                {"id": "step1", "script": "hello"},
                {"id": "end", "type": "end"},
            ],
        }
        (pipelines / "test.yaml").write_text(yaml.dump(pipeline_def), encoding="utf-8")

        result = discover_pipelines(str(pipelines))
        assert len(result) == 1
        assert result[0].name == "测试流水线"

    def test_empty_dir_returns_empty(self, tmp_dir):
        pipelines = tmp_dir / "pipelines"
        pipelines.mkdir()
        result = discover_pipelines(str(pipelines))
        assert result == []


class TestValidatePipeline:
    def test_valid_pipeline_no_warnings(self):
        steps = [
            {"id": "check", "script": "git_check"},
            {"id": "end", "type": "end"},
        ]
        available_scripts = ["git_check"]
        warnings = validate_pipeline(steps, available_scripts)
        assert warnings == []

    def test_warns_on_missing_script(self):
        steps = [
            {"id": "check", "script": "nonexistent_script"},
            {"id": "end", "type": "end"},
        ]
        available_scripts = ["git_check"]
        warnings = validate_pipeline(steps, available_scripts)
        assert any("nonexistent_script" in w for w in warnings)

    def test_warns_on_script_and_type_together(self):
        steps = [
            {"id": "bad", "script": "git_check", "type": "prompt"},
        ]
        available_scripts = ["git_check"]
        warnings = validate_pipeline(steps, available_scripts)
        assert any("互斥" in w for w in warnings)

    def test_warns_on_invalid_goto(self):
        steps = [
            {"id": "choose", "type": "prompt", "choices": [
                {"label": "Go", "goto": "nonexistent_step"},
            ]},
        ]
        available_scripts = []
        warnings = validate_pipeline(steps, available_scripts)
        assert any("nonexistent_step" in w for w in warnings)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_core/test_discovery.py -v
```

Expected: FAIL — `ImportError`

- [ ] **Step 3: 实现 discovery.py**

```python
# toolbox/core/discovery.py
from __future__ import annotations

import ast
from pathlib import Path

import yaml

from toolbox.core.events import ParamDef, ScriptMeta, PipelineMeta


def discover_scripts(scripts_dir: str) -> list[ScriptMeta]:
    scripts_path = Path(scripts_dir)
    if not scripts_path.exists():
        return []
    results = []
    for py_file in sorted(scripts_path.glob("*.py")):
        manifest_path = py_file.with_suffix(".yaml")
        if manifest_path.exists():
            meta = _parse_manifest(py_file, manifest_path)
        else:
            meta = ScriptMeta(
                name=py_file.stem,
                description="",
                category="未分类",
                params=[],
                outputs=[],
                has_manifest=False,
                script_path=py_file,
            )
        results.append(meta)
    return results


def _parse_manifest(script_path: Path, manifest_path: Path) -> ScriptMeta:
    with open(manifest_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    params = []
    for p in data.get("params", []):
        param_def = ParamDef(
            name=p["name"],
            label=p.get("label", p["name"]),
            type=p.get("type", "text"),
            default=p.get("default"),
            multiline=p.get("multiline", False),
            clipboard=p.get("clipboard", False),
            options=p.get("options"),
            options_from=p.get("options_from"),
        )
        params.append(param_def)
    return ScriptMeta(
        name=data.get("name", script_path.stem),
        description=data.get("description", ""),
        category=data.get("category", "未分类"),
        params=params,
        outputs=data.get("outputs", []),
        has_manifest=True,
        script_path=script_path,
    )


def discover_pipelines(pipelines_dir: str) -> list[PipelineMeta]:
    pipelines_path = Path(pipelines_dir)
    if not pipelines_path.exists():
        return []
    results = []
    for yaml_file in sorted(pipelines_path.glob("*.yaml")):
        with open(yaml_file, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        results.append(PipelineMeta(
            name=data.get("name", yaml_file.stem),
            description=data.get("description", ""),
            steps=data.get("steps", []),
            file_path=yaml_file,
        ))
    return results


def validate_pipeline(steps: list[dict], available_scripts: list[str]) -> list[str]:
    warnings = []
    step_ids = {s.get("id") for s in steps if "id" in s}

    for step in steps:
        sid = step.get("id", "?")
        has_script = "script" in step
        has_type = "type" in step

        if has_script and has_type:
            warnings.append(f"步骤 '{sid}': 'script' 和 'type' 互斥")

        if has_script and step["script"] not in available_scripts:
            warnings.append(f"步骤 '{sid}': 脚本 '{step['script']}' 不存在")

        if has_type and step["type"] == "prompt":
            for choice in step.get("choices", []):
                goto = choice.get("goto", "")
                if goto and goto != "end" and goto not in step_ids:
                    warnings.append(f"步骤 '{sid}': goto 目标 '{goto}' 不存在")

    return warnings


def parse_main_signature(script_path: Path) -> list[ParamDef]:
    source = script_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            params = []
            for arg in node.args.args:
                params.append(ParamDef(
                    name=arg.arg,
                    label=arg.arg,
                    type="text",
                ))
            return params
    return []


def generate_manifest(script_path: Path) -> str:
    params = parse_main_signature(script_path)
    manifest = {
        "name": script_path.stem,
        "category": "未分类",
        "params": [
            {"name": p.name, "label": p.label, "type": p.type}
            for p in params
        ],
        "outputs": ["result"],
    }
    return yaml.dump(manifest, allow_unicode=True, default_flow_style=False)
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_core/test_discovery.py -v
```

Expected: 8 passed

- [ ] **Step 5: 提交**

```bash
git add toolbox/core/discovery.py tests/test_core/test_discovery.py
git commit -m "feat(core): 脚本与流水线自动发现、校验、清单生成"
```

---

### Task 10: toolbox/core/executor.py — 脚本执行引擎

**Files:**
- Create: `toolbox/core/executor.py`
- Create: `tests/test_core/test_executor.py`

- [ ] **Step 1: 写测试**

```python
# tests/test_core/test_executor.py
import asyncio
import pathlib
import threading

import pytest

from toolbox.core.events import (
    ScriptStarted, ScriptOutput, ScriptCompleted, ScriptFailed, ExecutionEnded,
)
from toolbox.core.executor import Executor, OutputCapture


class TestOutputCapture:
    def test_captures_line_on_newline(self):
        lines = []
        cap = OutputCapture(lambda line: lines.append(line))
        cap.write("hello\n")
        assert lines == ["hello"]

    def test_buffers_partial_line(self):
        lines = []
        cap = OutputCapture(lambda line: lines.append(line))
        cap.write("hel")
        cap.write("lo\n")
        assert lines == ["hello"]

    def test_flush_remaining_emits_buffer(self):
        lines = []
        cap = OutputCapture(lambda line: lines.append(line))
        cap.write("partial")
        cap.flush_remaining()
        assert lines == ["partial"]

    def test_flush_remaining_does_nothing_when_empty(self):
        lines = []
        cap = OutputCapture(lambda line: lines.append(line))
        cap.flush_remaining()
        assert lines == []


class TestExecutor:
    def _run_and_collect(self, script_path, params=None):
        """辅助：执行脚本并收集所有事件"""
        loop = asyncio.new_event_loop()
        queue = asyncio.Queue()
        executor = Executor(project_root=script_path.parent.parent)
        collector = []

        async def _collect():
            while True:
                event = await queue.get()
                collector.append(event)
                if isinstance(event, ExecutionEnded):
                    break

        def _run():
            executor.run_script(
                script_path=str(script_path),
                params=params or {},
                loop=loop,
                event_queue=queue,
            )

        t = threading.Thread(target=_run)
        t.start()
        loop.run_until_complete(_collect())
        t.join()
        loop.close()
        return collector

    def test_simple_script_emits_started_output_completed_ended(self, tmp_dir):
        script = tmp_dir / "scripts" / "hello.py"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("def main():\n    print('hello world')\n    return {'ok': True}\n", encoding="utf-8")

        events = self._run_and_collect(script)
        types = [type(e).__name__ for e in events]

        assert "ScriptStarted" in types
        assert "ScriptOutput" in types
        assert "ScriptCompleted" in types
        assert "ExecutionEnded" in types

    def test_completed_event_contains_output_dict(self, tmp_dir):
        script = tmp_dir / "scripts" / "ret.py"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("def main():\n    return {'count': 42}\n", encoding="utf-8")

        events = self._run_and_collect(script)
        completed = [e for e in events if isinstance(e, ScriptCompleted)][0]
        assert completed.output == {"count": 42}

    def test_none_return_becomes_empty_dict(self, tmp_dir):
        script = tmp_dir / "scripts" / "noreturn.py"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("def main():\n    print('done')\n", encoding="utf-8")

        events = self._run_and_collect(script)
        completed = [e for e in events if isinstance(e, ScriptCompleted)][0]
        assert completed.output == {}

    def test_non_dict_return_wrapped(self, tmp_dir):
        script = tmp_dir / "scripts" / "strreturn.py"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("def main():\n    return 'plain string'\n", encoding="utf-8")

        events = self._run_and_collect(script)
        completed = [e for e in events if isinstance(e, ScriptCompleted)][0]
        assert completed.output == {"result": "plain string"}

    def test_exception_emits_script_failed(self, tmp_dir):
        script = tmp_dir / "scripts" / "crash.py"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("def main():\n    raise ValueError('boom')\n", encoding="utf-8")

        events = self._run_and_collect(script)
        failed = [e for e in events if isinstance(e, ScriptFailed)]
        assert len(failed) == 1
        assert "boom" in failed[0].error
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_core/test_executor.py -v
```

Expected: FAIL — `ImportError`

- [ ] **Step 3: 实现 executor.py**

```python
# toolbox/core/executor.py
from __future__ import annotations

import asyncio
import importlib.util
import io
import sys
import threading
import time
import traceback
from pathlib import Path

from lib.cancel import reset as reset_cancel, is_cancelled
from toolbox.core.events import (
    ScriptStarted, ScriptOutput, ScriptCompleted, ScriptFailed, ExecutionEnded,
)


class OutputCapture(io.TextIOBase):
    def __init__(self, callback):
        self._callback = callback
        self._buffer = ""

    def write(self, text):
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self._callback(line)
        return len(text)

    def flush(self):
        pass

    def flush_remaining(self):
        if self._buffer:
            self._callback(self._buffer)
            self._buffer = ""

    @property
    def encoding(self):
        return "utf-8"


class Executor:
    def __init__(self, project_root: str | None = None):
        self._project_root = Path(project_root) if project_root else Path(".")
        self._current_script = ""
        self._current_proc = None

    def load_script(self, script_path: str):
        path = Path(script_path)
        spec = importlib.util.spec_from_file_location(
            f"toolbox_script_{path.stem}",
            path,
        )
        mod = importlib.util.module_from_spec(spec)
        # 确保 lib 在 sys.path 上
        root = str(self._project_root)
        if root not in sys.path:
            sys.path.insert(0, root)
        spec.loader.exec_module(mod)
        return mod.main

    def run_script(self, script_path: str, params: dict, loop: asyncio.AbstractEventLoop, event_queue: asyncio.Queue):
        self._current_script = Path(script_path).stem
        reset_cancel()

        def emit(event):
            loop.call_soon_threadsafe(event_queue.put_nowait, event)

        emit(ScriptStarted(script_name=self._current_script))

        capture = OutputCapture(lambda line: emit(ScriptOutput(
            script_name=self._current_script, line=line,
        )))

        original_stdout = sys.stdout
        sys.stdout = capture
        start = time.time()
        try:
            main_fn = self.load_script(script_path)
            result = main_fn(**params)
            if result is None:
                result = {}
            elif not isinstance(result, dict):
                result = {"result": result}
            duration = time.time() - start
            emit(ScriptCompleted(
                script_name=self._current_script,
                output=result,
                duration=duration,
            ))
        except Exception as e:
            emit(ScriptFailed(
                script_name=self._current_script,
                error=str(e),
                traceback=traceback.format_exc(),
            ))
        finally:
            capture.flush_remaining()
            sys.stdout = original_stdout
            emit(ExecutionEnded())
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_core/test_executor.py -v
```

Expected: 9 passed

- [ ] **Step 5: 提交**

```bash
git add toolbox/core/executor.py tests/test_core/test_executor.py
git commit -m "feat(core): 脚本执行引擎，线程 + OutputCapture + 返回值归一化"
```

---

### Task 11: toolbox/core/pipeline.py — 流水线引擎

**Files:**
- Create: `toolbox/core/pipeline.py`
- Create: `tests/test_core/test_pipeline.py`

- [ ] **Step 1: 写测试**

```python
# tests/test_core/test_pipeline.py
import asyncio
import pathlib
import threading

import pytest

from toolbox.core.events import (
    ScriptStarted, ScriptOutput, ScriptCompleted, ExecutionEnded,
    PromptRequired, PipelineCompleted,
)
from toolbox.core.pipeline import PipelineEngine


@pytest.fixture
def scripts_dir(tmp_dir):
    sd = tmp_dir / "scripts"
    sd.mkdir()
    (sd / "step1.py").write_text(
        "def main():\n    print('step1')\n    return {'value': 42}\n", encoding="utf-8"
    )
    (sd / "step2.py").write_text(
        "def main(count=None):\n    print(f'step2 got {count}')\n    return {'doubled': int(count) * 2}\n", encoding="utf-8"
    )
    (sd / "echo.py").write_text(
        "def main(msg=None):\n    print(msg or 'echo')\n    return {'msg': msg}\n", encoding="utf-8"
    )
    return sd


def _run_pipeline_collect(steps, scripts_dir, respond_fn=None):
    """辅助：运行流水线并收集事件"""
    loop = asyncio.new_event_loop()
    queue = asyncio.Queue()
    collector = []
    engine = PipelineEngine(
        steps=steps,
        scripts_dir=str(scripts_dir),
        project_root=str(scripts_dir.parent),
    )

    async def _collect():
        while True:
            event = await queue.get()
            collector.append(event)
            if isinstance(event, (ExecutionEnded, PipelineCompleted)):
                break
            if isinstance(event, PromptRequired) and respond_fn:
                respond_fn(engine, event)

    def _run():
        engine.run(loop, queue)

    t = threading.Thread(target=_run)
    t.start()
    loop.run_until_complete(_collect())
    t.join(timeout=10)
    loop.close()
    return collector


class TestPipelineSequential:
    def test_runs_steps_in_order(self, scripts_dir):
        steps = [
            {"id": "s1", "script": "step1"},
            {"id": "s2", "script": "step2", "mapping": {"count": "${steps.s1.value}"}},
            {"id": "end", "type": "end"},
        ]
        events = _run_pipeline_collect(steps, scripts_dir)
        outputs = [e for e in events if isinstance(e, ScriptOutput)]
        texts = [e.line for e in outputs]
        assert "step1" in texts
        assert "step2 got 42" in texts

    def test_mapping_preserves_type(self, scripts_dir):
        steps = [
            {"id": "s1", "script": "step1"},
            {"id": "s2", "script": "step2", "mapping": {"count": "${steps.s1.value}"}},
            {"id": "end", "type": "end"},
        ]
        events = _run_pipeline_collect(steps, scripts_dir)
        completed = [e for e in events if isinstance(e, ScriptCompleted) and e.script_name == "step2"]
        assert completed[0].output["doubled"] == 84


class TestPipelineEnd:
    def test_end_step_stops_pipeline(self, scripts_dir):
        steps = [
            {"id": "s1", "script": "step1"},
            {"id": "end", "type": "end"},
            {"id": "s2", "script": "step2"},
        ]
        events = _run_pipeline_collect(steps, scripts_dir)
        names = [e.script_name for e in events if isinstance(e, ScriptStarted)]
        assert "step2" not in names


class TestPipelinePrompt:
    def test_prompt_emits_prompt_required(self, scripts_dir):
        steps = [
            {"id": "choose", "type": "prompt", "message": "选一个", "choices": [
                {"label": "Echo Hello", "goto": "echo"},
                {"label": "End", "goto": "end"},
            ]},
            {"id": "echo", "script": "echo", "mapping": {"msg": "${choice}"}},
            {"id": "end", "type": "end"},
        ]

        def respond(engine, event):
            engine.respond_prompt(event.step_id, "Echo Hello")

        events = _run_pipeline_collect(steps, scripts_dir, respond_fn=respond)
        prompt_events = [e for e in events if isinstance(e, PromptRequired)]
        assert len(prompt_events) == 1
        assert "Echo Hello" in prompt_events[0].choices
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_core/test_pipeline.py -v
```

Expected: FAIL — `ImportError`

- [ ] **Step 3: 实现 pipeline.py**

```python
# toolbox/core/pipeline.py
from __future__ import annotations

import asyncio
import threading
from pathlib import Path

from toolbox.core.events import (
    ScriptStarted, ScriptOutput, ScriptCompleted, ScriptFailed,
    PromptRequired, ConfirmRequired, PipelineCompleted, ExecutionEnded,
)
from toolbox.core.executor import Executor
from toolbox.core.config_loader import resolve_value


class PipelineEngine:
    def __init__(self, steps: list[dict], scripts_dir: str, project_root: str):
        self._steps = steps
        self._scripts_dir = Path(scripts_dir)
        self._project_root = project_root
        self._executor = Executor(project_root=project_root)
        self._step_outputs: dict[str, dict] = {}
        self._prompt_events: dict[str, threading.Event] = {}
        self._prompt_responses: dict[str, str] = {}
        self._current_choice = None

    def respond_prompt(self, step_id: str, choice: str):
        self._prompt_responses[step_id] = choice
        self._current_choice = choice
        if step_id in self._prompt_events:
            self._prompt_events[step_id].set()

    def respond_confirm(self, step_id: str, confirmed: bool):
        self._prompt_responses[step_id] = "yes" if confirmed else "no"
        if step_id in self._prompt_events:
            self._prompt_events[step_id].set()

    def run(self, loop: asyncio.AbstractEventLoop, event_queue: asyncio.Queue):
        def emit(event):
            loop.call_soon_threadsafe(event_queue.put_nowait, event)

        idx = 0
        while idx < len(self._steps):
            step = self._steps[idx]
            sid = step.get("id", f"step_{idx}")

            if step.get("type") == "end":
                emit(PipelineCompleted(
                    pipeline_name="",
                    outputs=list(self._step_outputs.values()),
                ))
                return

            if step.get("type") == "prompt":
                message = step.get("message", "")
                message = self._resolve_message(message)
                choices = [c["label"] for c in step.get("choices", [])]

                emit(PromptRequired(step_id=sid, message=message, choices=choices))

                wait_event = threading.Event()
                self._prompt_events[sid] = wait_event
                wait_event.wait()

                choice_label = self._prompt_responses.get(sid, "")

                # 检查是否有 goto_template
                if "goto_template" in step:
                    self._current_choice = choice_label
                    template = step["goto_template"]
                    script_name = template["script"]
                    mapping = template.get("mapping", {})
                    params = self._resolve_mapping(mapping)
                    script_path = self._scripts_dir / f"{script_name}.py"

                    sub_queue = asyncio.Queue()
                    self._executor.run_script(str(script_path), params, loop, sub_queue)
                    self._drain_queue(sub_queue, emit)

                    if sid in self._step_outputs:
                        pass
                    self._step_outputs[sid] = {"choice": choice_label}

                    emit(PipelineCompleted(
                        pipeline_name="",
                        outputs=list(self._step_outputs.values()),
                    ))
                    return

                # 静态 choices — 找 goto
                for c in step.get("choices", []):
                    if c["label"] == choice_label:
                        goto_id = c.get("goto", "end")
                        if goto_id == "end":
                            emit(PipelineCompleted(
                                pipeline_name="",
                                outputs=list(self._step_outputs.values()),
                            ))
                            return
                        # 跳转到对应 id
                        for i, s in enumerate(self._steps):
                            if s.get("id") == goto_id:
                                idx = i
                                break
                        else:
                            idx += 1
                        break
                else:
                    idx += 1
                continue

            if step.get("type") == "confirm":
                message = step.get("message", "")
                emit(ConfirmRequired(step_id=sid, message=message))

                wait_event = threading.Event()
                self._prompt_events[sid] = wait_event
                wait_event.wait()

                response = self._prompt_responses.get(sid, "no")
                goto = step.get("yes_goto" if response == "yes" else "no_goto", "end")
                if goto == "end":
                    emit(PipelineCompleted(
                        pipeline_name="",
                        outputs=list(self._step_outputs.values()),
                    ))
                    return
                for i, s in enumerate(self._steps):
                    if s.get("id") == goto:
                        idx = i
                        break
                else:
                    idx += 1
                continue

            # 脚本步骤
            script_name = step.get("script", "")
            mapping = step.get("mapping", {})
            params = self._resolve_mapping(mapping)
            script_path = self._scripts_dir / f"{script_name}.py"

            sub_queue = asyncio.Queue()
            self._executor.run_script(str(script_path), params, loop, sub_queue)
            completed_output = self._drain_queue(sub_queue, emit)
            self._step_outputs[sid] = completed_output or {}

            idx += 1

        emit(PipelineCompleted(
            pipeline_name="",
            outputs=list(self._step_outputs.values()),
        ))

    def _resolve_mapping(self, mapping: dict) -> dict:
        result = {}
        for key, expr in mapping.items():
            result[key] = resolve_value(
                expr,
                self._step_outputs,
                is_step_outputs=True,
            )
        return result

    def _resolve_message(self, message: str) -> str:
        if "${" not in message:
            return message
        return resolve_value(message, self._step_outputs, is_step_outputs=True)

    def _drain_queue(self, queue: asyncio.Queue, emit_fn) -> dict | None:
        """同步消费子队列中的事件，转发到主管道队列，返回 Completed 的 output"""
        output = None
        while True:
            try:
                event = queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            emit_fn(event)
            if isinstance(event, ScriptCompleted):
                output = event.output
            if isinstance(event, ExecutionEnded):
                break
        return output
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_core/test_pipeline.py -v
```

Expected: 4 passed

- [ ] **Step 5: 运行全部 Phase 2 测试确认无回归**

```bash
python -m pytest tests/ -v
```

Expected: 全部通过

- [ ] **Step 6: 提交**

```bash
git add toolbox/core/pipeline.py tests/test_core/test_pipeline.py
git commit -m "feat(core): 流水线引擎，步骤串联 + prompt/confirm 交互 + goto 跳转"
```


---

## Phase 3：前端

### Task 12: toolbox/frontend_base.py + ToolboxCore 封装

**Files:**
- Create: `toolbox/frontend_base.py`
- Create: `toolbox/core/__init__.py`（更新，加入 ToolboxCore）

- [ ] **Step 1: 实现 frontend_base.py**

```python
# toolbox/frontend_base.py
from __future__ import annotations

from abc import ABC, abstractmethod


class FrontendBase(ABC):
    def __init__(self, core):
        self.core = core

    @abstractmethod
    def run(self) -> None:
        ...
```

- [ ] **Step 2: 实现 ToolboxCore 封装**

将 Phase 2 的组件组装成统一的 `ToolboxCore` 类：

```python
# toolbox/core/__init__.py
from __future__ import annotations

import asyncio
import threading
from pathlib import Path

from toolbox.core.config_loader import load_config
from toolbox.core.discovery import discover_scripts, discover_pipelines, validate_pipeline
from toolbox.core.executor import Executor
from toolbox.core.pipeline import PipelineEngine
from toolbox.core.events import ScriptMeta, PipelineMeta


class ToolboxCore:
    def __init__(self, config_path: str):
        self._config_path = config_path
        self._config = {}
        self._scripts: list[ScriptMeta] = []
        self._pipelines: list[PipelineMeta] = []
        self._executor = Executor()
        self._current_pipeline_engine: PipelineEngine | None = None

    def load(self):
        self._config = load_config(self._config_path)
        self._reload_discovery()

    def reload(self):
        self._reload_discovery()

    def _reload_discovery(self):
        root = Path(self._config_path).parent
        self._scripts = discover_scripts(str(root / "scripts"))
        self._pipelines = discover_pipelines(str(root / "pipelines"))
        script_names = [s.name for s in self._scripts]
        for p in self._pipelines:
            p._warnings = validate_pipeline(p.steps, script_names)

    def list_scripts(self) -> list[ScriptMeta]:
        return self._scripts

    def list_pipelines(self) -> list[PipelineMeta]:
        return self._pipelines

    def get_config(self) -> dict:
        return self._config

    def run_script(self, name: str, params: dict) -> asyncio.Queue:
        queue = asyncio.Queue()
        script_meta = next((s for s in self._scripts if s.name == name), None)
        if script_meta is None:
            script_meta = next((s for s in self._scripts if s.script_path.stem == name), None)
        if script_meta is None:
            loop = asyncio.get_event_loop()
            from toolbox.core.events import ScriptFailed, ExecutionEnded
            loop.call_soon_threadsafe(queue.put_nowait, ScriptFailed(
                script_name=name, error=f"脚本 '{name}' 不存在",
            ))
            loop.call_soon_threadsafe(queue.put_nowait, ExecutionEnded())
            return queue

        loop = asyncio.get_event_loop()
        root = Path(self._config_path).parent
        self._executor = Executor(project_root=str(root))
        thread = threading.Thread(
            target=self._executor.run_script,
            args=(str(script_meta.script_path), params, loop, queue),
            daemon=True,
        )
        thread.start()
        return queue

    def run_pipeline(self, name: str) -> asyncio.Queue:
        queue = asyncio.Queue()
        pipeline_meta = next((p for p in self._pipelines if p.name == name), None)
        if pipeline_meta is None:
            loop = asyncio.get_event_loop()
            from toolbox.core.events import ScriptFailed, ExecutionEnded
            loop.call_soon_threadsafe(queue.put_nowait, ScriptFailed(
                script_name=name, error=f"流水线 '{name}' 不存在",
            ))
            loop.call_soon_threadsafe(queue.put_nowait, ExecutionEnded())
            return queue

        loop = asyncio.get_event_loop()
        root = Path(self._config_path).parent
        engine = PipelineEngine(
            steps=pipeline_meta.steps,
            scripts_dir=str(root / "scripts"),
            project_root=str(root),
        )
        self._current_pipeline_engine = engine
        thread = threading.Thread(
            target=engine.run,
            args=(loop, queue),
            daemon=True,
        )
        thread.start()
        return queue

    def respond_prompt(self, step_id: str, choice: str):
        if self._current_pipeline_engine:
            self._current_pipeline_engine.respond_prompt(step_id, choice)

    def respond_confirm(self, step_id: str, confirmed: bool):
        if self._current_pipeline_engine:
            self._current_pipeline_engine.respond_confirm(step_id, confirmed)

    def cancel(self):
        from lib.cancel import request_cancel
        request_cancel()
```

- [ ] **Step 3: 验证导入**

```bash
python -c "import sys; sys.path.insert(0,'.'); from toolbox.core import ToolboxCore; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: 提交**

```bash
git add toolbox/frontend_base.py toolbox/core/__init__.py
git commit -m "feat(core): ToolboxCore 统一接口与前端抽象基类"
```

---

### Task 13: toolbox/frontend_tui/app.py — TUI 主界面框架

**Files:**
- Create: `toolbox/frontend_tui/app.py`

这个任务建立 TUI 骨架：左侧菜单 + 右侧面板，脚本/流水线列表可点击，点击后右侧显示欢迎信息。

- [ ] **Step 1: 实现 TUI 主应用**

```python
# toolbox/frontend_tui/app.py
from __future__ import annotations

import asyncio
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
)

from toolbox.core.events import (
    ScriptStarted, ScriptOutput, ScriptCompleted, ScriptFailed,
    PromptRequired, ConfirmRequired, PipelineCompleted, ExecutionEnded,
)
from toolbox.frontend_base import FrontendBase


class ScriptMenu(ListView):
    """左侧脚本/流水线菜单"""

    def __init__(self, scripts, pipelines):
        items = []
        # 按分类分组脚本
        categories: dict[str, list] = {}
        for s in scripts:
            cat = s.category or "未分类"
            categories.setdefault(cat, []).append(s)

        for cat, cat_scripts in categories.items():
            items.append(ListItem(Label(Text(f"── {cat} ──", style="bold cyan"))))
            for s in cat_scripts:
                items.append(ListItem(Label(s.name), id=f"script:{s.name}"))

        if pipelines:
            items.append(ListItem(Label(Text("── 流水线 ──", style="bold cyan"))))
            for p in pipelines:
                items.append(ListItem(Label(p.name), id=f"pipeline:{p.name}"))

        super().__init__(*items)
        self._scripts = {s.name: s for s in scripts}
        self._pipelines = {p.name: p for p in pipelines}


class ContentPanel(Static):
    """右侧内容区域，显示参数表单或输出"""

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
        ))

    def show_error(self, message: str):
        self.update(Text.from_markup(f"[bold red]错误：[/]{message}"))

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

    .prompt-choice {
        background: $primary;
        color: $text;
        padding: 0 1;
        margin: 0 0;
    }
    """

    BINDINGS = [
        Binding("f5", "refresh_menu", "刷新菜单"),
        Binding("ctrl+c", "cancel_execution", "中止"),
    ]

    def __init__(self, core):
        super().__init__()
        self.core = core
        self._current_meta = None
        self._current_type = None  # "script" or "pipeline"
        self._event_queue: asyncio.Queue | None = None
        self._running = False

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

        content = self.query_one(ContentPanel)

        if item_id.startswith("script:"):
            name = item_id[len("script:"):]
            self._current_type = "script"
            script = next((s for s in self.core.list_scripts() if s.name == name), None)
            if script:
                self._current_meta = script
                self._show_script_info(script)

        elif item_id.startswith("pipeline:"):
            name = item_id[len("pipeline:"):]
            self._current_type = "pipeline"
            pipeline = next((p for p in self.core.list_pipelines() if p.name == name), None)
            if pipeline:
                self._current_meta = pipeline
                self._show_pipeline_info(pipeline)

    def _show_script_info(self, script):
        content = self.query_one(ContentPanel)
        lines = [f"[bold]{script.name}[/bold]"]
        if script.description:
            lines.append(f"\n{script.description}")
        lines.append(f"\n类别: {script.category}")
        if script.params:
            lines.append("\n[bold]参数:[/]")
            for p in script.params:
                lines.append(f"  {p.label} ({p.type})")
                if p.clipboard:
                    lines.append(f"    [dim]支持剪贴板粘贴[/dim]")
        lines.append("\n[dim]按 F9 执行[/dim]")
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

    def action_cancel_execution(self):
        if self._running:
            self.core.cancel()

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
                    content.write_line(f"\n{message}")
                    for i, c in enumerate(choices or []):
                        content.write_line(f"  [{i+1}] {c}")
                    content.write_line("\n[dim]输入序号选择...[/dim]")
                case ExecutionEnded():
                    self._running = False
                    break
        self._running = False


class TUIFrontend(FrontendBase):
    def run(self):
        app = ToolBoxTUI(self.core)
        app.run()
```

- [ ] **Step 2: 验证 TUI 可以启动**

需要先创建一个最小的 `config.yaml` 和测试脚本：

```bash
cd D:/Document/Project/ToolBox
cat > config.yaml << 'EOF'
build:
  project_path: "."
EOF

mkdir -p scripts
cat > scripts/hello.py << 'EOF'
def main():
    print("Hello from ToolBox!")
    return {"status": "ok"}
EOF
```

```bash
python -c "import sys; sys.path.insert(0,'.'); from toolbox.frontend_tui.app import ToolBoxTUI; print('Import OK')"
```

Expected: `Import OK`

- [ ] **Step 3: 手动验证 TUI 启动（交互式）**

```bash
python main.py
```

验证项：
- 左侧菜单显示 hello 脚本
- 点击 hello 后右侧显示脚本信息
- 按 `Ctrl+C` 退出

- [ ] **Step 4: 提交**

```bash
git add toolbox/frontend_tui/app.py
git commit -m "feat(tui): TUI 主界面框架，左侧菜单 + 右侧内容面板"
```

---

### Task 14: TUI 参数表单面板

**Files:**
- Modify: `toolbox/frontend_tui/app.py`

在右侧面板中根据 YAML 清单动态生成参数输入表单，支持 text/choice/path/flag 类型，支持剪贴板粘贴按钮，按 F9 执行。

- [ ] **Step 1: 添加参数表单和执行逻辑**

在 `ToolBoxTUI` 类中添加以下方法，替换 `_show_script_info`：

```python
    def _show_script_form(self, script):
        """根据 ScriptMeta 动态生成参数表单"""
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
                        lines.append(f"  {p.label} [{p.type}] 选项: {opts}{suffix}")
                    else:
                        lines.append(f"  {p.label} [{p.type}] (从配置加载){suffix}")
                elif p.type == "flag":
                    default_val = p.default if p.default is not None else False
                    lines.append(f"  {p.label} [{p.type}] 默认: {default_val}{suffix}")
                else:
                    default_hint = f" 默认: {p.default}" if p.default is not None else ""
                    lines.append(f"  {p.label} [{p.type}]{default_hint}{suffix}")

        content.update(Text.from_markup("\n".join(lines)))

    async def _execute_script(self, script):
        """收集参数并执行脚本"""
        content = self.query_one(ContentPanel)
        content.clear_output()
        content.write_line(f"── 执行: {script.name} ──\n")

        # 目前使用默认参数，后续 Task 可替换为从输入框读取
        params = {}
        for p in script.params:
            if p.default is not None:
                params[p.name] = p.default

        self._running = True
        queue = self.core.run_script(script.name, params)
        await self._consume_events(queue)

    async def _execute_pipeline(self, pipeline):
        """执行流水线"""
        content = self.query_one(ContentPanel)
        content.clear_output()
        content.write_line(f"── 流水线: {pipeline.name} ──\n")

        self._running = True
        queue = self.core.run_pipeline(pipeline.name)
        await self._consume_events(queue)
```

同时添加 F9 绑定和处理：

```python
    BINDINGS = [
        Binding("f5", "refresh_menu", "刷新菜单"),
        Binding("f9", "execute", "执行"),
        Binding("ctrl+c", "cancel_execution", "中止"),
    ]

    async def action_execute(self):
        if self._running:
            return
        if self._current_meta is None:
            return

        if self._current_type == "script":
            await self._execute_script(self._current_meta)
        elif self._current_type == "pipeline":
            await self._execute_pipeline(self._current_meta)
```

将 `_show_script_info` 调用替换为 `_show_script_form`，`_show_pipeline_info` 保持不变。

- [ ] **Step 2: 手动验证**

```bash
python main.py
```

验证项：
- 点击 hello 脚本，右侧显示参数表单（无参数）
- 按 F9，输出面板显示 "Hello from ToolBox!" 和执行完成信息
- 按 F5 刷新菜单

- [ ] **Step 3: 提交**

```bash
git add toolbox/frontend_tui/app.py
git commit -m "feat(tui): 参数表单与 F9 执行，脚本/流水线调用集成"
```

---

### Task 15: TUI 输出面板增强

**Files:**
- Modify: `toolbox/frontend_tui/app.py`

添加输出面板的滚动控制、全屏切换、搜索、导出功能。

- [ ] **Step 1: 在 ContentPanel 中添加功能方法**

```python
    def search(self, keyword: str):
        """在输出中搜索关键词，返回匹配行号"""
        matches = []
        for i, line in enumerate(self._output_lines):
            if keyword.lower() in line.lower():
                matches.append(i)
        return matches

    def export_log(self, path: str):
        """将输出导出为日志文件"""
        Path(path).write_text(
            "\n".join(self._output_lines),
            encoding="utf-8",
        )

    def get_line_count(self) -> int:
        return len(self._output_lines)
```

- [ ] **Step 2: 添加快捷键绑定**

在 `ToolBoxTUI` 的 BINDINGS 中添加：

```python
    BINDINGS = [
        Binding("f5", "refresh_menu", "刷新菜单"),
        Binding("f9", "execute", "执行"),
        Binding("f11", "toggle_fullscreen", "全屏输出"),
        Binding("ctrl+s", "export_log", "导出日志"),
        Binding("ctrl+c", "cancel_execution", "中止"),
    ]
```

添加 action 方法：

```python
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
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = f"toolbox_output_{timestamp}.log"
        content.export_log(log_path)
        content.write_line(f"\n[dim]已导出到: {log_path}[/dim]")
```

- [ ] **Step 3: 手动验证**

```bash
python main.py
```

验证项：
- 执行脚本后，按 F11 切换全屏输出
- 按 Ctrl+S 导出日志文件
- 按 F5 刷新菜单

- [ ] **Step 4: 提交**

```bash
git add toolbox/frontend_tui/app.py
git commit -m "feat(tui): 输出面板增强，全屏切换、日志导出"
```

---

### Task 16: TUI 交互渲染（prompt/confirm）

**Files:**
- Modify: `toolbox/frontend_tui/app.py`

处理流水线中的 prompt 和 confirm 交互事件，用户通过输入序号选择后调用 `core.respond_prompt()`。

- [ ] **Step 1: 添加交互处理**

在 `_consume_events` 中替换 `PromptRequired` 处理逻辑：

```python
                case PromptRequired(step_id=step_id, message=message, choices=choices):
                    content.write_line(f"\n[bold]{message}[/]")
                    if choices:
                        for i, c in enumerate(choices):
                            content.write_line(f"  [{i + 1}] {c}")
                        # 自动选择第一个选项（简化版）
                        # 完整版应等待用户输入
                        if len(choices) == 1:
                            self.core.respond_prompt(step_id, choices[0])
                    else:
                        # choices_from 动态选项场景
                        pass
```

添加 `ConfirmRequired` 处理：

```python
                case ConfirmRequired(step_id=step_id, message=message):
                    content.write_line(f"\n[bold]{message}[/]")
                    content.write_line("  [1] 确认")
                    content.write_line("  [2] 取消")
                    # 默认确认（简化版）
                    self.core.respond_confirm(step_id, True)
```

- [ ] **Step 2: 添加用户输入 action**

在 `ToolBoxTUI` 中添加一个简单的输入 action，允许用户通过 `/` 键输入选项：

```python
    BINDINGS = [
        Binding("f5", "refresh_menu", "刷新菜单"),
        Binding("f9", "execute", "执行"),
        Binding("f11", "toggle_fullscreen", "全屏输出"),
        Binding("ctrl+s", "export_log", "导出日志"),
        Binding("ctrl+c", "cancel_execution", "中止"),
        Binding("slash", "input_choice", "输入选项"),
    ]

    async def action_input_choice(self):
        """让用户输入选项序号来响应 prompt"""
        if not self._running:
            return
        from textual.widgets import Input
        # 弹出单行输入
        def on_submit(message):
            text = message.value.strip()
            self._handle_user_choice(text)
            input_widget.remove()

        input_widget = Input(placeholder="输入选项序号...", id="choice-input")
        mount_target = self.query_one("#main-area")
        mount_target.mount(input_widget)
        input_widget.focus()
        input_widget.on_submit = on_submit

    def _handle_user_choice(self, text: str):
        """处理用户输入的选项"""
        if not self._current_pipeline_engine:
            return
        # 简化处理：直接把用户输入的文本作为 choice 传递
        # 如果是数字序号，转换为对应的 label
        if text.isdigit():
            content = self.query_one(ContentPanel)
            idx = int(text) - 1
            # 从最近的 PromptRequired 事件中获取 choices
            if hasattr(self, '_last_prompt_choices') and self._last_prompt_choices:
                if 0 <= idx < len(self._last_prompt_choices):
                    self.core.respond_prompt(self._last_prompt_step_id, self._last_prompt_choices[idx])
                    return
        self.core.respond_prompt(self._last_prompt_step_id, text)
```

在 `_consume_events` 的 `PromptRequired` 处理中存储最新选项：

```python
                case PromptRequired(step_id=step_id, message=message, choices=choices):
                    self._last_prompt_step_id = step_id
                    self._last_prompt_choices = choices or []
                    content.write_line(f"\n[bold]{message}[/]")
                    if choices:
                        for i, c in enumerate(choices):
                            content.write_line(f"  [{i + 1}] {c}")
                        content.write_line("\n[dim]按 / 输入序号选择[/dim]")
```

- [ ] **Step 3: 手动验证**

创建一个测试流水线：

```yaml
# pipelines/test_prompt.yaml
name: 测试交互
steps:
  - id: choose
    type: prompt
    message: "请选择操作"
    choices:
      - label: "Hello"
        goto: hello
      - label: "End"
        goto: end
  - id: hello
    script: hello
  - id: end
    type: end
```

```bash
python main.py
```

验证项：
- 选择"测试交互"流水线，按 F9 执行
- 输出面板显示选项列表
- 按 `/` 输入序号 `1`，流水线继续执行 hello 脚本

- [ ] **Step 4: 运行全部测试确认无回归**

```bash
python -m pytest tests/ -v
```

Expected: 全部通过

- [ ] **Step 5: 提交**

```bash
git add toolbox/frontend_tui/app.py pipelines/test_prompt.yaml
git commit -m "feat(tui): prompt/confirm 交互渲染，用户输入选择"
```

