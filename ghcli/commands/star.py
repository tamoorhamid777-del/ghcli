"""Star command — star, unstar, and list starred repositories."""
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
def star():
    """Star, unstar, and list starred repositories."""


@star.command("list")
@click.option("--user", "-u", default=None, help="List stars for another user (default: yourself).")
@click.option("--sort", default="created", type=click.Choice(["created", "updated"]))
@click.option("--limit", "-n", default=20, show_default=True)
@click.option("--json", "as_json", is_flag=True)
def star_list(user: str | None, sort: str, limit: int, as_json: bool) -> None:
    """List starred repositories."""
    client = _client()
    endpoint = f"/users/{user}/starred" if user else "/user/starred"
    items = client.get(endpoint, params={"sort": sort, "per_page": min(limit, 100)})
    if isinstance(items, list):
        items = items[:limit]
    if as_json:
        click.echo(json.dumps(items, indent=2))
        return
    title = f"Stars — {user}" if user else "Your Starred Repos"
    table = Table(title=title, box=box.ROUNDED)
    table.add_column("Repo", style="cyan")
    table.add_column("⭐", justify="right")
    table.add_column("Language")
    table.add_column("Description")
    for r in items:
        table.add_row(
            r.get("full_name", ""),
            str(r.get("stargazers_count", 0)),
            r.get("language") or "",
            (r.get("description") or "")[:55],
        )
    console.print(table)


@star.command("add")
@click.argument("repo")
def star_add(repo: str) -> None:
    """Star REPO (owner/repo)."""
    client = _client()
    client.put(f"/user/starred/{repo}", json=None)
    console.print(f"[green]⭐ Starred {repo}[/green]")


@star.command("remove")
@click.argument("repo")
def star_remove(repo: str) -> None:
    """Unstar REPO (owner/repo)."""
    client = _client()
    client.delete(f"/user/starred/{repo}")
    console.print(f"[yellow]✓ Unstarred {repo}[/yellow]")


@star.command("check")
@click.argument("repo")
def star_check(repo: str) -> None:
    """Check if you have starred REPO (owner/repo)."""
    client = _client()
    try:
        client.get(f"/user/starred/{repo}")
        console.print(f"[green]⭐ You have starred {repo}[/green]")
    except Exception:
        console.print(f"[dim]You have not starred {repo}[/dim]")
