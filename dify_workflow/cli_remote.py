"""CLI commands for remote Dify Console login and DSL sync."""

from __future__ import annotations

import sys

import click
from rich.table import Table

from .cli_shared import OrderedGroup, console, output_json
from .remote_client import RemoteAPIError, RemoteAppPage, RemoteImportResult, RemoteWorkspace
from .remote_service import (
    RemoteLoginResult,
    RemoteProfileError,
    RemotePullResult,
    RemoteService,
    RemoteServiceError,
    RemoteWorkflowValidationError,
)


@click.group(cls=OrderedGroup)
def remote() -> None:
    """Login to Dify Console and push/pull apps from a live server.

    \b
    Typical flow:
      1. dify-workflow remote login     → save a local session profile
      2. dify-workflow remote list      → view apps in the current workspace
      3. dify-workflow remote push ...  → create/update an app from local DSL
      4. dify-workflow remote pull ...  → export a remote app back to local YAML
    """


@remote.command("login")
@click.option("--profile", default="default", show_default=True, help="Local profile name to save")
@click.option(
    "--server",
    default=None,
    help=(
        "Dify base URL, usually the same address you open in a browser. "
        "Examples: http://localhost, http://127.0.0.1:8080, https://dify.example.com. "
        "Do not include page paths like /signin or /apps. /console or /console/api are accepted and stripped automatically."
    ),
)
@click.option("--email", default=None, help="Console login email")
@click.option("--password", default=None, help="Console login password (omit to prompt securely)")
@click.option("--workspace-id", default=None, help="Workspace ID to use after login")
@click.option("--insecure", is_flag=True, help="Disable TLS certificate verification")
@click.option("--json-output", "json_output", is_flag=True, help="Output result as JSON")
def login_cmd(
    profile: str,
    server: str | None,
    email: str | None,
    password: str | None,
    workspace_id: str | None,
    insecure: bool,
    json_output: bool,
) -> None:
    """Log in to Dify Console and save a reusable local session profile.

    \b
    SERVER URL GUIDE:
      • Fill in the base address of your Dify deployment.
      • If you open Dify in a browser at http://localhost, then use http://localhost.
      • If your reverse proxy exposes Dify on http://127.0.0.1:8080, then use that.
      • If you access the backend API directly, it must expose /console/api on that host.
      • Do not paste page URLs like /signin or /apps.

    \b
    EXAMPLES:
      dify-workflow remote login --server http://localhost --email you@example.com
      dify-workflow remote login --server http://127.0.0.1:8080 --email you@example.com
      dify-workflow remote login --server https://dify.example.com --email you@example.com
    """
    resolved_server = server or click.prompt(
        "Dify server URL (base URL, e.g. http://localhost or http://127.0.0.1:8080)",
        type=str,
    )
    resolved_email = email or click.prompt("Email", type=str)
    resolved_password = password or click.prompt("Password", hide_input=True, type=str)

    service = RemoteService(verify=not insecure)
    try:
        result = service.login(
            profile_name=profile,
            server=resolved_server,
            email=resolved_email,
            password=resolved_password,
            workspace_id=workspace_id,
            workspace_selector=_prompt_for_workspace if workspace_id is None else None,
        )
    except (RemoteAPIError, RemoteServiceError) as exc:
        _handle_error(exc, json_output=json_output)
        return

    if json_output:
        output_json(result.to_dict())
        return

    console.print(f"[green]✓[/green] Logged in to {result.server}")
    console.print(f"  Profile: {result.profile_name}")
    console.print(f"  Workspace: {result.workspace.name} ({result.workspace.id})")
    if result.workspace_count > 1:
        console.print(f"  Accessible workspaces: {result.workspace_count}")


@remote.command("push")
@click.option("--file", "file_path", "-f", required=True, help="Local workflow YAML/JSON file to push")
@click.option("--app-id", default=None, help="Existing remote app ID to update. Omit to create a new app")
@click.option("--profile", default=None, help="Saved remote profile name (defaults to active profile)")
@click.option("--force", is_flag=True, help="Auto-confirm pending imports caused by DSL version mismatch")
@click.option("--insecure", is_flag=True, help="Disable TLS certificate verification")
@click.option("--json-output", "json_output", is_flag=True, help="Output result as JSON")
def push_cmd(
    file_path: str,
    app_id: str | None,
    profile: str | None,
    force: bool,
    insecure: bool,
    json_output: bool,
) -> None:
    """Push a local workflow DSL file to Dify Console."""
    service = RemoteService(verify=not insecure)
    try:
        result = service.push(file_path, profile_name=profile, app_id=app_id, force=force)
    except RemoteWorkflowValidationError as exc:
        _handle_validation_error(exc, json_output=json_output)
        return
    except (RemoteAPIError, RemoteProfileError, RemoteServiceError) as exc:
        _handle_error(exc, json_output=json_output)
        return

    if json_output:
        output_json(result.to_dict())
    else:
        _print_import_result(result)

    if result.status == "pending" and not force:
        sys.exit(1)


