"""Auto-layout engine for Dify workflow DSL files.

Provides 4 layout strategies to automatically reposition workflow nodes:
- linear:       horizontal single-line (left-to-right)
- hierarchical: DAG layered layout with cross minimization (default)
- vertical:     DAG layered layout top-to-bottom
- compact:      tighter hierarchical with reduced spacing

Spacing parameters are aligned with Dify's frontend ELK.js configuration.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any, Literal

from .models import DifyDSL, Position

# ── Constants (aligned with Dify frontend ELK.js) ──────────────────────
NODE_WIDTH = 244
NODE_HEIGHT = 90
START_X = 30.0
START_Y = 50.0

# Spacing presets per strategy
_SPACING = {
    "linear":       {"layer_gap": 100, "node_gap": 0},
    "hierarchical": {"layer_gap": 100, "node_gap": 80},
    "vertical":     {"layer_gap": 100, "node_gap": 100},
    "compact":      {"layer_gap": 60,  "node_gap": 40},
}

LayoutStrategy = Literal["linear", "hierarchical", "vertical", "compact", "tree"]


# ── Public API ──────────────────────────────────────────────────────────

def auto_layout(
    dsl: DifyDSL,
    strategy: LayoutStrategy = "hierarchical",
) -> dict[str, tuple[float, float]]:
    """Reposition all workflow nodes using the given layout strategy.

    Modifies the DSL object in-place and returns a mapping of
    node_id -> (x, y) for the computed positions.
    """
    nodes = dsl.workflow.graph.nodes
    edges = dsl.workflow.graph.edges

    if not nodes:
        return {}

    node_ids = [n.id for n in nodes]
    node_id_set = set(node_ids)

    # Build adjacency lists (only for edges whose endpoints exist)
    adj: dict[str, list[str]] = defaultdict(list)
    rev: dict[str, list[str]] = defaultdict(list)
    for e in edges:
        if e.source in node_id_set and e.target in node_id_set:
            adj[e.source].append(e.target)
            rev[e.target].append(e.source)

    # Build branch-order map for deterministic ordering
    branch_order = _build_branch_order(nodes, edges)

    if strategy == "linear":
        positions = _layout_linear(node_ids, adj, rev, branch_order)
    elif strategy == "vertical":
        positions = _layout_dag(node_ids, adj, rev, branch_order,
                                direction="vertical",
                                spacing=_SPACING["vertical"])
    elif strategy == "compact":
        positions = _layout_dag(node_ids, adj, rev, branch_order,
                                direction="horizontal",
                                spacing=_SPACING["compact"])
    elif strategy == "tree":
        from .layout_tree import layout_tree
        positions = layout_tree(node_ids, adj, rev, branch_order)
    else:
        positions = _layout_dag(node_ids, adj, rev, branch_order,
                                direction="horizontal",
                                spacing=_SPACING["hierarchical"])

    # Apply positions to DSL nodes
    for node in nodes:
        if node.id in positions:
            x, y = positions[node.id]
            node.position = Position(x=x, y=y)
            node.positionAbsolute = Position(x=x, y=y)

    return positions


# ── Branch order helpers ────────────────────────────────────────────────

def _build_branch_order(nodes: list, edges: list) -> dict[str, dict[str, int]]:
    """Build a mapping: source_id -> {target_id: order_index}.

    For if-else / question-classifier / human-input nodes, edges from the
    same source should be ordered by their sourceHandle to match the
    case/class/action order defined in node data.
    """
    from .models import NodeType

    node_map: dict[str, Any] = {n.id: n for n in nodes}
    out_edges: dict[str, list] = defaultdict(list)
    for e in edges:
        out_edges[e.source].append(e)

    result: dict[str, dict[str, int]] = {}

    for src_id, src_edges in out_edges.items():
        node = node_map.get(src_id)
        if not node:
            continue

        extras = getattr(node.data, "__pydantic_extra__", None) or {}
        node_type = node.data.type

        ordered_handles: list[str] = []

        if node_type == NodeType.IF_ELSE:
            # cases is a typed field on NodeData, not an extra
            cases = node.data.cases or []
            for c in cases:
                cid = c.case_id if hasattr(c, "case_id") else ""
                if cid:
                    ordered_handles.append(cid)
            ordered_handles.append("false")

        elif node_type == NodeType.QUESTION_CLASSIFIER:
            classes = extras.get("classes", [])
            for cls in classes:
                cid = cls.get("id", "") if isinstance(cls, dict) else ""
                if cid:
                    ordered_handles.append(cid)

        elif node_type == NodeType.HUMAN_INPUT:
            actions = extras.get("user_actions", [])
            for act in actions:
                aid = act.get("id", "") if isinstance(act, dict) else ""
                if aid:
                    ordered_handles.append(aid)
            ordered_handles.append("__timeout")

        if ordered_handles:
            handle_rank = {h: i for i, h in enumerate(ordered_handles)}
            sorted_edges = sorted(
                src_edges,
                key=lambda e: handle_rank.get(e.sourceHandle, len(ordered_handles)),
            )
            result[src_id] = {e.target: i for i, e in enumerate(sorted_edges)}
        else:
            result[src_id] = {e.target: i for i, e in enumerate(src_edges)}

    return result


# ── Topological order (shared) ──────────────────────────────────────────

def _topo_order(
    node_ids: list[str],
    adj: dict[str, list[str]],
    rev: dict[str, list[str]],
) -> list[str]:
    """Kahn's algorithm for topological sort. Falls back to input order for cycles."""
    in_degree: dict[str, int] = {nid: 0 for nid in node_ids}
    for nid in node_ids:
        for tgt in adj.get(nid, []):
            if tgt in in_degree:
                in_degree[tgt] += 1

    queue = deque(nid for nid in node_ids if in_degree[nid] == 0)
    result: list[str] = []

    while queue:
        nid = queue.popleft()
        result.append(nid)
        for tgt in adj.get(nid, []):
            if tgt in in_degree:
                in_degree[tgt] -= 1
                if in_degree[tgt] == 0:
                    queue.append(tgt)

    # If there are cycles, append remaining nodes
    if len(result) < len(node_ids):
        seen = set(result)
        for nid in node_ids:
            if nid not in seen:
                result.append(nid)

    return result


