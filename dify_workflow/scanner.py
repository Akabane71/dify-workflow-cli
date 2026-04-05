"""Source code scanner - analyzes dify-test project to extract workflow DSL generation chain."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


# Key files in dify-test that relate to workflow DSL
WORKFLOW_KEY_FILES = {
    "dsl_service": "api/services/app_dsl_service.py",
    "workflow_service": "api/services/workflow_service.py",
    "workflow_model": "api/models/workflow.py",
    "workflow_converter": "api/services/workflow/workflow_converter.py",
    "node_factory": "api/core/workflow/node_factory.py",
    "workflow_entry": "api/core/workflow/workflow_entry.py",
    "app_config_manager": "api/core/app/apps/workflow/app_config_manager.py",
    "app_generator": "api/core/app/apps/workflow/app_generator.py",
    "export_controller": "api/controllers/console/app/app.py",
    "import_controller": "api/controllers/console/app/app_import.py",
}

WORKFLOW_NODE_DIRS = [
    "api/core/workflow/nodes/knowledge_retrieval",
    "api/core/workflow/nodes/trigger_webhook",
    "api/core/workflow/nodes/trigger_schedule",
    "api/core/workflow/nodes/trigger_plugin",
    "api/core/workflow/nodes/agent",
    "api/core/workflow/nodes/datasource",
    "api/core/workflow/nodes/knowledge_index",
]

DSL_GENERATION_CHAIN = """
=== Dify Workflow DSL Generation Chain ===

1. EXPORT FLOW (Code → YAML):
   AppExportApi.get()  [controllers/console/app/app.py]
   → AppDslService.export_dsl(app_model, include_secret)  [services/app_dsl_service.py]
     → WorkflowService.get_draft_workflow(app_model)  [services/workflow_service.py]
     → Workflow.to_dict(include_secret)  [models/workflow.py]
       → Workflow.graph_dict  (JSON parse of graph field)
       → Workflow.features_dict  (JSON parse of features field)
       → environment_variables / conversation_variables / rag_pipeline_variables
     → Filter sensitive data (encrypt dataset_ids, remove credentials)
     → Extract dependencies (tool providers, model providers)
     → yaml.dump(export_data)
   → Return YAML string

2. IMPORT FLOW (YAML → Code):
   AppImportApi.post()  [controllers/console/app/app_import.py]
   → AppDslService.import_app(account, yaml_content)  [services/app_dsl_service.py]
     → yaml.safe_load(content)
     → Check version compatibility
     → Create/update App model
     → Create/update Workflow model (graph stored as JSON string)
   → Return ImportStatus

3. KEY DATA STRUCTURES:
   - DifyWorkflowDSL (top-level: version, kind, app, workflow, dependencies)
   - WorkflowContent (graph, features, environment_variables, etc.)
   - Graph (nodes: list[Node], edges: list[Edge])
   - Node (id, type="custom", position, data: NodeData)
   - NodeData (type: NodeType, title, + type-specific fields)
   - Edge (id, source, target, sourceHandle, targetHandle, data: EdgeData)

4. DSL VERSION: 0.6.0

5. FORMAT: YAML (primary), JSON (internal storage)
"""


def scan_dify_project(project_path: str | Path) -> dict[str, Any]:
    """Scan the dify-test project and return analysis of workflow DSL structure."""
    root = Path(project_path)
    if not root.exists():
        raise FileNotFoundError(f"Project directory not found: {root}")

    result: dict[str, Any] = {
        "project_root": str(root),
        "key_files": {},
        "node_directories": [],
        "test_fixtures": [],
        "generation_chain": DSL_GENERATION_CHAIN.strip(),
    }

    # Check key files
    for name, rel_path in WORKFLOW_KEY_FILES.items():
        full = root / rel_path
        result["key_files"][name] = {
            "path": rel_path,
            "exists": full.exists(),
            "size": full.stat().st_size if full.exists() else 0,
        }

    # Check node directories
    for nd in WORKFLOW_NODE_DIRS:
        full = root / nd
        if full.exists():
            files = [f.name for f in full.iterdir() if f.is_file() and f.suffix == ".py"]
            result["node_directories"].append({"path": nd, "files": files})

    # Find test fixtures
    fixtures_dir = root / "api" / "tests" / "fixtures" / "workflow"
    if fixtures_dir.exists():
        result["test_fixtures"] = [
            f.name for f in fixtures_dir.iterdir() if f.suffix in (".yml", ".yaml", ".json")
        ]

    return result


def get_fixture_path(project_path: str | Path, fixture_name: str) -> Path | None:
    """Get the full path to a test fixture file."""
    root = Path(project_path)
    fixtures_dir = root / "api" / "tests" / "fixtures" / "workflow"
    if not fixtures_dir.exists():
        return None

    # Try exact name
    p = fixtures_dir / fixture_name
    if p.exists():
        return p

    # Try with extension
    for ext in (".yml", ".yaml", ".json"):
        p = fixtures_dir / f"{fixture_name}{ext}"
        if p.exists():
            return p

    return None
