"""Node configuration checks for pre-publish checklist validation.

Each _check_* function mirrors a frontend checkValid call
from use-checklist.ts for a specific node type.
"""

from __future__ import annotations

from typing import Any

from .models import Node, NodeType

from .checklist_validator import (
    ChecklistError,
    _extras,
    _get,
    _is_selector_empty,
    _EMPTY_OPS,
)


# ── Node configuration checks (mirrors frontend checkValid) ────────────

def _check_end(node: Node) -> list[ChecklistError]:
    errors = []
    outputs = _get(node, "outputs")
    if isinstance(outputs, list):
        if not outputs:
            errors.append(ChecklistError("error", "End node: output variable required", node.id, node.data.title, "outputs"))
        for i, out in enumerate(outputs):
            if isinstance(out, dict):
                if not out.get("variable", "").strip():
                    errors.append(ChecklistError("error", "End node: output variable name required", node.id, node.data.title, f"outputs[{i}].variable"))
                if _is_selector_empty(out.get("value_selector")):
                    errors.append(ChecklistError("error", "End node: output value_selector required", node.id, node.data.title, f"outputs[{i}].value_selector"))
            elif hasattr(out, "variable"):
                if not getattr(out, "variable", "").strip():
                    errors.append(ChecklistError("error", "End node: output variable name required", node.id, node.data.title, f"outputs[{i}].variable"))
                vs = getattr(out, "value_selector", [])
                if _is_selector_empty(vs):
                    errors.append(ChecklistError("error", "End node: output value_selector required", node.id, node.data.title, f"outputs[{i}].value_selector"))
    return errors


def _check_answer(node: Node) -> list[ChecklistError]:
    answer = _get(node, "answer", "")
    if not answer:
        return [ChecklistError("error", "Answer node: answer text required", node.id, node.data.title, "answer")]
    return []


def _check_llm(node: Node) -> list[ChecklistError]:
    errors = []
    model = _get(node, "model")
    if not model or not isinstance(model, dict) and not hasattr(model, "provider"):
        errors.append(ChecklistError("error", "LLM node: model required", node.id, node.data.title, "model"))
    else:
        provider = model.get("provider", "") if isinstance(model, dict) else getattr(model, "provider", "")
        if not provider:
            errors.append(ChecklistError("error", "LLM node: model provider required", node.id, node.data.title, "model.provider"))

    prompt = _get(node, "prompt_template")
    if prompt is not None:
        is_empty = True
        if isinstance(prompt, list):
            for p in prompt:
                text = p.get("text", "") if isinstance(p, dict) else getattr(p, "text", "")
                jinja = p.get("jinja2_text", "") if isinstance(p, dict) else getattr(p, "jinja2_text", "")
                if text or jinja:
                    is_empty = False
                    break
        elif isinstance(prompt, dict):
            if prompt.get("text") or prompt.get("jinja2_text"):
                is_empty = False
        if is_empty and not errors:
            errors.append(ChecklistError("error", "LLM node: prompt required", node.id, node.data.title, "prompt_template"))

    vision = _get(node, "vision")
    if isinstance(vision, dict) and vision.get("enabled"):
        configs = vision.get("configs", {})
        vs = configs.get("variable_selector", []) if isinstance(configs, dict) else []
        if _is_selector_empty(vs):
            errors.append(ChecklistError("error", "LLM node: vision variable required when vision enabled", node.id, node.data.title, "vision.configs.variable_selector"))

    return errors


def _check_code(node: Node) -> list[ChecklistError]:
    errors = []
    variables = _get(node, "variables", [])
    if isinstance(variables, list):
        for i, v in enumerate(variables):
            var_name = v.get("variable", "") if isinstance(v, dict) else getattr(v, "variable", "")
            if not var_name:
                errors.append(ChecklistError("error", "Code node: variable name required", node.id, node.data.title, f"variables[{i}].variable"))
            vs = v.get("value_selector", []) if isinstance(v, dict) else getattr(v, "value_selector", [])
            if _is_selector_empty(vs):
                errors.append(ChecklistError("error", "Code node: variable value_selector required", node.id, node.data.title, f"variables[{i}].value_selector"))

    code = _get(node, "code", "")
    if not code:
        errors.append(ChecklistError("error", "Code node: code required", node.id, node.data.title, "code"))
    return errors