@remote.command("pull")
@click.option("--app-id", required=True, help="Remote app ID to export")
@click.option("--output", "output_path", "-o", default=None, help="Output file path (omit to print to stdout)")
@click.option("--include-secret", is_flag=True, help="Include secrets in the exported DSL")
@click.option("--profile", default=None, help="Saved remote profile name (defaults to active profile)")
@click.option("--insecure", is_flag=True, help="Disable TLS certificate verification")
@click.option("--json-output", "json_output", is_flag=True, help="Output result as JSON")
def pull_cmd(
    app_id: str,
    output_path: str | None,
    include_secret: bool,
    profile: str | None,
    insecure: bool,
    json_output: bool,
) -> None:
    """Pull a remote Dify app export to stdout or a local file."""
    service = RemoteService(verify=not insecure)
    try:
        result = service.pull(
            app_id,
            profile_name=profile,
            include_secret=include_secret,
            output_path=output_path,
        )
    except (RemoteAPIError, RemoteProfileError, RemoteServiceError) as exc:
        _handle_error(exc, json_output=json_output)
        return

    if json_output:
        output_json(result.to_dict())
        return

    if result.output_path is not None:
        console.print(f"[green]✓[/green] Exported remote app to: {result.output_path}")
        return

    click.echo(result.content)


@remote.command("list")
@click.option("--profile", default=None, help="Saved remote profile name (defaults to active profile)")
@click.option("--page", default=1, show_default=True, type=click.IntRange(1, None), help="Results page")
@click.option("--limit", default=20, show_default=True, type=click.IntRange(1, 200), help="Results per page")
@click.option("--insecure", is_flag=True, help="Disable TLS certificate verification")
@click.option("--json-output", "json_output", is_flag=True, help="Output result as JSON")
def list_cmd(
    profile: str | None,
    page: int,
    limit: int,
    insecure: bool,
    json_output: bool,
) -> None:
    """List remote apps in the current Dify workspace."""
    service = RemoteService(verify=not insecure)
    try:
        app_page = service.list_apps(profile_name=profile, page=page, limit=limit)
    except (RemoteAPIError, RemoteProfileError, RemoteServiceError) as exc:
        _handle_error(exc, json_output=json_output)
        return

    if json_output:
        output_json(app_page.to_dict())
        return

    _print_app_page(app_page)


def _prompt_for_workspace(
    workspaces: list[RemoteWorkspace],
    current_workspace: RemoteWorkspace | None,
) -> str | None:
    if len(workspaces) <= 1:
        return None

    console.print("\n[bold]Available workspaces[/bold]")
    default_index = 1
    for index, workspace in enumerate(workspaces, start=1):
        marker = " (current)" if workspace.current else ""
        console.print(f"  {index}. {workspace.name} [{workspace.id}]{marker}")
        if current_workspace is not None and workspace.id == current_workspace.id:
            default_index = index

    selection = click.prompt(
        "Select workspace",
        type=click.IntRange(1, len(workspaces)),
        default=default_index,
        show_default=True,
    )
    return workspaces[selection - 1].id


def _print_import_result(result: RemoteImportResult) -> None:
    if result.status == "pending":
        console.print("[yellow]![yellow] Import is pending due to DSL version compatibility checks")
        console.print(f"  Import ID: {result.id}")
        console.print("  Re-run with --force to confirm the import automatically.")
        return

    if result.status == "completed-with-warnings":
        console.print("[yellow]![yellow] Import completed with warnings")
    else:
        console.print("[green]✓[/green] Import completed")

    if result.app_id:
        console.print(f"  App ID: {result.app_id}")
    if result.app_mode:
        console.print(f"  Mode: {result.app_mode}")
    if result.imported_dsl_version:
        console.print(
            f"  DSL version: {result.imported_dsl_version} → {result.current_dsl_version}"
        )


def _print_app_page(app_page: RemoteAppPage) -> None:
    if not app_page.data:
        console.print("[yellow]No apps found in the current workspace.[/yellow]")
        return

    table = Table(title=f"Remote Apps (page {app_page.page}, total {app_page.total})")
    table.add_column("Name", style="cyan")
    table.add_column("Mode", style="magenta")
    table.add_column("ID", style="dim")
    table.add_column("Access", style="dim")
    for app in app_page.data:
        table.add_row(app.name, app.mode, app.id, app.access_mode or "-")
    console.print(table)
    if app_page.has_more:
        console.print("[dim]More apps are available. Use --page to view the next page.[/dim]")


def _handle_validation_error(error: RemoteWorkflowValidationError, *, json_output: bool) -> None:
    if json_output:
        payload = error.to_dict()
        payload["status"] = "validation-error"
        output_json(payload)
    else:
        console.print(f"[red]✗[/red] {error}")
        for item in error.validation_errors:
            node_id = getattr(item, "node_id", None)
            suffix = f" (node: {node_id})" if node_id else ""
            console.print(f"  [red]error[/red]: {getattr(item, 'message', str(item))}{suffix}")
        for item in error.checklist_errors:
            node_label = item.node_title or item.node_id
            suffix = f" [{node_label}]" if node_label else ""
            console.print(f"  [red]checklist[/red]: {item.message}{suffix}")
    sys.exit(1)


def _handle_error(error: Exception, *, json_output: bool) -> None:
    if json_output:
        payload = {
            "status": "error",
            "message": str(error),
        }
        if isinstance(error, RemoteAPIError):
            payload["status_code"] = error.status_code
            payload["payload"] = error.payload
        output_json(payload)
    else:
        console.print(f"[red]✗[/red] {error}")
    sys.exit(1)