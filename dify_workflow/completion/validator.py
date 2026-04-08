"""Completion-specific validation rules.

Calls shared model_config validators (model, variables, prompt, dataset, features)
then applies completion-specific checks (no opening_statement, more_like_this support).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..models import DifyDSL

if TYPE_CHECKING:
    from ..validator import ValidationResult


def _to_raw(dsl: DifyDSL) -> dict:
    """Convert ModelConfigContent to a raw dict for shared validators."""
    return dsl.model_config_content.model_dump(by_alias=True)  # type: ignore[union-attr]


def validate_completion_mode(dsl: DifyDSL, result: ValidationResult) -> None:
    """Validate completion-specific rules."""
    config = dsl.model_config_content
    if config is None:
        result.add_error("Completion app missing model_config section")
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
    validate_dataset_configs(raw, result, is_completion=True)
    validate_features(raw, result, app_mode="completion")

    # --- Completion-specific rules ---

    # Conversation features should not be enabled
    if config.opening_statement:
        result.add_warning(
            "Completion mode does not support opening_statement (single-turn only)"
        )

    sqa = config.suggested_questions_after_answer
    if isinstance(sqa, dict) and sqa.get("enabled"):
        result.add_warning(
            "Completion mode does not support suggested_questions_after_answer"
        )

    stt = config.speech_to_text
    if isinstance(stt, dict) and stt.get("enabled"):
        result.add_warning(
            "Completion mode does not support speech_to_text"
        )

    # User input form recommended
    if not config.user_input_form:
        result.add_warning(
            "Completion app has no user input variables (user_input_form)"
        )
