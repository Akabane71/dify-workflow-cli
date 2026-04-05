"""Chatflow mode templates and creation operations.

Chatflow (advanced-chat) is like Workflow but with multi-turn conversation support.
Key differences from Workflow:
  - Uses Answer nodes instead of End nodes
  - Has conversation_variables for cross-turn persistence
  - system variables: sys.query, sys.conversation_id, sys.dialogue_count
  - LLM nodes can have memory enabled
"""

from __future__ import annotations

from ..editor import add_edge, add_node, add_start_variable
from ..models import AppMode, DifyDSL, NodeType


def create_chatflow(
    name: str = "Chatflow",
    description: str = "",
    *,
    model_provider: str = "openai",
    model_name: str = "gpt-4o",
    system_prompt: str = "You are a helpful assistant.",
) -> DifyDSL:
    """Create a Chatflow with Start → LLM → Answer."""
    dsl = DifyDSL()
    dsl.app.name = name
    dsl.app.mode = AppMode.ADVANCED_CHAT
    dsl.app.description = description

    start = add_node(dsl, NodeType.START, title="Start", node_id="start_node", position=(30, 227))
    add_start_variable(dsl, start.id, "query", label="query")

    llm = add_node(
        dsl, NodeType.LLM, title="LLM", node_id="llm_node", position=(334, 227),
        data_overrides={
            "model": {"provider": model_provider, "name": model_name, "mode": "chat"},
            "prompt_template": [
                {"role": "system", "text": system_prompt},
                {"role": "user", "text": "{{#start_node.query#}}"},
            ],
            "memory": {"enabled": True, "window": {"enabled": True, "size": 50}},
        },
    )

    answer = add_node(
        dsl, NodeType.ANSWER, title="Answer", node_id="answer_node", position=(638, 227),
        data_overrides={"answer": "{{#llm_node.text#}}"},
    )

    add_edge(dsl, start.id, llm.id)
    add_edge(dsl, llm.id, answer.id)
    return dsl


def create_knowledge_chatflow(
    name: str = "Knowledge Chatflow",
    description: str = "",
    *,
    model_provider: str = "openai",
    model_name: str = "gpt-4o",
    system_prompt: str = (
        "You are a helpful assistant.\n"
        "Use the following context to answer questions:\n"
        "<context>\n{{#context#}}\n</context>\n"
        "If you don't know, say so."
    ),
    dataset_ids: list[str] | None = None,
) -> DifyDSL:
    """Create a Chatflow with Start → Knowledge Retrieval → LLM → Answer."""
    dsl = DifyDSL()
    dsl.app.name = name
    dsl.app.mode = AppMode.ADVANCED_CHAT
    dsl.app.description = description

    start = add_node(dsl, NodeType.START, title="Start", node_id="start_node", position=(30, 282))
    add_start_variable(dsl, start.id, "query", label="query")

    kr = add_node(
        dsl, NodeType.KNOWLEDGE_RETRIEVAL, title="Knowledge Retrieval",
        node_id="knowledge_node", position=(334, 282),
        data_overrides={
            "dataset_ids": dataset_ids or [],
            "retrieval_mode": "single",
            "query_variable_selector": ["sys", "query"],
        },
    )

    llm = add_node(
        dsl, NodeType.LLM, title="LLM", node_id="llm_node", position=(638, 282),
        data_overrides={
            "model": {"provider": model_provider, "name": model_name, "mode": "chat"},
            "prompt_template": [
                {"role": "system", "text": system_prompt},
                {"role": "user", "text": "{{#start_node.query#}}"},
            ],
            "memory": {"enabled": True, "window": {"enabled": True, "size": 50}},
            "context": {"enabled": True, "variable_selector": ["knowledge_node", "result"]},
        },
    )

    answer = add_node(
        dsl, NodeType.ANSWER, title="Answer", node_id="answer_node", position=(942, 282),
        data_overrides={"answer": "{{#llm_node.text#}}"},
    )

    add_edge(dsl, start.id, kr.id)
    add_edge(dsl, kr.id, llm.id)
    add_edge(dsl, llm.id, answer.id)
    return dsl
