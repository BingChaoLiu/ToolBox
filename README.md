# ToolBox

ToolBox 是一款专为 Android 开发者打造的工作流自动化工具。它集成了脚本执行、资源监控、交互式流水线管理于一体，旨在简化日常重复性开发任务。

## ✨ 特性

- **现代化 TUI 界面**：基于 Textual 开发，支持快捷键操作、全屏视图、执行记录管理和脚本搜索过滤。
- **内置资源监控**：实时显示 CPU 和内存占用情况。
- **交互式流水线**：支持 Prompt（选项输入）、Confirm（确认请求）和条件步骤（`if`），允许在脚本执行过程中进行人工决策和分支控制。
- **渐进式脚本集成**：丢进去就能跑 → 加清单有参数 → 接管道可串联，三层渐进。
- **声明式配置**：YAML 清单描述脚本接口，YAML 文件描述流水线，支持 `${}` 变量引用和类型保持。
- **一键打包**：提供自动化打包脚本，可生成独立运行的可执行文件（无需 Python 环境）。

## 🚀 快速开始

### 环境要求

- Python 3.10+
- 已安装 `pip`

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行程序

```bash
python main.py
```

### 独立运行脚本

```bash
python run.py <脚本名> --参数名 值
```

### 生成脚本清单

```bash
python main.py --init-script scripts/my_script.py
```

## 📦 打包分发

项目支持使用 PyInstaller 打包为独立的可执行文件（Windows/Linux/macOS）。

```bash
python build.py
```

打包后的文件位于 `dist/ToolBox/` 目录下。

## 🛠️ 配置说明

1. 复制 `config.example.yaml` 为 `config.yaml`。
2. 根据你的环境修改 `config.yaml` 中的配置项。
3. 如果需要增加自定义脚本，将其放置在 `scripts/` 目录下并提供对应的 `.yaml` 清单文件。

配置项包括：Android 构建设置、Git 仓库管理、Native 崩溃分析（addr2line）、邮件集成、Launcher 模块组管理等。

## ⌨️ 快捷键

| 快捷键 | 功能 |
|--------|------|
| `F5` | 刷新菜单 |
| `F9` | 执行当前任务 |
| `F11` | 切换全屏视图 |
| `F12` | 展开/隐藏历史记录 |
| `/` | 搜索脚本/流水线 |
| `Ctrl+S` | 导出当前日志 |
| `Ctrl+C` | 中止任务 |

## 📂 项目结构

- `toolbox/`：核心逻辑及前端 UI 代码。
- `lib/`：通用工具类（日志、路径处理、Git 操作、剪贴板等）。
- `scripts/`：内置脚本库（含 YAML 清单）。
- `pipelines/`：流水线配置定义。
- `tests/`：测试套件。
- `build.py`：打包脚本。
- `main.py`：程序入口。
- `run.py`：脚本独立运行器。

## 📝 许可证

[MIT License](LICENSE)
