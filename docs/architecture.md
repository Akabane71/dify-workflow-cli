# CLI 工具架构与设计

## 1. 模块结构

```
dify_workflow/
├── __init__.py              # 包入口，版本号
├── models.py                # Pydantic v2 数据模型（全模式 DSL 结构定义）
├── editor.py                # 通用图编辑操作（节点/边增删改）
├── validator.py             # 模式分派校验器（自动检测模式→调用专用校验）
├── node_data_validator.py   # 节点数据校验（对齐 Dify graphon 节点 schema）
├── node_validators_core.py  # 核心节点校验器（LLM/Code/HTTP/IF-ELSE/Tool 等）
├── node_validators_extra.py # 扩展节点校验器（Iteration/Loop/Agent 等）
├── frontend_validator.py    # 前端崩溃预防校验（对齐 Dify React 前端渲染要求）
├── checklist_validator.py   # Pre-publish 清单（对齐 Dify use-checklist.ts 三层校验）
├── checklist_checks.py      # 清单子检查函数
├── layout.py                # 自动布局引擎（5 种策略调度）
├── layout_tree.py           # 树形布局算法（Dify 风格左→右分支分组）
├── mermaid.py               # Mermaid 流程图输出
├── io.py                    # YAML/JSON 文件读写 + 模式感知序列化
├── scanner.py               # [废弃] dify-test 源码扫描分析
├── cli.py                   # Click CLI 入口（命令注册）
├── cli_edit.py              # edit 子命令组
├── cli_config.py            # config 子命令组
├── cli_inspect.py           # inspect 命令
├── cli_ops.py               # validate / checklist / export / import / diff / layout
├── cli_shared.py            # CLI 公共工具
├── workflow/                # Workflow 模式 (mode=workflow)
│   ├── editor.py            #   模板创建：minimal / llm / if-else
│   └── validator.py         #   图结构校验：start/end、连通性、环检测、checklist
├── chatflow/                # Chatflow 模式 (mode=advanced-chat)
│   ├── editor.py            #   模板创建：chatflow / knowledge
│   └── validator.py         #   chatflow 校验：Answer 节点、LLM memory
├── model_config_validators/ # 共享 model_config 校验模块（对齐 Dify ConfigManager 链）
│   ├── __init__.py
│   ├── model_validator.py       # model 配置校验（provider/name/mode/stop）
│   ├── variables_validator.py   # user_input_form 校验（类型/label/variable 格式/唯一性）
│   ├── prompt_validator.py      # prompt_type + prompt_config 校验
│   ├── dataset_validator.py     # dataset_configs 校验（retrieval_model/UUID/query_variable）
│   ├── agent_mode_validator.py  # agent_mode 校验（enabled/strategy/tools/tool_parameters）
│   └── features_validator.py    # Features 校验（TTS/STT/开场白/敏感词等）
├── chat/                    # 聊天助手模式 (mode=chat)
│   ├── editor.py            #   model_config 编辑操作
│   └── validator.py         #   共享校验链 + chat 专属规则
├── agent/                   # Agent 模式 (mode=agent-chat)
│   ├── editor.py            #   Agent 配置：strategy / 工具管理
│   └── validator.py         #   共享校验链 + agent_mode/strategy/tools 校验
└── completion/              # 文本生成模式 (mode=completion)
    ├── editor.py            #   completion 配置
    └── validator.py         #   共享校验链 + dataset_query_variable/features 校验
```

## 2. 技术选型

| 组件 | 选择 | 原因 |
|------|------|------|
| CLI 框架 | Click 8.x | 成熟稳定，支持子命令、参数校验、OrderedGroup |
| 数据模型 | Pydantic v2 | 类型安全，ConfigDict，validation_alias/serialization_alias |
| YAML | PyYAML | 标准库级别，Dify 原生使用 |
| 输出美化 | Rich | 树形结构、表格、彩色输出 |
| 测试 | pytest | 行业标准，513 个测试 |
| 运行时 | Python 3.12 | 类型提示、match 语法 |

## 3. 设计原则

### 3.1 与 Dify 真实格式对齐
- 所有模型字段名与 Dify 导出的 YAML 完全一致
- 能加载 Dify 导出的真实 DSL 文件（经 dify-test fixture 验证）
- 导出格式可直接被 Dify 导入

### 3.2 两大架构分类
Dify 的 5 种应用模式分为两种底层架构：

