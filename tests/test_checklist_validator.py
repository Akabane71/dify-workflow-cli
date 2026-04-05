"""Unit tests for checklist_validator — pre-publish checklist validation."""

import pytest
from dify_workflow.checklist_validator import (
    ChecklistError,
    validate_checklist,
    _extract_template_vars,
    _extract_used_vars,
    _build_node_outputs,
)
from dify_workflow.editor import (
    add_edge,
    add_node,
    create_minimal_workflow,
)
from dify_workflow.models import (
    DifyWorkflowDSL,
    IfElseCase,
    IfElseCondition,
    NodeType,
)


# ── Helpers ─────────────────────────────────────────────────────────────

def _make_workflow(*node_specs):
    """Create workflow from (type, node_id, extras_dict) tuples."""
    dsl = DifyWorkflowDSL()
    for spec in node_specs:
        node_type, nid = spec[0], spec[1]
        extras = spec[2] if len(spec) > 2 else {}
        add_node(dsl, node_type, node_id=nid, data_overrides=extras)
    return dsl


def _find_errors(errors, *, node_id=None, message_contains=None):
    result = errors
    if node_id:
        result = [e for e in result if e.node_id == node_id]
    if message_contains:
        result = [e for e in result if message_contains.lower() in e.message.lower()]
    return result


# ── Template variable extraction ────────────────────────────────────────

class TestExtractTemplateVars:
    def test_basic(self):
        refs = _extract_template_vars("Hello {{#node1.text#}}")
        assert refs == [["node1", "text"]]

    def test_multiple(self):
        refs = _extract_template_vars("{{#n1.a#}} and {{#n2.b#}}")
        assert len(refs) == 2
        assert ["n1", "a"] in refs
        assert ["n2", "b"] in refs

    def test_empty(self):
        assert _extract_template_vars("") == []
        assert _extract_template_vars("no vars here") == []

    def test_special_prefix_skipped(self):
        refs = _extract_template_vars("{{#sys.query#}} and {{#env.key#}}")
        assert refs == []

    def test_conversation_skipped(self):
        refs = _extract_template_vars("{{#conversation.user_id#}}")
        assert refs == []


# ── Node config checks ─────────────────────────────────────────────────

class TestCheckEnd:
    def test_end_no_outputs(self):
        dsl = _make_workflow(
            (NodeType.START, "s1"),
            (NodeType.END, "end1", {"outputs": []}),
        )
        errors = validate_checklist(dsl)
        assert _find_errors(errors, node_id="end1", message_contains="output")

    def test_end_missing_value_selector(self):
        dsl = _make_workflow(
            (NodeType.START, "s1"),
            (NodeType.END, "end1", {"outputs": [{"variable": "result", "value_selector": []}]}),
        )
        errors = validate_checklist(dsl)
        assert _find_errors(errors, node_id="end1", message_contains="value_selector")

    def test_end_valid(self):
        dsl = _make_workflow(
            (NodeType.START, "s1", {"variables": [{"variable": "query", "label": "Query", "type": "text-input"}]}),
            (NodeType.END, "end1", {"outputs": [{"variable": "result", "value_selector": ["s1", "query"]}]}),
        )
        add_edge(dsl, "s1", "end1")
        errors = validate_checklist(dsl)
        end_errors = _find_errors(errors, node_id="end1")
        assert not end_errors


class TestCheckAnswer:
    def test_empty_answer(self):
        dsl = _make_workflow(
            (NodeType.START, "s1"),
            (NodeType.ANSWER, "a1", {"answer": ""}),
        )
        errors = validate_checklist(dsl)
        assert _find_errors(errors, node_id="a1", message_contains="answer")

    def test_valid_answer(self):
        dsl = _make_workflow(
            (NodeType.START, "s1"),
            (NodeType.ANSWER, "a1", {"answer": "Hello {{#s1.text#}}"}),
        )
        errors = validate_checklist(dsl)
        assert not _find_errors(errors, node_id="a1", message_contains="answer text")


class TestCheckLLM:
    def test_no_model(self):
        dsl = _make_workflow(
            (NodeType.START, "s1"),
            (NodeType.LLM, "llm1"),
        )
        # Clear model to None
        for n in dsl.workflow.graph.nodes:
            if n.id == "llm1":
                n.data.model = None
        errors = validate_checklist(dsl)
        assert _find_errors(errors, node_id="llm1", message_contains="model")


