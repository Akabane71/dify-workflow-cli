"""CLI operational commands — validate, checklist, export, import, diff, layout."""

from __future__ import annotations

import sys

import click

from .cli_shared import console, output_json
from .io import load_workflow, save_workflow, workflow_to_string
from .models import DifyDSL, NodeType
from .validator import validate_workflow


# --- validate ---

@click.command()
@click.argument("file")
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON (structured validation report)")
@click.option("--strict", is_flag=True, help="Treat warnings as errors (exit code 1 if any warning)")
def validate(file: str, json_output: bool, strict: bool):
    """Validate a workflow DSL file for errors and warnings.

    \b
    CHECKS PERFORMED:
      • Top-level: version, kind, app.name, app.mode present
      • Graph: nodes exist, IDs unique, has start node
      • Rules: start and trigger nodes cannot coexist
      • Nodes: LLM needs model config, no duplicate start variables
      • Edges: endpoints exist, no self-loops
      • Connectivity: all nodes reachable from start

    \b
    EXIT CODES:
      0  → valid (may have warnings)
      1  → has errors (or warnings in --strict mode)

    \b
    EXAMPLES:
      dify-workflow validate my.yaml
      dify-workflow validate my.yaml -j          → JSON report
      dify-workflow validate my.yaml --strict     → warnings = errors

    \b
    NEXT STEPS:
      dify-workflow inspect my.yaml   → see the structure visually
      dify-workflow export my.yaml    → export if valid
    """
    try:
        dsl = load_workflow(file)
    except Exception as e:
        if json_output:
            output_json({"valid": False, "error_count": 1, "errors": [{"level": "error", "message": str(e)}]})
        else:
            console.print(f"[red]✗[/red] Failed to parse: {e}")
        sys.exit(1)

    result = validate_workflow(dsl)

    if strict:
        if any(e.level == "warning" for e in result.errors):
            result.valid = False

    if json_output:
        output_json(result.to_dict())
    else:
        if result.valid:
            console.print(f"[green]✓[/green] Workflow is valid")
        else:
            console.print(f"[red]✗[/red] Workflow has errors")

        for err in result.errors:
            color = "red" if err.level == "error" else "yellow"
            node_info = f" (node: {err.node_id})" if err.node_id else ""
            console.print(f"  [{color}]{err.level}[/{color}]: {err.message}{node_info}")

    if not result.valid:
        sys.exit(1)


# --- checklist ---

@click.command()
@click.argument("file")
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON")
def checklist(file: str, json_output: bool):
    """Run Dify pre-publish checklist validation.

    \b
    Mirrors the Dify frontend "检查清单" panel that shows all issues
    blocking workflow publishing. Covers two layers:

    \b
    LAYER 1 — Node Configuration Completeness:
      • End: outputs + value_selector required
      • LLM: model provider, prompt_template
      • Code: variables, value_selector, code body
      • IF/ELSE: conditions, variable_selector, operator, value
      • Question Classifier: model, query_variable, classes with names
      • Knowledge Retrieval: dataset_ids
      • HTTP Request: url
      • Template Transform: variables, template
      • Iteration: iterator_selector
      • And more…

    \b
    LAYER 2 — Variable Reference Validation:
      • All value_selector paths reference existing nodes
      • Referenced node has the expected output variable
      • Skips special prefixes: sys, env, conversation, rag

    \b
    EXIT CODES:
      0  → no checklist issues
      1  → has issues blocking publishing

    \b
    EXAMPLES:
      dify-workflow checklist workflow.yaml
      dify-workflow checklist workflow.yaml -j   → JSON report

    \b
    NEXT STEPS:
      dify-workflow validate workflow.yaml  → full structural validation
      dify-workflow inspect workflow.yaml   → see workflow structure
    """
    try:
        dsl = load_workflow(file)
    except Exception as e:
        if json_output:
            output_json({"issue_count": 0, "issues": [], "error": str(e)})
        else:
            console.print(f"[red]✗[/red] Failed to parse: {e}")
        sys.exit(1)

    from .checklist_validator import validate_checklist
    errors = validate_checklist(dsl)

    if json_output:
        issues = [
            {"level": e.level, "message": e.message, "node_id": e.node_id, "node_title": e.node_title, "field": e.field}
            for e in errors
        ]
        output_json({"issue_count": len(issues), "issues": issues})
    else:
        if not errors:
            console.print(f"[green]✓[/green] Checklist passed — no issues found")
        else:
            console.print(f"[red]✗[/red] Checklist: {len(errors)} issue(s) found")
            for e in errors:
                node_label = e.node_title or e.node_id
                if node_label:
                    console.print(f"  [red]•[/red] [{node_label}] {e.message}")
                else:
                    console.print(f"  [red]•[/red] {e.message}")

    if errors:
        sys.exit(1)


