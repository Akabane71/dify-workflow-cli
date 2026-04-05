# Node Types Reference

## All 22 Node Types

| Type | Category | Description |
|------|----------|-------------|
| `start` | Entry | Workflow entry point, defines user input variables |
| `end` | Terminal | Workflow output, defines output variables |
| `answer` | Terminal | Chatflow streaming response |
| `llm` | AI | LLM text generation (requires model config) |
| `code` | Processing | Python3/JavaScript code execution |
| `if-else` | Routing | Conditional branching (IF/ELIF/ELSE) |
| `question-classifier` | Routing | LLM-based intent classification |
| `knowledge-retrieval` | Data | RAG knowledge base search |
| `tool` | Integration | External tool/API call |
| `http-request` | Integration | HTTP API request (GET/POST/PUT/DELETE/PATCH/HEAD) |
| `template-transform` | Processing | Jinja2 template rendering |
| `variable-assigner` | Data | Write to conversation variables |
| `variable-aggregator` | Data | Merge variables from multiple branches |
| `parameter-extractor` | AI | LLM-based parameter extraction |
| `iteration` | Control | Loop over array items |
| `loop` | Control | Conditional loop with break condition |
| `document-extractor` | Data | Extract text from documents |
| `list-operator` | Data | List filtering/sorting/slicing |
| `agent` | AI | Autonomous agent with tools |
| `human-input` | Interaction | Wait for human input/approval |
| `datasource` | Entry | Database source trigger |
| `assigner` | Data | Variable assignment (legacy) |

## Node Data Schemas

### start

```json
{
  "type": "start",
  "title": "Start",
  "variables": [
    {"variable": "query", "label": "用户问题", "type": "paragraph", "required": true}
  ]
}
```

Variable types: `text-input`, `paragraph`, `number`, `select`, `file`, `file-list`

### end

```json
{
  "type": "end",
  "title": "End",
  "outputs": [
    {"variable": "result", "value_selector": ["llm_node", "text"], "value_type": "string"}
  ]
}
```

### llm

```json
{
  "type": "llm",
  "title": "GPT Node",
  "model": {
    "provider": "openai",
    "name": "gpt-4o-mini",
    "mode": "chat",
    "completion_params": {"temperature": 0.7}
  },
  "prompt_template": [
    {"role": "system", "text": "You are a helpful assistant."},
    {"role": "user", "text": "{{#start_node.query#}}"}
  ],
  "vision": {"enabled": false},
  "memory": {"enabled": false},
  "context": {"enabled": false}
}
```

### code

```json
{
  "type": "code",
  "title": "Process",
  "code_language": "python3",
  "code": "return {\"result\": inputs[\"text\"]}",
  "variables": [{"variable": "text", "value_selector": ["llm_node", "text"]}],
  "outputs": {"result": {"type": "string"}}
}
```

Allowed `code_language`: `python3`, `javascript`
Output types: `string`, `number`, `object`, `array[string]`, `array[number]`, `array[object]`

### if-else

```json
{
  "type": "if-else",
  "title": "Check",
  "cases": [
    {
      "case_id": "true",
      "conditions": [
        {"id": "c1", "variable_selector": ["node_id", "var"], "comparison_operator": "contains", "value": "keyword"}
      ],
      "logical_operator": "and"
    }
  ]
}
```

Comparison operators: `contains`, `not contains`, `start with`, `end with`, `is`, `is not`, `empty`, `not empty`, `=`, `≠`, `>`, `<`, `≥`, `≤`

Edge handles: IF branch → `sourceHandle: "true"`, ELSE → `sourceHandle: "false"`

### question-classifier

```json
{
  "type": "question-classifier",
  "title": "Intent",
  "model": {"provider": "openai", "name": "gpt-4o-mini", "mode": "chat"},
  "query_variable_selector": ["start_node", "query"],
  "classes": [
    {"id": "consult", "name": "咨询类"},
    {"id": "order", "name": "订单类"}
  ],
  "instruction": "Classify the user query."
}
```

Edge handles: use class `id` as `sourceHandle` (e.g., `sourceHandle: consult`)

### tool

```json
{
  "type": "tool",
  "title": "Search",
  "provider_id": "my_provider",
  "provider_type": "api",
  "tool_name": "search",
  "tool_parameters": {"query": "{{#start_node.query#}}"},
  "tool_configurations": {}
}
```

**Output variables**: `text`, `files`, `json` (NOT `result`)

### http-request

```json
{
  "type": "http-request",
  "title": "Call API",
  "method": "get",
  "url": "https://api.example.com/data",
  "headers": "{}",
  "params": "{}",
  "body": {"type": "none", "data": []},
  "authorization": {"type": "no-auth", "config": null}
}
```

Methods: `get`, `post`, `put`, `delete`, `patch`, `head`
Output variables: `body`, `status_code`, `headers`, `files`

### knowledge-retrieval

```json
{
  "type": "knowledge-retrieval",
  "title": "KB Search",
  "dataset_ids": ["dataset_uuid_here"],
  "retrieval_model": {"search_method": "semantic_search", "top_k": 3},
  "query_variable_selector": ["start_node", "query"]
}
```

Output: `result` (array of retrieved chunks)

### parameter-extractor

```json
{
  "type": "parameter-extractor",
  "title": "Extract Params",
  "model": {"provider": "openai", "name": "gpt-4o-mini", "mode": "chat"},
  "query": ["start_node", "query"],
  "parameters": [
    {"name": "city", "type": "string", "description": "City name", "required": true}
  ],
  "reasoning_mode": "prompt"
}
```

Reasoning modes: `prompt`, `function_call`
Output: extracted parameter values + `__is_success`, `__reason`

## Node Output Variable Mapping

This table shows what variables each node type actually outputs (for variable references `{{#node_id.VAR#}}`):

| Node Type | Output Variables |
|-----------|-----------------|
| start | User-defined variables |
| end | — (terminal) |
| answer | — (terminal) |
| llm | `text`, `reasoning_content`, `usage` |
| code | User-defined in `outputs` |
| tool | `text`, `files`, `json` |
| http-request | `body`, `status_code`, `headers`, `files` |
| knowledge-retrieval | `result` |
| question-classifier | `class_name`, `usage` |
| parameter-extractor | Defined params + `__is_success`, `__reason`, `__usage` |
| template-transform | `output` |
| if-else | — (routing only) |
| variable-assigner | — (writes to conversation var) |
| variable-aggregator | `output` |
| iteration | `output` (from child graph) |
| loop | Loop variables defined in config |
| agent | `text`, `files`, `json`, `usage` |
