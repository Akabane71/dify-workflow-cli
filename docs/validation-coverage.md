# DSL 校验覆盖对照表

本文档详细对比 CLI 工具 `dify-workflow validate` 命令与 Dify 官方导入/运行时校验的覆盖范围。

## 1. 校验架构概述

### Dify 官方的三层校验

| 层级 | 时机 | 覆盖范围 | CLI 是否覆盖 |
|------|------|---------|-------------|
| **导入校验** | DSL 文件导入时 (`app_dsl_service.py`) | YAML 解析、版本检查、app 字段、环境变量、HumanInput 深度校验 | ✅ 全部覆盖 |
| **图结构校验** | 工作流保存时 (`workflow_service.py`) | Start/trigger 互斥、HumanInput Pydantic 校验 | ✅ 全部覆盖 + 额外检查 |
| **运行时校验** | 节点构造时 (graphon `Node.validate_node_data()`) | 每种节点的 Pydantic model_validate | ✅ 等效覆盖 |
| **前端渲染校验** | 前端 React 组件渲染时 (`nodes/*/node.tsx`, `initialNodes()`) | 组件直接解构 node.data 属性，缺失即白屏 | ✅ `frontend_validator.py` |
| **发布检查清单** | 前端 `use-checklist.ts` hook | 节点配置完整性 + 变量引用有效性 | ✅ `checklist_validator.py` |

### CLI 额外提供（Dify 不检查的）

| 检查项 | CLI 命令 | 说明 |
|--------|---------|------|
| 重复节点 ID | `validate` | Dify 导入时不检查 |
| 自环边检测 | `validate` | Dify 导入时不检查 |
| 重复边 ID | `validate` | Dify 导入时不检查 |
| 连通性分析（孤立节点） | `validate` | Dify 导入时不检查 |
| Start/End 节点存在性 | `validate` | Dify 导入时不检查 |
| 节点标题缺失 | `validate` | Dify 导入时不检查 |
| Chatflow Answer 节点检查 | `validate` | Dify 导入时不检查 |
| 前端崩溃预防 (16 种节点) | `validate` | 前端不校验字段完整性，缺失即白屏 |
| 发布检查清单 (17 种节点) | `validate` / `checklist` | 节点配置完整性 + 跨节点变量引用验证 |

---

## 2. 导入层校验对照

### app_dsl_service.py 检查项

| # | Dify 检查项 | Dify 代码位置 | CLI 状态 | 说明 |
|---|-----------|------------|---------|------|
| 1 | YAML 解析正确性 | `app_dsl_service.py:202` | ✅ | 加载时自动检查 |
| 2 | 数据必须为 dict | `app_dsl_service.py:203` | ✅ | Pydantic 模型加载 |
| 3 | `version` 类型必须为 str | `app_dsl_service.py:216` | ✅ | `validate_dsl_metadata()` |
| 4 | 版本兼容性检查 (semver) | `app_dsl_service.py:83-101` | ✅ | 版本高于 0.6.0 会警告 |
| 5 | `app` section 存在 | `app_dsl_service.py:221` | ✅ | 顶层校验 |
| 6 | `app.mode` 有效性 | `app_dsl_service.py:436` | ✅ | AppMode 枚举 |
| 7 | `icon_type` 枚举 (emoji/image/link) | `app_dsl_service.py:442` | ✅ | `validate_dsl_metadata()` |
| 8 | workflow/advanced-chat 需要 `workflow` 字段 | `app_dsl_service.py:498` | ✅ | 模式校验 |
| 9 | chat/agent/completion 需要 `model_config` | `app_dsl_service.py:529` | ✅ | 模式校验 |
| 10 | `environment_variables` name/value_type 校验 | `variable_factory.py:59-79` | ✅ | `validate_dsl_metadata()` |
| 11 | `conversation_variables` name/value_type | `variable_factory.py:53` | ✅ | `validate_dsl_metadata()` |
| 12 | 目标应用必须为 workflow/advanced-chat（覆盖导入） | `app_dsl_service.py:244` | ⬜ | 服务端限制，CLI 无需 |
| 13 | URL 导入 max 10MB | `app_dsl_service.py:172` | ⬜ | 服务端限制 |
| 14 | 加密 dataset_ids 解密 | `app_dsl_service.py:513` | ⬜ | 需要 AES key |
| 15 | `PluginDependency.model_validate()` | `app_dsl_service.py:282` | ⬜ | 大多数 DSL 无依赖 |

