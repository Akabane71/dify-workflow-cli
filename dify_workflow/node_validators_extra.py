"""Node data validators for advanced node types.

Covers: human_input, agent, datasource, knowledge_index, triggers.
"""

from __future__ import annotations

from .models import Node
from .node_data_validator import (
    NodeDataError,
    _get_field,
    _is_valid_uuid,
    _BUTTON_STYLES,
    _DELIVERY_METHOD_TYPES,
    _FORM_INPUT_TYPES,
    _IDENTIFIER_PATTERN,
    _SELECTORS_LENGTH,
    _TIMEOUT_UNITS,
)


def _validate_human_input(node: Node) -> list[NodeDataError]:
    """Validate HumanInput node data — this is the ONLY node Dify validates at import time.

    Mirrors Dify's _validate_human_input_node_data() which calls
    HumanInputNodeData.model_validate() from graphon.
    """
    errors: list[NodeDataError] = []
    nid = node.id

    # --- inputs validation ---
    inputs = _get_field(node, "inputs", [])
    if isinstance(inputs, list):
        seen_output_var_names: set[str] = set()
        for i, inp in enumerate(inputs):
            if isinstance(inp, dict):
                # output_variable_name is REQUIRED
                ovn = inp.get("output_variable_name")
                if not ovn:
                    errors.append(NodeDataError(
                        "error",
                        f"HumanInput inputs[{i}] missing required 'output_variable_name' field",
                        nid, f"inputs[{i}].output_variable_name",
                    ))
                else:
                    if ovn in seen_output_var_names:
                        errors.append(NodeDataError(
                            "error",
                            f"HumanInput duplicate output_variable_name: {ovn!r}",
                            nid, f"inputs[{i}].output_variable_name",
                        ))
                    seen_output_var_names.add(ovn)

                # type must be valid
                inp_type = inp.get("type")
                if inp_type and inp_type not in _FORM_INPUT_TYPES:
                    errors.append(NodeDataError(
                        "error",
                        f"HumanInput inputs[{i}] invalid type: {inp_type!r} (must be 'text_input' or 'paragraph')",
                        nid, f"inputs[{i}].type",
                    ))

                # default.selector validation (graphon FormInputDefault._validate_selector)
                inp_default = inp.get("default")
                if isinstance(inp_default, dict):
                    default_type = inp_default.get("type")
                    if default_type == "variable":
                        selector = inp_default.get("selector", [])
                        if isinstance(selector, (list, tuple)) and len(selector) < _SELECTORS_LENGTH:
                            errors.append(NodeDataError(
                                "error",
                                f"HumanInput inputs[{i}].default selector length must be at least {_SELECTORS_LENGTH}",
                                nid, f"inputs[{i}].default.selector",
                            ))

    # --- user_actions validation ---
    user_actions = _get_field(node, "user_actions", [])
    if isinstance(user_actions, list):
        seen_action_ids: set[str] = set()
        for i, action in enumerate(user_actions):
            if isinstance(action, dict):
                aid = action.get("id", "")
                if not aid:
                    errors.append(NodeDataError("error", f"HumanInput user_actions[{i}] missing 'id'", nid, f"user_actions[{i}].id"))
                else:
                    if len(aid) > 20:
                        errors.append(NodeDataError(
                            "error",
                            f"HumanInput user_actions[{i}].id too long (max 20 chars)",
                            nid, f"user_actions[{i}].id",
                        ))
                    if not _IDENTIFIER_PATTERN.match(aid):
                        errors.append(NodeDataError(
                            "error",
                            f"HumanInput user_actions[{i}].id must be a valid identifier (letters/digits/underscores, start with letter or underscore)",
                            nid, f"user_actions[{i}].id",
                        ))
                    if aid in seen_action_ids:
                        errors.append(NodeDataError(
                            "error",
                            f"HumanInput duplicate user_action id: {aid!r}",
                            nid, f"user_actions[{i}].id",
                        ))
                    seen_action_ids.add(aid)

                title = action.get("title", "")
                if title and len(title) > 20:
                    errors.append(NodeDataError(
                        "warning",
                        f"HumanInput user_actions[{i}].title too long (max 20 chars)",
                        nid, f"user_actions[{i}].title",
                    ))

                style = action.get("button_style")
                if style and style not in _BUTTON_STYLES:
                    errors.append(NodeDataError(
                        "error",
                        f"HumanInput user_actions[{i}] invalid button_style: {style!r}",
                        nid, f"user_actions[{i}].button_style",
                    ))

    # --- delivery_methods validation ---
    delivery_methods = _get_field(node, "delivery_methods", [])
    if isinstance(delivery_methods, list):
        for i, dm in enumerate(delivery_methods):
            if isinstance(dm, dict):
                dm_type = dm.get("type")
                if dm_type and dm_type not in _DELIVERY_METHOD_TYPES:
                    errors.append(NodeDataError(
                        "error",
                        f"HumanInput delivery_methods[{i}] invalid type: {dm_type!r} (must be 'webapp' or 'email')",
                        nid, f"delivery_methods[{i}].type",
                    ))

                dm_id = dm.get("id")
                if dm_id is not None and not _is_valid_uuid(dm_id):
                    errors.append(NodeDataError(
                        "error",
                        f"HumanInput delivery_methods[{i}].id must be a valid UUID, got: {dm_id!r}",
                        nid, f"delivery_methods[{i}].id",
                    ))

                # Email type requires config with recipients, subject, body
                if dm_type == "email":
                    config = dm.get("config", {})
                    if isinstance(config, dict):
                        for req_field in ("recipients", "subject", "body"):
                            if req_field not in config:
                                errors.append(NodeDataError(
                                    "error",
                                    f"HumanInput delivery_methods[{i}] email config missing '{req_field}'",
                                    nid, f"delivery_methods[{i}].config.{req_field}",
                                ))

    # --- timeout validation ---
    timeout_unit = _get_field(node, "timeout_unit")
    if timeout_unit and timeout_unit not in _TIMEOUT_UNITS:
        errors.append(NodeDataError(
            "error",
            f"HumanInput invalid timeout_unit: {timeout_unit!r} (must be 'hour' or 'day')",
            nid, "timeout_unit",
        ))

    return errors