def _check_if_else(node: Node) -> list[ChecklistError]:
    errors = []
    cases = node.data.cases or _get(node, "cases", [])
    if not cases:
        errors.append(ChecklistError("error", "IF/ELSE node: cases required", node.id, node.data.title, "cases"))
        return errors

    for ci, case in enumerate(cases):
        conditions = case.conditions if hasattr(case, "conditions") else (case.get("conditions", []) if isinstance(case, dict) else [])
        if not conditions:
            label = "IF" if ci == 0 else "ELIF"
            errors.append(ChecklistError("error", f"IF/ELSE node: {label} conditions required", node.id, node.data.title, f"cases[{ci}].conditions"))
            continue

        for cj, cond in enumerate(conditions):
            if isinstance(cond, dict):
                vs = cond.get("variable_selector", [])
                op = cond.get("comparison_operator", "")
                val = cond.get("value")
            else:
                vs = getattr(cond, "variable_selector", [])
                op = getattr(cond, "comparison_operator", "")
                val = getattr(cond, "value", None)

            if _is_selector_empty(vs):
                errors.append(ChecklistError("error", "IF/ELSE node: condition variable required", node.id, node.data.title, f"cases[{ci}].conditions[{cj}].variable_selector"))
            if not op:
                errors.append(ChecklistError("error", "IF/ELSE node: condition operator required", node.id, node.data.title, f"cases[{ci}].conditions[{cj}].comparison_operator"))
            elif op.lower() not in _EMPTY_OPS and not val:
                errors.append(ChecklistError("error", "IF/ELSE node: condition value required", node.id, node.data.title, f"cases[{ci}].conditions[{cj}].value"))
    return errors


def _check_question_classifier(node: Node) -> list[ChecklistError]:
    errors = []
    qvs = _get(node, "query_variable_selector", [])
    if _is_selector_empty(qvs):
        errors.append(ChecklistError("error", "Question Classifier: input variable required", node.id, node.data.title, "query_variable_selector"))

    model = _get(node, "model")
    if not model:
        errors.append(ChecklistError("error", "Question Classifier: model required", node.id, node.data.title, "model"))
    else:
        provider = model.get("provider", "") if isinstance(model, dict) else getattr(model, "provider", "")
        if not provider:
            errors.append(ChecklistError("error", "Question Classifier: model provider required", node.id, node.data.title, "model.provider"))

    classes = _get(node, "classes", [])
    if not classes:
        errors.append(ChecklistError("error", "Question Classifier: classes required", node.id, node.data.title, "classes"))
    else:
        for i, cls in enumerate(classes):
            name = cls.get("name", "") if isinstance(cls, dict) else getattr(cls, "name", "")
            if not name:
                errors.append(ChecklistError("error", f"Question Classifier: class[{i}] name required", node.id, node.data.title, f"classes[{i}].name"))
    return errors


