"""Frontend crash prevention validator.

Validates that node data fields required by Dify's React frontend are present
and have the correct type, preventing React rendering crashes (white screen).

The Dify frontend does NOT validate node data completeness before rendering.
Components directly destructure and access nested properties like:
  - ``cases.map(...)``  (if-else/node.tsx)
  - ``data.model.provider``  (question-classifier/node.tsx)
  - ``variables.length``  (start/node.tsx)

If these fields are missing, React crashes with "Cannot read properties of
undefined". This module catches those issues at DSL generation time.

Key crash sources in frontend:
  - ``workflow/utils/workflow-init.ts``  → ``initialNodes()``
  - ``workflow/nodes/*/node.tsx``  → per-node rendering components
"""

from __future__ import annotations

from typing import Any

from .models import Node, NodeType
from .node_data_validator import NodeDataError, _extras, _get_field

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = ["validate_frontend_compat"]


def validate_frontend_compat(node: Node) -> list[NodeDataError]:
    """Validate that a node's data won't crash the Dify frontend.

    Returns a list of ``NodeDataError`` with level ``"error"`` for fields
    that will definitely cause a React crash, and ``"warning"`` for fields
    that may cause visual glitches.
    """
    validator = _FRONTEND_VALIDATORS.get(node.data.type)
    if validator is not None:
        return validator(node)
    return []


# ---------------------------------------------------------------------------
# Per-node validators — each mirrors the exact data access in the
# corresponding frontend ``node.tsx`` and ``initialNodes()``
# ---------------------------------------------------------------------------


def _fe_start(node: Node) -> list[NodeDataError]:
    """start/node.tsx: ``const { variables } = data; variables.length``"""
    errors: list[NodeDataError] = []
    nid = node.id
    variables = node.data.variables
    if variables is None:
        errors.append(NodeDataError(
            "error",
            "Frontend crash: start node missing 'variables' (must be array, can be empty). "
            "start/node.tsx does `variables.length` without null check.",
            nid, "variables",
        ))
    return errors


def _fe_if_else(node: Node) -> list[NodeDataError]:
    """if-else/node.tsx: ``const { cases } = data; cases.length; cases.map(...)``
    Also initialNodes() calls ``cases.map(item => ...)`` for _targetBranches.
    """
    errors: list[NodeDataError] = []
    nid = node.id
    cases = node.data.cases
    # Check for old format fields that initialNodes() uses as fallback
    has_legacy = bool(_get_field(node, "logical_operator") and _get_field(node, "conditions"))

    if not cases and not has_legacy:
        errors.append(NodeDataError(
            "error",
            "Frontend crash: if-else node missing 'cases' array. "
            "initialNodes() and if-else/node.tsx call cases.map() without null check.",
            nid, "cases",
        ))
    elif isinstance(cases, list):
        for i, case in enumerate(cases):
            if isinstance(case, dict):
                conditions = case.get("conditions")
            else:
                conditions = getattr(case, "conditions", None)
            if conditions is None:
                errors.append(NodeDataError(
                    "error",
                    f"Frontend crash: if-else cases[{i}] missing 'conditions' array. "
                    "if-else/node.tsx does caseItem.conditions.map() without null check.",
                    nid, f"cases[{i}].conditions",
                ))
            case_id = case.get("case_id") if isinstance(case, dict) else getattr(case, "case_id", None)
            if not case_id:
                errors.append(NodeDataError(
                    "error",
                    f"Frontend crash: if-else cases[{i}] missing 'case_id'. "
                    "Used as React key and in _targetBranches.",
                    nid, f"cases[{i}].case_id",
                ))
    return errors


def _fe_llm(node: Node) -> list[NodeDataError]:
    """initialNodes() does ``(node as any).data.model.provider = correctModelProvider(...)``
    llm/node.tsx has safe fallback: ``data.model || {}``
    """
    errors: list[NodeDataError] = []
    nid = node.id
    model = node.data.model
    if model is None and _get_field(node, "model") is None:
        errors.append(NodeDataError(
            "error",
            "Frontend crash: LLM node missing 'model' object. "
            "initialNodes() accesses data.model.provider without null check.",
            nid, "model",
        ))
    elif model is not None:
        provider = getattr(model, "provider", None) if not isinstance(model, dict) else model.get("provider")
        if not provider:
            errors.append(NodeDataError(
                "warning",
                "Frontend: LLM node model missing 'provider'. "
                "initialNodes() may pass undefined to correctModelProvider().",
                nid, "model.provider",
            ))
    return errors