| 架构 | 模式 | 核心数据结构 | CLI 编辑命令 |
|------|------|------------|-------------|
| **Workflow-based** | workflow, advanced-chat (chatflow) | `workflow.graph` (nodes + edges) | `edit` 命令组 |
| **ModelConfig-based** | chat, agent-chat, completion | `model_config` (model + prompt + tools) | `config` 命令组 |

### 3.3 AI 友好
- 所有命令支持 `-j` / `--json-output` 输出结构化 JSON
- 支持非交互模式（无需人工确认）
- 参数接受 JSON 字符串（`-d '{"key": "value"}'`）和 `--data-file` 文件
- 错误信息明确，包含 node_id 和字段名
- `guide` 命令提供渐进式教程
- `list-node-types` 命令发现可用节点类型

### 3.4 本地优先
- 纯文件操作，不依赖远程 API 或数据库
- 读 → 改 → 验证 → 导出 全部在本地完成
- 支持 YAML 和 JSON 双格式

### 3.5 一个功能一个目录
- 每种应用模式独立目录（workflow / chatflow / chat / agent / completion）
- 每个目录有独立的 editor.py + validator.py
- 通过 `__init__.py` 控制公开 API
- 通过顶层 `validator.py` 统一分派，用户无需关心内部细节

## 4. 分层架构

```
┌──────────────────────────────────────────────────────┐
│                    CLI Layer                          │
│  cli.py — Click 命令定义                              │
│  命令组：create / edit / config / validate / ...      │
│  输入解析、输出格式化（JSON/Rich）                      │
├──────────────────────────────────────────────────────┤
│                  Service Layer                        │
│  editor.py — 通用图编辑操作（add_node/edge/etc.）      │
│  workflow/editor.py — workflow 模板创建                │
│  chatflow/editor.py — chatflow 模板创建               │
│  chat/editor.py — model_config 编辑                   │
│  agent/editor.py — agent 配置 + 工具管理               │
│  completion/editor.py — completion 配置               │
├──────────────────────────────────────────────────────┤
│                 Validator Layer                        │
│  validator.py — 统一分派入口                           │
│  node_data_validator.py — 逐节点数据校验（25 种类型）   │
│  frontend_validator.py — 前端崩溃预防校验（16 种类型）   │
│  checklist_validator.py — Pre-publish 清单（三层校验）   │
│  layout.py + layout_tree.py — 自动布局（5 种策略）      │
│  mermaid.py — Mermaid 流程图输出                        │
│  workflow/validator.py — 图结构+环检测+连通性+checklist  │
│  chatflow/validator.py — Answer 节点 + memory          │
│  model_config_validators/ — 6 个共享校验模块              │
│    model / variables / prompt / dataset / agent_mode /  │
│    features（对齐 Dify ConfigManager 链）                │
│  chat/validator.py — 共享链 + opening_statement 等      │
│  agent/validator.py — 共享链 + agent_mode.enabled/tools │
│  completion/validator.py — 共享链 + query_variable 等   │
├──────────────────────────────────────────────────────┤
│                    I/O Layer                           │
│  io.py — YAML/JSON 文件读写、模式感知序列化              │
│  _clean_export_data() 清理空字段                       │
│  by_alias=True 确保 model_config 正确序列化             │
├──────────────────────────────────────────────────────┤
│                   Model Layer                         │
│  models.py — Pydantic v2 模型                          │
│  DifyDSL — 顶层文档（统一所有模式）                      │
│  ModelConfigContent — chat/agent/completion 配置        │
│  Graph / Node / Edge — 工作流图结构                     │
│  AppMode / NodeType — 枚举                             │
└──────────────────────────────────────────────────────┘
```

## 5. 数据模型核心设计

### DifyDSL — 统一顶层模型

```python
class DifyDSL(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    version: str = "0.6.0"
    kind: str = "app"
    app: AppInfo = AppInfo()
    workflow: WorkflowContent = WorkflowContent()
    model_config_content: ModelConfigContent | None = Field(
        default=None,
        validation_alias="model_config",      # YAML 中的 model_config 键
        serialization_alias="model_config",    # 导出时用 model_config 键
    )
    dependencies: list[dict] = []
```

> **关键设计**：Pydantic v2 中 `model_config` 是保留类变量（ConfigDict），不能作为字段名。
> 因此使用 `model_config_content` 作为 Python 属性名，通过 `validation_alias` 和 `serialization_alias` 映射到 YAML 中的 `model_config`。

### 模式判断

```python
WORKFLOW_MODES = frozenset({AppMode.WORKFLOW, AppMode.ADVANCED_CHAT})
CONFIG_MODES = frozenset({AppMode.CHAT, AppMode.AGENT_CHAT, AppMode.COMPLETION})

@property
def is_workflow_based(self) -> bool:
    return self.app.mode in WORKFLOW_MODES

@property
def is_config_based(self) -> bool:
    return self.app.mode in CONFIG_MODES
```

