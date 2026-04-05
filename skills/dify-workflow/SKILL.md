---
name: dify-workflow
description: 'Build, edit, validate, and export Dify AI workflow DSL files using the dify-workflow CLI. Use when: creating Dify workflows/chatflows/chat/agent/completion apps; adding nodes and edges to workflows; configuring LLM/tool/code/if-else/question-classifier nodes; validating DSL before Dify import; auto-layout node positions; generating Mermaid diagrams; troubleshooting Dify import errors. Supports all 5 Dify app modes and 22 node types.'
argument-hint: 'Describe the Dify workflow you want to build or the editing operation to perform'
---

# Dify Workflow CLI Skill

Build, edit, validate, layout, and export Dify DSL files entirely from the command line.
The CLI is installed as `dify-workflow` (or `dify-workflow.exe` on Windows).

If the CLI is not yet installed in the current environment, use [PowerShell install script](./scripts/install.ps1) on Windows or [shell install script](./scripts/install.sh) on macOS/Linux.

## When to Use

- User asks to create a Dify workflow, chatflow, chat app, agent, or completion app
- User asks to add/remove/update nodes or edges in a Dify YAML
- User asks to validate a Dify DSL file before import
- User asks to auto-layout node positions
- User asks to generate a Mermaid diagram of a workflow
- User asks to troubleshoot why a Dify import shows disconnected nodes or errors

## Key Constraints

- **DAG only**: Dify workflows must be directed acyclic graphs. No cycles allowed — Dify's frontend runs `getCycleEdges()` and silently removes all edges between cycle nodes, causing disconnections.
- **Variable references**: Use `{{#node_id.variable#}}` syntax. Tool nodes output `text`/`files`/`json` (NOT `result`). LLM nodes output `text`.
- **Node positioning**: Dify uses screen coordinates (origin top-left, X→right, Y→down). Use `layout` command to auto-arrange.
- **PowerShell JSON**: On Windows PowerShell, avoid inline JSON with `--data`. Use `--data-file` with UTF-8 (no BOM) files instead.

## Procedure: Create a Workflow from Scratch

Before editing a workflow, prefer this execution order:

1. Ensure the CLI is installed
2. Create or open a DSL file
3. Add/update nodes and edges
4. Run `validate`
5. Run `checklist`
6. Run `layout`
7. Export or inspect with Mermaid

If the user asks for a complex node payload, prefer using templates in [assets](./assets/).

### Step 1: Create base file

```bash
dify-workflow create --mode workflow --name "My Workflow" -o workflow.yaml
# Templates: minimal (default), llm, if-else
# Modes: workflow, chatflow, chat, agent, completion
```

### Step 2: Add nodes

```bash
# Add nodes one at a time
dify-workflow edit add-node -f workflow.yaml --type llm --title "GPT Node" --id my_llm

# With data (prefer --data-file on Windows to avoid escaping issues)
dify-workflow edit add-node -f workflow.yaml --type code --title "Process" --id processor
dify-workflow edit update-node -f workflow.yaml --id my_llm --data-file ./assets/llm-node-config.json
```

### Step 3: Add edges

```bash
dify-workflow edit add-edge -f workflow.yaml --source start_node --target my_llm
dify-workflow edit add-edge -f workflow.yaml --source my_llm --target end_node

# For branching nodes (if-else, question-classifier), specify --source-handle
dify-workflow edit add-edge -f workflow.yaml -s ifelse_node -t happy_path --source-handle true
dify-workflow edit add-edge -f workflow.yaml -s ifelse_node -t sad_path --source-handle false
```

### Step 4: Update node data

```bash
dify-workflow edit update-node -f workflow.yaml --id my_llm \
  -d '{"model": {"provider": "openai", "name": "gpt-4o-mini", "mode": "chat", "completion_params": {"temperature": 0.7}}}'

# Or from file (recommended on Windows)
dify-workflow edit update-node -f workflow.yaml --id my_llm --data-file llm_config.json

# Ready-to-use templates are bundled in this skill
# - ./assets/llm-node-config.json
# - ./assets/question-classifier-config.json
# - ./assets/http-request-config.json
```

### Step 5: Validate

```bash
dify-workflow validate workflow.yaml           # Human-readable
dify-workflow validate workflow.yaml -j        # JSON output
dify-workflow validate workflow.yaml --strict  # Warnings = errors
dify-workflow checklist workflow.yaml          # Dify frontend pre-publish check
```

### Step 6: Layout and export

```bash
dify-workflow layout -f workflow.yaml          # Auto-arrange (tree strategy, in-place)
dify-workflow layout -f workflow.yaml -o out.yaml --strategy hierarchical
dify-workflow export workflow.yaml -o final.yaml
```

## Command Reference

See [commands reference](./references/commands.md) for full command details.
See [node types reference](./references/node-types.md) for all 22 node types and their data schemas.
See [patterns reference](./references/patterns.md) for common workflow patterns and PowerShell examples.

## Bundled Resources

- [install.ps1](./scripts/install.ps1): editable install for Windows PowerShell
- [install.sh](./scripts/install.sh): editable install for bash/zsh
- [llm-node-config.json](./assets/llm-node-config.json): LLM node payload template
- [question-classifier-config.json](./assets/question-classifier-config.json): classifier payload template
- [http-request-config.json](./assets/http-request-config.json): HTTP request node payload template

## Quick Command Table

| Command | Purpose |
|---------|---------|
| `create -o file.yaml` | Create new app (use `--mode` and `--template`) |
| `edit add-node -f file.yaml --type TYPE --title TITLE` | Add a node |
| `edit add-edge -f file.yaml --source SRC --target TGT` | Add an edge |
| `edit update-node -f file.yaml --id ID -d JSON` | Update node data |
| `edit remove-node -f file.yaml --id ID` | Remove node + cleanup edges |
| `edit set-title -f file.yaml --id ID --title TEXT` | Rename a node |
| `validate file.yaml` | Validate DSL |
| `checklist file.yaml` | Pre-publish checks (mirrors Dify UI) |
| `inspect file.yaml` | Tree view |
| `inspect file.yaml -j` | JSON structure |
| `inspect file.yaml -m` | Mermaid flowchart |
| `layout -f file.yaml` | Auto-layout (tree default) |
| `diff a.yaml b.yaml` | Compare two files |
| `config set-model -f app.yaml --provider X --name Y` | Set model (chat/agent/completion) |
| `config set-prompt -f app.yaml --text "..."` | Set prompt |

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Nodes disconnected after Dify import | Cycle in graph → frontend strips edges | Run `validate` to detect cycles, remove back-edges |
| Checklist errors in Dify UI | Missing required fields or invalid variable refs | Run `checklist` locally first |
| Variable reference not found | Wrong output variable name (e.g. `.result` vs `.text`) | Tool nodes output `text`, not `result` |
| Layout looks messy in Dify | No layout applied or wrong strategy | Run `layout -f file.yaml` (tree default) |
| JSON parse error on Windows | PowerShell escaping issues | Use `--data-file` instead of `-d` |

## Agent Behavior

- Prefer `--data-file` over inline JSON on Windows
- Prefer `inspect -m` when the user asks for a visual explanation of the graph
- Prefer `checklist` in addition to `validate` before claiming a file is Dify-ready
- Prefer `layout` before export when the user cares about Dify canvas appearance
- If the user asks for a complex workflow, build it incrementally and validate after each major branch
