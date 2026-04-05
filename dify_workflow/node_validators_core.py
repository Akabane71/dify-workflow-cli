"""Node data validators for core node types.

Covers: code, template_transform, http_request, tool, knowledge_retrieval,
question_classifier, parameter_extractor, variable_aggregator,
variable_assigner, iteration, loop, document_extractor, list_operator.
"""

from __future__ import annotations

import re

from .models import Node
from .node_data_validator import (
    NodeDataError,
    _get_field,
    _ALLOWED_CODE_OUTPUT_TYPES,
    _RESERVED_PARAMETER_NAMES,
    _VALID_HTTP_AUTH_CONFIG_TYPES,
    _VALID_HTTP_AUTH_TYPES,
    _VALID_HTTP_BODY_TYPES,
    _VALID_LOOP_VAR_TYPES,
    _VALID_PARAMETER_TYPES,
    _VALID_TOOL_INPUT_TYPES,
    _VALID_TOOL_PROVIDER_TYPES,
)


def _validate_code(node: Node) -> list[NodeDataError]:
    errors: list[NodeDataError] = []
    code_lang = node.data.code_language or _get_field(node, "code_language")
    if not code_lang:
        errors.append(NodeDataError("warning", "Code node missing 'code_language'", node.id, "code_language"))
    elif code_lang not in ("python3", "javascript"):
        errors.append(NodeDataError("error", f"Code node invalid code_language: {code_lang!r} (must be 'python3' or 'javascript')", node.id, "code_language"))

    code = node.data.code or _get_field(node, "code", "")
    if not code:
        errors.append(NodeDataError("warning", "Code node has empty code", node.id, "code"))
    else:
        # Validate function signature: must contain def main(...) or function main(...)
        if code_lang == "python3":
            match = re.search(r"def\s+main\s*\((.*?)\)", code)
            if not match:
                errors.append(NodeDataError(
                    "error",
                    "Code node (python3) must define a 'def main(...)' function",
                    node.id, "code",
                ))
            else:
                # Extract function parameter names
                params_str = match.group(1).strip()
                if params_str:
                    func_params = [p.split(":")[0].strip() for p in params_str.split(",") if p.strip()]
                else:
                    func_params = []
                # Cross-check with declared variables
                variables = _get_field(node, "variables")
                if isinstance(variables, list):
                    var_names = []
                    for v in variables:
                        if isinstance(v, dict):
                            var_names.append(v.get("variable", ""))
                        elif hasattr(v, "variable"):
                            var_names.append(v.variable)
                    if set(func_params) != set(var_names):
                        errors.append(NodeDataError(
                            "warning",
                            f"Code node function params {func_params} don't match declared variables {var_names}",
                            node.id, "variables",
                        ))
        elif code_lang == "javascript":
            match = re.search(r"function\s+main\s*\((.*?)\)", code)
            if not match:
                errors.append(NodeDataError(
                    "error",
                    "Code node (javascript) must define a 'function main(...)' function",
                    node.id, "code",
                ))

    # Validate outputs structure (must be dict for code nodes)
    outputs = _get_field(node, "outputs")
    if outputs is None:
        # Check typed field too (in case it's stored there for backward compat)
        outputs = node.data.outputs
    if isinstance(outputs, dict):
        if not outputs:
            errors.append(NodeDataError("warning", "Code node has empty outputs", node.id, "outputs"))
        for name, output in outputs.items():
            if isinstance(output, dict):
                out_type = output.get("type")
                if not out_type:
                    errors.append(NodeDataError(
                        "error",
                        f"Code node output '{name}' missing 'type'",
                        node.id, f"outputs.{name}.type",
                    ))
                elif out_type not in _ALLOWED_CODE_OUTPUT_TYPES:
                    errors.append(NodeDataError(
                        "error",
                        f"Code node output '{name}' invalid type: {out_type!r} "
                        f"(allowed: {', '.join(sorted(_ALLOWED_CODE_OUTPUT_TYPES))})",
                        node.id, f"outputs.{name}.type",
                    ))
    elif outputs is not None and not isinstance(outputs, list):
        errors.append(NodeDataError(
            "error",
            "Code node 'outputs' must be a dict mapping name → {type, children}",
            node.id, "outputs",
        ))

    # Validate variables structure (must be list of {variable, value_selector})
    variables = _get_field(node, "variables")
    if isinstance(variables, list):
        for i, v in enumerate(variables):
            if isinstance(v, dict):
                if not v.get("variable"):
                    errors.append(NodeDataError(
                        "error",
                        f"Code node variables[{i}] missing 'variable' name",
                        node.id, f"variables[{i}].variable",
                    ))
                vs = v.get("value_selector")
                if not vs or (isinstance(vs, list) and not any(vs)):
                    errors.append(NodeDataError(
                        "warning",
                        f"Code node variables[{i}] missing 'value_selector'",
                        node.id, f"variables[{i}].value_selector",
                    ))
            elif hasattr(v, "variable"):
                if not getattr(v, "variable", ""):
                    errors.append(NodeDataError(
                        "error",
                        f"Code node variables[{i}] missing 'variable' name",
                        node.id, f"variables[{i}].variable",
                    ))
                vs = getattr(v, "value_selector", [])
                if not vs or (isinstance(vs, list) and not any(vs)):
                    errors.append(NodeDataError(
                        "warning",
                        f"Code node variables[{i}] missing 'value_selector'",
                        node.id, f"variables[{i}].value_selector",
                    ))

    return errors


