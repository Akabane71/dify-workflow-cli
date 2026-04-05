"""Chatflow-specific validation rules."""

from __future__ import annotations

from ..models import DifyDSL, NodeType


def validate_chatflow_mode(dsl: DifyDSL, result) -> None:
    """Validate chatflow-specific rules (on top of workflow graph validation)."""
    graph = dsl.workflow.graph
    if not graph.nodes:
        return

    node_types = {n.data.type for n in graph.nodes}

    # Chatflow should use Answer nodes, not End nodes
    if NodeType.ANSWER not in node_types:
        result.add_warning("Chatflow should have at least one Answer node (not End)")

    if NodeType.END in node_types:
        result.add_warning(
            "Chatflow uses Answer nodes for output, not End nodes. "
            "End nodes are for Workflow mode."
        )

    # Check that LLM nodes have memory enabled (recommended for chatflow)
    for node in graph.nodes:
        if node.data.type == NodeType.LLM:
            memory = node.data.memory
            if memory is None or not getattr(memory, "enabled", False):
                extra = node.data.__pydantic_extra__ or {}
                mem_dict = extra.get("memory", {})
                if not isinstance(mem_dict, dict) or not mem_dict.get("enabled"):
                    result.add_warning(
                        "LLM node in Chatflow should have memory enabled for conversation context",
                        node_id=node.id,
                    )
