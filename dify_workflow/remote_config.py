"""Persistent storage for Dify remote login profiles."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CONFIG_PATH_ENV_VAR = "DIFY_WORKFLOW_CREDENTIALS_FILE"
DEFAULT_CONFIG_DIRNAME = ".dify-workflow"
DEFAULT_CONFIG_FILENAME = "credentials.json"


def normalize_server_url(server: str) -> str:
    """Normalize a user-provided Dify server URL."""
    normalized = server.strip().rstrip("/")
    if not normalized:
        raise ValueError("Server URL cannot be empty.")
    if "://" not in normalized:
        normalized = f"http://{normalized}"

    for suffix in ("/console/api", "/console"):
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
            break

    return normalized.rstrip("/")


@dataclass(slots=True)
class RemoteProfile:
    """Saved remote login state for one Dify server/workspace."""

    server: str
    email: str
    workspace_id: str | None = None
    workspace_name: str | None = None
    auth_type: str = "session"
    access_token: str | None = None
    refresh_token: str | None = None
    csrf_token: str | None = None
    cookie_prefix: str = ""

    def __post_init__(self) -> None:
        self.server = normalize_server_url(self.server)
        self.email = self.email.strip()

    @property
    def has_session(self) -> bool:
        return bool(self.access_token and self.refresh_token and self.csrf_token)

    def to_dict(self) -> dict[str, Any]:
        return {
            "server": self.server,
            "email": self.email,
            "workspace_id": self.workspace_id,
            "workspace_name": self.workspace_name,
            "auth_type": self.auth_type,
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "csrf_token": self.csrf_token,
            "cookie_prefix": self.cookie_prefix,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RemoteProfile":
        return cls(
            server=str(data.get("server", "")),
            email=str(data.get("email", "")),
            workspace_id=_optional_str(data.get("workspace_id")),
            workspace_name=_optional_str(data.get("workspace_name")),
            auth_type=str(data.get("auth_type", "session") or "session"),
            access_token=_optional_str(data.get("access_token")),
            refresh_token=_optional_str(data.get("refresh_token")),
            csrf_token=_optional_str(data.get("csrf_token")),
            cookie_prefix=str(data.get("cookie_prefix", "") or ""),
        )


@dataclass(slots=True)
class RemoteCredentials:
    """Collection of saved remote profiles."""

    profiles: dict[str, RemoteProfile] = field(default_factory=dict)
    active_profile: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "profiles": {name: profile.to_dict() for name, profile in self.profiles.items()},
            "active_profile": self.active_profile,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RemoteCredentials":
        raw_profiles = data.get("profiles") or {}
        profiles: dict[str, RemoteProfile] = {}
        if isinstance(raw_profiles, dict):
            for name, raw_profile in raw_profiles.items():
                if not isinstance(raw_profile, dict):
                    continue
                profiles[str(name)] = RemoteProfile.from_dict(raw_profile)
        active_profile = _optional_str(data.get("active_profile"))
        return cls(profiles=profiles, active_profile=active_profile)

    def get_profile(self, profile_name: str | None = None) -> tuple[str, RemoteProfile]:
        selected_name = profile_name or self.active_profile
        if not selected_name:
            raise KeyError("No active remote profile configured.")
        profile = self.profiles.get(selected_name)
        if profile is None:
            raise KeyError(f"Remote profile not found: {selected_name}")
        return selected_name, profile

    def set_profile(self, profile_name: str, profile: RemoteProfile, *, set_active: bool = True) -> None:
        self.profiles[profile_name] = profile
        if set_active:
            self.active_profile = profile_name


def resolve_credentials_path(path: str | Path | None = None) -> Path:
    """Return the configured credentials file path."""
    if path is not None:
        return Path(path)

    from_env = os.environ.get(CONFIG_PATH_ENV_VAR)
    if from_env:
        return Path(from_env)

    return Path.home() / DEFAULT_CONFIG_DIRNAME / DEFAULT_CONFIG_FILENAME


def load_remote_credentials(path: str | Path | None = None) -> RemoteCredentials:
    """Load saved remote credentials from disk."""
    credentials_path = resolve_credentials_path(path)
    if not credentials_path.exists():
        return RemoteCredentials()

    raw = credentials_path.read_text(encoding="utf-8")
    if not raw.strip():
        return RemoteCredentials()

    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Invalid credentials file: expected a JSON object.")
    return RemoteCredentials.from_dict(data)


def save_remote_credentials(credentials: RemoteCredentials, path: str | Path | None = None) -> Path:
    """Save remote credentials to disk."""
    credentials_path = resolve_credentials_path(path)
    credentials_path.parent.mkdir(parents=True, exist_ok=True)
    credentials_path.write_text(
        json.dumps(credentials.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    if os.name != "nt":
        credentials_path.chmod(0o600)

    return credentials_path


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None