"""Tests for frontend crash prevention validator."""

import pytest

from dify_workflow.frontend_validator import validate_frontend_compat
from dify_workflow.models import (
    IfElseCase,
    ModelConfig,
    Node,
    NodeData,
    NodeType,
    Position,
    StartVariable,
)


def _make_node(node_type: NodeType, **extra_data) -> Node:
    """Helper to create a Node with the given type and extra data fields."""
    data = NodeData(type=node_type, title="test", **extra_data)
    return Node(id="test-node", data=data, position=Position(x=0, y=0))


def _make_node_raw(node_type: str, extra: dict) -> Node:
    """Helper to create a Node with raw extra fields via pydantic extras."""
    data = NodeData(type=node_type, title="test", **extra)
    return Node(id="test-node", data=data, position=Position(x=0, y=0))


# ──────────────────────────────────────────────────────────────────
# Start node
# ──────────────────────────────────────────────────────────────────

class TestFeStartNode:
    def test_missing_variables_crashes(self):
        node = _make_node(NodeType.START, variables=None)
        errors = validate_frontend_compat(node)
        assert any("Frontend crash" in e.message and "variables" in e.message for e in errors)
        assert any(e.level == "error" for e in errors)

    def test_empty_variables_ok(self):
        node = _make_node(NodeType.START, variables=[])
        errors = validate_frontend_compat(node)
        assert not errors

    def test_with_variables_ok(self):
        node = _make_node(NodeType.START, variables=[
            StartVariable(variable="name", type="text-input"),
        ])
        errors = validate_frontend_compat(node)
        assert not errors


# ──────────────────────────────────────────────────────────────────
# IfElse node
# ──────────────────────────────────────────────────────────────────

class TestFeIfElseNode:
    def test_missing_cases_crashes(self):
        node = _make_node(NodeType.IF_ELSE) 
        errors = validate_frontend_compat(node)
        assert any("Frontend crash" in e.message and "cases" in e.message for e in errors)

    def test_missing_cases_with_legacy_fields_ok(self):
        """initialNodes() converts old format (logical_operator + conditions) to cases."""
        node = _make_node_raw("if-else", {
            "logical_operator": "and",
            "conditions": [{"id": "1", "comparison_operator": "contains"}],
        })
        errors = validate_frontend_compat(node)
        assert not any("cases" in e.message and e.level == "error" for e in errors)

    def test_cases_without_conditions_crashes(self):
        """Test that cases with empty conditions list still validate OK.
        Pydantic forces conditions to be a list, so None isn't possible.
        The real crash scenario is if cases itself is missing (tested above).
        """
        node = _make_node(NodeType.IF_ELSE, cases=[
            IfElseCase(case_id="true", conditions=[], logical_operator="and"),
        ])
        errors = validate_frontend_compat(node)
        # Empty conditions is valid (just no conditions set yet)
        assert not any(e.level == "error" for e in errors)

    def test_cases_without_case_id_crashes(self):
        node = _make_node_raw("if-else", {
            "cases": [{"case_id": "", "conditions": []}],  # empty case_id
        })
        errors = validate_frontend_compat(node)
        assert any("case_id" in e.message for e in errors)

    def test_valid_cases_ok(self):
        node = _make_node(NodeType.IF_ELSE, cases=[
            IfElseCase(case_id="true", conditions=[], logical_operator="and"),
        ])
        errors = validate_frontend_compat(node)
        assert not errors


# ──────────────────────────────────────────────────────────────────
# LLM node
# ──────────────────────────────────────────────────────────────────

class TestFeLLMNode:
    def test_missing_model_crashes(self):
        node = _make_node(NodeType.LLM)  # model defaults to None
        errors = validate_frontend_compat(node)
        assert any("Frontend crash" in e.message and "model" in e.message for e in errors)

    def test_model_without_provider_warns(self):
        node = _make_node(NodeType.LLM, model=ModelConfig(provider="", name="gpt-4"))
        errors = validate_frontend_compat(node)
        # Empty string provider — should warn
        assert any("provider" in e.message for e in errors)

    def test_valid_model_ok(self):
        node = _make_node(NodeType.LLM, model=ModelConfig(provider="openai", name="gpt-4"))
        errors = validate_frontend_compat(node)
        assert not errors


# ──────────────────────────────────────────────────────────────────
# QuestionClassifier node
# ──────────────────────────────────────────────────────────────────

