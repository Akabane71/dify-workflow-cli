"""Workflow-specific validation rules."""

from __future__ import annotations

from ..models import AppMode, DifyDSL, NodeType
from ..node_data_validator import validate_node_data
from ..frontend_validator import validate_frontend_compat
from ..checklist_validator import validate_checklist

TRIGGER_NODE_TYPES = frozenset({
    NodeType.TRIGGER_WEBHOOK,
    NodeType.TRIGGER_SCHEDULE,
    NodeType.TRIGGER_PLUGIN,
})

START_NODE_TYPES = frozenset({
    NodeType.START,
    NodeType.DATASOURCE,
    *TRIGGER_NODE_TYPES,
})


def validate_workflow_mode(dsl: DifyDSL, result) -> None:
    """Validate workflow-specific rules (graph structure, nodes, edges, connectivity)."""
    graph = dsl.workflow.graph
    if not graph.nodes:
        result.add_error("Workflow has no nodes")
        return

    node_types = {n.data.type for n in graph.nodes}
    node_ids = [n.id for n in graph.nodes]

    # Duplicate IDs
    seen: set[str] = set()
    for nid in node_ids:
        if nid in seen:
            result.add_error(f"Duplicate node ID: {nid}", node_id=nid)
        seen.add(nid)

    # Start node check
    start_types = node_types & START_NODE_TYPES
    if not start_types:
        result.add_error("Workflow must have a start node (start, datasource, or trigger)")

    start_nodes = [n for n in graph.nodes if n.data.type in START_NODE_TYPES]
    if len(start_nodes) > 1:
        result.add_warning("Workflow has multiple start-type nodes")

    # Start + trigger conflict
    if NodeType.START in node_types:
        trigger_types = node_types & TRIGGER_NODE_TYPES
        if trigger_types:
            result.add_error("Start node and trigger nodes cannot coexist in the same workflow")

    # End/answer node check
    if dsl.app.mode == AppMode.WORKFLOW:
        if NodeType.END not in node_types and NodeType.ANSWER not in node_types:
            result.add_warning("Workflow has no end or answer node")

    # Node-level validation
    _validate_nodes(dsl, result)
    # Edge validation
    _validate_edges(dsl, result)
    # Connectivity
    _validate_connectivity(dsl, result)
    # Pre-publish checklist (variable references, node config completeness)
    _validate_checklist(dsl, result)


def _validate_nodes(dsl: DifyDSL, result) -> None:
    for node in dsl.workflow.graph.nodes:
        nd = node.data
        nid = node.id

        if not nd.title:
            result.add_warning("Node has no title", node_id=nid)

        # Per-node-type data validation (mirrors Dify's official schemas)
        node_errors = validate_node_data(node)
        for err in node_errors:
            if err.level == "error":
                result.add_error(err.message, node_id=err.node_id, field_name=err.field)
            else:
                result.add_warning(err.message, node_id=err.node_id, field_name=err.field)

        # Frontend crash prevention validation
        fe_errors = validate_frontend_compat(node)
        for err in fe_errors:
            if err.level == "error":
                result.add_error(err.message, node_id=err.node_id, field_name=err.field)
            else:
                result.add_warning(err.message, node_id=err.node_id, field_name=err.field)


def _validate_edges(dsl: DifyDSL, result) -> None:
    node_ids = {n.id for n in dsl.workflow.graph.nodes}
    edge_ids: set[str] = set()

    for edge in dsl.workflow.graph.edges:
        if edge.id in edge_ids:
            result.add_warning(f"Duplicate edge ID: {edge.id}")
        edge_ids.add(edge.id)

        if edge.source not in node_ids:
            result.add_error(f"Edge references nonexistent source node: {edge.source}")
        if edge.target not in node_ids:
            result.add_error(f"Edge references nonexistent target node: {edge.target}")
        if edge.source == edge.target:
            result.add_error(f"Self-loop edge detected: {edge.id}")

    # Cycle detection — Dify's frontend filters out all edges between cycle
    # nodes (getCycleEdges in workflow-init.ts), which causes nodes to appear
    # disconnected after import.  Detect and report cycles as errors.
    _detect_cycles(dsl, result)


def _detect_cycles(dsl: DifyDSL, result) -> None:
    """Detect graph cycles — mirrors Dify frontend getCycleEdges().

    Dify's frontend removes ALL edges between nodes on the DFS cycle path,
    which causes nodes to appear disconnected after import.
    """
    graph = dsl.workflow.graph
    adj: dict[str, list[str]] = {n.id: [] for n in graph.nodes}
    for edge in graph.edges:
        if edge.source in adj:
            adj[edge.source].append(edge.target)

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {n.id: WHITE for n in graph.nodes}
    back_edges: list[tuple[str, str]] = []

    def _dfs(node_id: str) -> None:
        color[node_id] = GRAY
        for neighbor in adj[node_id]:
            if color.get(neighbor) == GRAY:
                back_edges.append((node_id, neighbor))
            elif color.get(neighbor) == WHITE:
                _dfs(neighbor)
        color[node_id] = BLACK

    for node in graph.nodes:
        if color[node.id] == WHITE:
            _dfs(node.id)

    node_title = {n.id: n.data.title for n in graph.nodes}
    for src, tgt in back_edges:
        result.add_error(
            f"Cycle detected: edge '{src}' → '{tgt}' creates a loop. "
            f"Dify does not support cycles — edges between cycle nodes "
            f"will be hidden after import. "
            f"({node_title.get(src, src)} → {node_title.get(tgt, tgt)})",
        )


def _validate_connectivity(dsl: DifyDSL, result) -> None:
    """Every node must be reachable from Start (root). Unreachable = error."""
    graph = dsl.workflow.graph
    if not graph.nodes:
        return

    start_ids = {n.id for n in graph.nodes if n.data.type in START_NODE_TYPES}
    if not start_ids:
        return

    # BFS from start nodes, including Iteration/Loop children
    node_by_id = {n.id: n for n in graph.nodes}
    children_by_parent: dict[str, list[str]] = {}
    for node in graph.nodes:
        parent_id = getattr(node, "parentId", None)
        if parent_id:
            children_by_parent.setdefault(parent_id, []).append(node.id)

    adjacency: dict[str, list[str]] = {n.id: [] for n in graph.nodes}
    for edge in graph.edges:
        if edge.source in adjacency:
            adjacency[edge.source].append(edge.target)

    visited: set[str] = set()
    queue = list(start_ids)
    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)

        current_node = node_by_id.get(current)
        if current_node and current_node.data.type in {NodeType.ITERATION, NodeType.LOOP}:
            for child_id in children_by_parent.get(current, []):
                if child_id not in visited:
                    queue.append(child_id)

        for neighbor in adjacency.get(current, []):
            if neighbor not in visited:
                queue.append(neighbor)

    unreachable = {n.id for n in graph.nodes} - visited
    for nid in unreachable:
        result.add_error("Node is unreachable from start", node_id=nid)


def _validate_checklist(dsl: DifyDSL, result) -> None:
    """Pre-publish checklist: variable references + node config completeness."""
    cl_errors = validate_checklist(dsl)
    for err in cl_errors:
        if err.level == "error":
            result.add_error(err.message, node_id=err.node_id, field_name=err.field)
        else:
            result.add_warning(err.message, node_id=err.node_id, field_name=err.field)
