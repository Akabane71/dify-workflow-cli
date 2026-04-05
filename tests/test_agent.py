"""Tests for agent module (mode='agent-chat')."""

import pytest

from dify_workflow.agent.editor import (
    add_tool,
    create_agent_app,
    remove_tool,
    set_agent_strategy,
)
from dify_workflow.models import AppMode, DifyDSL
from dify_workflow.validator import validate_workflow
from dify_workflow.io import save_workflow, load_workflow


class TestCreateAgentApp:
    def test_basic_agent(self):
        dsl = create_agent_app(name="My Agent")
        assert dsl.app.mode == AppMode.AGENT_CHAT
        assert dsl.is_config_based
        mc = dsl.model_config_content
        assert mc is not None
        assert mc.agent_mode["enabled"]
        assert mc.agent_mode["strategy"] == "function_call"

    def test_agent_with_react(self):
        dsl = create_agent_app(strategy="react")
        assert dsl.model_config_content.agent_mode["strategy"] == "react"

    def test_agent_with_tools(self):
        tools = [
            {"tool_type": "builtin", "provider_id": "calc", "tool_name": "calculate"},
            {"tool_type": "api", "provider_id": "weather", "tool_name": "forecast"},
        ]
        dsl = create_agent_app(tools=tools)
        assert len(dsl.model_config_content.agent_mode["tools"]) == 2


class TestAgentEditing:
    def test_add_tool(self):
        dsl = create_agent_app()
        add_tool(dsl, "calculator", "calculate")
        tools = dsl.model_config_content.agent_mode["tools"]
        assert len(tools) == 1
        assert tools[0]["tool_name"] == "calculate"

    def test_add_multiple_tools(self):
        dsl = create_agent_app()
        add_tool(dsl, "calculator", "calculate")
        add_tool(dsl, "wikipedia", "search")
        assert len(dsl.model_config_content.agent_mode["tools"]) == 2

    def test_remove_tool(self):
        dsl = create_agent_app()
        add_tool(dsl, "calculator", "calculate")
        add_tool(dsl, "wikipedia", "search")
        assert remove_tool(dsl, "calculate")
        tools = dsl.model_config_content.agent_mode["tools"]
        assert len(tools) == 1
        assert tools[0]["tool_name"] == "search"

    def test_remove_nonexistent_tool(self):
        dsl = create_agent_app()
        assert not remove_tool(dsl, "nonexistent")

    def test_set_strategy(self):
        dsl = create_agent_app()
        set_agent_strategy(dsl, "react")
        assert dsl.model_config_content.agent_mode["strategy"] == "react"

    def test_add_tool_to_empty_dsl(self):
        dsl = DifyDSL()
        dsl.app.mode = AppMode.AGENT_CHAT
        add_tool(dsl, "calculator", "calculate")
        assert dsl.model_config_content is not None
        assert len(dsl.model_config_content.agent_mode["tools"]) == 1


class TestAgentIO:
    def test_roundtrip_agent(self, tmp_path):
        dsl = create_agent_app(name="RT Agent")
        add_tool(dsl, "calculator", "calculate")
        path = tmp_path / "agent.yaml"
        save_workflow(dsl, path)
        loaded = load_workflow(path)
        assert loaded.app.mode == AppMode.AGENT_CHAT
        mc = loaded.model_config_content
        assert mc.agent_mode["enabled"]
        assert len(mc.agent_mode["tools"]) == 1


class TestAgentValidation:
    def test_valid_agent(self):
        dsl = create_agent_app(pre_prompt="You are helpful")
        add_tool(dsl, "calculator", "calculate")
        result = validate_workflow(dsl)
        assert result.valid

    def test_agent_no_tools_warning(self):
        dsl = create_agent_app(pre_prompt="Hello")
        result = validate_workflow(dsl)
        warnings = [e for e in result.errors if e.level == "warning"]
        assert any("tools" in w.message.lower() for w in warnings)

    def test_agent_disabled_error(self):
        dsl = create_agent_app()
        dsl.model_config_content.agent_mode["enabled"] = False
        result = validate_workflow(dsl)
        assert not result.valid

    def test_agent_invalid_strategy(self):
        dsl = create_agent_app()
        dsl.model_config_content.agent_mode["strategy"] = "invalid"
        result = validate_workflow(dsl)
        assert not result.valid

    def test_agent_missing_config(self):
        dsl = DifyDSL()
        dsl.app.mode = AppMode.AGENT_CHAT
        result = validate_workflow(dsl)
        assert not result.valid
