"""Validate model_config.agent_mode — aligns with Dify's AgentChatAppConfigManager.

Checks:
  - agent_mode.enabled is a boolean
  - agent_mode.strategy is one of: router, react-router, react, function_call
  - agent_mode.tools is a list
  - Each tool (new format) has provider_type, provider_id, tool_name, tool_parameters
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..validator import ValidationResult

_FIELD_PREFIX = "model_config.agent_mode"

_VALID_STRATEGIES = frozenset({
    "router", "react-router", "react", "function_call",
})

# Legacy tool keys that use the old dict-of-dicts format
_LEGACY_TOOL_KEYS = frozenset({
    "dataset", "google_search", "web_reader", "wikipedia", "current_datetime",
})


def validate_agent_mode(
    model_config: dict[str, Any],
    result: ValidationResult,
) -> None:
    """Validate the ``agent_mode`` section inside model_config."""
    agent_mode = model_config.get("agent_mode")
    if not agent_mode:
        return

    if not isinstance(agent_mode, dict):
        result.add_error(
            "agent_mode must be a dict",
            field_name=_FIELD_PREFIX,
        )
        return

    # enabled
    enabled = agent_mode.get("enabled")
    if enabled is not None and not isinstance(enabled, bool):
        result.add_error(
            "agent_mode.enabled must be a boolean",
            field_name=f"{_FIELD_PREFIX}.enabled",
        )

    # strategy
    strategy = agent_mode.get("strategy", "")
    if strategy and strategy not in _VALID_STRATEGIES:
        result.add_error(
            f"agent_mode.strategy must be one of "
            f"{sorted(_VALID_STRATEGIES)}, got '{strategy}'",
            field_name=f"{_FIELD_PREFIX}.strategy",
        )

    # tools
    tools = agent_mode.get("tools")
    if tools is None:
        return

    if not isinstance(tools, list):
        result.add_error(
            "agent_mode.tools must be a list",
            field_name=f"{_FIELD_PREFIX}.tools",
        )
        return

    for idx, tool in enumerate(tools):
        if not isinstance(tool, dict):
            result.add_error(
                f"agent_mode.tools[{idx}] must be a dict",
                field_name=f"{_FIELD_PREFIX}.tools[{idx}]",
            )
            continue

        _validate_tool_entry(tool, idx, result)


def _validate_tool_entry(
    tool: dict[str, Any],
    idx: int,
    result: ValidationResult,
) -> None:
    """Validate a single tool entry in agent_mode.tools."""
    prefix = f"{_FIELD_PREFIX}.tools[{idx}]"

    # Skip legacy tool format (dict with known keys like "dataset", "google_search")
    if any(k in tool for k in _LEGACY_TOOL_KEYS):
        return

    # New-format tool: requires provider_type (or tool_type), provider_id, tool_name, tool_parameters
    # Dify uses provider_type; the CLI editor historically uses tool_type — accept both.
    provider_type = tool.get("provider_type") or tool.get("tool_type")
    if not provider_type:
        result.add_error(
            f"agent_mode.tools[{idx}].provider_type is required",
            field_name=f"{prefix}.provider_type",
        )
    for field_name in ("provider_id", "tool_name"):
        value = tool.get(field_name)
        if not value:
            result.add_error(
                f"agent_mode.tools[{idx}].{field_name} is required",
                field_name=f"{prefix}.{field_name}",
            )

    # tool_parameters must be present and be a dict
    params = tool.get("tool_parameters")
    if params is None:
        result.add_error(
            f"agent_mode.tools[{idx}].tool_parameters is required",
            field_name=f"{prefix}.tool_parameters",
        )
    elif not isinstance(params, dict):
        result.add_error(
            f"agent_mode.tools[{idx}].tool_parameters must be a dict",
            field_name=f"{prefix}.tool_parameters",
        )
