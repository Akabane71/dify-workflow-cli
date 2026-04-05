"""Shared utilities for CLI modules — console, helpers, constants."""

from __future__ import annotations

import json
import sys

import click
from rich.console import Console

from .frontend_validator import validate_frontend_compat
from .node_data_validator import validate_node_data

console = Console()


class OrderedGroup(click.Group):
    """Click group that preserves command registration order in --help."""
    def list_commands(self, ctx: click.Context) -> list[str]:
        return list(self.commands)


def output_json(data: dict) -> None:
    click.echo(json.dumps(data, indent=2, ensure_ascii=False))


def check_node_errors(node, *, action: str = "add") -> None:
    """Validate a node after creation/update. Abort with errors if invalid.

    Runs both backend schema validation and frontend crash prevention.
    Only reports errors (not warnings) — warnings don't cause failures.
    """
    errors = []
    for err in validate_node_data(node):
        if err.level == "error":
            errors.append(err)
    for err in validate_frontend_compat(node):
        if err.level == "error":
            errors.append(err)

    if errors:
        click.echo(f"Error: Cannot {action} node '{node.id}' — validation failed:", err=True)
        for e in errors:
            field_hint = f" [{e.field}]" if e.field else ""
            click.echo(f"  • {e.message}{field_hint}", err=True)
        sys.exit(1)


MODE_CHOICES = ["workflow", "chatflow", "chat", "agent", "completion"]
MODE_HELP = (
    "App mode: workflow (visual nodes→End), chatflow (visual nodes→Answer, multi-turn), "
    "chat (simple chatbot), agent (chat+tools), completion (single-turn text gen)"
)

DIFY_TEST_DEFAULT = "dify-test"

# All supported node types and their descriptions, for help and discovery
NODE_TYPE_INFO: list[tuple[str, str, str]] = [
    ("start",                "Workflow entry point",        "variables (input params)"),
    ("end",                  "Workflow output/termination", "outputs (variable mappings)"),
    ("answer",               "Answer output node",          "answer, variables"),
    ("llm",                  "Large language model call",   "model, prompt_template, vision, memory"),
    ("tool",                 "External tool/plugin call",   "provider_id, tool_name, tool_parameters"),
    ("code",                 "Python/JavaScript execution", "code, code_language"),
    ("if-else",              "Conditional branching",       "cases (conditions list)"),
    ("template-transform",   "Jinja2 template rendering",   "template"),
    ("http-request",         "HTTP API request",            "url, method, headers, body"),
    ("knowledge-retrieval",  "RAG knowledge retrieval",     "dataset_ids, retrieval_model, query_variable_selector"),
    ("question-classifier",  "Question classification",     "query_variable_selector, model, classes, instruction"),
    ("parameter-extractor",  "Parameter extraction",        "model, query, parameters, reasoning_mode, instruction"),
    ("variable-aggregator",  "Variable aggregation (legacy)", "output_type, variables"),
    ("assigner",             "Variable assigner (write)",   "version, items (variable_selector, operation, value)"),
    ("list-operator",        "List filter/sort/slice",      "variable, filter_by, order_by, limit, extract_by"),
    ("iteration",            "Iterate over list items",     "iterator_selector, output_selector, is_parallel, error_handle_mode"),
    ("loop",                 "Loop with break conditions",  "loop_count, break_conditions, loop_variables, logical_operator"),
    ("agent",                "Autonomous agent node",       "agent_strategy_provider_name, agent_strategy_name, agent_parameters"),
    ("document-extractor",   "Document/file text extraction", "variable_selector, is_array_file"),
    ("human-input",          "Human review/input form",     "form_content, inputs, user_actions, timeout"),
    ("knowledge-index",      "Index data into knowledge base", "chunk_structure, index_chunk_variable_selector, indexing_technique"),
    ("datasource",           "Datasource entry point",      "plugin_id, provider_name, provider_type, datasource_parameters"),
    ("trigger-webhook",      "HTTP webhook trigger",        "method, content_type, headers, params, body"),
    ("trigger-schedule",     "Scheduled trigger",           "mode, frequency, timezone, cron_expression"),
    ("trigger-plugin",       "Plugin-based trigger",        "plugin_id, provider_id, event_name, event_parameters"),
]

NODE_TYPES_STR = ", ".join(t[0] for t in NODE_TYPE_INFO)