def _validate_agent(node: Node) -> list[NodeDataError]:
    errors: list[NodeDataError] = []
    for field in ("agent_strategy_provider_name", "agent_strategy_name", "agent_strategy_label"):
        if not _get_field(node, field):
            errors.append(NodeDataError("warning", f"Agent node missing '{field}'", node.id, field))
    if _get_field(node, "agent_parameters") is None:
        errors.append(NodeDataError("warning", "Agent node missing 'agent_parameters'", node.id, "agent_parameters"))
    return errors


def _validate_datasource(node: Node) -> list[NodeDataError]:
    errors: list[NodeDataError] = []
    for field in ("plugin_id", "provider_name", "provider_type"):
        if not _get_field(node, field):
            errors.append(NodeDataError("warning", f"Datasource node missing '{field}'", node.id, field))
    return errors


def _validate_knowledge_index(node: Node) -> list[NodeDataError]:
    errors: list[NodeDataError] = []
    # Knowledge Index has minimal required fields in Dify
    return errors


def _validate_trigger_webhook(node: Node) -> list[NodeDataError]:
    return []


def _validate_trigger_schedule(node: Node) -> list[NodeDataError]:
    return []


def _validate_trigger_plugin(node: Node) -> list[NodeDataError]:
    errors: list[NodeDataError] = []
    for field in ("plugin_id", "provider_id", "event_name"):
        if not _get_field(node, field):
            errors.append(NodeDataError("warning", f"Trigger Plugin missing '{field}'", node.id, field))
    return errors
