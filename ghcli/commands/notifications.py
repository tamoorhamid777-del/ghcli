"""Notifications command — list and mark GitHub notifications."""
from __future__ import annotations

import json
import click
from rich.console import Console
from rich.table import Table
from rich import box

from ghcli.client import GitHubAPIError, GitHubClient

console = Console()


def _client() -> GitHubClient:
    c = GitHubClient()
    c.require_auth()
    return c


@click.group()
def notifications():
    """Manage GitHub notifications."""


@notifications.command("list")
@click.option("--all", "show_all", is_flag=True, help="Include already-read notifications.")
@click.option("--limit", "-n", default=20, show_default=True)
@click.option("--json", "as_json", is_flag=True)
def notifications_list(show_all: bool, limit: int, as_json: bool) -> None:
    """List your notifications."""
    client = _client()
    params: dict = {"per_page": min(limit, 100)}
    if show_all:
        params["all"] = "true"
    items = client.get("/notifications", params=params)
    if isinstance(items, list):
        items = items[:limit]
    if as_json:
        click.echo(json.dumps(items, indent=2))
        return
    if not items:
        console.print("[green]✓ No unread notifications.[/green]")
        return
    table = Table(title="Notifications", box=box.ROUNDED)
    table.add_column("ID", style="dim")
    table.add_column("Repo", style="cyan")
    table.add_column("Type")
    table.add_column("Subject")
    table.add_column("Updated")
    for n in items:
        table.add_row(
            n.get("id", ""),
            n.get("repository", {}).get("full_name", ""),
            n.get("subject", {}).get("type", ""),
            (n.get("subject", {}).get("title") or "")[:50],
            n.get("updated_at", "")[:10],
        )
    console.print(table)


@notifications.command("read")
@click.argument("thread_id")
def notifications_read(thread_id: str) -> None:
    """Mark a notification thread as read."""
    client = _client()
    client.patch(f"/notifications/threads/{thread_id}", json={})
    console.print(f"[green]✓ Thread {thread_id} marked as read.[/green]")


@notifications.command("read-all")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation.")
def notifications_read_all(yes: bool) -> None:
    """Mark ALL notifications as read."""
    client = _client()
    if not yes:
        click.confirm("Mark all notifications as read?", abort=True)
    client.put("/notifications", json={})
    console.print("[green]✓ All notifications marked as read.[/green]")