def _validate_template_transform(node: Node) -> list[NodeDataError]:
    errors: list[NodeDataError] = []
    template = node.data.template
    if template is None and not _get_field(node, "template"):
        errors.append(NodeDataError("warning", "Template Transform node missing 'template'", node.id, "template"))
    return errors


def _validate_http_request(node: Node) -> list[NodeDataError]:
    errors: list[NodeDataError] = []
    url = node.data.url or _get_field(node, "url", "")
    if not url:
        errors.append(NodeDataError("warning", "HTTP Request node has no URL", node.id, "url"))
    method = node.data.method or _get_field(node, "method")
    if method:
        valid_methods = {"get", "post", "put", "patch", "delete", "head", "options"}
        if method.lower() not in valid_methods:
            errors.append(NodeDataError("error", f"HTTP Request invalid method: {method!r}", node.id, "method"))

    # Authorization validation (graphon HttpRequestNodeAuthorization.check_config)
    authorization = _get_field(node, "authorization")
    if isinstance(authorization, dict):
        auth_type = authorization.get("type")
        if auth_type and auth_type not in _VALID_HTTP_AUTH_TYPES:
            errors.append(NodeDataError(
                "error",
                f"HTTP Request invalid authorization type: {auth_type!r} (must be 'no-auth' or 'api-key')",
                node.id, "authorization.type",
            ))
        if auth_type == "api-key":
            config = authorization.get("config")
            if not config or not isinstance(config, dict):
                errors.append(NodeDataError(
                    "error",
                    "HTTP Request authorization config must be a dict when type is 'api-key'",
                    node.id, "authorization.config",
                ))
            elif config:
                config_type = config.get("type")
                if config_type and config_type not in _VALID_HTTP_AUTH_CONFIG_TYPES:
                    errors.append(NodeDataError(
                        "error",
                        f"HTTP Request auth config invalid type: {config_type!r} (must be 'basic', 'bearer', or 'custom')",
                        node.id, "authorization.config.type",
                    ))

    # Body type validation (graphon HttpRequestNodeBody)
    body = node.data.body or _get_field(node, "body")
    if isinstance(body, dict):
        body_type = body.get("type")
        if body_type and body_type not in _VALID_HTTP_BODY_TYPES:
            errors.append(NodeDataError(
                "error",
                f"HTTP Request invalid body type: {body_type!r}",
                node.id, "body.type",
            ))

    return errors


