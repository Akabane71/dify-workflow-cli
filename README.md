# Dify AI Workflow Tools

[English README](README_EN.md)

**本地创建、编辑、校验、布局、导出 Dify 全部 5 种应用类型的 CLI 工具。**

基于 Dify 前端 + 后端源码逆向分析 DSL v0.6.0 格式，覆盖 **Workflow、Chatflow、聊天助手、Agent、文本生成** 全部模式。

校验层对齐 Dify 前端三层校验 (节点配置 → 变量引用 → 连通性)，并增加了环检测 — 生成的 YAML 可直接导入 Dify 前端无警告。

---

## 功能概览

| 功能 | 说明 |
|------|------|
| **创建** | 通过 `create --mode` 一键创建 5 种应用类型，支持多种模板 |
| **编辑** | `edit` 命令组编辑工作流图（节点/边），`config` 命令组编辑模型配置 |
| **校验** | 自动识别应用模式，分派专用校验 (结构 + 节点数据 + 前端兼容 + 变量引用 + 连通性 + 环检测) |
| **前端清单** | `checklist` 命令对齐 Dify 前端 `use-checklist.ts` 的 pre-publish 校验 |
| **布局** | `layout` 自动排列节点位置，支持 5 种策略 (tree / hierarchical / linear / vertical / compact) |
| **检视** | `inspect` 以 Rich 树形 / JSON / **Mermaid 流程图** 展示结构 |
| **导出** | YAML / JSON 双格式导出，可直接导入 Dify |
| **对比** | `diff` 对比两个配置文件的差异 |

## 支持的应用模式

| CLI `--mode` | Dify `app.mode` | 架构类型 | 说明 |
|--------------|-----------------|---------|------|
| `workflow` | `workflow` | 工作流图 (Start→…→End) | 可视化编排，单次执行 |
| `chatflow` | `advanced-chat` | 工作流图 (Start→…→Answer) | 可视化编排，多轮对话 |
| `chat` | `chat` | model_config | 简单聊天机器人 |
| `agent` | `agent-chat` | model_config | 聊天 + 工具调用 (function_call / react) |
| `completion` | `completion` | model_config | 单轮文本生成 |

---

## 快速开始

### 安装

```bash
cd dify-ai-workflow-tools
pip install -e .
```

验证安装：

```bash
dify-workflow --version
# dify-workflow, version 0.1.1
```

### 5 种模式创建示例

```bash
# 工作流 (默认)
dify-workflow create -o my_workflow.yaml

# LLM 工作流模板
dify-workflow create --mode workflow --template llm --name "翻译机器人" -o translator.yaml

# IF/ELSE 分支工作流
dify-workflow create --mode workflow --template if-else -o router.yaml

# Chatflow (多轮对话工作流)
dify-workflow create --mode chatflow -o chatflow.yaml

# 知识库 Chatflow
dify-workflow create --mode chatflow --template knowledge -o kb_chat.yaml

# 聊天助手
dify-workflow create --mode chat --name "聊天机器人" -o chat.yaml

# Agent (工具调用)
dify-workflow create --mode agent --name "智能助手" -o agent.yaml

# 文本生成
dify-workflow create --mode completion --name "文案生成器" -o gen.yaml
```

### 编辑工作流图（workflow / chatflow 模式）

```bash
# 添加节点
dify-workflow edit add-node -f my_workflow.yaml --type code --title "数据处理"

# 添加连线
dify-workflow edit add-edge -f my_workflow.yaml --source start_node --target <node_id>

# 更新节点数据
dify-workflow edit update-node -f my_workflow.yaml --id llm_node \
  -d '{"model": {"provider": "openai", "name": "gpt-4o"}}'

# 删除节点（自动清理连线）
dify-workflow edit remove-node -f my_workflow.yaml --id <node_id>

# 修改节点标题
dify-workflow edit set-title -f my_workflow.yaml --id start_node --title "用户输入"
```

### 编辑模型配置（chat / agent / completion 模式）