def _check_parameter_extractor(node: Node) -> list[ChecklistError]:
    errors = []
    model = _get(node, "model")
    if not model:
        errors.append(ChecklistError("error", "Parameter Extractor: model required", node.id, node.data.title, "model"))
    else:
        provider = model.get("provider", "") if isinstance(model, dict) else getattr(model, "provider", "")
        if not provider:
            errors.append(ChecklistError("error", "Parameter Extractor: model provider required", node.id, node.data.title, "model.provider"))

    query = _get(node, "query", [])
    if _is_selector_empty(query):
        errors.append(ChecklistError("error", "Parameter Extractor: query variable required", node.id, node.data.title, "query"))

    params = _get(node, "parameters", [])
    if not params:
        errors.append(ChecklistError("error", "Parameter Extractor: parameters required", node.id, node.data.title, "parameters"))
    elif isinstance(params, list):
        for i, param in enumerate(params):
            if isinstance(param, dict):
                if not param.get("name", "").strip():
                    errors.append(ChecklistError("error", f"Parameter Extractor: parameter[{i}] name required", node.id, node.data.title, f"parameters[{i}].name"))
                if not param.get("type", "").strip():
                    errors.append(ChecklistError("error", f"Parameter Extractor: parameter[{i}] type required", node.id, node.data.title, f"parameters[{i}].type"))
                if not param.get("description", "").strip():
                    errors.append(ChecklistError("error", f"Parameter Extractor: parameter[{i}] description required", node.id, node.data.title, f"parameters[{i}].description"))
            elif hasattr(param, "name"):
                if not getattr(param, "name", "").strip():
                    errors.append(ChecklistError("error", f"Parameter Extractor: parameter[{i}] name required", node.id, node.data.title, f"parameters[{i}].name"))
                if not getattr(param, "type", "").strip():
                    errors.append(ChecklistError("error", f"Parameter Extractor: parameter[{i}] type required", node.id, node.data.title, f"parameters[{i}].type"))
                if not getattr(param, "description", "").strip():
                    errors.append(ChecklistError("error", f"Parameter Extractor: parameter[{i}] description required", node.id, node.data.title, f"parameters[{i}].description"))
    return errors


def _check_knowledge_retrieval(node: Node) -> list[ChecklistError]:
    errors = []
    dataset_ids = _get(node, "dataset_ids", [])
    if not dataset_ids:
        errors.append(ChecklistError("error", "Knowledge Retrieval: knowledge base required", node.id, node.data.title, "dataset_ids"))
    return errors


def _check_http_request(node: Node) -> list[ChecklistError]:
    errors = []
    url = _get(node, "url", "")
    if not url:
        errors.append(ChecklistError("error", "HTTP Request: URL required", node.id, node.data.title, "url"))
    return errors


def _check_tool(node: Node) -> list[ChecklistError]:
    errors = []
    provider_id = _get(node, "provider_id", "")
    if not provider_id:
        errors.append(ChecklistError("error", "Tool node: provider_id required", node.id, node.data.title, "provider_id"))
    tool_name = _get(node, "tool_name", "")
    if not tool_name:
        errors.append(ChecklistError("error", "Tool node: tool_name required", node.id, node.data.title, "tool_name"))
    return errors


def _check_template_transform(node: Node) -> list[ChecklistError]:
    errors = []
    variables = _get(node, "variables", [])
    if isinstance(variables, list):
        for i, v in enumerate(variables):
            var_name = v.get("variable", "") if isinstance(v, dict) else getattr(v, "variable", "")
            if not var_name:
                errors.append(ChecklistError("error", "Template Transform: variable name required", node.id, node.data.title, f"variables[{i}].variable"))
            vs = v.get("value_selector", []) if isinstance(v, dict) else getattr(v, "value_selector", [])
            if _is_selector_empty(vs):
                errors.append(ChecklistError("error", "Template Transform: variable value_selector required", node.id, node.data.title, f"variables[{i}].value_selector"))

    template = _get(node, "template", "")
    if not template:
        errors.append(ChecklistError("error", "Template Transform: template required", node.id, node.data.title, "template"))
    return errors


def _check_iteration(node: Node) -> list[ChecklistError]:
    it_sel = _get(node, "iterator_selector", [])
    if _is_selector_empty(it_sel):
        return [ChecklistError("error", "Iteration node: iterator_selector required", node.id, node.data.title, "iterator_selector")]
    return []


