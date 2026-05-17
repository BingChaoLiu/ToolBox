# CLAUDE.md

ToolBox — Android 开发者工作流自动化 TUI 工具。Textual + Rich。

## Commands

```bash
pytest                  # 测试
pytest tests/test_lib/test_formatter.py -v  # 单文件
python main.py          # 运行 TUI
python main.py --init-script NAME  # 生成脚本模板
python build.py         # 构建 exe
```

## Rules

### Script (`scripts/*.py` + `scripts/*.yaml`)
- 入口: `def main(param1="default", ...)`
- 用户输出用 `print()`，结构化数据用 `return dict`
- 长任务检查 `from lib.cancel import is_cancelled`
- 可导入 `lib/`，禁止依赖 `toolbox/`

### Pipeline (`pipelines/*.yaml`)
- 步骤类型: `script` / `prompt` / `confirm` / `end`
- 引用: `${config:key}` / `${steps.id.field}` / `${choice}`
- 条件: `_safe_eval_condition()` 支持 `== != > >= < <= and or not`

### Config
- **永远不要提交 `config.yaml`**（含凭据，已在 `.gitignore`）
- 凭据读取路径: `lib/launcher_config.py` → config，不硬编码

### Design Constraints
- 单脚本执行：`sys.stdout` 在执行期被替换
- 脚本在 daemon 线程运行，Pipeline 用 `threading.Event` 阻塞等待交互
- 脚本加载用 `importlib.util.spec_from_file_location`，不污染 `sys.path`

### Planning
- 使用 `superpowers:writing-plans` 时，大型项目拆分为多个小 plan，每个 plan 独立可测试

## Key Paths

```
toolbox/core/          # ToolboxCore, Executor, PipelineEngine, Discovery
toolbox/frontend_tui/  # Textual TUI (app.py)
lib/                   # 工具库 (cancel, clipboard, config, process...)
scripts/               # 脚本 .py + .yaml
pipelines/             # 流水线 .yaml
```

## Dependencies

Python 3.10+ | Textual >=3.0 | Rich >=13.0 | PyYAML | psutil | pyperclip | PyInstaller | pytest + pytest-asyncio
