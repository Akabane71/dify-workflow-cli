# Dify AI Workflow Tools

[中文 README](README.md)

**A local CLI for creating, editing, validating, laying out, and exporting all 5 Dify application types.**

Built from reverse engineering of Dify frontend + backend source code for DSL v0.6.0, covering all modes: **Workflow, Chatflow, Chat Assistant, Agent, and Text Generation**.

The validation layer aligns with Dify frontend's three-stage validation chain (node configuration -> variable references -> connectivity), and adds cycle detection so generated YAML can be imported into Dify without frontend warnings.

---

## Feature Overview

| Feature | Description |
|------|------|
| **Create** | Create any of the 5 app types with `create --mode`, including multiple templates |
| **Edit** | Use the `edit` command group to modify workflow graphs (nodes/edges), and `config` to edit model configuration |
| **Validate** | Auto-detect app mode and dispatch specialized validation (structure + node data + frontend compatibility + variable references + connectivity + cycle detection) |
| **Frontend Checklist** | The `checklist` command mirrors Dify frontend `use-checklist.ts` pre-publish checks |
| **Layout** | `layout` auto-arranges node positions with 5 strategies: `tree`, `hierarchical`, `linear`, `vertical`, `compact` |
| **Inspect** | `inspect` renders structure as a Rich tree, JSON, or a **Mermaid flowchart** |
| **Export** | Export as YAML or JSON, ready to import into Dify |
| **Diff** | `diff` compares two configuration files |

## Supported Application Modes

| CLI `--mode` | Dify `app.mode` | Architecture | Description |
|--------------|-----------------|---------|------|
| `workflow` | `workflow` | Workflow graph (Start->...->End) | Visual orchestration, single-run execution |
| `chatflow` | `advanced-chat` | Workflow graph (Start->...->Answer) | Visual orchestration, multi-turn conversation |
| `chat` | `chat` | model_config | Simple chatbot |
| `agent` | `agent-chat` | model_config | Chat + tool calling (`function_call` / `react`) |
| `completion` | `completion` | model_config | Single-turn text generation |

---

## Quick Start

### Install

```bash
cd dify-ai-workflow-tools
pip install -e .
```

Verify installation:

```bash
dify-workflow --version
# dify-workflow, version 0.1.1
```

### Create Examples for All 5 Modes

```bash
# Workflow (default)
dify-workflow create -o my_workflow.yaml

# LLM workflow template
dify-workflow create --mode workflow --template llm --name "Translator Bot" -o translator.yaml

# IF/ELSE branching workflow
dify-workflow create --mode workflow --template if-else -o router.yaml

# Chatflow (multi-turn workflow)
dify-workflow create --mode chatflow -o chatflow.yaml

# Knowledge-base Chatflow
dify-workflow create --mode chatflow --template knowledge -o kb_chat.yaml

# Chat assistant
dify-workflow create --mode chat --name "Chat Bot" -o chat.yaml

# Agent (tool calling)
dify-workflow create --mode agent --name "Smart Assistant" -o agent.yaml

# Text generation
dify-workflow create --mode completion --name "Copy Generator" -o gen.yaml
```

### Edit Workflow Graphs (`workflow` / `chatflow`)

```bash
# Add a node
dify-workflow edit add-node -f my_workflow.yaml --type code --title "Data Processing"

# Add an edge
dify-workflow edit add-edge -f my_workflow.yaml --source start_node --target <node_id>

# Update node data
dify-workflow edit update-node -f my_workflow.yaml --id llm_node \
  -d '{"model": {"provider": "openai", "name": "gpt-4o"}}'

# Remove a node (edges cleaned up automatically)
dify-workflow edit remove-node -f my_workflow.yaml --id <node_id>

# Rename a node
dify-workflow edit set-title -f my_workflow.yaml --id start_node --title "User Input"
```

### Edit Model Config (`chat` / `agent` / `completion`)

```bash
# Set model
dify-workflow config set-model -f chat.yaml --provider openai --name gpt-4o

# Set prompt
dify-workflow config set-prompt -f chat.yaml --text "You are a helpful assistant."

# Load prompt from file
dify-workflow config set-prompt -f chat.yaml --data-file prompt.txt

# Add user input variable
dify-workflow config add-variable -f chat.yaml --name query --type paragraph

# Set opening statement
dify-workflow config set-opening -f chat.yaml --text "Hello! How can I help you?"

# Add suggested question
dify-workflow config add-question -f chat.yaml --text "What can you do?"

# Agent: add tool
dify-workflow config add-tool -f agent.yaml --provider calculator --tool calculate

# Agent: remove tool
dify-workflow config remove-tool -f agent.yaml --tool calculate
```

