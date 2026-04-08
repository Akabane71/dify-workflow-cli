"""Validate model_config feature toggles — aligns with Dify's feature ConfigManagers.

Checks per-feature enabled flags and type correctness.
Validates feature applicability per app mode:
  - Chat/Agent: all features except more_like_this
  - Completion: only text_to_speech, more_like_this, sensitive_word_avoidance, file_upload
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..validator import ValidationResult

_FIELD_PREFIX = "model_config"

# Features available per mode (True = supported)
_CHAT_AGENT_FEATURES = frozenset({
    "opening_statement",
    "suggested_questions_after_answer",
    "speech_to_text",
    "text_to_speech",
    "retriever_resource",
    "sensitive_word_avoidance",
    "file_upload",
})

_COMPLETION_FEATURES = frozenset({
    "text_to_speech",
    "more_like_this",
    "sensitive_word_avoidance",
    "file_upload",
})

# Features that are dict with an 'enabled' flag
_TOGGLE_FEATURES = (
    "suggested_questions_after_answer",
    "speech_to_text",
    "text_to_speech",
    "retriever_resource",
    "more_like_this",
    "sensitive_word_avoidance",
)

# Features not applicable per mode
_NOT_FOR_COMPLETION = frozenset({
    "opening_statement",
    "suggested_questions_after_answer",
    "speech_to_text",
    "retriever_resource",
})

_NOT_FOR_CHAT_AGENT = frozenset({
    "more_like_this",
})


def validate_features(
    model_config: dict[str, Any],
    result: ValidationResult,
    *,
    app_mode: str = "chat",
) -> None:
    """Validate feature toggles in model_config."""
    _validate_toggle_types(model_config, result)
    _validate_sensitive_word(model_config, result)
    _validate_feature_applicability(model_config, result, app_mode=app_mode)


def _validate_toggle_types(
    model_config: dict[str, Any],
    result: ValidationResult,
) -> None:
    """Check that toggle features have boolean 'enabled' flag."""
    for feature_name in _TOGGLE_FEATURES:
        feature = model_config.get(feature_name)
        if feature is None:
            continue

        if not isinstance(feature, dict):
            result.add_error(
                f"{feature_name} must be a dict with 'enabled' key",
                field_name=f"{_FIELD_PREFIX}.{feature_name}",
            )
            continue

        enabled = feature.get("enabled")
        if enabled is not None and not isinstance(enabled, bool):
            result.add_error(
                f"{feature_name}.enabled must be a boolean",
                field_name=f"{_FIELD_PREFIX}.{feature_name}.enabled",
            )


def _validate_sensitive_word(
    model_config: dict[str, Any],
    result: ValidationResult,
) -> None:
    """sensitive_word_avoidance: type is required when enabled."""
    swa = model_config.get("sensitive_word_avoidance")
    if not isinstance(swa, dict):
        return

    if swa.get("enabled") and not swa.get("type"):
        result.add_error(
            "sensitive_word_avoidance.type is required when enabled",
            field_name=f"{_FIELD_PREFIX}.sensitive_word_avoidance.type",
        )


def _validate_feature_applicability(
    model_config: dict[str, Any],
    result: ValidationResult,
    *,
    app_mode: str,
) -> None:
    """Warn about features that don't apply to the current mode."""
    if app_mode == "completion":
        unsupported = _NOT_FOR_COMPLETION
    elif app_mode in ("chat", "agent-chat"):
        unsupported = _NOT_FOR_CHAT_AGENT
    else:
        return

    for feature_name in unsupported:
        feature = model_config.get(feature_name)
        if feature is None:
            continue

        # Check if the feature is actively enabled/configured
        is_active = False
        if isinstance(feature, dict):
            is_active = bool(feature.get("enabled"))
        elif isinstance(feature, str):
            is_active = bool(feature)  # e.g. opening_statement
        elif isinstance(feature, list):
            is_active = bool(feature)  # e.g. suggested_questions

        if is_active:
            result.add_warning(
                f"{feature_name} is not supported in {app_mode} mode",
                field_name=f"{_FIELD_PREFIX}.{feature_name}",
            )
