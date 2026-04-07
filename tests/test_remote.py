"""Tests for remote Dify Console login and sync features."""

from __future__ import annotations

import json
from pathlib import Path

import base64

import httpx

from dify_workflow.editor import create_minimal_workflow
from dify_workflow.io import save_workflow
from dify_workflow.remote_client import DifyRemoteClient, RemoteSession
from dify_workflow.remote_config import RemoteCredentials, RemoteProfile, load_remote_credentials, save_remote_credentials
from dify_workflow.remote_service import RemoteService


def _cookie_headers(
    access_token: str = "access-1",
    refresh_token: str = "refresh-1",
    csrf_token: str = "csrf-1",
) -> list[tuple[str, str]]:
    return [
        ("set-cookie", f"access_token={access_token}; Path=/"),
        ("set-cookie", f"refresh_token={refresh_token}; Path=/"),
        ("set-cookie", f"csrf_token={csrf_token}; Path=/"),
    ]


def _json_body(request: httpx.Request) -> dict[str, object]:
    raw = request.content.decode("utf-8")
    return json.loads(raw) if raw else {}


def _save_profile(config_path: Path) -> None:
    credentials = RemoteCredentials(
        profiles={
            "default": RemoteProfile(
                server="http://localhost:5001",
                email="user@example.com",
                workspace_id="ws-1",
                workspace_name="Workspace One",
                access_token="access-1",
                refresh_token="refresh-1",
                csrf_token="csrf-1",
            )
        },
        active_profile="default",
    )
    save_remote_credentials(credentials, config_path)


def test_remote_client_login_injects_cookies_and_csrf_headers() -> None:
    recorded_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/console/api/login":
            body = _json_body(request)
            assert body["email"] == "user@example.com"
            assert base64.b64decode(body["password"]).decode("utf-8") == "secret"
            return httpx.Response(200, json={"result": "success"}, headers=_cookie_headers())

        if request.url.path == "/console/api/apps/imports":
            recorded_headers["cookie"] = request.headers.get("cookie", "")
            recorded_headers["csrf"] = request.headers.get("x-csrf-token", "")
            return httpx.Response(
                200,
                json={
                    "id": "import-1",
                    "status": "completed",
                    "app_id": "app-1",
                    "app_mode": "workflow",
                    "current_dsl_version": "0.6.0",
                    "imported_dsl_version": "0.6.0",
                    "error": "",
                },
            )

        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    transport = httpx.MockTransport(handler)
    with DifyRemoteClient("http://localhost:5001", transport=transport) as client:
        session = client.login("user@example.com", "secret")
        assert session.access_token == "access-1"
        result = client.import_app(yaml_content="version: 0.6.0\n")

    assert result.status == "completed"
    assert "access_token=access-1" in recorded_headers["cookie"]
    assert "refresh_token=refresh-1" in recorded_headers["cookie"]
    assert "csrf_token=csrf-1" in recorded_headers["cookie"]
    assert recorded_headers["csrf"] == "csrf-1"


def test_remote_client_sends_csrf_header_on_get_requests() -> None:
    observed_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/console/api/login":
            return httpx.Response(200, json={"result": "success"}, headers=_cookie_headers())

        if request.url.path == "/console/api/workspaces":
            observed_headers["csrf"] = request.headers.get("x-csrf-token", "")
            observed_headers["cookie"] = request.headers.get("cookie", "")
            return httpx.Response(200, json={"workspaces": []})

        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    transport = httpx.MockTransport(handler)
    with DifyRemoteClient("http://localhost:5001", transport=transport) as client:
        client.login("user@example.com", "secret")
        client.list_workspaces()

    assert observed_headers["csrf"] == "csrf-1"
    assert "csrf_token=csrf-1" in observed_headers["cookie"]


def test_remote_client_refreshes_and_retries_after_401() -> None:
    import_attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal import_attempts

        if request.url.path == "/console/api/apps/imports":
            import_attempts += 1
            if import_attempts == 1:
                assert request.headers.get("x-csrf-token") == "csrf-old"
                return httpx.Response(401, json={"message": "expired"})

            assert request.headers.get("x-csrf-token") == "csrf-new"
            assert "access_token=access-new" in request.headers.get("cookie", "")
            return httpx.Response(
                200,
                json={
                    "id": "import-2",
                    "status": "completed",
                    "app_id": "app-2",
                    "app_mode": "workflow",
                    "current_dsl_version": "0.6.0",
                    "imported_dsl_version": "0.6.0",
                    "error": "",
                },
            )

        if request.url.path == "/console/api/refresh-token":
            return httpx.Response(200, json={"result": "success"}, headers=_cookie_headers("access-new", "refresh-new", "csrf-new"))

        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    transport = httpx.MockTransport(handler)
    session = RemoteSession(
        access_token="access-old",
        refresh_token="refresh-old",
        csrf_token="csrf-old",
    )
    with DifyRemoteClient("http://localhost:5001", session=session, transport=transport) as client:
        result = client.import_app(yaml_content="version: 0.6.0\n")
        assert result.status == "completed"
        assert client.session is not None
        assert client.session.access_token == "access-new"
        assert client.session.refresh_token == "refresh-new"
        assert client.session.csrf_token == "csrf-new"

    assert import_attempts == 2


