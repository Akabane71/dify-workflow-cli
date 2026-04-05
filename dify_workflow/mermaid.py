"""Generate Mermaid flowchart from a Dify workflow DSL.

Produces standard Mermaid ``flowchart TD`` syntax where:
  - Each node shows ``title (type)`` as its label
  - Branching edges (IF/ELSE case_id, Question Classifier class id) are
    annotated with the sourceHandle value
  - Node shapes follow Mermaid conventions:
    start/trigger → stadium ``([...])``
    end → double-circle ``((...))``
    if-else → rhombus ``{...}``
    other → rectangle ``["..."]``
"""

from __future__ import annotations

from .models import DifyDSL, NodeType


# Node types that use stadium shape (rounded)
_STADIUM_TYPES = frozenset({
    NodeType.START,
    NodeType.TRIGGER_WEBHOOK,
    NodeType.TRIGGER_SCHEDULE,
    NodeType.TRIGGER_PLUGIN,
    NodeType.DATASOURCE,
})

# Node types that use rhombus shape (diamond)
_DIAMOND_TYPES = frozenset({
    NodeType.IF_ELSE,
})

# Node types that use double-circle shape (terminal)
_TERMINAL_TYPES = frozenset({
    NodeType.END,
})

# sourceHandle values that are plain "source" → no label needed
_DEFAULT_HANDLES = frozenset({"source", "target", ""})


def _escape_label(text: str) -> str:
    """Escape characters that break Mermaid syntax inside labels."""
    return text.replace('"', "'").replace("\n", " ")


def _node_label(title: str, node_type: str) -> str:
    """Build the display label: ``title (type)``."""
    return _escape_label(f"{title} ({node_type})")


def _node_shape(node_id: str, label: str, node_type: NodeType) -> str:
    """Return the Mermaid node definition with appropriate shape."""
    if node_type in _STADIUM_TYPES:
        return f'    {node_id}(["{label}"])'
    if node_type in _DIAMOND_TYPES:
        return f'    {node_id}{{"{label}"}}'
    if node_type in _TERMINAL_TYPES:
        return f'    {node_id}(("{label}"))'
    return f'    {node_id}["{label}"]'


def generate_mermaid(dsl: DifyDSL) -> str:
    """Generate a Mermaid flowchart string from a workflow DSL.

    Returns a complete ``flowchart TD`` block that can be pasted into
    any Markdown renderer that supports Mermaid.
    """
    if not dsl.is_workflow_based:
        return "flowchart TD\n    note[\"Not a workflow/chatflow app — no graph to render\"]"

    graph = dsl.workflow.graph
    lines: list[str] = ["flowchart TD"]

    # Build node ID → type lookup
    node_type_map: dict[str, NodeType] = {}
    for node in graph.nodes:
        node_type_map[node.id] = node.data.type

    # Emit node definitions
    for node in graph.nodes:
        label = _node_label(node.data.title, node.data.type.value)
        lines.append(_node_shape(node.id, label, node.data.type))

    # Emit edges
    for edge in graph.edges:
        handle = edge.sourceHandle
        if handle and handle not in _DEFAULT_HANDLES:
            edge_label = _escape_label(handle)
            lines.append(f"    {edge.source} -->|{edge_label}| {edge.target}")
        else:
            lines.append(f"    {edge.source} --> {edge.target}")

    return "\n".join(lines)
