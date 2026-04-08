"""Core data models for Dify Workflow DSL, reverse-engineered from dify-test source code.

The DSL structure follows version 0.6.0 format:
  Top-level: version, kind, app, workflow, dependencies
  workflow: graph (nodes + edges), features, environment_variables, conversation_variables, rag_pipeline_variables
  Each node: id, type="custom", position, data (type-specific fields)
  Each edge: id, source, target, sourceHandle, targetHandle, type="custom", data
"""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# --- Enums ---

class AppMode(StrEnum):
    WORKFLOW = "workflow"
    ADVANCED_CHAT = "advanced-chat"
    AGENT_CHAT = "agent-chat"
    CHAT = "chat"
    COMPLETION = "completion"


class NodeType(StrEnum):
    START = "start"
    END = "end"
    ANSWER = "answer"
    LLM = "llm"
    TOOL = "tool"
    CODE = "code"
    IF_ELSE = "if-else"
    TEMPLATE_TRANSFORM = "template-transform"
    QUESTION_CLASSIFIER = "question-classifier"
    PARAMETER_EXTRACTOR = "parameter-extractor"
    HTTP_REQUEST = "http-request"
    KNOWLEDGE_RETRIEVAL = "knowledge-retrieval"
    VARIABLE_AGGREGATOR = "variable-aggregator"
    VARIABLE_ASSIGNER = "assigner"
    LIST_OPERATOR = "list-operator"
    ITERATION = "iteration"
    LOOP = "loop"
    AGENT = "agent"
    DOCUMENT_EXTRACTOR = "document-extractor"
    HUMAN_INPUT = "human-input"
    KNOWLEDGE_INDEX = "knowledge-index"
    DATASOURCE = "datasource"
    TRIGGER_WEBHOOK = "trigger-webhook"
    TRIGGER_SCHEDULE = "trigger-schedule"
    TRIGGER_PLUGIN = "trigger-plugin"


class VariableType(StrEnum):
    TEXT_INPUT = "text-input"
    PARAGRAPH = "paragraph"
    SELECT = "select"
    NUMBER = "number"
    FILE = "file"
    FILE_LIST = "file-list"


# --- Sub-models ---

class Position(BaseModel):
    x: float = 0.0
    y: float = 0.0


class StartVariable(BaseModel):
    variable: str
    label: str = ""
    type: VariableType = VariableType.TEXT_INPUT
    required: bool = True
    max_length: int | None = None
    options: list[str] = Field(default_factory=list)
    # Code nodes reuse the variables field with value_selector for input binding
    value_selector: list[str] = Field(default_factory=list)

    def model_post_init(self, __context: Any) -> None:
        if not self.label:
            self.label = self.variable


class OutputVariable(BaseModel):
    variable: str
    value_selector: list[str] = Field(default_factory=list)
    value_type: str = "string"


class ModelConfig(BaseModel):
    provider: str = "openai"
    name: str = "gpt-3.5-turbo"
    mode: str = "chat"
    completion_params: dict[str, Any] = Field(default_factory=dict)


class PromptMessage(BaseModel):
    role: str = "user"
    text: str = ""


class VisionConfig(BaseModel):
    enabled: bool = False
    configs: dict[str, Any] = Field(default_factory=lambda: {"variable_selector": []})


class MemoryConfig(BaseModel):
    enabled: bool = False
    window: dict[str, Any] = Field(default_factory=lambda: {"enabled": False, "size": 50})


class ContextConfig(BaseModel):
    enabled: bool = False
    variable_selector: list[str] = Field(default_factory=list)


class RetryConfig(BaseModel):
    enabled: bool = False
    max_retries: int = 1
    retry_interval: int = 1000
    exponential_backoff: dict[str, Any] = Field(
        default_factory=lambda: {"enabled": False, "multiplier": 2, "max_interval": 10000}
    )