### Validate and Export

```bash
# Validate (mode is auto-detected and dispatched to mode-specific rules)
dify-workflow validate my_workflow.yaml

# JSON validation report
dify-workflow validate my_workflow.yaml -j

# Strict mode (treat warnings as errors)
dify-workflow validate my_workflow.yaml --strict

# Export as YAML
dify-workflow export my_workflow.yaml --output final.yaml

# Export as JSON
dify-workflow export my_workflow.yaml -o final.json --format json

# Write to stdout
dify-workflow export my_workflow.yaml

# Inspect structure (Rich tree)
dify-workflow inspect my_workflow.yaml

# Inspect structure as JSON (useful for AI tooling)
dify-workflow inspect chat.yaml -j
```

### Other Commands

```bash
# Import and re-export (format conversion / normalization)
dify-workflow import external.yaml --output local.yaml

# Compare differences
dify-workflow diff before.yaml after.yaml

# Auto-layout (default: tree, Dify-style left-to-right)
dify-workflow layout -f my_workflow.yaml -o laid_out.yaml

# Optional strategies: tree / hierarchical / linear / vertical / compact
dify-workflow layout -f my_workflow.yaml --strategy hierarchical

# Dify frontend pre-publish checklist validation
dify-workflow checklist my_workflow.yaml

# Mermaid flowchart output (for AI analysis or Markdown embedding)
dify-workflow inspect my_workflow.yaml --mermaid

# List all supported node types
dify-workflow list-node-types

# Beginner guide
dify-workflow guide
```

---

## Project Structure

```text
dify_workflow/
├── __init__.py              # Package entry point, version
├── models.py                # Pydantic v2 data models for all DSL modes
├── editor.py                # Generic graph editing operations (add/remove/update nodes and edges)
├── validator.py             # Mode dispatcher (detect mode -> run specialized validator)
├── node_data_validator.py   # Node data validation aligned with Dify graph node schemas (25 node types)
├── node_validators_core.py  # Core node validators (LLM / Code / HTTP / IF-ELSE / Tool, etc.)
├── node_validators_extra.py # Extended node validators (Iteration / Loop / Agent, etc.)
├── frontend_validator.py    # Frontend compatibility validation (prevent import-time crashes)
├── checklist_validator.py   # Pre-publish checklist aligned with Dify use-checklist.ts three-layer checks
├── checklist_checks.py      # Checklist sub-check functions
├── layout.py                # Auto-layout engine (dispatches 5 strategies)
├── layout_tree.py           # Tree layout algorithm (Dify-style left-to-right grouped branches)
├── mermaid.py               # Mermaid flowchart output
├── io.py                    # YAML/JSON I/O + mode-aware serialization
├── scanner.py               # [Deprecated] dify-test source scanning analysis
├── cli.py                   # Click CLI entry point (command registration)
├── cli_edit.py              # edit command group
├── cli_config.py            # config command group
├── cli_inspect.py           # inspect command
├── cli_ops.py               # validate / checklist / export / import / diff / layout
├── cli_shared.py            # Shared CLI utilities
├── workflow/                # Workflow mode (mode=workflow)
│   ├── editor.py            #   Template creation: minimal / llm / if-else
│   └── validator.py         #   Graph validation: start/end, connectivity, cycle detection, checklist
├── chatflow/                # Chatflow mode (mode=advanced-chat)
│   ├── editor.py            #   Template creation: chatflow / knowledge
│   └── validator.py         #   Chatflow validation: Answer node, LLM memory
├── chat/                    # Chat assistant mode (mode=chat)
│   ├── editor.py            #   model_config editing: set_model / set_prompt / add_variable, etc.
│   └── validator.py         #   model / prompt validation
├── agent/                   # Agent mode (mode=agent-chat)
│   ├── editor.py            #   Agent config: strategy / add_tool / remove_tool
│   └── validator.py         #   agent_mode / strategy / tools validation
└── completion/              # Text generation mode (mode=completion)
    ├── editor.py            #   completion config: enable_more_like_this
    └── validator.py         #   prompt / user_input_form validation
```

