"""Unit tests for workflow editing operations."""

import pytest
from dify_workflow.editor import (
    add_edge,
    add_end_output,
    add_node,
    add_start_variable,
    create_llm_workflow,
    create_minimal_workflow,
    get_edges_for_node,
    get_node,
    remove_edge,
    remove_node,
    set_node_title,
    update_node,
)
from dify_workflow.models import DifyWorkflowDSL, NodeType


@pytest.fixture
def empty_dsl():
    return DifyWorkflowDSL()


@pytest.fixture
def minimal_dsl():
    return create_minimal_workflow(name="Test")


class TestAddNode:
    def test_add_start_node(self, empty_dsl):
        node = add_node(empty_dsl, NodeType.START, title="Start")
        assert node.data.type == NodeType.START
        assert node.data.title == "Start"
        assert len(empty_dsl.workflow.graph.nodes) == 1

    def test_add_end_node(self, empty_dsl):
        node = add_node(empty_dsl, NodeType.END, title="End")
        assert node.data.type == NodeType.END

    def test_add_llm_node(self, empty_dsl):
        node = add_node(empty_dsl, NodeType.LLM, title="LLM")
        assert node.data.model is not None
        assert node.data.prompt_template is not None

    def test_add_code_node(self, empty_dsl):
        node = add_node(empty_dsl, NodeType.CODE, title="Code")
        assert "def main" in node.data.code
        assert node.data.code_language == "python3"
        extras = node.data.__pydantic_extra__ or {}
        assert isinstance(extras.get("outputs"), dict)
        assert "result" in extras["outputs"]
        # Code node variables are stored in typed field (StartVariable with value_selector)
        assert isinstance(node.data.variables, list)
        assert len(node.data.variables) == 2
        assert node.data.variables[0].variable == "arg1"

    def test_add_ifelse_node(self, empty_dsl):
        node = add_node(empty_dsl, NodeType.IF_ELSE, title="Condition")
        assert node.data.cases is not None

    def test_add_with_custom_id(self, empty_dsl):
        node = add_node(empty_dsl, NodeType.START, node_id="my_id")
        assert node.id == "my_id"

    def test_add_with_position(self, empty_dsl):
        node = add_node(empty_dsl, NodeType.START, position=(100, 200))
        assert node.position.x == 100
        assert node.position.y == 200

    def test_add_with_data_overrides(self, empty_dsl):
        node = add_node(empty_dsl, NodeType.LLM, data_overrides={
            "model": {"provider": "anthropic", "name": "claude-3"},
        })
        assert node.data.model.provider == "anthropic"

    def test_auto_layout(self, empty_dsl):
        n1 = add_node(empty_dsl, NodeType.START, position=(30, 227))
        n2 = add_node(empty_dsl, NodeType.END)
        assert n2.position.x > n1.position.x

    def test_string_node_type(self, empty_dsl):
        node = add_node(empty_dsl, "llm", title="LLM")
        assert node.data.type == NodeType.LLM

    def test_add_answer_node(self, empty_dsl):
        node = add_node(empty_dsl, NodeType.ANSWER, title="Answer")
        assert node.data.__pydantic_extra__["answer"] == ""

    def test_add_question_classifier_node(self, empty_dsl):
        node = add_node(empty_dsl, NodeType.QUESTION_CLASSIFIER)
        assert node.data.model is not None
        classes = node.data.__pydantic_extra__["classes"]
        assert len(classes) == 2
        assert classes[0]["id"] == "1"
        assert classes[1]["id"] == "2"

    def test_add_parameter_extractor_node(self, empty_dsl):
        node = add_node(empty_dsl, NodeType.PARAMETER_EXTRACTOR)
        assert node.data.model is not None
        assert node.data.__pydantic_extra__["parameters"] == []

    def test_add_variable_aggregator_node(self, empty_dsl):
        node = add_node(empty_dsl, NodeType.VARIABLE_AGGREGATOR)
        assert node.data.__pydantic_extra__["output_type"] == "string"

    def test_add_variable_assigner_node(self, empty_dsl):
        node = add_node(empty_dsl, NodeType.VARIABLE_ASSIGNER)
        assert node.data.__pydantic_extra__["version"] == "2"
        assert node.data.__pydantic_extra__["items"] == []

    def test_add_list_operator_node(self, empty_dsl):
        node = add_node(empty_dsl, NodeType.LIST_OPERATOR)
        assert node.data.__pydantic_extra__["filter_by"]["enabled"] is False
        assert node.data.__pydantic_extra__["limit"]["enabled"] is False

    def test_add_iteration_node(self, empty_dsl):
        node = add_node(empty_dsl, NodeType.ITERATION)
        assert node.data.iterator_selector == []
        assert node.data.__pydantic_extra__["is_parallel"] is False

    def test_add_loop_node(self, empty_dsl):
        node = add_node(empty_dsl, NodeType.LOOP)
        assert node.data.__pydantic_extra__["loop_count"] == 10
        assert node.data.__pydantic_extra__["break_conditions"] == []

    def test_add_agent_node(self, empty_dsl):
        node = add_node(empty_dsl, NodeType.AGENT)
        assert node.data.__pydantic_extra__["agent_strategy_provider_name"] == ""

    def test_add_document_extractor_node(self, empty_dsl):
        node = add_node(empty_dsl, NodeType.DOCUMENT_EXTRACTOR)
        assert node.data.__pydantic_extra__["is_array_file"] is False

    def test_add_human_input_node(self, empty_dsl):
        node = add_node(empty_dsl, NodeType.HUMAN_INPUT)
        assert node.data.__pydantic_extra__["timeout"] == 24
        assert node.data.__pydantic_extra__["inputs"] == []

    def test_add_knowledge_index_node(self, empty_dsl):
        node = add_node(empty_dsl, NodeType.KNOWLEDGE_INDEX)
        assert node.data.__pydantic_extra__["chunk_structure"] == "text_model"

    def test_add_datasource_node(self, empty_dsl):
        node = add_node(empty_dsl, NodeType.DATASOURCE)
        assert node.data.provider_type == "local_file"

    def test_add_trigger_webhook_node(self, empty_dsl):
        node = add_node(empty_dsl, NodeType.TRIGGER_WEBHOOK)
        assert node.data.method == "get"
        assert node.data.__pydantic_extra__["content_type"] == "application/json"

    def test_add_trigger_schedule_node(self, empty_dsl):
        node = add_node(empty_dsl, NodeType.TRIGGER_SCHEDULE)
        assert node.data.__pydantic_extra__["mode"] == "visual"
        assert node.data.__pydantic_extra__["frequency"] == "daily"

    def test_add_trigger_plugin_node(self, empty_dsl):
        node = add_node(empty_dsl, NodeType.TRIGGER_PLUGIN)
        assert node.data.__pydantic_extra__["event_name"] == ""


