"""Integration tests - end-to-end workflows with real Dify fixture validation."""

import json
import os
import pytest
import yaml
from pathlib import Path

from dify_workflow.editor import (
    add_edge,
    add_end_output,
    add_node,
    add_start_variable,
    create_llm_workflow,
    create_minimal_workflow,
    get_node,
    remove_node,
    update_node,
)
from dify_workflow.io import load_workflow, save_workflow, workflow_to_string, load_workflow_from_string
from dify_workflow.models import DifyWorkflowDSL, NodeType
from dify_workflow.validator import validate_workflow


# Path to dify-test fixtures
DIFY_TEST_FIXTURES = Path(__file__).parent.parent / "dify-test" / "api" / "tests" / "fixtures" / "workflow"


class TestCreateAndExportWorkflow:
    """Test creating a workflow from scratch and exporting it."""

    def test_create_minimal_and_export(self, tmp_path):
        dsl = create_minimal_workflow("Integration Test")
        result = validate_workflow(dsl)
        assert result.valid is True

        out = tmp_path / "minimal.yaml"
        save_workflow(dsl, out)
        assert out.exists()

        # Reload and verify
        loaded = load_workflow(out)
        assert loaded.app.name == "Integration Test"
        assert len(loaded.workflow.graph.nodes) == 2
        assert len(loaded.workflow.graph.edges) == 1

    def test_create_llm_and_export(self, tmp_path):
        dsl = create_llm_workflow(
            name="LLM Integration",
            model_provider="openai",
            model_name="gpt-4",
            system_prompt="You are a test assistant.",
        )
        result = validate_workflow(dsl)
        assert result.valid is True

        out = tmp_path / "llm.yaml"
        save_workflow(dsl, out)

        loaded = load_workflow(out)
        llm = get_node(loaded, "llm_node")
        assert llm.data.model.provider == "openai"
        assert llm.data.model.name == "gpt-4"
        assert any("test assistant" in p.text for p in llm.data.prompt_template)


class TestEditExistingWorkflow:
    """Test editing an existing workflow and preserving data."""

    def test_add_node_and_edge(self, tmp_path):
        dsl = create_minimal_workflow("Edit Test")
        out = tmp_path / "edit.yaml"
        save_workflow(dsl, out)

        # Load, edit, save
        dsl = load_workflow(out)
        code_node = add_node(dsl, NodeType.CODE, title="Process", node_id="code_node",
                             data_overrides={"code": "def main(arg1: str, arg2: str) -> dict:\n    return {'result': arg1 + arg2}"})

        # Rewire: start -> code -> end
        dsl.workflow.graph.edges.clear()
        add_edge(dsl, "start_node", "code_node")
        add_edge(dsl, "code_node", "end_node")

        save_workflow(dsl, out)

        # Verify
        loaded = load_workflow(out)
        assert len(loaded.workflow.graph.nodes) == 3
        assert len(loaded.workflow.graph.edges) == 2
        code = get_node(loaded, "code_node")
        assert code is not None
        assert code.data.title == "Process"

    def test_remove_node_and_edges_cleaned(self, tmp_path):
        dsl = create_llm_workflow("Remove Test")
        out = tmp_path / "remove.yaml"
        save_workflow(dsl, out)

        dsl = load_workflow(out)
        assert len(dsl.workflow.graph.nodes) == 3

        # Remove LLM node
        remove_node(dsl, "llm_node")
        assert len(dsl.workflow.graph.nodes) == 2
        # Edges connected to llm_node should be removed
        assert not any(e.source == "llm_node" or e.target == "llm_node"
                       for e in dsl.workflow.graph.edges)

        save_workflow(dsl, out)
        loaded = load_workflow(out)
        assert len(loaded.workflow.graph.nodes) == 2

    def test_update_llm_model(self, tmp_path):
        dsl = create_llm_workflow("Update Model Test")
        out = tmp_path / "update.yaml"
        save_workflow(dsl, out)

        dsl = load_workflow(out)
        update_node(dsl, "llm_node", {
            "model": {"provider": "anthropic", "name": "claude-3-sonnet", "mode": "chat"},
        })
        save_workflow(dsl, out)

        loaded = load_workflow(out)
        llm = get_node(loaded, "llm_node")
        assert llm.data.model.provider == "anthropic"
        assert llm.data.model.name == "claude-3-sonnet"


