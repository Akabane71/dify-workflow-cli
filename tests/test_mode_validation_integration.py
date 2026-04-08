"""Integration tests for chat/agent/completion mode validation via DSL fixtures."""

import pytest
from pathlib import Path

from dify_workflow.io import load_workflow
from dify_workflow.validator import validate_workflow, ValidationResult
from dify_workflow.models import AppMode, DifyDSL, ModelConfigContent

FIXTURES = Path(__file__).parent / "fixtures"


def _errors(result: ValidationResult) -> list[str]:
    return [e.message for e in result.errors if e.level == "error"]


def _warnings(result: ValidationResult) -> list[str]:
    return [e.message for e in result.errors if e.level == "warning"]


# ─── Valid fixtures ───────────────────────────────────────────────────────────

class TestValidFixtures:
    def test_chat_valid(self):
        dsl = load_workflow(str(FIXTURES / "chat_valid.yaml"))
        result = validate_workflow(dsl)
        assert result.valid, f"Unexpected errors: {_errors(result)}"

    def test_agent_valid(self):
        dsl = load_workflow(str(FIXTURES / "agent_valid.yaml"))
        result = validate_workflow(dsl)
        assert result.valid, f"Unexpected errors: {_errors(result)}"

    def test_completion_valid(self):
        dsl = load_workflow(str(FIXTURES / "completion_valid.yaml"))
        result = validate_workflow(dsl)
        assert result.valid, f"Unexpected errors: {_errors(result)}"


# ─── Mode ↔ Structure consistency ─────────────────────────────────────────────

class TestModeStructureConsistency:
    def test_config_mode_missing_model_config(self):
        """Chat mode without model_config should error."""
        dsl = DifyDSL(
            app={"name": "Test", "mode": "chat"},
        )
        result = validate_workflow(dsl)
        assert not result.valid
        assert any("model_config" in e for e in _errors(result))

    def test_workflow_mode_warns_on_model_config(self):
        """Workflow mode with model_config should warn."""
        dsl = DifyDSL(
            app={"name": "Test", "mode": "workflow"},
            model_config={"model": {"provider": "openai", "name": "gpt-4o"}},
        )
        result = validate_workflow(dsl)
        assert any("model_config" in w for w in _warnings(result))


# ─── Chat validation integration ─────────────────────────────────────────────

class TestChatValidation:
    def _make_chat_dsl(self, **overrides) -> DifyDSL:
        config = {
            "model": {"provider": "openai", "name": "gpt-4o", "mode": "chat"},
            "pre_prompt": "Hello",
            "prompt_type": "simple",
            "user_input_form": [],
        }
        config.update(overrides)
        return DifyDSL(
            app={"name": "Test", "mode": "chat"},
            model_config=config,
        )

    def test_missing_model_provider(self):
        dsl = self._make_chat_dsl(model={"name": "gpt-4o"})
        result = validate_workflow(dsl)
        assert not result.valid
        assert any("provider" in e for e in _errors(result))

    def test_invalid_prompt_type(self):
        dsl = self._make_chat_dsl(prompt_type="fancy")
        result = validate_workflow(dsl)
        assert not result.valid

    def test_invalid_variable_name(self):
        dsl = self._make_chat_dsl(user_input_form=[
            {"text-input": {"label": "Bad", "variable": "123bad"}}
        ])
        result = validate_workflow(dsl)
        assert not result.valid

    def test_agent_enabled_warns(self):
        dsl = self._make_chat_dsl(agent_mode={"enabled": True, "tools": []})
        result = validate_workflow(dsl)
        assert any("agent_mode" in w for w in _warnings(result))

    def test_stop_too_many(self):
        dsl = self._make_chat_dsl(model={
            "provider": "openai", "name": "gpt-4o",
            "completion_params": {"stop": ["a", "b", "c", "d", "e"]}
        })
        result = validate_workflow(dsl)
        assert not result.valid
        assert any("at most 4" in e for e in _errors(result))


# ─── Agent validation integration ─────────────────────────────────────────────

