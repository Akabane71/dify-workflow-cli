"""Unit tests for node-level data validation (node_data_validator).

Tests follow Dify's official node data schemas from graphon entities
and Dify's workflow_service._validate_human_input_node_data().
"""

import uuid

import pytest
from dify_workflow.editor import add_node
from dify_workflow.models import DifyDSL, NodeType
from dify_workflow.node_data_validator import validate_node_data


def _make_node(node_type: NodeType, **overrides):
    """Create a node and return it for validation."""
    dsl = DifyDSL()
    add_node(dsl, NodeType.START, node_id="start_node")
    return add_node(dsl, node_type, node_id="test_node", data_overrides=overrides or None)


class TestHumanInputValidation:
    """HumanInput is the ONLY node Dify validates at import time."""

    def test_default_node_is_valid(self):
        node = _make_node(NodeType.HUMAN_INPUT)
        errors = validate_node_data(node)
        assert len(errors) == 0

    def test_missing_output_variable_name(self):
        node = _make_node(NodeType.HUMAN_INPUT, inputs=[
            {"type": "paragraph", "label": "info"},
        ])
        errors = validate_node_data(node)
        assert any("output_variable_name" in e.message for e in errors)
        assert any(e.level == "error" for e in errors)

    def test_valid_inputs(self):
        node = _make_node(NodeType.HUMAN_INPUT, inputs=[
            {"type": "paragraph", "label": "info", "output_variable_name": "user_info"},
        ])
        errors = validate_node_data(node)
        assert len(errors) == 0

    def test_duplicate_output_variable_name(self):
        node = _make_node(NodeType.HUMAN_INPUT, inputs=[
            {"type": "text_input", "output_variable_name": "dup"},
            {"type": "paragraph", "output_variable_name": "dup"},
        ])
        errors = validate_node_data(node)
        assert any("duplicate" in e.message.lower() for e in errors)

    def test_invalid_input_type(self):
        node = _make_node(NodeType.HUMAN_INPUT, inputs=[
            {"type": "invalid_type", "output_variable_name": "x"},
        ])
        errors = validate_node_data(node)
        assert any("invalid type" in e.message.lower() for e in errors)

    def test_delivery_method_id_must_be_uuid(self):
        node = _make_node(NodeType.HUMAN_INPUT, delivery_methods=[
            {"id": "webapp", "type": "webapp", "enabled": True},
        ])
        errors = validate_node_data(node)
        assert any("UUID" in e.message for e in errors)
        assert any(e.level == "error" for e in errors)

    def test_delivery_method_valid_uuid(self):
        node = _make_node(NodeType.HUMAN_INPUT, delivery_methods=[
            {"id": str(uuid.uuid4()), "type": "webapp", "enabled": True, "config": {}},
        ])
        errors = validate_node_data(node)
        assert len(errors) == 0

    def test_delivery_method_invalid_type(self):
        node = _make_node(NodeType.HUMAN_INPUT, delivery_methods=[
            {"id": str(uuid.uuid4()), "type": "sms", "enabled": True},
        ])
        errors = validate_node_data(node)
        assert any("invalid type" in e.message.lower() for e in errors)

    def test_email_delivery_missing_config(self):
        node = _make_node(NodeType.HUMAN_INPUT, delivery_methods=[
            {"id": str(uuid.uuid4()), "type": "email", "enabled": True, "config": {}},
        ])
        errors = validate_node_data(node)
        assert any("recipients" in e.message for e in errors)
        assert any("subject" in e.message for e in errors)
        assert any("body" in e.message for e in errors)

    def test_email_delivery_valid_config(self):
        node = _make_node(NodeType.HUMAN_INPUT, delivery_methods=[
            {
                "id": str(uuid.uuid4()),
                "type": "email",
                "enabled": True,
                "config": {
                    "recipients": {"include_bound_group": False, "items": []},
                    "subject": "Action required",
                    "body": "Please fill the form",
                },
            },
        ])
        errors = validate_node_data(node)
        assert len(errors) == 0

    def test_user_action_id_pattern(self):
        node = _make_node(NodeType.HUMAN_INPUT, user_actions=[
            {"id": "123invalid", "title": "Bad"},
        ])
        errors = validate_node_data(node)
        assert any("identifier" in e.message.lower() for e in errors)

    def test_user_action_id_too_long(self):
        node = _make_node(NodeType.HUMAN_INPUT, user_actions=[
            {"id": "a" * 21, "title": "Long ID"},
        ])
        errors = validate_node_data(node)
        assert any("too long" in e.message.lower() for e in errors)

    def test_user_action_duplicate_id(self):
        node = _make_node(NodeType.HUMAN_INPUT, user_actions=[
            {"id": "submit", "title": "Submit"},
            {"id": "submit", "title": "Submit Again"},
        ])
        errors = validate_node_data(node)
        assert any("duplicate" in e.message.lower() for e in errors)

    def test_valid_user_actions(self):
        node = _make_node(NodeType.HUMAN_INPUT, user_actions=[
            {"id": "submit", "title": "Submit", "button_style": "primary"},
            {"id": "cancel", "title": "Cancel", "button_style": "default"},
        ])
        errors = validate_node_data(node)
        assert len(errors) == 0

    def test_invalid_button_style(self):
        node = _make_node(NodeType.HUMAN_INPUT, user_actions=[
            {"id": "action", "title": "Act", "button_style": "neon"},
        ])
        errors = validate_node_data(node)
        assert any("button_style" in e.message for e in errors)

    def test_invalid_timeout_unit(self):
        node = _make_node(NodeType.HUMAN_INPUT, timeout_unit="minute")
        errors = validate_node_data(node)
        assert any("timeout_unit" in e.message for e in errors)

    def test_combined_errors(self):
        """Reproduces the exact Dify import error from the user's report."""
        node = _make_node(NodeType.HUMAN_INPUT,
            inputs=[{"type": "paragraph", "label": "info", "variable": "supplemental_info"}],
            delivery_methods=[{"id": "webapp", "type": "webapp", "enabled": True}],
        )
        errors = validate_node_data(node)
        error_messages = [e.message for e in errors]
        assert any("output_variable_name" in m for m in error_messages)
        assert any("UUID" in m for m in error_messages)
        assert len([e for e in errors if e.level == "error"]) >= 2


