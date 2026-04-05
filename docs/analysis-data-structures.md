# Dify 工作流 DSL 逆向分析：核心数据结构

> 基于 `dify-test/api/models/workflow.py` 及相关源码

## 1. Workflow ORM 模型

源码位置：`api/models/workflow.py`

```python
class Workflow(Base):
    __tablename__ = "workflows"

    id: str                        # UUID
    tenant_id: str                 # 租户 ID
    app_id: str                    # 应用 ID
    type: WorkflowType             # workflow | chat | rag-pipeline
    version: str                   # "draft" 或 datetime 字符串
    marked_name: str               # 版本标记名
    marked_comment: str            # 版本注释
    graph: str                     # JSON 字符串 → 存储节点和连线
    _features: str                 # JSON 字符串 → 功能配置
    created_by: str
    created_at: datetime
    updated_by: str | None
    updated_at: datetime
    _environment_variables: str    # JSON 字符串
    _conversation_variables: str   # JSON 字符串
    _rag_pipeline_variables: str   # JSON 字符串
```

### 关键属性和方法

```python
# JSON → dict 转换
@property
def graph_dict(self) -> Mapping[str, Any]:
    return json.loads(self.graph) if self.graph else {}

# 导出用：返回完整工作流内容字典
def to_dict(self, *, include_secret=False) -> WorkflowContentDict:
    ...

# 遍历节点
def walk_nodes(self, specific_node_type=None):
    yield from ((node["id"], node["data"]) for node in graph_dict["nodes"])

# 获取单个节点配置
def get_node_config_by_id(self, node_id) -> NodeConfigDict
```

## 2. WorkflowContentDict

```python
class WorkflowContentDict(TypedDict):
    graph: Mapping[str, Any]           # { nodes: [...], edges: [...] }
    features: dict[str, Any]           # 功能配置
    environment_variables: list[dict]  # 环境变量
    conversation_variables: list[dict] # 对话变量
    rag_pipeline_variables: list[dict] # RAG 变量
```

## 3. WorkflowType 枚举

```python
class WorkflowType(StrEnum):
    WORKFLOW = "workflow"
    CHAT = "chat"
    RAG_PIPELINE = "rag-pipeline"
```

## 4. NodeType（来自 graphon 库 + 内置定义）

节点类型分为两类：

### BuiltinNodeTypes（graphon 库定义）

```
START, END, ANSWER, IF_ELSE, LOOP, ITERATION,
VARIABLE_AGGREGATOR, DATASOURCE, LLM, TOOL, CODE,
HTTP_REQUEST, TEMPLATE_TRANSFORM, AGENT,
KNOWLEDGE_RETRIEVAL, DOCUMENT_EXTRACTOR, HUMAN_INPUT,
QUESTION_CLASSIFIER, PARAMETER_EXTRACTOR
```

### Trigger 节点类型（Dify 自定义）

```python
# api/core/trigger/constants.py
TRIGGER_NODE_TYPES = frozenset({
    "trigger-webhook",
    "trigger-schedule",
    "trigger-plugin",
})
```

### Start 类节点

```python
_START_NODE_TYPES = frozenset({
    BuiltinNodeTypes.START,
    BuiltinNodeTypes.DATASOURCE,
    *TRIGGER_NODE_TYPES,
})
```

## 5. 系统变量

源码位置：`api/core/workflow/system_variables.py`

```python
class SystemVariableKey(StrEnum):
    QUERY = "query"
    FILES = "files"
    CONVERSATION_ID = "conversation_id"
    USER_ID = "user_id"
    DIALOGUE_COUNT = "dialogue_count"
    APP_ID = "app_id"
    WORKFLOW_ID = "workflow_id"
    WORKFLOW_EXECUTION_ID = "workflow_run_id"
    TIMESTAMP = "timestamp"
    DOCUMENT_ID = "document_id"
    ORIGINAL_DOCUMENT_ID = "original_document_id"
    BATCH = "batch"
    DATASET_ID = "dataset_id"
    DATASOURCE_TYPE = "datasource_type"
    DATASOURCE_INFO = "datasource_info"
    INVOKE_FROM = "invoke_from"
```

