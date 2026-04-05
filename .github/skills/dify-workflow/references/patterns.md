# Common Patterns & Examples

## Pattern 1: Linear LLM Workflow

```bash
dify-workflow create --template llm --name "Translator" -o translator.yaml
dify-workflow edit update-node -f translator.yaml --id llm_node --data-file ./assets/llm-node-config.json
dify-workflow validate translator.yaml
dify-workflow layout -f translator.yaml
```

Result: Start → LLM → End

## Pattern 2: IF-ELSE Branching

```bash
dify-workflow create --template if-else --name "Router" -o router.yaml
# Adds: Start → IF-ELSE → End(true) / End(false)

# Add processing nodes on each branch
dify-workflow edit add-node -f router.yaml --type llm --title "Handle Yes" --id yes_handler
dify-workflow edit add-node -f router.yaml --type llm --title "Handle No" --id no_handler
dify-workflow edit add-edge -f router.yaml -s ifelse_node -t yes_handler --source-handle true
dify-workflow edit add-edge -f router.yaml -s ifelse_node -t no_handler --source-handle false
```

## Pattern 3: Question Classifier (Intent Routing)

```bash
dify-workflow create -o intent.yaml
dify-workflow edit add-node -f intent.yaml --type question-classifier --title "Intent" --id classifier

# Update with classes
dify-workflow edit update-node -f intent.yaml --id classifier --data-file ./assets/question-classifier-config.json

# Connect branches using class IDs as handles
dify-workflow edit add-edge -f intent.yaml -s classifier -t sales_node --source-handle sales
dify-workflow edit add-edge -f intent.yaml -s classifier -t support_node --source-handle support
```

## Pattern 4: Knowledge Base + LLM (RAG)

```bash
dify-workflow create --mode chatflow --template knowledge -o rag.yaml
# Creates: Start → Knowledge Retrieval → LLM (with context) → Answer
```

## Pattern 5: HTTP API Integration

```bash
dify-workflow edit add-node -f wf.yaml --type http-request --title "Call API" --id api_call
dify-workflow edit update-node -f wf.yaml --id api_call --data-file ./assets/http-request-config.json

# Reference HTTP response in downstream node
# Use: {{#api_call.body#}} for response body
```

## Bootstrap CLI If Missing

```powershell
./scripts/install.ps1
```

```bash
./scripts/install.sh
```

## Pattern 6: Multi-Branch Convergence

Multiple branches that converge to a single node:

```bash
# Three tool nodes → one LLM
dify-workflow edit add-edge -f wf.yaml -s tool_a -t summary_llm
dify-workflow edit add-edge -f wf.yaml -s tool_b -t summary_llm
dify-workflow edit add-edge -f wf.yaml -s tool_c -t summary_llm
```

## Windows PowerShell Tips

### Use --data-file for complex JSON

```powershell
# Create JSON file (UTF-8 without BOM)
$config = @{
    model = @{
        provider = "openai"
        name = "gpt-4o-mini"
        mode = "chat"
        completion_params = @{ temperature = 0.3 }
    }
    prompt_template = @(
        @{ role = "system"; text = "You are a helpful assistant." }
        @{ role = "user"; text = "{{#start_node.query#}}" }
    )
}
[System.IO.File]::WriteAllText("config.json", ($config | ConvertTo-Json -Depth 10), [System.Text.UTF8Encoding]::new($false))

dify-workflow edit update-node -f workflow.yaml --id my_llm --data-file config.json
Remove-Item config.json
```

### Batch workflow build script

```powershell
param([string]$OutputPath = "workflow.yaml")

dify-workflow create --name "My Workflow" -o $OutputPath

dify-workflow edit add-node -f $OutputPath --type llm --title "Process" --id processor
dify-workflow edit add-edge -f $OutputPath --source start_node --target processor
dify-workflow edit add-edge -f $OutputPath --source processor --target end_node

dify-workflow validate $OutputPath --strict
dify-workflow layout -f $OutputPath
dify-workflow inspect $OutputPath -m
```

## Chat / Agent / Completion Mode

```bash
# Chat app
dify-workflow create --mode chat --name "Bot" -o bot.yaml
dify-workflow config set-model -f bot.yaml --provider openai --name gpt-4o
dify-workflow config set-prompt -f bot.yaml --text "You are a helpful assistant."
dify-workflow config add-variable -f bot.yaml --name query --type paragraph
dify-workflow config set-opening -f bot.yaml --text "Hello! How can I help?"

# Agent with tools
dify-workflow create --mode agent --name "Agent" -o agent.yaml
dify-workflow config add-tool -f agent.yaml --provider calculator --tool calculate
dify-workflow config add-tool -f agent.yaml --provider wikipedia --tool search

# Completion (text generation)
dify-workflow create --mode completion --name "Writer" -o writer.yaml
dify-workflow config set-prompt -f writer.yaml --text "Summarize: {{query}}"
```

## Validation Flow (Recommended)

Always validate before importing to Dify:

```bash
# 1. Structural + node data + cycle detection
dify-workflow validate workflow.yaml --strict

# 2. Dify frontend pre-publish checklist
dify-workflow checklist workflow.yaml

# 3. Visual check via Mermaid
dify-workflow inspect workflow.yaml -m

# 4. Auto-layout for clean positioning
dify-workflow layout -f workflow.yaml

# 5. Final export
dify-workflow export workflow.yaml -o final.yaml
```
