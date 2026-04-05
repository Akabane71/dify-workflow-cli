# Dify 节点输出变量映射研究

## 背景

Dify 前端通过 `getNodeInfoById()` 函数（位于 `variable/utils.ts`）来确定每种节点类型的输出变量列表。  
当 `value_selector` 引用某节点的输出时，前端检查该输出变量名是否存在于该节点类型的输出列表中。  
如果不存在，视为无效引用。

本文档汇总每种节点类型的**固定输出变量名**，供 CLI `_build_node_outputs()` 对齐使用。

## 数据来源

- **常量定义**: `web/app/components/workflow/constants.ts`
- **输出构建逻辑**: `web/app/components/workflow/nodes/_base/components/variable/utils.ts` → `getNodeInfoById()`

---

## 节点输出变量映射表

| 节点类型 (NodeType) | DSL type 值 | 固定输出变量 | 动态输出 | 说明 |
|---|---|---|---|---|
| Start | `start` | 用户定义的 `variables[].variable` | 是 | 另有 `sys.query`(聊天模式)、`sys.files` |
| LLM | `llm` | `text`, `reasoning_content`, `usage` | 可选 `structured_output` | structured_output 需 enabled |
| Knowledge Retrieval | `knowledge-retrieval` | `result` | 否 | 类型为 arrayObject |
| Code | `code` | 用户定义的 `outputs` 字典键 | 是 | — |
| Template Transform | `template-transform` | `output` | 否 | 类型为 string |
| Question Classifier | `question-classifier` | `class_name`, `usage` | 否 | — |
| HTTP Request | `http-request` | `body`, `status_code`, `headers`, `files` | 否 | — |
| Tool | `tool` | `text`, `files`, `json` | 可选（插件 schema） | 不是 `result` |
| Parameter Extractor | `parameter-extractor` | `__is_success`, `__reason`, `__usage` | 是（用户定义参数名） | — |
| Iteration | `iteration` | `output` | 否 | 类型由 output_type 决定 |
| Loop | `loop` | 用户定义的 `loop_variables[].label` | 是 | 无固定 `output` |
| Variable Assigner | `assigner` | `output` | 否 | 分组模式下有 group_name.output |
| Variable Aggregator | `variable-aggregator` | `output` | 否 | 同 assigner |
| Document Extractor | `doc-extractor` | `text` | 否 | is_array_file 时类型为 arrayString |
| List Filter/Operator | `list-operator` | `result`, `first_record`, `last_record` | 否 | — |
| Agent | `agent` | `text`, `files`, `json`, `usage` | 可选（output_schema） | 继承 TOOL_OUTPUT_STRUCT + AGENT_OUTPUT_STRUCT |
| IF/ELSE | `if-else` | 无 | 否 | 纯路由节点 |
| End | `end` | 无 | 否 | 终端节点 |
| Answer | `answer` | 无 | 否 | 终端节点 |
| Human Input | `human-input` | `__action_id`, `__rendered_content` | 是（插件 schema） | — |
| DataSource | `datasource` | 动态（插件 schema） | 是 | — |

---

## 关键发现

### 1. Tool 节点输出是 `text`，不是 `result`

**这是最常见的错误。** Tool 节点的固定输出为：
```
text    (string)   — 工具执行的文本结果
files   (arrayFile) — 工具产生的文件列表
json    (arrayObject) — 工具返回的 JSON 数据
```

源码证据（`constants.ts`）：
```typescript
export const TOOL_OUTPUT_STRUCT: Var[] = [
  { variable: 'text', type: VarType.string },
  { variable: 'files', type: VarType.arrayFile },
  { variable: 'json', type: VarType.arrayObject },
]
```

### 2. LLM 节点有三个固定输出

```
text               (string) — 生成文本
reasoning_content  (string) — 推理过程
usage              (object) — token 用量
```

可选第四个：`structured_output`（需 `structured_output_enabled: true`）。

### 3. Question Classifier 有数据输出

不是纯路由节点，输出 `class_name` (string) 和 `usage` (object)。

### 4. Loop 与 Iteration 输出不同

- **Iteration**: 固定输出 `output`
- **Loop**: 只输出用户定义的 `loop_variables[].label`，**没有** 固定 `output`

### 5. Agent 节点继承 Tool + 额外 usage

Agent 输出 = `output_schema` 动态字段 + `TOOL_OUTPUT_STRUCT`(`text`, `files`, `json`) + `AGENT_OUTPUT_STRUCT`(`usage`)。

---

## CLI _build_node_outputs() 需要的修正

| 节点类型 | 当前 CLI 输出 | 正确输出 |
|---|---|---|
| Tool | `{"*"}` (通配符) | `{"text", "files", "json"}` |
| LLM | `{"text"}` | `{"text", "reasoning_content", "usage"}` |
| Question Classifier | `pass` (空) | `{"class_name", "usage"}` |
| HTTP Request | `{"body", "status_code", "headers"}` | `{"body", "status_code", "headers", "files"}` |
| Loop | `{"output", ...loop_vars}` | `{...loop_vars}`（去掉固定 output） |
| Agent | `{"text"}` | `{"text", "files", "json", "usage"}` |
| Parameter Extractor | `{param_names}` | `{param_names, "__is_success", "__reason", "__usage"}` |
| List Operator | 未处理 | `{"result", "first_record", "last_record"}` |
| Variable Assigner | 未处理 | `{"output"}` |
| Variable Aggregator | 未处理 | `{"output"}` (暂不处理分组) |
| Human Input | `{"form_data", action_ids}` | `{"__action_id", "__rendered_content"}` + 动态 |

---

## 示例 YAML 需要修正的引用

`enterprise_customer_service_ticket_workflow.yaml` 中以下引用错误：

| 位置 | 错误引用 | 被引用节点类型 | 正确引用 |
|---|---|---|---|
| end_consult_handoff.value_selector | `consult_handoff_node.result` | Tool | `consult_handoff_node.text` |
| end_fault_ticket.value_selector | `fault_notify_node.result` | Tool | `fault_notify_node.text` |
| end_complaint_high.value_selector | `complaint_supervisor_node.result` | Tool | `complaint_supervisor_node.text` |
| end_complaint_ticket.value_selector | `complaint_create_node.result` | Tool | `complaint_create_node.text` |
| fault_extract_node 模板 | `fault_extract_node.result` | Tool | `fault_extract_node.text` |
| fault_solution_node 模板 | `fault_monitor_node.result` | Tool | `fault_monitor_node.text` |
| fault_ticket_node 模板 | `fault_monitor_node.result` | Tool | `fault_monitor_node.text` |
| fault_notify 模板 | `fault_ticket_node.result` | Tool | `fault_ticket_node.text` |

注意：`consult_kb_node.result` 是 Knowledge Retrieval 节点，`result` 是**正确的**输出名。