## Technology Choices

| Component | Choice | Notes |
|------|------|------|
| Runtime | Python 3.12+ | Type hints |
| CLI framework | Click 8.x | Subcommands, argument validation, OrderedGroup |
| Data model | Pydantic v2 | ConfigDict, validation_alias / serialization_alias |
| YAML | PyYAML | Native Dify format |
| Output formatting | Rich | Tree view, tables, colored output |
| DSL version | Dify v0.6.0 | Tracks the latest DSL format |
| Testing | pytest | 419 tests passing |

---

## Validation Architecture

Validation runs from top to bottom, aligned with Dify frontend + backend behavior:

| Validation Layer | Command | Description |
|--------|------|------|
| **Graph structure validation** | `validate` | Start node existence, edge legality, cycle detection (DFS 3-color, aligned with frontend `getCycleEdges`) |
| **Node data validation** | `validate` | Field-level validation for 25 node types (aligned with graph node schemas) |
| **Frontend compatibility validation** | `validate` | UUID format for human-input, enum values, and similar constraints to prevent frontend crashes |
| **Connectivity validation** | `validate` | BFS reachability from Start, including Iteration/Loop subnodes |
| **Pre-publish checklist** | `checklist` | Mirrors Dify frontend `use-checklist.ts`: node completeness, upstream variable references, and reachability |

> When Dify frontend loads a DSL file, it runs cycle detection (`getCycleEdges`) and removes all edges on detected cycles.
> This tool fails early during `validate` so you do not import a graph that becomes disconnected after Dify cleans the cycle.

---

## Tests

```bash
# Run the full test suite
python -m pytest tests/ -v

# Quick summary
python -m pytest tests/ -q
# 419 passed
```

| File | Count | Coverage |
|------|------|--------|
| test_node_data_validator.py | 76 | Field-level validation for 25 node types |
| test_editor.py | 49 | Node/edge operations and template creation |
| test_checklist_validator.py | 47 | Pre-publish checklist (variable references, connectivity) |
| test_cli.py | 46 | End-to-end coverage for all CLI commands |
| test_frontend_validator.py | 43 | Frontend compatibility validation |
| test_layout.py | 37 | Five layout strategies + node non-overlap |
| test_models.py | 20 | Data models, enums, serialization |
| test_chat.py | 19 | Chat assistant creation, editing, I/O, validation |
| test_integration.py | 19 | End-to-end scenarios with real Dify fixtures |
| test_validator.py | 16 | Graph structure, connectivity, cycle detection |
| test_agent.py | 15 | Agent creation, editing, I/O, validation |
| test_io.py | 13 | YAML/JSON I/O and round-trip |
| test_completion.py | 11 | Text generation creation, editing, I/O, validation |
| test_chatflow.py | 8 | Chatflow creation and validation |
| **Total** | **419** | |

---

## Documentation

| Document | Content |
|------|------|
| [docs/cli-reference.md](docs/cli-reference.md) | Complete CLI command reference |
| [docs/architecture.md](docs/architecture.md) | Architecture, module layering, design principles |
| [docs/testing.md](docs/testing.md) | Testing guide and coverage analysis |
| [docs/validation-coverage.md](docs/validation-coverage.md) | DSL validation coverage matrix vs official Dify behavior |
| [docs/analysis-frontend-checklist.md](docs/analysis-frontend-checklist.md) | Reverse engineering notes for the Dify frontend pre-publish checklist |
| [docs/analysis-node-output-variables.md](docs/analysis-node-output-variables.md) | Node output variable mapping table |
| [docs/analysis-dsl-structure.md](docs/analysis-dsl-structure.md) | Reverse engineering notes for Dify DSL structure |
| [docs/analysis-call-chain.md](docs/analysis-call-chain.md) | Import/export call chain analysis |
| [docs/analysis-data-structures.md](docs/analysis-data-structures.md) | Core data structure analysis |
| [docs/dify-dsl研究/](docs/dify-dsl研究/) | Comparative research across all 5 application types |
| [docs/examples/](docs/examples/) | Example workflow documentation |

## Examples

See the detailed example guide at [docs/examples/使用案例.md](docs/examples/使用案例.md)