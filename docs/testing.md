# 测试说明与结果

## 1. 测试结构

```
tests/
├── test_models.py              # 模型测试 (20 个)
├── test_editor.py              # 图编辑操作测试 (49 个)
├── test_validator.py           # 校验逻辑测试 (16 个，含环检测)
├── test_node_data_validator.py # 节点数据校验测试 (76 个)
├── test_frontend_validator.py  # 前端崩溃预防校验测试 (43 个)
├── test_layout.py              # 自动布局引擎测试 (37 个，含 5 种策略)
├── test_checklist_validator.py # 发布检查清单校验测试 (47 个)
├── test_io.py                  # 文件读写测试 (13 个)
├── test_cli.py                 # CLI 命令行测试 (46 个，含端到端)
├── test_integration.py         # 集成测试 + 真实 fixture 校验 (19 个)
├── test_chatflow.py            # Chatflow 模块测试 (8 个)
├── test_chat.py                # 聊天助手模块测试 (19 个)
├── test_agent.py               # Agent 模块测试 (15 个)
└── test_completion.py          # 文本生成模块测试 (11 个)
                                ──────
                                共 419 个测试
```

## 2. 测试通过结果

```
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2
collected 419 items

tests/test_agent.py               15 passed
tests/test_chat.py                19 passed
tests/test_chatflow.py             8 passed
tests/test_checklist_validator.py  47 passed
tests/test_cli.py                 46 passed
tests/test_completion.py          11 passed
tests/test_editor.py              49 passed
tests/test_frontend_validator.py  43 passed
tests/test_integration.py         19 passed
tests/test_io.py                  13 passed
tests/test_layout.py              37 passed
tests/test_models.py              20 passed
tests/test_node_data_validator.py 76 passed
tests/test_validator.py           16 passed

========================= 419 passed in 1.02s =================================
```

## 3. 核心模块测试覆盖

### test_models.py — 数据模型验证 (20 个)

| 测试类 | 覆盖内容 |
|--------|---------|
| TestNodeType | 25 种节点类型全覆盖 |
| TestPosition | 默认值、自定义坐标 |
| TestStartVariable | 变量创建、标签自动填充 |
| TestNodeData | start/end/llm 节点数据、extra 字段 |
| TestNode | 基本创建、自动 ID 生成 |
| TestEdge | 自动 ID 生成、自定义 handle |
| TestGraph | 空图、含节点 |
| TestDifyWorkflowDSL | 默认值、序列化 round-trip、DifyDSL 统一模型 |

### test_editor.py — 图编辑操作验证 (49 个)

| 测试类 | 覆盖内容 |
|--------|---------|
| TestAddNode | 各类型节点添加、自定义 ID/位置/数据覆盖、自动布局 |
| TestRemoveNode | 删除已有节点（含连线清理）、删除不存在节点 |
| TestGetNode | 查找存在/不存在节点 |
| TestUpdateNode | 更新字段、不存在节点 |
| TestSetNodeTitle | 设置标题 |
| TestAddStartVariable | 添加变量到 start 节点、拒绝其他类型 |
| TestAddEndOutput | 添加输出到 end 节点、拒绝其他类型 |
| TestAddEdge | 正常添加、不存在节点 |
| TestRemoveEdge | 正常删除、不存在 |
| TestCreateMinimalWorkflow | 默认/自定义/带输入变量 |
| TestCreateLlmWorkflow | 默认/自定义模型 |

### test_validator.py — 校验逻辑验证 (16 个)

| 测试类 | 覆盖内容 |
|--------|--------|
| TestValidateMinimalWorkflow | 合法最小工作流、空图 |
| TestValidateTopLevel | 缺失 version、缺失 app.name |
| TestValidateGraphStructure | 重复 ID、无 start、start+trigger 共存、缺少 end |
| TestValidateNodes | LLM 缺 model、重复变量名 |
| TestValidateEdges | 边引用不存在节点、自环、**环检测**、无环无误报 |
| TestValidateConnectivity | 孤立节点检测 |
| TestValidationResult | 结果序列化 |

### test_node_data_validator.py — 节点数据校验 (76 个)

