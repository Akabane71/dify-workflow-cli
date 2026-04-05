# Dify 前端检查清单机制分析

> 源码版本: dify-test (2026-04)
> 分析目标: 理解前端 "检查清单(32)" 面板的完整校验逻辑，指导 CLI 工具生成可直接运行的 DSL

---

## 1. 检查清单整体架构

前端检查清单由 `use-checklist.ts` 驱动，对每个节点执行三层检查：

```
useChecklist(nodes, edges)
  ↓
For each node:
  ① checkValid(data, t)        — 节点自身配置完整性
  ② 变量引用有效性              — 引用的上游变量是否存在
  ③ 连通性检查                  — 是否从 Start 节点可达
  ↓
ChecklistItem { id, type, title, unConnected, errorMessages[] }
```

### 关键源文件

| 文件 | 作用 |
|------|------|
| `hooks/use-checklist.ts` | 主逻辑：遍历节点，调用三层检查 |
| `utils/workflow.ts` → `getValidTreeNodes()` | 连通性判定：从 Start 出发 BFS |
| `nodes/*/default.ts` → `checkValid()` | 每个节点类型的配置校验 |
| `nodes/_base/components/variable/utils.ts` → `getNodeUsedVars()` | 提取节点引用的所有变量 |
| `hooks/use-nodes-available-var-list.ts` | 计算每个节点可用的上游变量列表 |

---

## 2. 第一层：节点配置完整性 (`checkValid`)

每个节点类型在 `default.ts` 中实现 `checkValid(payload, t)`，返回 `{ isValid, errorMessage }`。

### 各节点类型校验规则

| 节点类型 | 校验内容 | 前端报错信息 |
|---------|---------|-------------|
| **start** | 永远通过 | — |
| **end** | `outputs` 非空；每个 output 必须有 `variable`(trim 非空) 和 `value_selector`(数组且>0) | "输出变量 is required" |
| **llm** | `model.provider` 非空；prompt 非空（chat 模式检查 PromptItem[] 每项的 text 或 jinja2_text）；memory 时检查 query_prompt_template 含 `{{#sys.query#}}`；vision 启用时检查 variable_selector | "请配置模型" / "提示词 is required" |
| **code** | `variables` 中不能有空 `variable` 名；`variables` 中不能有空 `value_selector`；`code` 非空 | "变量 is required" / "代码 is required" |
| **if-else** | `cases` 非空；每个 case 的 `conditions` 非空；每个 condition 必须有 `variable_selector`、`comparison_operator`；非 empty 类操作符时 `value` 必填 | "IF is required" / "变量 is required" |
| **http-request** | `url` 非空；binary body 时检查 file 变量 | "API is required" |
| **question-classifier** | `query_variable_selector` 非空；`model.provider` 非空；`classes` 非空且每个 class 的 `name` 非空；vision 启用时检查 variable_selector | "输入变量 is required" / "请配置模型" |
| **parameter-extractor** | `query` 非空；`model.provider` 非空；`parameters` 非空；每个 param 的 `name`、`type`、`description` 非空；vision 启用时检查 variable_selector | "输入变量 is required" / "请配置模型" |
| **knowledge-retrieval** | `dataset_ids` 非空；oneWay 模式时检查 single_retrieval_config.model.provider；multiWay 时检查 rerank model | "知识库 is required" |
| **tool** | 先检查认证状态；遍历 required 输入参数必须有值；遍历 required 配置参数必须有值 | "认证 is required" / "{field} is required" |

### CLI 当前覆盖状态

CLI 的 `checklist_checks.py` 已覆盖大部分 checkValid 逻辑，但以下场景遗漏：
- ❌ 未检查 LLM prompt 非空（仅在 node_data_validator 里做了 warning）
- ❌ 未检查 Code 的 `code` 字段非空（已在 checklist 有）
- ✅ 其他节点类型的 checkValid 已对齐

---

## 3. 第二层：变量引用有效性

### 前端逻辑 (`use-checklist.ts` 第 238-264 行)

```typescript
// 1. 通过 getNodeUsedVars(node) 提取当前节点引用的所有变量
const usedVars = getNodeUsedVars(node).filter(v => v.length > 0)

// 2. 获取当前节点可用的上游变量列表
const availableVars = map[node.id].availableVars

// 3. 逐个检查引用的变量是否在可用列表中
for (const variable of usedVars) {
    if (isSpecialVar(variable[0]))  // sys, env, conversation, rag → 跳过
        continue
    const usedNode = availableVars.find(v => v.nodeId === variable[0])
    if (!usedNode || !usedNode.vars.some(v => v.variable === variable[1]))
        hasInvalidVar = true
}
```

### 变量引用格式

DSL 中变量引用通过两种方式：
1. **value_selector**: `["node_id", "variable_name"]` — 直接数组引用
2. **模板字符串**: `{{#node_id.variable_name#}}` — 在 prompt/url/headers 等文本中

