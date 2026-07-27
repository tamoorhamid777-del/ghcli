"""Gist command — create, list, view, and delete GitHub Gists."""

from __future__ import annotations

import json

import click
from rich import box
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table

from ghcli.client import GitHubAPIError, GitHubClient

console = Console()


def _client() -> GitHubClient:
    c = GitHubClient()
    c.require_auth()
    return c


@click.group()
def gist():
    """Manage GitHub Gists."""


@gist.command("list")
@click.option("--limit", "-n", default=10, show_default=True)
@click.option("--json", "as_json", is_flag=True)
def gist_list(limit: int, as_json: bool) -> None:
    """List your gists."""
    client = _client()
    items = client.get("/gists", params={"per_page": min(limit, 100)})
    if isinstance(items, list):
        items = items[:limit]
    if as_json:
        click.echo(json.dumps(items, indent=2))
        return
    table = Table(title="Your Gists", box=box.ROUNDED)
    table.add_column("ID", style="dim")
    table.add_column("Description", style="cyan")
    table.add_column("Files")
    table.add_column("Public")
    table.add_column("Updated")
    for g in items:
        table.add_row(
            g["id"][:8],
            (g.get("description") or "(no description)")[:50],
            str(len(g.get("files", {}))),
            "✓" if g.get("public") else "✗",
            g.get("updated_at", "")[:10],
        )
    console.print(table)


@gist.command("view")
@click.argument("gist_id")
@click.option("--json", "as_json", is_flag=True)
def gist_view(gist_id: str, as_json: bool) -> None:
    """View a gist by ID."""
    client = _client()
    g = client.get(f"/gists/{gist_id}")
    if as_json:
        click.echo(json.dumps(g, indent=2))
        return
    console.print(f"[bold cyan]{g.get('description') or '(no description)'}[/bold cyan]")
    console.print(
        f"[dim]ID: {g['id']} | Public: {g.get('public')} | Updated: {g.get('updated_at', '')[:10]}[/dim]\n"
    )
    for fname, fdata in g.get("files", {}).items():
        console.print(f"[bold yellow]── {fname} ──[/bold yellow]")
        lang = fdata.get("language") or "text"
        content = fdata.get("content") or ""
        console.print(Syntax(content, lang.lower(), theme="monokai", line_numbers=True))


@gist.command("create")
@click.argument("filename")
@click.argument("content")
@click.option("--description", "-d", default="", help="Gist description.")
@click.option("--public", is_flag=True, default=False, help="Make gist public.")
def gist_create(filename: str, content: str, description: str, public: bool) -> None:
    """Create a new gist. FILENAME is the file name, CONTENT is the text."""
    client = _client()
    payload = {
        "description": description,
        "public": public,
        "files": {filename: {"content": content}},
    }
    g = client.post("/gists", json=payload)
    console.print(f"[green]✓ Gist created:[/green] {g.get('html_url')}")
    console.print(f"  ID: [cyan]{g['id']}[/cyan]")


@gist.command("delete")
@click.argument("gist_id")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation.")
def gist_delete(gist_id: str, yes: bool) -> None:
    """Delete a gist by ID."""
    client = _client()
    if not yes:
        click.confirm(f"Delete gist {gist_id}?", abort=True)
    client.delete(f"/gists/{gist_id}")
    console.print(f"[green]✓ Gist {gist_id} deleted.[/green]")
