"""Release command — list, create, and download GitHub releases."""
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
def release():
    """Manage GitHub releases."""


@release.command("list")
@click.argument("repo")
@click.option("--limit", "-n", default=10, show_default=True)
@click.option("--json", "as_json", is_flag=True)
def release_list(repo: str, limit: int, as_json: bool) -> None:
    """List releases for REPO (owner/repo)."""
    client = _client()
    items = client.get(f"/repos/{repo}/releases", params={"per_page": min(limit, 100)})
    if isinstance(items, list):
        items = items[:limit]
    if as_json:
        click.echo(json.dumps(items, indent=2))
        return
    table = Table(title=f"Releases — {repo}", box=box.ROUNDED)
    table.add_column("Tag", style="cyan")
    table.add_column("Name")
    table.add_column("Draft")
    table.add_column("Pre-release")
    table.add_column("Published")
    table.add_column("Assets")
    for r in items:
        table.add_row(
            r.get("tag_name", ""),
            (r.get("name") or "")[:40],
            "✓" if r.get("draft") else "",
            "✓" if r.get("prerelease") else "",
            r.get("published_at", "")[:10],
            str(len(r.get("assets", []))),
        )
    console.print(table)


@release.command("create")
@click.argument("repo")
@click.argument("tag")
@click.option("--name", "-n", default=None, help="Release name (defaults to tag).")
@click.option("--body", "-b", default="", help="Release notes.")
@click.option("--draft", is_flag=True, default=False)
@click.option("--prerelease", is_flag=True, default=False)
def release_create(repo: str, tag: str, name: str | None, body: str, draft: bool, prerelease: bool) -> None:
    """Create a release for REPO at TAG."""
    client = _client()
    payload = {
        "tag_name": tag,
        "name": name or tag,
        "body": body,
        "draft": draft,
        "prerelease": prerelease,
    }
    r = client.post(f"/repos/{repo}/releases", json=payload)
    console.print(f"[green]✓ Release created:[/green] {r.get('html_url')}")
    console.print(f"  Tag: [cyan]{r.get('tag_name')}[/cyan] | ID: {r.get('id')}")


@release.command("view")
@click.argument("repo")
@click.argument("tag")
@click.option("--json", "as_json", is_flag=True)
def release_view(repo: str, tag: str, as_json: bool) -> None:
    """View a specific release by TAG for REPO."""
    client = _client()
    r = client.get(f"/repos/{repo}/releases/tags/{tag}")
    if as_json:
        click.echo(json.dumps(r, indent=2))
        return
    console.print(f"[bold cyan]{r.get('name') or r.get('tag_name')}[/bold cyan]")
    console.print(f"[dim]Tag: {r.get('tag_name')} | Published: {r.get('published_at', '')[:10]}[/dim]")
    console.print(f"[dim]URL: {r.get('html_url')}[/dim]\n")
    if r.get("body"):
        console.print(r["body"])
    assets = r.get("assets", [])
    if assets:
        console.print(f"\n[bold]Assets ({len(assets)}):[/bold]")
        for a in assets:
            size_kb = a.get("size", 0) // 1024
            console.print(f"  • {a['name']} ({size_kb} KB) — {a.get('browser_download_url', '')}")


@release.command("download")
@click.argument("repo")
@click.argument("tag")
@click.option("--asset", "-a", default=None, help="Asset name to download (default: first asset).")
def release_download(repo: str, tag: str, asset: str | None) -> None:
    """Download a release asset from REPO at TAG."""
    import urllib.request
    client = _client()
    r = client.get(f"/repos/{repo}/releases/tags/{tag}")
    assets = r.get("assets", [])
    if not assets:
        console.print("[yellow]No assets found for this release.[/yellow]")
        return
    target = next((a for a in assets if a["name"] == asset), assets[0]) if asset else assets[0]
    url = target["browser_download_url"]
    fname = target["name"]
    console.print(f"Downloading [cyan]{fname}[/cyan] …")
    urllib.request.urlretrieve(url, fname)
    console.print(f"[green]✓ Saved to {fname}[/green]")
