"""CLI config subcommands — model config for chat/agent/completion apps."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from .cli_shared import OrderedGroup, console, output_json
from .io import load_workflow, save_workflow


@click.group(cls=OrderedGroup)
def config():
    """Edit model config for chat, agent, and completion apps.

    \b
    These commands modify the model_config section (not the workflow graph).
    Use for apps with mode: chat, agent-chat, or completion.

    \b
    SUBCOMMANDS:
      set-model       Set the LLM model and parameters
      set-prompt      Set the system prompt (pre_prompt)
      add-variable    Add a user input variable
      set-opening     Set the opening statement
      add-question    Add a suggested question
      add-tool        Add an agent tool (agent mode only)
      remove-tool     Remove an agent tool by name

    \b
    EXAMPLES:
      dify-workflow config set-model -f app.yaml --provider openai --name gpt-4o
      dify-workflow config set-prompt -f app.yaml --text "You are helpful."
      dify-workflow config add-variable -f app.yaml --name query --type paragraph
      dify-workflow config add-tool -f app.yaml --provider calculator --tool calculate

    \b
    DISCOVERY:
      dify-workflow inspect app.yaml       → see current model config
      dify-workflow validate app.yaml      → check for errors
    """
    pass


@config.command("set-model")
@click.option("--file", "-f", required=True, help="App file path to edit")
@click.option("--provider", required=True, help="Model provider (e.g. openai, anthropic)")
@click.option("--name", required=True, help="Model name (e.g. gpt-4o, claude-3-opus)")
@click.option("--temperature", type=float, default=None, help="Sampling temperature")
@click.option("--max-tokens", type=int, default=None, help="Max output tokens")
@click.option("--json-output", "-j", is_flag=True, help="Output result as JSON")
def config_set_model(file: str, provider: str, name: str, temperature: float | None,
                     max_tokens: int | None, json_output: bool):
    """Set the LLM model for a chat/agent/completion app.

    \b
    EXAMPLES:
      dify-workflow config set-model -f app.yaml --provider openai --name gpt-4o
      dify-workflow config set-model -f app.yaml --provider anthropic --name claude-3-opus --temperature 0.3
    """
    from .chat.editor import set_model
    dsl = load_workflow(file)
    params = {}
    if temperature is not None:
        params["temperature"] = temperature
    if max_tokens is not None:
        params["max_tokens"] = max_tokens
    set_model(dsl, provider, name, **(params or {"temperature": 0.7}))
    save_workflow(dsl, file)
    if json_output:
        output_json({"status": "updated", "model": f"{provider}/{name}"})
    else:
        console.print(f"[green]✓[/green] Model set to {provider}/{name}")


@config.command("set-prompt")
@click.option("--file", "-f", required=True, help="App file path to edit")
@click.option("--text", default=None, help="System prompt text (pre_prompt)")
@click.option("--data-file", "data_file", default=None, type=click.Path(exists=True),
              help="Read prompt from a text file")
@click.option("--json-output", "-j", is_flag=True, help="Output result as JSON")
def config_set_prompt(file: str, text: str | None, data_file: str | None, json_output: bool):
    """Set the system prompt (pre_prompt) for a chat/agent/completion app.

    \b
    EXAMPLES:
      dify-workflow config set-prompt -f app.yaml --text "You are a helpful assistant."
      dify-workflow config set-prompt -f app.yaml --data-file prompt.txt
    """
    from .chat.editor import set_prompt
    if data_file:
        prompt = Path(data_file).read_text(encoding="utf-8")
    elif text:
        prompt = text
    else:
        click.echo("Error: Provide either --text or --data-file", err=True)
        sys.exit(1)
    dsl = load_workflow(file)
    set_prompt(dsl, prompt)
    save_workflow(dsl, file)
    if json_output:
        output_json({"status": "updated", "prompt_length": len(prompt)})
    else:
        console.print(f"[green]✓[/green] Prompt set ({len(prompt)} chars)")


@config.command("add-variable")
@click.option("--file", "-f", required=True, help="App file path to edit")
@click.option("--name", required=True, help="Variable name")
@click.option("--label", default="", help="Display label (defaults to name)")
@click.option("--type", "var_type", default="paragraph",
              help="Variable type: text-input, paragraph, select, number")
@click.option("--required/--optional", default=True, help="Whether the variable is required")
@click.option("--json-output", "-j", is_flag=True, help="Output result as JSON")
def config_add_variable(file: str, name: str, label: str, var_type: str,
                        required: bool, json_output: bool):
    """Add a user input variable to the app's input form.

    \b
    EXAMPLES:
      dify-workflow config add-variable -f app.yaml --name query --type paragraph
      dify-workflow config add-variable -f app.yaml --name topic --label "Topic" --type text-input
    """
    from .chat.editor import add_user_variable
    dsl = load_workflow(file)
    add_user_variable(dsl, name, label=label or name, var_type=var_type, required=required)
    save_workflow(dsl, file)
    if json_output:
        output_json({"status": "added", "variable": name, "type": var_type})
    else:
        console.print(f"[green]✓[/green] Added variable: {name} ({var_type})")


@config.command("set-opening")
@click.option("--file", "-f", required=True, help="App file path to edit")
@click.option("--text", required=True, help="Opening statement text")
@click.option("--json-output", "-j", is_flag=True, help="Output result as JSON")
def config_set_opening(file: str, text: str, json_output: bool):
    """Set the opening statement for a chat/agent app.

    \b
    EXAMPLES:
      dify-workflow config set-opening -f app.yaml --text "Hello! How can I help?"
    """
    from .chat.editor import set_opening_statement
    dsl = load_workflow(file)
    set_opening_statement(dsl, text)
    save_workflow(dsl, file)
    if json_output:
        output_json({"status": "updated"})
    else:
        console.print(f"[green]✓[/green] Opening statement set")


@config.command("add-question")
@click.option("--file", "-f", required=True, help="App file path to edit")
@click.option("--text", required=True, help="Suggested question text")
@click.option("--json-output", "-j", is_flag=True, help="Output result as JSON")
def config_add_question(file: str, text: str, json_output: bool):
    """Add a suggested question to the app.

    \b
    EXAMPLES:
      dify-workflow config add-question -f app.yaml --text "What can you do?"
    """
    from .chat.editor import add_suggested_question
    dsl = load_workflow(file)
    add_suggested_question(dsl, text)
    save_workflow(dsl, file)
    if json_output:
        output_json({"status": "added", "question": text})
    else:
        console.print(f"[green]✓[/green] Added suggested question")


@config.command("add-tool")
@click.option("--file", "-f", required=True, help="App file path to edit")
@click.option("--provider", required=True, help="Tool provider ID (e.g. calculator, wikipedia)")
@click.option("--tool", "tool_name", required=True, help="Tool name (e.g. calculate, search)")
@click.option("--tool-type", default="builtin", help="Tool type: builtin or api")
@click.option("--json-output", "-j", is_flag=True, help="Output result as JSON")
def config_add_tool(file: str, provider: str, tool_name: str, tool_type: str,
                    json_output: bool):
    """Add a tool to an agent app.

    \b
    EXAMPLES:
      dify-workflow config add-tool -f agent.yaml --provider calculator --tool calculate
      dify-workflow config add-tool -f agent.yaml --provider wikipedia --tool search
    """
    from .agent.editor import add_tool
    dsl = load_workflow(file)
    add_tool(dsl, provider, tool_name, tool_type=tool_type)
    save_workflow(dsl, file)
    if json_output:
        output_json({"status": "added", "provider": provider, "tool": tool_name})
    else:
        console.print(f"[green]✓[/green] Added tool: {provider}/{tool_name}")


@config.command("remove-tool")
@click.option("--file", "-f", required=True, help="App file path to edit")
@click.option("--tool", "tool_name", required=True, help="Tool name to remove")
@click.option("--json-output", "-j", is_flag=True, help="Output result as JSON")
def config_remove_tool(file: str, tool_name: str, json_output: bool):
    """Remove a tool from an agent app.

    \b
    EXAMPLES:
      dify-workflow config remove-tool -f agent.yaml --tool calculate
    """
    from .agent.editor import remove_tool
    dsl = load_workflow(file)
    removed = remove_tool(dsl, tool_name)
    if not removed:
        click.echo(f"Error: Tool '{tool_name}' not found", err=True)
        sys.exit(1)
    save_workflow(dsl, file)
    if json_output:
        output_json({"status": "removed", "tool": tool_name})
    else:
        console.print(f"[green]✓[/green] Removed tool: {tool_name}")
