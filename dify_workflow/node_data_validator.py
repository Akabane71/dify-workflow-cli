"""Node-level data validation following Dify's official node data schemas.

Validates that each node's data fields match what Dify expects at import time
and runtime. Based on Dify's graphon node entities and workflow_service validation.

Key references:
  - graphon/nodes/*/entities.py  (per-node Pydantic models)
  - graphon/entities/base_node_data.py  (DefaultValue type validation)
  - api/services/workflow_service.py  (validate_graph_structure → _validate_human_input_node_data)
  - api/core/workflow/human_input_compat.py  (delivery_methods normalization)
"""

from __future__ import annotations

import json
import re
import uuid as _uuid
from typing import Any

from .models import Node, NodeType

# Valid identifier pattern for UserAction.id (same as graphon)
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Valid FormInput types
_FORM_INPUT_TYPES = frozenset({"text_input", "paragraph"})

# Valid ButtonStyle values
_BUTTON_STYLES = frozenset({"primary", "default", "accent", "ghost"})

# Valid TimeoutUnit values
_TIMEOUT_UNITS = frozenset({"hour", "day"})

# Valid delivery method types
_DELIVERY_METHOD_TYPES = frozenset({"webapp", "email"})

# Valid ParameterExtractor parameter types (graphon SegmentType values + legacy aliases)
_VALID_PARAMETER_TYPES = frozenset({
    "string", "number", "boolean",
    "array[string]", "array[number]", "array[object]", "array[boolean]",
    "bool",    # legacy alias for boolean
    "select",  # legacy alias for string (with options)
})

# Reserved parameter names in ParameterExtractor
_RESERVED_PARAMETER_NAMES = frozenset({"__reason", "__is_success"})

# Valid code output types (graphon _ALLOWED_OUTPUT_FROM_CODE)
_ALLOWED_CODE_OUTPUT_TYPES = frozenset({
    "string", "number", "object", "boolean",
    "array[string]", "array[number]", "array[object]", "array[boolean]",
})

# Valid loop variable types (graphon _VALID_VAR_TYPE)
_VALID_LOOP_VAR_TYPES = frozenset({
    "string", "number", "object", "boolean",
    "array[string]", "array[number]", "array[object]", "array[boolean]",
})

# Valid DefaultValue types (graphon DefaultValueType)
_VALID_DEFAULT_VALUE_TYPES = frozenset({
    "string", "number", "object",
    "array[number]", "array[string]", "array[object]", "array[file]",
})

# Valid VariableEntityType values for start node variables
_VALID_VARIABLE_ENTITY_TYPES = frozenset({
    "text-input", "select", "paragraph", "number",
    "external_data_tool", "file", "file-list", "checkbox", "json_object",
})

# Valid HTTP request body types
_VALID_HTTP_BODY_TYPES = frozenset({
    "none", "form-data", "x-www-form-urlencoded", "raw-text", "json", "binary",
})

# Valid HTTP auth types
_VALID_HTTP_AUTH_TYPES = frozenset({"no-auth", "api-key"})

# Valid HTTP auth config types
_VALID_HTTP_AUTH_CONFIG_TYPES = frozenset({"basic", "bearer", "custom"})

# Valid icon_type values
_VALID_ICON_TYPES = frozenset({"emoji", "image", "link"})

# Valid ToolProviderType values
_VALID_TOOL_PROVIDER_TYPES = frozenset({
    "plugin", "builtin", "workflow", "api", "app", "dataset-retrieval", "mcp",
})

# Valid ToolInput type values
_VALID_TOOL_INPUT_TYPES = frozenset({"mixed", "variable", "constant"})

# Min selector length for HumanInput FormInputDefault VARIABLE type
_SELECTORS_LENGTH = 2


def _extras(node: Node) -> dict[str, Any]:
    """Get pydantic extra fields for a node, safely."""
    return node.data.__pydantic_extra__ or {}


