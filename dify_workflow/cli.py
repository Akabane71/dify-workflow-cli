"""Dify Workflow CLI - Main entry point.

This CLI is designed for AI agents and scripts to progressively discover and
use Dify workflow operations. Every command and subcommand has detailed --help
with examples, supported values, and next-step guidance.

Usage pattern for AI agents:
  1. dify-workflow --help                 → discover available commands
  2. dify-workflow <command> --help       → learn command usage and examples
  3. dify-workflow list-node-types        → discover supported node types
  4. dify-workflow guide                  → step-by-step tutorial
"""

from __future__ import annotations

import sys
import textwrap

import click
from rich.table import Table

from .cli_shared import (
    DIFY_TEST_DEFAULT,
    MODE_CHOICES,
    MODE_HELP,
    NODE_TYPE_INFO,
    NODE_TYPES_STR,
    OrderedGroup,
    console,
    output_json,
)
from .io import save_workflow
from .scanner import scan_dify_project


def _configure_stdio() -> None:
    """Prefer UTF-8 stdio so Click help text works on Windows locales."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8")
        except ValueError:
            # Some redirected streams do not allow reconfiguration.
            pass


_configure_stdio()


@click.group(cls=OrderedGroup, invoke_without_command=True)
@click.version_option(version="0.1.0", prog_name="dify-workflow")
@click.pass_context
def cli(ctx):
    """Dify Workflow CLI — create, edit, validate, and export Dify workflow DSL files.

    \b
    QUICK START (run these commands in order):
      1. dify-workflow guide                    → interactive tutorial
      2. dify-workflow list-node-types          → see all 22 node types
      3. dify-workflow create -o my.yaml        → create a workflow
      4. dify-workflow inspect my.yaml          → view its structure
      5. dify-workflow validate my.yaml         → check if it's valid
      6. dify-workflow export my.yaml           → export to stdout

    \b
    FOR AI AGENTS:
      • Every command supports -j / --json-output for structured JSON output
      • Use --help on any command or subcommand to see usage and examples
      • Use 'dify-workflow list-node-types -j' to get node type metadata
      • Use 'dify-workflow guide -j' for machine-readable step-by-step guide

    \b
    COMMANDS OVERVIEW:
      guide             Step-by-step tutorial for first-time users
      list-node-types   List all 22 supported node types with descriptions
      scan              [DEPRECATED] Analyze dify-test source code structure
      create            Create a new workflow from a template
      inspect           View a workflow's structure (tree / JSON / Mermaid)
      validate          Check a workflow for errors and warnings
      checklist         Pre-publish checklist (mirrors Dify frontend)
      edit              Edit nodes and edges (subcommands: add-node, remove-node, ...)
      export            Export workflow to YAML or JSON
      import            Import, validate, and re-export a workflow
      diff              Compare two workflow files
      layout            Auto-layout workflow nodes
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# ─── guide ───