def _validate_tool(node: Node) -> list[NodeDataError]:
    errors: list[NodeDataError] = []
    for field in ("provider_id", "tool_name"):
        if not _get_field(node, field):
            errors.append(NodeDataError("warning", f"Tool node missing '{field}'", node.id, field))

    # provider_type validation (graphon ToolProviderType enum)
    provider_type = node.data.provider_type or _get_field(node, "provider_type")
    if provider_type and provider_type not in _VALID_TOOL_PROVIDER_TYPES:
        errors.append(NodeDataError(
            "error",
            f"Tool node invalid provider_type: {provider_type!r} "
            f"(valid: {', '.join(sorted(_VALID_TOOL_PROVIDER_TYPES))})",
            node.id, "provider_type",
        ))

    # tool_configurations validation (graphon ToolEntity.validate_tool_configurations)
    tool_configs = node.data.tool_parameters if node.data.tool_parameters is None else _get_field(node, "tool_configurations")
    if tool_configs is not None:
        if not isinstance(tool_configs, dict):
            errors.append(NodeDataError(
                "error", "Tool node tool_configurations must be a dict",
                node.id, "tool_configurations",
            ))
        else:
            for key, val in tool_configs.items():
                if val is not None and not isinstance(val, (str, int, float, bool)):
                    errors.append(NodeDataError(
                        "error",
                        f"Tool node tool_configurations['{key}'] must be a scalar (str/int/float/bool)",
                        node.id, f"tool_configurations.{key}",
                    ))

    # tool_parameters validation (graphon ToolNodeData.ToolInput type cross-validation)
    tool_params = node.data.tool_parameters or _get_field(node, "tool_parameters")
    if isinstance(tool_params, dict):
        for pname, param in tool_params.items():
            if isinstance(param, dict):
                ptype = param.get("type")
                pvalue = param.get("value")
                if ptype and ptype not in _VALID_TOOL_INPUT_TYPES:
                    errors.append(NodeDataError(
                        "error",
                        f"Tool node parameter '{pname}' invalid type: {ptype!r} (must be 'mixed', 'variable', or 'constant')",
                        node.id, f"tool_parameters.{pname}.type",
                    ))
                if ptype and pvalue is not None:
                    if ptype == "mixed" and not isinstance(pvalue, str):
                        errors.append(NodeDataError(
                            "error",
                            f"Tool node parameter '{pname}' value must be string for type 'mixed'",
                            node.id, f"tool_parameters.{pname}.value",
                        ))
                    elif ptype == "variable" and not isinstance(pvalue, list):
                        errors.append(NodeDataError(
                            "error",
                            f"Tool node parameter '{pname}' value must be list[str] for type 'variable'",
                            node.id, f"tool_parameters.{pname}.value",
                        ))

    return errors


def _validate_knowledge_retrieval(node: Node) -> list[NodeDataError]:
    errors: list[NodeDataError] = []
    if not node.data.dataset_ids:
        errors.append(NodeDataError("warning", "Knowledge Retrieval node has no dataset IDs", node.id, "dataset_ids"))
    return errors


def _validate_question_classifier(node: Node) -> list[NodeDataError]:
    errors: list[NodeDataError] = []
    qvs = _get_field(node, "query_variable_selector")
    if not qvs or (isinstance(qvs, list) and not any(qvs)):
        errors.append(NodeDataError("warning", "Question Classifier missing 'query_variable_selector'", node.id, "query_variable_selector"))
    model = node.data.model or _get_field(node, "model")
    if model is None:
        errors.append(NodeDataError("error", "Question Classifier missing 'model' configuration", node.id, "model"))
    else:
        provider = getattr(model, "provider", None) if not isinstance(model, dict) else model.get("provider")
        if not provider:
            errors.append(NodeDataError("warning", "Question Classifier model missing 'provider'", node.id, "model.provider"))
    classes = _get_field(node, "classes")
    if classes is None:
        errors.append(NodeDataError("error", "Question Classifier missing 'classes'", node.id, "classes"))
    elif isinstance(classes, list):
        for i, cls in enumerate(classes):
            name = cls.get("name", "") if isinstance(cls, dict) else getattr(cls, "name", "")
            if not name:
                errors.append(NodeDataError("warning", f"Question Classifier classes[{i}] missing 'name'", node.id, f"classes[{i}].name"))
    return errors


def _validate_parameter_extractor(node: Node) -> list[NodeDataError]:
    errors: list[NodeDataError] = []
    model = node.data.model or _get_field(node, "model")
    if model is None:
        errors.append(NodeDataError("error", "Parameter Extractor missing 'model' configuration", node.id, "model"))
    else:
        provider = getattr(model, "provider", None) if not isinstance(model, dict) else model.get("provider")
        if not provider:
            errors.append(NodeDataError("warning", "Parameter Extractor model missing 'provider'", node.id, "model.provider"))
    query = _get_field(node, "query")
    if not query or (isinstance(query, list) and not any(query)):
        errors.append(NodeDataError("warning", "Parameter Extractor missing 'query'", node.id, "query"))
    if not _get_field(node, "parameters"):
        errors.append(NodeDataError("warning", "Parameter Extractor missing 'parameters'", node.id, "parameters"))
    reasoning = _get_field(node, "reasoning_mode")
    if reasoning and reasoning not in ("function_call", "prompt"):
        errors.append(NodeDataError("error", f"Parameter Extractor invalid reasoning_mode: {reasoning!r}", node.id, "reasoning_mode"))

    # Validate each parameter config (graphon ParameterConfig validators)
    parameters = _get_field(node, "parameters", [])
    if isinstance(parameters, list):
        for i, param in enumerate(parameters):
            if isinstance(param, dict):
                pname = param.get("name", "")
                # name is required and cannot be reserved
                if not pname:
                    errors.append(NodeDataError(
                        "error",
                        f"Parameter Extractor parameters[{i}] name is required",
                        node.id, f"parameters[{i}].name",
                    ))
                elif pname in _RESERVED_PARAMETER_NAMES:
                    errors.append(NodeDataError(
                        "error",
                        f"Parameter Extractor parameters[{i}] name '{pname}' is reserved (__reason and __is_success are reserved)",
                        node.id, f"parameters[{i}].name",
                    ))

                # type must be in valid set
                ptype = param.get("type")
                if not ptype:
                    errors.append(NodeDataError(
                        "warning",
                        f"Parameter Extractor parameters[{i}] type is required",
                        node.id, f"parameters[{i}].type",
                    ))
                elif ptype not in _VALID_PARAMETER_TYPES:
                    errors.append(NodeDataError(
                        "error",
                        f"Parameter Extractor parameters[{i}] invalid type: {ptype!r} "
                        f"(allowed: {', '.join(sorted(_VALID_PARAMETER_TYPES))})",
                        node.id, f"parameters[{i}].type",
                    ))

                # description is required by frontend checkValid
                pdesc = param.get("description", "")
                if not pdesc:
                    errors.append(NodeDataError(
                        "warning",
                        f"Parameter Extractor parameters[{i}] description is required",
                        node.id, f"parameters[{i}].description",
                    ))

    return errors


