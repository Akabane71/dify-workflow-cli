# Dify 工作流 DSL 逆向分析：调用链与关键文件

> 基于 `dify-test` 项目源码逆向分析

## 1. 关键文件列表

### 核心 DSL 服务层

| 文件 | 职责 | 关键类/函数 |
|------|------|-----------|
| `api/services/app_dsl_service.py` | DSL 导入导出主入口 | `AppDslService.export_dsl()`, `import_app()` |
| `api/services/workflow_service.py` | 工作流 CRUD | `get_draft_workflow()`, `sync_draft_workflow()`, `publish_workflow()`, `validate_graph_structure()` |
| `api/services/workflow/workflow_converter.py` | 工作流格式转换 | 格式兼容适配 |

### 数据模型层

| 文件 | 职责 | 关键类/函数 |
|------|------|-----------|
| `api/models/workflow.py` | Workflow ORM 模型 | `Workflow.to_dict()`, `graph_dict`, `walk_nodes()` |
| `api/models/_workflow_exc.py` | 工作流异常定义 | `WorkflowDataError` |

### 核心工作流引擎

| 文件 | 职责 | 关键类/函数 |
|------|------|-----------|
| `api/core/workflow/node_factory.py` | 节点注册与实例化 | `resolve_workflow_node_class()`, `NODE_TYPE_CLASSES_MAPPING` |
| `api/core/workflow/workflow_entry.py` | 工作流执行入口 | 运行时执行 |
| `api/core/workflow/system_variables.py` | 系统变量定义 | `SystemVariableKey` 枚举 |

### API 控制器

| 文件 | 职责 |
|------|------|
| `api/controllers/console/app/app.py` | `AppExportApi` 导出端点 |
| `api/controllers/console/app/app_import.py` | `AppImportApi` 导入端点 |
| `api/controllers/inner_api/app/dsl.py` | 企业版 DSL 端点 |

### 节点实现（`api/core/workflow/nodes/`）

| 目录 | 包含文件 |
|------|---------|
| `knowledge_retrieval/` | `knowledge_retrieval_node.py`, `entities.py`, `retrieval.py` |
| `trigger_webhook/` | `node.py`, `entities.py` |
| `trigger_schedule/` | `trigger_schedule_node.py`, `entities.py` |
| `trigger_plugin/` | `trigger_event_node.py` |
| `agent/` | Agent 节点实现 |
| `datasource/` | 数据源节点实现 |
| `knowledge_index/` | 知识索引节点 |

### 应用配置

| 文件 | 职责 |
|------|------|
| `api/core/app/apps/workflow/app_config_manager.py` | 工作流应用配置管理 |
| `api/core/app/apps/workflow/app_generator.py` | 工作流应用生成 |

## 2. 导出调用链（DSL Export）

```
HTTP GET /apps/<app_id>/export
│
├─ AppExportApi.get(include_secret, workflow_id)
│  │  [api/controllers/console/app/app.py]
│  │
│  └─ AppDslService.export_dsl(app_model, include_secret)
│     │  [api/services/app_dsl_service.py]
│     │
│     ├─ 构建顶层结构
│     │  export_data = {
│     │    "version": "0.6.0",
│     │    "kind": "app",
│     │    "app": { name, mode, icon, ... }
│     │  }
│     │
│     ├─ _append_workflow_export_data()
│     │  │
│     │  ├─ WorkflowService.get_draft_workflow(app_model)
│     │  │  │  [api/services/workflow_service.py]
│     │  │  └─ SELECT * FROM workflows WHERE version='draft'
│     │  │
│     │  ├─ Workflow.to_dict(include_secret)
│     │  │  │  [api/models/workflow.py]
│     │  │  ├─ self.graph_dict      → json.loads(self.graph)
│     │  │  ├─ self.features_dict   → json.loads(self.features)
│     │  │  ├─ environment_variables → model_dump()
│     │  │  ├─ conversation_variables → model_dump()
│     │  │  └─ rag_pipeline_variables
│     │  │
│     │  ├─ 敏感数据过滤
│     │  │  ├─ knowledge_retrieval 节点: encrypt_dataset_id()
│     │  │  ├─ tool 节点: 移除 credential_id
│     │  │  ├─ trigger_webhook: 清空 webhook_url
│     │  │  └─ trigger_plugin: 清空 subscription_id
│     │  │
│     │  └─ export_data["workflow"] = workflow_dict
│     │
│     ├─ _extract_dependencies_from_workflow()
│     │  ├─ 遍历节点收集 tool/model provider
│     │  └─ TOOL / LLM / QUESTION_CLASSIFIER / PARAMETER_EXTRACTOR / KNOWLEDGE_RETRIEVAL
│     │
│     ├─ DependenciesAnalysisService.generate_dependencies()
│     │
│     └─ yaml.dump(export_data, allow_unicode=True)
│
└─ Return: YAML 字符串
```

