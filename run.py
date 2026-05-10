import argparse
import importlib.util
import inspect
import pathlib
import sys

ROOT = pathlib.Path(__file__).parent
sys.path.insert(0, str(ROOT))


def main():
    if len(sys.argv) < 2:
        print("用法: python run.py <脚本名> [--参数名 值] ...")
        print("示例: python run.py git_check --repo_name 主项目")
        sys.exit(1)

    script_name = sys.argv[1].replace(".py", "")
    script_path = ROOT / "scripts" / (script_name + ".py")

    if not script_path.exists():
        print(f"脚本不存在: {script_path}")
        sys.exit(1)

    spec = importlib.util.spec_from_file_location(
        f"toolbox_script_{script_path.stem}", script_path
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    if not hasattr(mod, "main"):
        print(f"脚本 '{script_name}' 没有 main() 函数")
        sys.exit(1)

    parser = argparse.ArgumentParser(description=f"运行 {script_name}")
    sig = inspect.signature(mod.main)
    for name, param in sig.parameters.items():
        parser.add_argument(f"--{name}", default=param.default)

    args = parser.parse_args(sys.argv[2:])
    result = mod.main(**vars(args))
    if result:
        print(result)


if __name__ == "__main__":
    main()