class TestFeQuestionClassifierNode:
    def test_missing_model_crashes(self):
        node = _make_node_raw("question-classifier", {"classes": [{"id": "1", "name": "a"}]})
        errors = validate_frontend_compat(node)
        assert any("model" in e.message and e.level == "error" for e in errors)

    def test_missing_classes_crashes(self):
        node = _make_node(NodeType.QUESTION_CLASSIFIER, model=ModelConfig())
        errors = validate_frontend_compat(node)
        assert any("classes" in e.message and e.level == "error" for e in errors)

    def test_classes_missing_id_crashes(self):
        node = _make_node_raw("question-classifier", {
            "model": {"provider": "openai", "name": "gpt-4"},
            "classes": [{"name": "topic1"}],  # missing id
        })
        errors = validate_frontend_compat(node)
        assert any("classes[0]" in e.message and "id" in e.message for e in errors)

    def test_valid_ok(self):
        node = _make_node_raw("question-classifier", {
            "model": {"provider": "openai", "name": "gpt-4"},
            "classes": [{"id": "1", "name": "a"}, {"id": "2", "name": "b"}],
        })
        errors = validate_frontend_compat(node)
        assert not errors


# ──────────────────────────────────────────────────────────────────
# ParameterExtractor node
# ──────────────────────────────────────────────────────────────────

class TestFeParameterExtractorNode:
    def test_missing_model_crashes(self):
        node = _make_node(NodeType.PARAMETER_EXTRACTOR)
        errors = validate_frontend_compat(node)
        assert any("model" in e.message and e.level == "error" for e in errors)

    def test_with_model_ok(self):
        node = _make_node(NodeType.PARAMETER_EXTRACTOR, model=ModelConfig())
        errors = validate_frontend_compat(node)
        assert not errors


# ──────────────────────────────────────────────────────────────────
# HumanInput node
# ──────────────────────────────────────────────────────────────────

class TestFeHumanInputNode:
    def test_missing_delivery_methods_crashes(self):
        node = _make_node_raw("human-input", {"user_actions": []})
        errors = validate_frontend_compat(node)
        assert any("delivery_methods" in e.message and e.level == "error" for e in errors)

    def test_missing_user_actions_crashes(self):
        node = _make_node_raw("human-input", {"delivery_methods": []})
        errors = validate_frontend_compat(node)
        assert any("user_actions" in e.message and e.level == "error" for e in errors)

    def test_delivery_methods_not_array_crashes(self):
        node = _make_node_raw("human-input", {
            "delivery_methods": "webapp",
            "user_actions": [],
        })
        errors = validate_frontend_compat(node)
        assert any("delivery_methods" in e.message and "array" in e.message for e in errors)

    def test_user_actions_not_array_crashes(self):
        node = _make_node_raw("human-input", {
            "delivery_methods": [],
            "user_actions": "approve",
        })
        errors = validate_frontend_compat(node)
        assert any("user_actions" in e.message and "array" in e.message for e in errors)

    def test_valid_empty_arrays_ok(self):
        node = _make_node_raw("human-input", {
            "delivery_methods": [],
            "user_actions": [],
        })
        errors = validate_frontend_compat(node)
        assert not errors


# ──────────────────────────────────────────────────────────────────
# Tool node
# ──────────────────────────────────────────────────────────────────

class TestFeToolNode:
    def test_v2_config_missing_value_warns(self):
        node = _make_node_raw("tool", {
            "tool_node_version": "2",
            "tool_configurations": {
                "param1": {"type": "constant"},  # missing value
            },
            "tool_name": "test",
        })
        errors = validate_frontend_compat(node)
        assert any("value" in e.message for e in errors)

    def test_v2_config_with_value_ok(self):
        node = _make_node_raw("tool", {
            "tool_node_version": "2",
            "tool_configurations": {
                "param1": {"type": "constant", "value": "hello"},
            },
            "tool_name": "test",
        })
        errors = validate_frontend_compat(node)
        assert not errors

    def test_no_version_no_configs_ok(self):
        node = _make_node_raw("tool", {
            "tool_name": "test",
            "tool_configurations": {},
        })
        errors = validate_frontend_compat(node)
        assert not errors


# ──────────────────────────────────────────────────────────────────
# VariableAssigner / VariableAggregator node
# ──────────────────────────────────────────────────────────────────

