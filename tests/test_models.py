"""Unit tests for workflow models."""

import pytest
from dify_workflow.models import (
    AppInfo,
    AppMode,
    DifyWorkflowDSL,
    Edge,
    EdgeData,
    Features,
    Graph,
    ModelConfigContent,
    Node,
    NodeData,
    NodeType,
    OutputVariable,
    Position,
    StartVariable,
    WorkflowContent,
)


class TestNodeType:
    def test_all_node_types_exist(self):
        expected = [
            "start", "end", "answer", "llm", "tool", "code", "if-else",
            "template-transform", "question-classifier", "parameter-extractor",
            "http-request", "knowledge-retrieval", "variable-aggregator",
            "assigner", "list-operator",
            "iteration", "loop", "agent", "document-extractor", "human-input",
            "knowledge-index", "datasource",
            "trigger-webhook", "trigger-schedule", "trigger-plugin",
        ]
        for t in expected:
            assert NodeType(t) is not None

    def test_node_type_values(self):
        assert NodeType.START == "start"
        assert NodeType.LLM == "llm"
        assert NodeType.IF_ELSE == "if-else"
        assert NodeType.VARIABLE_ASSIGNER == "assigner"
        assert NodeType.LIST_OPERATOR == "list-operator"
        assert NodeType.KNOWLEDGE_INDEX == "knowledge-index"


class TestPosition:
    def test_default(self):
        p = Position()
        assert p.x == 0.0
        assert p.y == 0.0

    def test_custom(self):
        p = Position(x=100, y=200)
        assert p.x == 100.0
        assert p.y == 200.0


class TestStartVariable:
    def test_basic(self):
        v = StartVariable(variable="query")
        assert v.variable == "query"
        assert v.label == "query"
        assert v.type == "text-input"
        assert v.required is True

    def test_custom(self):
        v = StartVariable(variable="name", label="Name", type="paragraph", required=False)
        assert v.label == "Name"
        assert v.type == "paragraph"


class TestNodeData:
    def test_start_node(self):
        nd = NodeData(type=NodeType.START, title="Start", variables=[])
        assert nd.type == NodeType.START
        assert nd.variables == []

    def test_variable_aggregator_selectors(self):
        nd = NodeData(
            type=NodeType.VARIABLE_AGGREGATOR,
            title="Aggregator",
            variables=[["llm_a", "text"], ["llm_b", "text"]],
        )
        assert nd.variables == [["llm_a", "text"], ["llm_b", "text"]]

    def test_end_node(self):
        nd = NodeData(type=NodeType.END, title="End", outputs=[
            OutputVariable(variable="result", value_selector=["start", "query"])
        ])
        assert len(nd.outputs) == 1
        assert nd.outputs[0].variable == "result"

    def test_llm_node(self):
        nd = NodeData(
            type=NodeType.LLM, title="LLM",
            model={"provider": "openai", "name": "gpt-4"},
            prompt_template=[{"role": "user", "text": "hello"}],
        )
        assert nd.model.provider == "openai"
        assert nd.prompt_template[0].text == "hello"

    def test_extra_fields_allowed(self):
        nd = NodeData(type=NodeType.CODE, title="Code", custom_field="value")
        assert nd.__pydantic_extra__["custom_field"] == "value"


class TestNode:
    def test_basic(self):
        n = Node(id="n1", data=NodeData(type=NodeType.START, title="Start"))
        assert n.id == "n1"
        assert n.type == "custom"
        assert n.width == 244

    def test_default_id(self):
        n = Node(data=NodeData(type=NodeType.END, title="End"))
        assert n.id  # auto-generated


class TestEdge:
    def test_basic(self):
        e = Edge(source="n1", target="n2")
        assert e.source == "n1"
        assert e.target == "n2"
        assert e.type == "custom"

    def test_auto_id(self):
        e = Edge(source="a", target="b")
        assert e.id == "a-source-b-target"

    def test_custom_handles(self):
        e = Edge(source="a", target="b", sourceHandle="true", targetHandle="target")
        assert e.id == "a-true-b-target"


class TestGraph:
    def test_empty(self):
        g = Graph()
        assert g.nodes == []
        assert g.edges == []

    def test_with_nodes(self):
        g = Graph(nodes=[
            Node(id="n1", data=NodeData(type=NodeType.START, title="Start")),
            Node(id="n2", data=NodeData(type=NodeType.END, title="End")),
        ])
        assert len(g.nodes) == 2


class TestDifyWorkflowDSL:
    def test_default(self):
        dsl = DifyWorkflowDSL()
        assert dsl.version == "0.6.0"
        assert dsl.kind == "app"
        assert dsl.app.mode == "workflow"

    def test_serialization_roundtrip(self):
        dsl = DifyWorkflowDSL(app=AppInfo(name="Test", description="A test"))
        data = dsl.model_dump(mode="json", exclude_none=True)
        dsl2 = DifyWorkflowDSL.model_validate(data)
        assert dsl2.app.name == "Test"
        assert dsl2.version == "0.6.0"


class TestModelConfigContent:
    def test_prompt_config_defaults_are_frontend_safe(self):
        config = ModelConfigContent()
        assert config.chat_prompt_config == {"prompt": []}
        assert config.completion_prompt_config == {
            "prompt": {"text": ""},
            "conversation_histories_role": {
                "user_prefix": "",
                "assistant_prefix": "",
            },
        }
