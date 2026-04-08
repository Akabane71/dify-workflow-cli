"""Tests for model_config shared validators."""

import pytest

from dify_workflow.validator import ValidationResult
from dify_workflow.model_config_validators.model_validator import validate_model
from dify_workflow.model_config_validators.variables_validator import (
    validate_user_input_form,
)
from dify_workflow.model_config_validators.prompt_validator import validate_prompt
from dify_workflow.model_config_validators.dataset_validator import (
    validate_dataset_configs,
)
from dify_workflow.model_config_validators.agent_mode_validator import (
    validate_agent_mode,
)
from dify_workflow.model_config_validators.features_validator import validate_features


def _result() -> ValidationResult:
    return ValidationResult()


def _errors(r: ValidationResult) -> list[str]:
    return [e.message for e in r.errors if e.level == "error"]


def _warnings(r: ValidationResult) -> list[str]:
    return [e.message for e in r.errors if e.level == "warning"]


# ── model_validator ───────────────────────────────────────────────────────────


class TestModelValidator:
    def test_valid(self):
        r = _result()
        validate_model({"model": {"provider": "openai", "name": "gpt-4o"}}, r)
        assert r.valid

    def test_missing_model(self):
        r = _result()
        validate_model({}, r)
        assert not r.valid

    def test_model_not_dict(self):
        r = _result()
        validate_model({"model": "openai"}, r)
        assert not r.valid

    def test_missing_provider(self):
        r = _result()
        validate_model({"model": {"name": "gpt-4o"}}, r)
        assert any("provider" in e for e in _errors(r))

    def test_missing_name(self):
        r = _result()
        validate_model({"model": {"provider": "openai"}}, r)
        assert any("name" in e for e in _errors(r))

    def test_empty_provider(self):
        r = _result()
        validate_model({"model": {"provider": "", "name": "gpt-4o"}}, r)
        assert not r.valid

    def test_invalid_mode_warning(self):
        r = _result()
        validate_model({"model": {"provider": "x", "name": "y", "mode": "bad"}}, r)
        assert r.valid
        assert _warnings(r)

    def test_completion_params_not_dict(self):
        r = _result()
        validate_model({"model": {"provider": "x", "name": "y", "completion_params": "z"}}, r)
        assert not r.valid

    def test_stop_too_long(self):
        r = _result()
        validate_model(
            {"model": {"provider": "x", "name": "y",
                        "completion_params": {"stop": list("abcde")}}}, r)
        assert not r.valid

    def test_stop_valid(self):
        r = _result()
        validate_model(
            {"model": {"provider": "x", "name": "y",
                        "completion_params": {"stop": ["a", "b"]}}}, r)
        assert r.valid

    def test_stop_not_list(self):
        r = _result()
        validate_model(
            {"model": {"provider": "x", "name": "y",
                        "completion_params": {"stop": "bad"}}}, r)
        assert not r.valid


# ── variables_validator ───────────────────────────────────────────────────────


class TestVariablesValidator:
    def test_valid_form(self):
        r = _result()
        validate_user_input_form({"user_input_form": [
            {"text-input": {"label": "Q", "variable": "query"}}
        ]}, r)
        assert r.valid

    def test_no_form_ok(self):
        r = _result()
        validate_user_input_form({}, r)
        assert r.valid

    def test_form_not_list(self):
        r = _result()
        validate_user_input_form({"user_input_form": "bad"}, r)
        assert not r.valid

    def test_missing_type_key(self):
        r = _result()
        validate_user_input_form({"user_input_form": [
            {"unknown": {"label": "X", "variable": "x"}}
        ]}, r)
        assert any("type key" in e for e in _errors(r))

    def test_missing_label(self):
        r = _result()
        validate_user_input_form({"user_input_form": [
            {"text-input": {"variable": "x"}}
        ]}, r)
        assert any("label" in e for e in _errors(r))

    def test_missing_variable(self):
        r = _result()
        validate_user_input_form({"user_input_form": [
            {"text-input": {"label": "X"}}
        ]}, r)
        assert any("variable" in e for e in _errors(r))

    def test_variable_starts_with_digit(self):
        r = _result()
        validate_user_input_form({"user_input_form": [
            {"text-input": {"label": "X", "variable": "1abc"}}
        ]}, r)
        assert any("invalid format" in e for e in _errors(r))

    def test_variable_chinese(self):
        r = _result()
        validate_user_input_form({"user_input_form": [
            {"text-input": {"label": "X", "variable": "\u540d\u5b57"}}
        ]}, r)
        assert r.valid

    def test_variable_too_long(self):
        r = _result()
        validate_user_input_form({"user_input_form": [
            {"text-input": {"label": "X", "variable": "a" * 101}}
        ]}, r)
        assert any("max length" in e for e in _errors(r))

    def test_variable_max_ok(self):
        r = _result()
        validate_user_input_form({"user_input_form": [
            {"text-input": {"label": "X", "variable": "a" * 100}}
        ]}, r)
        assert r.valid

    def test_duplicate_variable(self):
        r = _result()
        validate_user_input_form({"user_input_form": [
            {"text-input": {"label": "A", "variable": "x"}},
            {"paragraph": {"label": "B", "variable": "x"}},
        ]}, r)
        assert any("duplicate" in e for e in _errors(r))

    def test_select_default_not_in_options(self):
        r = _result()
        validate_user_input_form({"user_input_form": [
            {"select": {"label": "L", "variable": "v", "options": ["a"], "default": "b"}}
        ]}, r)
        assert any("not in options" in e for e in _errors(r))

    def test_select_default_in_options(self):
        r = _result()
        validate_user_input_form({"user_input_form": [
            {"select": {"label": "L", "variable": "v", "options": ["a"], "default": "a"}}
        ]}, r)
        assert r.valid

    def test_all_form_types(self):
        types = ["text-input", "select", "paragraph", "number", "checkbox"]
        r = _result()
        items = [{t: {"label": f"L{i}", "variable": f"v{i}"}} for i, t in enumerate(types)]
        validate_user_input_form({"user_input_form": items}, r)
        assert r.valid


