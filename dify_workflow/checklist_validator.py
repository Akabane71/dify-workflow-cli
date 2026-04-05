"""Pre-publish checklist validator — mirrors Dify frontend use-checklist.ts.

Two validation layers:
1. Node configuration completeness (per-node checkValid)
2. Cross-node variable reference validation (value_selector → upstream node output)
"""

from __future__ import annotations

import re
from typing import Any

from .models import DifyDSL, Node, NodeType

# ── Error type ──────────────────────────────────────────────────────────

class ChecklistError:
    __slots__ = ("level", "message", "node_id", "node_title", "field")

    def __init__(
        self,
        level: str,
        message: str,
        node_id: str = "",
        node_title: str = "",
        field: str = "",
    ):
        self.level = level
        self.message = message
        self.node_id = node_id
        self.node_title = node_title
        self.field = field

    def __repr__(self) -> str:
        return f"ChecklistError({self.level!r}, {self.message!r}, node={self.node_id!r})"


# ── Helpers ─────────────────────────────────────────────────────────────

def _extras(node: Node) -> dict[str, Any]:
    return getattr(node.data, "__pydantic_extra__", None) or {}


def _get(node: Node, field: str, default: Any = None) -> Any:
    if hasattr(node.data, field):
        val = getattr(node.data, field)
        if val is not None:
            return val
    return _extras(node).get(field, default)


_SPECIAL_PREFIXES = frozenset({"sys", "env", "conversation", "rag"})

_TEMPLATE_VAR_RE = re.compile(r"\{\{#([^#]+)#\}\}")

_EMPTY_OPS = frozenset({
    "is empty", "is not empty", "empty", "not empty",
    "is-empty", "is-not-empty", "null", "not null",
    "is null", "is not null",
})


def _extract_template_vars(text: str) -> list[list[str]]:
    """Extract variable references from Dify template syntax {{#node_id.var#}}.

    Single-element refs like {{#context#}} are LLM-internal template
    placeholders, not cross-node references — they are skipped.
    """
    result = []
    for m in _TEMPLATE_VAR_RE.finditer(text):
        parts = m.group(1).split(".")
        if len(parts) >= 2 and parts[0] not in _SPECIAL_PREFIXES:
            result.append(parts)
    return result


def _is_selector_empty(sel: Any) -> bool:
    return not sel or not isinstance(sel, list) or len(sel) == 0


# ── Node configuration checks — imported from checklist_checks.py ───────
# These imports happen AFTER shared helpers/classes are defined,
# so the circular import (checklist_checks importing from this file) is safe.

from .checklist_checks import _NODE_CHECKERS  # noqa: E402


# ── Variable reference extraction ───────────────────────────────────────