class TestLLMValidation:
    def test_default_is_valid(self):
        node = _make_node(NodeType.LLM)
        errors = validate_node_data(node)
        error_level = [e for e in errors if e.level == "error"]
        assert len(error_level) == 0

    def test_missing_model(self):
        node = _make_node(NodeType.LLM, model=None)
        errors = validate_node_data(node)
        assert any("model" in e.message.lower() and e.level == "error" for e in errors)


class TestCodeValidation:
    def test_invalid_code_language(self):
        node = _make_node(NodeType.CODE, code_language="ruby")
        errors = validate_node_data(node)
        assert any("code_language" in e.message and e.level == "error" for e in errors)

    def test_valid_python3(self):
        node = _make_node(NodeType.CODE, code="def main(arg1: str):\n    return {'result': arg1}", code_language="python3")
        errors = validate_node_data(node)
        error_level = [e for e in errors if e.level == "error"]
        assert len(error_level) == 0

    def test_missing_main_python3(self):
        node = _make_node(NodeType.CODE, code="print('hello')", code_language="python3")
        errors = validate_node_data(node)
        assert any("def main" in e.message and e.level == "error" for e in errors)

    def test_missing_main_javascript(self):
        node = _make_node(NodeType.CODE, code="console.log('hi')", code_language="javascript")
        errors = validate_node_data(node)
        assert any("function main" in e.message and e.level == "error" for e in errors)

    def test_valid_javascript(self):
        node = _make_node(NodeType.CODE, code="function main(arg1) { return {result: arg1} }", code_language="javascript")
        errors = validate_node_data(node)
        error_level = [e for e in errors if e.level == "error"]
        assert len(error_level) == 0

    def test_param_variable_mismatch_warning(self):
        """Function params don't match declared variables."""
        node = _make_node(NodeType.CODE, code="def main(x: str):\n    return {'r': x}", code_language="python3")
        from dify_workflow.models import StartVariable
        node.data.variables = [StartVariable(variable="y", value_selector=[])]
        errors = validate_node_data(node)
        assert any("don't match" in e.message and e.level == "warning" for e in errors)

    def test_param_variable_match_no_warning(self):
        """Function params match declared variables — no warning."""
        node = _make_node(NodeType.CODE, code="def main(x: str):\n    return {'r': x}", code_language="python3")
        from dify_workflow.models import StartVariable
        node.data.variables = [StartVariable(variable="x", value_selector=[])]
        errors = validate_node_data(node)
        assert not any("don't match" in e.message for e in errors)

    def test_invalid_output_type(self):
        node = _make_node(NodeType.CODE, code="def main():\n    pass", code_language="python3")
        node.data.__pydantic_extra__["outputs"] = {"r": {"type": "invalid_type", "children": None}}
        errors = validate_node_data(node)
        assert any("invalid type" in e.message and e.level == "error" for e in errors)

    def test_valid_output_types(self):
        """All allowed output types should pass."""
        for t in ["string", "number", "object", "boolean", "array[string]", "array[number]", "array[object]"]:
            node = _make_node(NodeType.CODE, code="def main():\n    pass", code_language="python3")
            node.data.__pydantic_extra__["outputs"] = {"r": {"type": t, "children": None}}
            errors = validate_node_data(node)
            type_errors = [e for e in errors if "invalid type" in e.message]
            assert len(type_errors) == 0, f"Type {t} should be valid"