## 6. 导入状态枚举

```python
class ImportStatus(StrEnum):
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed-with-warnings"
    PENDING = "pending"        # 需人工确认（版本不兼容）
    FAILED = "failed"
```

## 7. 节点工厂注册映射

源码位置：`api/core/workflow/node_factory.py`

```python
NODE_TYPE_CLASSES_MAPPING: MutableMapping[NodeType, Mapping[str, type[Node]]]
```

每个节点类型映射到具体实现类，并按版本号索引。节点初始化时根据类型注入不同依赖：

| 节点类型 | 初始化依赖 |
|---------|----------|
| CODE | `code_executor`, `code_limits` |
| TEMPLATE_TRANSFORM | `jinja2_template_renderer`, `max_output_length` |
| HTTP_REQUEST | `http_request_config`, `http_client`, `tool_file_manager_factory` |
| LLM | `credentials_provider`, `model_factory`, `model_instance`, `memory` |
| TOOL | `tool_file_manager_factory`, `runtime` |
| AGENT | `strategy_resolver`, `presentation_provider`, `runtime_support` |
| HUMAN_INPUT | `runtime`, `form_repository` |

## 8. CLI 工具中的数据模型映射

本 CLI 工具在 `dify_workflow/models.py` 中重建了完整的数据结构，支持全部 5 种应用模式：

### 核心模型

| 原始 (dify-test) | CLI 工具 (dify_workflow) | 说明 |
|-----------------|------------------------|------|
| Workflow ORM | `DifyDSL` (别名 `DifyWorkflowDSL`) | 顶层 DSL 文档，统一所有模式 |
| graph_dict | `Graph` | 包含 nodes + edges |
| node config | `Node` + `NodeData` | Pydantic 模型 |
| edge config | `Edge` + `EdgeData` | Pydantic 模型 |
| WorkflowContentDict | `WorkflowContent` | graph + features + variables |
| features JSON | `Features` | 功能配置 |
| AppMode enum | `AppMode` | 5 种应用模式枚举 |
| NodeType enum | `NodeType` | 22 种节点类型 |

### 新增模型（model_config 架构）

| 模型 | 用途 | 关键字段 |
|------|------|---------|
| `ModelConfigContent` | chat/agent/completion 的模型配置 | model, pre_prompt, user_input_form, agent_mode, opening_statement, suggested_questions, more_like_this, dataset_configs 等 |
| `AgentToolConfig` | Agent 工具定义 | tool_type, provider_id, tool_name, tool_parameters |
| `AgentModeConfig` | Agent 模式配置 | enabled, strategy (function_call/react), tools |
| `DatasetConfig` | 数据集配置 | datasets, retrieval_model, top_k, score_threshold |

### 模式分类常量

```python
WORKFLOW_MODES = frozenset({AppMode.WORKFLOW, AppMode.ADVANCED_CHAT})
CONFIG_MODES = frozenset({AppMode.CHAT, AppMode.AGENT_CHAT, AppMode.COMPLETION})
```

### DifyDSL 关键设计

```python
class DifyDSL(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    version: str = "0.6.0"
    kind: str = "app"
    app: AppInfo = AppInfo()
    workflow: WorkflowContent = WorkflowContent()
    model_config_content: ModelConfigContent | None = Field(
        default=None,
        validation_alias="model_config",
        serialization_alias="model_config",
    )
    dependencies: list[dict] = []

    @property
    def is_workflow_based(self) -> bool: ...
    @property
    def is_config_based(self) -> bool: ...
```

> **Pydantic v2 字段名冲突解决**：`model_config` 是 Pydantic v2 的保留类变量（ConfigDict），
> 不能直接作为字段名。通过 `validation_alias` + `serialization_alias` 将 Python 属性
> `model_config_content` 映射到 YAML 中的 `model_config` 键。

所有模型使用 Pydantic v2，支持 `model_dump(mode="json", by_alias=True)` 序列化和 `model_validate()` 反序列化，
并设置 `extra="allow"` 以兼容未知字段。`DifyWorkflowDSL = DifyDSL` 保持向后兼容。
