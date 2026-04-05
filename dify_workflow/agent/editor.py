"""Agent mode creation and editing operations.

Agent mode (mode='agent-chat') extends Chat with tool-calling capabilities.
It uses model_config with agent_mode.enabled=true and a list of tools.
Supports function_call or react strategies.
Note: Agent mode only supports streaming (no blocking mode).
"""

from __future__ import annotations

from typing import Any

from ..models import AppMode, DifyDSL, ModelConfigContent


def _ensure_config(dsl: DifyDSL) -> ModelConfigContent:
    if dsl.model_config_content is None:
        dsl.model_config_content = ModelConfigContent()
    return dsl.model_config_content


def create_agent_app(
    name: str = "Agent App",
    description: str = "",
    *,
    model_provider: str = "openai",
    model_name: str = "gpt-4o",
    pre_prompt: str = "",
    strategy: str = "function_call",
    tools: list[dict[str, Any]] | None = None,
) -> DifyDSL:
    """Create an agent-chat mode app with tool-calling support.

    Args:
        strategy: "function_call" or "react"
        tools: List of tool configs, each with tool_type, provider_id, tool_name, etc.
    """
    dsl = DifyDSL()
    dsl.app.name = name
    dsl.app.mode = AppMode.AGENT_CHAT
    dsl.app.description = description

    agent_tools = tools or []
    dsl.model_config_content = ModelConfigContent(
        model={
            "provider": model_provider,
            "name": model_name,
            "mode": "chat",
            "completion_params": {"temperature": 0.7},
        },
        pre_prompt=pre_prompt,
        agent_mode={
            "enabled": True,
            "strategy": strategy,
            "tools": agent_tools,
        },
    )
    return dsl


def set_agent_strategy(dsl: DifyDSL, strategy: str) -> None:
    """Set the agent reasoning strategy.

    Args:
        strategy: "function_call" or "react"
    """
    config = _ensure_config(dsl)
    if isinstance(config.agent_mode, dict):
        config.agent_mode["enabled"] = True
        config.agent_mode["strategy"] = strategy
    else:
        config.agent_mode = {"enabled": True, "strategy": strategy, "tools": []}


def add_tool(
    dsl: DifyDSL,
    provider_id: str,
    tool_name: str,
    *,
    tool_type: str = "builtin",
    tool_parameters: dict[str, Any] | None = None,
) -> None:
    """Add a tool to the agent's tool list."""
    config = _ensure_config(dsl)
    if not isinstance(config.agent_mode, dict):
        config.agent_mode = {"enabled": True, "strategy": "function_call", "tools": []}

    config.agent_mode.setdefault("tools", [])
    config.agent_mode["tools"].append({
        "tool_type": tool_type,
        "provider_id": provider_id,
        "tool_name": tool_name,
        "tool_parameters": tool_parameters or {},
    })


def remove_tool(dsl: DifyDSL, tool_name: str) -> bool:
    """Remove a tool by name. Returns True if found and removed."""
    config = _ensure_config(dsl)
    if not isinstance(config.agent_mode, dict):
        return False

    tools = config.agent_mode.get("tools", [])
    original_len = len(tools)
    config.agent_mode["tools"] = [t for t in tools if t.get("tool_name") != tool_name]
    return len(config.agent_mode["tools"]) < original_len
