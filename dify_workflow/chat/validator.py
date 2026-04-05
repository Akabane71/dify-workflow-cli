"""Chat-specific validation rules."""

from __future__ import annotations

from ..models import DifyDSL


def validate_chat_mode(dsl: DifyDSL, result) -> None:
    """Validate chat-specific rules (model_config structure)."""
    config = dsl.model_config_content
    if config is None:
        result.add_error("Chat app missing model_config section")
        return

    # Model configuration
    model = config.model
    if not model:
        result.add_error("Chat app missing model configuration", field_name="model_config.model")
    elif not model.get("provider") or not model.get("name"):
        result.add_error(
            "Chat app model must specify provider and name",
            field_name="model_config.model",
        )

    # Pre-prompt recommended
    if not config.pre_prompt:
        result.add_warning("Chat app has no system prompt (pre_prompt)")

    # Agent mode should be disabled for plain chat
    agent_mode = config.agent_mode
    if isinstance(agent_mode, dict) and agent_mode.get("enabled"):
        result.add_warning(
            "Chat app has agent_mode enabled. Consider using agent-chat mode instead."
        )