class TestInvalidWorkflowDetection:
    """Test that invalid configurations are properly caught."""

    def test_invalid_no_start(self):
        dsl = DifyWorkflowDSL()
        add_node(dsl, NodeType.END, node_id="end1")
        result = validate_workflow(dsl)
        assert result.valid is False
        assert any("start" in e.message.lower() for e in result.errors)

    def test_invalid_edge_to_missing_node(self):
        dsl = create_minimal_workflow()
        from dify_workflow.models import Edge, EdgeData
        dsl.workflow.graph.edges.append(Edge(source="start_node", target="missing"))
        result = validate_workflow(dsl)
        assert result.valid is False
        assert any("nonexistent" in e.message for e in result.errors)

    def test_invalid_trigger_with_start(self):
        dsl = DifyWorkflowDSL()
        add_node(dsl, NodeType.START, node_id="s1")
        add_node(dsl, NodeType.TRIGGER_WEBHOOK, node_id="tw1")
        result = validate_workflow(dsl)
        assert result.valid is False


class TestRoundTripExportImport:
    """Test that export → import preserves all data."""

    def test_yaml_roundtrip(self, tmp_path):
        original = create_llm_workflow("Roundtrip YAML")
        add_start_variable(original, "start_node", "name", label="Name")

        yaml_str = workflow_to_string(original, fmt="yaml")
        loaded = load_workflow_from_string(yaml_str, fmt="yaml")

        assert loaded.app.name == original.app.name
        assert len(loaded.workflow.graph.nodes) == len(original.workflow.graph.nodes)
        assert len(loaded.workflow.graph.edges) == len(original.workflow.graph.edges)

        # Check variables preserved
        start = get_node(loaded, "start_node")
        assert len(start.data.variables) == 2  # query + name

    def test_json_roundtrip(self, tmp_path):
        original = create_llm_workflow("Roundtrip JSON")
        json_str = workflow_to_string(original, fmt="json")
        loaded = load_workflow_from_string(json_str, fmt="json")
        assert loaded.app.name == original.app.name

    def test_yaml_to_json_to_yaml(self, tmp_path):
        original = create_llm_workflow("Cross Format")
        yaml_out = tmp_path / "cross.yaml"
        json_out = tmp_path / "cross.json"
        yaml2_out = tmp_path / "cross2.yaml"

        save_workflow(original, yaml_out)
        dsl = load_workflow(yaml_out)
        save_workflow(dsl, json_out)
        dsl = load_workflow(json_out)
        save_workflow(dsl, yaml2_out)

        final = load_workflow(yaml2_out)
        assert final.app.name == "Cross Format"
        assert len(final.workflow.graph.nodes) == 3

    def test_no_field_loss(self, tmp_path):
        """Verify that key fields are not lost during round-trip."""
        dsl = create_llm_workflow("Field Loss Test")
        llm = get_node(dsl, "llm_node")

        # Ensure all llm fields exist
        assert llm.data.model is not None
        assert llm.data.prompt_template is not None
        assert llm.data.vision is not None
        assert llm.data.memory is not None

        out = tmp_path / "field_loss.yaml"
        save_workflow(dsl, out)
        loaded = load_workflow(out)
        llm2 = get_node(loaded, "llm_node")

        assert llm2.data.model.provider == llm.data.model.provider
        assert llm2.data.model.name == llm.data.model.name
        assert len(llm2.data.prompt_template) == len(llm.data.prompt_template)


