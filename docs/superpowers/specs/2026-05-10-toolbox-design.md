# ToolBox — Android 开发工作流自动化工具

## 概述

统一入口的自动化工具，将 Android 开发日常工作流（编译打包、Git 管理、崩溃分析、邮件跟踪等）集中管理。支持脚本自动发现、流水线编排、交互式分支，前后端分离，前端可替换（TUI / Web / GUI）。

## 设计原则

- **脚本零 UI 依赖**：脚本是纯 Python，可独立运行，不依赖 TUI 框架
- **渐进式集成**：丢进去就能跑 → 加清单有参数 → 接管道可串联
- **前后端分离**：后端纯逻辑 + 事件驱动，前端只负责渲染
- **声明式配置**：YAML 清单描述脚本接口，YAML 文件描述流水线
- **单脚本串行执行**：同一时刻只运行一个脚本/流水线，简化线程模型和资源管理

## 项目结构

```
ToolBox/
├── main.py                          # 入口，选择前端启动
├── run.py                           # 脚本独立运行器
├── config.yaml                      # 全局配置
├── config.example.yaml              # 配置模板
├── requirements.txt                 # 依赖
├── toolbox/
│   ├── __init__.py
│   ├── core/                        # 后端 — 纯 Python，零 UI 依赖
│   │   ├── __init__.py
│   │   ├── discovery.py             # 脚本 & 流水线自动发现
│   │   ├── executor.py              # 脚本执行引擎（线程 + 事件队列）
│   │   ├── pipeline.py              # 流水线引擎（解析 + 串联 + 交互分支）
│   │   ├── config_loader.py         # 配置加载（支持字段引用和 config: 前缀）
│   │   └── events.py                # 事件定义
│   ├── frontend_base.py             # 前端抽象基类
│   └── frontend_tui/                # Textual TUI 前端
│       ├── __init__.py
│       └── app.py
├── lib/                             # 公共工具库（不依赖 UI 框架）
│   ├── __init__.py
│   ├── process.py                   # 子进程封装（实时逐行输出、超时、cwd 支持）
│   ├── git_helper.py                # Git 操作封装
│   ├── config.py                    # 读取 config.yaml
│   ├── clipboard.py                 # 剪贴板读写（基于 pyperclip）
│   ├── cancel.py                    # 协作式取消检查
│   └── path_helper.py               # 路径工具
├── scripts/                         # 工作流脚本
│   ├── addr2line.py
│   ├── addr2line.yaml
│   ├── apk_build.py
│   ├── apk_build.yaml
│   ├── git_check.py
│   ├── git_check.yaml
│   ├── git_merge.py
│   ├── git_merge.yaml
│   ├── email_check.py
│   ├── email_check.yaml
│   └── clean_build.py               # 无清单脚本，仍可被发现和执行
└── pipelines/                       # 流水线定义
    ├── crash_analysis.yaml
    ├── git_sync.yaml
    └── daily_check.yaml
```

**依赖关系：**

- `scripts/` → 可导入 `lib/`，不依赖 `toolbox/`
- `toolbox/core/` → 导入 `lib/`，零 UI 依赖
- `toolbox/frontend_tui/` → 导入 `toolbox/core/` + Textual + Rich
- `lib/` → 依赖 `pyyaml`、`pyperclip`，无 UI 框架依赖

**依赖分层（requirements.txt）：**

```
# 核心依赖
pyyaml>=6.0
pyperclip>=1.8.0

# TUI 前端（可选）
textual>=3.0.0
rich>=13.0.0
```

## 脚本体系

### 三层渐进集成

| 层级 | 操作 | 获得的能力 |
|------|------|-----------|
| Tier 1 | 复制 `.py` 到 `scripts/` | TUI 自动发现、可运行、有输出 |
| Tier 2 | 运行 `--init-script` 生成 YAML 清单并编辑 | 参数输入、剪贴板、下拉选择 |
| Tier 3 | 确保 `main()` 返回 `dict`，编写 `pipelines/*.yaml` | 流水线串联 |

### 脚本编写约定

```python
# scripts/git_check.py

from lib.git_helper import fetch, get_new_commits
from lib.config import get_config


def main(repo_name=None):
    """框架调用入口。参数名与 YAML 清单 params 一一对应。"""
    repos = get_config("git.repos")
    repo = next(r for r in repos if r["name"] == repo_name)

    fetch(repo["path"])
    commits = get_new_commits(repo["path"], repo["branch"])

    # print() → 输出面板实时显示，给人看
    if commits:
        for c in commits:
            print(f"  {c['hash'][:8]} {c['message']}")

    # return dict → 传递给流水线下游
    return {
        "new_commits": len(commits),
        "repo_name": repo_name,
    }
```

