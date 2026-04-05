"""CLI edit subcommands — workflow graph node/edge operations."""

from __future__ import annotations

import json
import sys

import click

from .cli_shared import OrderedGroup, check_node_errors, console, output_json, NODE_TYPES_STR
from .editor import (
    add_edge,
    add_node,
    remove_edge,
    remove_node,
    set_node_title,
    update_node,
)
from .io import load_workflow, save_workflow


@click.group(cls=OrderedGroup)
def edit():
    """Edit an existing workflow (nodes and edges).

    \b
    SUBCOMMANDS:
      add-node      Add a new node to the workflow
      remove-node   Remove a node (and its connected edges)
      update-node   Update a node's data fields via JSON
      add-edge      Connect two nodes with an edge
      remove-edge   Remove an edge by ID
      set-title     Change a node's display title

    \b
    TYPICAL WORKFLOW:
      1. dify-workflow inspect my.yaml                → see current nodes/edges
      2. dify-workflow edit add-node --help            → learn add-node options
      3. dify-workflow edit add-node -f my.yaml --type code --title "Process"
      4. dify-workflow edit add-edge -f my.yaml --source start_node --target <new_id>
      5. dify-workflow validate my.yaml               → verify changes

    \b
    DISCOVERY:
      dify-workflow list-node-types               → see all available --type values
      dify-workflow edit <subcommand> --help       → detailed help per subcommand
    """
    pass


@edit.command("add-node")
@click.option("--file", "-f", required=True, help="Workflow file path to edit")
@click.option("--type", "node_type", required=True,
              help=f"Node type. Allowed values: {NODE_TYPES_STR}")
@click.option("--title", "-t", default="", help="Node display title (auto-generated from type if empty)")
@click.option("--id", "node_id", default=None, help="Custom node ID (auto-generated timestamp if empty)")
@click.option("--data", "-d", default=None,
              help='Node data overrides as JSON string, e.g. \'{"model": {"provider": "openai"}}\'')
@click.option("--data-file", "data_file", default=None, type=click.Path(exists=True),
              help="Read node data overrides from a JSON file (avoids shell escaping issues)")
@click.option("--json-output", "-j", is_flag=True, help="Output result as JSON")
def edit_add_node(file: str, node_type: str, title: str, node_id: str | None,
                  data: str | None, data_file: str | None, json_output: bool):
    """Add a node to an existing workflow.

    \b
    EXAMPLES:
      dify-workflow edit add-node -f wf.yaml --type code --title "Process"
      dify-workflow edit add-node -f wf.yaml --type llm --id my_llm \\
          -d '{"model": {"provider": "openai", "name": "gpt-4"}}'
      dify-workflow edit add-node -f wf.yaml --type llm --id my_llm \\
          --data-file node_config.json
      dify-workflow edit add-node -f wf.yaml --type end --title "Done" -j

    \b
    DISCOVER NODE TYPES:
      dify-workflow list-node-types                → see all 22 types
      dify-workflow list-node-types --type llm     → LLM node details

    \b
    NEXT STEPS:
      dify-workflow edit add-edge -f wf.yaml --source <src> --target <new_id>
      dify-workflow inspect wf.yaml -j             → verify the new node
    """
    dsl = load_workflow(file)
    if data_file:
        with open(data_file, encoding="utf-8") as f:
            overrides = json.load(f)
    else:
        overrides = json.loads(data) if data else None
    node = add_node(dsl, node_type, title=title, node_id=node_id, data_overrides=overrides)
    check_node_errors(node, action="add")
    save_workflow(dsl, file)

    if json_output:
        output_json({"status": "added", "node_id": node.id, "type": node_type})
    else:
        console.print(f"[green]✓[/green] Added node: {node.id} (type={node_type})")


@edit.command("remove-node")
@click.option("--file", "-f", required=True, help="Workflow file path to edit")
@click.option("--id", "node_id", required=True, help="Node ID to remove (find IDs via 'inspect -j')")
@click.option("--json-output", "-j", is_flag=True, help="Output result as JSON")
def edit_remove_node(file: str, node_id: str, json_output: bool):
    """Remove a node and all its connected edges from a workflow.

    \b
    EXAMPLES:
      dify-workflow edit remove-node -f wf.yaml --id code_node
      dify-workflow edit remove-node -f wf.yaml --id llm_node -j

    \b
    FIND NODE IDS:
      dify-workflow inspect wf.yaml -j    → shows all node IDs and types
    """
    dsl = load_workflow(file)
    removed = remove_node(dsl, node_id)
    if not removed:
        click.echo(f"Error: Node '{node_id}' not found", err=True)
        sys.exit(1)
    save_workflow(dsl, file)

    if json_output:
        output_json({"status": "removed", "node_id": node_id})
    else:
        console.print(f"[green]✓[/green] Removed node: {node_id}")


@edit.command("update-node")
@click.option("--file", "-f", required=True, help="Workflow file path to edit")
@click.option("--id", "node_id", required=True, help="Node ID to update (find IDs via 'inspect -j')")
@click.option("--data", "-d", default=None,
              help='Updates as JSON string, e.g. \'{"title": "New Name", "model": {"name": "gpt-4"}}\'')
@click.option("--data-file", "data_file", default=None, type=click.Path(exists=True),
              help="Read JSON updates from a file (avoids shell escaping issues)")