# --- export ---

@click.command()
@click.argument("file")
@click.option("--output", "-o", default=None,
              help="Output file path. If omitted, prints to stdout.")
@click.option("--format", "fmt", type=click.Choice(["yaml", "json"]), default="yaml",
              help="Output format: yaml (default) or json")
def export(file: str, output: str | None, fmt: str):
    """Export a workflow to YAML or JSON format.

    \b
    EXAMPLES:
      dify-workflow export my.yaml                          → print YAML to stdout
      dify-workflow export my.yaml --output final.yaml      → save as YAML file
      dify-workflow export my.yaml -o out.json --format json → save as JSON file

    \b
    NOTES:
      • The exported file uses Dify DSL v0.6.0 format
      • Output can be imported back with 'dify-workflow import'
    """
    dsl = load_workflow(file)

    if output:
        path = save_workflow(dsl, output, fmt=fmt)
        console.print(f"[green]✓[/green] Exported to: {path}")
    else:
        click.echo(workflow_to_string(dsl, fmt=fmt))


# --- import (load and re-export) ---

@click.command("import")
@click.argument("file")
@click.option("--output", "-o", required=True, help="Output file path for the re-exported workflow")
@click.option("--format", "fmt", type=click.Choice(["yaml", "json"]), default="yaml",
              help="Output format: yaml (default) or json")
@click.option("--validate-only", is_flag=True, help="Only validate the file without saving")
def import_cmd(file: str, output: str, fmt: str, validate_only: bool):
    """Import a workflow file, validate it, and re-export.

    \b
    Use this to:
      • Validate a workflow from an external source
      • Convert between YAML and JSON formats
      • Normalize a workflow file (re-serialize with clean structure)

    \b
    EXAMPLES:
      dify-workflow import external.yaml --output local.yaml
      dify-workflow import old.yaml -o new.json --format json    → convert to JSON
      dify-workflow import untrusted.yaml -o /dev/null --validate-only
    """
    dsl = load_workflow(file)
    result = validate_workflow(dsl)

    if not result.valid:
        console.print("[red]✗[/red] Import validation failed:")
        for err in result.errors:
            console.print(f"  {err.level}: {err.message}")
        sys.exit(1)

    if validate_only:
        console.print("[green]✓[/green] Workflow is valid for import")
        return

    path = save_workflow(dsl, output, fmt=fmt)
    console.print(f"[green]✓[/green] Imported and saved to: {path}")


# --- diff ---