class TestHTTPRequestValidation:
    def test_invalid_method(self):
        node = _make_node(NodeType.HTTP_REQUEST, method="BREW")
        errors = validate_node_data(node)
        assert any("method" in e.message and e.level == "error" for e in errors)

    def test_missing_url_warning(self):
        node = _make_node(NodeType.HTTP_REQUEST)
        errors = validate_node_data(node)
        assert any("URL" in e.message and e.level == "warning" for e in errors)


class TestEndNodeValidation:
    def test_end_default_valid(self):
        node = _make_node(NodeType.END)
        errors = validate_node_data(node)
        error_level = [e for e in errors if e.level == "error"]
        assert len(error_level) == 0

    def test_end_missing_outputs(self):
        node = _make_node(NodeType.END, outputs=None)
        errors = validate_node_data(node)
        assert any("outputs" in e.message for e in errors)


class TestAnswerNodeValidation:
    def test_answer_default_valid(self):
        node = _make_node(NodeType.ANSWER)
        errors = validate_node_data(node)
        error_level = [e for e in errors if e.level == "error"]
        assert len(error_level) == 0


class TestQuestionClassifierValidation:
    def test_missing_model(self):
        node = _make_node(NodeType.QUESTION_CLASSIFIER, model=None)
        errors = validate_node_data(node)
        assert any("model" in e.message and e.level == "error" for e in errors)

    def test_missing_classes(self):
        node = _make_node(NodeType.QUESTION_CLASSIFIER, classes=None)
        errors = validate_node_data(node)
        assert any("classes" in e.message and e.level == "error" for e in errors)


class TestParameterExtractorValidation:
    def test_invalid_reasoning_mode(self):
        node = _make_node(NodeType.PARAMETER_EXTRACTOR, reasoning_mode="magic")
        errors = validate_node_data(node)
        assert any("reasoning_mode" in e.message and e.level == "error" for e in errors)

    def test_reserved_parameter_name(self):
        node = _make_node(NodeType.PARAMETER_EXTRACTOR, parameters=[
            {"name": "__reason", "type": "string", "description": "test", "required": True},
        ])
        errors = validate_node_data(node)
        assert any("reserved" in e.message for e in errors)

    def test_empty_parameter_name(self):
        node = _make_node(NodeType.PARAMETER_EXTRACTOR, parameters=[
            {"name": "", "type": "string", "description": "test", "required": True},
        ])
        errors = validate_node_data(node)
        assert any("name is required" in e.message for e in errors)

    def test_invalid_parameter_type(self):
        node = _make_node(NodeType.PARAMETER_EXTRACTOR, parameters=[
            {"name": "color", "type": "color", "description": "test", "required": True},
        ])
        errors = validate_node_data(node)
        assert any("invalid type" in e.message.lower() for e in errors)

    def test_valid_parameter_types(self):
        """All valid parameter types should pass."""
        for ptype in ("string", "number", "boolean", "bool", "select",
                       "array[string]", "array[number]", "array[object]"):
            node = _make_node(NodeType.PARAMETER_EXTRACTOR, parameters=[
                {"name": "p", "type": ptype, "description": "test", "required": True},
            ])
            errors = validate_node_data(node)
            type_errors = [e for e in errors if "invalid type" in e.message.lower()]
            assert len(type_errors) == 0, f"Type {ptype!r} should be valid"


