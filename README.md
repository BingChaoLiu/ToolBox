# ToolBox

ToolBox 是一款专为 Android 开发者打造的工作流自动化工具。它集成了脚本执行、资源监控、交互式流水线管理于一体，旨在简化日常重复性开发任务。

## ✨ 特性

- **现代化 TUI 界面**：基于 Textual 开发，支持快捷键操作、全屏视图和执行记录管理。
- **内置资源监控**：实时显示 CPU 和内存占用情况。
- **交互式流水线**：支持 Prompt（输入请求）和 Confirm（确认请求），允许在脚本执行过程中进行人工决策。
- **版本化管理**：内置版本控制逻辑，方便分发和升级。
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

## 📂 项目结构

- `toolbox/`：核心逻辑及前端 UI 代码。
- `lib/`：通用工具类（日志、路径处理等）。
- `scripts/`：内置脚本库。
- `pipelines/`：流水线配置定义。
- `build.py`：打包脚本。
- `main.py`：程序入口。

## 📝 许可证

[MIT License](LICENSE)
