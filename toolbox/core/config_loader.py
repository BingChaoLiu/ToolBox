from __future__ import annotations

import re
from pathlib import Path

import yaml

_REF_PATTERN = re.compile(r"\$\{([^}]+)\}")


def load_config(config_path: str) -> dict:
    p = Path(config_path)
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(p, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return _resolve_all_references(raw, set())


def _resolve_all_references(root: dict, resolving: set) -> dict:
    max_iterations = 10
    iteration = 0
    changed = True
    while changed and iteration < max_iterations:
        changed, root = _resolve_pass(root, root, resolving)
        iteration += 1
    if _has_unresolved_refs(root):
        raise ValueError("circular reference detected in config")
    return root


def _has_unresolved_refs(data) -> bool:
    if isinstance(data, str):
        return bool(_REF_PATTERN.search(data))
    if isinstance(data, dict):
        return any(_has_unresolved_refs(v) for v in data.values())
    if isinstance(data, list):
        return any(_has_unresolved_refs(item) for item in data)
    return False


def _resolve_pass(data, root: dict, resolving: set) -> tuple[bool, any]:
    changed = False
    if isinstance(data, dict):
        new = {}
        for k, v in data.items():
            did_change, new_v = _resolve_pass(v, root, resolving)
            changed = changed or did_change
            new[k] = new_v
        return changed, new
    if isinstance(data, list):
        new_list = []
        for item in data:
            did_change, new_item = _resolve_pass(item, root, resolving)
            changed = changed or did_change
            new_list.append(new_item)
        return changed, new_list
    if isinstance(data, str):
        return _resolve_ref_in_string(data, root, resolving)
    return False, data


def _resolve_ref_in_string(value: str, root: dict, resolving: set) -> tuple[bool, str]:
    matches = list(_REF_PATTERN.finditer(value))
    if not matches:
        return False, value

    result = value
    did_change = False
    for match in reversed(matches):
        ref_path = match.group(1)
        try:
            resolved = _get_by_dot_path(root, ref_path)
        except (KeyError, TypeError):
            continue
        if resolved is None:
            continue
        if isinstance(resolved, str) and "${" in resolved:
            continue  # not yet resolved, skip this pass
        result = result[:match.start()] + str(resolved) + result[match.end():]
        did_change = True
    return did_change, result


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
    if ref_content.startswith("steps."):
        dot_path = ref_content[len("steps."):]
        parts = dot_path.split(".", 1)
        if len(parts) == 2:
            step_id, field = parts
            step_data = context.get(step_id, {})
            return step_data.get(field)
    if ref_content.startswith("config:"):
        dot_path = ref_content[len("config:"):]
        return _get_by_dot_path(context, dot_path)
    if ref_content == "choice":
        return "${choice}"
    return "${" + ref_content + "}"


def _get_by_dot_path(data, dot_path: str):
    keys = dot_path.split(".")
    value = data
    for key in keys:
        if isinstance(value, dict):
            value = value[key]
        else:
            raise KeyError(f"Cannot resolve key '{key}' in path '{dot_path}'")
    return value