class TestVariableAssignerValidation:
    def test_invalid_write_mode_v1(self):
        node = _make_node(NodeType.VARIABLE_ASSIGNER, version="1", write_mode="replace")
        errors = validate_node_data(node)
        assert any("write_mode" in e.message and e.level == "error" for e in errors)


class TestLoopValidation:
    def test_invalid_logical_operator(self):
        node = _make_node(NodeType.LOOP, logical_operator="xor")
        errors = validate_node_data(node)
        assert any("logical_operator" in e.message and e.level == "error" for e in errors)

    def test_invalid_loop_variable_type(self):
        node = _make_node(NodeType.LOOP, loop_variables=[
            {"label": "x", "var_type": "color", "value_type": "constant", "value": "red"},
        ])
        errors = validate_node_data(node)
        assert any("var_type" in e.message for e in errors)


class TestStartNodeValidation:
    def test_duplicate_variable(self):
        dsl = DifyDSL()
        from dify_workflow.models import StartVariable
        node = add_node(dsl, NodeType.START, node_id="s1", data_overrides={
            "variables": [
                StartVariable(variable="q", label="q"),
                StartVariable(variable="q", label="q2"),
            ]
        })
        errors = validate_node_data(node)
        assert any("Duplicate start variable" in e.message for e in errors)


class TestNoValidationNodes:
    """Nodes with no specific validation rules should return no errors."""

    @pytest.mark.parametrize("node_type", [
        NodeType.TRIGGER_WEBHOOK,
        NodeType.TRIGGER_SCHEDULE,
        NodeType.KNOWLEDGE_INDEX,
    ])
    def test_no_errors_for_default(self, node_type):
        node = _make_node(node_type)
        errors = validate_node_data(node)
        assert len(errors) == 0


class TestCodeOutputTypeValidation:
    """Code node output type validation (graphon _ALLOWED_OUTPUT_FROM_CODE)."""

    def test_valid_output_types(self):
        for out_type in ("string", "number", "object", "boolean",
                         "array[string]", "array[number]", "array[object]"):
            node = _make_node(NodeType.CODE)
            # Set code outputs via extra fields (avoid conflict with NodeData.outputs)
            node.data.__pydantic_extra__["code_outputs"] = {"result": {"type": out_type}}
            # Manually rename for validator — the validator checks "outputs" extra key
            node.data.__pydantic_extra__["outputs"] = {"result": {"type": out_type}}
            errors = validate_node_data(node)
            type_errors = [e for e in errors if "invalid type" in e.message.lower() and "output" in e.message.lower()]
            assert len(type_errors) == 0, f"Output type {out_type!r} should be valid"

    def test_invalid_output_type(self):
        node = _make_node(NodeType.CODE)
        node.data.__pydantic_extra__["outputs"] = {"result": {"type": "file"}}
        errors = validate_node_data(node)
        assert any("invalid type" in e.message.lower() for e in errors)