def _check_loop(node: Node) -> list[ChecklistError]:
    errors = []
    loop_count = _get(node, "loop_count", 0)
    if not loop_count or loop_count < 1:
        errors.append(ChecklistError("error", "Loop node: loop_count must be >= 1", node.id, node.data.title, "loop_count"))

    conditions = _get(node, "break_conditions", [])
    if isinstance(conditions, list):
        for i, cond in enumerate(conditions):
            if isinstance(cond, dict):
                vs = cond.get("variable_selector", [])
                op = cond.get("comparison_operator", "")
                val = cond.get("value")
            else:
                vs = getattr(cond, "variable_selector", [])
                op = getattr(cond, "comparison_operator", "")
                val = getattr(cond, "value", None)
            if _is_selector_empty(vs):
                errors.append(ChecklistError("error", "Loop node: break condition variable required", node.id, node.data.title, f"break_conditions[{i}].variable_selector"))
            if not op:
                errors.append(ChecklistError("error", "Loop node: break condition operator required", node.id, node.data.title, f"break_conditions[{i}].comparison_operator"))
            elif op.lower() not in _EMPTY_OPS and not val:
                errors.append(ChecklistError("error", "Loop node: break condition value required", node.id, node.data.title, f"break_conditions[{i}].value"))
    return errors


def _check_human_input(node: Node) -> list[ChecklistError]:
    errors = []
    actions = _get(node, "user_actions", [])
    if not actions:
        errors.append(ChecklistError("error", "Human Input: user_actions required", node.id, node.data.title, "user_actions"))
    elif isinstance(actions, list):
        seen_ids: set[str] = set()
        for i, act in enumerate(actions):
            title = act.get("title", "") if isinstance(act, dict) else getattr(act, "title", "")
            if not title or not title.strip():
                errors.append(ChecklistError("error", f"Human Input: action[{i}] title required", node.id, node.data.title, f"user_actions[{i}].title"))
            aid = act.get("id", "") if isinstance(act, dict) else getattr(act, "id", "")
            if aid in seen_ids:
                errors.append(ChecklistError("error", f"Human Input: duplicate action id '{aid}'", node.id, node.data.title, f"user_actions[{i}].id"))
            if aid:
                seen_ids.add(aid)
    return errors


def _check_document_extractor(node: Node) -> list[ChecklistError]:
    vs = _get(node, "variable_selector", [])
    if _is_selector_empty(vs):
        return [ChecklistError("error", "Document Extractor: variable_selector required", node.id, node.data.title, "variable_selector")]
    return []


def _check_variable_assigner(node: Node) -> list[ChecklistError]:
    items = _get(node, "items", [])
    if not items:
        return [ChecklistError("error", "Variable Assigner: items required", node.id, node.data.title, "items")]
    return []


def _check_list_operator(node: Node) -> list[ChecklistError]:
    var = _get(node, "variable", [])
    if _is_selector_empty(var):
        return [ChecklistError("error", "List Operator: variable required", node.id, node.data.title, "variable")]
    return []


# ── Check dispatch table ────────────────────────────────────────────────

_NODE_CHECKERS: dict[str, Any] = {
    NodeType.END: _check_end,
    NodeType.ANSWER: _check_answer,
    NodeType.LLM: _check_llm,
    NodeType.CODE: _check_code,
    NodeType.IF_ELSE: _check_if_else,
    NodeType.QUESTION_CLASSIFIER: _check_question_classifier,
    NodeType.PARAMETER_EXTRACTOR: _check_parameter_extractor,
    NodeType.KNOWLEDGE_RETRIEVAL: _check_knowledge_retrieval,
    NodeType.HTTP_REQUEST: _check_http_request,
    NodeType.TOOL: _check_tool,
    NodeType.TEMPLATE_TRANSFORM: _check_template_transform,
    NodeType.ITERATION: _check_iteration,
    NodeType.LOOP: _check_loop,
    NodeType.HUMAN_INPUT: _check_human_input,
    NodeType.DOCUMENT_EXTRACTOR: _check_document_extractor,
    NodeType.VARIABLE_ASSIGNER: _check_variable_assigner,
    NodeType.LIST_OPERATOR: _check_list_operator,
}
