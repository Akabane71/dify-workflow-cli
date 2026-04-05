"""Tests for completion module (mode='completion')."""

import pytest

from dify_workflow.completion.editor import (
    create_completion_app,
    enable_more_like_this,
)
from dify_workflow.models import AppMode, DifyDSL
from dify_workflow.validator import validate_workflow
from dify_workflow.io import save_workflow, load_workflow


class TestCreateCompletionApp:
    def test_basic_completion(self):
        dsl = create_completion_app(name="My Completion")
        assert dsl.app.mode == AppMode.COMPLETION
        assert dsl.is_config_based
        mc = dsl.model_config_content
        assert mc is not None
        assert "{{query}}" in mc.pre_prompt

    def test_custom_prompt(self):
        dsl = create_completion_app(pre_prompt="Translate: {{input}}")
        assert dsl.model_config_content.pre_prompt == "Translate: {{input}}"

    def test_with_user_input_form(self):
        dsl = create_completion_app()
        mc = dsl.model_config_content
        assert mc.user_input_form is not None
        assert len(mc.user_input_form) > 0

    def test_with_model_provider(self):
        dsl = create_completion_app(
            model_provider="anthropic",
            model_name="claude-3-haiku-20240307",
        )
        mc = dsl.model_config_content
        assert mc.model["provider"] == "anthropic"
        assert mc.model["name"] == "claude-3-haiku-20240307"


class TestCompletionEditing:
    def test_enable_more_like_this(self):
        dsl = create_completion_app()
        enable_more_like_this(dsl)
        mc = dsl.model_config_content
        assert mc.more_like_this["enabled"]

    def test_disable_more_like_this(self):
        dsl = create_completion_app()
        enable_more_like_this(dsl)
        enable_more_like_this(dsl, enabled=False)
        assert not dsl.model_config_content.more_like_this["enabled"]


class TestCompletionIO:
    def test_roundtrip_completion(self, tmp_path):
        dsl = create_completion_app(name="RT Completion")
        path = tmp_path / "completion.yaml"
        save_workflow(dsl, path)
        loaded = load_workflow(path)
        assert loaded.app.mode == AppMode.COMPLETION
        assert "{{query}}" in loaded.model_config_content.pre_prompt


class TestCompletionValidation:
    def test_valid_completion(self):
        dsl = create_completion_app()
        result = validate_workflow(dsl)
        assert result.valid

    def test_no_prompt_warning(self):
        dsl = create_completion_app()
        dsl.model_config_content.pre_prompt = ""
        result = validate_workflow(dsl)
        warnings = [e for e in result.errors if e.level == "warning"]
        assert any("pre_prompt" in w.message.lower() for w in warnings)

    def test_missing_config(self):
        dsl = DifyDSL()
        dsl.app.mode = AppMode.COMPLETION
        result = validate_workflow(dsl)
        assert not result.valid

    def test_no_user_input_warning(self):
        dsl = create_completion_app()
        dsl.model_config_content.user_input_form = []
        result = validate_workflow(dsl)
        warnings = [e for e in result.errors if e.level == "warning"]
        assert any("user_input" in w.message.lower() for w in warnings)
