"""Business logic for Dify remote login and DSL sync."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import httpx

from .checklist_validator import ChecklistError, validate_checklist
from .io import load_workflow, workflow_to_string
from .remote_client import (
    DifyRemoteClient,
    RemoteAPIError,
    RemoteAppPage,
    RemoteImportResult,
    RemoteSession,
    RemoteWorkspace,
)
from .remote_config import RemoteCredentials, RemoteProfile, load_remote_credentials, save_remote_credentials
from .validator import validate_workflow

WorkspaceSelector = Callable[[list[RemoteWorkspace], RemoteWorkspace | None], str | None]


class RemoteServiceError(RuntimeError):
    """Base error for remote service operations."""


class RemoteProfileError(RemoteServiceError):
    """Raised when a saved remote profile is missing or invalid."""


class RemoteWorkflowValidationError(RemoteServiceError):
    """Raised when local workflow validation fails before push."""

    def __init__(
        self,
        message: str,
        *,
        validation_errors: list[Any] | None = None,
        checklist_errors: list[ChecklistError] | None = None,
    ) -> None:
        super().__init__(message)
        self.validation_errors = validation_errors or []
        self.checklist_errors = checklist_errors or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "message": str(self),
            "validation_errors": [
                {
                    "level": getattr(error, "level", "error"),
                    "message": getattr(error, "message", str(error)),
                    "node_id": getattr(error, "node_id", None),
                }
                for error in self.validation_errors
            ],
            "checklist_errors": [
                {
                    "level": error.level,
                    "message": error.message,
                    "node_id": error.node_id or None,
                    "node_title": error.node_title or None,
                    "field": error.field or None,
                }
                for error in self.checklist_errors
            ],
        }


@dataclass(slots=True)
class RemoteLoginResult:
    """Result of a successful remote login."""

    profile_name: str
    server: str
    email: str
    workspace: RemoteWorkspace
    workspace_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_name": self.profile_name,
            "server": self.server,
            "email": self.email,
            "workspace": self.workspace.to_dict(),
            "workspace_count": self.workspace_count,
        }


@dataclass(slots=True)
class RemotePullResult:
    """Result of pulling a remote app export."""

    content: str
    output_path: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "output_path": str(self.output_path) if self.output_path else None,
            "content": self.content,
        }


class RemoteService:
    """Coordinates config, login, validation, and Dify Console requests."""

    def __init__(
        self,
        *,
        config_path: str | Path | None = None,
        verify: bool = True,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.config_path = Path(config_path) if config_path is not None else None
        self.verify = verify
        self.timeout = timeout
        self.transport = transport

    def login(
        self,
        *,
        profile_name: str,
        server: str,
        email: str,
        password: str,
        workspace_id: str | None = None,
        workspace_selector: WorkspaceSelector | None = None,
    ) -> RemoteLoginResult:
        with DifyRemoteClient(
            server,
            verify=self.verify,
            timeout=self.timeout,
            transport=self.transport,
        ) as client:
            session = client.login(email, password)
            workspaces = client.list_workspaces()

            if not workspaces:
                raise RemoteServiceError("Login succeeded but no workspace is available for this account.")

            selected_workspace = self._select_workspace(workspaces, workspace_id, workspace_selector)
            if not selected_workspace.current:
                selected_workspace = client.switch_workspace(selected_workspace.id)

            profile = RemoteProfile(
                server=server,
                email=email,
                workspace_id=selected_workspace.id,
                workspace_name=selected_workspace.name,
                access_token=session.access_token,
                refresh_token=session.refresh_token,
                csrf_token=session.csrf_token,
                cookie_prefix=session.cookie_prefix,
            )
            credentials = load_remote_credentials(self.config_path)
            credentials.set_profile(profile_name, profile, set_active=True)
            save_remote_credentials(credentials, self.config_path)

            return RemoteLoginResult(
                profile_name=profile_name,
                server=profile.server,
                email=profile.email,
                workspace=selected_workspace,
                workspace_count=len(workspaces),
            )

    def push(
        self,
        file_path: str | Path,
        *,
        profile_name: str | None = None,
        app_id: str | None = None,
        force: bool = False,
    ) -> RemoteImportResult:
        dsl = load_workflow(file_path)
        validation_result = validate_workflow(dsl)
        if not validation_result.valid:
            raise RemoteWorkflowValidationError(
                "Workflow validation failed.",
                validation_errors=validation_result.errors,
            )

        checklist_errors = validate_checklist(dsl)
        if checklist_errors:
            raise RemoteWorkflowValidationError(
                "Checklist validation failed.",
                checklist_errors=checklist_errors,
            )

        credentials, actual_profile_name, profile = self._load_profile(profile_name)
        with self._client_for_profile(profile) as client:
            self._ensure_workspace(client, profile)
            yaml_content = workflow_to_string(dsl, fmt="yaml")
            result = client.import_app(yaml_content=yaml_content, app_id=app_id)
            if result.status == "pending" and force:
                result = client.confirm_import(result.id)
            self._persist_profile(credentials, actual_profile_name, profile, client)
            return result

    def pull(
        self,
        app_id: str,
        *,
        profile_name: str | None = None,
        include_secret: bool = False,
        output_path: str | Path | None = None,
    ) -> RemotePullResult:
        credentials, actual_profile_name, profile = self._load_profile(profile_name)
        with self._client_for_profile(profile) as client:
            self._ensure_workspace(client, profile)
            content = client.export_app(app_id, include_secret=include_secret)
            output: Path | None = None
            if output_path is not None:
                output = Path(output_path)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(content, encoding="utf-8")
            self._persist_profile(credentials, actual_profile_name, profile, client)
            return RemotePullResult(content=content, output_path=output)

    def list_apps(
        self,
        *,
        profile_name: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> RemoteAppPage:
        credentials, actual_profile_name, profile = self._load_profile(profile_name)
        with self._client_for_profile(profile) as client:
            self._ensure_workspace(client, profile)
            app_page = client.list_apps(page=page, limit=limit)
            self._persist_profile(credentials, actual_profile_name, profile, client)
            return app_page

    def _load_profile(self, profile_name: str | None) -> tuple[RemoteCredentials, str, RemoteProfile]:
        credentials = load_remote_credentials(self.config_path)
        try:
            actual_profile_name, profile = credentials.get_profile(profile_name)
        except KeyError as exc:
            raise RemoteProfileError("No saved remote session found. Run 'dify-workflow remote login' first.") from exc

        if not profile.has_session:
            raise RemoteProfileError(
                f"Remote profile '{actual_profile_name}' has no valid session. Run 'dify-workflow remote login' again."
            )
        return credentials, actual_profile_name, profile

    def _client_for_profile(self, profile: RemoteProfile) -> DifyRemoteClient:
        session = RemoteSession(
            access_token=profile.access_token or "",
            refresh_token=profile.refresh_token or "",
            csrf_token=profile.csrf_token or "",
            cookie_prefix=profile.cookie_prefix,
        )
        return DifyRemoteClient(
            profile.server,
            verify=self.verify,
            timeout=self.timeout,
            session=session,
            transport=self.transport,
        )

    def _ensure_workspace(self, client: DifyRemoteClient, profile: RemoteProfile) -> None:
        if not profile.workspace_id:
            return
        workspace = client.switch_workspace(profile.workspace_id)
        profile.workspace_name = workspace.name

    def _persist_profile(
        self,
        credentials: RemoteCredentials,
        profile_name: str,
        profile: RemoteProfile,
        client: DifyRemoteClient,
    ) -> None:
        if client.session is not None:
            profile.access_token = client.session.access_token
            profile.refresh_token = client.session.refresh_token
            profile.csrf_token = client.session.csrf_token
            profile.cookie_prefix = client.session.cookie_prefix

        credentials.set_profile(profile_name, profile, set_active=True)
        save_remote_credentials(credentials, self.config_path)

    def _select_workspace(
        self,
        workspaces: list[RemoteWorkspace],
        workspace_id: str | None,
        workspace_selector: WorkspaceSelector | None,
    ) -> RemoteWorkspace:
        current_workspace = next((workspace for workspace in workspaces if workspace.current), None)

        if workspace_id:
            for workspace in workspaces:
                if workspace.id == workspace_id or workspace.name == workspace_id:
                    return workspace
            raise RemoteServiceError(f"Workspace not found or not accessible: {workspace_id}")

        if workspace_selector is not None and len(workspaces) > 1:
            selected_id = workspace_selector(workspaces, current_workspace)
            if selected_id:
                for workspace in workspaces:
                    if workspace.id == selected_id:
                        return workspace
                raise RemoteServiceError(f"Selected workspace is invalid: {selected_id}")

        if current_workspace is not None:
            return current_workspace
        return workspaces[0]