"""Agent-specific validation rules."""

from __future__ import annotations

from ..models import DifyDSL


def validate_agent_mode(dsl: DifyDSL, result) -> None:
    """Validate agent-specific rules."""
    config = dsl.model_config_content
    if config is None:
        result.add_error("Agent app missing model_config section")
        return

    # Model configuration
    model = config.model
    if not model:
        result.add_error("Agent app missing model configuration", field_name="model_config.model")
    elif not model.get("provider") or not model.get("name"):
        result.add_error(
            "Agent app model must specify provider and name",
            field_name="model_config.model",
        )

    # Agent mode must be enabled
    agent_mode = config.agent_mode
    if not isinstance(agent_mode, dict):
        result.add_error("Agent app missing agent_mode configuration")
        return

    if not agent_mode.get("enabled"):
        result.add_error("Agent app must have agent_mode.enabled=true")

    # Strategy validation
    strategy = agent_mode.get("strategy", "")
    if strategy not in ("function_call", "react"):
        result.add_error(
            f"Agent strategy must be 'function_call' or 'react', got '{strategy}'",
            field_name="model_config.agent_mode.strategy",
        )

    # Tools check
    tools = agent_mode.get("tools", [])
    if not tools:
        result.add_warning("Agent app has no tools configured")

    # Pre-prompt recommended
    if not config.pre_prompt:
        result.add_warning("Agent app has no system prompt (pre_prompt)")
