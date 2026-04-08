"""Agent-specific validation rules.

Calls shared model_config validators (model, variables, prompt, dataset, features, agent_mode)
then applies agent-specific checks (enabled must be true, tools should be present).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..models import DifyDSL

if TYPE_CHECKING:
    from ..validator import ValidationResult


def _to_raw(dsl: DifyDSL) -> dict:
    """Convert ModelConfigContent to a raw dict for shared validators."""
    return dsl.model_config_content.model_dump(by_alias=True)  # type: ignore[union-attr]


def validate_agent_mode(dsl: DifyDSL, result: ValidationResult) -> None:
    """Validate agent-specific rules."""
    config = dsl.model_config_content
    if config is None:
        result.add_error("Agent app missing model_config section")
        return

    raw = _to_raw(dsl)

    # --- Shared validators (aligned with Dify's ConfigManager chain) ---
    from ..model_config_validators.model_validator import validate_model
    from ..model_config_validators.variables_validator import validate_user_input_form
    from ..model_config_validators.prompt_validator import validate_prompt
    from ..model_config_validators.agent_mode_validator import validate_agent_mode as validate_agent_mode_fields
    from ..model_config_validators.dataset_validator import validate_dataset_configs
    from ..model_config_validators.features_validator import validate_features

    validate_model(raw, result)
    validate_user_input_form(raw, result)
    validate_prompt(raw, result)
    validate_agent_mode_fields(raw, result)
    validate_dataset_configs(raw, result, is_completion=False)
    validate_features(raw, result, app_mode="agent-chat")

    # --- Agent-specific rules ---
    agent_mode_cfg = config.agent_mode

    if not isinstance(agent_mode_cfg, dict):
        result.add_error("Agent app missing agent_mode configuration")
        return

    if not agent_mode_cfg.get("enabled"):
        result.add_error(
            "Agent app has agent_mode.enabled=false — must be enabled for agent mode"
        )

    # Tools should be present for an agent to be useful
    tools = agent_mode_cfg.get("tools", [])
    if not tools:
        result.add_warning("Agent app has no tools configured")