class TestCheckCode:
    def test_empty_code(self):
        dsl = _make_workflow(
            (NodeType.START, "s1"),
            (NodeType.CODE, "c1"),
        )
        for n in dsl.workflow.graph.nodes:
            if n.id == "c1":
                n.data.code = ""
                n.data.variables = []
        errors = validate_checklist(dsl)
        assert _find_errors(errors, node_id="c1", message_contains="code required")

    def test_variable_missing_selector(self):
        dsl = _make_workflow(
            (NodeType.START, "s1"),
            (NodeType.CODE, "c1"),
        )
        from dify_workflow.models import StartVariable
        for n in dsl.workflow.graph.nodes:
            if n.id == "c1":
                n.data.variables = [StartVariable(variable="x", value_selector=[])]
        errors = validate_checklist(dsl)
        assert _find_errors(errors, node_id="c1", message_contains="value_selector")


class TestCheckIfElse:
    def test_empty_cases(self):
        dsl = _make_workflow(
            (NodeType.START, "s1"),
            (NodeType.IF_ELSE, "ie1"),
        )
        for n in dsl.workflow.graph.nodes:
            if n.id == "ie1":
                n.data.cases = []
        errors = validate_checklist(dsl)
        assert _find_errors(errors, node_id="ie1", message_contains="cases required")

    def test_condition_missing_variable(self):
        dsl = _make_workflow(
            (NodeType.START, "s1"),
            (NodeType.IF_ELSE, "ie1"),
        )
        for n in dsl.workflow.graph.nodes:
            if n.id == "ie1":
                n.data.cases = [
                    IfElseCase(
                        id="true", case_id="true",
                        conditions=[IfElseCondition(variable_selector=[], comparison_operator="contains", value="test")],
                    )
                ]
        errors = validate_checklist(dsl)
        assert _find_errors(errors, node_id="ie1", message_contains="condition variable")

    def test_condition_missing_value_not_empty_op(self):
        dsl = _make_workflow(
            (NodeType.START, "s1"),
            (NodeType.IF_ELSE, "ie1"),
        )
        for n in dsl.workflow.graph.nodes:
            if n.id == "ie1":
                n.data.cases = [
                    IfElseCase(
                        id="true", case_id="true",
                        conditions=[IfElseCondition(
                            variable_selector=["s1", "query"],
                            comparison_operator="contains",
                            value="",
                        )],
                    )
                ]
        errors = validate_checklist(dsl)
        assert _find_errors(errors, node_id="ie1", message_contains="condition value")

    def test_empty_op_no_value_needed(self):
        dsl = _make_workflow(
            (NodeType.START, "s1", {"variables": [{"variable": "query", "label": "Query", "type": "text-input"}]}),
            (NodeType.IF_ELSE, "ie1"),
        )
        add_edge(dsl, "s1", "ie1")
        for n in dsl.workflow.graph.nodes:
            if n.id == "ie1":
                n.data.cases = [
                    IfElseCase(
                        id="true", case_id="true",
                        conditions=[IfElseCondition(
                            variable_selector=["s1", "query"],
                            comparison_operator="is empty",
                            value="",
                        )],
                    )
                ]
        errors = validate_checklist(dsl)
        ie_errors = _find_errors(errors, node_id="ie1")
        assert not ie_errors


class TestCheckQuestionClassifier:
    def test_no_model(self):
        dsl = _make_workflow(
            (NodeType.START, "s1"),
            (NodeType.QUESTION_CLASSIFIER, "qc1"),
        )
        for n in dsl.workflow.graph.nodes:
            if n.id == "qc1":
                n.data.model = None
        errors = validate_checklist(dsl)
        assert _find_errors(errors, node_id="qc1", message_contains="model required")


class TestCheckKnowledgeRetrieval:
    def test_no_datasets(self):
        dsl = _make_workflow(
            (NodeType.START, "s1"),
            (NodeType.KNOWLEDGE_RETRIEVAL, "kr1"),
        )
        for n in dsl.workflow.graph.nodes:
            if n.id == "kr1":
                n.data.dataset_ids = []
        errors = validate_checklist(dsl)
        assert _find_errors(errors, node_id="kr1", message_contains="knowledge base")


class TestCheckHTTP:
    def test_no_url(self):
        dsl = _make_workflow(
            (NodeType.START, "s1"),
            (NodeType.HTTP_REQUEST, "h1"),
        )
        for n in dsl.workflow.graph.nodes:
            if n.id == "h1":
                n.data.url = ""
        errors = validate_checklist(dsl)
        assert _find_errors(errors, node_id="h1", message_contains="URL required")


class TestCheckTemplateTransform:
    def test_no_template(self):
        dsl = _make_workflow(
            (NodeType.START, "s1"),
            (NodeType.TEMPLATE_TRANSFORM, "tt1"),
        )
        for n in dsl.workflow.graph.nodes:
            if n.id == "tt1":
                n.data.template = ""
        errors = validate_checklist(dsl)
        assert _find_errors(errors, node_id="tt1", message_contains="template required")