**约定：**

| 规则 | 说明 |
|------|------|
| 入口函数 | `def main(**params)`，参数名对应 YAML 清单 |
| 用户可见输出 | `print()`，实时显示在输出面板 |
| 结构化输出 | `return dict`，传递给流水线下游。返回 `None` 视为 `{}`，返回非 dict 自动包装为 `{"result": 值}` |
| 独立运行 | `python run.py git_check --repo_name 主项目` |
| 协作取消 | 长耗时脚本可调用 `from lib.cancel import is_cancelled` 检查取消状态 |

### 脚本独立运行器（run.py）

按文件路径加载脚本（不把 `scripts/` 加入 `sys.path`，避免与标准库名冲突），支持命名参数：

```python
# run.py
import sys, pathlib, argparse, inspect
import importlib.util

ROOT = pathlib.Path(__file__).parent
sys.path.insert(0, str(ROOT))  # 让 from lib.xxx import 生效

if len(sys.argv) < 2:
    print("用法: python run.py <脚本名> [参数...]")
    print("示例: python run.py git_check --repo_name 主项目")
    sys.exit(1)

script_path = ROOT / "scripts" / (sys.argv[1].replace(".py", "") + ".py")
if not script_path.exists():
    print(f"脚本不存在: {script_path}")
    sys.exit(1)

# 按文件路径加载，避免模块名污染 sys.path
spec = importlib.util.spec_from_file_location(
    f"toolbox_script_{script_path.stem}", script_path
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# 从 main() 签名自动构建 argparse
parser = argparse.ArgumentParser(description=f"运行 {script_path.stem}")
for name, param in inspect.signature(mod.main).parameters.items():
    parser.add_argument(f"--{name}", default=param.default)

args = parser.parse_args(sys.argv[2:])
result = mod.main(**vars(args))
if result:
    print(result)
```

### 脚本清单 YAML Schema

```yaml
name: 崩溃地址分析          # 可选，缺省取文件名
description: 解析 native 崩溃地址对应的源码位置  # 可选
category: 调试              # 可选，缺省归"未分类"

params:
  - name: address
    label: 崩溃地址
    type: text              # text | choice | path | flag
    multiline: true         # 可选，多行输入
    clipboard: true         # 可选，显示"从剪贴板粘贴"按钮
    default: ""             # 可选

  - name: so_file
    label: SO 文件
    type: choice
    options_from:
      source: config:addr2line.so_files    # 从 config.yaml 动态读取
      label_field: name                    # 下拉框显示的字段
      value_field: path                    # 传给 main() 的字段
    # 或静态选项: options: [libapp.so, libnative.so]

outputs:
  - result                  # main() 返回 dict 的 key，用于流水线映射校验

env:                        # 可选
  working_dir: config:build.project_path    # 传给子进程的 cwd，不改变 Python 进程目录
```

**param type 说明：**

| type | UI 组件 | 特有字段 |
|------|---------|---------|
| `text` | 文本输入框 | `multiline`, `clipboard` |
| `choice` | 下拉选择 | `options` 静态列表 或 `options_from` 动态读取 |
| `path` | 路径选择 | `path_type: file \| dir` |
| `flag` | 复选框 | `default: true` |

**`options_from` 语法：**

```yaml
# 复杂对象列表 — 指定 label/value 字段
options_from:
  source: config:addr2line.so_files
  label_field: name
  value_field: path

# 简单字符串列表 — 简写
options_from: config:some.string_list
```

### `--init-script` 自动生成模板

```bash
python main.py --init-script scripts/my_script.py
```

框架通过 `ast` 模块静态解析脚本 `main()` 函数签名（不执行脚本，避免副作用），自动生成 YAML 模板：

```python
import ast

def parse_main_signature(script_path: Path) -> list[ParamDef]:
    source = script_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            return [_ast_param_to_def(arg) for arg in node.args.args]
    return []
```

生成结果：

```yaml
# scripts/my_script.yaml (自动生成)
name: 我的脚本
category: 未分类
params:
  - name: target_path
    label: 目标路径
    type: text
    # clipboard: true
outputs:
  - result
```

## 变量与映射体系

### 变量语法

所有动态值统一使用 `${}` 插值，通过前缀区分来源：