### workflow_service.py 检查项

| # | Dify 检查项 | Dify 代码位置 | CLI 状态 | 说明 |
|---|-----------|------------|---------|------|
| 16 | 空图允许通过 | `workflow_service.py:1397` | ✅ | |
| 17 | Start + trigger 不共存 | `workflow_service.py:1411` | ✅ | |
| 18 | HumanInput Pydantic 深度校验 | `workflow_service.py:1431` | ✅ | 含 delivery_methods UUID、inputs output_variable_name 等 |
| 19 | Features 结构校验 (file_upload 等) | `workflow_service.py:265` | ⬜ | 依赖 ConfigManager 类 |
| 20 | LLM model provider/credentials 校验 | `workflow_service.py:478` | ⬜ | 需要服务端 provider 列表 |
| 21 | Tool credentials 策略校验 | `workflow_service.py:398` | ⬜ | 需要 DB |
| 22 | Billboard 触发节点数限制 | `workflow_service.py:375` | ⬜ | 服务端计费限制 |

> ⬜ = 服务端专属功能，CLI 作为本地工具无需实现

---

## 3. 节点数据校验对照（运行时层）

### 全节点覆盖状态

| 节点类型 | 必填字段校验 | 枚举值校验 | 深度 validator | CLI 状态 |
|---------|------------|----------|---------------|---------|
| **start** | variables | VariableEntityType | 去重 | ✅ |
| **end** | outputs | — | — | ✅ |
| **answer** | answer | — | — | ✅ |
| **llm** | model, prompt_template | — | context 存在 | ✅ |
| **code** | code, code_language, variables, outputs | python3/javascript, `def main()`/`function main()` 函数签名, 参数匹配 variables, outputs dict 结构, Output.type ∈ _ALLOWED_OUTPUT_FROM_CODE | ✅ |
| **if-else** | cases | — | — | ✅ |
| **template-transform** | template | — | — | ✅ |
| **http-request** | url, method | method 枚举 | authorization.type/config, body.type | ✅ |
| **tool** | provider_id, tool_name | provider_type 枚举 | tool_configurations 类型, tool_parameters type/value 交叉校验 | ✅ |
| **knowledge-retrieval** | dataset_ids | — | — | ✅ |
| **question-classifier** | model, classes | — | query_variable_selector | ✅ |
| **parameter-extractor** | model, query, parameters | reasoning_mode | ParameterConfig.name 非空/非保留, type ∈ _VALID_PARAMETER_TYPES | ✅ |
| **variable-aggregator** | output_type | — | — | ✅ |
| **assigner** (v1) | assigned_variable_selector, write_mode, input_variable_selector | write_mode 枚举 | — | ✅ |
| **assigner** (v2) | — | — | — | ✅ |
| **list-operator** | filter_by, order_by, limit | — | — | ✅ |
| **iteration** | iterator_selector, output_selector | — | — | ✅ |
| **loop** | loop_count, break_conditions | logical_operator | loop_variables[].var_type ∈ _VALID_VAR_TYPE | ✅ |
| **agent** | strategy_provider/name/label | — | agent_parameters | ✅ |
| **document-extractor** | variable_selector | — | — | ✅ |
| **human-input** | — | timeout_unit, button_style | inputs[].output_variable_name 必填/去重, delivery_methods[].id UUID, user_actions[].id 标识符/去重, default.selector 长度, email config | ✅ |
| **knowledge-index** | — | — | — | ✅ |
| **datasource** | plugin_id, provider_name, provider_type | — | — | ✅ |
| **trigger-webhook** | — | — | — | ✅ |
| **trigger-schedule** | — | — | — | ✅ |
| **trigger-plugin** | plugin_id, provider_id, event_name | — | — | ✅ |

### 通用 BaseNodeData 校验（适用于所有节点）

| 字段 | 校验内容 | CLI 状态 |
|------|---------|---------|
| `error_strategy` | 必须为 `"fail-branch"` 或 `"default-value"` | ✅ |
| `default_value[].type` | 必须为 string/number/object/array[number]/array[string]/array[object]/array[file] | ✅ |
| `default_value[].key` | 必填 | ✅ |
| `default_value[].value` | 类型必须与声明的 type 匹配（数字/字典/数组等） | ✅ |