```bash
# 设置模型
dify-workflow config set-model -f chat.yaml --provider openai --name gpt-4o

# 设置提示词
dify-workflow config set-prompt -f chat.yaml --text "你是一个有用的助手。"

# 从文件读取提示词
dify-workflow config set-prompt -f chat.yaml --data-file prompt.txt

# 添加用户输入变量
dify-workflow config add-variable -f chat.yaml --name query --type paragraph

# 设置开场白
dify-workflow config set-opening -f chat.yaml --text "你好！有什么可以帮助你的？"

# 添加推荐问题
dify-workflow config add-question -f chat.yaml --text "你能做什么？"

# Agent: 添加工具
dify-workflow config add-tool -f agent.yaml --provider calculator --tool calculate

# Agent: 移除工具
dify-workflow config remove-tool -f agent.yaml --tool calculate
```

### 校验与导出

```bash
# 校验（自动识别模式，分派模式专用规则）
dify-workflow validate my_workflow.yaml

# JSON 格式校验报告
dify-workflow validate my_workflow.yaml -j

# 严格模式（warnings 也视为错误）
dify-workflow validate my_workflow.yaml --strict

# 导出为 YAML
dify-workflow export my_workflow.yaml --output final.yaml

# 导出为 JSON
dify-workflow export my_workflow.yaml -o final.json --format json

# 输出到 stdout
dify-workflow export my_workflow.yaml

# 检视结构（Rich 树形）
dify-workflow inspect my_workflow.yaml

# 检视结构（JSON，适合 AI 使用）
dify-workflow inspect chat.yaml -j
```

### 其他命令

```bash
# 导入并再导出（格式转换、归一化）
dify-workflow import external.yaml --output local.yaml

# 对比差异
dify-workflow diff before.yaml after.yaml

# 自动布局（默认 tree 策略，Dify 风格左→右树形）
dify-workflow layout -f my_workflow.yaml -o laid_out.yaml

# 可选策略：tree / hierarchical / linear / vertical / compact
dify-workflow layout -f my_workflow.yaml --strategy hierarchical

# Dify 前端 pre-publish 清单校验
dify-workflow checklist my_workflow.yaml

# Mermaid 流程图输出（便于 AI 分析或粘贴到 Markdown）
dify-workflow inspect my_workflow.yaml --mermaid

# 查看所有节点类型
dify-workflow list-node-types

# 新手教程
dify-workflow guide
```

---

## 项目结构

```
dify_workflow/
├── __init__.py              # 包入口，版本号
├── models.py                # Pydantic v2 数据模型（全模式 DSL 结构）
├── editor.py                # 通用图编辑操作（节点/边增删改）
├── validator.py             # 模式分派校验器（自动检测模式→调用专用校验）
├── node_data_validator.py   # 节点数据校验（对齐 Dify graphon 节点 schema，25 种类型）
├── node_validators_core.py  # 核心节点校验器（LLM/Code/HTTP/IF-ELSE/Tool 等）
├── node_validators_extra.py # 扩展节点校验器（Iteration/Loop/Agent 等）
├── frontend_validator.py    # 前端兼容性校验（导入后不崩溃）
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
├── chat/                    # 聊天助手模式 (mode=chat)
│   ├── editor.py            #   model_config 编辑：set_model / set_prompt / add_variable 等
│   └── validator.py         #   model / prompt 校验
├── agent/                   # Agent 模式 (mode=agent-chat)
│   ├── editor.py            #   Agent 配置：strategy / add_tool / remove_tool
│   └── validator.py         #   agent_mode / strategy / tools 校验
└── completion/              # 文本生成模式 (mode=completion)
    ├── editor.py            #   completion 配置：enable_more_like_this
    └── validator.py         #   prompt / user_input_form 校验
```

## 技术选型

| 组件 | 选择 | 说明 |
|------|------|------|
| 运行时 | Python 3.12+ | 类型提示 |
| CLI 框架 | Click 8.x | 子命令、参数校验、OrderedGroup |
| 数据模型 | Pydantic v2 | ConfigDict、validation_alias / serialization_alias |
| YAML | PyYAML | Dify 原生格式 |
| 输出美化 | Rich | 树形结构、表格、彩色输出 |
| DSL 版本 | Dify v0.6.0 | 对齐最新版 DSL 格式 |
| 测试 | pytest | 419 个测试全部通过 |