| 语法 | 含义 | 示例 |
|------|------|------|
| `${steps.<id>.<field>}` | 引用上游步骤 `main()` 返回 dict 中的字段 | `${steps.check_remote.new_commits}` |
| `${choice}` | 当前 prompt 用户选择的值（仅在 `goto_template` 中可用） | `${choice}` |
| `${config:<path>}` | 引用 `config.yaml` 中的值，`.` 分隔逐层取值 | `${config:addr2line.default_so}` |

### 映射语法

```yaml
mapping:
  address: ${steps.parse_addresses.addresses}    # 变量：保留原始类型
  so_file: ${config:addr2line.default_so}        # 配置：保留原始类型
  verbose: true                                   # 字面量：布尔
  output_path: "/tmp/result.txt"                  # 字面量：字符串
  count: 42                                       # 字面量：数字
  msg: "检测到 ${steps.check_remote.new_commits} 个新提交"  # 混合：字符串插值
```

**类型保持规则：**
- YAML 值**整体是**一个 `${}` 表达式（无其他字符）→ 传递原始 Python 对象，保留类型（int 是 int，list 是 list）
- `${}` 嵌入在字符串中 → 做字符串插值，值被转为 str
- 无 `${}` → 按字面量传递，YAML 原生类型（str/int/bool）

### 消息模板

`prompt` 的 `message` 字段支持 `${}` 字符串插值：

```yaml
message: "检测到 ${steps.check_remote.new_commits} 个新提交，请选择："
```

## 流水线体系

### 步骤类型约束

步骤分为两类，**互斥**：

| 步骤类型 | 必填字段 | 可选字段 |
|---------|---------|---------|
| 脚本步骤 | `id` + `script` | `mapping` |
| 交互步骤 | `id` + `type` (prompt/confirm/end) | `message`, `choices`, `choices_from`, `yes_goto`, `no_goto`, `goto_template` |

discovery 校验时检查：步骤同时出现 `script` 和 `type` → 报错。

### 流水线 YAML Schema

```yaml
# pipelines/git_sync.yaml
name: Git 仓库同步
description: 检查远端更新，用户决定后续操作

steps:
  - id: check_remote
    script: git_check

  - id: choose_action
    type: prompt
    message: "检测到 ${steps.check_remote.new_commits} 个新提交，请选择："
    choices:
      - label: "查看提交详情"
        goto: show_log
      - label: "合并远端更新"
        goto: git_merge
      - label: "跳过"
        goto: end

  - id: show_log
    script: git_show_log
    mapping:
      count: ${steps.check_remote.new_commits}

  - id: after_log
    type: prompt
    message: "下一步："
    choices:
      - label: "合并远端更新"
        goto: git_merge
      - label: "返回选择"
        goto: choose_action

  - id: git_merge
    script: git_merge

  - id: end
    type: end
```

**执行顺序：** 步骤按列表顺序依次执行。`goto` 跳转到指定 id 的步骤。交互只有 `prompt` 一种机制，显式写在步骤列表中。

### 交互节点类型

| type | 行为 |
|------|------|
| `prompt` | 显示选项列表，等用户选择后跳转对应步骤 |
| `confirm` | 是/否确认 |
| `end` | 终止流水线 |

**confirm 示例：**

```yaml
- id: confirm_merge
  type: confirm
  message: "确认合并远端更新？"
  yes_goto: git_merge
  no_goto: end
```

### 动态选项

```yaml
- id: choose_repo
  type: prompt
  message: "选择仓库："
  choices_from: ${steps.list_repos.repo_names}
  goto_template:
    script: git_check
    mapping:
      repo_name: ${choice}
```

`${choice}` 是特殊的运行时变量，代表用户在当前 prompt 中选择的值。

### 执行规则

- 步骤按列表顺序执行，前一步失败则终止流水线
- 每步实时显示 `print()` 输出
- 遇到 `prompt`/`confirm` 暂停，等用户操作后继续
- 全部完成后展示最后一步的 `return` 结果摘要
- 流水线引擎维护 `step_outputs: dict[str, dict]` 存储每步返回值
- `goto` 目标不存在时在 discovery 校验阶段报错

## 核心框架

### 事件定义（events.py）

