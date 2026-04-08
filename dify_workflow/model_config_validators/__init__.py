"""Shared model_config validators for chat / agent-chat / completion modes.

Each sub-module corresponds to one Dify backend ConfigManager.
All validators accept a ModelConfigContent (or raw dict) and a ValidationResult,
appending errors/warnings directly into the result.
"""