### `getNodeUsedVars()` 提取规则

| 节点类型 | 提取位置 |
|---------|---------|
| end | `outputs[].value_selector` |
| answer | 从 `answer` 文本匹配 `{{#...#}}` |
| llm | 从 `prompt_template[].text` 匹配 `{{#...#}}` + `context.variable_selector` |
| code | `variables[].value_selector` |
| if-else | `cases[].conditions[].variable_selector` |
| http-request | 从 `url`, `headers`, `params`, `body.data` 匹配 `{{#...#}}` |
| question-classifier | `query_variable_selector` + 从 `instruction` 匹配 |
| parameter-extractor | `query` + 从 `instruction` 匹配 |
| knowledge-retrieval | `query_variable_selector` |
| tool | 从 tool_parameters 中提取 mixed(模板匹配) 和 variable(直接引用) |
| iteration | `iterator_selector` |
| loop | `break_conditions[].variable_selector` |

### 可用变量来源

`useNodesAvailableVarList` 计算每个节点可用的变量：
- 沿边反向遍历，收集所有上游节点的输出变量
- 包括 start 节点的用户输入变量
- 特殊变量 (`sys.*`, `env.*`, `conversation.*`, `rag.*`) 始终可用

### CLI 需要实现的检查

**核心规则**: 对每个节点提取其引用的所有变量 (value_selector 和模板引用)，检查：
1. 如果变量前缀是 `sys`/`env`/`conversation`/`rag` → 跳过
2. 否则，`variable[0]` 必须是图中存在的节点 ID
3. 该节点必须是当前节点的上游（可通过边从 start 可达 → 到当前节点路径上）

---

## 4. 第三层：连通性检查

### 前端逻辑 (`getValidTreeNodes`)

```typescript
function getValidTreeNodes(nodes, edges) {
    // 找到所有起始节点 (Start, TriggerSchedule, TriggerWebhook, TriggerPlugin)
    const startNodes = nodes.filter(n =>
        n.data.type === 'start' || n.data.type.startsWith('trigger-'))

    // 从每个起始节点出发，BFS 遍历所有可达节点
    const traverse = (root, depth) => {
        list.push(root)
        const outgoers = getOutgoers(root, nodes, edges)  // 找到所有直接后继
        outgoers.forEach(outgoer => {
            if (!visited) traverse(outgoer, depth + 1)
        })
    }

    return { validNodes, maxDepth }
}
```

### 判定规则

- **"此节点尚未连接到其他节点"** = 节点不在 validNodes 中
- Start 类型节点跳过连通性检查 (`canSkipConnectionCheck`)
- Iteration/Loop 的子节点自动视为已连接

### CLI 当前状态

CLI 的 `workflow/validator.py` 已有 `_validate_connectivity()` 函数做连通性检查，但那个报错信息是：
- `"Node {id} is not reachable from start node"` — 这和前端的检查逻辑一致

**但当前检查在 validate 命令里，不在 checklist 命令里。需要确认 checklist 也包含连通性检查。**

---

## 5. 截图中 32 个问题分类

根据截图中可见的错误信息：

| 错误信息 | 对应检查层 | 出现原因 |
|---------|-----------|---------|
| "此节点尚未连接到其他节点" | 第三层 - 连通性 | 节点存在但没有从 Start 可达的边路径 |
| "无效的变量，请选择一个已有的变量" | 第二层 - 变量引用 | value_selector 引用了不存在的节点或变量 |
| "知识库不能为空" | 第一层 - checkValid | dataset_ids 为空 |
| "请配置模型" | 第一层 - checkValid | model.provider 为空 |

---

## 6. CLI 实现方案

### 6.1 checklist 需要做的三层检查

```
checklist_checks.py (已有)    → 第一层: checkValid 对齐
checklist_validator.py (补充) → 第二层: 变量引用有效性
                              → 第三层: 连通性检查
```

### 6.2 变量引用检查实现要点

1. **解析节点引用的变量**: 
   - 从 `value_selector` 字段直接提取 `[node_id, var_name]`
   - 从文本字段 (prompt, url, headers, params, body.data) 正则匹配 `{{#node_id.var_name#}}`

2. **构建可用变量图**:
   - 从 Start 节点出发遍历边，记录每个节点的全部上游节点集合
   - 每个节点的输出变量已知（start 的 variables, code 的 outputs, llm 的 text, tool 的 result 等）

3. **校验**:
   - 跳过 `sys.*`, `env.*`, `conversation.*`, `rag.*`
   - 对每个引用 `[node_id, var_name]`：检查 node_id 是否存在且为上游

### 6.3 连通性检查实现要点

已有逻辑可复用，需在 checklist 输出中体现 "此节点尚未连接到其他节点"。