---

## 4. 详细校验规则参考

### 4.1 HumanInput 节点（Dify 唯一导入时校验的节点）

```
inputs[]:
  ├── type         → 必须为 "text_input" 或 "paragraph"
  ├── output_variable_name → 必填，不可重复
  └── default:
      ├── type     → "variable" 或 "constant"
      └── selector → type=variable 时长度 ≥ 2

user_actions[]:
  ├── id           → 必填，≤20 字符，标识符格式 ^[A-Za-z_][A-Za-z0-9_]*$，不可重复
  ├── title        → ≤20 字符（警告）
  └── button_style → primary/default/accent/ghost

delivery_methods[]:
  ├── id           → 必须为有效 UUID
  ├── type         → "webapp" 或 "email"
  └── config       → email 类型需含 recipients/subject/body

timeout_unit       → "hour" 或 "day"
```

### 4.2 ParameterExtractor 参数校验

```
parameters[]:
  ├── name → 必填，不可为 "__reason" 或 "__is_success"
  └── type → string/number/boolean/bool/select/array[string]/array[number]/array[object]/array[boolean]
```

### 4.3 HTTP Request 校验

```
authorization:
  ├── type   → "no-auth" 或 "api-key"
  └── config → api-key 时必须为 dict
      └── config.type → "basic"/"bearer"/"custom"

body:
  └── type → none/form-data/x-www-form-urlencoded/raw-text/json/binary
```

### 4.4 Tool 节点校验

```
provider_type       → plugin/builtin/workflow/api/app/dataset-retrieval/mcp
tool_configurations → 必须为 dict，值只能是 str/int/float/bool
tool_parameters:
  ├── type  → "mixed"/"variable"/"constant"
  └── value → mixed→str, variable→list[str], constant→scalar/dict/list
```

### 4.5 Code 节点输出类型

```
outputs.{name}.type → string/number/object/boolean/array[string]/array[number]/array[object]/array[boolean]
```

### 4.6 Loop 变量类型

```
loop_variables[].var_type → string/number/object/boolean/array[string]/array[number]/array[object]/array[boolean]
```

---

## 5. 不覆盖项及原因

以下检查项属于 Dify 服务端专属功能，CLI 作为独立本地工具无需实现：

| 检查项 | 原因 |
|--------|------|
| LLM model provider 是否存在 | 需要服务端 provider 注册表 |
| LLM model credentials 有效 | 需要 DB 存储的密钥 |
| Tool credentials 策略 | 需要 workspace 配置 |
| Dataset ID 解密 | 需要 AES key + tenant_id |
| Billboard 节点数限制 | 计费系统限制 |
| 覆盖导入目标 app 类型检查 | 服务端 API 限制 |
| URL 导入大小限制 | 服务端网络限制 |
| Features ConfigManager 校验 | 依赖运行时 ConfigManager 类链 |
| PluginDependency model_validate | 绝大多数 DSL 无 dependencies |

---

## 6. 前端崩溃预防校验（`frontend_validator.py`）

Dify 前端不校验节点 data 字段完整性，组件直接解构并访问深层属性。字段缺失时 React 崩溃白屏。
CLI 通过 `frontend_validator.py` 模块在生成阶段拦截这些问题。

详细分析见 `docs/dify-dsl研究/前端DSL校验与崩溃分析.md`。

### 崩溃风险等级

| 等级 | 节点类型 | 缺失字段 | 崩溃位置 |
|------|---------|----------|---------|
| CRITICAL | start | `variables` | `start/node.tsx`: `variables.length` |
| CRITICAL | if-else | `cases` | `initialNodes()` + `if-else/node.tsx`: `cases.map()` |
| CRITICAL | llm | `model` | `initialNodes()`: `data.model.provider` |
| CRITICAL | question-classifier | `model` / `classes` | `initialNodes()` + `node.tsx` |
| CRITICAL | parameter-extractor | `model` | `initialNodes()`: `data.model.provider` |
| HIGH | human-input | `delivery_methods` / `user_actions` | `node.tsx`: `.length` |
| HIGH | tool | `tool_configurations[key].value` 格式 | `tool/node.tsx` |
| HIGH | variable-assigner | `advanced_settings.groups` | `node.tsx`: `groups.map()` |
| MODERATE | list-operator | `filter_by.conditions` 类型 | `panel.tsx`: `conditions[0]` |
| LOW | answer / http-request / code / knowledge-retrieval | — | 安全（有 null 保护） |