```python
@dataclass
class ScriptStarted(Event):
    script_name: str
    step_info: str | None

@dataclass
class ScriptOutput(Event):
    script_name: str
    line: str

@dataclass
class ScriptCompleted(Event):
    script_name: str
    output: dict | None
    duration: float

@dataclass
class ScriptFailed(Event):
    script_name: str
    error: str
    traceback: str

@dataclass
class PromptRequired(Event):
    step_id: str
    message: str
    choices: list[str]

@dataclass
class ConfirmRequired(Event):
    step_id: str
    message: str

@dataclass
class PipelineCompleted(Event):
    pipeline_name: str
    outputs: list[dict]

@dataclass
class ExecutionEnded(Event):
    """执行结束哨兵事件。收到后前端应退出事件消费循环。"""
    pass
```

### 元数据结构

```python
@dataclass
class ParamDef:
    name: str
    label: str
    type: str                   # text | choice | path | flag
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

### 后端接口（ToolboxCore）

```python
class ToolboxCore:
    def __init__(self, config_path: str): ...
    def load(self) -> None: ...
    def reload(self) -> None: ...                   # F5 刷新：重新扫描 scripts/ 和 pipelines/
    def list_scripts(self) -> list[ScriptMeta]: ...
    def list_pipelines(self) -> list[PipelineMeta]: ...
    def run_script(self, name: str, params: dict) -> asyncio.Queue: ...
    def run_pipeline(self, name: str) -> asyncio.Queue: ...
    def respond_prompt(self, step_id: str, choice: str) -> None: ...
    def respond_confirm(self, step_id: str, confirmed: bool) -> None: ...
    def cancel(self) -> None: ...
```

`run_script()` 和 `run_pipeline()` 返回 `asyncio.Queue`，前端在自身异步上下文中消费事件。交互节点（prompt/confirm）使工作线程阻塞等待 `threading.Event`，前端调用 `respond_prompt()`/`respond_confirm()` 唤醒。

`reload()` 仅重新扫描 `scripts/` 和 `pipelines/` 目录并更新菜单，不重新加载 `config.yaml`（配置变更需重启 TUI）。脚本代码本身每次执行都重新加载（`spec_from_file_location`），所以修改脚本不需要 F5。

### 前端抽象（frontend_base.py）

```python
class FrontendBase(ABC):
    def __init__(self, core: ToolboxCore): ...
    @abstractmethod
    def run(self) -> None: ...
```

前端持有 `core` 引用，通过调用 `core.run_script()` 获取事件队列，在自身异步循环中消费。收到 `ExecutionEnded` 后退出循环回到空闲状态：

```python
# TUI 前端消费示例
class TUIFrontend(FrontendBase):
    async def _consume_events(self, queue: asyncio.Queue):
        while True:
            event = await queue.get()
            match event:
                case ScriptOutput(line=line):
                    self.output_panel.write(line)
                case PromptRequired(step_id=step_id, choices=choices):
                    self._show_choices(step_id, choices)
                case ScriptCompleted(output=output):
                    self._show_summary(output)
                case ExecutionEnded():
                    self._set_idle()
                    break
```

### 线程模型

```
UI 线程 (async)                        工作线程 (sync)
    │                                        │
    ├─ queue = core.run_script()             │
    │   → 启动工作线程 ─────────────────────►│
    │                                        ├─ 替换 sys.stdout 为 OutputCapture
    │                                        ├─ main(**params)
    │                                        │   ├─ print() → OutputCapture.write()
    │                                        │   │   → loop.call_soon_threadsafe(
    │                                        │   │       queue.put_nowait, ScriptOutput)
    │                                        │   └─ return dict → emit(ScriptCompleted)
    │◄── await queue.get() ──────────────────┤
    ├─ 渲染到界面                             │
    │                                        ├─ 遇到 prompt:
    │                                        │   → emit(PromptRequired)
    │                                        │   → threading.Event.wait() 阻塞
    │◄── 渲染选项列表                         │
    │                                        │
    ├─ core.respond_prompt() ───────────────►│
    │   → threading.Event.set() ─────────────┤
    │                                        ├─ 恢复执行
    │                                        ├─ 最后 → emit(ExecutionEnded)
    │◄── 收到 ExecutionEnded ────────────────┤
    ├─ 回到空闲状态                            │
```

**关键设计：**
- 工作线程中临时替换 `sys.stdout`，脚本结束后立即恢复（单脚本串行，不会冲突）
- 工作线程通过 `loop.call_soon_threadsafe(queue.put_nowait, event)` 安全地向 asyncio Queue 推送事件
- 线程同步用 `threading.Event`（工作线程阻塞/唤醒）
- 子进程输出由 `lib.process.run()` 通过 `subprocess.Popen` 逐行捕获，走同一事件队列
- 工作线程为 daemon 线程，进程退出时自动清理

### 取消机制

```
用户按 Ctrl+C
    → core.cancel()
        → 终止当前子进程 (proc.terminate() → 2秒后 proc.kill())
        → 设置 lib.cancel._cancelled = True
        → 子进程死后脚本自然结束，工作线程退出
