"""Completion-specific validation rules."""

from __future__ import annotations

from ..models import DifyDSL


def validate_completion_mode(dsl: DifyDSL, result) -> None:
    """Validate completion-specific rules."""
    config = dsl.model_config_content
    if config is None:
        result.add_error("Completion app missing model_config section")
        return

    # Model configuration
    model = config.model
    if not model:
        result.add_error("Completion app missing model configuration", field_name="model_config.model")
    elif not model.get("provider") or not model.get("name"):
        result.add_error(
            "Completion app model must specify provider and name",
            field_name="model_config.model",
        )

    # Pre-prompt required (should contain at least one variable reference)
    if not config.pre_prompt:
        result.add_warning("Completion app has no prompt template (pre_prompt)")

    # User input form recommended
    if not config.user_input_form:
        result.add_warning("Completion app has no user input variables (user_input_form)")

    # Conversation features should not be enabled
    if config.opening_statement:
        result.add_warning(
            "Completion mode does not support opening_statement (single-turn only)"
        )

    if isinstance(config.suggested_questions_after_answer, dict) and \
       config.suggested_questions_after_answer.get("enabled"):
        result.add_warning(
            "Completion mode does not support suggested_questions_after_answer"
        )