def test_remote_service_login_selects_workspace_and_persists_profile(tmp_path: Path) -> None:
    config_path = tmp_path / "credentials.json"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/console/api/login":
            return httpx.Response(200, json={"result": "success"}, headers=_cookie_headers())

        if request.url.path == "/console/api/workspaces" and request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "workspaces": [
                        {"id": "ws-1", "name": "Workspace One", "current": True, "status": "normal"},
                        {"id": "ws-2", "name": "Workspace Two", "current": False, "status": "normal"},
                    ]
                },
            )

        if request.url.path == "/console/api/workspaces/switch":
            body = _json_body(request)
            assert body["tenant_id"] == "ws-2"
            assert request.headers.get("x-csrf-token") == "csrf-1"
            return httpx.Response(
                200,
                json={
                    "result": "success",
                    "new_tenant": {"id": "ws-2", "name": "Workspace Two", "status": "normal"},
                },
            )

        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    service = RemoteService(config_path=config_path, transport=httpx.MockTransport(handler))
    result = service.login(
        profile_name="default",
        server="http://localhost:5001/console",
        email="user@example.com",
        password="secret",
        workspace_selector=lambda workspaces, current: "ws-2",
    )

    credentials = load_remote_credentials(config_path)
    _, profile = credentials.get_profile("default")

    assert result.workspace.id == "ws-2"
    assert credentials.active_profile == "default"
    assert profile.server == "http://localhost:5001"
    assert profile.workspace_id == "ws-2"
    assert profile.workspace_name == "Workspace Two"
    assert profile.access_token == "access-1"


def test_remote_service_push_validates_and_confirms_pending(tmp_path: Path) -> None:
    config_path = tmp_path / "credentials.json"
    workflow_path = tmp_path / "workflow.yaml"
    _save_profile(config_path)
    save_workflow(create_minimal_workflow("Remote Push Test"), workflow_path)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/console/api/workspaces/switch":
            return httpx.Response(
                200,
                json={
                    "result": "success",
                    "new_tenant": {"id": "ws-1", "name": "Workspace One", "status": "normal"},
                },
            )

        if request.url.path == "/console/api/apps/imports":
            body = _json_body(request)
            assert body["mode"] == "yaml-content"
            assert "Remote Push Test" in str(body["yaml_content"])
            assert request.headers.get("x-csrf-token") == "csrf-1"
            return httpx.Response(
                202,
                json={
                    "id": "import-3",
                    "status": "pending",
                    "app_id": None,
                    "app_mode": "workflow",
                    "current_dsl_version": "0.6.0",
                    "imported_dsl_version": "0.6.0",
                    "error": "",
                },
            )

        if request.url.path == "/console/api/apps/imports/import-3/confirm":
            return httpx.Response(
                200,
                json={
                    "id": "import-3",
                    "status": "completed",
                    "app_id": "app-3",
                    "app_mode": "workflow",
                    "current_dsl_version": "0.6.0",
                    "imported_dsl_version": "0.6.0",
                    "error": "",
                },
            )

        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    service = RemoteService(config_path=config_path, transport=httpx.MockTransport(handler))
    result = service.push(workflow_path, force=True)

    assert result.status == "completed"
    assert result.app_id == "app-3"


def test_remote_service_pull_writes_output_file(tmp_path: Path) -> None:
    config_path = tmp_path / "credentials.json"
    output_path = tmp_path / "downloaded.yaml"
    _save_profile(config_path)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/console/api/workspaces/switch":
            return httpx.Response(
                200,
                json={
                    "result": "success",
                    "new_tenant": {"id": "ws-1", "name": "Workspace One", "status": "normal"},
                },
            )

        if request.url.path == "/console/api/apps/app-1/export":
            return httpx.Response(200, json={"data": "version: 0.6.0\napp:\n  name: Pulled App\n"})

        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    service = RemoteService(config_path=config_path, transport=httpx.MockTransport(handler))
    result = service.pull("app-1", output_path=output_path)

    assert result.output_path == output_path
    assert output_path.read_text(encoding="utf-8").startswith("version: 0.6.0")


def test_remote_client_delete_app_calls_delete_endpoint() -> None:
    seen_request: tuple[str, str] | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_request
        seen_request = (request.method, request.url.path)
        return httpx.Response(204)

    session = RemoteSession(
        access_token="access-1",
        refresh_token="refresh-1",
        csrf_token="csrf-1",
    )
    with DifyRemoteClient("http://localhost:5001", session=session, transport=httpx.MockTransport(handler)) as client:
        client.delete_app("app-42")

    assert seen_request == ("DELETE", "/console/api/apps/app-42")


def test_remote_service_list_apps_returns_page(tmp_path: Path) -> None:
    config_path = tmp_path / "credentials.json"
    _save_profile(config_path)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/console/api/workspaces/switch":
            return httpx.Response(
                200,
                json={
                    "result": "success",
                    "new_tenant": {"id": "ws-1", "name": "Workspace One", "status": "normal"},
                },
            )

        if request.url.path == "/console/api/apps":
            assert request.url.params["page"] == "2"
            assert request.url.params["limit"] == "5"
            return httpx.Response(
                200,
                json={
                    "page": 2,
                    "limit": 5,
                    "total": 1,
                    "has_more": False,
                    "data": [
                        {
                            "id": "app-1",
                            "name": "Remote App",
                            "mode": "workflow",
                            "description": "demo",
                            "access_mode": "private",
                        }
                    ],
                },
            )

        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    service = RemoteService(config_path=config_path, transport=httpx.MockTransport(handler))
    app_page = service.list_apps(page=2, limit=5)

    assert app_page.page == 2
    assert app_page.limit == 5
    assert app_page.total == 1
    assert len(app_page.data) == 1
    assert app_page.data[0].name == "Remote App"