def _has_field(node: Node, field: str) -> bool:
    """Check if a node has a field (either typed or extra)."""
    if hasattr(node.data, field) and not field.startswith("_"):
        val = getattr(node.data, field)
        return val is not None
    return field in _extras(node)


def _get_field(node: Node, field: str, default: Any = None) -> Any:
    """Get a field from node data (typed or extra)."""
    if hasattr(node.data, field) and not field.startswith("_"):
        val = getattr(node.data, field)
        if val is not None:
            return val
    return _extras(node).get(field, default)


def _is_valid_uuid(value: str) -> bool:
    """Check if a string is a valid UUID."""
    try:
        _uuid.UUID(str(value))
        return True
    except (ValueError, AttributeError):
        return False


class NodeDataError:
    """A single node data validation issue."""
    __slots__ = ("level", "message", "node_id", "field")

    def __init__(self, level: str, message: str, node_id: str, field: str | None = None):
        self.level = level
        self.message = message
        self.node_id = node_id
        self.field = field


def validate_node_data(node: Node) -> list[NodeDataError]:
    """Validate a node's data fields match Dify's requirements.

    Returns a list of NodeDataError objects.
    Checks required fields, type constraints, and structural rules
    per Dify's official node data schemas.
    """
    errors: list[NodeDataError] = []

    # Base node data validation (applies to ALL node types)
    errors.extend(_validate_base_node_data(node))

    # Per-node-type validation
    validator = _NODE_VALIDATORS.get(node.data.type)
    if validator is not None:
        errors.extend(validator(node))
    return errors


def _validate_base_node_data(node: Node) -> list[NodeDataError]:
    """Validate fields from BaseNodeData that apply to all node types.

    Mirrors graphon/entities/base_node_data.py:
    - error_strategy enum
    - default_value type validation (DefaultValue.validate_value_type)
    """
    errors: list[NodeDataError] = []
    nid = node.id

    # error_strategy validation
    error_strategy = _get_field(node, "error_strategy")
    if error_strategy is not None and error_strategy not in ("fail-branch", "default-value"):
        errors.append(NodeDataError(
            "error",
            f"Invalid error_strategy: {error_strategy!r} (must be 'fail-branch' or 'default-value')",
            nid, "error_strategy",
        ))

    # default_value type validation (graphon DefaultValue.validate_value_type model_validator)
    default_values = _get_field(node, "default_value")
    if isinstance(default_values, list):
        for i, dv in enumerate(default_values):
            if isinstance(dv, dict):
                dv_type = dv.get("type")
                dv_value = dv.get("value")
                dv_key = dv.get("key")

                if not dv_key:
                    errors.append(NodeDataError(
                        "error", f"default_value[{i}] missing 'key'",
                        nid, f"default_value[{i}].key",
                    ))
                if dv_type and dv_type not in _VALID_DEFAULT_VALUE_TYPES:
                    errors.append(NodeDataError(
                        "error",
                        f"default_value[{i}] invalid type: {dv_type!r}",
                        nid, f"default_value[{i}].type",
                    ))
                elif dv_type and dv_value is not None:
                    errors.extend(_validate_default_value_type(dv_type, dv_value, i, nid))

    return errors


def _validate_default_value_type(
    dv_type: str, dv_value: Any, index: int, nid: str,
) -> list[NodeDataError]:
    """Validate DefaultValue.value matches its declared type.

    Mirrors graphon DefaultValue.validate_value_type model_validator.
    """
    errors: list[NodeDataError] = []
    prefix = f"default_value[{index}]"

    if dv_type == "string":
        if not isinstance(dv_value, str):
            errors.append(NodeDataError("error", f"{prefix} value must be string for type 'string'", nid, f"{prefix}.value"))
    elif dv_type == "number":
        if not isinstance(dv_value, (int, float)) and not _is_number_string(dv_value):
            errors.append(NodeDataError("error", f"{prefix} value must be number for type 'number'", nid, f"{prefix}.value"))
    elif dv_type == "object":
        if not isinstance(dv_value, dict) and not _is_json_string(dv_value):
            errors.append(NodeDataError("error", f"{prefix} value must be object/dict for type 'object'", nid, f"{prefix}.value"))
    elif dv_type.startswith("array["):
        if isinstance(dv_value, str):
            if not _is_json_string(dv_value):
                errors.append(NodeDataError("error", f"{prefix} value must be array or valid JSON string for type '{dv_type}'", nid, f"{prefix}.value"))
        elif not isinstance(dv_value, list):
            errors.append(NodeDataError("error", f"{prefix} value must be array for type '{dv_type}'", nid, f"{prefix}.value"))

    return errors


