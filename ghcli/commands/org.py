"""Org command — list organizations, members, and repos."""
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
def org():
    """Manage GitHub organizations."""


@org.command("list")
@click.option("--limit", "-n", default=20, show_default=True)
@click.option("--json", "as_json", is_flag=True)
def org_list(limit: int, as_json: bool) -> None:
    """List organizations you belong to."""
    client = _client()
    items = client.get("/user/orgs", params={"per_page": min(limit, 100)})
    if isinstance(items, list):
        items = items[:limit]
    if as_json:
        click.echo(json.dumps(items, indent=2))
        return
    table = Table(title="Your Organizations", box=box.ROUNDED)
    table.add_column("Login", style="cyan")
    table.add_column("ID", justify="right")
    table.add_column("URL")
    for o in items:
        table.add_row(o.get("login", ""), str(o.get("id", "")), o.get("url", ""))
    console.print(table)


@org.command("members")
@click.argument("org_name")
@click.option("--role", default="all", type=click.Choice(["all", "admin", "member"]))
@click.option("--limit", "-n", default=20, show_default=True)
@click.option("--json", "as_json", is_flag=True)
def org_members(org_name: str, role: str, limit: int, as_json: bool) -> None:
    """List members of ORG_NAME."""
    client = _client()
    items = client.get(f"/orgs/{org_name}/members", params={"role": role, "per_page": min(limit, 100)})
    if isinstance(items, list):
        items = items[:limit]
    if as_json:
        click.echo(json.dumps(items, indent=2))
        return
    table = Table(title=f"Members of {org_name}", box=box.ROUNDED)
    table.add_column("Login", style="cyan")
    table.add_column("Type")
    table.add_column("Profile")
    for m in items:
        table.add_row(m.get("login", ""), m.get("type", "User"), m.get("html_url", ""))
    console.print(table)


@org.command("repos")
@click.argument("org_name")
@click.option("--type", "repo_type", default="all", type=click.Choice(["all", "public", "private", "forks", "sources"]))
@click.option("--sort", default="updated", type=click.Choice(["created", "updated", "pushed", "full_name"]))
@click.option("--limit", "-n", default=20, show_default=True)
@click.option("--json", "as_json", is_flag=True)
def org_repos(org_name: str, repo_type: str, sort: str, limit: int, as_json: bool) -> None:
    """List repositories for ORG_NAME."""
    client = _client()
    items = client.get(
        f"/orgs/{org_name}/repos",
        params={"type": repo_type, "sort": sort, "per_page": min(limit, 100)},
    )
    if isinstance(items, list):
        items = items[:limit]
    if as_json:
        click.echo(json.dumps(items, indent=2))
        return
    table = Table(title=f"Repos — {org_name}", box=box.ROUNDED)
    table.add_column("Name", style="cyan")
    table.add_column("⭐", justify="right")
    table.add_column("Language")
    table.add_column("Private")
    table.add_column("Updated")
    for r in items:
        table.add_row(
            r.get("name", ""),
            str(r.get("stargazers_count", 0)),
            r.get("language") or "",
            "✓" if r.get("private") else "",
            r.get("updated_at", "")[:10],
        )
    console.print(table)


@org.command("view")
@click.argument("org_name")
@click.option("--json", "as_json", is_flag=True)
def org_view(org_name: str, as_json: bool) -> None:
    """View details of ORG_NAME."""
    client = _client()
    o = client.get(f"/orgs/{org_name}")
    if as_json:
        click.echo(json.dumps(o, indent=2))
        return
    console.print(f"[bold cyan]{o.get('name') or o.get('login')}[/bold cyan]")
    console.print(f"[dim]{o.get('description') or ''}[/dim]")
    console.print(f"  Login:    {o.get('login')}")
    console.print(f"  Members:  {o.get('public_members_url', '').split('{')[0]}")
    console.print(f"  Repos:    {o.get('public_repos', 0)} public")
    console.print(f"  URL:      {o.get('html_url')}")
