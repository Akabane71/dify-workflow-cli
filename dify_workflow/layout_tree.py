"""Tree-style layout for Dify workflows — keeps branches grouped vertically.

Unlike the DAG layered layout (which intermixes branches at each layer),
this tree layout allocates a contiguous vertical band for each sub-branch,
producing a clean left-to-right tree that mirrors Dify's visual style.

Algorithm:
  1. Build a spanning tree from the start node via BFS
  2. Compute subtree weight (leaf count) for vertical space allocation
  3. Sort children by branch order (if-else case_id, classifier class_id)
  4. Recursively assign Y bands proportional to subtree weight
  5. Assign X by depth (layer * horizontal step)
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

NODE_WIDTH = 244
NODE_HEIGHT = 90
H_GAP = 100  # horizontal gap between layers
V_GAP = 40   # vertical gap between sibling branches
START_X = 30.0
START_Y = 50.0


def layout_tree(
    node_ids: list[str],
    adj: dict[str, list[str]],
    rev: dict[str, list[str]],
    branch_order: dict[str, dict[str, int]],
) -> dict[str, tuple[float, float]]:
    """Compute tree layout positions: node_id -> (x, y).

    Groups each branch into a contiguous vertical band, flowing left-to-right.
    Handles convergent nodes (multiple parents) and cycles gracefully.
    """
    if not node_ids:
        return {}

    # Find root nodes (no incoming edges)
    roots = [nid for nid in node_ids if not rev.get(nid)]
    if not roots:
        roots = [node_ids[0]]

    # Build spanning tree via BFS
    tree_children, depth = _build_spanning_tree(roots, node_ids, adj, branch_order)

    # Compute subtree weight for each node (for vertical space allocation)
    weights = _compute_weights(roots, tree_children)

    # Assign positions recursively
    positions: dict[str, tuple[float, float]] = {}
    total_weight = sum(weights.get(r, 1) for r in roots)
    total_height = total_weight * (NODE_HEIGHT + V_GAP) - V_GAP

    y_offset = START_Y
    for root in roots:
        root_weight = weights.get(root, 1)
        band_height = (root_weight / total_weight) * total_height
        _assign_positions(
            root, depth, tree_children, weights,
            y_top=y_offset, y_bottom=y_offset + band_height,
            positions=positions,
        )
        y_offset += band_height + V_GAP

    return positions


def _build_spanning_tree(
    roots: list[str],
    node_ids: list[str],
    adj: dict[str, list[str]],
    branch_order: dict[str, dict[str, int]],
) -> tuple[dict[str, list[str]], dict[str, int]]:
    """BFS from roots to build a spanning tree.

    Returns:
        tree_children: parent -> ordered list of children
        depth: node_id -> depth from root
    """
    tree_children: dict[str, list[str]] = defaultdict(list)
    depth: dict[str, int] = {}
    visited: set[str] = set()
    node_id_set = set(node_ids)

    queue: deque[str] = deque()
    for r in roots:
        if r in node_id_set:
            queue.append(r)
            depth[r] = 0
            visited.add(r)

    while queue:
        current = queue.popleft()
        children = adj.get(current, [])

        # Sort children by branch order for deterministic placement
        bo = branch_order.get(current, {})
        sorted_children = sorted(
            [c for c in children if c in node_id_set],
            key=lambda c: bo.get(c, 999),
        )

        for child in sorted_children:
            if child not in visited:
                visited.add(child)
                tree_children[current].append(child)
                depth[child] = depth[current] + 1
                queue.append(child)

    # Handle disconnected nodes
    for nid in node_ids:
        if nid not in visited:
            depth[nid] = 0

    return tree_children, depth


def _compute_weights(
    roots: list[str],
    tree_children: dict[str, list[str]],
) -> dict[str, int]:
    """Compute subtree weights (leaf count) bottom-up via post-order DFS."""
    weights: dict[str, int] = {}

    def dfs(nid: str) -> int:
        children = tree_children.get(nid, [])
        if not children:
            weights[nid] = 1
            return 1
        w = sum(dfs(c) for c in children)
        weights[nid] = w
        return w

    for root in roots:
        dfs(root)
    return weights


def _assign_positions(
    nid: str,
    depth: dict[str, int],
    tree_children: dict[str, list[str]],
    weights: dict[str, int],
    y_top: float,
    y_bottom: float,
    positions: dict[str, tuple[float, float]],
) -> None:
    """Recursively assign positions, centering each node in its vertical band."""
    x = START_X + depth[nid] * (NODE_WIDTH + H_GAP)
    y_center = (y_top + y_bottom) / 2 - NODE_HEIGHT / 2
    positions[nid] = (round(x, 1), round(y_center, 1))

    children = tree_children.get(nid, [])
    if not children:
        return

    total_weight = sum(weights.get(c, 1) for c in children)
    band_height = y_bottom - y_top

    y_cursor = y_top
    for child in children:
        child_weight = weights.get(child, 1)
        child_band = (child_weight / total_weight) * band_height
        _assign_positions(
            child, depth, tree_children, weights,
            y_top=y_cursor, y_bottom=y_cursor + child_band,
            positions=positions,
        )
        y_cursor += child_band
