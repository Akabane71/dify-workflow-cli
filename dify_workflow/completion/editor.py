"""Completion mode creation and editing operations.

Completion mode (mode='completion') is for single-turn text generation.
No conversation support. Uses model_config with user_input_form.
Unique feature: more_like_this (generate similar variants).
"""

from __future__ import annotations

from ..models import AppMode, DifyDSL, ModelConfigContent


def create_completion_app(
    name: str = "Text Generator",
    description: str = "",
    *,
    model_provider: str = "openai",
    model_name: str = "gpt-4o",
    pre_prompt: str = "{{query}}",
    input_variable: str = "query",
    input_label: str = "Query",
) -> DifyDSL:
    """Create a completion mode app for single-turn text generation."""
    dsl = DifyDSL()
    dsl.app.name = name
    dsl.app.mode = AppMode.COMPLETION
    dsl.app.description = description

    dsl.model_config_content = ModelConfigContent(
        model={
            "provider": model_provider,
            "name": model_name,
            "mode": "chat",
            "completion_params": {"temperature": 0.7},
        },
        pre_prompt=pre_prompt,
        user_input_form=[{
            "paragraph": {
                "label": input_label,
                "variable": input_variable,
                "required": True,
                "default": "",
            }
        }],
    )
    return dsl


def enable_more_like_this(dsl: DifyDSL, enabled: bool = True) -> None:
    """Enable or disable more-like-this feature (completion mode only)."""
    if dsl.model_config_content is None:
        dsl.model_config_content = ModelConfigContent()
    dsl.model_config_content.more_like_this = {"enabled": enabled}
