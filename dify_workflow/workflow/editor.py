"""Workflow mode templates and creation operations."""

from __future__ import annotations

from typing import Any

from ..editor import add_edge, add_end_output, add_node, add_start_variable
from ..models import AppMode, DifyDSL, NodeType


def create_minimal_workflow(
    name: str = "Untitled Workflow",
    description: str = "",
    *,
    input_variables: list[dict[str, Any]] | None = None,
) -> DifyDSL:
    """Create a minimal workflow with Start → End nodes."""
    dsl = DifyDSL()
    dsl.app.name = name
    dsl.app.mode = AppMode.WORKFLOW
    dsl.app.description = description

    start = add_node(dsl, NodeType.START, title="Start", node_id="start_node", position=(30, 227))
    end = add_node(dsl, NodeType.END, title="End", node_id="end_node", position=(334, 227))

    if input_variables:
        for var in input_variables:
            add_start_variable(dsl, start.id, **var)
    else:
        add_start_variable(dsl, start.id, "query", label="query")

    add_end_output(dsl, end.id, "result", [start.id, "query"])
    add_edge(dsl, start.id, end.id)
    return dsl


def create_llm_workflow(
    name: str = "LLM Workflow",
    description: str = "",
    *,
    model_provider: str = "openai",
    model_name: str = "gpt-3.5-turbo",
    system_prompt: str = "You are a helpful assistant.",
    user_prompt: str = "{{#start_node.query#}}",
) -> DifyDSL:
    """Create a workflow with Start → LLM → End."""
    dsl = DifyDSL()
    dsl.app.name = name
    dsl.app.mode = AppMode.WORKFLOW
    dsl.app.description = description

    start = add_node(dsl, NodeType.START, title="Start", node_id="start_node", position=(30, 227))
    add_start_variable(dsl, start.id, "query", label="query")

    llm = add_node(
        dsl, NodeType.LLM, title="LLM", node_id="llm_node", position=(334, 227),
        data_overrides={
            "model": {"provider": model_provider, "name": model_name, "mode": "chat"},
            "prompt_template": [
                {"role": "system", "text": system_prompt},
                {"role": "user", "text": user_prompt},
            ],
        },
    )

    end = add_node(dsl, NodeType.END, title="End", node_id="end_node", position=(638, 227))
    add_end_output(dsl, end.id, "answer", [llm.id, "text"])

    add_edge(dsl, start.id, llm.id)
    add_edge(dsl, llm.id, end.id)
    return dsl


def create_ifelse_workflow(
    name: str = "IF/ELSE Workflow",
    description: str = "",
) -> DifyDSL:
    """Create a workflow with Start → IF/ELSE → End True / End False."""
    dsl = DifyDSL()
    dsl.app.name = name
    dsl.app.mode = AppMode.WORKFLOW
    dsl.app.description = description

    start = add_node(dsl, NodeType.START, title="Start", node_id="start_node", position=(30, 263))
    add_start_variable(dsl, start.id, "query", label="query")

    ifelse = add_node(
        dsl, NodeType.IF_ELSE, title="IF/ELSE", node_id="ifelse_node", position=(364, 263),
        data_overrides={
            "cases": [{
                "id": "true", "case_id": "true", "logical_operator": "and",
                "conditions": [{
                    "id": "cond1", "comparison_operator": "contains",
                    "value": "hello", "varType": "string",
                    "variable_selector": ["start_node", "query"],
                }],
            }],
        },
    )

    end_true = add_node(dsl, NodeType.END, title="End True", node_id="end_true", position=(766, 161))
    add_end_output(dsl, end_true.id, "true", ["start_node", "query"])

    end_false = add_node(dsl, NodeType.END, title="End False", node_id="end_false", position=(766, 363))
    add_end_output(dsl, end_false.id, "false", ["start_node", "query"])

    add_edge(dsl, start.id, ifelse.id)
    add_edge(dsl, ifelse.id, end_true.id, source_handle="true")
    add_edge(dsl, ifelse.id, end_false.id, source_handle="false")

    return dsl
