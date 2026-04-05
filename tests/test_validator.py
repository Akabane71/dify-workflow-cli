"""Unit tests for workflow validation."""

import pytest
from dify_workflow.editor import (
    add_edge,
    add_node,
    add_start_variable,
    create_minimal_workflow,
)
from dify_workflow.models import DifyWorkflowDSL, NodeType
from dify_workflow.validator import ValidationResult, validate_workflow


class TestValidateMinimalWorkflow:
    def test_valid_minimal(self):
        dsl = create_minimal_workflow()
        result = validate_workflow(dsl)
        assert result.valid is True
        assert not any(e.level == "error" for e in result.errors)

    def test_empty_graph(self):
        dsl = DifyWorkflowDSL()
        result = validate_workflow(dsl)
        assert result.valid is False
        assert any("no nodes" in e.message for e in result.errors)


class TestValidateTopLevel:
    def test_missing_version(self):
        dsl = create_minimal_workflow()
        dsl.version = ""
        result = validate_workflow(dsl)
        assert any("version" in e.message for e in result.errors)

    def test_missing_app_name(self):
        dsl = create_minimal_workflow()
        dsl.app.name = ""
        result = validate_workflow(dsl)
        assert any("app name" in e.message for e in result.errors)


class TestValidateGraphStructure:
    def test_duplicate_node_ids(self):
        dsl = DifyWorkflowDSL()
        add_node(dsl, NodeType.START, node_id="dup")
        add_node(dsl, NodeType.END, node_id="dup")
        result = validate_workflow(dsl)
        assert any("Duplicate node ID" in e.message for e in result.errors)

    def test_no_start_node(self):
        dsl = DifyWorkflowDSL()
        add_node(dsl, NodeType.END, node_id="end1")
        result = validate_workflow(dsl)
        assert any("start node" in e.message.lower() for e in result.errors)

    def test_start_and_trigger_coexist(self):
        dsl = DifyWorkflowDSL()
        add_node(dsl, NodeType.START, node_id="s1")
        add_node(dsl, NodeType.TRIGGER_WEBHOOK, node_id="tw1")
        result = validate_workflow(dsl)
        assert any("coexist" in e.message for e in result.errors)

    def test_no_end_node_warning(self):
        dsl = DifyWorkflowDSL()
        add_node(dsl, NodeType.START, node_id="s1")
        result = validate_workflow(dsl)
        assert any("end" in e.message.lower() and e.level == "warning" for e in result.errors)


class TestValidateNodes:
    def test_llm_no_model(self):
        dsl = DifyWorkflowDSL()
        add_node(dsl, NodeType.START, node_id="s1")
        add_node(dsl, NodeType.LLM, node_id="llm1", data_overrides={"model": None})
        result = validate_workflow(dsl)
        assert any("model" in e.message.lower() for e in result.errors)

    def test_duplicate_start_variable(self):
        dsl = create_minimal_workflow()
        add_start_variable(dsl, "start_node", "query")  # duplicate
        result = validate_workflow(dsl)
        assert any("Duplicate start variable" in e.message for e in result.errors)


class TestValidateEdges:
    def test_edge_to_nonexistent_node(self):
        dsl = create_minimal_workflow()
        from dify_workflow.models import Edge, EdgeData
        dsl.workflow.graph.edges.append(
            Edge(source="start_node", target="ghost", data=EdgeData())
        )
        result = validate_workflow(dsl)
        assert any("nonexistent" in e.message for e in result.errors)

    def test_self_loop(self):
        dsl = create_minimal_workflow()
        from dify_workflow.models import Edge, EdgeData
        dsl.workflow.graph.edges.append(
            Edge(id="loop", source="start_node", target="start_node", data=EdgeData())
        )
        result = validate_workflow(dsl)
        assert any("Self-loop" in e.message for e in result.errors)

    def test_cycle_detected(self):
        """Cycle A→B→C→A should produce an error (Dify strips cycle edges)."""
        dsl = create_minimal_workflow()
        add_node(dsl, NodeType.CODE, node_id="a")
        add_node(dsl, NodeType.CODE, node_id="b")
        add_node(dsl, NodeType.CODE, node_id="c")
        add_edge(dsl, "start_node", "a")
        add_edge(dsl, "a", "b")
        add_edge(dsl, "b", "c")
        add_edge(dsl, "c", "a")  # back edge creating cycle
        result = validate_workflow(dsl)
        assert any("Cycle" in e.message or "cycle" in e.message for e in result.errors)

    def test_no_cycle_no_error(self):
        """DAG without cycles should not trigger cycle error."""
        dsl = create_minimal_workflow()
        add_node(dsl, NodeType.CODE, node_id="a")
        add_node(dsl, NodeType.CODE, node_id="b")
        add_edge(dsl, "start_node", "a")
        add_edge(dsl, "a", "b")
        result = validate_workflow(dsl)
        assert not any("cycle" in e.message.lower() for e in result.errors)


class TestValidateConnectivity:
    def test_unreachable_node(self):
        dsl = create_minimal_workflow()
        add_node(dsl, NodeType.CODE, node_id="orphan")
        result = validate_workflow(dsl)
        assert any("unreachable" in e.message.lower() for e in result.errors)


class TestValidationResult:
    def test_to_dict(self):
        r = ValidationResult()
        r.add_error("bad thing", node_id="n1")
        r.add_warning("minor issue")
        d = r.to_dict()
        assert d["valid"] is False
        assert d["error_count"] == 1
        assert d["warning_count"] == 1
        assert len(d["errors"]) == 2