# ── prompt_validator ──────────────────────────────────────────────────────────


class TestPromptValidator:
    def test_simple_with_prompt(self):
        r = _result()
        validate_prompt({"prompt_type": "simple", "pre_prompt": "Hello"}, r)
        assert r.valid and not _warnings(r)

    def test_simple_empty_warning(self):
        r = _result()
        validate_prompt({"prompt_type": "simple", "pre_prompt": ""}, r)
        assert r.valid and _warnings(r)

    def test_default_is_simple(self):
        r = _result()
        validate_prompt({"pre_prompt": "ok"}, r)
        assert r.valid

    def test_simple_chat_prompt_config_requires_prompt_key(self):
        r = _result()
        validate_prompt({"prompt_type": "simple", "chat_prompt_config": {}}, r)
        assert any("prompt list" in e for e in _errors(r))

    def test_simple_completion_prompt_config_requires_prompt_key(self):
        r = _result()
        validate_prompt({"prompt_type": "simple", "completion_prompt_config": {}}, r)
        assert any("prompt object" in e for e in _errors(r))

    def test_invalid_type(self):
        r = _result()
        validate_prompt({"prompt_type": "fancy"}, r)
        assert not r.valid

    def test_advanced_chat_config(self):
        r = _result()
        validate_prompt({"prompt_type": "advanced", "chat_prompt_config": {
            "prompt": [{"role": "system", "text": "Hi"}]
        }}, r)
        assert r.valid

    def test_advanced_missing_config(self):
        r = _result()
        validate_prompt({"prompt_type": "advanced"}, r)
        assert not r.valid

    def test_advanced_too_many(self):
        r = _result()
        msgs = [{"role": "user", "text": f"m{i}"} for i in range(11)]
        validate_prompt({"prompt_type": "advanced", "chat_prompt_config": {"prompt": msgs}}, r)
        assert any("10" in e for e in _errors(r))

    def test_advanced_bad_role(self):
        r = _result()
        validate_prompt({"prompt_type": "advanced", "chat_prompt_config": {
            "prompt": [{"role": "king", "text": "hi"}]
        }}, r)
        assert any("role" in e for e in _errors(r))

    def test_advanced_missing_text(self):
        r = _result()
        validate_prompt({"prompt_type": "advanced", "chat_prompt_config": {
            "prompt": [{"role": "user"}]
        }}, r)
        assert any("text" in e for e in _errors(r))

    def test_advanced_completion_valid(self):
        r = _result()
        validate_prompt({"prompt_type": "advanced", "completion_prompt_config": {
            "prompt": {"text": "Do it"}
        }}, r)
        assert r.valid

    def test_advanced_completion_no_text(self):
        r = _result()
        validate_prompt({"prompt_type": "advanced", "completion_prompt_config": {
            "prompt": {}
        }}, r)
        assert not r.valid


# ── dataset_validator ─────────────────────────────────────────────────────────


