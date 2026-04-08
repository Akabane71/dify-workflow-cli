"""Validate prompt_type and prompt config — aligns with Dify's PromptTemplateConfigManager.

Checks:
  - prompt_type is "simple" or "advanced"
  - Simple mode: pre_prompt should be non-empty (warning)
  - Advanced mode: requires chat_prompt_config or completion_prompt_config
  - chat_prompt_config.prompt has at most 10 messages
  - Each message has text and role (user/assistant/system)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..validator import ValidationResult

_FIELD_PREFIX = "model_config"

_VALID_PROMPT_TYPES = frozenset({"simple", "advanced"})
_VALID_ROLES = frozenset({"user", "assistant", "system"})
_MAX_CHAT_PROMPT_MESSAGES = 10


def validate_prompt(
    model_config: dict[str, Any],
    result: ValidationResult,
) -> None:
    """Validate prompt_type and related prompt configuration."""
    prompt_type = model_config.get("prompt_type", "simple")

    if prompt_type not in _VALID_PROMPT_TYPES:
        result.add_error(
            f"prompt_type must be 'simple' or 'advanced', got '{prompt_type}'",
            field_name=f"{_FIELD_PREFIX}.prompt_type",
        )
        return

    has_chat_prompt = _validate_present_chat_prompt_config(model_config, result)
    has_completion_prompt = _validate_present_completion_prompt_config(model_config, result)

    if prompt_type == "simple":
        _validate_simple_prompt(model_config, result)
    else:
        _validate_advanced_prompt(has_chat_prompt, has_completion_prompt, result)


def _validate_simple_prompt(
    model_config: dict[str, Any],
    result: ValidationResult,
) -> None:
    """Check simple mode: pre_prompt should be non-empty."""
    pre_prompt = model_config.get("pre_prompt", "")
    if not pre_prompt:
        result.add_warning(
            "pre_prompt is empty — model will have no system prompt",
            field_name=f"{_FIELD_PREFIX}.pre_prompt",
        )


def _validate_advanced_prompt(
    has_chat_prompt: bool,
    has_completion_prompt: bool,
    result: ValidationResult,
) -> None:
    """Check advanced mode: must have chat or completion prompt config."""
    if not has_chat_prompt and not has_completion_prompt:
        result.add_error(
            "Advanced prompt_type requires chat_prompt_config or "
            "completion_prompt_config with non-empty prompt",
            field_name=f"{_FIELD_PREFIX}.chat_prompt_config",
        )


def _validate_present_chat_prompt_config(
    model_config: dict[str, Any],
    result: ValidationResult,
) -> bool:
    """Validate chat_prompt_config shape when the key is present."""
    if "chat_prompt_config" not in model_config:
        return False

    config = model_config.get("chat_prompt_config")
    if not isinstance(config, dict):
        result.add_error(
            "chat_prompt_config must be a dict",
            field_name=f"{_FIELD_PREFIX}.chat_prompt_config",
        )
        return False

    if "prompt" not in config:
        result.add_error(
            "chat_prompt_config must contain a prompt list when present",
            field_name=f"{_FIELD_PREFIX}.chat_prompt_config.prompt",
        )
        return False

    _validate_chat_prompt_config(config, result)
    return bool(config.get("prompt"))


def _validate_present_completion_prompt_config(
    model_config: dict[str, Any],
    result: ValidationResult,
) -> bool:
    """Validate completion_prompt_config shape when the key is present."""
    if "completion_prompt_config" not in model_config:
        return False

    config = model_config.get("completion_prompt_config")
    if not isinstance(config, dict):
        result.add_error(
            "completion_prompt_config must be a dict",
            field_name=f"{_FIELD_PREFIX}.completion_prompt_config",
        )
        return False

    if "prompt" not in config:
        result.add_error(
            "completion_prompt_config must contain a prompt object when present",
            field_name=f"{_FIELD_PREFIX}.completion_prompt_config.prompt",
        )
        return False

    _validate_completion_prompt_config(config, result)
    return bool(config.get("prompt"))


def _validate_chat_prompt_config(
    config: dict[str, Any],
    result: ValidationResult,
) -> None:
    """Validate chat_prompt_config.prompt messages."""
    messages = config.get("prompt", [])
    if not isinstance(messages, list):
        result.add_error(
            "chat_prompt_config.prompt must be a list of messages",
            field_name=f"{_FIELD_PREFIX}.chat_prompt_config.prompt",
        )
        return

    if len(messages) > _MAX_CHAT_PROMPT_MESSAGES:
        result.add_error(
            f"chat_prompt_config.prompt has {len(messages)} messages "
            f"(max {_MAX_CHAT_PROMPT_MESSAGES})",
            field_name=f"{_FIELD_PREFIX}.chat_prompt_config.prompt",
        )

    for idx, msg in enumerate(messages):
        if not isinstance(msg, dict):
            result.add_error(
                f"chat_prompt_config.prompt[{idx}] must be a dict",
                field_name=f"{_FIELD_PREFIX}.chat_prompt_config.prompt[{idx}]",
            )
            continue

        role = msg.get("role")
        if role not in _VALID_ROLES:
            result.add_error(
                f"chat_prompt_config.prompt[{idx}].role must be "
                f"user/assistant/system, got '{role}'",
                field_name=f"{_FIELD_PREFIX}.chat_prompt_config.prompt[{idx}].role",
            )

        text = msg.get("text")
        if text is None:
            result.add_error(
                f"chat_prompt_config.prompt[{idx}].text is required",
                field_name=f"{_FIELD_PREFIX}.chat_prompt_config.prompt[{idx}].text",
            )


def _validate_completion_prompt_config(
    config: dict[str, Any],
    result: ValidationResult,
) -> None:
    """Validate completion_prompt_config.prompt structure."""
    prompt = config.get("prompt")
    if not isinstance(prompt, dict):
        result.add_error(
            "completion_prompt_config.prompt must be a dict with 'text' key",
            field_name=f"{_FIELD_PREFIX}.completion_prompt_config.prompt",
        )
        return

    if "text" not in prompt:
        result.add_error(
            "completion_prompt_config.prompt.text is required",
            field_name=f"{_FIELD_PREFIX}.completion_prompt_config.prompt.text",
        )
