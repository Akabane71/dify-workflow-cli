"""Unit tests for workflow I/O operations."""

import json
import pytest
import yaml
from pathlib import Path

from dify_workflow.editor import add_node, create_minimal_workflow, create_llm_workflow
from dify_workflow.io import (
    load_workflow,
    save_workflow,
    load_workflow_from_string,
    workflow_to_string,
)
from dify_workflow.models import DifyWorkflowDSL, NodeType


@pytest.fixture
def tmp_yaml(tmp_path):
    return tmp_path / "test.yaml"


@pytest.fixture
def tmp_json(tmp_path):
    return tmp_path / "test.json"


class TestSaveAndLoad:
    def test_save_yaml(self, tmp_yaml):
        dsl = create_minimal_workflow("Save Test")
        path = save_workflow(dsl, tmp_yaml)
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        assert data["app"]["name"] == "Save Test"
        assert data["version"] == "0.6.0"

    def test_save_json(self, tmp_json):
        dsl = create_minimal_workflow("JSON Test")
        path = save_workflow(dsl, tmp_json)
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        data = json.loads(content)
        assert data["app"]["name"] == "JSON Test"

    def test_load_yaml(self, tmp_yaml):
        dsl = create_minimal_workflow("Load Test")
        save_workflow(dsl, tmp_yaml)
        loaded = load_workflow(tmp_yaml)
        assert loaded.app.name == "Load Test"
        assert len(loaded.workflow.graph.nodes) == 2

    def test_load_json(self, tmp_json):
        dsl = create_minimal_workflow("Load JSON")
        save_workflow(dsl, tmp_json)
        loaded = load_workflow(tmp_json)
        assert loaded.app.name == "Load JSON"

    def test_roundtrip_yaml(self, tmp_yaml):
        original = create_llm_workflow(name="Roundtrip", model_provider="openai", model_name="gpt-4")
        save_workflow(original, tmp_yaml)
        loaded = load_workflow(tmp_yaml)

        assert loaded.app.name == original.app.name
        assert len(loaded.workflow.graph.nodes) == len(original.workflow.graph.nodes)
        assert len(loaded.workflow.graph.edges) == len(original.workflow.graph.edges)

        # Check LLM node preserved
        llm = None
        for n in loaded.workflow.graph.nodes:
            if n.data.type == "llm":
                llm = n
        assert llm is not None
        assert llm.data.model.name == "gpt-4"

    def test_roundtrip_json(self, tmp_json):
        original = create_llm_workflow(name="JSON RT")
        save_workflow(original, tmp_json)
        loaded = load_workflow(tmp_json)
        assert loaded.app.name == "JSON RT"
        assert len(loaded.workflow.graph.nodes) == 3

    def test_variable_aggregator_selectors_roundtrip(self, tmp_yaml):
        dsl = create_minimal_workflow("Aggregator Roundtrip")
        add_node(
            dsl,
            NodeType.VARIABLE_AGGREGATOR,
            node_id="agg1",
            data_overrides={
                "output_type": "string",
                "variables": [["llm_a", "text"], ["llm_b", "text"]],
            },
        )

        save_workflow(dsl, tmp_yaml)
        loaded = load_workflow(tmp_yaml)
        agg = next(n for n in loaded.workflow.graph.nodes if n.id == "agg1")
        assert agg.data.variables == [["llm_a", "text"], ["llm_b", "text"]]

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_workflow("nonexistent.yaml")

    def test_invalid_content(self, tmp_yaml):
        tmp_yaml.write_text("not: a: valid: workflow: really", encoding="utf-8")
        # Should fail validation somewhat, but model_validate may be lenient
        # At minimum it should not crash
        with pytest.raises(Exception):
            load_workflow(tmp_yaml)


class TestStringIO:
    def test_to_yaml_string(self):
        dsl = create_minimal_workflow("String Test")
        s = workflow_to_string(dsl, fmt="yaml")
        data = yaml.safe_load(s)
        assert data["app"]["name"] == "String Test"

    def test_to_json_string(self):
        dsl = create_minimal_workflow("JSON String")
        s = workflow_to_string(dsl, fmt="json")
        data = json.loads(s)
        assert data["app"]["name"] == "JSON String"

    def test_from_yaml_string(self):
        dsl = create_minimal_workflow("From String")
        s = workflow_to_string(dsl, fmt="yaml")
        loaded = load_workflow_from_string(s)
        assert loaded.app.name == "From String"

    def test_from_json_string(self):
        dsl = create_minimal_workflow("From JSON")
        s = workflow_to_string(dsl, fmt="json")
        loaded = load_workflow_from_string(s, fmt="json")
        assert loaded.app.name == "From JSON"
