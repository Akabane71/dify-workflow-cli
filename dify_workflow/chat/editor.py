"""Chat mode creation and editing operations.

Chat mode (mode='chat') uses model_config instead of workflow graph.
It supports multi-turn conversation with opening statements, suggested questions,
knowledge base retrieval, and various features.
"""

from __future__ import annotations

from typing import Any

from ..models import AppMode, DifyDSL, ModelConfigContent


def _ensure_config(dsl: DifyDSL) -> ModelConfigContent:
    """Ensure model_config_content exists, creating it if needed."""
    if dsl.model_config_content is None:
        dsl.model_config_content = ModelConfigContent()
    return dsl.model_config_content


def create_chat_app(
    name: str = "Chat App",
    description: str = "",
    *,
    model_provider: str = "openai",
    model_name: str = "gpt-4o",
    pre_prompt: str = "",
    opening_statement: str = "",
) -> DifyDSL:
    """Create a chat mode app with model_config."""
    dsl = DifyDSL()
    dsl.app.name = name
    dsl.app.mode = AppMode.CHAT
    dsl.app.description = description

    dsl.model_config_content = ModelConfigContent(
        model={
            "provider": model_provider,
            "name": model_name,
            "mode": "chat",
            "completion_params": {"temperature": 0.7},
        },
        pre_prompt=pre_prompt,
        opening_statement=opening_statement,
    )
    return dsl


def set_model(
    dsl: DifyDSL,
    provider: str,
    name: str,
    *,
    mode: str = "chat",
    **completion_params: Any,
) -> None:
    """Set the model for a config-based app."""
    config = _ensure_config(dsl)
    config.model = {
        "provider": provider,
        "name": name,
        "mode": mode,
        "completion_params": completion_params or {"temperature": 0.7},
    }


def set_prompt(dsl: DifyDSL, pre_prompt: str) -> None:
    """Set the system prompt (pre_prompt)."""
    config = _ensure_config(dsl)
    config.pre_prompt = pre_prompt


def add_user_variable(
    dsl: DifyDSL,
    variable: str,
    label: str = "",
    var_type: str = "paragraph",
    *,
    required: bool = True,
    default: str = "",
) -> None:
    """Add a user input form variable.

    The user_input_form uses Dify's format: [{<type>: {variable, label, ...}}]
    """
    config = _ensure_config(dsl)
    config.user_input_form.append({
        var_type: {
            "label": label or variable,
            "variable": variable,
            "required": required,
            "default": default,
        }
    })


def set_opening_statement(dsl: DifyDSL, text: str) -> None:
    """Set the opening statement for the chat app."""
    config = _ensure_config(dsl)
    config.opening_statement = text


def add_suggested_question(dsl: DifyDSL, question: str) -> None:
    """Add a suggested question."""
    config = _ensure_config(dsl)
    config.suggested_questions.append(question)


def configure_dataset(
    dsl: DifyDSL,
    dataset_ids: list[str],
    *,
    retrieval_model: str = "single",
    top_k: int = 4,
    score_threshold_enabled: bool = False,
    score_threshold: float | None = None,
) -> None:
    """Configure knowledge base / dataset retrieval."""
    config = _ensure_config(dsl)
    config.dataset_configs = {
        "datasets": {"datasets": [{"dataset": {"id": did, "enabled": True}} for did in dataset_ids]},
        "retrieval_model": retrieval_model,
        "top_k": top_k,
        "score_threshold_enabled": score_threshold_enabled,
        "score_threshold": score_threshold,
    }


def enable_feature(dsl: DifyDSL, feature: str, enabled: bool = True) -> None:
    """Enable or disable a feature by name.

    Supported features: speech_to_text, text_to_speech, sensitive_word_avoidance,
    suggested_questions_after_answer, retriever_resource, file_upload, more_like_this.
    """
    config = _ensure_config(dsl)
    current = getattr(config, feature, None)
    if isinstance(current, dict):
        current["enabled"] = enabled
        setattr(config, feature, current)
    else:
        setattr(config, feature, {"enabled": enabled})