def _fe_question_classifier(node: Node) -> list[NodeDataError]:
    """question-classifier/node.tsx: ``const { provider, name } = data.model``
    ``const topics = data.classes; topics.length; topics.map(...)``
    initialNodes(): ``data.model.provider = correctModelProvider(...)``
    initialNodes(): ``classes.map(topic => topic)`` for _targetBranches
    """
    errors: list[NodeDataError] = []
    nid = node.id

    model = node.data.model
    if model is None and _get_field(node, "model") is None:
        errors.append(NodeDataError(
            "error",
            "Frontend crash: question-classifier missing 'model' object. "
            "node.tsx destructures data.model and initialNodes() accesses data.model.provider.",
            nid, "model",
        ))

    classes = _get_field(node, "classes")
    if classes is None:
        errors.append(NodeDataError(
            "error",
            "Frontend crash: question-classifier missing 'classes' array. "
            "node.tsx does data.classes.length and classes.map().",
            nid, "classes",
        ))
    elif isinstance(classes, list):
        for i, cls in enumerate(classes):
            if isinstance(cls, dict):
                if not cls.get("id"):
                    errors.append(NodeDataError(
                        "error",
                        f"Frontend crash: question-classifier classes[{i}] missing 'id'. "
                        "Used as React key and in _targetBranches.",
                        nid, f"classes[{i}].id",
                    ))
    return errors


def _fe_parameter_extractor(node: Node) -> list[NodeDataError]:
    """initialNodes(): ``data.model.provider = correctModelProvider(...)``
    parameter-extractor/node.tsx has safe fallback: ``data.model || {}``
    """
    errors: list[NodeDataError] = []
    nid = node.id
    model = node.data.model
    if model is None and _get_field(node, "model") is None:
        errors.append(NodeDataError(
            "error",
            "Frontend crash: parameter-extractor missing 'model' object. "
            "initialNodes() accesses data.model.provider without null check.",
            nid, "model",
        ))
    return errors


def _fe_iteration(node: Node) -> list[NodeDataError]:
    """iteration/node.tsx: ``data._children!.length === 1``
    _children is set in initialNodes() as ``iterationOrLoopNodeMap[node.id] || []``
    so normally safe, but crashes if initialNodes() exits early due to
    another node's error.
    """
    # _children is always set by initialNodes() — no separate DSL field needed.
    # But we validate that fields accessed during initialNodes() processing exist.
    errors: list[NodeDataError] = []
    nid = node.id
    is_parallel = _get_field(node, "is_parallel")
    if is_parallel is not None and not isinstance(is_parallel, bool):
        errors.append(NodeDataError(
            "warning",
            "Frontend: iteration is_parallel should be boolean.",
            nid, "is_parallel",
        ))
    return errors


def _fe_loop(node: Node) -> list[NodeDataError]:
    """loop/node.tsx: ``data._children!.length === 1``
    Same pattern as iteration.
    """
    return []


def _fe_human_input(node: Node) -> list[NodeDataError]:
    """human-input/node.tsx:
    ``const deliveryMethods = data.delivery_methods; deliveryMethods.length > 0``
    ``const userActions = data.user_actions; userActions.length > 0``
    """
    errors: list[NodeDataError] = []
    nid = node.id

    dm = _get_field(node, "delivery_methods")
    if dm is None:
        errors.append(NodeDataError(
            "error",
            "Frontend crash: human-input missing 'delivery_methods' array. "
            "node.tsx does deliveryMethods.length without null check.",
            nid, "delivery_methods",
        ))
    elif not isinstance(dm, list):
        errors.append(NodeDataError(
            "error",
            "Frontend crash: human-input 'delivery_methods' must be an array.",
            nid, "delivery_methods",
        ))

    ua = _get_field(node, "user_actions")
    if ua is None:
        errors.append(NodeDataError(
            "error",
            "Frontend crash: human-input missing 'user_actions' array. "
            "node.tsx does userActions.length without null check.",
            nid, "user_actions",
        ))
    elif not isinstance(ua, list):
        errors.append(NodeDataError(
            "error",
            "Frontend crash: human-input 'user_actions' must be an array.",
            nid, "user_actions",
        ))

    return errors


def _fe_tool(node: Node) -> list[NodeDataError]:
    """tool/node.tsx accesses ``tool_configurations[key].value``
    initialNodes() does version migration: wraps scalar values into
    ``{type: 'constant', value: ...}`` when tool_node_version is missing.
    After migration, values are objects, so ``[key].value`` is safe.
    But if tool_configurations values are already objects with wrong shape,
    it can crash.
    """
    errors: list[NodeDataError] = []
    nid = node.id
    tc = _get_field(node, "tool_configurations")
    version = _get_field(node, "tool_node_version") or _get_field(node, "version")

    if isinstance(tc, dict) and version == "2":
        for key, val in tc.items():
            if val is not None and isinstance(val, dict):
                if "value" not in val:
                    errors.append(NodeDataError(
                        "warning",
                        f"Frontend: tool_configurations['{key}'] is object "
                        "but missing 'value' field. node.tsx accesses .value directly.",
                        nid, f"tool_configurations.{key}.value",
                    ))
    return errors


def _fe_code(node: Node) -> list[NodeDataError]:
    """code/node.tsx is empty <div> — safe.
    But code/default.ts checkValid() does ``variables.filter(v => !v.variable)``
    which crashes if variables is not an array.
    """
    errors: list[NodeDataError] = []
    nid = node.id
    variables = node.data.variables
    code_vars = _get_field(node, "variables")
    # For code nodes, variables field serves a different purpose than start node
    if node.data.type == NodeType.CODE:
        if code_vars is not None and not isinstance(code_vars, list):
            errors.append(NodeDataError(
                "warning",
                "Frontend: code node 'variables' must be an array for checkValid().",
                nid, "variables",
            ))
    return errors


