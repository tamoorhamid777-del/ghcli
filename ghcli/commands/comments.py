"""
ghcli comments — Add and manage comments on issues and pull requests.

Commands:
  create  Add a comment to an issue or PR
  list    List comments on an issue or PR
  delete  Delete a comment by ID
"""

from __future__ import annotations

import json as _json

import click
from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from ghcli.client import GitHubAPIError, GitHubClient

console = Console()


def _client() -> GitHubClient:
    c = GitHubClient()
    c.require_auth()
    return c


@click.group()
def comments() -> None:
    """Add and manage comments on issues and pull requests."""


# ── create ─────────────────────────────────────────────────────────────────


@comments.command("create")
@click.argument("repo")
@click.argument("number", type=int)
@click.option(
    "--body",
    "-b",
    default=None,
    help="Comment body (Markdown). Opens $EDITOR if omitted.",
)
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON.")
def comments_create(repo: str, number: int, body: str | None, as_json: bool) -> None:
    """Add a comment to issue/PR NUMBER in OWNER/REPO.

    \b
    Examples:
      ghcli comments create owner/repo 42 --body "Looks good to me!"
      ghcli comments create owner/repo 42          # opens $EDITOR
    """
    if not body:
        body = click.edit("<!-- Enter your comment above this line -->\n") or ""
        body = "\n".join(
            line for line in body.splitlines() if not line.strip().startswith("<!--")
        ).strip()
        if not body:
            console.print("[yellow]Aborted — empty comment.[/yellow]")
            return

    c = _client()
    try:
        comment = c.post(
            f"/repos/{repo}/issues/{number}/comments",
            json={"body": body},
        )
    except GitHubAPIError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise SystemExit(1)

    if as_json:
        click.echo(_json.dumps(comment, indent=2))
        return

    console.print(
        Panel(
            f"[bold green]✓ Comment added![/bold green]\n\n"
            f"  Issue/PR: [cyan]#{number}[/cyan] in [cyan]{repo}[/cyan]\n"
            f"  Comment ID: [dim]{comment.get('id', '')}[/dim]\n"
            f"  URL: [link]{comment.get('html_url', '')}[/link]",
            title="[bold cyan]New Comment[/bold cyan]",
            border_style="green",
        )
    )


# ── list ───────────────────────────────────────────────────────────────────


@comments.command("list")
@click.argument("repo")
@click.argument("number", type=int)
@click.option("--limit", "-n", default=20, show_default=True, help="Max comments to show.")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON.")
def comments_list(repo: str, number: int, limit: int, as_json: bool) -> None:
    """List comments on issue/PR NUMBER in OWNER/REPO.

    \b
    Example:
      ghcli comments list owner/repo 42
      ghcli comments list owner/repo 42 --json
    """
    c = _client()
    try:
        items = list(
            c.paginate(
                f"/repos/{repo}/issues/{number}/comments",
                params={"per_page": min(limit, 100)},
                max_pages=3,
            )
        )[:limit]
    except GitHubAPIError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise SystemExit(1)

    if as_json:
        click.echo(_json.dumps(items, indent=2))
        return

    if not items:
        console.print(f"[yellow]No comments on #{number} in {repo}.[/yellow]")
        return

    console.print(
        f"\n[bold]Comments on[/bold] [cyan]{repo}#{number}[/cyan]  " f"({len(items)} shown)\n"
    )
    for comment in items:
        author = comment.get("user", {}).get("login", "unknown")
        created = (comment.get("created_at") or "")[:10]
        body = comment.get("body") or "_(empty)_"
        console.print(
            Panel(
                Markdown(body),
                title=f"[dim]{author} — {created}  ID:{comment.get('id', '')}[/dim]",
                border_style="dim",
            )
        )


# ── delete ─────────────────────────────────────────────────────────────────


@comments.command("delete")
@click.argument("repo")
@click.argument("comment_id", type=int)
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation.")
def comments_delete(repo: str, comment_id: int, yes: bool) -> None:
    """Delete a comment by its ID.

    \b
    Example:
      ghcli comments delete owner/repo 987654321
    """
    if not yes:
        click.confirm(f"Delete comment {comment_id} in {repo}?", abort=True)

    c = _client()
    try:
        c.delete(f"/repos/{repo}/issues/comments/{comment_id}")
    except GitHubAPIError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise SystemExit(1)

    console.print(f"[bold green]✓ Comment {comment_id} deleted.[/bold green]")