@cli.command()
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON (machine-readable step list)")
def guide(json_output: bool):
    """Step-by-step tutorial: learn this CLI from zero in 6 steps.

    \b
    This command prints a progressive tutorial that teaches you (or an AI agent)
    how to use all major features of the CLI. Run it first when you're new.

    \b
    EXAMPLES:
      dify-workflow guide          → human-readable tutorial
      dify-workflow guide -j       → JSON step list for AI agents
    """
    steps = [
        {
            "step": 1,
            "title": "Discover available commands",
            "command": "dify-workflow --help",
            "explanation": "Shows all top-level commands with descriptions. Start here.",
        },
        {
            "step": 2,
            "title": "Learn about node types",
            "command": "dify-workflow list-node-types",
            "explanation": "Lists all 22 supported Dify node types (start, end, llm, code, etc.) with their key fields.",
        },
        {
            "step": 3,
            "title": "Create your first workflow",
            "command": 'dify-workflow create --name "My Bot" --template llm --output workflow.yaml',
            "explanation": "Creates a Start → LLM → End workflow. Templates: minimal, llm, if-else.",
        },
        {
            "step": 4,
            "title": "Inspect the workflow structure",
            "command": "dify-workflow inspect workflow.yaml",
            "explanation": "Shows all nodes, edges, and variables in a tree view. Use -j for JSON.",
        },
        {
            "step": 5,
            "title": "Edit the workflow",
            "command": "dify-workflow edit --help",
            "explanation": "Shows edit subcommands: add-node, remove-node, update-node, add-edge, remove-edge, set-title. Each has its own --help.",
        },
        {
            "step": 6,
            "title": "Validate and export",
            "command": "dify-workflow validate workflow.yaml && dify-workflow export workflow.yaml --output final.yaml",
            "explanation": "Validate checks for errors. Export saves the final DSL file in YAML or JSON format.",
        },
    ]

    if json_output:
        output_json({"steps": steps, "total": len(steps),
                       "tip": "Run each command in order. Use --help on any command for details."})
        return

    console.print("\n[bold]Dify Workflow CLI — Step-by-Step Guide[/bold]\n")
    for s in steps:
        console.print(f"[cyan]Step {s['step']}:[/cyan] [bold]{s['title']}[/bold]")
        console.print(f"  $ {s['command']}")
        console.print(f"  {s['explanation']}\n")
    console.print("[dim]Tip: Add --help to any command to see detailed usage and examples.[/dim]")


# ─── list-node-types ───

@cli.command("list-node-types")
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON (machine-readable node type list)")
@click.option("--type", "filter_type", default=None, help="Show details for a specific node type")
def list_node_types(json_output: bool, filter_type: str | None):
    """List all 22 supported Dify workflow node types.

    \b
    Shows each node type's name, description, and key data fields.
    Use this to discover which --type value to pass to 'edit add-node'.

    \b
    EXAMPLES:
      dify-workflow list-node-types               → table of all types
      dify-workflow list-node-types -j             → JSON list for AI agents
      dify-workflow list-node-types --type llm     → details for LLM node

    \b
    NEXT STEPS:
      dify-workflow edit add-node --help           → learn how to add a node
      dify-workflow create --help                  → create a workflow from template
    """
    if filter_type:
        matches = [t for t in NODE_TYPE_INFO if t[0] == filter_type]
        if not matches:
            click.echo(f"Error: Unknown node type '{filter_type}'. Run 'dify-workflow list-node-types' to see all.", err=True)
            sys.exit(1)
        name, desc, fields = matches[0]
        if json_output:
            output_json({"type": name, "description": desc, "key_fields": fields,
                          "usage": f'dify-workflow edit add-node -f workflow.yaml --type {name} --title "My {name.title()}"'})
        else:
            console.print(f"\n[bold]{name}[/bold] — {desc}")
            console.print(f"  Key fields: {fields}")
            console.print(f'  Usage: dify-workflow edit add-node -f workflow.yaml --type {name} --title "My {name.title()}"')
        return

    if json_output:
        output_json({
            "node_types": [{"type": t[0], "description": t[1], "key_fields": t[2]} for t in NODE_TYPE_INFO],
            "total": len(NODE_TYPE_INFO),
            "tip": "Use --type <name> for single node details, or pass type to 'edit add-node --type <name>'",
        })
        return

    table = Table(title="Supported Node Types (use with: edit add-node --type <type>)")
    table.add_column("Type", style="cyan", no_wrap=True)
    table.add_column("Description")
    table.add_column("Key Fields", style="dim")
    for name, desc, fields in NODE_TYPE_INFO:
        table.add_row(name, desc, fields)
    console.print(table)
    console.print("\n[dim]Tip: dify-workflow list-node-types --type llm  → show details for one type[/dim]")


# --- scan ---

