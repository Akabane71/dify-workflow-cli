"""Workflow editing operations: add/remove/update nodes and edges.

Also re-exports workflow template creators for backward compatibility.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from .models import (
    DifyDSL,
    DifyWorkflowDSL,
    Edge,
    EdgeData,
    Node,
    NodeData,
    NodeType,
    OutputVariable,
    Position,
    StartVariable,
)


def _next_id() -> str:
    return str(int(time.time() * 1000))


def _auto_layout_x(dsl: DifyDSL) -> float:
    """Return the next X position for a new node."""
    if not dsl.workflow.graph.nodes:
        return 30.0
    max_x = max(n.position.x for n in dsl.workflow.graph.nodes)
    return max_x + 304.0


# --- Node operations ---

def add_node(
    dsl: DifyDSL,
    node_type: NodeType | str,
    *,
    title: str = "",
    node_id: str | None = None,
    position: tuple[float, float] | None = None,
    data_overrides: dict[str, Any] | None = None,
) -> Node:
    """Add a new node to the workflow graph."""
    node_type = NodeType(node_type)
    if not title:
        title = node_type.value.replace("-", " ").title()

    nid = node_id or _next_id()
    pos = Position(x=position[0], y=position[1]) if position else Position(x=_auto_layout_x(dsl), y=227.0)

    node_data_dict: dict[str, Any] = {"type": node_type, "title": title, "desc": ""}
    _code_output_extras: dict[str, Any] | None = None  # Code node outputs (dict format)

    # Set type-specific defaults
    if node_type == NodeType.START:
        node_data_dict["variables"] = []
    elif node_type == NodeType.END:
        node_data_dict["outputs"] = []
    elif node_type == NodeType.LLM:
        node_data_dict.update({
            "model": {"provider": "", "name": "", "mode": "chat",
                      "completion_params": {"temperature": 0.7}},
            "prompt_template": [{"role": "system", "text": ""}],
            "vision": {"enabled": False, "configs": {"variable_selector": []}},
            "memory": {"enabled": False, "window": {"enabled": False, "size": 50}},
            "context": {"enabled": False, "variable_selector": []},
            "structured_output": {"enabled": False},
            "retry_config": {
                "enabled": False, "max_retries": 1, "retry_interval": 1000,
                "exponential_backoff": {"enabled": False, "multiplier": 2, "max_interval": 10000},
            },
        })
    elif node_type == NodeType.CODE:
        # Code node variables go through the typed field (StartVariable has value_selector).
        # Code node outputs use dict format — stored as extras after model construction.
        node_data_dict.update({
            "code_language": "python3",
            "code": 'def main(arg1: str, arg2: str) -> dict:\n    return {\n        "result": arg1 + arg2,\n    }',
            "variables": [
                {"variable": "arg1", "value_selector": []},
                {"variable": "arg2", "value_selector": []},
            ],
        })
        _code_output_extras = {
            "result": {"type": "string", "children": None},
        }
    elif node_type == NodeType.IF_ELSE:
        node_data_dict["cases"] = [
            {"case_id": "true", "logical_operator": "and", "conditions": []},
        ]
    elif node_type == NodeType.TEMPLATE_TRANSFORM:
        node_data_dict["template"] = ""
    elif node_type == NodeType.HTTP_REQUEST:
        node_data_dict.update({
            "url": "",
            "method": "get",
            "headers": "",
            "params": "",
            "body": {"type": "none", "data": []},
            "authorization": {"type": "no-auth", "config": None},
            "timeout": {
                "max_connect_timeout": 0,
                "max_read_timeout": 0,
                "max_write_timeout": 0,
            },
            "ssl_verify": True,
            "retry_config": {
                "retry_enabled": True,
                "max_retries": 3,
                "retry_interval": 100,
            },
        })
    elif node_type == NodeType.KNOWLEDGE_RETRIEVAL:
        node_data_dict.update({"dataset_ids": [], "retrieval_model": {}, "query_variable_selector": []})
    elif node_type == NodeType.TOOL:
        node_data_dict.update({"provider_id": "", "provider_type": "builtin", "tool_name": "", "tool_parameters": {}, "tool_configurations": {}})
    elif node_type == NodeType.ANSWER:
        node_data_dict.update({"answer": "", "variables": []})
    elif node_type == NodeType.QUESTION_CLASSIFIER:
        node_data_dict.update({
            "query_variable_selector": [],
            "model": {"provider": "", "name": "", "mode": "chat",
                      "completion_params": {"temperature": 0.7}},
            "classes": [{"id": "1", "name": ""}, {"id": "2", "name": ""}],
            "instruction": "",
            "vision": {"enabled": False},
        })
    elif node_type == NodeType.PARAMETER_EXTRACTOR:
        node_data_dict.update({
            "model": {"provider": "", "name": "", "mode": "chat",
                      "completion_params": {"temperature": 0.7}},
            "query": [],
            "parameters": [],
            "reasoning_mode": "prompt",
            "instruction": "",
            "vision": {"enabled": False},
        })
    elif node_type == NodeType.VARIABLE_AGGREGATOR:
        node_data_dict.update({"output_type": "string", "variables": []})
    elif node_type == NodeType.VARIABLE_ASSIGNER:
        node_data_dict.update({"version": "2", "items": []})
    elif node_type == NodeType.LIST_OPERATOR:
        node_data_dict.update({
            "variable": [],
            "filter_by": {"enabled": False, "conditions": []},
            "extract_by": {"enabled": False, "serial": "1"},
            "order_by": {"enabled": False, "key": "", "value": "asc"},
            "limit": {"enabled": False, "size": 10},
        })
    elif node_type == NodeType.ITERATION:
        node_data_dict.update({
            "iterator_selector": [],
            "output_selector": [],
            "output_type": "array[string]",
            "is_parallel": False,
            "parallel_nums": 10,
            "error_handle_mode": "terminated",
            "flatten_output": False,
        })
    elif node_type == NodeType.LOOP:
        node_data_dict.update({
            "loop_count": 10,
            "logical_operator": "and",
            "break_conditions": [],
            "loop_variables": [],
            "error_handle_mode": "terminated",
        })
    elif node_type == NodeType.AGENT:
        node_data_dict.update({
            "agent_strategy_provider_name": "",
            "agent_strategy_name": "",
            "agent_strategy_label": "",
            "agent_parameters": {},
        })
    elif node_type == NodeType.DOCUMENT_EXTRACTOR:
        node_data_dict.update({"variable_selector": [], "is_array_file": False})
    elif node_type == NodeType.HUMAN_INPUT:
        node_data_dict.update({
            "form_content": "",
            "inputs": [],
            "user_actions": [],
            "delivery_methods": [
                {
                    "id": str(uuid.uuid4()),
                    "type": "webapp",
                    "enabled": True,
                    "config": {},
                },
            ],
            "timeout": 24,
            "timeout_unit": "hour",
        })
    elif node_type == NodeType.KNOWLEDGE_INDEX:
        node_data_dict.update({
            "chunk_structure": "text_model",
            "index_chunk_variable_selector": [],
            "indexing_technique": "high_quality",
        })
    elif node_type == NodeType.DATASOURCE:
        node_data_dict.update({
            "plugin_id": "",
            "provider_name": "",
            "provider_type": "local_file",
            "datasource_parameters": {},
        })
    elif node_type == NodeType.TRIGGER_WEBHOOK:
        node_data_dict.update({
            "method": "get",
            "content_type": "application/json",
            "params": [],
        })
    elif node_type == NodeType.TRIGGER_SCHEDULE:
        node_data_dict.update({
            "mode": "visual",
            "frequency": "daily",
            "timezone": "UTC",
        })
    elif node_type == NodeType.TRIGGER_PLUGIN:
        node_data_dict.update({
            "plugin_id": "",
            "provider_id": "",
            "event_name": "",
            "event_parameters": {},
        })

    if data_overrides:
        node_data_dict.update(data_overrides)

    # For code nodes, extract outputs (dict format) that conflict with typed field
    if node_type == NodeType.CODE:
        if "outputs" in node_data_dict and isinstance(node_data_dict["outputs"], dict):
            _code_output_extras = node_data_dict.pop("outputs")

    node_data = NodeData.model_validate(node_data_dict)

    # Apply code-specific extras (outputs in dict format)
    if _code_output_extras is not None:
        if node_data.__pydantic_extra__ is None:
            node_data.__pydantic_extra__ = {}
        node_data.__pydantic_extra__["outputs"] = _code_output_extras

    node = Node(id=nid, data=node_data, position=pos, positionAbsolute=pos)

    dsl.workflow.graph.nodes.append(node)
    return node


def remove_node(dsl: DifyDSL, node_id: str) -> bool:
    """Remove a node and all its connected edges."""
    original_count = len(dsl.workflow.graph.nodes)
    dsl.workflow.graph.nodes = [n for n in dsl.workflow.graph.nodes if n.id != node_id]
    removed = len(dsl.workflow.graph.nodes) < original_count

    if removed:
        dsl.workflow.graph.edges = [
            e for e in dsl.workflow.graph.edges
            if e.source != node_id and e.target != node_id
        ]
    return removed


def get_node(dsl: DifyDSL, node_id: str) -> Node | None:
    """Find a node by ID."""
    for n in dsl.workflow.graph.nodes:
        if n.id == node_id:
            return n
    return None


def update_node(dsl: DifyDSL, node_id: str, updates: dict[str, Any]) -> Node | None:
    """Update a node's data fields."""
    node = get_node(dsl, node_id)
    if node is None:
        return None

    merged = node.data.model_dump(mode="python", exclude_none=False)
    merged.update(updates)

    # Code nodes store outputs in extras (dict format vs End node's list format)
    code_output_extras: dict[str, Any] | None = None
    if node.data.type == NodeType.CODE and "outputs" in merged and isinstance(merged["outputs"], dict):
        code_output_extras = merged.pop("outputs")

    node.data = NodeData.model_validate(merged)

    if code_output_extras is not None:
        if node.data.__pydantic_extra__ is None:
            node.data.__pydantic_extra__ = {}
        node.data.__pydantic_extra__["outputs"] = code_output_extras

    return node