### 向后兼容

```python
DifyWorkflowDSL = DifyDSL  # 旧代码使用的别名仍可用
```

## 6. 校验架构

`validator.py` 是统一入口，自动检测 app.mode 并分派到模式专用校验器：

| 模式 | 校验器 | 校验内容 |
|------|--------|---------|
| workflow | `workflow.validator.validate_workflow_mode()` | 顶层字段、图结构、节点规则、边合法性、环检测、连通性、pre-publish 清单 |
| advanced-chat | `chatflow.validator.validate_chatflow_mode()` | 同 workflow + Answer 节点检查 + memory 建议 |
| chat | `chat.validator.validate_chat_mode()` | 共享校验链（model→variables→prompt→dataset→features） + opening_statement、suggested_questions、agent_mode 启用警告 |
| agent-chat | `agent.validator.validate_agent_mode()` | 共享校验链 + agent_mode_fields（enabled/strategy/tools/tool_parameters）、enabled 必须为 true、无 tools 警告 |
| completion | `completion.validator.validate_completion_mode()` | 共享校验链（含 dataset_query_variable 必填）+ opening_statement/SQA/STT 不适用警告、无 user_input_form 警告 |

### Workflow 模式校验维度（8 维）

| 维度 | 检查内容 |
|------|--------|
| **顶层校验** | version、kind、app.name、app.mode 存在性 |
| **图结构校验** | 节点非空、ID 唯一、有 start 节点、start/trigger 不共存 |
| **节点数据校验** | 25 种节点类型的必填字段、类型约束、枚举值合法性（对齐 Dify graphon schema） |
| **前端崩溃预防** | 16 种节点类型的前端渲染必填字段（对齐 Dify React 前端 node.tsx / initialNodes()） |
| **HumanInput 深度校验** | inputs[].output_variable_name 必填、delivery_methods[].id 必须为 UUID、user_actions 标识符格式、去重等 |
| **边校验** | 端点存在、无自环、ID 唯一 |
| **环检测** | DFS 3-color 算法检测 DAG 中的环（对齐 Dify 前端 `getCycleEdges`），环上所有边会被前端移除导致断连 |
| **连通性校验** | BFS 从 start 出发，检测孤立节点（含 Iteration/Loop 子节点遍历） |
| **Pre-publish 清单** | 对齐 Dify 前端 `use-checklist.ts`：节点配置完整性、上游变量引用有效性、所有节点可达 |

## 7. CLI 命令一览

### 顶层命令

| 命令 | 功能 |
|------|------|
| `guide` | 渐进式教程（6 步） |
| `list-node-types` | 列出全部 25 种节点类型 |
| `scan` | [废弃] 扫描 dify-test 源码分析 |
| `create` | 创建应用（支持 5 种模式 + 多种模板） |
| `inspect` | 查看结构（树形 / JSON / Mermaid，自动识别模式） |
| `validate` | 校验合法性（结构 + 节点数据 + 连通性 + 环检测） |
| `checklist` | Pre-publish 清单（对齐 Dify 前端检查面板） |
| `export` | 导出为 YAML / JSON |
| `import` | 导入、校验、再导出 |
| `diff` | 对比两个文件差异 |
| `layout` | 自动布局节点（5 种策略：tree / hierarchical / linear / vertical / compact） |

### edit 子命令（workflow / chatflow 模式）

| 子命令 | 功能 |
|--------|------|
| `add-node` | 添加节点 |
| `remove-node` | 删除节点（自动清理连线） |
| `update-node` | 更新节点数据字段 |
| `add-edge` | 添加连线 |
| `remove-edge` | 删除连线 |
| `set-title` | 修改节点标题 |
| `layout` | 自动排版布局（linear/hierarchical/vertical/compact） |

### config 子命令（chat / agent / completion 模式）

| 子命令 | 功能 |
|--------|------|
| `set-model` | 设置 LLM 模型和参数 |
| `set-prompt` | 设置系统提示词 (pre_prompt) |
| `add-variable` | 添加用户输入变量 |
| `set-opening` | 设置开场白 |
| `add-question` | 添加推荐问题 |
| `add-tool` | 添加 Agent 工具 |
| `remove-tool` | 移除 Agent 工具 |

## 8. 自动布局引擎

`layout.py` 提供 4 种布局策略，一键重排工作流节点位置：

### 布局策略