@cli.command()
@click.option("--project-path", "-p", default=DIFY_TEST_DEFAULT,
              help="Path to dify-test project directory (default: ./dify-test)")
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON (machine-readable analysis)")
def scan(project_path: str, json_output: bool):
    """[DEPRECATED] Scan Dify source code to analyze workflow DSL generation chain.

    \b
    ⚠️  This command is deprecated and will be removed in a future version.

    \b
    EXAMPLES:
      dify-workflow scan                          → scan ./dify-test
      dify-workflow scan -p /path/to/dify-test    → scan custom path
    """
    import warnings
    warnings.warn(
        "'dify-workflow scan' is deprecated and will be removed in a future version.",
        DeprecationWarning,
        stacklevel=1,
    )
    click.echo(
        "\u26a0\ufe0f  Warning: 'dify-workflow scan' is deprecated and will be removed in a future version.",
        err=True,
    )
    try:
        result = scan_dify_project(project_path)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    if json_output:
        output_json(result)
        return

    console.print(f"\n[bold]Project Root:[/bold] {result['project_root']}\n")

    # Key files table
    table = Table(title="Key Workflow DSL Files")
    table.add_column("Component", style="cyan")
    table.add_column("Path")
    table.add_column("Exists", style="green")
    table.add_column("Size")

    for name, info in result["key_files"].items():
        exists = "✓" if info["exists"] else "✗"
        table.add_row(name, info["path"], exists, str(info["size"]))

    console.print(table)

    # Node directories
    if result["node_directories"]:
        console.print("\n[bold]Node Directories:[/bold]")
        for nd in result["node_directories"]:
            console.print(f"  {nd['path']}: {', '.join(nd['files'])}")

    # Test fixtures
    if result["test_fixtures"]:
        console.print(f"\n[bold]Test Fixtures:[/bold] {len(result['test_fixtures'])} found")
        for f in result["test_fixtures"][:10]:
            console.print(f"  {f}")

    # Generation chain
    console.print(f"\n{result['generation_chain']}")


# --- create ---

@cli.command()
@click.option("--name", "-n", default="", help="App name (auto-generated if empty)")
@click.option("--description", "-d", default="", help="App description text")
@click.option("--output", "-o", required=True, help="Output file path (.yaml or .json)")
@click.option("--mode", "app_mode", type=click.Choice(MODE_CHOICES), default="workflow",
              help=MODE_HELP)
@click.option("--template", "-t", default=None,
              help="Template: minimal|llm|if-else (workflow), chatflow|knowledge (chatflow)")
@click.option("--model-provider", default="openai",
              help="LLM model provider (e.g. openai, anthropic)")
@click.option("--model-name", default="gpt-4o",
              help="LLM model name (e.g. gpt-4o, claude-3-opus)")
@click.option("--system-prompt", default="You are a helpful assistant.",
              help="System prompt / pre_prompt")