# ── Linear layout ───────────────────────────────────────────────────────

def _layout_linear(
    node_ids: list[str],
    adj: dict[str, list[str]],
    rev: dict[str, list[str]],
    branch_order: dict[str, dict[str, int]],
) -> dict[str, tuple[float, float]]:
    """Place all nodes in a single horizontal line in topological order."""
    order = _topo_order(node_ids, adj, rev)
    spacing = NODE_WIDTH + _SPACING["linear"]["layer_gap"]
    center_y = START_Y + NODE_HEIGHT / 2

    positions: dict[str, tuple[float, float]] = {}
    for i, nid in enumerate(order):
        positions[nid] = (START_X + i * spacing, center_y)

    return positions


# ── DAG layered layout ──────────────────────────────────────────────────

def _layout_dag(
    node_ids: list[str],
    adj: dict[str, list[str]],
    rev: dict[str, list[str]],
    branch_order: dict[str, dict[str, int]],
    *,
    direction: Literal["horizontal", "vertical"],
    spacing: dict[str, int],
) -> dict[str, tuple[float, float]]:
    """DAG layered layout: assign layers, minimize crossings, position nodes."""
    node_id_set = set(node_ids)

    # Step 1: Layer assignment (longest-path from sources)
    layers = _assign_layers(node_ids, adj, rev)

    # Step 2: Group nodes by layer
    max_layer = max(layers.values()) if layers else 0
    layer_nodes: list[list[str]] = [[] for _ in range(max_layer + 1)]
    for nid in node_ids:
        layer_nodes[layers[nid]].append(nid)

    # Step 3: Initial ordering within layers (topological)
    topo = _topo_order(node_ids, adj, rev)
    topo_rank = {nid: i for i, nid in enumerate(topo)}
    for layer in layer_nodes:
        layer.sort(key=lambda nid: topo_rank.get(nid, 0))

    # Step 4: Cross minimization (barycenter heuristic, 4 iterations)
    layer_nodes = _minimize_crossings(layer_nodes, adj, rev, branch_order)

    # Step 5: Position assignment
    layer_gap = spacing["layer_gap"]
    node_gap = spacing["node_gap"]

    positions: dict[str, tuple[float, float]] = {}

    # Find the maximum number of nodes in any layer (for centering)
    max_count = max(len(layer) for layer in layer_nodes) if layer_nodes else 1

    # In horizontal mode: primary=X (layers), secondary=Y (within layer)
    # In vertical mode:   primary=Y (layers), secondary=X (within layer)
    primary_size = NODE_WIDTH if direction == "horizontal" else NODE_HEIGHT
    secondary_size = NODE_HEIGHT if direction == "horizontal" else NODE_WIDTH

    for layer_idx, layer in enumerate(layer_nodes):
        count = len(layer)
        layer_span = count * secondary_size + (count - 1) * node_gap if count > 1 else secondary_size
        max_span = max_count * secondary_size + (max_count - 1) * node_gap if max_count > 1 else secondary_size
        # Center this layer relative to the widest layer
        offset = (max_span - layer_span) / 2

        for node_idx, nid in enumerate(layer):
            primary = START_X + layer_idx * (primary_size + layer_gap)
            secondary = START_Y + offset + node_idx * (secondary_size + node_gap)

            if direction == "horizontal":
                positions[nid] = (primary, secondary)
            else:
                positions[nid] = (secondary, primary)

    return positions