def _validate_variable_aggregator(node: Node) -> list[NodeDataError]:
    errors: list[NodeDataError] = []
    if not _get_field(node, "output_type"):
        errors.append(NodeDataError("warning", "Variable Aggregator missing 'output_type'", node.id, "output_type"))
    return errors


def _validate_variable_assigner(node: Node) -> list[NodeDataError]:
    errors: list[NodeDataError] = []
    version = _get_field(node, "version", "1")
    if version == "1":
        for field in ("assigned_variable_selector", "write_mode", "input_variable_selector"):
            if not _get_field(node, field):
                errors.append(NodeDataError("warning", f"Variable Assigner v1 missing '{field}'", node.id, field))
        write_mode = _get_field(node, "write_mode")
        if write_mode and write_mode not in ("over-write", "append", "clear"):
            errors.append(NodeDataError("error", f"Variable Assigner invalid write_mode: {write_mode!r}", node.id, "write_mode"))
    return errors


def _validate_iteration(node: Node) -> list[NodeDataError]:
    errors: list[NodeDataError] = []
    if not _get_field(node, "iterator_selector"):
        errors.append(NodeDataError("warning", "Iteration node missing 'iterator_selector'", node.id, "iterator_selector"))
    if not _get_field(node, "output_selector"):
        errors.append(NodeDataError("warning", "Iteration node missing 'output_selector'", node.id, "output_selector"))
    return errors


def _validate_loop(node: Node) -> list[NodeDataError]:
    errors: list[NodeDataError] = []
    if _get_field(node, "loop_count") is None:
        errors.append(NodeDataError("warning", "Loop node missing 'loop_count'", node.id, "loop_count"))
    if _get_field(node, "break_conditions") is None:
        errors.append(NodeDataError("warning", "Loop node missing 'break_conditions'", node.id, "break_conditions"))
    logical_op = _get_field(node, "logical_operator")
    if logical_op and logical_op not in ("and", "or"):
        errors.append(NodeDataError("error", f"Loop node invalid logical_operator: {logical_op!r}", node.id, "logical_operator"))

    # Validate loop_variables types (graphon LoopVariableData._is_valid_var_type)
    loop_vars = _get_field(node, "loop_variables", [])
    if isinstance(loop_vars, list):
        for i, lv in enumerate(loop_vars):
            if isinstance(lv, dict):
                vt = lv.get("var_type")
                if vt and vt not in _VALID_LOOP_VAR_TYPES:
                    errors.append(NodeDataError(
                        "error",
                        f"Loop node loop_variables[{i}] invalid var_type: {vt!r} "
                        f"(allowed: {', '.join(sorted(_VALID_LOOP_VAR_TYPES))})",
                        node.id, f"loop_variables[{i}].var_type",
                    ))

    return errors


def _validate_document_extractor(node: Node) -> list[NodeDataError]:
    errors: list[NodeDataError] = []
    if not _get_field(node, "variable_selector"):
        errors.append(NodeDataError("warning", "Document Extractor missing 'variable_selector'", node.id, "variable_selector"))
    return errors


def _validate_list_operator(node: Node) -> list[NodeDataError]:
    errors: list[NodeDataError] = []
    for field in ("filter_by", "order_by", "limit"):
        if _get_field(node, field) is None:
            errors.append(NodeDataError("warning", f"List Operator missing '{field}'", node.id, field))
    return errors
