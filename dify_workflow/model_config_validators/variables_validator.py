"""Validate model_config.user_input_form — aligns with Dify's BasicVariablesConfigManager.

Checks:
  - user_input_form is a list
  - Each item has exactly one type key from the allowed set
  - Each item has required label (str) and variable (str matching regex)
  - Variable names are unique
  - Select type: options is a list, default is in options
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..validator import ValidationResult

_FIELD_PREFIX = "model_config.user_input_form"

_ALLOWED_FORM_TYPES = frozenset({
    "text-input", "select", "paragraph", "number",
    "checkbox", "external_data_tool",
})

# Dify backend regex for variable names:
# Cannot start with digit, allows Chinese, alphanumeric, underscore, emoji
_VARIABLE_PATTERN = re.compile(
    r"^(?!\d)"
    r"[\u4e00-\u9fa5A-Za-z0-9_"
    r"\U0001F300-\U0001F64F"
    r"\U0001F680-\U0001F6FF"
    r"]+$"
)

_VARIABLE_MAX_LENGTH = 100


def validate_user_input_form(
    model_config: dict[str, Any],
    result: ValidationResult,
) -> None:
    """Validate the ``user_input_form`` section inside model_config."""
    form = model_config.get("user_input_form")
    if form is None:
        return  # optional, defaults to []

    if not isinstance(form, list):
        result.add_error(
            "user_input_form must be a list",
            field_name=_FIELD_PREFIX,
        )
        return

    seen_variables: set[str] = set()

    for idx, item in enumerate(form):
        if not isinstance(item, dict):
            result.add_error(
                f"user_input_form[{idx}] must be a dict",
                field_name=f"{_FIELD_PREFIX}[{idx}]",
            )
            continue

        _validate_form_item(item, idx, seen_variables, result)


def _validate_form_item(
    item: dict[str, Any],
    idx: int,
    seen_variables: set[str],
    result: ValidationResult,
) -> None:
    """Validate a single user_input_form entry."""
    prefix = f"{_FIELD_PREFIX}[{idx}]"

    # Find the type key
    type_keys = [k for k in item if k in _ALLOWED_FORM_TYPES]
    if not type_keys:
        result.add_error(
            f"user_input_form[{idx}] must contain a type key: "
            f"{', '.join(sorted(_ALLOWED_FORM_TYPES))}",
            field_name=prefix,
        )
        return

    if len(type_keys) > 1:
        result.add_warning(
            f"user_input_form[{idx}] has multiple type keys: {type_keys}",
            field_name=prefix,
        )

    form_type = type_keys[0]
    inner = item[form_type]
    if not isinstance(inner, dict):
        result.add_error(
            f"user_input_form[{idx}].{form_type} must be a dict",
            field_name=f"{prefix}.{form_type}",
        )
        return

    # label — required
    label = inner.get("label")
    if not label or not isinstance(label, str):
        result.add_error(
            f"user_input_form[{idx}].{form_type}.label is required",
            field_name=f"{prefix}.{form_type}.label",
        )

    # variable — required, pattern, length
    variable = inner.get("variable")
    if not variable or not isinstance(variable, str):
        result.add_error(
            f"user_input_form[{idx}].{form_type}.variable is required",
            field_name=f"{prefix}.{form_type}.variable",
        )
    else:
        _validate_variable_name(variable, form_type, idx, seen_variables, result)

    # select-specific checks
    if form_type == "select":
        _validate_select_options(inner, form_type, idx, result)


def _validate_variable_name(
    variable: str,
    form_type: str,
    idx: int,
    seen_variables: set[str],
    result: ValidationResult,
) -> None:
    """Check variable name format, length, and uniqueness."""
    prefix = f"{_FIELD_PREFIX}[{idx}].{form_type}.variable"

    if len(variable) > _VARIABLE_MAX_LENGTH:
        result.add_error(
            f"variable '{variable}' exceeds max length {_VARIABLE_MAX_LENGTH}",
            field_name=prefix,
        )

    if not _VARIABLE_PATTERN.match(variable):
        result.add_error(
            f"variable '{variable}' has invalid format "
            "(must not start with digit, only alphanumeric/underscore/Chinese/emoji)",
            field_name=prefix,
        )

    if variable in seen_variables:
        result.add_error(
            f"duplicate variable name '{variable}'",
            field_name=prefix,
        )
    seen_variables.add(variable)


def _validate_select_options(
    inner: dict[str, Any],
    form_type: str,
    idx: int,
    result: ValidationResult,
) -> None:
    """Validate options and default for select-type fields."""
    prefix = f"{_FIELD_PREFIX}[{idx}].{form_type}"

    options = inner.get("options")
    if options is not None and not isinstance(options, list):
        result.add_error(
            "select options must be a list",
            field_name=f"{prefix}.options",
        )
        return

    default = inner.get("default")
    if default is not None and options is not None:
        if isinstance(options, list) and default not in options:
            result.add_error(
                f"select default '{default}' is not in options",
                field_name=f"{prefix}.default",
            )