class TestCheckIteration:
    def test_no_iterator(self):
        dsl = _make_workflow(
            (NodeType.START, "s1"),
            (NodeType.ITERATION, "it1"),
        )
        for n in dsl.workflow.graph.nodes:
            if n.id == "it1":
                n.data.iterator_selector = []
        errors = validate_checklist(dsl)
        assert _find_errors(errors, node_id="it1", message_contains="iterator_selector")


# ── Variable reference validation ────────────────────────────────────────

class TestVariableReferenceValidation:
    def test_valid_reference(self):
        """End node referencing Start node's variable — no error."""
        dsl = DifyWorkflowDSL()
        add_node(dsl, NodeType.START, node_id="s1", data_overrides={
            "variables": [{"variable": "query", "label": "Query", "type": "text-input"}]
        })
        add_node(dsl, NodeType.END, node_id="end1", data_overrides={
            "outputs": [{"variable": "result", "value_selector": ["s1", "query"]}]
        })
        add_edge(dsl, "s1", "end1")
        errors = validate_checklist(dsl)
        var_errors = _find_errors(errors, message_contains="invalid variable")
        assert not var_errors

    def test_reference_nonexistent_node(self):
        """End node referencing a node that doesn't exist."""
        dsl = DifyWorkflowDSL()
        add_node(dsl, NodeType.START, node_id="s1")
        add_node(dsl, NodeType.END, node_id="end1", data_overrides={
            "outputs": [{"variable": "result", "value_selector": ["ghost_node", "output"]}]
        })
        errors = validate_checklist(dsl)
        assert _find_errors(errors, message_contains="non-existent node")

    def test_reference_nonexistent_output(self):
        """End node referencing an output that the source node doesn't have."""
        dsl = DifyWorkflowDSL()
        add_node(dsl, NodeType.START, node_id="s1", data_overrides={
            "variables": [{"variable": "query", "label": "Query", "type": "text-input"}]
        })
        add_node(dsl, NodeType.END, node_id="end1", data_overrides={
            "outputs": [{"variable": "result", "value_selector": ["s1", "nonexistent"]}]
        })
        add_edge(dsl, "s1", "end1")
        errors = validate_checklist(dsl)
        assert _find_errors(errors, message_contains="no output")

    def test_special_vars_skipped(self):
        """References to sys/env/conversation/rag should not error."""
        dsl = DifyWorkflowDSL()
        add_node(dsl, NodeType.START, node_id="s1")
        add_node(dsl, NodeType.ANSWER, node_id="a1", data_overrides={
            "answer": "{{#sys.query#}} {{#env.API_KEY#}} {{#conversation.user_id#}}"
        })
        errors = validate_checklist(dsl)
        var_errors = _find_errors(errors, message_contains="invalid variable")
        assert not var_errors

    def test_llm_text_output(self):
        """LLM node produces 'text' output — End can reference it."""
        dsl = DifyWorkflowDSL()
        add_node(dsl, NodeType.START, node_id="s1")
        add_node(dsl, NodeType.LLM, node_id="llm1")
        add_node(dsl, NodeType.END, node_id="end1", data_overrides={
            "outputs": [{"variable": "result", "value_selector": ["llm1", "text"]}]
        })
        add_edge(dsl, "s1", "llm1")
        add_edge(dsl, "llm1", "end1")
        errors = validate_checklist(dsl)
        var_errors = _find_errors(errors, node_id="end1", message_contains="invalid variable")
        assert not var_errors

    def test_code_outputs(self):
        """Code node with custom outputs — End can reference them."""
        dsl = DifyWorkflowDSL()
        add_node(dsl, NodeType.START, node_id="s1")
        add_node(dsl, NodeType.CODE, node_id="c1")
        # Set code output keys
        for n in dsl.workflow.graph.nodes:
            if n.id == "c1":
                n.data.__pydantic_extra__ = n.data.__pydantic_extra__ or {}
                n.data.__pydantic_extra__["outputs"] = {
                    "result": {"type": "string", "children": None},
                    "count": {"type": "number", "children": None},
                }
        add_node(dsl, NodeType.END, node_id="end1", data_overrides={
            "outputs": [
                {"variable": "r", "value_selector": ["c1", "result"]},
                {"variable": "c", "value_selector": ["c1", "count"]},
            ]
        })
        add_edge(dsl, "s1", "c1")
        add_edge(dsl, "c1", "end1")
        errors = validate_checklist(dsl)
        var_errors = _find_errors(errors, node_id="end1", message_contains="invalid variable")
        assert not var_errors

    def test_code_outputs_wrong_key(self):
        """Code node reference to non-existent output key."""
        dsl = DifyWorkflowDSL()
        add_node(dsl, NodeType.START, node_id="s1")
        add_node(dsl, NodeType.CODE, node_id="c1")
        for n in dsl.workflow.graph.nodes:
            if n.id == "c1":
                n.data.__pydantic_extra__ = n.data.__pydantic_extra__ or {}
                n.data.__pydantic_extra__["outputs"] = {
                    "result": {"type": "string", "children": None},
                }
        add_node(dsl, NodeType.END, node_id="end1", data_overrides={
            "outputs": [{"variable": "x", "value_selector": ["c1", "wrong_key"]}]
        })
        add_edge(dsl, "s1", "c1")
        add_edge(dsl, "c1", "end1")
        errors = validate_checklist(dsl)
        assert _find_errors(errors, message_contains="no output 'wrong_key'")

    def test_http_outputs(self):
        """HTTP node has body, status_code, headers outputs."""
        dsl = DifyWorkflowDSL()
        add_node(dsl, NodeType.START, node_id="s1")
        add_node(dsl, NodeType.HTTP_REQUEST, node_id="h1", data_overrides={"url": "https://example.com"})
        add_node(dsl, NodeType.END, node_id="end1", data_overrides={
            "outputs": [
                {"variable": "body", "value_selector": ["h1", "body"]},
                {"variable": "status", "value_selector": ["h1", "status_code"]},
            ]
        })
        add_edge(dsl, "s1", "h1")
        add_edge(dsl, "h1", "end1")
        errors = validate_checklist(dsl)
        var_errors = _find_errors(errors, node_id="end1", message_contains="invalid variable")
        assert not var_errors