class TestHTTPRequestAuthValidation:
    """HTTP Request authorization and body validation."""

    def test_invalid_auth_type(self):
        node = _make_node(NodeType.HTTP_REQUEST, authorization={"type": "oauth2"})
        errors = validate_node_data(node)
        assert any("authorization type" in e.message for e in errors)

    def test_api_key_missing_config(self):
        node = _make_node(NodeType.HTTP_REQUEST, authorization={"type": "api-key"})
        errors = validate_node_data(node)
        assert any("config must be a dict" in e.message for e in errors)

    def test_api_key_valid_config(self):
        node = _make_node(NodeType.HTTP_REQUEST, authorization={
            "type": "api-key",
            "config": {"type": "bearer", "api_key": "test"},
        })
        errors = validate_node_data(node)
        auth_errors = [e for e in errors if "authorization" in e.message.lower() or "auth" in e.message.lower()]
        assert len(auth_errors) == 0

    def test_invalid_auth_config_type(self):
        node = _make_node(NodeType.HTTP_REQUEST, authorization={
            "type": "api-key",
            "config": {"type": "digest"},
        })
        errors = validate_node_data(node)
        assert any("auth config invalid type" in e.message.lower() for e in errors)

    def test_no_auth_is_valid(self):
        node = _make_node(NodeType.HTTP_REQUEST, authorization={"type": "no-auth"})
        errors = validate_node_data(node)
        auth_errors = [e for e in errors if "authorization" in e.message.lower()]
        assert len(auth_errors) == 0

    def test_invalid_body_type(self):
        node = _make_node(NodeType.HTTP_REQUEST, body={"type": "xml"})
        errors = validate_node_data(node)
        assert any("body type" in e.message.lower() for e in errors)

    def test_valid_body_types(self):
        for btype in ("none", "form-data", "x-www-form-urlencoded", "raw-text", "json", "binary"):
            node = _make_node(NodeType.HTTP_REQUEST, body={"type": btype})
            errors = validate_node_data(node)
            body_errors = [e for e in errors if "body type" in e.message.lower()]
            assert len(body_errors) == 0, f"Body type {btype!r} should be valid"


class TestToolValidation:
    """Tool node deep validation (provider_type, tool_configurations, tool_parameters)."""

    def test_invalid_provider_type(self):
        node = _make_node(NodeType.TOOL, provider_type="unknown_provider")
        errors = validate_node_data(node)
        assert any("provider_type" in e.message for e in errors)

    def test_valid_provider_types(self):
        for pt in ("builtin", "plugin", "workflow", "api", "app", "dataset-retrieval", "mcp"):
            node = _make_node(NodeType.TOOL, provider_type=pt)
            errors = validate_node_data(node)
            pt_errors = [e for e in errors if "provider_type" in e.message]
            assert len(pt_errors) == 0, f"Provider type {pt!r} should be valid"

    def test_tool_param_mixed_must_be_string(self):
        node = _make_node(NodeType.TOOL, tool_parameters={
            "p1": {"type": "mixed", "value": 123},
        })
        errors = validate_node_data(node)
        assert any("must be string" in e.message and "mixed" in e.message for e in errors)

    def test_tool_param_variable_must_be_list(self):
        node = _make_node(NodeType.TOOL, tool_parameters={
            "p1": {"type": "variable", "value": "not_a_list"},
        })
        errors = validate_node_data(node)
        assert any("must be list" in e.message for e in errors)

    def test_tool_param_invalid_type(self):
        node = _make_node(NodeType.TOOL, tool_parameters={
            "p1": {"type": "dynamic", "value": "x"},
        })
        errors = validate_node_data(node)
        assert any("invalid type" in e.message.lower() for e in errors)