def _is_number_string(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        float(value)
        return True
    except ValueError:
        return False


def _is_json_string(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        json.loads(value)
        return True
    except (json.JSONDecodeError, ValueError):
        return False


# --- Per-node-type validators ---
# Each returns list[NodeDataError]. Mirrors graphon entity requirements.


def _validate_start(node: Node) -> list[NodeDataError]:
    errors: list[NodeDataError] = []
    variables = node.data.variables or []
    seen: set[str] = set()
    for i, v in enumerate(variables):
        var_name = v.variable
        if var_name in seen:
            errors.append(NodeDataError("error", f"Duplicate start variable: {var_name}", node.id, f"variables[{i}].variable"))
        seen.add(var_name)

        # Validate variable type (graphon VariableEntityType)
        var_type = v.type
        if var_type and str(var_type) not in _VALID_VARIABLE_ENTITY_TYPES:
            errors.append(NodeDataError(
                "error",
                f"Start variable '{var_name}' invalid type: {var_type!r}",
                node.id, f"variables[{i}].type",
            ))

    return errors


def _validate_end(node: Node) -> list[NodeDataError]:
    errors: list[NodeDataError] = []
    outputs = node.data.outputs
    if outputs is None:
        errors.append(NodeDataError("error", "End node missing 'outputs' field", node.id, "outputs"))
    elif isinstance(outputs, list):
        for i, out in enumerate(outputs):
            if isinstance(out, dict):
                if not out.get("variable", "").strip():
                    errors.append(NodeDataError("error", f"End node outputs[{i}] missing variable name", node.id, f"outputs[{i}].variable"))
                vs = out.get("value_selector")
                if not vs or not isinstance(vs, list) or not any(vs):
                    errors.append(NodeDataError("error", f"End node outputs[{i}] missing value_selector", node.id, f"outputs[{i}].value_selector"))
            elif hasattr(out, "variable"):
                if not getattr(out, "variable", "").strip():
                    errors.append(NodeDataError("error", f"End node outputs[{i}] missing variable name", node.id, f"outputs[{i}].variable"))
                vs = getattr(out, "value_selector", [])
                if not vs or not isinstance(vs, list) or not any(vs):
                    errors.append(NodeDataError("error", f"End node outputs[{i}] missing value_selector", node.id, f"outputs[{i}].value_selector"))
    return errors


def _validate_answer(node: Node) -> list[NodeDataError]:
    errors: list[NodeDataError] = []
    answer = _get_field(node, "answer")
    if answer is None:
        errors.append(NodeDataError("error", "Answer node missing 'answer' field", node.id, "answer"))
    return errors


def _validate_llm(node: Node) -> list[NodeDataError]:
    errors: list[NodeDataError] = []
    model = node.data.model
    if model is None:
        errors.append(NodeDataError("error", "LLM node missing 'model' configuration", node.id, "model"))
    else:
        provider = getattr(model, "provider", None) if not isinstance(model, dict) else model.get("provider")
        if not provider:
            errors.append(NodeDataError("warning", "LLM node model missing 'provider'", node.id, "model.provider"))
    prompt = node.data.prompt_template
    if not prompt:
        errors.append(NodeDataError("warning", "LLM node has empty prompt template", node.id, "prompt_template"))
    elif isinstance(prompt, list):
        has_content = any(
            (p.get("text", "") if isinstance(p, dict) else getattr(p, "text", ""))
            or (p.get("jinja2_text", "") if isinstance(p, dict) else getattr(p, "jinja2_text", ""))
            for p in prompt
        )
        if not has_content:
            errors.append(NodeDataError("warning", "LLM node prompt template has no content", node.id, "prompt_template"))
    context = node.data.context or _get_field(node, "context")
    if context is None:
        errors.append(NodeDataError("warning", "LLM node missing 'context' configuration", node.id, "context"))
    return errors


def _validate_if_else(node: Node) -> list[NodeDataError]:
    errors: list[NodeDataError] = []
    cases = node.data.cases
    if not cases:
        errors.append(NodeDataError("error", "IF/ELSE node has no cases defined", node.id, "cases"))
    elif isinstance(cases, list):
        for i, case in enumerate(cases):
            if isinstance(case, dict):
                conditions = case.get("conditions")
                case_id = case.get("case_id")
            else:
                conditions = getattr(case, "conditions", None)
                case_id = getattr(case, "case_id", None)
            if not case_id:
                errors.append(NodeDataError("error", f"IF/ELSE cases[{i}] missing 'case_id'", node.id, f"cases[{i}].case_id"))
            if conditions is None:
                errors.append(NodeDataError("error", f"IF/ELSE cases[{i}] missing 'conditions' array", node.id, f"cases[{i}].conditions"))
            elif isinstance(conditions, list):
                for j, cond in enumerate(conditions):
                    if isinstance(cond, dict):
                        vs = cond.get("variable_selector", [])
                        op = cond.get("comparison_operator", "")
                    else:
                        vs = getattr(cond, "variable_selector", [])
                        op = getattr(cond, "comparison_operator", "")
                    if not vs or (isinstance(vs, list) and not any(vs)):
                        errors.append(NodeDataError("warning", f"IF/ELSE cases[{i}].conditions[{j}] missing variable_selector", node.id, f"cases[{i}].conditions[{j}].variable_selector"))
                    if not op:
                        errors.append(NodeDataError("warning", f"IF/ELSE cases[{i}].conditions[{j}] missing comparison_operator", node.id, f"cases[{i}].conditions[{j}].comparison_operator"))
    return errors


# --- Import validators from split modules ---
# These imports happen AFTER all shared constants/helpers/classes are defined,
# so the circular import (ext modules importing from this file) is safe.

from .node_validators_core import (  # noqa: E402
    _validate_code,
    _validate_document_extractor,
    _validate_http_request,
    _validate_iteration,
    _validate_knowledge_retrieval,
    _validate_list_operator,
    _validate_loop,
    _validate_parameter_extractor,
    _validate_question_classifier,
    _validate_template_transform,
    _validate_tool,
    _validate_variable_aggregator,
    _validate_variable_assigner,
)
from .node_validators_extra import (  # noqa: E402
    _validate_agent,
    _validate_datasource,
    _validate_human_input,
    _validate_knowledge_index,
    _validate_trigger_plugin,
    _validate_trigger_schedule,
    _validate_trigger_webhook,
)

# Dispatch table
_NODE_VALIDATORS = {
    NodeType.START: _validate_start,
    NodeType.END: _validate_end,
    NodeType.ANSWER: _validate_answer,
    NodeType.LLM: _validate_llm,
    NodeType.CODE: _validate_code,
    NodeType.IF_ELSE: _validate_if_else,
    NodeType.TEMPLATE_TRANSFORM: _validate_template_transform,
    NodeType.HTTP_REQUEST: _validate_http_request,
    NodeType.TOOL: _validate_tool,
    NodeType.KNOWLEDGE_RETRIEVAL: _validate_knowledge_retrieval,
    NodeType.QUESTION_CLASSIFIER: _validate_question_classifier,
    NodeType.PARAMETER_EXTRACTOR: _validate_parameter_extractor,
    NodeType.VARIABLE_AGGREGATOR: _validate_variable_aggregator,
    NodeType.VARIABLE_ASSIGNER: _validate_variable_assigner,
    NodeType.LIST_OPERATOR: _validate_list_operator,
    NodeType.ITERATION: _validate_iteration,
    NodeType.LOOP: _validate_loop,
    NodeType.AGENT: _validate_agent,
    NodeType.DOCUMENT_EXTRACTOR: _validate_document_extractor,
    NodeType.HUMAN_INPUT: _validate_human_input,
    NodeType.KNOWLEDGE_INDEX: _validate_knowledge_index,
    NodeType.DATASOURCE: _validate_datasource,
    NodeType.TRIGGER_WEBHOOK: _validate_trigger_webhook,
    NodeType.TRIGGER_SCHEDULE: _validate_trigger_schedule,
    NodeType.TRIGGER_PLUGIN: _validate_trigger_plugin,
}


# ──────────────────────────────────────────────────────────────────
# DSL-level validation (version, app, environment variables, etc.)
# These are NOT node-level checks — called from the top-level validator.
# ──────────────────────────────────────────────────────────────────

CURRENT_DSL_VERSION = "0.6.0"


def validate_dsl_metadata(dsl) -> list[NodeDataError]:
    """Validate DSL-level metadata that Dify checks at import.

    Covers:
    - Version compatibility (semver comparison)
    - version type check (must be str)
    - icon_type enum
    - environment_variables structure
    - conversation_variables structure
    """
    from .models import CURRENT_DSL_VERSION as _CDV
    errors: list[NodeDataError] = []

    # version must be string type (app_dsl_service.py line 216-217)
    version = dsl.version
    if version and not isinstance(version, str):
        errors.append(NodeDataError(
            "error", f"DSL version must be a string, got {type(version).__name__}",
            "", "version",
        ))

    # Version compatibility warning (app_dsl_service.py line 83-101)
    if isinstance(version, str) and version:
        try:
            imported_parts = [int(x) for x in version.split(".")]
            current_parts = [int(x) for x in _CDV.split(".")]
            if imported_parts[:2] > current_parts[:2]:
                errors.append(NodeDataError(
                    "warning",
                    f"DSL version {version} is newer than current supported version {_CDV}",
                    "", "version",
                ))
        except (ValueError, AttributeError):
            errors.append(NodeDataError(
                "warning", f"DSL version {version!r} is not a valid semver",
                "", "version",
            ))

    # icon_type validation (app_dsl_service.py line 442-446)
    icon_type = dsl.app.icon_type
    if icon_type and icon_type not in _VALID_ICON_TYPES:
        errors.append(NodeDataError(
            "warning",
            f"App icon_type {icon_type!r} is not valid (must be 'emoji', 'image', or 'link')",
            "", "app.icon_type",
        ))

    # environment_variables validation (variable_factory.py)
    if hasattr(dsl, "workflow") and dsl.workflow:
        for i, ev in enumerate(dsl.workflow.environment_variables):
            if not ev.name:
                errors.append(NodeDataError(
                    "error", f"environment_variables[{i}] missing 'name'",
                    "", f"environment_variables[{i}].name",
                ))
            if ev.value_type and ev.value_type not in ("string", "number", "secret"):
                errors.append(NodeDataError(
                    "warning",
                    f"environment_variables[{i}] unusual value_type: {ev.value_type!r}",
                    "", f"environment_variables[{i}].value_type",
                ))

        # conversation_variables validation
        for i, cv in enumerate(dsl.workflow.conversation_variables):
            if isinstance(cv, dict):
                if not cv.get("name"):
                    errors.append(NodeDataError(
                        "error", f"conversation_variables[{i}] missing 'name'",
                        "", f"conversation_variables[{i}].name",
                    ))
                if not cv.get("value_type"):
                    errors.append(NodeDataError(
                        "warning", f"conversation_variables[{i}] missing 'value_type'",
                        "", f"conversation_variables[{i}].value_type",
                    ))

    return errors