# ── Build node outputs ──────────────────────────────────────────────────

class TestBuildNodeOutputs:
    def test_start_outputs(self):
        dsl = DifyWorkflowDSL()
        add_node(dsl, NodeType.START, node_id="s1", data_overrides={
            "variables": [{"variable": "q", "type": "text-input"}]
        })
        outputs = _build_node_outputs(dsl.workflow.graph.nodes)
        assert "q" in outputs["s1"]

    def test_llm_outputs(self):
        dsl = DifyWorkflowDSL()
        add_node(dsl, NodeType.LLM, node_id="llm1")
        outputs = _build_node_outputs(dsl.workflow.graph.nodes)
        assert outputs["llm1"] == {"text", "reasoning_content", "usage"}

    def test_tool_outputs(self):
        dsl = DifyWorkflowDSL()
        add_node(dsl, NodeType.TOOL, node_id="t1")
        outputs = _build_node_outputs(dsl.workflow.graph.nodes)
        assert outputs["t1"] == {"text", "files", "json"}

    def test_template_transform_output(self):
        dsl = DifyWorkflowDSL()
        add_node(dsl, NodeType.TEMPLATE_TRANSFORM, node_id="tt1")
        outputs = _build_node_outputs(dsl.workflow.graph.nodes)
        assert "output" in outputs["tt1"]

    def test_http_request_outputs(self):
        dsl = DifyWorkflowDSL()
        add_node(dsl, NodeType.HTTP_REQUEST, node_id="http1")
        outputs = _build_node_outputs(dsl.workflow.graph.nodes)
        assert outputs["http1"] == {"body", "status_code", "headers", "files"}

    def test_question_classifier_outputs(self):
        dsl = DifyWorkflowDSL()
        add_node(dsl, NodeType.QUESTION_CLASSIFIER, node_id="qc1")
        outputs = _build_node_outputs(dsl.workflow.graph.nodes)
        assert outputs["qc1"] == {"class_name", "usage"}

    def test_agent_outputs(self):
        dsl = DifyWorkflowDSL()
        add_node(dsl, NodeType.AGENT, node_id="ag1")
        outputs = _build_node_outputs(dsl.workflow.graph.nodes)
        assert outputs["ag1"] == {"text", "files", "json", "usage"}

    def test_parameter_extractor_outputs(self):
        dsl = DifyWorkflowDSL()
        add_node(dsl, NodeType.PARAMETER_EXTRACTOR, node_id="pe1", data_overrides={
            "parameters": [{"name": "city"}, {"name": "date"}]
        })
        outputs = _build_node_outputs(dsl.workflow.graph.nodes)
        assert outputs["pe1"] == {"city", "date", "__is_success", "__reason", "__usage"}

    def test_loop_outputs_use_label(self):
        dsl = DifyWorkflowDSL()
        add_node(dsl, NodeType.LOOP, node_id="lp1", data_overrides={
            "loop_variables": [{"label": "counter"}, {"label": "total"}]
        })
        outputs = _build_node_outputs(dsl.workflow.graph.nodes)
        assert outputs["lp1"] == {"counter", "total"}