class TestFeVariableAssignerNode:
    def test_group_enabled_missing_groups_crashes(self):
        node = _make_node_raw("variable-aggregator", {
            "advanced_settings": {"group_enabled": True},
            "output_type": "string",
        })
        errors = validate_frontend_compat(node)
        assert any("groups" in e.message and e.level == "error" for e in errors)

    def test_group_enabled_groups_not_array_crashes(self):
        node = _make_node_raw("variable-aggregator", {
            "advanced_settings": {"group_enabled": True, "groups": "invalid"},
            "output_type": "string",
        })
        errors = validate_frontend_compat(node)
        assert any("groups" in e.message and "array" in e.message for e in errors)

    def test_group_enabled_with_groups_ok(self):
        node = _make_node_raw("variable-aggregator", {
            "advanced_settings": {
                "group_enabled": True,
                "groups": [{"groupId": "g1", "group_name": "G1", "output_type": "string", "variables": []}],
            },
            "output_type": "string",
        })
        errors = validate_frontend_compat(node)
        assert not errors

    def test_no_advanced_settings_ok(self):
        node = _make_node_raw("variable-aggregator", {"output_type": "string"})
        errors = validate_frontend_compat(node)
        assert not errors


# ──────────────────────────────────────────────────────────────────
# Code node
# ──────────────────────────────────────────────────────────────────

class TestFeCodeNode:
    def test_variables_none_ok(self):
        """Code node with None variables — Pydantic prevents non-list, so test None."""
        node = _make_node(NodeType.CODE, variables=None, code="print(1)")
        errors = validate_frontend_compat(node)
        assert not errors

    def test_variables_empty_array_ok(self):
        node = _make_node(NodeType.CODE, variables=[], code="print(1)")
        errors = validate_frontend_compat(node)
        assert not errors


# ──────────────────────────────────────────────────────────────────
# ListOperator node
# ──────────────────────────────────────────────────────────────────

class TestFeListOperatorNode:
    def test_filter_by_conditions_not_array_crashes(self):
        node = _make_node_raw("list-operator", {
            "filter_by": {"enabled": True, "conditions": "invalid"},
        })
        errors = validate_frontend_compat(node)
        assert any("conditions" in e.message for e in errors)

    def test_filter_by_conditions_array_ok(self):
        node = _make_node_raw("list-operator", {
            "filter_by": {"enabled": True, "conditions": []},
        })
        errors = validate_frontend_compat(node)
        assert not errors


# ──────────────────────────────────────────────────────────────────
# Safe nodes (should return no errors)
# ──────────────────────────────────────────────────────────────────

class TestFeSafeNodes:
    """Nodes whose frontend components handle missing data safely."""

    @pytest.mark.parametrize("node_type", [
        NodeType.END,
        NodeType.ANSWER,
        NodeType.HTTP_REQUEST,
        NodeType.KNOWLEDGE_RETRIEVAL,
    ])
    def test_safe_nodes_no_errors(self, node_type):
        node = _make_node(node_type)
        errors = validate_frontend_compat(node)
        assert not errors


# ──────────────────────────────────────────────────────────────────
# Nodes not in dispatch table (should return empty)
# ──────────────────────────────────────────────────────────────────

class TestFeUnregisteredNodes:
    @pytest.mark.parametrize("node_type", [
        NodeType.TEMPLATE_TRANSFORM,
        NodeType.DOCUMENT_EXTRACTOR,
        NodeType.AGENT,
    ])
    def test_unregistered_nodes_return_empty(self, node_type):
        node = _make_node(node_type)
        errors = validate_frontend_compat(node)
        assert not errors


# ──────────────────────────────────────────────────────────────────
# Iteration / Loop (edge cases)
# ──────────────────────────────────────────────────────────────────

class TestFeIterationNode:
    def test_is_parallel_non_bool_warns(self):
        node = _make_node_raw("iteration", {"is_parallel": "yes"})
        errors = validate_frontend_compat(node)
        assert any("is_parallel" in e.message for e in errors)

    def test_is_parallel_bool_ok(self):
        node = _make_node_raw("iteration", {"is_parallel": False})
        errors = validate_frontend_compat(node)
        assert not errors

    def test_loop_returns_empty(self):
        node = _make_node(NodeType.LOOP)
        errors = validate_frontend_compat(node)
        assert not errors