def set_node_title(dsl: DifyDSL, node_id: str, title: str) -> bool:
    node = get_node(dsl, node_id)
    if node is None:
        return False
    node.data.title = title
    return True


def add_start_variable(
    dsl: DifyDSL,
    node_id: str,
    variable: str,
    *,
    label: str = "",
    var_type: str = "text-input",
    required: bool = True,
    max_length: int | None = None,
    options: list[str] | None = None,
) -> bool:
    """Add a variable to a start node."""
    node = get_node(dsl, node_id)
    if node is None or node.data.type != NodeType.START:
        return False
    if node.data.variables is None:
        node.data.variables = []

    sv = StartVariable(
        variable=variable,
        label=label or variable,
        type=var_type,
        required=required,
        max_length=max_length,
        options=options or [],
    )
    node.data.variables.append(sv)
    return True


def add_end_output(
    dsl: DifyDSL,
    node_id: str,
    variable: str,
    value_selector: list[str],
    *,
    value_type: str = "string",
) -> bool:
    """Add an output to an end node."""
    node = get_node(dsl, node_id)
    if node is None or node.data.type != NodeType.END:
        return False
    if node.data.outputs is None:
        node.data.outputs = []

    ov = OutputVariable(variable=variable, value_selector=value_selector, value_type=value_type)
    node.data.outputs.append(ov)
    return True