def _assign_layers(
    node_ids: list[str],
    adj: dict[str, list[str]],
    rev: dict[str, list[str]],
) -> dict[str, int]:
    """Assign each node to a layer using longest-path from sources.

    layer(n) = 0 if n has no predecessors
    layer(n) = max(layer(p) for p in predecessors) + 1
    """
    layers: dict[str, int] = {}
    node_id_set = set(node_ids)

    # Find sources (no incoming edges)
    sources = [nid for nid in node_ids if not rev.get(nid)]
    if not sources:
        # All nodes have incoming edges (cycle) → pick first as source
        sources = [node_ids[0]]

    # BFS to assign layers
    queue = deque(sources)
    for s in sources:
        layers[s] = 0

    visited_count: dict[str, int] = defaultdict(int)
    in_degree: dict[str, int] = {nid: 0 for nid in node_ids}
    for nid in node_ids:
        for tgt in adj.get(nid, []):
            if tgt in node_id_set:
                in_degree[tgt] += 1

    while queue:
        nid = queue.popleft()
        current_layer = layers[nid]
        for tgt in adj.get(nid, []):
            if tgt not in node_id_set:
                continue
            new_layer = current_layer + 1
            if tgt not in layers or new_layer > layers[tgt]:
                layers[tgt] = new_layer
            visited_count[tgt] += 1
            if visited_count[tgt] >= in_degree[tgt]:
                queue.append(tgt)

    # Assign unvisited nodes (disconnected components)
    for nid in node_ids:
        if nid not in layers:
            layers[nid] = 0

    return layers


def _minimize_crossings(
    layer_nodes: list[list[str]],
    adj: dict[str, list[str]],
    rev: dict[str, list[str]],
    branch_order: dict[str, dict[str, int]],
    iterations: int = 4,
) -> list[list[str]]:
    """Barycenter heuristic for layer-by-layer crossing minimization.

    Performs forward and backward sweeps, using the average position of
    connected nodes in adjacent layers as the barycenter value.
    Branch order from if-else/question-classifier is respected.
    """
    num_layers = len(layer_nodes)
    if num_layers <= 1:
        return layer_nodes

    for _ in range(iterations):
        # Forward sweep (layer 1 to n-1)
        for i in range(1, num_layers):
            _sort_layer_by_barycenter(
                layer_nodes, i, rev, branch_order, direction="forward",
            )

        # Backward sweep (layer n-2 to 0)
        for i in range(num_layers - 2, -1, -1):
            _sort_layer_by_barycenter(
                layer_nodes, i, adj, branch_order, direction="backward",
            )

    return layer_nodes


def _sort_layer_by_barycenter(
    layer_nodes: list[list[str]],
    layer_idx: int,
    connections: dict[str, list[str]],
    branch_order: dict[str, dict[str, int]],
    *,
    direction: Literal["forward", "backward"],
) -> None:
    """Sort a single layer by barycenter of connected nodes in adjacent layer."""
    if direction == "forward":
        ref_layer_idx = layer_idx - 1
    else:
        ref_layer_idx = layer_idx + 1

    if ref_layer_idx < 0 or ref_layer_idx >= len(layer_nodes):
        return

    ref_layer = layer_nodes[ref_layer_idx]
    ref_pos = {nid: i for i, nid in enumerate(ref_layer)}

    layer = layer_nodes[layer_idx]

    def barycenter(nid: str) -> float:
        if direction == "forward":
            # Predecessors of nid
            connected = [p for p in (connections.get(nid) or []) if p in ref_pos]
        else:
            # Successors of nid
            connected = [s for s in (connections.get(nid) or []) if s in ref_pos]

        if not connected:
            return float("inf")

        # Weight by branch order if available
        weighted_positions: list[float] = []
        for c in connected:
            base_pos = ref_pos[c]
            # Check if the reference node has a branch order for the current node
            if direction == "forward":
                bo = branch_order.get(c, {}).get(nid)
            else:
                bo = branch_order.get(nid, {}).get(c)
            if bo is not None:
                weighted_positions.append(base_pos + bo * 0.01)
            else:
                weighted_positions.append(float(base_pos))

        return sum(weighted_positions) / len(weighted_positions)

    layer.sort(key=barycenter)
    layer_nodes[layer_idx] = layer
