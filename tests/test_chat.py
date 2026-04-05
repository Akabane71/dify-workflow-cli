"""Tests for chat module (mode='chat')."""

import pytest

from dify_workflow.chat.editor import (
    add_suggested_question,
    add_user_variable,
    configure_dataset,
    create_chat_app,
    enable_feature,
    set_model,
    set_opening_statement,
    set_prompt,
)
from dify_workflow.chat.validator import validate_chat_mode
from dify_workflow.models import AppMode, DifyDSL, ModelConfigContent
from dify_workflow.validator import ValidationResult, validate_workflow
from dify_workflow.io import save_workflow, load_workflow


class TestCreateChatApp:
    def test_basic_chat(self):
        dsl = create_chat_app(name="My Chat")
        assert dsl.app.mode == AppMode.CHAT
        assert dsl.app.name == "My Chat"
        assert dsl.is_config_based
        assert not dsl.is_workflow_based
        assert dsl.model_config_content is not None

    def test_chat_model_config(self):
        dsl = create_chat_app(model_provider="openai", model_name="gpt-4o")
        mc = dsl.model_config_content
        assert mc.model["provider"] == "openai"
        assert mc.model["name"] == "gpt-4o"

    def test_chat_with_prompt(self):
        dsl = create_chat_app(pre_prompt="You are a translator.")
        assert dsl.model_config_content.pre_prompt == "You are a translator."

    def test_chat_with_opening(self):
        dsl = create_chat_app(opening_statement="Hello!")
        assert dsl.model_config_content.opening_statement == "Hello!"


class TestChatEditing:
    def test_set_model(self):
        dsl = create_chat_app()
        set_model(dsl, "anthropic", "claude-3-opus", temperature=0.3)
        mc = dsl.model_config_content
        assert mc.model["provider"] == "anthropic"
        assert mc.model["name"] == "claude-3-opus"

    def test_set_prompt(self):
        dsl = create_chat_app()
        set_prompt(dsl, "Act as a pirate.")
        assert dsl.model_config_content.pre_prompt == "Act as a pirate."

    def test_add_user_variable(self):
        dsl = create_chat_app()
        add_user_variable(dsl, "topic", label="Topic", var_type="text-input")
        form = dsl.model_config_content.user_input_form
        assert len(form) == 1
        assert "text-input" in form[0]
        assert form[0]["text-input"]["variable"] == "topic"

    def test_add_multiple_variables(self):
        dsl = create_chat_app()
        add_user_variable(dsl, "topic")
        add_user_variable(dsl, "language", var_type="select")
        assert len(dsl.model_config_content.user_input_form) == 2

    def test_set_opening_statement(self):
        dsl = create_chat_app()
        set_opening_statement(dsl, "Welcome!")
        assert dsl.model_config_content.opening_statement == "Welcome!"

    def test_add_suggested_question(self):
        dsl = create_chat_app()
        add_suggested_question(dsl, "What can you do?")
        add_suggested_question(dsl, "Tell me more")
        assert len(dsl.model_config_content.suggested_questions) == 2

    def test_configure_dataset(self):
        dsl = create_chat_app()
        configure_dataset(dsl, ["ds1", "ds2"], retrieval_model="multiple", top_k=6)
        dc = dsl.model_config_content.dataset_configs
        assert dc["retrieval_model"] == "multiple"
        assert dc["top_k"] == 6

    def test_enable_feature(self):
        dsl = create_chat_app()
        enable_feature(dsl, "speech_to_text", True)
        assert dsl.model_config_content.speech_to_text["enabled"]

    def test_set_model_on_empty_dsl(self):
        dsl = DifyDSL()
        dsl.app.mode = AppMode.CHAT
        set_model(dsl, "openai", "gpt-4")
        assert dsl.model_config_content is not None
        assert dsl.model_config_content.model["name"] == "gpt-4"


class TestChatIO:
    def test_roundtrip_chat(self, tmp_path):
        dsl = create_chat_app(name="RT Chat", pre_prompt="Hello")
        path = tmp_path / "chat.yaml"
        save_workflow(dsl, path)
        loaded = load_workflow(path)
        assert loaded.app.mode == AppMode.CHAT
        assert loaded.model_config_content is not None
        assert loaded.model_config_content.pre_prompt == "Hello"

    def test_chat_yaml_has_model_config(self, tmp_path):
        dsl = create_chat_app()
        path = tmp_path / "chat.yaml"
        save_workflow(dsl, path)
        content = path.read_text()
        assert "model_config:" in content
        assert "workflow:" not in content  # Config-based apps shouldn't have workflow


class TestChatValidation:
    def test_valid_chat(self):
        dsl = create_chat_app(pre_prompt="Hello")
        result = validate_workflow(dsl)
        assert result.valid

    def test_chat_no_model(self):
        dsl = create_chat_app()
        dsl.model_config_content.model = {}
        result = validate_workflow(dsl)
        assert not result.valid

    def test_chat_no_prompt_warning(self):
        dsl = create_chat_app(pre_prompt="")
        result = validate_workflow(dsl)
        warnings = [e for e in result.errors if e.level == "warning"]
        assert any("prompt" in w.message.lower() for w in warnings)

    def test_chat_missing_config(self):
        dsl = DifyDSL()
        dsl.app.mode = AppMode.CHAT
        result = validate_workflow(dsl)
        assert not result.valid