def _extract_used_vars(node: Node) -> list[list[str]]:
    """Extract all value_selector references used by a node."""
    t = node.data.type
    refs: list[list[str]] = []

    if t == NodeType.END:
        outputs = _get(node, "outputs", [])
        if isinstance(outputs, list):
            for out in outputs:
                vs = out.get("value_selector", []) if isinstance(out, dict) else getattr(out, "value_selector", [])
                if vs:
                    refs.append(list(vs))

    elif t == NodeType.ANSWER:
        answer = _get(node, "answer", "")
        if answer:
            refs.extend(_extract_template_vars(answer))

    elif t == NodeType.LLM:
        prompt = _get(node, "prompt_template")
        if isinstance(prompt, list):
            for p in prompt:
                text = p.get("text", "") if isinstance(p, dict) else getattr(p, "text", "")
                if text:
                    refs.extend(_extract_template_vars(text))
        elif isinstance(prompt, dict):
            text = prompt.get("text", "")
            if text:
                refs.extend(_extract_template_vars(text))
        ctx = _get(node, "context")
        if isinstance(ctx, dict) and ctx.get("variable_selector"):
            refs.append(list(ctx["variable_selector"]))

    elif t == NodeType.CODE:
        variables = _get(node, "variables", [])
        if isinstance(variables, list):
            for v in variables:
                vs = v.get("value_selector", []) if isinstance(v, dict) else getattr(v, "value_selector", [])
                if vs:
                    refs.append(list(vs))

    elif t == NodeType.TEMPLATE_TRANSFORM:
        variables = _get(node, "variables", [])
        if isinstance(variables, list):
            for v in variables:
                vs = v.get("value_selector", []) if isinstance(v, dict) else getattr(v, "value_selector", [])
                if vs:
                    refs.append(list(vs))

    elif t == NodeType.IF_ELSE:
        cases = node.data.cases or _get(node, "cases", [])
        if isinstance(cases, list):
            for case in cases:
                conditions = case.conditions if hasattr(case, "conditions") else (case.get("conditions", []) if isinstance(case, dict) else [])
                for cond in (conditions or []):
                    vs = cond.get("variable_selector", []) if isinstance(cond, dict) else getattr(cond, "variable_selector", [])
                    if vs:
                        refs.append(list(vs))

    elif t == NodeType.QUESTION_CLASSIFIER:
        qvs = _get(node, "query_variable_selector", [])
        if qvs:
            refs.append(list(qvs))
        instruction = _get(node, "instruction", "")
        if instruction:
            refs.extend(_extract_template_vars(instruction))

    elif t == NodeType.PARAMETER_EXTRACTOR:
        query = _get(node, "query", [])
        if query:
            refs.append(list(query))
        instruction = _get(node, "instruction", "")
        if instruction:
            refs.extend(_extract_template_vars(instruction))

    elif t == NodeType.KNOWLEDGE_RETRIEVAL:
        qvs = _get(node, "query_variable_selector", [])
        if qvs:
            refs.append(list(qvs))

    elif t == NodeType.HTTP_REQUEST:
        for field in ("url", "headers", "params"):
            text = _get(node, field, "")
            if text and isinstance(text, str):
                refs.extend(_extract_template_vars(text))
        body = _get(node, "body")
        if isinstance(body, dict):
            body_data = body.get("data", "")
            if isinstance(body_data, str) and body_data:
                refs.extend(_extract_template_vars(body_data))

    elif t == NodeType.ITERATION:
        it_sel = _get(node, "iterator_selector", [])
        if it_sel:
            refs.append(list(it_sel))

    elif t == NodeType.LOOP:
        conditions = _get(node, "break_conditions", [])
        if isinstance(conditions, list):
            for cond in conditions:
                vs = cond.get("variable_selector", []) if isinstance(cond, dict) else getattr(cond, "variable_selector", [])
                if vs:
                    refs.append(list(vs))

    elif t == NodeType.VARIABLE_ASSIGNER:
        variables = _get(node, "variables", [])
        if isinstance(variables, list):
            for v in variables:
                if isinstance(v, list) and v:
                    refs.append(v)

    elif t == NodeType.LIST_OPERATOR:
        var = _get(node, "variable", [])
        if var:
            refs.append(list(var))

    elif t == NodeType.DOCUMENT_EXTRACTOR:
        vs = _get(node, "variable_selector", [])
        if vs:
            refs.append(list(vs))

    elif t == NodeType.HUMAN_INPUT:
        form = _get(node, "form_content", "")
        if form:
            refs.extend(_extract_template_vars(form))

    return [r for r in refs if r and len(r) >= 1]


# ── Build available outputs map ─────────────────────────────────────────

def _build_node_outputs(nodes: list[Node]) -> dict[str, set[str]]:
    """Build mapping: node_id → set of output variable names it provides."""
    outputs_map: dict[str, set[str]] = {}

    for node in nodes:
        nid = node.id
        t = node.data.type
        out: set[str] = set()

        if t == NodeType.START:
            variables = _get(node, "variables", [])
            if isinstance(variables, list):
                for v in variables:
                    var_name = v.get("variable", "") if isinstance(v, dict) else getattr(v, "variable", "")
                    if var_name:
                        out.add(var_name)

        elif t == NodeType.LLM:
            out.update({"text", "reasoning_content", "usage"})

        elif t == NodeType.CODE:
            code_outputs = _get(node, "outputs")
            if isinstance(code_outputs, dict):
                out.update(code_outputs.keys())

        elif t == NodeType.KNOWLEDGE_RETRIEVAL:
            out.add("result")

        elif t == NodeType.HTTP_REQUEST:
            out.update({"body", "status_code", "headers", "files"})

        elif t == NodeType.TEMPLATE_TRANSFORM:
            out.add("output")

        elif t == NodeType.PARAMETER_EXTRACTOR:
            out.update({"__is_success", "__reason", "__usage"})
            params = _get(node, "parameters", [])
            if isinstance(params, list):
                for p in params:
                    name = p.get("name", "") if isinstance(p, dict) else getattr(p, "name", "")
                    if name:
                        out.add(name)

        elif t == NodeType.ITERATION:
            out.add("output")

        elif t == NodeType.TOOL:
            out.update({"text", "files", "json"})

        elif t == NodeType.HUMAN_INPUT:
            out.update({"__action_id", "__rendered_content"})

        elif t == NodeType.DOCUMENT_EXTRACTOR:
            out.add("text")

        elif t == NodeType.AGENT:
            out.update({"text", "files", "json", "usage"})

        elif t == NodeType.LOOP:
            loop_vars = _get(node, "loop_variables", [])
            if isinstance(loop_vars, list):
                for lv in loop_vars:
                    label = lv.get("label", "") if isinstance(lv, dict) else getattr(lv, "label", "")
                    if label:
                        out.add(label)

        elif t == NodeType.IF_ELSE:
            pass

        elif t == NodeType.QUESTION_CLASSIFIER:
            out.update({"class_name", "usage"})

        elif t == NodeType.VARIABLE_ASSIGNER:
            out.add("output")

        elif t == NodeType.VARIABLE_AGGREGATOR:
            out.add("output")

        elif t == NodeType.LIST_OPERATOR:
            out.update({"result", "first_record", "last_record"})

        elif t == NodeType.DATASOURCE:
            out.add("*")

        else:
            # Unknown types: accept any reference to avoid false positives
            out.add("*")

        outputs_map[nid] = out

    return outputs_map