## 3. 导入调用链（DSL Import）

```
HTTP POST /apps/imports
│
├─ AppImportApi.post(mode, yaml_content/url, name, icon, ...)
│  │  [api/controllers/console/app/app_import.py]
│  │
│  └─ AppDslService.import_app(account, import_mode, content)
│     │  [api/services/app_dsl_service.py]
│     │
│     ├─ yaml.safe_load(content) → dict
│     │
│     ├─ 结构校验
│     │  ├─ 检查 "app" 键存在
│     │  └─ 检查 version 字段
│     │
│     ├─ _check_version_compatibility(imported_version)
│     │  ├─ major 不匹配 → PENDING (存入 Redis)
│     │  ├─ minor < 当前 → COMPLETED_WITH_WARNINGS
│     │  └─ 其他 → COMPLETED
│     │
│     ├─ _create_or_update_app(data, account)
│     │  ├─ 创建/更新 App 模型
│     │  ├─ 创建 Workflow 模型
│     │  │  ├─ graph = json.dumps(data["workflow"]["graph"])
│     │  │  ├─ features = json.dumps(data["workflow"]["features"])
│     │  │  └─ variables = data["workflow"]["*_variables"]
│     │  └─ db.session.commit()
│     │
│     └─ Return: Import(app_id, status, error)
```

## 4. 工作流发布调用链

```
WorkflowService.publish_workflow()
│  [api/services/workflow_service.py]
│
├─ 读取 draft workflow
├─ validate_graph_structure(graph_dict)
│  ├─ 检查节点非空
│  ├─ start 节点和 trigger 节点不能共存
│  └─ human_input 节点数据校验
├─ 创建新 Workflow (version = datetime 字符串)
└─ 发送 app_published_workflow_was_updated 信号
```

## 5. 数据流转图

```
                    ┌──────────────┐
                    │   Database   │
                    │  (PostgreSQL)│
                    └──────┬───────┘
                           │
              graph (JSON string)
              features (JSON string)
              variables (JSON string)
                           │
                    ┌──────▼───────┐
                    │   Workflow   │
                    │    Model     │
                    │ (SQLAlchemy) │
                    └──────┬───────┘
                           │
                    to_dict() / graph_dict
                    json.loads() → dict
                           │
                    ┌──────▼───────┐
                    │ AppDslService│
                    │  export_dsl  │
                    └──────┬───────┘
                           │
              过滤敏感数据 + 提取依赖
                           │
                    ┌──────▼───────┐
                    │  yaml.dump() │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │ workflow.yaml│
                    │  (DSL 文件)  │
                    └──────────────┘
```

## 6. 可复用逻辑分析

| 逻辑 | 是否可直接复用 | 原因 |
|------|-------------|------|
| DSL YAML 格式 | ✅ 完全复用 | 纯数据格式，无依赖 |
| 节点类型定义 | ✅ 完全复用 | 枚举值，已在 models.py 中重建 |
| 图结构校验 | ⚠️ 部分复用 | 原始逻辑依赖 DB/graphon，已在 validator.py 中重新实现核心规则 |
| 导出过滤逻辑 | ⚠️ 参考实现 | 敏感数据过滤依赖 AES，本地工具不需要 |
| 节点工厂 | ❌ 不可复用 | 深度依赖 graphon 库和运行时环境 |
| Workflow ORM | ❌ 不可复用 | 依赖 SQLAlchemy + PostgreSQL |

## 7. 测试 Fixture 文件（23 个）

位于 `api/tests/fixtures/workflow/`，已全部可被本工具加载和校验：

- `basic_llm_chat_workflow.yml` — Start → LLM → End
- `simple_passthrough_workflow.yml` — Start → End (echo)
- `conditional_hello_branching_workflow.yml` — IF/ELSE 分支
- `conditional_parallel_code_execution_workflow.yml`
- `dual_switch_variable_aggregator_workflow.yml`
- `http_request_with_json_tool_workflow.yml`
- `increment_loop_with_break_condition_workflow.yml`
- `iteration_flatten_output_*_workflow.yml`
- `loop_contains_answer.yml`
- `multilingual_parallel_llm_streaming_workflow.yml`
- 等