class IfElseCondition(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    comparison_operator: str = "contains"
    value: str = ""
    varType: str = "string"
    variable_selector: list[str] = Field(default_factory=list)


class IfElseCase(BaseModel):
    id: str = "true"
    case_id: str = "true"
    conditions: list[IfElseCondition] = Field(default_factory=list)
    logical_operator: str = "and"


# --- Node Data ---

class NodeData(BaseModel):
    """Base node data. The `type` field determines the node kind."""
    type: NodeType
    title: str = ""
    desc: str = ""
    selected: bool = False
    # Start node variables
    variables: list[StartVariable] | list[list[str]] | None = None
    # End node outputs (list) or Code node outputs (dict mapping name → {type, children})
    outputs: list[OutputVariable] | dict[str, Any] | None = None
    # LLM node
    model: ModelConfig | None = None
    prompt_template: list[PromptMessage] | None = None
    vision: VisionConfig | None = None
    memory: MemoryConfig | None = None
    context: ContextConfig | None = None
    structured_output: dict[str, Any] | None = None
    retry_config: RetryConfig | None = None
    # Code node
    code: str | None = None
    code_language: str | None = None
    # IF/ELSE node
    cases: list[IfElseCase] | None = None
    # Tool node
    provider_id: str | None = None
    provider_type: str | None = None
    tool_name: str | None = None
    tool_parameters: dict[str, Any] | None = None
    credential_id: str | None = None
    # HTTP Request node
    url: str | None = None
    method: str | None = None
    headers: str | None = None
    body: dict[str, Any] | None = None
    # Knowledge Retrieval
    dataset_ids: list[str] | None = None
    retrieval_model: dict[str, Any] | None = None
    query_variable_selector: list[str] | None = None
    # Template Transform
    template: str | None = None
    # Iteration
    iterator_selector: list[str] | None = None
    output_selector: list[str] | None = None

    model_config = {"extra": "allow"}


class Node(BaseModel):
    id: str = Field(default_factory=lambda: str(int(time.time() * 1000)))
    type: str = "custom"
    data: NodeData
    position: Position = Field(default_factory=Position)
    positionAbsolute: Position | None = None
    width: int = 244
    height: int = 90
    selected: bool = False
    sourcePosition: str = "right"
    targetPosition: str = "left"

    model_config = {"extra": "allow"}


class EdgeData(BaseModel):
    sourceType: str = ""
    targetType: str = ""
    isInIteration: bool = False
    isInLoop: bool = False

    model_config = {"extra": "allow"}


class Edge(BaseModel):
    id: str = ""
    source: str
    target: str
    sourceHandle: str = "source"
    targetHandle: str = "target"
    type: str = "custom"
    zIndex: int = 0
    data: EdgeData = Field(default_factory=EdgeData)

    model_config = {"extra": "allow"}

    def model_post_init(self, __context: Any) -> None:
        if not self.id:
            self.id = f"{self.source}-{self.sourceHandle}-{self.target}-{self.targetHandle}"


class Viewport(BaseModel):
    x: float = 0
    y: float = 0
    zoom: float = 1.0


class Graph(BaseModel):
    nodes: list[Node] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)
    viewport: Viewport = Field(default_factory=Viewport)

    model_config = {"extra": "allow"}


class Features(BaseModel):
    file_upload: dict[str, Any] = Field(default_factory=lambda: {"enabled": False})
    opening_statement: str = ""
    retriever_resource: dict[str, Any] = Field(default_factory=lambda: {"enabled": False})
    sensitive_word_avoidance: dict[str, Any] = Field(default_factory=lambda: {"enabled": False})
    speech_to_text: dict[str, Any] = Field(default_factory=lambda: {"enabled": False})
    suggested_questions: list[str] = Field(default_factory=list)
    suggested_questions_after_answer: dict[str, Any] = Field(default_factory=lambda: {"enabled": False})
    text_to_speech: dict[str, Any] = Field(default_factory=lambda: {"enabled": False})

    model_config = {"extra": "allow"}