### 校验覆盖

| 节点类型 | 校验内容 | CLI 状态 |
|---------|---------|---------|
| start | `variables` 必须是数组 | ✅ |
| if-else | `cases` 非空数组 + 每个 case 有 `case_id` 和 `conditions` | ✅ |
| llm | `model` 对象存在 + `provider` 非空 | ✅ |
| question-classifier | `model` 对象 + `classes` 数组 + 每项有 `id` | ✅ |
| parameter-extractor | `model` 对象存在 | ✅ |
| human-input | `delivery_methods` 和 `user_actions` 是数组 | ✅ |
| tool | v2 版本 `tool_configurations` 值包含 `value` 字段 | ✅ |
| variable-assigner | `group_enabled=true` 时 `groups` 是数组 | ✅ |
| list-operator | `filter_by.conditions` 是数组 | ✅ |
| iteration | `is_parallel` 是布尔值 | ✅ |

---

## 7. 测试覆盖

### 后端 schema 校验（`tests/test_node_data_validator.py`，69 个测试）

| 测试类 | 数量 | 覆盖内容 |
|--------|------|---------|
| TestHumanInputValidation | 17 | output_variable_name、UUID、标识符、去重、枚举值、email config、组合错误 |
| TestHumanInputSelectorValidation | 3 | FormInputDefault selector 长度校验 |
| TestLLMValidation | 2 | model 必填 |
| TestCodeValidation | 9 | code_language 枚举、def main 签名、function main 签名、参数-变量匹配、output type 合法性 |
| TestCodeOutputTypeValidation | 2 | 输出类型枚举 |
| TestHTTPRequestValidation | 2 | method、URL |
| TestHTTPRequestAuthValidation | 7 | auth type、config、body type |
| TestToolValidation | 5 | provider_type、tool_parameters type/value 交叉校验 |
| TestParameterExtractorValidation | 5 | reasoning_mode、name 保留/空、type 枚举 |
| TestVariableAssignerValidation | 1 | write_mode 枚举 |
| TestLoopValidation | 2 | logical_operator、var_type |
| TestBaseNodeDataValidation | 7 | error_strategy、default_value 类型校验 |
| TestDSLMetadataValidation | 5 | icon_type、版本兼容、env/conv 变量 |
| 其他 | 9 | End/Answer/QuestionClassifier/Start/NoValidation |

### 前端崩溃预防校验（`tests/test_frontend_validator.py`，43 个测试）

| 测试类 | 数量 | 覆盖内容 |
|--------|------|---------|
| TestFeStartNode | 3 | 缺 variables 崩溃、空数组合法、有变量合法 |
| TestFeIfElseNode | 5 | 缺 cases 崩溃、旧格式兼容、conditions/case_id 校验、完整合法 |
| TestFeLLMNode | 3 | 缺 model 崩溃、空 provider 警告、完整合法 |
| TestFeQuestionClassifierNode | 4 | 缺 model/classes 崩溃、classes 缺 id、完整合法 |
| TestFeParameterExtractorNode | 2 | 缺 model 崩溃、有 model 合法 |
| TestFeHumanInputNode | 5 | 缺 delivery_methods/user_actions 崩溃、非数组检测、空数组合法 |
| TestFeToolNode | 3 | v2 缺 value 警告、有 value 合法、无配置合法 |
| TestFeVariableAssignerNode | 4 | group_enabled 缺 groups/非数组崩溃、有 groups 合法、无设置合法 |
| TestFeCodeNode | 2 | None 合法、空数组合法 |
| TestFeListOperatorNode | 2 | conditions 非数组崩溃、数组合法 |
| TestFeSafeNodes | 4 | end/answer/http-request/knowledge-retrieval 无错误 |
| TestFeUnregisteredNodes | 3 | template-transform/document-extractor/agent 无错误 |
| TestFeIterationNode | 3 | is_parallel 非布尔警告、布尔合法、loop 空返回 |
