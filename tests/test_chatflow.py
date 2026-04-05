"""Tests for chatflow module (mode='advanced-chat')."""

import pytest

from dify_workflow.chatflow.editor import create_chatflow, create_knowledge_chatflow
from dify_workflow.chatflow.validator import validate_chatflow_mode
from dify_workflow.models import AppMode, DifyDSL, NodeType
from dify_workflow.validator import ValidationResult, validate_workflow


class TestCreateChatflow:
    def test_basic_chatflow(self):
        dsl = create_chatflow(name="My Chatflow")
        assert dsl.app.mode == AppMode.ADVANCED_CHAT
        assert dsl.app.name == "My Chatflow"
        assert dsl.is_workflow_based
        assert not dsl.is_config_based

        nodes = dsl.workflow.graph.nodes
        assert len(nodes) == 3
        types = {n.data.type for n in nodes}
        assert NodeType.START in types
        assert NodeType.LLM in types
        assert NodeType.ANSWER in types

        edges = dsl.workflow.graph.edges
        assert len(edges) == 2

    def test_chatflow_has_answer_node(self):
        dsl = create_chatflow()
        answer_nodes = [n for n in dsl.workflow.graph.nodes if n.data.type == NodeType.ANSWER]
        assert len(answer_nodes) == 1
        assert answer_nodes[0].data.title == "Answer"

    def test_chatflow_llm_has_memory(self):
        dsl = create_chatflow()
        llm = [n for n in dsl.workflow.graph.nodes if n.data.type == NodeType.LLM][0]
        extra = llm.data.__pydantic_extra__ or {}
        memory = getattr(llm.data, "memory", None)
        if memory:
            assert memory.enabled
        else:
            assert extra.get("memory", {}).get("enabled")

    def test_chatflow_custom_model(self):
        dsl = create_chatflow(model_provider="anthropic", model_name="claude-3-opus")
        llm = [n for n in dsl.workflow.graph.nodes if n.data.type == NodeType.LLM][0]
        model = llm.data.model
        if hasattr(model, "provider"):
            assert model.provider == "anthropic"
            assert model.name == "claude-3-opus"
        else:
            extra = llm.data.__pydantic_extra__ or {}
            m = extra.get("model", {})
            assert m.get("provider") == "anthropic"

    def test_knowledge_chatflow(self):
        dsl = create_knowledge_chatflow(name="KB Chat", dataset_ids=["ds1", "ds2"])
        assert dsl.app.mode == AppMode.ADVANCED_CHAT
        nodes = dsl.workflow.graph.nodes
        assert len(nodes) == 4
        types = [n.data.type for n in nodes]
        assert NodeType.KNOWLEDGE_RETRIEVAL in types
        assert NodeType.ANSWER in types

        edges = dsl.workflow.graph.edges
        assert len(edges) == 3


class TestChatflowValidation:
    def test_valid_chatflow(self):
        dsl = create_chatflow()
        result = validate_workflow(dsl)
        assert result.valid

    def test_chatflow_no_answer_warning(self):
        dsl = create_chatflow()
        # Replace answer with end node
        for n in dsl.workflow.graph.nodes:
            if n.data.type == NodeType.ANSWER:
                n.data.type = NodeType.END
                break
        result = validate_workflow(dsl)
        warnings = [e for e in result.errors if e.level == "warning"]
        msgs = [w.message for w in warnings]
        assert any("Answer" in m for m in msgs)

    def test_knowledge_chatflow_valid(self):
        dsl = create_knowledge_chatflow(dataset_ids=["ds-test-001"])
        result = validate_workflow(dsl)
        assert result.valid