class TestRemoveNode:
    def test_remove_existing(self, minimal_dsl):
        assert len(minimal_dsl.workflow.graph.nodes) == 2
        assert len(minimal_dsl.workflow.graph.edges) == 1
        removed = remove_node(minimal_dsl, "end_node")
        assert removed is True
        assert len(minimal_dsl.workflow.graph.nodes) == 1
        assert len(minimal_dsl.workflow.graph.edges) == 0  # edges cleaned up

    def test_remove_nonexistent(self, minimal_dsl):
        removed = remove_node(minimal_dsl, "nonexistent")
        assert removed is False


class TestGetNode:
    def test_found(self, minimal_dsl):
        node = get_node(minimal_dsl, "start_node")
        assert node is not None
        assert node.data.type == NodeType.START

    def test_not_found(self, minimal_dsl):
        assert get_node(minimal_dsl, "nope") is None


class TestUpdateNode:
    def test_update_title(self, minimal_dsl):
        node = update_node(minimal_dsl, "start_node", {"title": "New Title"})
        assert node is not None
        assert node.data.title == "New Title"

    def test_update_typed_list_fields_are_revalidated(self, minimal_dsl):
        node = update_node(minimal_dsl, "start_node", {
            "variables": [
                {
                    "variable": "user_query",
                    "label": "用户诉求",
                    "type": "paragraph",
                    "required": True,
                    "options": [],
                },
                {
                    "variable": "order_id",
                    "label": "订单号",
                    "type": "text-input",
                    "required": False,
                    "options": [],
                },
            ]
        })

        assert node is not None
        assert node.data.variables is not None
        assert node.data.variables[0].variable == "user_query"
        assert node.data.variables[0].label == "用户诉求"
        assert node.data.variables[1].variable == "order_id"

    def test_update_nonexistent(self, minimal_dsl):
        assert update_node(minimal_dsl, "nope", {"title": "X"}) is None


