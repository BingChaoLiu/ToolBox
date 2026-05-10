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
