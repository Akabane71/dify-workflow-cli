"""HTTP client for Dify Console remote operations."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

import httpx

from .remote_config import normalize_server_url

ACCESS_TOKEN_COOKIE = "access_token"
REFRESH_TOKEN_COOKIE = "refresh_token"
CSRF_TOKEN_COOKIE = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"


class RemoteAPIError(RuntimeError):
    """Raised when a Dify Console API call fails."""

    def __init__(self, message: str, *, status_code: int | None = None, payload: Any = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.payload = payload


class RemoteAuthenticationError(RemoteAPIError):
    """Raised when login or session refresh fails."""


@dataclass(slots=True)
class RemoteSession:
    """Serializable session state for Dify Console access."""

    access_token: str
    refresh_token: str
    csrf_token: str
    cookie_prefix: str = ""

    def cookie_name(self, cookie_suffix: str) -> str:
        return f"{self.cookie_prefix}{cookie_suffix}"


@dataclass(slots=True)
class RemoteWorkspace:
    """Workspace information returned by Dify Console."""

    id: str
    name: str
    current: bool = False
    status: str | None = None
    plan: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RemoteWorkspace":
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            current=bool(data.get("current", False)),
            status=_optional_text(data.get("status")),
            plan=_optional_text(data.get("plan")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "current": self.current,
            "status": self.status,
            "plan": self.plan,
        }


@dataclass(slots=True)
class RemoteAppSummary:
    """Lightweight app info used by remote list."""

    id: str
    name: str
    mode: str
    description: str | None = None
    updated_at: int | None = None
    access_mode: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RemoteAppSummary":
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            mode=str(data.get("mode", "")),
            description=_optional_text(data.get("description")),
            updated_at=_optional_int(data.get("updated_at")),
            access_mode=_optional_text(data.get("access_mode")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "mode": self.mode,
            "description": self.description,
            "updated_at": self.updated_at,
            "access_mode": self.access_mode,
        }


@dataclass(slots=True)
class RemoteAppPage:
    """Paginated app list response."""

    page: int
    limit: int
    total: int
    has_more: bool
    data: list[RemoteAppSummary]

    def to_dict(self) -> dict[str, Any]:
        return {
            "page": self.page,
            "limit": self.limit,
            "total": self.total,
            "has_more": self.has_more,
            "data": [item.to_dict() for item in self.data],
        }


@dataclass(slots=True)
class RemoteImportResult:
    """Import response returned by Dify Console."""

    id: str
    status: str
    app_id: str | None = None
    app_mode: str | None = None
    current_dsl_version: str = ""
    imported_dsl_version: str = ""
    error: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RemoteImportResult":
        return cls(
            id=str(data.get("id", "")),
            status=str(data.get("status", "")),
            app_id=_optional_text(data.get("app_id")),
            app_mode=_optional_text(data.get("app_mode")),
            current_dsl_version=str(data.get("current_dsl_version", "") or ""),
            imported_dsl_version=str(data.get("imported_dsl_version", "") or ""),
            error=str(data.get("error", "") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "app_id": self.app_id,
            "app_mode": self.app_mode,
            "current_dsl_version": self.current_dsl_version,
            "imported_dsl_version": self.imported_dsl_version,
            "error": self.error,
        }


class DifyRemoteClient:
    """Minimal Dify Console client for login and DSL import/export."""

    def __init__(
        self,
        server: str,
        *,
        verify: bool = True,
        timeout: float = 30.0,
        session: RemoteSession | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.server = normalize_server_url(server)
        self._client = httpx.Client(
            base_url=f"{self.server}/console/api",
            follow_redirects=True,
            timeout=timeout,
            verify=verify,
            trust_env=False,
            transport=transport,
        )
        self._session: RemoteSession | None = None
        if session is not None:
            self.set_session(session)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "DifyRemoteClient":
        return self

    def __exit__(self, exc_type, exc, exc_tb) -> None:
        self.close()

    @property
    def session(self) -> RemoteSession | None:
        return self._session

    def set_session(self, session: RemoteSession) -> None:
        self._client.cookies.clear()
        self._client.cookies.set(session.cookie_name(ACCESS_TOKEN_COOKIE), session.access_token)
        self._client.cookies.set(session.cookie_name(REFRESH_TOKEN_COOKIE), session.refresh_token)
        self._client.cookies.set(session.cookie_name(CSRF_TOKEN_COOKIE), session.csrf_token)
        self._session = session

    def login(self, email: str, password: str) -> RemoteSession:
        response = self._client.post(
            "/login",
            json={
                "email": email,
                "password": _encode_sensitive_field(password),
                "remember_me": False,
                "invite_token": None,
            },
        )
        if response.status_code >= 400:
            raise self._build_error(response, auth_error=True)

        payload = _safe_json(response)
        if isinstance(payload, dict) and payload.get("result") == "fail":
            raise RemoteAuthenticationError(
                _extract_error_message(payload, fallback="Login failed."),
                status_code=response.status_code,
                payload=payload,
            )

        session = self._update_session_from_cookies()
        if session is None:
            raise RemoteAuthenticationError("Login succeeded but no session cookies were returned.")
        return session

    def refresh_session(self) -> RemoteSession:
        response = self._client.post(
            "/refresh-token",
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        if response.status_code >= 400:
            raise self._build_error(response, auth_error=True)

        session = self._update_session_from_cookies()
        if session is None:
            raise RemoteAuthenticationError("Token refresh succeeded but no updated session cookies were returned.")
        return session

    def list_workspaces(self) -> list[RemoteWorkspace]:
        response = self._request("GET", "/workspaces")
        payload = _expect_dict(response)
        workspaces = payload.get("workspaces") or []
        if not isinstance(workspaces, list):
            raise RemoteAPIError("Unexpected workspaces response from Dify.", status_code=response.status_code, payload=payload)
        return [RemoteWorkspace.from_dict(item) for item in workspaces if isinstance(item, dict)]

    def switch_workspace(self, workspace_id: str) -> RemoteWorkspace:
        response = self._request("POST", "/workspaces/switch", json_body={"tenant_id": workspace_id})
        payload = _expect_dict(response)
        raw_workspace = payload.get("new_tenant")
        if not isinstance(raw_workspace, dict):
            raise RemoteAPIError("Unexpected workspace switch response from Dify.", status_code=response.status_code, payload=payload)
        workspace = RemoteWorkspace.from_dict(raw_workspace)
        workspace.current = True
        return workspace

    def list_apps(self, *, page: int = 1, limit: int = 20) -> RemoteAppPage:
        response = self._request("GET", "/apps", params={"page": page, "limit": limit})
        payload = _expect_dict(response)
        raw_apps = payload.get("data") or []
        if not isinstance(raw_apps, list):
            raise RemoteAPIError("Unexpected app list response from Dify.", status_code=response.status_code, payload=payload)
        return RemoteAppPage(
            page=int(payload.get("page", page) or page),
            limit=int(payload.get("limit", limit) or limit),
            total=int(payload.get("total", 0) or 0),
            has_more=bool(payload.get("has_more", False)),
            data=[RemoteAppSummary.from_dict(item) for item in raw_apps if isinstance(item, dict)],
        )

    def import_app(self, *, yaml_content: str, app_id: str | None = None) -> RemoteImportResult:
        payload: dict[str, Any] = {"mode": "yaml-content", "yaml_content": yaml_content}
        if app_id:
            payload["app_id"] = app_id
        response = self._request("POST", "/apps/imports", json_body=payload)
        return RemoteImportResult.from_dict(_expect_dict(response))

    def confirm_import(self, import_id: str) -> RemoteImportResult:
        response = self._request("POST", f"/apps/imports/{import_id}/confirm")
        return RemoteImportResult.from_dict(_expect_dict(response))

    def export_app(self, app_id: str, *, include_secret: bool = False) -> str:
        response = self._request(
            "GET",
            f"/apps/{app_id}/export",
            params={"include_secret": str(include_secret).lower()},
        )
        payload = _expect_dict(response)
        data = payload.get("data")
        if not isinstance(data, str):
            raise RemoteAPIError("Unexpected export response from Dify.", status_code=response.status_code, payload=payload)
        return data

    def delete_app(self, app_id: str) -> None:
        self._request("DELETE", f"/apps/{app_id}")

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        retry_on_auth: bool = True,
        include_csrf: bool | None = None,
    ) -> httpx.Response:
        normalized_method = method.upper()
        # Dify's frontend sends X-CSRF-Token on all Console API requests, including GET.
        send_csrf = include_csrf if include_csrf is not None else True

        response = self._client.request(
            normalized_method,
            path,
            json=json_body,
            params=params,
            headers=self._request_headers(send_csrf),
        )
        self._update_session_from_cookies()

        if response.status_code == 401 and retry_on_auth and self._session is not None:
            self.refresh_session()
            response = self._client.request(
                normalized_method,
                path,
                json=json_body,
                params=params,
                headers=self._request_headers(send_csrf),
            )
            self._update_session_from_cookies()

        if response.status_code >= 400:
            raise self._build_error(response)
        return response

    def _request_headers(self, include_csrf: bool) -> dict[str, str]:
        headers: dict[str, str] = {}
        if include_csrf and self._session is not None:
            headers[CSRF_HEADER_NAME] = self._session.csrf_token
        return headers

    def _update_session_from_cookies(self) -> RemoteSession | None:
        session = _extract_session_from_cookies(self._client.cookies)
        if session is not None:
            # Refresh responses can leave duplicate cookie names with different domains.
            # Normalize them back into one active session snapshot for future requests.
            self.set_session(session)
        return self._session

    def _build_error(self, response: httpx.Response, *, auth_error: bool = False) -> RemoteAPIError:
        payload = _safe_json(response)
        message = _extract_error_message(payload, fallback=f"Dify request failed with status {response.status_code}.")
        error_cls = RemoteAuthenticationError if auth_error or response.status_code == 401 else RemoteAPIError
        return error_cls(message, status_code=response.status_code, payload=payload)


def _extract_session_from_cookies(cookies: httpx.Cookies) -> RemoteSession | None:
    access_name, access_token = _find_cookie(cookies, ACCESS_TOKEN_COOKIE)
    refresh_name, refresh_token = _find_cookie(cookies, REFRESH_TOKEN_COOKIE)
    csrf_name, csrf_token = _find_cookie(cookies, CSRF_TOKEN_COOKIE)

    if not access_token or not refresh_token or not csrf_token:
        return None

    prefix = ""
    for cookie_name, suffix in (
        (access_name, ACCESS_TOKEN_COOKIE),
        (refresh_name, REFRESH_TOKEN_COOKIE),
        (csrf_name, CSRF_TOKEN_COOKIE),
    ):
        if cookie_name and cookie_name.endswith(suffix):
            maybe_prefix = cookie_name[: -len(suffix)]
            if maybe_prefix:
                prefix = maybe_prefix
                break

    return RemoteSession(
        access_token=access_token,
        refresh_token=refresh_token,
        csrf_token=csrf_token,
        cookie_prefix=prefix,
    )


def _find_cookie(cookies: httpx.Cookies, suffix: str) -> tuple[str | None, str | None]:
    matches: list[tuple[str, str]] = []
    for cookie in cookies.jar:
        if cookie.name == suffix or cookie.name.endswith(suffix):
            matches.append((cookie.name, cookie.value))

    if not matches:
        return None, None

    # Prefer the most recently inserted match when multiple domains exist.
    return matches[-1]


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return None


def _expect_dict(response: httpx.Response) -> dict[str, Any]:
    payload = _safe_json(response)
    if isinstance(payload, dict):
        return payload
    raise RemoteAPIError(
        "Unexpected non-JSON response from Dify.",
        status_code=response.status_code,
        payload=payload,
    )


def _extract_error_message(payload: Any, *, fallback: str) -> str:
    if isinstance(payload, dict):
        for key in ("message", "msg", "error"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        data_value = payload.get("data")
        if isinstance(data_value, str) and data_value.strip():
            return data_value.strip()
    return fallback


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _encode_sensitive_field(value: str) -> str:
    encoded = base64.b64encode(value.encode("utf-8"))
    return encoded.decode("ascii")