| 测试类 | 覆盖内容 |
|--------|---------|
| TestHumanInputValidation | output_variable_name 必填、delivery_methods UUID 校验、user_actions 标识符、重复检测、button_style、timeout_unit、email config、组合错误复现 |
| TestHumanInputSelectorValidation | FormInputDefault selector 长度校验 |
| TestLLMValidation | 默认合法、缺 model 报错 |
| TestCodeValidation | 无效 code_language 报错、python3 合法 |
| TestCodeOutputTypeValidation | 输出类型枚举校验 (graphon _ALLOWED_OUTPUT_FROM_CODE) |
| TestHTTPRequestValidation | 无效 method 报错、缺 URL 警告 |
| TestHTTPRequestAuthValidation | auth type、config 必填、auth config type、body type 枚举 |
| TestToolValidation | provider_type 枚举、tool_parameters type/value 交叉校验 |
| TestEndNodeValidation | 默认合法、缺 outputs 报错 |
| TestAnswerNodeValidation | 默认合法 |
| TestQuestionClassifierValidation | 缺 model、缺 classes 报错 |
| TestParameterExtractorValidation | reasoning_mode、name 保留/空、type 枚举、全部合法类型 |
| TestVariableAssignerValidation | 无效 write_mode v1 报错 |
| TestLoopValidation | 无效 logical_operator、loop_variables var_type 枚举 |
| TestBaseNodeDataValidation | error_strategy 枚举、default_value 类型校验 (7 个场景) |
| TestStartNodeValidation | 重复变量名 |
| TestNoValidationNodes | trigger-webhook/schedule/knowledge-index 无错误 |
| TestDSLMetadataValidation | icon_type、版本兼容、env/conv 变量 |

### test_frontend_validator.py — 前端崩溃预防校验 (43 个)

| 测试类 | 覆盖内容 |
|--------|---------|
| TestFeStartNode | 缺 variables 崩溃检测、空数组合法、有变量合法 |
| TestFeIfElseNode | 缺 cases 崩溃检测、旧格式兼容、空 conditions 合法、空 case_id 检测、完整合法 |
| TestFeLLMNode | 缺 model 崩溃检测、空 provider 警告、完整合法 |
| TestFeQuestionClassifierNode | 缺 model/classes 崩溃检测、classes 缺 id 检测、完整合法 |
| TestFeParameterExtractorNode | 缺 model 崩溃检测、有 model 合法 |
| TestFeHumanInputNode | 缺 delivery_methods/user_actions 崩溃检测、非数组类型检测、空数组合法 |
| TestFeToolNode | v2 配置缺 value 警告、有 value 合法、无版本无配置合法 |
| TestFeVariableAssignerNode | group_enabled 缺 groups 崩溃检测、groups 非数组检测、有 groups 合法、无 advanced_settings 合法 |
| TestFeCodeNode | None variables 合法、空数组合法 |
| TestFeListOperatorNode | conditions 非数组崩溃检测、数组合法 |
| TestFeSafeNodes | end/answer/http-request/knowledge-retrieval 安全节点无错误 |
| TestFeUnregisteredNodes | template-transform/document-extractor/agent 无错误 |
| TestFeIterationNode | is_parallel 非布尔警告、布尔合法、loop 节点空返回 |

### test_layout.py — 自动布局引擎 (37 个)

| 测试类 | 覆盖内容 |
|--------|--------|
| TestAutoLayout | 空 DSL、4 种策略、位置写入 DSL、分支分离 |
| TestTopoOrder | 简单链、扇出、循环容错、断连节点 |
| TestAssignLayers | 链式/菱形/扇出/孤立节点/最长路径分层 |
| TestMinimizeCrossings | 无交叉保持、单层不变 |
| TestLayoutLinear | 水平排列、间距正确 |
| TestLayoutDag | 水平/垂直方向、扇出垂直展开、菱形合并、紧凑间距 |
| TestBuildBranchOrder | if-else 分支顺序、普通节点边序 |
| TestTreeLayout | 线性链、分支分组、四路分支、无重叠、位置应用到 DSL |
| TestLayoutIntegration | 无重叠验证、5 策略全覆盖、断连节点、复杂工作流 |

### test_io.py — 文件读写验证 (13 个)

| 测试类 | 覆盖内容 |
|--------|---------|
| TestSaveAndLoad | YAML/JSON 保存、加载、round-trip、文件不存在、无效内容 |
| TestStringIO | 字符串 YAML/JSON 序列化和反序列化 |

## 4. CLI 测试覆盖

### test_cli.py — 命令行接口 (46 个)

| 测试类 | 覆盖命令 |
|--------|--------|
| TestCreateCommand | create: workflow (minimal/llm/if-else)、chatflow、chat、agent、completion、JSON 输出 |
| TestValidateCommand | validate: 通过/失败/不存在文件 |
| TestInspectCommand | inspect: 文本/JSON/Mermaid 输出、workflow 和 config 模式 |
| TestExportCommand | export: yaml/json/stdout |
| TestEditCommands | edit: add-node/remove-node/update-node/add-edge/set-title |
| TestConfigCommands | config: set-model/set-prompt/add-variable/set-opening/add-question/add-tool/remove-tool |
| TestDiffCommand | 相同文件/不同文件/JSON 输出 |
| TestImportCommand | import: 保存/仅校验 |
| TestChecklistCommand | checklist: 清单校验、JSON 输出 |
| TestLayoutCommand | layout: tree/hierarchical 策略、输出文件 |
| **TestEndToEnd** | **create → add-node → add-edge → validate → inspect → export** |

