"""Chat-specific validation rules.

Calls shared model_config validators (model, variables, prompt, dataset, features)
then applies chat-specific checks (opening_statement, suggested_questions, agent_mode).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..models import DifyDSL

if TYPE_CHECKING:
    from ..validator import ValidationResult


def _to_raw(dsl: DifyDSL) -> dict:
    """Convert ModelConfigContent to a raw dict for shared validators."""
    return dsl.model_config_content.model_dump(by_alias=True)  # type: ignore[union-attr]


def validate_chat_mode(dsl: DifyDSL, result: ValidationResult) -> None:
    """Validate chat-specific rules (model_config structure)."""
    config = dsl.model_config_content
    if config is None:
        result.add_error("Chat app missing model_config section")
        return

    raw = _to_raw(dsl)

    # --- Shared validators (aligned with Dify's ConfigManager chain) ---
    from ..model_config_validators.model_validator import validate_model
    from ..model_config_validators.variables_validator import validate_user_input_form
    from ..model_config_validators.prompt_validator import validate_prompt
    from ..model_config_validators.dataset_validator import validate_dataset_configs
    from ..model_config_validators.features_validator import validate_features

    validate_model(raw, result)
    validate_user_input_form(raw, result)
    validate_prompt(raw, result)
    validate_dataset_configs(raw, result, is_completion=False)
    validate_features(raw, result, app_mode="chat")

    # --- Chat-specific rules ---

    # opening_statement type check
    opening = config.opening_statement
    if opening is not None and not isinstance(opening, str):
        result.add_error(
            "opening_statement must be a string",
            field_name="model_config.opening_statement",
        )

    # suggested_questions type check
    sq = config.suggested_questions
    if sq is not None and not isinstance(sq, list):
        result.add_error(
            "suggested_questions must be a list",
            field_name="model_config.suggested_questions",
        )

    # Agent mode should be disabled for plain chat
    agent_mode = config.agent_mode
    if isinstance(agent_mode, dict) and agent_mode.get("enabled"):
        result.add_warning(
            "Chat app has agent_mode enabled. Consider using agent-chat mode instead."
        )
