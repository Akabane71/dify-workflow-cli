# CLI 校验覆盖度分析

> 对比 Dify 官方后端/前端校验 vs dify-workflow-cli 已实现的校验  
> 分析日期: 2026-04-08

## 一、当前校验层总览

| 校验层 | 文件 | 适用模式 | 覆盖度 |
|--------|------|---------|--------|
| DSL 元数据 | `validator.py` | 全部 | ✅ 基本 |
| 模式特定 | `chat/validator.py` 等 | 各自模式 | ⚠ 部分 |
| Graph 结构 | `workflow/validator.py` | workflow/chatflow | ✅✅✅ 优秀 |
| 前端崩溃预防 | `frontend_validator.py` | workflow/chatflow | ✅✅ 良好 |
| 发布检查清单 | `checklist_validator.py` | workflow/chatflow | ✅✅✅ 全面 |
| 节点数据 | `node_data_validator.py` | workflow/chatflow | ✅✅ 良好 |

---

## 二、Workflow/Chatflow 校验覆盖情况

### 已覆盖 ✅

- Graph 结构: 起始节点、终止节点、边合法、无环、可达性
- 节点数据: 22 种节点的字段完整性
- 前端崩溃: 所有 CRITICAL 级字段
- 发布检查: 变量引用、连接性、配置完整性
- 迭代/循环: 子节点归属、嵌套层级

### 结论

**Workflow/Chatflow 的校验已接近完整**，与 Dify 官方对齐良好。

---

## 三、Chat/Agent/Completion 校验缺口分析

### 3.1 model_config.model（模型配置）

| 检查项 | Dify 后端 | CLI 当前 | 缺口 |
|--------|:---------:|:--------:|:----:|
| model 存在且为 dict | ✅ | ✅ | — |
| model.provider 必填 | ✅ | ✅ | — |
| model.name 必填 | ✅ | ✅ | — |
| model.completion_params 为 dict | ✅ | ❌ | **缺** |
| completion_params.stop ≤ 4 项 | ✅ | ❌ | **缺** |
| provider 在可用列表中 | ✅ | ❌ | 跳过（需在线） |
| name 在 provider 模型列表中 | ✅ | ❌ | 跳过（需在线） |

### 3.2 user_input_form（用户输入表单）

| 检查项 | Dify 后端 | CLI 当前 | 缺口 |
|--------|:---------:|:--------:|:----:|
| 必须为列表 | ✅ | ❌ | **缺** |
| 类型枚举: text-input/select/paragraph/number/checkbox | ✅ | ❌ | **缺** |
| label 必填 | ✅ | ❌ | **缺** |
| variable 正则校验 | ✅ | ❌ | **缺** |
| variable 长度 1-100 | ✅ | ❌ | **缺** |
| select 的 options 校验 | ✅ | ❌ | **缺** |
| default 须在 options 中 | ✅ | ❌ | **缺** |

### 3.3 prompt_type & prompt_config

| 检查项 | Dify 后端 | CLI 当前 | 缺口 |
|--------|:---------:|:--------:|:----:|
| prompt_type 枚举 (simple/advanced) | ✅ | ❌ | **缺** |
| advanced 须有 chat/completion_prompt_config | ✅ | ❌ | **缺** |
| chat_prompt_config 最多 10 条 | ✅ | ❌ | **缺** |
| pre_prompt 非空（前端校验） | ✅ | ❌ | **缺** |

### 3.4 dataset_configs（知识库配置）

| 检查项 | Dify 后端 | CLI 当前 | 缺口 |
|--------|:---------:|:--------:|:----:|
| retrieval_model 枚举 (single/multiple) | ✅ | ❌ | **全缺** |
| dataset ID 为 UUID | ✅ | ❌ | **全缺** |
| Completion 模式 dataset_query_variable 必填 | ✅ | ❌ | **全缺** |

### 3.5 agent_mode（Agent 模式配置）

| 检查项 | Dify 后端 | CLI 当前 | 缺口 |
|--------|:---------:|:--------:|:----:|
| agent_mode 存在 | ✅ | ⚠ 仅警告 | 需升级 |
| enabled 为布尔值 | ✅ | ❌ | **缺** |
| strategy 枚举 | ✅ | ⚠ 仅检查 function_call/react | 缺 router/react-router |
| tool.provider_type 必填 | ✅ | ❌ | **缺** |
| tool.provider_id 必填 | ✅ | ❌ | **缺** |
| tool.tool_name 必填 | ✅ | ❌ | **缺** |
| tool.tool_parameters 必填 | ✅ | ❌ | **缺** |

### 3.6 Features（各类开关特性）

| Feature | Dify 后端 | CLI 当前 | 缺口 |
|---------|:---------:|:--------:|:----:|
| opening_statement (Chat/Agent) | ✅ 默认设 | ❌ | **缺** |
| suggested_questions (Chat/Agent) | ✅ 默认设 | ❌ | **缺** |
| suggested_questions_after_answer | ✅ 默认设 | ❌ | **缺** |
| speech_to_text (Chat/Agent) | ✅ 默认设 | ❌ | **缺** |
| text_to_speech (全模式) | ✅ 默认设 | ❌ | **缺** |
| retriever_resource (Chat/Agent) | ✅ 默认设 | ❌ | **缺** |
| more_like_this (Completion) | ✅ 默认设 | ❌ | **缺** |
| sensitive_word_avoidance (全模式) | ✅ 默认设 | ❌ | **缺** |
| file_upload (全模式) | ✅ Pydantic 验证 | ❌ | **缺** |

### 3.7 结构一致性

| 检查项 | Dify 后端 | CLI 当前 | 缺口 |
|--------|:---------:|:--------:|:----:|
| workflow 模式必须有 workflow.graph | 隐式 | ❌ | **缺** |
| chat/agent/completion 必须有 model_config | 隐式 | ❌ | **缺** |
| chat/agent/completion 不应有 workflow | 隐式 | ❌ | **缺** |

---

## 四、优先级排序

### P0 — 必须实现（导入会直接失败）

1. `user_input_form` 变量名正则校验  
2. `prompt_type` 枚举校验 + advanced 模式结构检查
3. `dataset_query_variable`（Completion 使用知识库时必填）
4. `agent_mode.tools` 必填字段校验（provider_type/id/tool_name/parameters）
5. 模式↔结构一致性（workflow 模式 ↔ workflow 字段，model_config 模式 ↔ model_config 字段）

### P1 — 应该实现（提升 DSL 质量）

6. `model.completion_params` 结构 + stop 长度检查
7. `dataset_configs.retrieval_model` 枚举校验
8. Features 存在性 + 默认值填充
9. `agent_mode.strategy` 完整枚举（补 router/react-router）

### P2 — 可以实现（锦上添花）

10. `file_upload` 结构校验
11. `sensitive_word_avoidance` 启用时 type 必填
12. `text_to_speech` 启用时 voice/language 检查
13. 变量名唯一性检查

### P3 — 暂缓（需在线或极少触发）

14. Provider/Model 在线存在性验证
15. Dataset ID 在线存在性验证
16. ExternalDataTool 配置校验
17. ModerationFactory 配置校验
