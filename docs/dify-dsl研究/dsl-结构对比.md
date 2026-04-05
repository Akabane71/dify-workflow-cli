# Dify DSL 结构对比

> 两种架构下的 DSL YAML 结构差异

## 一、Workflow / Chatflow 架构的 DSL

```yaml
version: "0.6.0"
kind: app
app:
  name: "我的工作流"
  mode: workflow          # 或 "advanced-chat"
  icon: "🤖"
  icon_type: emoji
  icon_background: "#FFEAD5"
  description: "..."
  use_icon_as_answer_icon: false

workflow:
  graph:
    nodes:
    - id: start_node
      type: custom
      data:
        type: start       # 节点类型
        title: 开始
        variables: [...]  # 输入变量
      position: { x: 80, y: 282 }
      # ...
    - id: llm_node
      type: custom
      data:
        type: llm
        title: LLM
        model:
          provider: openai
          name: gpt-4o
          mode: chat
          completion_params: { temperature: 0.7 }
        prompt_template:
        - role: system
          text: "..."
        - role: user
          text: "{{#start_node.query#}}"
      # ...
    - id: end_node        # workflow 用 end，chatflow 用 answer
      type: custom
      data:
        type: end          # chatflow 用 type: answer
        title: 结束
        outputs: [...]
      # ...
    edges:
    - id: edge-1
      source: start_node
      target: llm_node
      sourceHandle: source
      targetHandle: target
      type: custom
      data:
        sourceType: start
        targetType: llm
    # ...
    viewport:
      x: 0
      y: 0
      zoom: 0.8

  features:
    file_upload:
      enabled: false
    opening_statement: ""           # chatflow 有效，workflow 无效
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

  environment_variables: []         # 环境变量（两者都有）
  conversation_variables: []        # 对话变量（仅 chatflow 有意义）
  rag_pipeline_variables: []

dependencies:
- name: openai
  type: model_provider
  version: ""
```

---

## 二、Chat / Agent / Completion 架构的 DSL

```yaml
version: "0.6.0"
kind: app
app:
  name: "我的聊天助手"
  mode: chat              # 或 "agent-chat" 或 "completion"
  icon: "🤖"
  icon_type: emoji
  icon_background: "#FFEAD5"
  description: "..."
  use_icon_as_answer_icon: false

model_config:                       # ← 注意：这里不是 workflow，而是 model_config
  model:
    provider: openai
    name: gpt-4o
    mode: chat
    completion_params:
      temperature: 0.7
      max_tokens: 512
      top_p: 1
      frequency_penalty: 0
      presence_penalty: 0

  pre_prompt: "你是一个有用的助手。\n\n{{query}}"
  prompt_type: simple               # simple 或 advanced

  # advanced 模式下使用
  chat_prompt_config: {}
  completion_prompt_config: {}

  user_input_form:
  - paragraph:
      label: 查询
      variable: query
      required: true
      default: ""

  # Agent 专属
  agent_mode:
    enabled: false                  # agent-chat 时为 true
    strategy: function_call         # 或 react
    tools:
    - tool_type: builtin
      provider_id: calculator
      tool_name: calculate
      tool_parameters: {}

  # 知识库配置
  dataset_configs:
    datasets:
      datasets: []
    retrieval_model: single         # single / multiple
    top_k: 4
    score_threshold: null
    score_threshold_enabled: false
    reranking_mode: null

  # 对话功能
  opening_statement: "你好！"       # completion 模式不支持
  suggested_questions:
  - "请介绍一下你自己"
  suggested_questions_after_answer:
    enabled: true
  retriever_resource:
    enabled: true
  more_like_this:
    enabled: false                  # 仅 completion 模式支持开启

  # 语音
  speech_to_text:
    enabled: false
  text_to_speech:
    enabled: false

  # 其他
  sensitive_word_avoidance:
    enabled: false
  file_upload:
    enabled: false

dependencies:
- name: openai
  type: model_provider
  version: ""
```

---

## 三、关键差异总结

| 维度 | Workflow 架构 | ModelConfig 架构 |
|------|:-------------|:----------------|
| **DSL 顶层字段** | `workflow:` | `model_config:` |
| **模型配置** | 分散在各 LLM 节点的 `data.model` 中 | 集中在 `model_config.model` |
| **Prompt** | 各 LLM 节点的 `data.prompt_template` | `model_config.pre_prompt` |
| **输入变量** | Start 节点的 `data.variables` | `model_config.user_input_form` |
| **输出** | End 节点的 `data.outputs` | 模型直接输出 |
| **知识库** | Knowledge-Retrieval 节点 | `model_config.dataset_configs` |
| **条件分支** | IF/ELSE 节点 | 不支持 |
| **代码执行** | Code 节点 | 不支持 |
| **工具调用** | Tool 节点 / Agent 节点 | `model_config.agent_mode.tools` |

---

## 四、Workflow vs Chatflow 终止节点差异

这是两种 Workflow 架构之间最关键的区别：

| 维度 | 工作流 (`workflow`) | Chatflow (`advanced-chat`) |
|------|:-------------------|:--------------------------|
| **终止节点类型** | `end` | `answer` |
| **WorkflowType** | `WorkflowType.WORKFLOW` | `WorkflowType.CHAT` |
| **终止节点结构** | `outputs: [{variable, value_selector}]` | `answer: "{{#node.var#}}"` |
| **系统变量** | 无对话变量 | `sys.query`, `sys.conversation_id`, `sys.dialogue_count` |

**End 节点示例**（工作流）:
```yaml
data:
  type: end
  title: 结束
  outputs:
  - variable: result
    value_selector: [llm_node, text]
```

**Answer 节点示例**（Chatflow）:
```yaml
data:
  type: answer
  title: 直接回复
  answer: "{{#llm_node.text#}}"
```

---

## 五、真实 DSL 示例参考

**用户导出的 Chatflow DSL**（`知识库 + 聊天机器人.yml`）:
- mode: `advanced-chat`
- 节点: 开始 → 知识检索 → LLM → 参数提取器 → 直接回复（Answer）
- 使用了 `knowledge-retrieval` 节点查询知识库
- 使用了 `parameter-extractor` 节点提取结构化参数
- 终止节点为 `answer` 类型，输出 `{{#参数提取器.answer#}}`

**工具生成的 Workflow DSL**（`resume_screener.yaml`）:
- mode: `workflow`
- 节点: Input → GPT-4o Resume Analyzer → Pass or Fail? → Candidate Passed / Failed
- 使用了 `if-else` 节点做条件路由
- 终止节点为 `end` 类型，定义 `outputs` 数组
