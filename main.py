import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from toolbox.core import ToolboxCore
from toolbox.core.discovery import generate_manifest
from toolbox.frontend_tui.app import TUIFrontend

FRONTENDS = {
    "tui": TUIFrontend,
}


def cmd_init_script(script_path_str: str, core: ToolboxCore):
    script_path = pathlib.Path(script_path_str)
    if not script_path.exists():
        alt = pathlib.Path(__file__).parent / "scripts" / (script_path_str.replace(".py", "") + ".py")
        if alt.exists():
            script_path = alt
        else:
            print(f"脚本不存在: {script_path_str}")
            sys.exit(1)

    manifest_yaml = generate_manifest(script_path)
    manifest_path = script_path.with_suffix(".yaml")

    if manifest_path.exists():
        print(f"清单文件已存在: {manifest_path}")
        print("如要覆盖，请先删除已有文件")
        sys.exit(1)

    manifest_path.write_text(manifest_yaml, encoding="utf-8")
    print(f"已生成清单模板: {manifest_path}")
    print("请编辑清单，补充参数类型、剪贴板、输出字段等信息。")


def main():
    parser = argparse.ArgumentParser(description="ToolBox — Android 开发工作流自动化工具")
    parser.add_argument(
        "--frontend", default="tui",
        choices=FRONTENDS.keys(),
        help="前端类型 (默认: tui)",
    )
    parser.add_argument(
        "--init-script",
        metavar="SCRIPT_PATH",
        help="生成脚本清单 YAML 模板，不启动 TUI",
    )
    args = parser.parse_args()

    config_path = pathlib.Path(__file__).parent / "config.yaml"
    core = ToolboxCore(str(config_path))

    if args.init_script:
        try:
            core.load()
        except FileNotFoundError:
            pass
        cmd_init_script(args.init_script, core)
    else:
        core.load()
        frontend = FRONTENDS[args.frontend](core)
        frontend.run()


if __name__ == "__main__":
    main()