class TestBaseNodeDataValidation:
    """Base node data validation (error_strategy, default_value)."""

    def test_invalid_error_strategy(self):
        node = _make_node(NodeType.LLM, error_strategy="retry")
        errors = validate_node_data(node)
        assert any("error_strategy" in e.message for e in errors)

    def test_valid_error_strategy(self):
        node = _make_node(NodeType.LLM, error_strategy="fail-branch")
        errors = validate_node_data(node)
        es_errors = [e for e in errors if "error_strategy" in (e.field or "")]
        assert len(es_errors) == 0

    def test_default_value_type_mismatch(self):
        node = _make_node(NodeType.LLM, default_value=[
            {"key": "output", "type": "number", "value": "not_a_number"},
        ])
        errors = validate_node_data(node)
        assert any("must be number" in e.message for e in errors)

    def test_default_value_missing_key(self):
        node = _make_node(NodeType.LLM, default_value=[
            {"type": "string", "value": "hello"},
        ])
        errors = validate_node_data(node)
        assert any("missing 'key'" in e.message for e in errors)

    def test_default_value_invalid_type(self):
        node = _make_node(NodeType.LLM, default_value=[
            {"key": "x", "type": "binary", "value": "data"},
        ])
        errors = validate_node_data(node)
        assert any("invalid type" in e.message.lower() for e in errors)

    def test_default_value_string_valid(self):
        node = _make_node(NodeType.LLM, default_value=[
            {"key": "x", "type": "string", "value": "hello"},
        ])
        errors = validate_node_data(node)
        dv_errors = [e for e in errors if "default_value" in (e.field or "")]
        assert len(dv_errors) == 0

    def test_default_value_number_from_string(self):
        """Number string like '42' should be accepted."""
        node = _make_node(NodeType.LLM, default_value=[
            {"key": "x", "type": "number", "value": "42"},
        ])
        errors = validate_node_data(node)
        dv_errors = [e for e in errors if "default_value" in (e.field or "")]
        assert len(dv_errors) == 0


class TestHumanInputSelectorValidation:
    """FormInputDefault.selector length validation."""

    def test_variable_selector_too_short(self):
        node = _make_node(NodeType.HUMAN_INPUT, inputs=[
            {
                "type": "text_input",
                "output_variable_name": "x",
                "default": {"type": "variable", "selector": ["only_one"]},
            },
        ])
        errors = validate_node_data(node)
        assert any("selector length" in e.message for e in errors)

    def test_variable_selector_valid(self):
        node = _make_node(NodeType.HUMAN_INPUT, inputs=[
            {
                "type": "text_input",
                "output_variable_name": "x",
                "default": {"type": "variable", "selector": ["node_id", "output"]},
            },
        ])
        errors = validate_node_data(node)
        selector_errors = [e for e in errors if "selector" in e.message]
        assert len(selector_errors) == 0

    def test_constant_type_no_selector_check(self):
        node = _make_node(NodeType.HUMAN_INPUT, inputs=[
            {
                "type": "text_input",
                "output_variable_name": "x",
                "default": {"type": "constant", "value": "hello", "selector": []},
            },
        ])
        errors = validate_node_data(node)
        selector_errors = [e for e in errors if "selector" in e.message]
        assert len(selector_errors) == 0


class TestDSLMetadataValidation:
    """DSL-level metadata validation (version, icon_type, env vars)."""

    def test_invalid_icon_type(self):
        from dify_workflow.node_data_validator import validate_dsl_metadata
        dsl = DifyDSL()
        dsl.app.icon_type = "svg"
        errors = validate_dsl_metadata(dsl)
        assert any("icon_type" in e.message for e in errors)

    def test_valid_icon_types(self):
        from dify_workflow.node_data_validator import validate_dsl_metadata
        for it in ("emoji", "image", "link"):
            dsl = DifyDSL()
            dsl.app.icon_type = it
            errors = validate_dsl_metadata(dsl)
            icon_errors = [e for e in errors if "icon_type" in e.message]
            assert len(icon_errors) == 0

    def test_env_var_missing_name(self):
        from dify_workflow.models import EnvironmentVariable
        from dify_workflow.node_data_validator import validate_dsl_metadata
        dsl = DifyDSL()
        dsl.workflow.environment_variables.append(
            EnvironmentVariable(name="", value="test")
        )
        errors = validate_dsl_metadata(dsl)
        assert any("environment_variables" in (e.field or "") and "name" in e.message for e in errors)

    def test_conversation_var_missing_name(self):
        from dify_workflow.node_data_validator import validate_dsl_metadata
        dsl = DifyDSL()
        dsl.workflow.conversation_variables.append({"value_type": "string"})
        errors = validate_dsl_metadata(dsl)
        assert any("conversation_variables" in (e.field or "") for e in errors)

    def test_version_compatibility_warning(self):
        from dify_workflow.node_data_validator import validate_dsl_metadata
        dsl = DifyDSL()
        dsl.version = "9.0.0"
        errors = validate_dsl_metadata(dsl)
        assert any("newer" in e.message for e in errors)