@click.command()
@click.argument("file1")
@click.argument("file2")
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON (structured diff list)")
def diff(file1: str, file2: str, json_output: bool):
    """Compare two workflow files and show differences.

    \b
    Compares: app name/mode, nodes (added/removed/changed), edges (added/removed).

    \b
    EXAMPLES:
      dify-workflow diff before.yaml after.yaml         → human-readable diff
      dify-workflow diff original.yaml modified.yaml -j  → JSON diff for scripts
    """
    dsl1 = load_workflow(file1)
    dsl2 = load_workflow(file2)

    diffs: list[dict[str, str]] = []

    # Compare app info
    if dsl1.app.name != dsl2.app.name:
        diffs.append({"field": "app.name", "before": dsl1.app.name, "after": dsl2.app.name})
    if dsl1.app.mode != dsl2.app.mode:
        diffs.append({"field": "app.mode", "before": dsl1.app.mode, "after": dsl2.app.mode})

    # Compare nodes
    nodes1 = {n.id: n for n in dsl1.workflow.graph.nodes}
    nodes2 = {n.id: n for n in dsl2.workflow.graph.nodes}

    for nid in nodes1.keys() - nodes2.keys():
        diffs.append({"field": f"node.{nid}", "before": f"type={nodes1[nid].data.type}", "after": "(removed)"})
    for nid in nodes2.keys() - nodes1.keys():
        diffs.append({"field": f"node.{nid}", "before": "(absent)", "after": f"type={nodes2[nid].data.type}"})
    for nid in nodes1.keys() & nodes2.keys():
        n1, n2 = nodes1[nid], nodes2[nid]
        if n1.data.title != n2.data.title:
            diffs.append({"field": f"node.{nid}.title", "before": n1.data.title, "after": n2.data.title})
        if n1.data.type != n2.data.type:
            diffs.append({"field": f"node.{nid}.type", "before": n1.data.type, "after": n2.data.type})

    # Compare edges
    edges1 = {e.id for e in dsl1.workflow.graph.edges}
    edges2 = {e.id for e in dsl2.workflow.graph.edges}
    for eid in edges1 - edges2:
        diffs.append({"field": f"edge.{eid}", "before": "exists", "after": "(removed)"})
    for eid in edges2 - edges1:
        diffs.append({"field": f"edge.{eid}", "before": "(absent)", "after": "added"})

    if json_output:
        output_json({"diff_count": len(diffs), "diffs": diffs})
    else:
        if not diffs:
            console.print("[green]✓[/green] No differences found")
        else:
            console.print(f"[yellow]Found {len(diffs)} difference(s):[/yellow]")
            for d in diffs:
                console.print(f"  {d['field']}: {d['before']} → {d['after']}")


# --- layout ---

@click.command()
@click.option("-f", "--file", required=True, help="Input workflow YAML/JSON file")
@click.option("-o", "--output", default=None, help="Output file (default: overwrite input file)")
@click.option(
    "-s", "--strategy",
    type=click.Choice(["tree", "linear", "hierarchical", "vertical", "compact"]),
    default="tree",
    help="Layout strategy (default: tree)",
)
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON (position map)")
def layout(file: str, output: str | None, strategy: str, json_output: bool):
    """Auto-layout workflow nodes with smart positioning.

    \b
    STRATEGIES:
      tree         — branch-grouped tree layout, left-to-right (default)
      linear       — all nodes in a single horizontal line
      hierarchical — DAG layered layout, left-to-right
      vertical     — DAG layered layout, top-to-bottom
      compact      — tighter hierarchical with reduced spacing

    \b
    EXAMPLES:
      dify-workflow layout -f my.yaml                        → tree layout (overwrite)
      dify-workflow layout -f my.yaml -s hierarchical        → layered DAG layout
      dify-workflow layout -f my.yaml -s compact -o out.yaml → compact, save to new file
      dify-workflow layout -f my.yaml -j                     → output position map as JSON
    """
    from .layout import auto_layout

    dsl = load_workflow(file)
    positions = auto_layout(dsl, strategy=strategy)  # type: ignore[arg-type]

    if json_output:
        pos_map = {nid: {"x": round(x, 1), "y": round(y, 1)} for nid, (x, y) in positions.items()}
        output_json({
            "strategy": strategy,
            "node_count": len(positions),
            "positions": pos_map,
        })
    else:
        out_path = save_workflow(dsl, output or file)
        console.print(f"[green]✓[/green] Layout applied ({strategy}): {len(positions)} nodes repositioned")
        console.print(f"  Saved to: {out_path}")