| 策略 | 方向 | 算法 | 适用场景 |
|------|------|------|---------|
| `linear` | 左→右 | 按拓扑序排列在同一水平线 | 简单顺序流程 |
| `hierarchical` | 左→右 | DAG 分层 + 交叉最小化 + 居中对齐 | **默认**，适合多分支工作流 |
| `vertical` | 上→下 | 同 hierarchical，轴向旋转 90° | 纵向展示 |
| `compact` | 左→右 | 同 hierarchical，间距压缩 40% | 大型工作流需要紧凑视图 |

### 核心算法（对齐 Dify 前端 ELK.js 布局）

```
┌─────────────────────────────────────────────────────────────┐
│ Step 1: 构建图                                               │
│   nodes[] + edges[] → adjacency list + reverse adjacency     │
├─────────────────────────────────────────────────────────────┤
│ Step 2: 分层（Layer Assignment）                              │
│   BFS 从源节点出发，layer = max(所有父节点层) + 1              │
│   保证分支和合并节点在正确的深度层级                             │
├─────────────────────────────────────────────────────────────┤
│ Step 3: 层内排序（Cross Minimization）                        │
│   重心法（Barycenter Heuristic）：                             │
│   · 正向扫描：节点按其前驱的平均位置排序                         │
│   · 反向扫描：节点按其后继的平均位置排序                         │
│   · 迭代 4 轮收敛                                             │
│   分支顺序遵循 if-else case / question-classifier class 顺序   │
├─────────────────────────────────────────────────────────────┤
│ Step 4: 坐标计算（Position Assignment）                       │
│   层内节点垂直居中                                             │
│   间距参数对齐 Dify 前端 ELK 配置：                             │
│   · 层间距：100px（compact: 60px）                             │
│   · 节点间距：80px（compact: 40px）                             │
│   · 节点尺寸：244×90px                                        │
└─────────────────────────────────────────────────────────────┘
```

### 使用方式

```bash
# 默认 hierarchical 布局
dify-workflow layout -f workflow.yaml

# 指定布局策略
dify-workflow layout -f workflow.yaml --strategy vertical

# 布局后输出到新文件
dify-workflow layout -f workflow.yaml -o workflow-laid-out.yaml

# 结合 JSON 输出
dify-workflow layout -f workflow.yaml -j
```

### API 调用

```python
from dify_workflow.layout import auto_layout

# 重排节点位置（修改 dsl 对象原地更新）
auto_layout(dsl, strategy="hierarchical")
```

## 9. I/O 模式感知序列化

`io.py` 中的 `_clean_export_data()` 根据应用模式清理导出数据：

- **Workflow-based** 应用：移除空的 `model_config` 字段
- **ModelConfig-based** 应用：移除空的 `workflow` 字段（仅含默认空图）
- 所有模式：`model_dump(by_alias=True)` 确保 `model_config_content` 序列化为 `model_config`

## 10. 测试架构

```
tests/
├── test_models.py              # 19 个测试 — 数据模型
├── test_editor.py              # 32 个测试 — 图编辑操作
├── test_validator.py           # 14 个测试 — 校验逻辑
├── test_node_data_validator.py # 76 个测试 — 节点数据校验
├── test_frontend_validator.py  # 43 个测试 — 前端崩溃预防校验
├── test_layout.py             # 32 个测试 — 自动布局引擎
├── test_io.py                  # 12 个测试 — 文件读写
├── test_cli.py                 # 43 个测试 — CLI 命令端到端
├── test_integration.py         # 19 个测试 — 集成场景 + Dify fixture 真实校验
├── test_chatflow.py            #  8 个测试 — Chatflow 模块
├── test_chat.py                # 19 个测试 — 聊天助手模块
├── test_agent.py               # 15 个测试 — Agent 模块
└── test_completion.py          # 11 个测试 — 文本生成模块
                                ──────────
                                361 个测试 全部通过
```

## 11. 扩展性设计

### 各模式目录结构一致

每个模式目录遵循相同的结构：

```
<mode>/
├── __init__.py     # 公开 API 导出
├── editor.py       # 创建和编辑操作
└── validator.py    # 模式专用校验
```

新增模式只需：
1. 创建新目录，实现 editor.py + validator.py
2. 在顶层 `validator.py` 的分派逻辑中注册
3. 在 `cli.py` 的 `_create_by_mode()` 中添加分支

### 平台适配预留

`DifyDSL` 模型设置了 `extra="allow"`，可兼容其他平台的额外字段。
未来可通过 `PlatformAdapter` 基类实现百炼 / 腾讯 ADP 等平台的转换。