class TestDatasetValidator:
    def test_no_datasets_ok(self):
        r = _result()
        validate_dataset_configs({}, r)
        assert r.valid

    def test_invalid_retrieval_model(self):
        r = _result()
        validate_dataset_configs({"dataset_configs": {"retrieval_model": "triple"}}, r)
        assert any("retrieval_model" in e for e in _errors(r))

    def test_valid_uuid(self):
        r = _result()
        validate_dataset_configs({"dataset_configs": {"datasets": {"datasets": [
            {"dataset": {"id": "12345678-1234-5678-1234-567812345678"}}
        ]}}}, r)
        assert r.valid

    def test_invalid_uuid(self):
        r = _result()
        validate_dataset_configs({"dataset_configs": {"datasets": {"datasets": [
            {"dataset": {"id": "not-a-uuid"}}
        ]}}}, r)
        assert any("UUID" in e for e in _errors(r))

    def test_completion_requires_query_var(self):
        r = _result()
        validate_dataset_configs({"dataset_configs": {"datasets": {"datasets": [
            {"dataset": {"id": "12345678-1234-5678-1234-567812345678"}}
        ]}}, "dataset_query_variable": ""}, r, is_completion=True)
        assert any("dataset_query_variable" in e for e in _errors(r))

    def test_completion_with_query_var(self):
        r = _result()
        validate_dataset_configs({"dataset_configs": {"datasets": {"datasets": [
            {"dataset": {"id": "12345678-1234-5678-1234-567812345678"}}
        ]}}, "dataset_query_variable": "q"}, r, is_completion=True)
        assert r.valid

    def test_not_dict(self):
        r = _result()
        validate_dataset_configs({"dataset_configs": "bad"}, r)
        assert not r.valid


# ── agent_mode_validator ──────────────────────────────────────────────────────


class TestAgentModeValidator:
    def test_no_agent_mode_ok(self):
        r = _result()
        validate_agent_mode({}, r)
        assert r.valid

    def test_valid(self):
        r = _result()
        validate_agent_mode({"agent_mode": {
            "enabled": True, "strategy": "function_call",
            "tools": [{"provider_type": "b", "provider_id": "c",
                        "tool_name": "d", "tool_parameters": {}}],
        }}, r)
        assert r.valid

    def test_enabled_not_bool(self):
        r = _result()
        validate_agent_mode({"agent_mode": {"enabled": "yes"}}, r)
        assert any("boolean" in e for e in _errors(r))

    def test_invalid_strategy(self):
        r = _result()
        validate_agent_mode({"agent_mode": {"strategy": "magic"}}, r)
        assert not r.valid

    def test_valid_strategies(self):
        for s in ("router", "react-router", "react", "function_call"):
            r = _result()
            validate_agent_mode({"agent_mode": {"strategy": s, "tools": []}}, r)
            assert r.valid, f"'{s}' should be valid"

    def test_tool_missing_fields(self):
        r = _result()
        validate_agent_mode({"agent_mode": {"tools": [{"provider_type": "b"}]}}, r)
        errs = _errors(r)
        assert any("provider_id" in e for e in errs)
        assert any("tool_name" in e for e in errs)

    def test_tool_params_not_dict(self):
        r = _result()
        validate_agent_mode({"agent_mode": {"tools": [
            {"provider_type": "b", "provider_id": "c", "tool_name": "d",
             "tool_parameters": "bad"}
        ]}}, r)
        assert any("tool_parameters must be a dict" in e for e in _errors(r))

    def test_legacy_skipped(self):
        r = _result()
        validate_agent_mode({"agent_mode": {
            "tools": [{"dataset": {"enabled": True}}]
        }}, r)
        assert r.valid

    def test_tools_not_list(self):
        r = _result()
        validate_agent_mode({"agent_mode": {"tools": "bad"}}, r)
        assert not r.valid


# ── features_validator ────────────────────────────────────────────────────────


class TestFeaturesValidator:
    def test_valid_chat(self):
        r = _result()
        validate_features({"speech_to_text": {"enabled": False}}, r, app_mode="chat")
        assert r.valid

    def test_enabled_not_bool(self):
        r = _result()
        validate_features({"speech_to_text": {"enabled": "yes"}}, r, app_mode="chat")
        assert any("boolean" in e for e in _errors(r))

    def test_feature_not_dict(self):
        r = _result()
        validate_features({"more_like_this": "yes"}, r, app_mode="completion")
        assert not r.valid

    def test_swa_type_required(self):
        r = _result()
        validate_features({"sensitive_word_avoidance": {"enabled": True}}, r, app_mode="chat")
        assert any("type is required" in e for e in _errors(r))

    def test_swa_with_type(self):
        r = _result()
        validate_features(
            {"sensitive_word_avoidance": {"enabled": True, "type": "kw"}}, r, app_mode="chat")
        assert r.valid

    def test_completion_warns_opening(self):
        r = _result()
        validate_features({"opening_statement": "Hi"}, r, app_mode="completion")
        assert any("not supported" in w for w in _warnings(r))

    def test_chat_warns_more_like_this(self):
        r = _result()
        validate_features({"more_like_this": {"enabled": True}}, r, app_mode="chat")
        assert any("not supported" in w for w in _warnings(r))

    def test_disabled_no_warn(self):
        r = _result()
        validate_features({"more_like_this": {"enabled": False}}, r, app_mode="chat")
        assert not _warnings(r)
