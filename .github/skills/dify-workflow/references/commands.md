# Commands Reference

## create — Create a new Dify app

```bash
dify-workflow create -o FILE [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--mode` | workflow | workflow / chatflow / chat / agent / completion |
| `--template` | minimal | workflow: minimal/llm/if-else; chatflow: chatflow/knowledge |
| `--name` | auto | App name |
| `--model-provider` | openai | LLM provider |
| `--model-name` | gpt-4o | Model name |
| `--system-prompt` | generic | System prompt (chat/agent/completion) |
| `-j` | false | JSON output |

## edit — Edit workflow graph

### add-node

```bash
dify-workflow edit add-node -f FILE --type TYPE --title TITLE [--id ID] [-d JSON | --data-file FILE]
```

### remove-node

```bash
dify-workflow edit remove-node -f FILE --id ID
```

Automatically removes all connected edges.

### update-node

```bash
dify-workflow edit update-node -f FILE --id ID [-d JSON | --data-file FILE]
```

Merges provided data into existing node data (shallow merge).

### add-edge

```bash
dify-workflow edit add-edge -f FILE --source SRC --target TGT [--source-handle HANDLE]
```

Source handles for branching nodes:
- **if-else**: `true` (IF branch), `false` (ELSE branch), or case_id for ELIF
- **question-classifier**: class ID string (e.g. `consult`, `order`)

### remove-edge

```bash
dify-workflow edit remove-edge -f FILE --id EDGE_ID
```

### set-title

```bash
dify-workflow edit set-title -f FILE --id ID --title TEXT
```

## config — Edit model config (chat/agent/completion)

```bash
dify-workflow config set-model -f FILE --provider PROVIDER --name MODEL [--temperature T] [--max-tokens N]
dify-workflow config set-prompt -f FILE --text "..." | --data-file prompt.txt
dify-workflow config add-variable -f FILE --name NAME --type TYPE [--required|--optional]
dify-workflow config set-opening -f FILE --text "..."
dify-workflow config add-question -f FILE --text "..."
dify-workflow config add-tool -f FILE --provider PROVIDER --tool TOOL [--tool-type builtin|api]
dify-workflow config remove-tool -f FILE --tool TOOL
```

Variable types: `text-input`, `paragraph`, `select`, `number`

## validate — Validate DSL

```bash
dify-workflow validate FILE [-j] [--strict]
```

Checks: structure, 25 node types schema, frontend compatibility, connectivity (BFS from Start), **cycle detection** (DFS 3-color), pre-publish checklist.

Exit code: 0 = valid, 1 = errors.

## checklist — Pre-publish checklist

```bash
dify-workflow checklist FILE [-j]
```

Mirrors Dify frontend `use-checklist.ts`:
1. Node config completeness (required fields)
2. Upstream variable reference validity
3. All nodes reachable from Start

## inspect — View structure

```bash
dify-workflow inspect FILE          # Rich tree
dify-workflow inspect FILE -j       # JSON
dify-workflow inspect FILE -m       # Mermaid flowchart
```

## layout — Auto-layout

```bash
dify-workflow layout -f FILE [-o OUTPUT] [-s STRATEGY]
```

Strategies: `tree` (default, Dify-style), `hierarchical`, `linear`, `vertical`, `compact`

## export / import / diff

```bash
dify-workflow export FILE [-o OUTPUT] [--format yaml|json]
dify-workflow import FILE -o OUTPUT [--validate-only]
dify-workflow diff FILE1 FILE2 [-j]
```

## Utility commands

```bash
dify-workflow guide [-j]            # Tutorial
dify-workflow list-node-types [-j]  # All 22 node types
```