## 5. 集成测试覆盖

### test_integration.py — 端到端场景 (19 个)

| 测试类 | 覆盖场景 |
|--------|---------|
| TestCreateAndExportWorkflow | 创建 → 校验 → 保存 → 重载验证（minimal/llm） |
| TestEditExistingWorkflow | 加载 → 添加节点 → 改连线 → 保存 → 验证 |
| | 加载 → 删除节点 → 连线自动清理 → 验证 |
| | 加载 → 修改 LLM model → 保存 → 验证 |
| TestInvalidWorkflowDetection | 无 start 被拦截、边引用不存在节点被拦截、trigger+start 冲突 |
| TestRoundTripExportImport | YAML round-trip、JSON round-trip、跨格式转换、字段无丢失 |
| **TestDifyFixtureValidation** | **使用 dify-test 真实 fixture 校验** |

### 真实 Fixture 校验

```python
class TestDifyFixtureValidation:
    test_fixtures_exist          # 确认 dify-test fixture 可达
    test_load_all_fixtures       # 加载全部真实 fixture 文件
    test_basic_llm_fixture       # 精确校验 basic_llm_chat_workflow.yml
    test_simple_passthrough      # 精确校验 simple_passthrough_workflow.yml
    test_conditional_fixture     # 精确校验 conditional_hello_branching_workflow.yml
    test_fixture_roundtrip       # load → save → reload，数据不丢失
    test_fixture_validate        # 对真实 fixture 运行 validate，0 error
```

## 6. 新增模式模块测试覆盖

### test_chatflow.py — Chatflow 模块 (8 个)

| 测试类 | 覆盖内容 |
|--------|---------|
| TestCreateChatflow | 基本 chatflow 创建、mode 检查、Answer 节点、knowledge 模板、LLM memory |
| TestChatflowValidation | 合法 chatflow 校验、无 Answer 节点警告、LLM memory 建议 |

### test_chat.py — 聊天助手模块 (19 个)

| 测试类 | 覆盖内容 |
|--------|---------|
| TestCreateChatApp | 基本创建、model_config 存在性、自定义 prompt、开场白 |
| TestChatEditing | set_model、set_prompt、add_user_variable（单个/多个）、set_opening_statement、add_suggested_question、configure_dataset、enable_feature、空 DSL 上 set_model |
| TestChatIO | YAML round-trip、model_config 键序列化正确性 |
| TestChatValidation | 合法 chat 校验、无 model_config 报错、缺 model 警告、agent_mode 警告 |

### test_agent.py — Agent 模块 (15 个)

| 测试类 | 覆盖内容 |
|--------|---------|
| TestCreateAgentApp | 基本 agent 创建、react 策略、带工具创建 |
| TestAgentEditing | add_tool（单个/多个）、remove_tool（存在/不存在）、set_strategy、空 DSL 上 add_tool |
| TestAgentIO | agent YAML round-trip |
| TestAgentValidation | 合法 agent、无工具警告、agent_mode 禁用报错、无效 strategy 报错、缺 config 报错 |

### test_completion.py — 文本生成模块 (11 个)

| 测试类 | 覆盖内容 |
|--------|---------|
| TestCreateCompletionApp | 基本创建、自定义 prompt、user_input_form、模型自定义 |
| TestCompletionEditing | enable_more_like_this（启用/禁用） |
| TestCompletionIO | completion YAML round-trip |
| TestCompletionValidation | 合法 completion、无 prompt 警告、缺 config 报错、无 user_input 警告 |

## 7. 未覆盖的边界

| 场景 | 原因 |
|------|------|
| 远程 URL 导入 | 本工具为纯本地工具 |
| 敏感数据加密/解密 | 需要 AES key 和 tenant_id |
| 并发编辑冲突 | 单文件操作无需处理 |
| 超大图性能 | 暂无 benchmark |
| 节点运行时执行 | 属于执行层，非 DSL 工具范畴 |
| 跨模式转换 | 如 chat → workflow 的自动转换 |

## 8. 运行命令

```bash
# 全部测试
python -m pytest tests/ -v

# 仅核心模块测试
python -m pytest tests/test_models.py tests/test_editor.py tests/test_validator.py tests/test_io.py -v

# 仅新增模式测试
python -m pytest tests/test_chatflow.py tests/test_chat.py tests/test_agent.py tests/test_completion.py -v

# 仅集成测试
python -m pytest tests/test_integration.py -v

# 仅 CLI 测试
python -m pytest tests/test_cli.py -v

# 快速摘要
python -m pytest tests/ -q
```