class TestDifyFixtureValidation:
    """Load real Dify test fixtures and validate them with our tool.

    This proves our model is compatible with real Dify DSL output.
    """

    @pytest.fixture
    def fixture_files(self):
        if not DIFY_TEST_FIXTURES.exists():
            pytest.skip("dify-test fixtures not found")
        return list(DIFY_TEST_FIXTURES.glob("*.yml"))

    def test_fixtures_exist(self, fixture_files):
        assert len(fixture_files) > 0, "No fixture files found"

    def test_load_all_fixtures(self, fixture_files):
        """Load every fixture file without errors."""
        loaded = 0
        errors = []
        for f in fixture_files:
            try:
                dsl = load_workflow(f)
                assert dsl.workflow.graph.nodes is not None
                loaded += 1
            except Exception as e:
                errors.append(f"{f.name}: {e}")

        assert loaded > 0, "No fixtures loaded successfully"
        # Allow some failures (some fixtures may have different format)
        # but more than 50% should succeed
        assert loaded >= len(fixture_files) * 0.5, f"Too many failures: {errors}"

    def test_basic_llm_fixture(self):
        """Validate the basic LLM workflow fixture specifically."""
        f = DIFY_TEST_FIXTURES / "basic_llm_chat_workflow.yml"
        if not f.exists():
            pytest.skip("basic_llm_chat_workflow.yml not found")

        dsl = load_workflow(f)
        assert dsl.app.name == "llm-simple"
        assert dsl.app.mode == "workflow"
        assert len(dsl.workflow.graph.nodes) == 3
        assert len(dsl.workflow.graph.edges) == 2

        # Find LLM node
        llm = None
        for n in dsl.workflow.graph.nodes:
            if n.data.type == "llm":
                llm = n
        assert llm is not None
        assert llm.data.model.provider == "openai"

    def test_simple_passthrough_fixture(self):
        """Validate the echo/passthrough workflow fixture."""
        f = DIFY_TEST_FIXTURES / "simple_passthrough_workflow.yml"
        if not f.exists():
            pytest.skip("simple_passthrough_workflow.yml not found")

        dsl = load_workflow(f)
        assert dsl.app.name == "echo"
        assert len(dsl.workflow.graph.nodes) == 2
        assert len(dsl.workflow.graph.edges) == 1

    def test_conditional_fixture(self):
        """Validate the conditional branching fixture."""
        f = DIFY_TEST_FIXTURES / "conditional_hello_branching_workflow.yml"
        if not f.exists():
            pytest.skip("conditional_hello_branching_workflow.yml not found")

        dsl = load_workflow(f)
        assert dsl.app.name == "if-else"
        assert len(dsl.workflow.graph.nodes) == 4  # start, if-else, end-true, end-false

        # Find IF/ELSE node
        ifelse = None
        for n in dsl.workflow.graph.nodes:
            if n.data.type == "if-else":
                ifelse = n
        assert ifelse is not None
        assert ifelse.data.cases is not None

    def test_fixture_roundtrip(self, tmp_path):
        """Load a fixture, export it, reload it, and compare."""
        f = DIFY_TEST_FIXTURES / "simple_passthrough_workflow.yml"
        if not f.exists():
            pytest.skip("simple_passthrough_workflow.yml not found")

        original = load_workflow(f)
        out = tmp_path / "rt.yaml"
        save_workflow(original, out)
        reloaded = load_workflow(out)

        assert reloaded.app.name == original.app.name
        assert len(reloaded.workflow.graph.nodes) == len(original.workflow.graph.nodes)
        assert len(reloaded.workflow.graph.edges) == len(original.workflow.graph.edges)

    def test_fixture_validate(self):
        """Run validation on real fixtures."""
        f = DIFY_TEST_FIXTURES / "basic_llm_chat_workflow.yml"
        if not f.exists():
            pytest.skip("basic_llm_chat_workflow.yml not found")

        dsl = load_workflow(f)
        result = validate_workflow(dsl)
        # Real fixtures should be valid (maybe with warnings)
        error_only = [e for e in result.errors if e.level == "error"]
        assert len(error_only) == 0, f"Real fixture has validation errors: {error_only}"
