"""CLI integration tests using Click's test runner."""

import json
import subprocess
import sys
import pytest
from click.testing import CliRunner
from pathlib import Path

from dify_workflow.cli import cli
from dify_workflow.io import load_workflow


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def tmp_workflow(tmp_path):
    return tmp_path / "test.yaml"


class TestHelpDiscovery:
    """Test that all commands have --help and are progressively discoverable."""

    def test_root_help(self, runner):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "QUICK START" in result.output
        assert "FOR AI AGENTS" in result.output
        assert "guide" in result.output
        assert "list-node-types" in result.output
        assert "remote" in result.output

    def test_root_no_args_shows_help(self, runner):
        result = runner.invoke(cli, [])
        assert result.exit_code == 0
        assert "QUICK START" in result.output

    def test_root_help_module_subprocess(self):
        result = subprocess.run(
            [sys.executable, "-m", "dify_workflow.cli", "--help"],
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        stdout = result.stdout.decode("utf-8")
        assert "QUICK START" in stdout

    def test_guide_help(self, runner):
        result = runner.invoke(cli, ["guide", "--help"])
        assert result.exit_code == 0
        assert "Step-by-step" in result.output

    def test_list_node_types_help(self, runner):
        result = runner.invoke(cli, ["list-node-types", "--help"])
        assert result.exit_code == 0
        assert "22" in result.output

    def test_create_help(self, runner):
        result = runner.invoke(cli, ["create", "--help"])
        assert result.exit_code == 0
        assert "TEMPLATES" in result.output
        assert "NEXT STEPS" in result.output
        assert "minimal" in result.output
        assert "llm" in result.output

    def test_edit_help(self, runner):
        result = runner.invoke(cli, ["edit", "--help"])
        assert result.exit_code == 0
        assert "SUBCOMMANDS" in result.output
        assert "add-node" in result.output
        assert "DISCOVERY" in result.output

    def test_edit_add_node_help(self, runner):
        result = runner.invoke(cli, ["edit", "add-node", "--help"])
        assert result.exit_code == 0
        assert "EXAMPLES" in result.output
        assert "DISCOVER NODE TYPES" in result.output
        assert "NEXT STEPS" in result.output

    def test_edit_add_edge_help(self, runner):
        result = runner.invoke(cli, ["edit", "add-edge", "--help"])
        assert result.exit_code == 0
        assert "NOTES" in result.output
        assert "source-handle" in result.output

    def test_validate_help(self, runner):
        result = runner.invoke(cli, ["validate", "--help"])
        assert result.exit_code == 0
        assert "CHECKS PERFORMED" in result.output
        assert "EXIT CODES" in result.output

    def test_inspect_help(self, runner):
        result = runner.invoke(cli, ["inspect", "--help"])
        assert result.exit_code == 0
        assert "MERMAID OUTPUT" in result.output

    def test_export_help(self, runner):
        result = runner.invoke(cli, ["export", "--help"])
        assert result.exit_code == 0
        assert "EXAMPLES" in result.output

    def test_diff_help(self, runner):
        result = runner.invoke(cli, ["diff", "--help"])
        assert result.exit_code == 0
        assert "EXAMPLES" in result.output

    def test_import_help(self, runner):
        result = runner.invoke(cli, ["import", "--help"])
        assert result.exit_code == 0
        assert "EXAMPLES" in result.output

    def test_remote_help(self, runner):
        result = runner.invoke(cli, ["remote", "--help"])
        assert result.exit_code == 0
        assert "login" in result.output
        assert "push" in result.output
        assert "pull" in result.output
        assert "list" in result.output

    def test_remote_login_help_explains_server_url(self, runner):
        result = runner.invoke(cli, ["remote", "login", "--help"])
        assert result.exit_code == 0
        assert "Dify base URL" in result.output
        assert "http://localhost" in result.output
        assert "/signin" in result.output


class TestGuideCommand:
    def test_guide_human(self, runner):
        result = runner.invoke(cli, ["guide"])
        assert result.exit_code == 0
        assert "Step 1" in result.output
        assert "Step 6" in result.output
        assert "dify-workflow" in result.output

    def test_guide_json(self, runner):
        result = runner.invoke(cli, ["guide", "-j"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total"] == 6
        assert len(data["steps"]) == 6
        assert data["steps"][0]["step"] == 1
        assert "command" in data["steps"][0]


class TestListNodeTypesCommand:
    def test_list_all_human(self, runner):
        result = runner.invoke(cli, ["list-node-types"])
        assert result.exit_code == 0
        assert "start" in result.output
        assert "llm" in result.output
        assert "code" in result.output

    def test_list_all_json(self, runner):
        result = runner.invoke(cli, ["list-node-types", "-j"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total"] == 25
        types = [t["type"] for t in data["node_types"]]
        assert "start" in types
        assert "llm" in types
        assert "end" in types

    def test_single_type(self, runner):
        result = runner.invoke(cli, ["list-node-types", "--type", "llm"])
        assert result.exit_code == 0
        assert "llm" in result.output
        assert "model" in result.output

    def test_single_type_json(self, runner):
        result = runner.invoke(cli, ["list-node-types", "--type", "code", "-j"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["type"] == "code"
        assert "usage" in data

    def test_unknown_type(self, runner):
        result = runner.invoke(cli, ["list-node-types", "--type", "nonexistent"])
        assert result.exit_code != 0


class TestCreateCommand:
    def test_create_minimal(self, runner, tmp_workflow):
        result = runner.invoke(cli, ["create", "--name", "CLI Test", "--output", str(tmp_workflow)])
        assert result.exit_code == 0
        assert tmp_workflow.exists()

    def test_create_llm(self, runner, tmp_workflow):
        result = runner.invoke(cli, [
            "create", "--name", "LLM CLI", "--output", str(tmp_workflow),
            "--template", "llm", "--model-name", "gpt-4",
        ])
        assert result.exit_code == 0

    def test_create_ifelse(self, runner, tmp_workflow):
        result = runner.invoke(cli, [
            "create", "--name", "IF CLI", "--output", str(tmp_workflow),
            "--template", "if-else",
        ])
        assert result.exit_code == 0

    def test_create_json_output(self, runner, tmp_workflow):
        result = runner.invoke(cli, [
            "create", "--name", "JSON Out", "--output", str(tmp_workflow), "-j",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "created"


class TestValidateCommand:
    def test_validate_valid(self, runner, tmp_workflow):
        runner.invoke(cli, ["create", "--output", str(tmp_workflow)])
        result = runner.invoke(cli, ["validate", str(tmp_workflow)])
        assert result.exit_code == 0

    def test_validate_json(self, runner, tmp_workflow):
        runner.invoke(cli, ["create", "--output", str(tmp_workflow)])
        result = runner.invoke(cli, ["validate", str(tmp_workflow), "-j"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["valid"] is True

    def test_validate_nonexistent(self, runner):
        result = runner.invoke(cli, ["validate", "nonexistent.yaml"])
        assert result.exit_code != 0


class TestInspectCommand:
    def test_inspect(self, runner, tmp_workflow):
        runner.invoke(cli, ["create", "--name", "Inspect Me", "--output", str(tmp_workflow)])
        result = runner.invoke(cli, ["inspect", str(tmp_workflow)])
        assert result.exit_code == 0
        assert "Inspect Me" in result.output

    def test_inspect_json(self, runner, tmp_workflow):
        runner.invoke(cli, ["create", "--name", "Inspect JSON", "--output", str(tmp_workflow)])
        result = runner.invoke(cli, ["inspect", str(tmp_workflow), "-j"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["app"]["name"] == "Inspect JSON"
        assert data["node_count"] == 2

    def test_inspect_mermaid(self, runner, tmp_workflow):
        runner.invoke(cli, ["create", "--name", "Mermaid Test", "--template", "llm", "--output", str(tmp_workflow)])
        result = runner.invoke(cli, ["inspect", str(tmp_workflow), "--mermaid"])
        assert result.exit_code == 0
        assert "flowchart TD" in result.output
        assert "start_node" in result.output
        assert "-->" in result.output

    def test_inspect_mermaid_short_flag(self, runner, tmp_workflow):
        runner.invoke(cli, ["create", "--output", str(tmp_workflow)])
        result = runner.invoke(cli, ["inspect", str(tmp_workflow), "-m"])
        assert result.exit_code == 0
        assert "flowchart TD" in result.output


class TestExportCommand:
    def test_export_yaml(self, runner, tmp_workflow, tmp_path):
        runner.invoke(cli, ["create", "--output", str(tmp_workflow)])
        out = tmp_path / "exported.yaml"
        result = runner.invoke(cli, ["export", str(tmp_workflow), "--output", str(out)])
        assert result.exit_code == 0
        assert out.exists()

    def test_export_json(self, runner, tmp_workflow, tmp_path):
        runner.invoke(cli, ["create", "--output", str(tmp_workflow)])
        out = tmp_path / "exported.json"
        result = runner.invoke(cli, ["export", str(tmp_workflow), "--output", str(out), "--format", "json"])
        assert result.exit_code == 0

    def test_export_stdout(self, runner, tmp_workflow):
        runner.invoke(cli, ["create", "--name", "Stdout", "--output", str(tmp_workflow)])
        result = runner.invoke(cli, ["export", str(tmp_workflow)])
        assert result.exit_code == 0
        assert "Stdout" in result.output


class TestEditCommands:
    def test_add_node(self, runner, tmp_workflow):
        runner.invoke(cli, ["create", "--output", str(tmp_workflow)])
        result = runner.invoke(cli, [
            "edit", "add-node", "-f", str(tmp_workflow),
            "--type", "code", "--title", "My Code", "-j",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "added"

    def test_remove_node(self, runner, tmp_workflow):
        runner.invoke(cli, ["create", "--output", str(tmp_workflow)])
        result = runner.invoke(cli, [
            "edit", "remove-node", "-f", str(tmp_workflow), "--id", "end_node", "-j",
        ])
        assert result.exit_code == 0

    def test_update_node(self, runner, tmp_workflow):
        runner.invoke(cli, ["create", "--output", str(tmp_workflow)])
        result = runner.invoke(cli, [
            "edit", "update-node", "-f", str(tmp_workflow),
            "--id", "start_node", "-d", '{"title": "New Start"}', "-j",
        ])
        assert result.exit_code == 0

    def test_update_node_data_file_revalidates_typed_fields(self, runner, tmp_workflow, tmp_path):
        runner.invoke(cli, ["create", "--output", str(tmp_workflow)])
        payload = tmp_path / "start_update.json"
        payload.write_text(json.dumps({
            "variables": [
                {
                    "variable": "user_query",
                    "label": "用户诉求",
                    "type": "paragraph",
                    "required": True,
                    "options": [],
                },
                {
                    "variable": "order_id",
                    "label": "订单号",
                    "type": "text-input",
                    "required": False,
                    "options": [],
                },
            ]
        }, ensure_ascii=False), encoding="utf-8")

        result = runner.invoke(cli, [
            "edit", "update-node", "-f", str(tmp_workflow),
            "--id", "start_node", "--data-file", str(payload),
        ])

        assert result.exit_code == 0

        dsl = load_workflow(tmp_workflow)
        start = next(node for node in dsl.workflow.graph.nodes if node.id == "start_node")
        assert start.data.variables is not None
        assert start.data.variables[0].variable == "user_query"
        assert start.data.variables[1].variable == "order_id"

    def test_add_edge(self, runner, tmp_workflow):
        runner.invoke(cli, ["create", "--output", str(tmp_workflow)])
        result = runner.invoke(cli, [
            "edit", "add-edge", "-f", str(tmp_workflow),
            "--source", "start_node", "--target", "end_node", "-j",
        ])
        assert result.exit_code == 0

    def test_set_title(self, runner, tmp_workflow):
        runner.invoke(cli, ["create", "--output", str(tmp_workflow)])
        result = runner.invoke(cli, [
            "edit", "set-title", "-f", str(tmp_workflow),
            "--id", "start_node", "--title", "Begin",
        ])
        assert result.exit_code == 0


class TestDiffCommand:
    def test_diff_same(self, runner, tmp_path):
        f1 = tmp_path / "a.yaml"
        f2 = tmp_path / "b.yaml"
        runner.invoke(cli, ["create", "--name", "Same", "--output", str(f1)])
        runner.invoke(cli, ["create", "--name", "Same", "--output", str(f2)])
        result = runner.invoke(cli, ["diff", str(f1), str(f2)])
        assert result.exit_code == 0

    def test_diff_different(self, runner, tmp_path):
        f1 = tmp_path / "a.yaml"
        f2 = tmp_path / "b.yaml"
        runner.invoke(cli, ["create", "--name", "Alpha", "--output", str(f1)])
        runner.invoke(cli, ["create", "--name", "Beta", "--output", str(f2)])
        result = runner.invoke(cli, ["diff", str(f1), str(f2)])
        assert result.exit_code == 0
        assert "app.name" in result.output

    def test_diff_json_output(self, runner, tmp_path):
        f1 = tmp_path / "a.yaml"
        f2 = tmp_path / "b.yaml"
        runner.invoke(cli, ["create", "--name", "A", "--output", str(f1)])
        runner.invoke(cli, ["create", "--name", "B", "--output", str(f2)])
        result = runner.invoke(cli, ["diff", str(f1), str(f2), "-j"])
        data = json.loads(result.output)
        assert data["diff_count"] >= 1


class TestImportCommand:
    def test_import(self, runner, tmp_path):
        src = tmp_path / "source.yaml"
        dst = tmp_path / "dest.yaml"
        runner.invoke(cli, ["create", "--output", str(src)])
        result = runner.invoke(cli, ["import", str(src), "--output", str(dst)])
        assert result.exit_code == 0
        assert dst.exists()

    def test_import_validate_only(self, runner, tmp_path):
        src = tmp_path / "source.yaml"
        dst = tmp_path / "dest.yaml"
        runner.invoke(cli, ["create", "--output", str(src)])
        result = runner.invoke(cli, ["import", str(src), "--output", str(dst), "--validate-only"])
        assert result.exit_code == 0
        assert not dst.exists()


class TestEndToEnd:
    """Full create → edit → validate → export pipeline."""

    def test_full_pipeline(self, runner, tmp_path):
        wf = tmp_path / "pipeline.yaml"
        exported = tmp_path / "final.yaml"

        # Create
        r = runner.invoke(cli, ["create", "--name", "Pipeline", "--output", str(wf)])
        assert r.exit_code == 0

        # Add a code node
        r = runner.invoke(cli, [
            "edit", "add-node", "-f", str(wf),
            "--type", "code", "--title", "Transform", "--id", "code_node",
        ])
        assert r.exit_code == 0

        # Add edge to it
        r = runner.invoke(cli, [
            "edit", "add-edge", "-f", str(wf),
            "--source", "start_node", "--target", "code_node",
        ])
        assert r.exit_code == 0

        # Wire up code node variables to reference start_node
        r = runner.invoke(cli, [
            "edit", "update-node", "-f", str(wf),
            "--id", "code_node", "-d",
            '{"variables": [{"variable": "arg1", "value_selector": ["start_node", "query"]}, {"variable": "arg2", "value_selector": ["start_node", "query"]}]}',
        ])
        assert r.exit_code == 0

        # Validate
        r = runner.invoke(cli, ["validate", str(wf)])
        assert r.exit_code == 0

        # Inspect
        r = runner.invoke(cli, ["inspect", str(wf), "-j"])
        data = json.loads(r.output)
        assert data["node_count"] == 3

        # Export
        r = runner.invoke(cli, ["export", str(wf), "--output", str(exported)])
        assert r.exit_code == 0
        assert exported.exists()