class EnvironmentVariable(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    value: str = ""
    value_type: str = "string"
    description: str = ""

    model_config = {"extra": "allow"}


class WorkflowContent(BaseModel):
    graph: Graph = Field(default_factory=Graph)
    features: Features = Field(default_factory=Features)
    environment_variables: list[EnvironmentVariable] = Field(default_factory=list)
    conversation_variables: list[dict[str, Any]] = Field(default_factory=list)
    rag_pipeline_variables: list[dict[str, Any]] = Field(default_factory=list)

    model_config = {"extra": "allow"}


class AppInfo(BaseModel):
    name: str = "Untitled Workflow"
    mode: AppMode = AppMode.WORKFLOW
    icon: str = "🤖"
    icon_type: str = "emoji"
    icon_background: str = "#FFEAD5"
    description: str = ""
    use_icon_as_answer_icon: bool = False

    model_config = {"extra": "allow"}


class Dependency(BaseModel):
    name: str = ""
    type: str = ""
    version: str = ""

    model_config = {"extra": "allow"}


# --- ModelConfig-based models (chat / agent-chat / completion) ---

class AgentToolConfig(BaseModel):
    """A single tool in agent_mode.tools."""
    tool_type: str = "builtin"
    provider_id: str = ""
    tool_name: str = ""
    tool_parameters: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow"}


class AgentModeConfig(BaseModel):
    """Agent mode configuration (used in model_config for agent-chat apps)."""
    enabled: bool = False
    strategy: str = "function_call"
    tools: list[AgentToolConfig] = Field(default_factory=list)

    model_config = {"extra": "allow"}


class DatasetConfig(BaseModel):
    """Dataset/knowledge base configuration."""
    datasets: dict[str, Any] = Field(default_factory=lambda: {"datasets": []})
    retrieval_model: str = "single"
    top_k: int = 4
    score_threshold: float | None = None
    score_threshold_enabled: bool = False
    reranking_mode: str | None = None

    model_config = {"extra": "allow"}


class ModelConfigContent(BaseModel):
    """The model_config section for chat/agent-chat/completion modes.

    This replaces the workflow section for non-workflow-based apps.
    Contains model settings, prompts, agent config, dataset config, and features.
    """
    model: dict[str, Any] = Field(default_factory=lambda: {
        "provider": "openai", "name": "gpt-4o", "mode": "chat",
        "completion_params": {"temperature": 0.7},
    })
    pre_prompt: str = ""
    prompt_type: str = "simple"
    chat_prompt_config: dict[str, Any] = Field(default_factory=lambda: {
        "prompt": [],
    })
    completion_prompt_config: dict[str, Any] = Field(default_factory=lambda: {
        "prompt": {"text": ""},
        "conversation_histories_role": {
            "user_prefix": "",
            "assistant_prefix": "",
        },
    })
    user_input_form: list[dict[str, Any]] = Field(default_factory=list)
    dataset_query_variable: str = ""
    opening_statement: str = ""
    suggested_questions: list[str] = Field(default_factory=list)
    suggested_questions_after_answer: dict[str, Any] = Field(default_factory=lambda: {"enabled": False})
    retriever_resource: dict[str, Any] = Field(default_factory=lambda: {"enabled": False})
    more_like_this: dict[str, Any] = Field(default_factory=lambda: {"enabled": False})
    sensitive_word_avoidance: dict[str, Any] = Field(default_factory=lambda: {"enabled": False})
    speech_to_text: dict[str, Any] = Field(default_factory=lambda: {"enabled": False})
    text_to_speech: dict[str, Any] = Field(default_factory=lambda: {"enabled": False, "language": "", "voice": ""})
    file_upload: dict[str, Any] = Field(default_factory=lambda: {"enabled": False})
    agent_mode: dict[str, Any] = Field(default_factory=lambda: {"enabled": False, "tools": []})
    dataset_configs: dict[str, Any] = Field(default_factory=lambda: {
        "datasets": {"datasets": []},
        "retrieval_model": "single",
    })
    annotation_reply: dict[str, Any] | None = None

    model_config = {"extra": "allow"}


CURRENT_DSL_VERSION = "0.6.0"

WORKFLOW_MODES = frozenset({AppMode.WORKFLOW, AppMode.ADVANCED_CHAT})
CONFIG_MODES = frozenset({AppMode.CHAT, AppMode.AGENT_CHAT, AppMode.COMPLETION})


class DifyDSL(BaseModel):
    """Universal top-level DSL document supporting all Dify app modes.

    - Workflow-based modes (workflow, advanced-chat): use ``workflow`` field
    - ModelConfig-based modes (chat, agent-chat, completion): use ``model_config_content`` field
    """
    version: str = CURRENT_DSL_VERSION
    kind: str = "app"
    app: AppInfo = Field(default_factory=AppInfo)
    workflow: WorkflowContent = Field(default_factory=WorkflowContent)
    model_config_content: ModelConfigContent | None = Field(
        default=None,
        validation_alias="model_config",
        serialization_alias="model_config",
    )
    dependencies: list[Dependency] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    @property
    def is_workflow_based(self) -> bool:
        return self.app.mode in WORKFLOW_MODES

    @property
    def is_config_based(self) -> bool:
        return self.app.mode in CONFIG_MODES


# Backward compatibility alias
DifyWorkflowDSL = DifyDSL
