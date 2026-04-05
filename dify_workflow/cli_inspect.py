"""CLI inspect command — view workflow structure as tree, JSON, or Mermaid."""

from __future__ import annotations

import click
from rich.tree import Tree

from .cli_shared import console, output_json
from .editor import get_node
from .io import load_workflow
from .mermaid import generate_mermaid
from .models import DifyDSL, NodeType


@click.command()
@click.argument("file")
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON (structured node/edge list)")
@click.option("--mermaid", "-m", is_flag=True, help="Output as Mermaid flowchart (for AI analysis and Markdown rendering)")
def inspect(file: str, json_output: bool, mermaid: bool):
    """Inspect the structure of a workflow file: nodes, edges, variables.

    \b
    OUTPUT FORMATS:
      (default)  Rich tree showing nodes, edges, variables, and model info.
      -j         Machine-readable JSON with app info, nodes, and edges.
      -m         Mermaid flowchart for visual node connection analysis.

    \b
    MERMAID OUTPUT:
      Generates standard Mermaid flowchart syntax. Each node shows
      "title (type)". Branch conditions (IF/ELSE case_id, classifier
      class id) are annotated on edges. Paste into any Markdown renderer.

    \b
    EXAMPLES:
      dify-workflow inspect my.yaml            → tree view
      dify-workflow inspect my.yaml -j         → JSON (use to find node/edge IDs)
      dify-workflow inspect my.yaml --mermaid   → Mermaid flowchart
      dify-workflow inspect my.yaml -m         → same, short flag

    \b
    NEXT STEPS:
      dify-workflow edit --help            → edit nodes/edges using the IDs
      dify-workflow validate my.yaml       → check for errors
    """
    dsl = load_workflow(file)

    if mermaid:
        click.echo(generate_mermaid(dsl))
        return

    if json_output:
        info: dict = {
            "app": dsl.app.model_dump(),
            "version": dsl.version,
        }
        if dsl.is_workflow_based:
            graph = dsl.workflow.graph
            info.update({
                "node_count": len(graph.nodes),
                "edge_count": len(graph.edges),
                "nodes": [
                    {"id": n.id, "type": n.data.type.value, "title": n.data.title}
                    for n in graph.nodes
                ],
                "edges": [
                    {"id": e.id, "source": e.source, "target": e.target}
                    for e in graph.edges
                ],
                "environment_variables": len(dsl.workflow.environment_variables),
            })
        elif dsl.model_config_content:
            mc = dsl.model_config_content
            info.update({
                "model": mc.model,
                "pre_prompt": mc.pre_prompt[:200] + ("..." if len(mc.pre_prompt) > 200 else ""),
                "user_input_form": mc.user_input_form,
                "agent_mode": mc.agent_mode,
                "opening_statement": mc.opening_statement,
            })
        output_json(info)
        return

    # Rich tree output
    console.print(f"\n[bold]{dsl.app.name}[/bold] ({dsl.app.mode})")
    console.print(f"  Version: {dsl.version}, Kind: {dsl.kind}")
    if dsl.app.description:
        console.print(f"  Description: {dsl.app.description}")

    if dsl.is_workflow_based:
        _inspect_workflow_tree(dsl)
    elif dsl.model_config_content:
        _inspect_config_tree(dsl)
    else:
        console.print("[yellow]No workflow graph or model_config found[/yellow]")


def _inspect_workflow_tree(dsl: DifyDSL) -> None:
    """Print workflow graph as a rich tree."""
    graph = dsl.workflow.graph
    tree = Tree("[bold]Workflow Graph[/bold]")

    nodes_branch = tree.add(f"[cyan]Nodes[/cyan] ({len(graph.nodes)})")
    for node in graph.nodes:
        label = f"[{node.id}] {node.data.title} (type={node.data.type.value})"
        node_branch = nodes_branch.add(label)
        if node.data.type == NodeType.START and node.data.variables:
            for v in node.data.variables:
                node_branch.add(f"var: {v.variable} ({v.type})")
        if node.data.type == NodeType.END and node.data.outputs:
            for o in node.data.outputs:
                node_branch.add(f"out: {o.variable} ← {'.'.join(o.value_selector)}")
        if node.data.type == NodeType.ANSWER:
            answer_text = (node.data.__pydantic_extra__ or {}).get("answer", "")
            if answer_text:
                node_branch.add(f"answer: {answer_text[:80]}")
        if node.data.type == NodeType.LLM and node.data.model:
            node_branch.add(f"model: {node.data.model.provider}/{node.data.model.name}")

    edges_branch = tree.add(f"[cyan]Edges[/cyan] ({len(graph.edges)})")
    for edge in graph.edges:
        src_node = get_node(dsl, edge.source)
        tgt_node = get_node(dsl, edge.target)
        src_name = src_node.data.title if src_node else edge.source
        tgt_name = tgt_node.data.title if tgt_node else edge.target
        edges_branch.add(f"{src_name} → {tgt_name}")

    if dsl.workflow.environment_variables:
        env_branch = tree.add(f"[cyan]Environment Variables[/cyan] ({len(dsl.workflow.environment_variables)})")
        for ev in dsl.workflow.environment_variables:
            env_branch.add(f"{ev.name} = {ev.value}")

    console.print(tree)


def _inspect_config_tree(dsl: DifyDSL) -> None:
    """Print model_config as a rich tree."""
    mc = dsl.model_config_content
    tree = Tree("[bold]Model Config[/bold]")

    # Model info
    model = mc.model
    provider = model.get("provider", "?")
    name = model.get("name", "?")
    tree.add(f"[cyan]Model[/cyan]: {provider}/{name}")

    # Prompt
    if mc.pre_prompt:
        prompt_preview = mc.pre_prompt[:120].replace("\n", "\\n")
        if len(mc.pre_prompt) > 120:
            prompt_preview += "..."
        tree.add(f"[cyan]Prompt[/cyan]: {prompt_preview}")

    # User input form
    if mc.user_input_form:
        form_branch = tree.add(f"[cyan]Input Variables[/cyan] ({len(mc.user_input_form)})")
        for item in mc.user_input_form:
            for var_type, var_config in item.items():
                vname = var_config.get("variable", "?")
                vlabel = var_config.get("label", vname)
                form_branch.add(f"{vname} ({var_type}) — {vlabel}")

    # Agent mode
    agent_mode = mc.agent_mode
    if isinstance(agent_mode, dict) and agent_mode.get("enabled"):
        strategy = agent_mode.get("strategy", "?")
        tools = agent_mode.get("tools", [])
        agent_branch = tree.add(f"[cyan]Agent[/cyan]: {strategy} ({len(tools)} tools)")
        for tool in tools:
            tool_name = tool.get("tool_name", "?")
            provider_id = tool.get("provider_id", "?")
            agent_branch.add(f"{provider_id}/{tool_name}")

    # Features
    features = []
    if mc.opening_statement:
        features.append("opening_statement")
    if mc.suggested_questions:
        features.append(f"suggested_questions ({len(mc.suggested_questions)})")
    if isinstance(mc.more_like_this, dict) and mc.more_like_this.get("enabled"):
        features.append("more_like_this")
    if isinstance(mc.speech_to_text, dict) and mc.speech_to_text.get("enabled"):
        features.append("speech_to_text")
    if isinstance(mc.retriever_resource, dict) and mc.retriever_resource.get("enabled"):
        features.append("retriever_resource")
    if features:
        tree.add(f"[cyan]Features[/cyan]: {', '.join(features)}")

    console.print(tree)
