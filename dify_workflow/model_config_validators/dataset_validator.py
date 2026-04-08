"""Validate model_config.dataset_configs — aligns with Dify's DatasetConfigManager.

Checks:
  - dataset_configs is a dict (if present)
  - retrieval_model is "single" or "multiple"
  - datasets.datasets is a list
  - Each dataset ID is a valid UUID format
  - Completion mode: dataset_query_variable is required when datasets exist
"""

from __future__ import annotations

import uuid as _uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..validator import ValidationResult

_FIELD_PREFIX = "model_config.dataset_configs"

_VALID_RETRIEVAL_MODELS = frozenset({"single", "multiple"})


def validate_dataset_configs(
    model_config: dict[str, Any],
    result: ValidationResult,
    *,
    is_completion: bool = False,
) -> None:
    """Validate the ``dataset_configs`` section inside model_config.

    Args:
        model_config: The raw model_config dict.
        result: ValidationResult to append issues to.
        is_completion: If True, enforce dataset_query_variable requirement.
    """
    dataset_configs = model_config.get("dataset_configs")
    if not dataset_configs:
        return

    if not isinstance(dataset_configs, dict):
        result.add_error(
            "dataset_configs must be a dict",
            field_name=_FIELD_PREFIX,
        )
        return

    # retrieval_model
    retrieval_model = dataset_configs.get("retrieval_model")
    if retrieval_model is not None and retrieval_model not in _VALID_RETRIEVAL_MODELS:
        result.add_error(
            f"dataset_configs.retrieval_model must be 'single' or 'multiple', "
            f"got '{retrieval_model}'",
            field_name=f"{_FIELD_PREFIX}.retrieval_model",
        )

    # datasets.datasets
    datasets_wrapper = dataset_configs.get("datasets")
    dataset_list = _extract_dataset_list(datasets_wrapper)
    if dataset_list is None:
        return  # No datasets configured

    _validate_dataset_ids(dataset_list, result)

    # Completion-specific: dataset_query_variable required
    if is_completion and dataset_list:
        query_var = model_config.get("dataset_query_variable", "")
        if not query_var:
            result.add_error(
                "dataset_query_variable is required when datasets are configured "
                "(completion mode)",
                field_name="model_config.dataset_query_variable",
            )


def _extract_dataset_list(
    datasets_wrapper: Any,
) -> list[dict[str, Any]] | None:
    """Extract the inner dataset list from various wrapper formats."""
    if datasets_wrapper is None:
        return None

    if isinstance(datasets_wrapper, dict):
        inner = datasets_wrapper.get("datasets", [])
        if isinstance(inner, list):
            return inner

    return None


def _validate_dataset_ids(
    dataset_list: list[dict[str, Any]],
    result: ValidationResult,
) -> None:
    """Check each dataset entry has a valid UUID id."""
    for idx, entry in enumerate(dataset_list):
        if not isinstance(entry, dict):
            continue

        # Dataset can be nested: {"dataset": {"id": "...", "enabled": true}}
        ds = entry.get("dataset", entry)
        if not isinstance(ds, dict):
            continue

        ds_id = ds.get("id", "")
        if ds_id and not _is_valid_uuid(ds_id):
            result.add_error(
                f"dataset_configs.datasets[{idx}].id '{ds_id}' is not a valid UUID",
                field_name=f"{_FIELD_PREFIX}.datasets.datasets[{idx}].id",
            )


def _is_valid_uuid(value: str) -> bool:
    """Check if a string is a valid UUID."""
    try:
        _uuid.UUID(str(value))
        return True
    except (ValueError, AttributeError):
        return False