class TestSetNodeTitle:
    def test_set(self, minimal_dsl):
        assert set_node_title(minimal_dsl, "start_node", "New") is True
        assert get_node(minimal_dsl, "start_node").data.title == "New"

    def test_not_found(self, minimal_dsl):
        assert set_node_title(minimal_dsl, "nope", "X") is False


class TestAddStartVariable:
    def test_add(self, minimal_dsl):
        assert add_start_variable(minimal_dsl, "start_node", "name", label="Name") is True
        node = get_node(minimal_dsl, "start_node")
        assert any(v.variable == "name" for v in node.data.variables)

    def test_wrong_node_type(self, minimal_dsl):
        assert add_start_variable(minimal_dsl, "end_node", "x") is False


class TestAddEndOutput:
    def test_add(self, minimal_dsl):
        assert add_end_output(minimal_dsl, "end_node", "extra", ["start_node", "query"]) is True
        node = get_node(minimal_dsl, "end_node")
        assert any(o.variable == "extra" for o in node.data.outputs)

    def test_wrong_node_type(self, minimal_dsl):
        assert add_end_output(minimal_dsl, "start_node", "x", []) is False


class TestAddEdge:
    def test_add(self, minimal_dsl):
        # Remove existing edge first
        minimal_dsl.workflow.graph.edges.clear()
        edge = add_edge(minimal_dsl, "start_node", "end_node")
        assert edge is not None
        assert edge.source == "start_node"
        assert edge.target == "end_node"

    def test_nonexistent_node(self, minimal_dsl):
        assert add_edge(minimal_dsl, "start_node", "nonexistent") is None


class TestRemoveEdge:
    def test_remove(self, minimal_dsl):
        edges = minimal_dsl.workflow.graph.edges
        assert len(edges) == 1
        edge_id = edges[0].id
        assert remove_edge(minimal_dsl, edge_id) is True
        assert len(minimal_dsl.workflow.graph.edges) == 0

    def test_nonexistent(self, minimal_dsl):
        assert remove_edge(minimal_dsl, "nope") is False


class TestGetEdgesForNode:
    def test_get(self, minimal_dsl):
        edges = get_edges_for_node(minimal_dsl, "start_node")
        assert len(edges) == 1


class TestCreateMinimalWorkflow:
    def test_default(self):
        dsl = create_minimal_workflow()
        assert dsl.app.name == "Untitled Workflow"
        assert len(dsl.workflow.graph.nodes) == 2
        assert len(dsl.workflow.graph.edges) == 1

        types = {n.data.type for n in dsl.workflow.graph.nodes}
        assert NodeType.START in types
        assert NodeType.END in types

    def test_custom(self):
        dsl = create_minimal_workflow("My Flow", "A description")
        assert dsl.app.name == "My Flow"
        assert dsl.app.description == "A description"

    def test_with_input_variables(self):
        dsl = create_minimal_workflow(input_variables=[
            {"variable": "name", "label": "Name"},
            {"variable": "age", "var_type": "number"},
        ])
        start = get_node(dsl, "start_node")
        assert len(start.data.variables) == 2


class TestCreateLlmWorkflow:
    def test_default(self):
        dsl = create_llm_workflow()
        assert len(dsl.workflow.graph.nodes) == 3
        assert len(dsl.workflow.graph.edges) == 2

        llm = get_node(dsl, "llm_node")
        assert llm is not None
        assert llm.data.model.provider == "openai"

    def test_custom_model(self):
        dsl = create_llm_workflow(model_provider="anthropic", model_name="claude-3-opus")
        llm = get_node(dsl, "llm_node")
        assert llm.data.model.provider == "anthropic"
        assert llm.data.model.name == "claude-3-opus"
