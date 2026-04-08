"""Validate model_config.model — aligns with Dify's ModelConfigManager.

Checks:
  - model exists and is a dict
  - model.provider is a non-empty string
  - model.name is a non-empty string
  - model.completion_params is a dict (if present)
  - completion_params.stop has at most 4 items
  - model.mode is "chat" or "completion" (if present)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..validator import ValidationResult

_FIELD_PREFIX = "model_config.model"

_VALID_MODEL_MODES = frozenset({"chat", "completion"})


def validate_model(
    model_config: dict[str, Any],
    result: ValidationResult,
) -> None:
    """Validate the ``model`` section inside model_config."""
    model = model_config.get("model")

    if not model:
        result.add_error("model is required", field_name=_FIELD_PREFIX)
        return

    if not isinstance(model, dict):
        result.add_error("model must be a dict", field_name=_FIELD_PREFIX)
        return

    # provider
    provider = model.get("provider")
    if not provider or not isinstance(provider, str):
        result.add_error(
            "model.provider is required and must be a non-empty string",
            field_name=f"{_FIELD_PREFIX}.provider",
        )

    # name
    name = model.get("name")
    if not name or not isinstance(name, str):
        result.add_error(
            "model.name is required and must be a non-empty string",
            field_name=f"{_FIELD_PREFIX}.name",
        )

    # mode (optional but if present must be valid)
    mode = model.get("mode")
    if mode is not None and mode not in _VALID_MODEL_MODES:
        result.add_warning(
            f"model.mode should be 'chat' or 'completion', got '{mode}'",
            field_name=f"{_FIELD_PREFIX}.mode",
        )

    # completion_params
    params = model.get("completion_params")
    if params is not None:
        if not isinstance(params, dict):
            result.add_error(
                "model.completion_params must be a dict",
                field_name=f"{_FIELD_PREFIX}.completion_params",
            )
        else:
            _validate_completion_params(params, result)


def _validate_completion_params(
    params: dict[str, Any],
    result: ValidationResult,
) -> None:
    """Check completion_params constraints."""
    stop = params.get("stop")
    if stop is not None:
        if not isinstance(stop, list):
            result.add_error(
                "completion_params.stop must be a list",
                field_name=f"{_FIELD_PREFIX}.completion_params.stop",
            )
        elif len(stop) > 4:
            result.add_error(
                f"completion_params.stop must have at most 4 items, got {len(stop)}",
                field_name=f"{_FIELD_PREFIX}.completion_params.stop",
            )