class TestConnectivityRules:
    def test_iteration_child_node_is_considered_connected(self):
        """Mirror Dify: iteration container reachability includes its parentId children."""
        dsl = DifyWorkflowDSL()
        add_node(dsl, NodeType.START, node_id="s1", data_overrides={
            "variables": [{"variable": "items", "label": "Items", "type": "paragraph"}],
        })
        add_node(dsl, NodeType.ITERATION, node_id="it1", data_overrides={
            "iterator_selector": ["s1", "items"],
        })
        add_node(dsl, NodeType.ANSWER, node_id="child1", data_overrides={"answer": "ok"})
        add_edge(dsl, "s1", "it1")

        for n in dsl.workflow.graph.nodes:
            if n.id == "child1":
                n.__pydantic_extra__ = n.__pydantic_extra__ or {}
                n.__pydantic_extra__["parentId"] = "it1"
                break

        errors = validate_checklist(dsl)
        conn_errors = _find_errors(errors, node_id="child1", message_contains="Node not connected")
        assert not conn_errors

    def test_regular_isolated_node_still_errors(self):
        dsl = DifyWorkflowDSL()
        add_node(dsl, NodeType.START, node_id="s1")
        add_node(dsl, NodeType.ANSWER, node_id="a1", data_overrides={"answer": "ok"})
        errors = validate_checklist(dsl)
        conn_errors = _find_errors(errors, node_id="a1", message_contains="Node not connected")
        assert conn_errors


# ── Extract used vars ───────────────────────────────────────────────────

class TestExtractUsedVars:
    def test_end_node(self):
        dsl = DifyWorkflowDSL()
        add_node(dsl, NodeType.END, node_id="end1", data_overrides={
            "outputs": [{"variable": "r", "value_selector": ["llm1", "text"]}]
        })
        node = dsl.workflow.graph.nodes[0]
        refs = _extract_used_vars(node)
        assert ["llm1", "text"] in refs

    def test_answer_node(self):
        dsl = DifyWorkflowDSL()
        add_node(dsl, NodeType.ANSWER, node_id="a1", data_overrides={
            "answer": "Result: {{#llm1.text#}}"
        })
        node = dsl.workflow.graph.nodes[0]
        refs = _extract_used_vars(node)
        assert ["llm1", "text"] in refs

    def test_code_node(self):
        dsl = DifyWorkflowDSL()
        add_node(dsl, NodeType.CODE, node_id="c1")
        node = dsl.workflow.graph.nodes[0]
        # Code node variables are in typed field (StartVariable with value_selector)
        from dify_workflow.models import StartVariable
        node.data.variables = [
            StartVariable(variable="x", value_selector=["s1", "query"])
        ]
        refs = _extract_used_vars(node)
        assert ["s1", "query"] in refs

    def test_if_else_node(self):
        dsl = DifyWorkflowDSL()
        add_node(dsl, NodeType.IF_ELSE, node_id="ie1")
        node = dsl.workflow.graph.nodes[0]
        node.data.cases = [
            IfElseCase(
                conditions=[IfElseCondition(
                    variable_selector=["s1", "query"],
                    comparison_operator="contains",
                    value="test",
                )]
            )
        ]
        refs = _extract_used_vars(node)
        assert ["s1", "query"] in refs


# ── Integration with validate_workflow ──────────────────────────────────

class TestChecklistIntegration:
    def test_checklist_runs_in_validate(self):
        """validate_workflow should now include checklist errors."""
        from dify_workflow.validator import validate_workflow

        dsl = DifyWorkflowDSL()
        add_node(dsl, NodeType.START, node_id="s1")
        add_node(dsl, NodeType.END, node_id="end1", data_overrides={
            "outputs": [{"variable": "r", "value_selector": ["ghost", "output"]}]
        })
        add_edge(dsl, "s1", "end1")
        result = validate_workflow(dsl)
        messages = [e.message for e in result.errors]
        assert any("non-existent node" in m for m in messages)

    def test_clean_workflow_passes(self):
        """A properly wired workflow should pass checklist."""
        from dify_workflow.validator import validate_workflow

        dsl = create_minimal_workflow()
        result = validate_workflow(dsl)
        checklist_errors = [e for e in result.errors if "Invalid variable" in e.message]
        assert not checklist_errors