```

对于无子进程的纯 Python 脚本，取消依赖脚本主动调用 `is_cancelled()` 协作：

```python
from lib.cancel import is_cancelled

def main():
    for item in large_list:
        if is_cancelled():
            return {"status": "cancelled"}
        process(item)
```

### 脚本加载（executor.py）

按文件路径加载，不污染 `sys.path`，避免脚本名与标准库冲突：

```python
import importlib.util

def load_script(script_path: Path):
    spec = importlib.util.spec_from_file_location(
        f"toolbox_script_{script_path.stem}",
        script_path,
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.main
```

### 输出捕获机制

```python
class OutputCapture(io.TextIOBase):
    """临时替换 sys.stdout，每行触发事件"""
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
        """刷出未换行的残余文本"""
        if self._buffer:
            self._callback(self._buffer)
            self._buffer = ""

    @property
    def encoding(self):
        return "utf-8"
```

### 工作线程执行

```python
def _run_in_thread(self, script_main, params, loop, event_queue):
    def emit(event):
        loop.call_soon_threadsafe(event_queue.put_nowait, event)

    capture = OutputCapture(lambda line: emit(ScriptOutput(
        script_name=self._current_script, line=line,
    )))
    original_stdout = sys.stdout
    sys.stdout = capture
    try:
        result = script_main(**params)
        # 统一返回值处理
        if result is None:
            result = {}
        elif not isinstance(result, dict):
            result = {"result": result}
        emit(ScriptCompleted(
            script_name=self._current_script, output=result, duration=0,
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

### 子进程封装（lib/process.py）

```python
def run(cmd, cwd=None, env=None):
    """
    封装 subprocess.Popen，实时逐行输出。
    cwd: 子进程工作目录，不改变 Python 进程当前目录。
    """
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
        print(line, end="")       # 通过 stdout 捕获 → 事件队列
    proc.wait()
    return proc.returncode
```

脚本中使用：

```python
from lib.process import run
from lib.config import get_config

def main():
    project = get_config("build.project_path")
    run(["gradlew.bat", "assembleRelease"], cwd=project)
```

### 协作式取消（lib/cancel.py）

```python
import threading

_cancelled = False
_cancel_event = threading.Event()

def is_cancelled():
    return _cancelled

def request_cancel():
    global _cancelled
    _cancelled = True

def reset():
    global _cancelled
    _cancelled = False
```

executor 在每次执行前调用 `reset()`，`cancel()` 调用 `request_cancel()`。

### 配置读取（lib/config.py）

```python
import os, pathlib
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

默认基于项目根目录定位 `config.yaml`，支持 `TOOLBOX_CONFIG` 环境变量覆盖。

### 自动发现（discovery.py）

启动时：

1. 扫描 `scripts/*.py` → 查找同名 `.yaml` 清单
2. 清单不存在 → Tier 1，仅记录脚本名和路径
3. 清单存在 → 解析 params、outputs，形成 `ScriptMeta`
4. 扫描 `pipelines/*.yaml` → 加载流水线定义，形成 `PipelineMeta`
5. 校验流水线引用的脚本是否存在
6. 校验 `${steps.<id>.<field>}` 映射中引用的字段是否与脚本 outputs 声明匹配
7. 校验步骤类型互斥：`script` 和 `type` 不能同时出现
8. 校验 `goto` 目标步骤 id 是否存在
9. 有错误标记警告但不阻止启动，只阻止执行该流水线

`reload()`（F5 触发）重新执行上述 1-9 步。

### 配置加载（config_loader.py）

支持字段引用避免重复：

```yaml
build:
  project_path: "D:/android/project"

git:
  repos:
    - name: "主项目"
      path: "${build.project_path}"
```

解析规则：遍历所有值节点，遇到 `${xxx.yyy}` 字符串时按 `.` 分隔逐层取值替换。检测循环引用，有则报错。不支持列表索引。

`${config:addr2line.default_so}` 在清单和流水线中引用配置值，解析为 `config.yaml` 中对应路径的值。

## TUI 前端

### 界面布局

```
┌─────────────────────────────────────────────────────────────┐
│ ToolBox                                          [帮助] [退出] │
├──────────────┬──────────────────────────────────────────────┤
│              │                                              │
│  ▸ 调试      │  崩溃地址分析                                  │
│    崩溃地址分析│ ┌──────────────────────────────────────────┐  │
│              │ │ 崩溃地址  [从剪贴板粘贴]                     │  │
│  ▸ 构建      │ │ ┌──────────────────────────────────────┐  │  │
│    APK 编译   │ │ │  (多行文本输入)                        │  │  │
│              │ │ └──────────────────────────────────────┘  │  │
│  ▸ Git       │ │                                          │  │
│    仓库同步   │ │ SO 文件   [▼ libapp.so              ]      │  │
│    远端检查   │ │                                          │  │
│              │ │          [ 执行 ]                         │  │
│  ▸ 邮件      │ └──────────────────────────────────────────┘  │
│    问题监控   │ ┌──────────────────────────────────────────┐  │
│              │ │ 输出 [自动滚动 ✓] [全屏] [导出] [搜索] 156行│  │
│  ▸ 流水线    │ ├──────────────────────────────────────────┤  │
│    崩溃分析   │ │ > 分析 0x7a3b → main.c:42 (func_x)       │  │
│    每日检查   │ │ > 分析 0x8c1d → native.cpp:108 (process)  │  │
│              │ └──────────────────────────────────────────┘  │
├──────────────┴──────────────────────────────────────────────┤
│ F5 刷新菜单  F9 执行  Ctrl+C 中止                            │
└─────────────────────────────────────────────────────────────┘
```

### 输出面板操作

| 操作 | 快捷键 | 说明 |
|------|--------|------|
| 向上滚动 | `PageUp` / 鼠标滚轮 | 查看历史输出，自动滚动关闭 |
| 跳到最新 | `End` / 点"自动滚动" | 重新锁定底部 |
| 全屏输出 | `F11` | 输出面板撑满窗口，再按恢复 |
| 搜索 | `Ctrl+F` | 输出中关键词搜索，高亮匹配 |
| 导出 | `Ctrl+S` | 保存为 `.log` 文件 |
| 中止 | `Ctrl+C` | 终止当前脚本/子进程 |

### 导航

- 键盘上下 + Enter
- 鼠标点击
- `/` 搜索过滤脚本/流水线
- `F5` 重新扫描 scripts/ 和 pipelines/，更新左侧菜单

## 入口

```python
# main.py
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))

FRONTENDS = {
    "tui": TUIFrontend,
    # "web": WebFrontend,
    # "gui": GUIFrontend,
}

parser = argparse.ArgumentParser()
parser.add_argument("--frontend", default="tui", choices=FRONTENDS.keys())
parser.add_argument("--init-script", help="生成脚本清单模板")
args = parser.parse_args()

core = ToolboxCore("config.yaml")
core.load()

if args.init_script:
    # 不启动前端，只生成模板
    generate_manifest(args.init_script, core)
else:
    frontend = FRONTENDS[args.frontend](core)
    frontend.run()
```

## 配置文件（config.yaml）

```yaml
build:
  project_path: "D:/path/to/android/project"
  gradlew: "gradlew.bat"
  java_home: "C:/path/to/jdk"
  variants: [debug, release]
  flavors: [channel_a, channel_b]

git:
  repos:
    - name: "主项目"
      path: "D:/path/to/repo"
      branch: "main"
    - name: "模块A"
      path: "D:/path/to/module_a"
      branch: "dev"

addr2line:
  tool_path: "addr2line"
  default_so: "D:/path/to/libapp.so"
  so_files:
    - name: "libapp"
      path: "D:/path/to/libapp.so"
    - name: "libnative"
      path: "D:/path/to/libnative.so"

email:
  imap_server: "imap.qq.com"
  imap_port: 993
  account: "xxx@qq.com"
  auth_code: "授权码"
  filter:
    from: ["bug-report@example.com"]
    subject_keywords: ["问题", "bug", "crash"]
  recent_count: 20
```

## 新增工作流流程

1. 编写 Python 脚本，放入 `scripts/` 目录
2. 用 `python run.py xxx --参数名 值` 独立运行测试
3. 运行 `python main.py --init-script scripts/xxx.py` 生成 YAML 清单模板
4. 编辑清单，声明参数、类型、输出字段
5. 如需流水线串联，在 `pipelines/` 下编写 YAML 定义
6. TUI 中按 `F5` 刷新菜单，新功能自动出现（脚本修改无需刷新）