# ── Connectivity check (mirrors getValidTreeNodes) ──────────────────────

_START_NODE_TYPES = frozenset({
    NodeType.START,
    NodeType.TRIGGER_WEBHOOK,
    NodeType.TRIGGER_SCHEDULE,
    NodeType.TRIGGER_PLUGIN,
    NodeType.DATASOURCE,
})


def _get_reachable_nodes(nodes: list[Node], edges: list) -> set[str]:
    """BFS from all start-type nodes to find reachable node IDs.

    Mirrors the frontend ``getValidTreeNodes()`` in ``workflow.ts``.
    """
    node_by_id = {n.id: n for n in nodes}
    children_by_parent: dict[str, list[str]] = {}
    for node in nodes:
        parent_id = getattr(node, "parentId", None)
        if parent_id:
            children_by_parent.setdefault(parent_id, []).append(node.id)

    adjacency: dict[str, list[str]] = {n.id: [] for n in nodes}
    for edge in edges:
        src = edge.source
        if src in adjacency:
            adjacency[src].append(edge.target)

    start_ids = {n.id for n in nodes if n.data.type in _START_NODE_TYPES}
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

    return visited


def _get_upstream_nodes(node_id: str, nodes: list[Node], edges: list) -> set[str]:
    """BFS backward from node_id to find all upstream (predecessor) node IDs."""
    reverse_adj: dict[str, list[str]] = {n.id: [] for n in nodes}
    for edge in edges:
        tgt = edge.target
        if tgt in reverse_adj:
            reverse_adj[tgt].append(edge.source)

    visited: set[str] = set()
    queue = list(reverse_adj.get(node_id, []))

    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)
        for neighbor in reverse_adj.get(current, []):
            if neighbor not in visited:
                queue.append(neighbor)

    return visited


# ── Public API ──────────────────────────────────────────────────────────

def validate_checklist(dsl: DifyDSL) -> list[ChecklistError]:
    """Run pre-publish checklist validation on a workflow DSL.

    Returns a list of ChecklistError items mirroring Dify's frontend
    checklist validation panel. Three layers:
    1. Node configuration completeness (checkValid)
    2. Variable reference validity (upstream node + output exists)
    3. Connectivity (reachable from start node)
    """
    errors: list[ChecklistError] = []
    nodes = dsl.workflow.graph.nodes
    edges = dsl.workflow.graph.edges

    if not nodes:
        return errors

    # 1. Node configuration completeness
    for node in nodes:
        checker = _NODE_CHECKERS.get(node.data.type)
        if checker:
            errors.extend(checker(node))

    # 2. Variable reference validation
    node_outputs = _build_node_outputs(nodes)
    node_id_set = set(node_outputs.keys())

    for node in nodes:
        used_vars = _extract_used_vars(node)
        if not used_vars:
            continue

        # Lazily compute upstream nodes for this node
        upstream: set[str] | None = None

        for ref in used_vars:
            if not ref:
                continue
            prefix = ref[0]
            if prefix in _SPECIAL_PREFIXES:
                continue
            # Check node exists
            if prefix not in node_id_set:
                errors.append(ChecklistError(
                    "error",
                    f"Invalid variable: references non-existent node '{prefix}'",
                    node.id, node.data.title, "value_selector",
                ))
                continue
            # Check node is upstream (reachable predecessor)
            if upstream is None:
                upstream = _get_upstream_nodes(node.id, nodes, edges)
            if prefix not in upstream:
                errors.append(ChecklistError(
                    "error",
                    f"Invalid variable: node '{prefix}' is not upstream of '{node.id}'",
                    node.id, node.data.title, "value_selector",
                ))
                continue
            # Check output exists (if node has known outputs)
            target_outputs = node_outputs[prefix]
            if "*" in target_outputs:
                continue
            if len(ref) >= 2:
                output_name = ref[1]
                if output_name not in target_outputs:
                    errors.append(ChecklistError(
                        "error",
                        f"Invalid variable: node '{prefix}' has no output '{output_name}'",
                        node.id, node.data.title, "value_selector",
                    ))

    # 3. Connectivity check — unconnected nodes
    reachable = _get_reachable_nodes(nodes, edges)
    for node in nodes:
        if node.data.type in _START_NODE_TYPES:
            continue  # Start nodes skip connectivity check
        if node.id not in reachable:
            errors.append(ChecklistError(
                "error",
                f"Node not connected: '{node.data.title}' is not reachable from start node",
                node.id, node.data.title, "",
            ))

    return errors