---

## 校验体系

校验层从上到下依次执行，对齐 Dify 官方前端+后端的完整校验链路：

| 校验层 | 命令 | 说明 |
|--------|------|------|
| **图结构校验** | `validate` | Start 节点存在、边合法性、环检测 (DFS 3-color，对齐前端 `getCycleEdges`) |
| **节点数据校验** | `validate` | 25 种节点类型的字段级校验 (对齐 graphon 节点 schema) |
| **前端兼容校验** | `validate` | human-input UUID 格式、枚举值等 (防止导入后前端崩溃) |
| **连通性校验** | `validate` | Start 为根的 BFS 可达性 (含 Iteration/Loop 子节点) |
| **Pre-publish 清单** | `checklist` | 对齐 Dify 前端 `use-checklist.ts` 三层检查：节点配置完整性、上游变量引用有效性、所有节点可达 |

> Dify 前端在加载 DSL 时会运行环检测算法 (`getCycleEdges`)，移除环上所有边。
> 本工具的 `validate` 命令会提前检测环并报错，避免导入后节点断连。

---

## 测试

```bash
# 运行全部测试
python -m pytest tests/ -v

# 快速摘要
python -m pytest tests/ -q
# 419 passed
```

| 文件 | 数量 | 覆盖范围 |
|------|------|--------|
| test_node_data_validator.py | 76 | 25 种节点类型字段级校验 |
| test_editor.py | 49 | 节点/边增删改、模板创建 |
| test_checklist_validator.py | 47 | Pre-publish 清单（变量引用、连通性） |
| test_cli.py | 46 | CLI 全部命令端到端测试 |
| test_frontend_validator.py | 43 | 前端兼容性校验 |
| test_layout.py | 37 | 5 种布局策略 + 节点不重叠 |
| test_models.py | 20 | 数据模型、枚举、序列化 |
| test_chat.py | 19 | 聊天助手创建/编辑/IO/校验 |
| test_integration.py | 19 | 端到端场景、Dify fixture 真实校验 |
| test_validator.py | 16 | 图结构/连通性/环检测 |
| test_agent.py | 15 | Agent 创建/编辑/IO/校验 |
| test_io.py | 13 | YAML/JSON 读写、round-trip |
| test_completion.py | 11 | 文本生成创建/编辑/IO/校验 |
| test_chatflow.py | 8 | Chatflow 创建与校验 |
| **合计** | **419** | |

---

## 文档

| 文档 | 内容 |
|------|------|
| [docs/cli-reference.md](docs/cli-reference.md) | CLI 命令完整参考手册 |
| [docs/architecture.md](docs/architecture.md) | 架构设计、模块分层、设计原则 |
| [docs/testing.md](docs/testing.md) | 测试说明与覆盖分析 |
| [docs/validation-coverage.md](docs/validation-coverage.md) | DSL 校验覆盖对照表（vs Dify 官方） |
| [docs/analysis-frontend-checklist.md](docs/analysis-frontend-checklist.md) | Dify 前端 pre-publish 清单逆向分析 |
| [docs/analysis-node-output-variables.md](docs/analysis-node-output-variables.md) | 节点输出变量映射表 |
| [docs/analysis-dsl-structure.md](docs/analysis-dsl-structure.md) | Dify DSL 结构逆向分析 |
| [docs/analysis-call-chain.md](docs/analysis-call-chain.md) | 导入导出调用链分析 |
| [docs/analysis-data-structures.md](docs/analysis-data-structures.md) | 核心数据结构分析 |
| [docs/dify-dsl研究/](docs/dify-dsl研究/) | 5 种应用类型对比研究 |
| [docs/examples/](docs/examples/) | 示例工作流说明文档 |

## 示例

详细查看 [使用案例](./docs/examples/使用案例.md)