@click.option("--json-output", "-j", is_flag=True, help="Output result as JSON")
def edit_update_node(file: str, node_id: str, data: str | None, data_file: str | None, json_output: bool):
    """Update a node's data fields with a JSON patch.

    \b
    EXAMPLES:
      dify-workflow edit update-node -f wf.yaml --id llm_node \\
          -d '{"title": "GPT-4", "model": {"provider": "openai", "name": "gpt-4"}}'
      dify-workflow edit update-node -f wf.yaml --id llm_node \\
          --data-file patch.json

    \b
    FIND NODE IDS & FIELDS:
      dify-workflow inspect wf.yaml -j             → node IDs and types
      dify-workflow list-node-types --type llm      → LLM node key fields
    """
    if data_file:
        with open(data_file, encoding="utf-8") as f:
            updates = json.load(f)
    elif data:
        updates = json.loads(data)
    else:
        click.echo("Error: Provide either --data or --data-file", err=True)
        sys.exit(1)
    dsl = load_workflow(file)
    node = update_node(dsl, node_id, updates)
    if node is None:
        click.echo(f"Error: Node '{node_id}' not found", err=True)
        sys.exit(1)
    check_node_errors(node, action="update")
    save_workflow(dsl, file)

    if json_output:
        output_json({"status": "updated", "node_id": node_id})
    else:
        console.print(f"[green]✓[/green] Updated node: {node_id}")


@edit.command("add-edge")
@click.option("--file", "-f", required=True, help="Workflow file path to edit")
@click.option("--source", "-s", required=True, help="Source node ID (edge starts here)")
@click.option("--target", "-t", required=True, help="Target node ID (edge points here)")
@click.option("--source-handle", default="source",
              help="Source handle name. Default: 'source'. For if-else: 'true' or 'false'")
@click.option("--target-handle", default="target", help="Target handle name. Default: 'target'")
@click.option("--json-output", "-j", is_flag=True, help="Output result as JSON")
def edit_add_edge(file: str, source: str, target: str, source_handle: str,
                  target_handle: str, json_output: bool):
    """Add an edge (connection) between two nodes.

    \b
    EXAMPLES:
      dify-workflow edit add-edge -f wf.yaml --source start_node --target llm_node
      dify-workflow edit add-edge -f wf.yaml -s ifelse_node -t end_true \\
          --source-handle true
      dify-workflow edit add-edge -f wf.yaml -s ifelse_node -t end_false \\
          --source-handle false

    \b
    NOTES:
      • Both source and target nodes must already exist in the workflow
      • For if-else nodes, use --source-handle true/false to specify the branch
      • Edge ID is auto-generated as: {source}-{sourceHandle}-{target}-{targetHandle}

    \b
    FIND NODE IDS:
      dify-workflow inspect wf.yaml -j    → shows all node IDs
    """
    dsl = load_workflow(file)
    edge = add_edge(dsl, source, target, source_handle=source_handle, target_handle=target_handle)
    if edge is None:
        click.echo("Error: Source or target node not found", err=True)
        sys.exit(1)
    save_workflow(dsl, file)

    if json_output:
        output_json({"status": "added", "edge_id": edge.id})
    else:
        console.print(f"[green]✓[/green] Added edge: {source} → {target}")


@edit.command("remove-edge")
@click.option("--file", "-f", required=True, help="Workflow file path to edit")
@click.option("--id", "edge_id", required=True,
              help="Edge ID to remove (find IDs via 'inspect -j' → edges[].id)")
@click.option("--json-output", "-j", is_flag=True, help="Output result as JSON")
def edit_remove_edge(file: str, edge_id: str, json_output: bool):
    """Remove an edge from a workflow by its ID.

    \b
    EXAMPLES:
      dify-workflow edit remove-edge -f wf.yaml --id "start_node-source-llm_node-target"

    \b
    FIND EDGE IDS:
      dify-workflow inspect wf.yaml -j    → edges[].id shows all edge IDs
    """
    dsl = load_workflow(file)
    removed = remove_edge(dsl, edge_id)
    if not removed:
        click.echo(f"Error: Edge '{edge_id}' not found", err=True)
        sys.exit(1)
    save_workflow(dsl, file)

    if json_output:
        output_json({"status": "removed", "edge_id": edge_id})
    else:
        console.print(f"[green]✓[/green] Removed edge: {edge_id}")


@edit.command("set-title")
@click.option("--file", "-f", required=True, help="Workflow file path to edit")
@click.option("--id", "node_id", required=True, help="Node ID (find via 'inspect -j')")
@click.option("--title", "-t", required=True, help="New display title for the node")
def edit_set_title(file: str, node_id: str, title: str):
    """Set a node's display title.

    \b
    EXAMPLES:
      dify-workflow edit set-title -f wf.yaml --id start_node --title "User Input"
      dify-workflow edit set-title -f wf.yaml --id llm_node -t "GPT-4 Processor"
    """
    dsl = load_workflow(file)
    if not set_node_title(dsl, node_id, title):
        click.echo(f"Error: Node '{node_id}' not found", err=True)
        sys.exit(1)
    save_workflow(dsl, file)
    console.print(f"[green]✓[/green] Set title of {node_id} to '{title}'")
