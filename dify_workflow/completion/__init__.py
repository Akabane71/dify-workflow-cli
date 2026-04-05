"""Completion mode (mode='completion') — single-turn text generation."""

from .editor import create_completion_app, enable_more_like_this
from .validator import validate_completion_mode

__all__ = [
    "create_completion_app",
    "enable_more_like_this",
    "validate_completion_mode",
]