@click.option("--json-output", "-j", is_flag=True, help="Output result as JSON")
def create(name: str, description: str, output: str, app_mode: str, template: str | None,
           model_provider: str, model_name: str, system_prompt: str, json_output: bool):
    """Create a new Dify app from a template (supports all 5 modes).

    \b
    MODES:
      workflow     Visual node-based workflow: Start → ... → End (default)
      chatflow     Visual workflow with conversation: Start → ... → Answer
      chat         Simple chatbot with model_config (no graph)
      agent        Chat with tool-calling (function_call/react)
      completion   Single-turn text generation (no conversation)

    \b
    WORKFLOW TEMPLATES (--mode workflow):
      minimal   → Start → End (2 nodes, 1 edge)
      llm       → Start → LLM → End (3 nodes, 2 edges)
      if-else   → Start → IF/ELSE → End True / End False (4 nodes, 3 edges)

    \b
    CHATFLOW TEMPLATES (--mode chatflow):
      chatflow     → Start → LLM → Answer (3 nodes, 2 edges, memory enabled)
      knowledge    → Start → Knowledge Retrieval → LLM → Answer (4 nodes, 3 edges)

    \b
    EXAMPLES:
      dify-workflow create -o my.yaml                                → minimal workflow
      dify-workflow create --mode workflow --template llm -o wf.yaml → LLM workflow
      dify-workflow create --mode chatflow -o chat.yaml              → chatflow
      dify-workflow create --mode chat --name "My Bot" -o bot.yaml   → chat app
      dify-workflow create --mode agent -o agent.yaml                → agent app
      dify-workflow create --mode completion -o gen.yaml              → text generator

    \b
    NEXT STEPS after creating:
      dify-workflow inspect my.yaml          → view the structure
      dify-workflow validate my.yaml         → check it's valid
      dify-workflow edit --help              → edit nodes/edges (workflow/chatflow)
      dify-workflow config --help            → edit model config (chat/agent/completion)
    """
    dsl = _create_by_mode(
        app_mode, template, name, description,
        model_provider, model_name, system_prompt,
    )

    path = save_workflow(dsl, output)

    if json_output:
        info: dict = {"status": "created", "path": str(path), "mode": dsl.app.mode.value}
        if dsl.is_workflow_based:
            info["nodes"] = len(dsl.workflow.graph.nodes)
            info["edges"] = len(dsl.workflow.graph.edges)
        output_json(info)
    else:
        console.print(f"[green]✓[/green] Created {dsl.app.mode.value} app: {path}")
        if dsl.is_workflow_based:
            console.print(f"  Nodes: {len(dsl.workflow.graph.nodes)}, Edges: {len(dsl.workflow.graph.edges)}")


def _create_by_mode(app_mode, template, name, description, model_provider, model_name, system_prompt):
    """Dispatch creation to the right mode module."""
    if app_mode == "workflow":
        from .workflow.editor import create_ifelse_workflow, create_llm_workflow, create_minimal_workflow
        template = template or "minimal"
        default_name = name or "Untitled Workflow"
        if template == "llm":
            return create_llm_workflow(
                name=default_name, description=description,
                model_provider=model_provider, model_name=model_name,
                system_prompt=system_prompt,
            )
        elif template == "if-else":
            return create_ifelse_workflow(name=default_name, description=description)
        else:
            return create_minimal_workflow(name=default_name, description=description)

    elif app_mode == "chatflow":
        from .chatflow.editor import create_chatflow, create_knowledge_chatflow
        default_name = name or "Chatflow"
        if template == "knowledge":
            return create_knowledge_chatflow(
                name=default_name, description=description,
                model_provider=model_provider, model_name=model_name,
                system_prompt=system_prompt,
            )
        else:
            return create_chatflow(
                name=default_name, description=description,
                model_provider=model_provider, model_name=model_name,
                system_prompt=system_prompt,
            )

    elif app_mode == "chat":
        from .chat.editor import create_chat_app
        return create_chat_app(
            name=name or "Chat App", description=description,
            model_provider=model_provider, model_name=model_name,
            pre_prompt=system_prompt,
        )

    elif app_mode == "agent":
        from .agent.editor import create_agent_app
        return create_agent_app(
            name=name or "Agent App", description=description,
            model_provider=model_provider, model_name=model_name,
            pre_prompt=system_prompt,
        )

    elif app_mode == "completion":
        from .completion.editor import create_completion_app
        return create_completion_app(
            name=name or "Text Generator", description=description,
            model_provider=model_provider, model_name=model_name,
            pre_prompt=system_prompt if system_prompt != "You are a helpful assistant." else "{{query}}",
        )


# --- Register subcommands from split modules ---

from .cli_edit import edit  # noqa: E402
from .cli_config import config  # noqa: E402
from .cli_ops import validate, checklist, export, import_cmd, diff, layout  # noqa: E402
from .cli_inspect import inspect  # noqa: E402

cli.add_command(edit)
cli.add_command(config)
cli.add_command(validate)
cli.add_command(checklist)
cli.add_command(export)
cli.add_command(inspect)
cli.add_command(import_cmd, "import")
cli.add_command(diff)
cli.add_command(layout)


if __name__ == "__main__":
    cli()
