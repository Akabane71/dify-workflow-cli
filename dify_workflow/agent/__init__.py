"""Agent mode (mode='agent-chat') — chat with tool-calling capabilities."""

from .editor import (
    create_agent_app,
    set_agent_strategy,
    add_tool,
    remove_tool,
)
from .validator import validate_agent_mode

__all__ = [
    "create_agent_app",
    "set_agent_strategy",
    "add_tool",
    "remove_tool",
    "validate_agent_mode",
]
