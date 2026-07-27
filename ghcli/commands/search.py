"""Search command — search repos, issues, code, and users on GitHub."""
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
def search():
    """Search GitHub for repos, issues, code, and users."""


@search.command("repos")
@click.argument("query")
@click.option("--language", "-l", default=None, help="Filter by programming language.")
@click.option("--sort", "-s", default="best-match", type=click.Choice(["best-match", "stars", "forks", "updated"]), help="Sort order.")
@click.option("--limit", "-n", default=10, show_default=True, help="Max results.")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON.")
def search_repos(query: str, language: str | None, sort: str, limit: int, as_json: bool) -> None:
    """Search GitHub repositories."""
    client = _client()
    q = query
    if language:
        q += f" language:{language}"
    data = client.get("/search/repositories", params={"q": q, "sort": sort, "per_page": min(limit, 100)})
    items = data.get("items", [])[:limit]
    if as_json:
        click.echo(json.dumps(items, indent=2))
        return
    table = Table(title=f"Repos matching '{query}'", box=box.ROUNDED)
    table.add_column("Repo", style="cyan")
    table.add_column("⭐ Stars", justify="right")
    table.add_column("Language")
    table.add_column("Description")
    for r in items:
        table.add_row(
            r["full_name"],
            str(r.get("stargazers_count", 0)),
            r.get("language") or "",
            (r.get("description") or "")[:60],
        )
    console.print(table)
    console.print(f"[dim]Total: {data.get('total_count', 0):,} results[/dim]")


@search.command("issues")
@click.argument("query")
@click.option("--sort", "-s", default="best-match", type=click.Choice(["best-match", "created", "updated", "comments"]))
@click.option("--limit", "-n", default=10, show_default=True)
@click.option("--json", "as_json", is_flag=True)
def search_issues(query: str, sort: str, limit: int, as_json: bool) -> None:
    """Search GitHub issues and pull requests."""
    client = _client()
    data = client.get("/search/issues", params={"q": query, "sort": sort, "per_page": min(limit, 100)})
    items = data.get("items", [])[:limit]
    if as_json:
        click.echo(json.dumps(items, indent=2))
        return
    table = Table(title=f"Issues matching '{query}'", box=box.ROUNDED)
    table.add_column("#", justify="right")
    table.add_column("Title", style="cyan")
    table.add_column("Repo")
    table.add_column("State")
    for i in items:
        repo_name = i.get("repository_url", "").split("/repos/")[-1]
        table.add_row(str(i["number"]), i["title"][:60], repo_name, i["state"])
    console.print(table)


@search.command("users")
@click.argument("query")
@click.option("--limit", "-n", default=10, show_default=True)
@click.option("--json", "as_json", is_flag=True)
def search_users(query: str, limit: int, as_json: bool) -> None:
    """Search GitHub users."""
    client = _client()
    data = client.get("/search/users", params={"q": query, "per_page": min(limit, 100)})
    items = data.get("items", [])[:limit]
    if as_json:
        click.echo(json.dumps(items, indent=2))
        return
    table = Table(title=f"Users matching '{query}'", box=box.ROUNDED)
    table.add_column("Login", style="cyan")
    table.add_column("Type")
    table.add_column("Profile URL")
    for u in items:
        table.add_row(u["login"], u.get("type", "User"), u.get("html_url", ""))
    console.print(table)


@search.command("code")
@click.argument("query")
@click.option("--limit", "-n", default=10, show_default=True)
@click.option("--json", "as_json", is_flag=True)
def search_code(query: str, limit: int, as_json: bool) -> None:
    """Search GitHub code."""
    client = _client()
    data = client.get("/search/code", params={"q": query, "per_page": min(limit, 100)})
    items = data.get("items", [])[:limit]
    if as_json:
        click.echo(json.dumps(items, indent=2))
        return
    table = Table(title=f"Code matching '{query}'", box=box.ROUNDED)
    table.add_column("File", style="cyan")
    table.add_column("Repo")
    table.add_column("URL")
    for c in items:
        table.add_row(c.get("name", ""), c.get("repository", {}).get("full_name", ""), c.get("html_url", "")[:60])
    console.print(table)
