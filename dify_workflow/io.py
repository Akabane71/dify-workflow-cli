"""Dify DSL I/O: load and save Dify DSL files (YAML/JSON) for all app modes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .models import DifyDSL, DifyWorkflowDSL  # noqa: F401 (DifyWorkflowDSL for compat)


def _clean_export_data(dsl: DifyDSL, data: dict[str, Any]) -> dict[str, Any]:
    """Remove irrelevant sections based on app mode."""
    if dsl.is_config_based:
        # Config-based apps (chat/agent/completion) don't have workflow graphs
        wf = data.get("workflow", {})
        if not wf.get("graph", {}).get("nodes"):
            data.pop("workflow", None)
    elif dsl.is_workflow_based:
        # Workflow-based apps don't have model_config
        data.pop("model_config", None)
    return data


def load_workflow(path: str | Path) -> DifyDSL:
    """Load a workflow DSL from a YAML or JSON file."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Workflow file not found: {p}")

    raw = p.read_text(encoding="utf-8")

    if p.suffix in (".yaml", ".yml"):
        data = yaml.safe_load(raw)
    elif p.suffix == ".json":
        data = json.loads(raw)
    else:
        # Try YAML first, then JSON
        try:
            data = yaml.safe_load(raw)
        except yaml.YAMLError:
            data = json.loads(raw)

    if not isinstance(data, dict):
        raise ValueError(f"Invalid workflow file: expected a mapping, got {type(data).__name__}")

    return DifyDSL.model_validate(data)


def save_workflow(dsl: DifyDSL, path: str | Path, *, fmt: str | None = None) -> Path:
    """Save a workflow DSL to a file.

    Args:
        dsl: The workflow DSL object.
        path: Output file path.
        fmt: Force format ("yaml" or "json"). Auto-detected from extension if None.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    data = dsl.model_dump(mode="json", exclude_none=True, by_alias=True)
    data = _clean_export_data(dsl, data)

    if fmt is None:
        fmt = "json" if p.suffix == ".json" else "yaml"

    if fmt == "json":
        content = json.dumps(data, indent=2, ensure_ascii=False)
    else:
        content = yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)

    p.write_text(content, encoding="utf-8")
    return p


def load_workflow_from_string(content: str, *, fmt: str = "yaml") -> DifyDSL:
    """Load a workflow DSL from a string."""
    if fmt == "json":
        data = json.loads(content)
    else:
        data = yaml.safe_load(content)

    if not isinstance(data, dict):
        raise ValueError(f"Invalid workflow content: expected a mapping, got {type(data).__name__}")

    return DifyDSL.model_validate(data)


def workflow_to_string(dsl: DifyDSL, *, fmt: str = "yaml") -> str:
    """Serialize a workflow DSL to a string."""
    data = dsl.model_dump(mode="json", exclude_none=True, by_alias=True)
    data = _clean_export_data(dsl, data)
    if fmt == "json":
        return json.dumps(data, indent=2, ensure_ascii=False)
    return yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge override into base, returning base."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base