# --- Edge operations ---

def add_edge(
    dsl: DifyDSL,
    source_id: str,
    target_id: str,
    *,
    source_handle: str = "source",
    target_handle: str = "target",
    edge_id: str | None = None,
) -> Edge | None:
    """Add an edge connecting two nodes."""
    source_node = get_node(dsl, source_id)
    target_node = get_node(dsl, target_id)
    if source_node is None or target_node is None:
        return None

    eid = edge_id or f"{source_id}-{source_handle}-{target_id}-{target_handle}"
    edge_data = EdgeData(
        sourceType=source_node.data.type.value,
        targetType=target_node.data.type.value,
    )
    edge = Edge(
        id=eid,
        source=source_id,
        target=target_id,
        sourceHandle=source_handle,
        targetHandle=target_handle,
        data=edge_data,
    )
    dsl.workflow.graph.edges.append(edge)
    return edge


def remove_edge(dsl: DifyDSL, edge_id: str) -> bool:
    """Remove an edge by ID."""
    original = len(dsl.workflow.graph.edges)
    dsl.workflow.graph.edges = [e for e in dsl.workflow.graph.edges if e.id != edge_id]
    return len(dsl.workflow.graph.edges) < original


def get_edges_for_node(dsl: DifyDSL, node_id: str) -> list[Edge]:
    """Get all edges connected to a node."""
    return [e for e in dsl.workflow.graph.edges if e.source == node_id or e.target == node_id]


# --- Backward compatibility: lazy re-exports from workflow submodule ---
_COMPAT_NAMES = {
    "create_minimal_workflow": "workflow.editor",
    "create_llm_workflow": "workflow.editor",
    "create_ifelse_workflow": "workflow.editor",
}


def __getattr__(name: str):
    if name in _COMPAT_NAMES:
        import importlib
        mod = importlib.import_module(f".{_COMPAT_NAMES[name]}", package="dify_workflow")
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