def _fe_variable_assigner(node: Node) -> list[NodeDataError]:
    """variable-assigner/node.tsx:
    ``if (!advanced_settings?.group_enabled) { ... data.variables ... }``
    ``else { advanced_settings.groups.map(...) }``
    """
    errors: list[NodeDataError] = []
    nid = node.id
    adv = _get_field(node, "advanced_settings")
    if isinstance(adv, dict) and adv.get("group_enabled"):
        groups = adv.get("groups")
        if groups is None:
            errors.append(NodeDataError(
                "error",
                "Frontend crash: variable-assigner advanced_settings.group_enabled "
                "is true but 'groups' is missing. node.tsx calls groups.map().",
                nid, "advanced_settings.groups",
            ))
        elif not isinstance(groups, list):
            errors.append(NodeDataError(
                "error",
                "Frontend crash: variable-assigner advanced_settings.groups must be array.",
                nid, "advanced_settings.groups",
            ))
    return errors


def _fe_list_operator(node: Node) -> list[NodeDataError]:
    """list-operator/panel.tsx: ``inputs.filter_by.conditions[0]``
    Direct array index access without length check.
    """
    errors: list[NodeDataError] = []
    nid = node.id
    filter_by = _get_field(node, "filter_by")
    if isinstance(filter_by, dict):
        conditions = filter_by.get("conditions")
        if conditions is not None and not isinstance(conditions, list):
            errors.append(NodeDataError(
                "error",
                "Frontend crash: list-operator filter_by.conditions must be an array. "
                "panel.tsx accesses conditions[0] directly.",
                nid, "filter_by.conditions",
            ))
    return errors


def _fe_knowledge_retrieval(node: Node) -> list[NodeDataError]:
    """knowledge-retrieval/node.tsx: safe with optional chaining.
    knowledge-retrieval/utils.ts: ``selectedDatasets[0].embedding_model_provider``
    Crashes when datasets array is empty, but that's runtime data not DSL.
    """
    return []


def _fe_answer(node: Node) -> list[NodeDataError]:
    """answer/node.tsx: ``value={data.answer}`` — passes undefined safely."""
    return []


def _fe_http_request(node: Node) -> list[NodeDataError]:
    """http/node.tsx: ``const { method, url } = data; if (!url) return null``
    Safe — early return on missing url.
    But http/panel.tsx accesses body.type, authorization.type without null checks.
    """
    errors: list[NodeDataError] = []
    nid = node.id
    body = node.data.body or _get_field(node, "body")
    if isinstance(body, dict):
        if "type" not in body:
            errors.append(NodeDataError(
                "error",
                "Frontend crash: HTTP node 'body' missing 'type' field. "
                "Panel component accesses body.type without null check.",
                nid, "body.type",
            ))
    elif body is not None and not isinstance(body, dict):
        errors.append(NodeDataError(
            "error",
            "Frontend crash: HTTP node 'body' must be a dict with 'type' and 'data' fields.",
            nid, "body",
        ))
    authorization = _get_field(node, "authorization")
    if isinstance(authorization, dict):
        if "type" not in authorization:
            errors.append(NodeDataError(
                "error",
                "Frontend crash: HTTP node 'authorization' missing 'type' field. "
                "Panel component accesses authorization.type without null check.",
                nid, "authorization.type",
            ))
    return errors


def _fe_end(node: Node) -> list[NodeDataError]:
    """end/node.tsx accesses outputs array for rendering output mappings."""
    errors: list[NodeDataError] = []
    nid = node.id
    outputs = node.data.outputs
    if outputs is not None and not isinstance(outputs, list):
        errors.append(NodeDataError(
            "error",
            "Frontend crash: end node 'outputs' must be an array. "
            "node.tsx iterates outputs without type check.",
            nid, "outputs",
        ))
    return errors


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_FRONTEND_VALIDATORS: dict[NodeType, Any] = {
    NodeType.START: _fe_start,
    NodeType.END: _fe_end,
    NodeType.ANSWER: _fe_answer,
    NodeType.LLM: _fe_llm,
    NodeType.IF_ELSE: _fe_if_else,
    NodeType.QUESTION_CLASSIFIER: _fe_question_classifier,
    NodeType.PARAMETER_EXTRACTOR: _fe_parameter_extractor,
    NodeType.ITERATION: _fe_iteration,
    NodeType.LOOP: _fe_loop,
    NodeType.HUMAN_INPUT: _fe_human_input,
    NodeType.TOOL: _fe_tool,
    NodeType.CODE: _fe_code,
    NodeType.HTTP_REQUEST: _fe_http_request,
    NodeType.KNOWLEDGE_RETRIEVAL: _fe_knowledge_retrieval,
    NodeType.VARIABLE_AGGREGATOR: _fe_variable_assigner,  # same component
    NodeType.VARIABLE_ASSIGNER: _fe_variable_assigner,
    NodeType.LIST_OPERATOR: _fe_list_operator,
}
