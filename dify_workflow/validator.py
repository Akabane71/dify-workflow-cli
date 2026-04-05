"""Validation dispatcher: detects app mode and calls mode-specific validators.

Backward compatible — validate_workflow() still works for all modes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import AppMode, DifyDSL


@dataclass
class ValidationError:
    level: str  # "error" or "warning"
    message: str
    node_id: str | None = None
    field: str | None = None


@dataclass
class ValidationResult:
    valid: bool = True
    errors: list[ValidationError] = field(default_factory=list)

    def add_error(self, message: str, *, node_id: str | None = None, field_name: str | None = None):
        self.errors.append(ValidationError(level="error", message=message, node_id=node_id, field=field_name))
        self.valid = False

    def add_warning(self, message: str, *, node_id: str | None = None, field_name: str | None = None):
        self.errors.append(ValidationError(level="warning", message=message, node_id=node_id, field=field_name))

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "error_count": sum(1 for e in self.errors if e.level == "error"),
            "warning_count": sum(1 for e in self.errors if e.level == "warning"),
            "errors": [
                {"level": e.level, "message": e.message, "node_id": e.node_id, "field": e.field}
                for e in self.errors
            ],
        }


def _validate_top_level(dsl: DifyDSL, result: ValidationResult) -> None:
    if not dsl.version:
        result.add_error("Missing DSL version")
    if not dsl.kind:
        result.add_error("Missing DSL kind")
    if not dsl.app.name:
        result.add_error("Missing app name", field_name="app.name")
    if not dsl.app.mode:
        result.add_error("Missing app mode", field_name="app.mode")

    # DSL metadata validation (version compatibility, icon_type, env vars)
    from .node_data_validator import validate_dsl_metadata
    for err in validate_dsl_metadata(dsl):
        if err.level == "error":
            result.add_error(err.message, field_name=err.field)
        else:
            result.add_warning(err.message, field_name=err.field)


def validate_workflow(dsl: DifyDSL) -> ValidationResult:
    """Validate a Dify DSL file — auto-detects mode and applies appropriate rules.

    This is the universal entry point for all app types.
    """
    result = ValidationResult()

    _validate_top_level(dsl, result)

    mode = dsl.app.mode

    if mode in (AppMode.WORKFLOW, AppMode.ADVANCED_CHAT):
        # Workflow-based validation (graph structure, nodes, edges, connectivity)
        from .workflow.validator import validate_workflow_mode
        validate_workflow_mode(dsl, result)

        if mode == AppMode.ADVANCED_CHAT:
            # Additional chatflow-specific rules
            from .chatflow.validator import validate_chatflow_mode
            validate_chatflow_mode(dsl, result)

    elif mode == AppMode.CHAT:
        from .chat.validator import validate_chat_mode
        validate_chat_mode(dsl, result)

    elif mode == AppMode.AGENT_CHAT:
        from .agent.validator import validate_agent_mode
        validate_agent_mode(dsl, result)

    elif mode == AppMode.COMPLETION:
        from .completion.validator import validate_completion_mode
        validate_completion_mode(dsl, result)

    return result
