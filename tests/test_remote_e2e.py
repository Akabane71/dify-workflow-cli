"""Optional live end-to-end tests for remote Dify Console sync.

Enable explicitly with:
    DIFY_REMOTE_E2E=1
    DIFY_REMOTE_E2E_SERVER=http://localhost
    DIFY_REMOTE_E2E_EMAIL=you@example.com
    DIFY_REMOTE_E2E_PASSWORD=secret

Optional:
    DIFY_REMOTE_E2E_WORKSPACE_ID=<workspace-id>
    DIFY_REMOTE_E2E_INSECURE=1
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

import pytest
from click.testing import CliRunner

from dify_workflow.cli import cli
from dify_workflow.editor import create_minimal_workflow
from dify_workflow.io import load_workflow, save_workflow
from dify_workflow.remote_client import DifyRemoteClient, RemoteSession
from dify_workflow.remote_config import CONFIG_PATH_ENV_VAR, load_remote_credentials

REMOTE_E2E_ENABLED = os.environ.get("DIFY_REMOTE_E2E") == "1"


@pytest.mark.skipif(not REMOTE_E2E_ENABLED, reason="Set DIFY_REMOTE_E2E=1 to run live remote E2E tests.")
def test_remote_cli_roundtrip_against_live_dify(tmp_path: Path) -> None:
    server = os.environ.get("DIFY_REMOTE_E2E_SERVER", "http://localhost")
    email = _require_env("DIFY_REMOTE_E2E_EMAIL")
    password = _require_env("DIFY_REMOTE_E2E_PASSWORD")
    insecure = _truthy_env("DIFY_REMOTE_E2E_INSECURE")
    workspace_id = os.environ.get("DIFY_REMOTE_E2E_WORKSPACE_ID") or _resolve_workspace_id(
        server=server,
        email=email,
        password=password,
        verify=not insecure,
    )

    profile_name = f"e2e-{uuid.uuid4().hex[:8]}"
    config_path = tmp_path / "credentials.json"
    workflow_name = f"Remote E2E {uuid.uuid4().hex[:10]}"
    workflow_path = tmp_path / "remote-e2e.yaml"
    pulled_path = tmp_path / "pulled.yaml"
    runner = CliRunner()
    cli_env = {CONFIG_PATH_ENV_VAR: str(config_path)}
    created_app_id: str | None = None

    save_workflow(create_minimal_workflow(workflow_name), workflow_path)

    try:
        login_result = runner.invoke(
            cli,
            _login_args(
                profile_name=profile_name,
                server=server,
                email=email,
                password=password,
                workspace_id=workspace_id,
                insecure=insecure,
            ),
            env=cli_env,
        )
        assert login_result.exit_code == 0, login_result.output
        login_payload = json.loads(login_result.output)
        assert login_payload["profile_name"] == profile_name
        assert login_payload["workspace"]["id"] == workspace_id

        push_result = runner.invoke(
            cli,
            _push_args(
                profile_name=profile_name,
                workflow_path=workflow_path,
                insecure=insecure,
            ),
            env=cli_env,
        )
        assert push_result.exit_code == 0, push_result.output
        push_payload = json.loads(push_result.output)
        assert push_payload["status"] in {"completed", "completed-with-warnings"}
        created_app_id = push_payload["app_id"]
        assert created_app_id

        listed_app = _wait_for_app_in_list(
            runner=runner,
            cli_env=cli_env,
            profile_name=profile_name,
            app_id=created_app_id,
            insecure=insecure,
        )
        assert listed_app["name"] == workflow_name

        pull_result = runner.invoke(
            cli,
            _pull_args(
                profile_name=profile_name,
                app_id=created_app_id,
                output_path=pulled_path,
                insecure=insecure,
            ),
            env=cli_env,
        )
        assert pull_result.exit_code == 0, pull_result.output
        pull_payload = json.loads(pull_result.output)
        assert pull_payload["output_path"] == str(pulled_path)
        pulled_workflow = load_workflow(pulled_path)
        assert pulled_workflow.app.name == workflow_name
    finally:
        if created_app_id:
            _delete_app(
                config_path=config_path,
                profile_name=profile_name,
                app_id=created_app_id,
                verify=not insecure,
            )


def _login_args(
    *,
    profile_name: str,
    server: str,
    email: str,
    password: str,
    workspace_id: str,
    insecure: bool,
) -> list[str]:
    args = [
        "remote",
        "login",
        "--profile",
        profile_name,
        "--server",
        server,
        "--email",
        email,
        "--password",
        password,
        "--workspace-id",
        workspace_id,
        "--json-output",
    ]
    if insecure:
        args.append("--insecure")
    return args


def _push_args(*, profile_name: str, workflow_path: Path, insecure: bool) -> list[str]:
    args = [
        "remote",
        "push",
        "--profile",
        profile_name,
        "--file",
        str(workflow_path),
        "--force",
        "--json-output",
    ]
    if insecure:
        args.append("--insecure")
    return args


def _pull_args(*, profile_name: str, app_id: str, output_path: Path, insecure: bool) -> list[str]:
    args = [
        "remote",
        "pull",
        "--profile",
        profile_name,
        "--app-id",
        app_id,
        "--output",
        str(output_path),
        "--json-output",
    ]
    if insecure:
        args.append("--insecure")
    return args


def _wait_for_app_in_list(
    *,
    runner: CliRunner,
    cli_env: dict[str, str],
    profile_name: str,
    app_id: str,
    insecure: bool,
) -> dict[str, object]:
    for _ in range(10):
        page = 1
        while True:
            result = runner.invoke(
                cli,
                _list_args(
                    profile_name=profile_name,
                    page=page,
                    limit=100,
                    insecure=insecure,
                ),
                env=cli_env,
            )
            assert result.exit_code == 0, result.output
            payload = json.loads(result.output)
            for item in payload.get("data", []):
                if item.get("id") == app_id:
                    return item
            if not payload.get("has_more"):
                break
            page += 1
        time.sleep(1)

    pytest.fail(f"Remote app {app_id} did not appear in list output within the retry window.")


def _list_args(*, profile_name: str, page: int, limit: int, insecure: bool) -> list[str]:
    args = [
        "remote",
        "list",
        "--profile",
        profile_name,
        "--page",
        str(page),
        "--limit",
        str(limit),
        "--json-output",
    ]
    if insecure:
        args.append("--insecure")
    return args


def _delete_app(*, config_path: Path, profile_name: str, app_id: str, verify: bool) -> None:
    credentials = load_remote_credentials(config_path)
    _, profile = credentials.get_profile(profile_name)
    session = RemoteSession(
        access_token=profile.access_token or "",
        refresh_token=profile.refresh_token or "",
        csrf_token=profile.csrf_token or "",
        cookie_prefix=profile.cookie_prefix,
    )
    with DifyRemoteClient(profile.server, verify=verify, session=session) as client:
        if profile.workspace_id:
            client.switch_workspace(profile.workspace_id)
        client.delete_app(app_id)


def _resolve_workspace_id(*, server: str, email: str, password: str, verify: bool) -> str:
    with DifyRemoteClient(server, verify=verify) as client:
        client.login(email, password)
        workspaces = client.list_workspaces()

    current = next((workspace for workspace in workspaces if workspace.current), None)
    if current is not None:
        return current.id
    if len(workspaces) == 1:
        return workspaces[0].id
    pytest.fail("Set DIFY_REMOTE_E2E_WORKSPACE_ID when the test account can access multiple workspaces.")


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if value:
        return value
    pytest.fail(f"Missing required environment variable: {name}")


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}