class TestAgentValidation:
    def _make_agent_dsl(self, **overrides) -> DifyDSL:
        config = {
            "model": {"provider": "openai", "name": "gpt-4o", "mode": "chat"},
            "pre_prompt": "You are agent.",
            "prompt_type": "simple",
            "agent_mode": {
                "enabled": True,
                "strategy": "function_call",
                "tools": [{
                    "provider_type": "builtin",
                    "provider_id": "calc",
                    "tool_name": "add",
                    "tool_parameters": {},
                }],
            },
        }
        config.update(overrides)
        return DifyDSL(
            app={"name": "Test", "mode": "agent-chat"},
            model_config=config,
        )

    def test_valid_agent(self):
        dsl = self._make_agent_dsl()
        result = validate_workflow(dsl)
        assert result.valid, f"Unexpected errors: {_errors(result)}"

    def test_agent_disabled_error(self):
        dsl = self._make_agent_dsl(agent_mode={"enabled": False, "tools": []})
        result = validate_workflow(dsl)
        assert not result.valid
        assert any("enabled=false" in e for e in _errors(result))

    def test_agent_no_tools_warns(self):
        dsl = self._make_agent_dsl(agent_mode={
            "enabled": True, "strategy": "function_call", "tools": [],
        })
        result = validate_workflow(dsl)
        assert any("no tools" in w for w in _warnings(result))

    def test_agent_invalid_strategy(self):
        dsl = self._make_agent_dsl(agent_mode={
            "enabled": True, "strategy": "magic", "tools": [],
        })
        result = validate_workflow(dsl)
        assert not result.valid

    def test_agent_tool_missing_fields(self):
        dsl = self._make_agent_dsl(agent_mode={
            "enabled": True, "strategy": "function_call",
            "tools": [{"provider_type": "builtin"}],
        })
        result = validate_workflow(dsl)
        assert not result.valid

    def test_agent_all_strategies(self):
        for strategy in ("router", "react-router", "react", "function_call"):
            dsl = self._make_agent_dsl(agent_mode={
                "enabled": True, "strategy": strategy,
                "tools": [{
                    "provider_type": "builtin",
                    "provider_id": "x",
                    "tool_name": "y",
                    "tool_parameters": {},
                }],
            })
            result = validate_workflow(dsl)
            assert result.valid, f"Strategy '{strategy}' should pass: {_errors(result)}"


# ─── Completion validation integration ────────────────────────────────────────

class TestCompletionValidation:
    def _make_completion_dsl(self, **overrides) -> DifyDSL:
        config = {
            "model": {"provider": "openai", "name": "gpt-4o", "mode": "chat"},
            "pre_prompt": "Translate: {{query}}",
            "prompt_type": "simple",
            "user_input_form": [
                {"text-input": {"label": "Query", "variable": "query"}},
            ],
        }
        config.update(overrides)
        return DifyDSL(
            app={"name": "Test", "mode": "completion"},
            model_config=config,
        )

    def test_valid_completion(self):
        dsl = self._make_completion_dsl()
        result = validate_workflow(dsl)
        assert result.valid, f"Unexpected errors: {_errors(result)}"

    def test_opening_statement_warns(self):
        dsl = self._make_completion_dsl(opening_statement="Hi!")
        result = validate_workflow(dsl)
        assert any("opening_statement" in w for w in _warnings(result))

    def test_sqa_warns(self):
        dsl = self._make_completion_dsl(
            suggested_questions_after_answer={"enabled": True}
        )
        result = validate_workflow(dsl)
        assert any("suggested_questions_after_answer" in w for w in _warnings(result))

    def test_stt_warns(self):
        dsl = self._make_completion_dsl(speech_to_text={"enabled": True})
        result = validate_workflow(dsl)
        assert any("speech_to_text" in w for w in _warnings(result))

    def test_dataset_without_query_variable(self):
        dsl = self._make_completion_dsl(
            dataset_configs={
                "datasets": {"datasets": [
                    {"dataset": {"id": "12345678-1234-5678-1234-567812345678"}}
                ]},
            },
            dataset_query_variable="",
        )
        result = validate_workflow(dsl)
        assert not result.valid
        assert any("dataset_query_variable" in e for e in _errors(result))

    def test_dataset_with_query_variable(self):
        dsl = self._make_completion_dsl(
            dataset_configs={
                "datasets": {"datasets": [
                    {"dataset": {"id": "12345678-1234-5678-1234-567812345678"}}
                ]},
            },
            dataset_query_variable="query",
        )
        result = validate_workflow(dsl)
        assert result.valid, f"Unexpected errors: {_errors(result)}"

    def test_no_user_input_warns(self):
        dsl = self._make_completion_dsl(user_input_form=[])
        result = validate_workflow(dsl)
        assert any("user_input_form" in w or "user input" in w for w in _warnings(result))
