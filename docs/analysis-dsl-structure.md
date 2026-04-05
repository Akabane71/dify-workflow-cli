# Dify 工作流 DSL 逆向分析：DSL 结构与格式

> 基于 `dify-test` 项目源码逆向分析，DSL 版本 0.6.0

## 1. 顶层 DSL 结构

Dify 工作流导出格式为 **YAML**（主格式），内部存储使用 JSON。顶层结构如下：

```yaml
version: "0.6.0"        # DSL 版本号
kind: "app"              # 固定值
app:                     # 应用元信息
  name: "App Name"
  mode: "workflow"       # workflow | advanced-chat | agent-chat | chat | completion
  icon: "🤖"
  icon_type: "emoji"     # emoji | image-from-url
  icon_background: "#FFEAD5"
  description: ""
  use_icon_as_answer_icon: false
workflow:                # 工作流内容（仅 workflow/advanced-chat 模式）
  graph:
    nodes: [...]         # 节点数组
    edges: [...]         # 连线数组
    viewport: { x, y, zoom }
  features: {...}        # 功能配置
  environment_variables: [...]   # 环境变量
  conversation_variables: [...]  # 对话变量
  rag_pipeline_variables: [...]  # RAG 变量
model_config: {...}      # 非工作流模式的模型配置
dependencies:            # 依赖的插件/模型提供商
  - name: "langgenius/openai"
    type: "model_provider"
    version: "..."
```

## 2. 节点结构 (Node)

每个节点遵循统一的外层结构，`data.type` 字段决定节点类型：

```yaml
- id: "start_node"              # 唯一 ID（字符串，通常为时间戳）
  type: "custom"                # 固定值 "custom"
  position:
    x: 30
    y: 227
  positionAbsolute:
    x: 30
    y: 227
  width: 244
  height: 90
  selected: false
  sourcePosition: "right"
  targetPosition: "left"
  data:
    type: "start"               # 节点类型（见下方列表）
    title: "Start"
    desc: ""
    # ... 类型特定字段
```

## 3. 支持的节点类型

| 节点类型 | `data.type` 值 | 用途 | 关键字段 |
|---------|---------------|------|---------|
| 开始 | `start` | 工作流入口 | `variables` |
| 结束 | `end` | 工作流出口 | `outputs` |
| 回答 | `answer` | 输出回答 | `answer` |
| LLM | `llm` | 大模型调用 | `model`, `prompt_template`, `vision`, `memory` |
| 工具 | `tool` | 工具/插件调用 | `provider_id`, `tool_name`, `tool_parameters` |
| 代码 | `code` | Python/JS 执行 | `code`, `code_language` |
| 条件分支 | `if-else` | 条件判断 | `cases` |
| 模板转换 | `template-transform` | Jinja2 渲染 | `template` |
| HTTP 请求 | `http-request` | HTTP 调用 | `url`, `method`, `headers`, `body` |
| 知识检索 | `knowledge-retrieval` | RAG 检索 | `dataset_ids`, `retrieval_model` |
| 问题分类 | `question-classifier` | 意图分类 | `classification_rules`, `model` |
| 参数提取 | `parameter-extractor` | 结构化提取 | `extraction_rules`, `model` |
| 变量聚合 | `variable-aggregator` | 变量合并 | - |
| 迭代 | `iteration` | 循环处理 | `iterator_variable` |
| 循环 | `loop` | 循环控制 | - |
| Agent | `agent` | 自主代理 | - |
| 文档提取 | `document-extractor` | 文档解析 | - |
| 人工输入 | `human-input` | 人工审核 | `form_fields` |
| 数据源 | `datasource` | 数据源入口 | - |
| Webhook 触发 | `trigger-webhook` | HTTP 触发 | `webhook_url` |
| 定时触发 | `trigger-schedule` | 定时执行 | `cron_expression` |
| 插件触发 | `trigger-plugin` | 插件触发 | `plugin_id` |

## 4. 连线结构 (Edge)

```yaml
- id: "start-to-llm"            # 连线 ID
  source: "start_node"           # 源节点 ID
  target: "llm_node"             # 目标节点 ID
  sourceHandle: "source"         # 源端口（默认 "source"，条件分支用 "true"/"false"）
  targetHandle: "target"         # 目标端口
  type: "custom"                 # 固定值
  zIndex: 0
  data:
    sourceType: "start"          # 源节点类型
    targetType: "llm"            # 目标节点类型
    isInIteration: false
    isInLoop: false
```

## 5. 各节点类型详细字段

### Start 节点
```yaml
data:
  type: start
  variables:
    - variable: query           # 变量名
      label: query              # 显示标签
      type: text-input          # text-input | paragraph | select | number | file | file-list
      required: true
      max_length: null
      options: []
```

### End 节点
```yaml
data:
  type: end
  outputs:
    - variable: result          # 输出变量名
      value_selector:           # 值来源（节点ID + 字段名）
        - start_node
        - query
      value_type: string
```

### LLM 节点
```yaml
data:
  type: llm
  model:
    provider: openai
    name: gpt-3.5-turbo
    mode: chat
    completion_params:
      temperature: 0.7
      max_tokens: 4096
  prompt_template:
    - role: system
      text: "You are a helpful assistant."
    - role: user
      text: "{{#start_node.query#}}"
  vision:
    enabled: false
  memory:
    enabled: false
    window: { enabled: false, size: 50 }
  context:
    enabled: false
    variable_selector: []
  structured_output:
    enabled: false
  retry_config:
    enabled: false
    max_retries: 1
    retry_interval: 1000
```

### IF/ELSE 节点
```yaml
data:
  type: if-else
  cases:
    - id: "true"
      case_id: "true"
      logical_operator: and
      conditions:
        - id: "uuid"
          comparison_operator: contains   # contains | eq | ne | gt | lt 等
          value: "hello"
          varType: string
          variable_selector:
            - start_node
            - query
```

## 6. Features 配置

```yaml
features:
  file_upload:
    enabled: false
  opening_statement: ""
  retriever_resource:
    enabled: false
  sensitive_word_avoidance:
    enabled: false
  speech_to_text:
    enabled: false
  suggested_questions: []
  suggested_questions_after_answer:
    enabled: false
  text_to_speech:
    enabled: false
```

## 7. 变量引用语法

节点间通过 `value_selector` 数组引用变量：
- `["start_node", "query"]` → 引用 start_node 的 query 变量
- `["llm_node", "text"]` → 引用 LLM 节点的文本输出

在 prompt 模板中使用 `{{#node_id.variable#}}` 语法。

## 8. 版本兼容性

| 导入版本 vs 当前版本 | 结果 |
|-------------------|------|
| major 不匹配 | PENDING（需人工确认） |
| minor < 当前 | COMPLETED_WITH_WARNINGS |
| 相同 | COMPLETED |
