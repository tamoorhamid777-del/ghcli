"""
ghcli commits — Commit history commands.

Commands:
  list     List recent commits for a repository
  view     Show full details of a single commit
  compare  Compare two commits/branches
"""

from __future__ import annotations

import click
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ghcli.client import GitHubAPIError, GitHubClient

console = Console()


def _client() -> GitHubClient:
    c = GitHubClient()
    c.require_auth()
    return c


@click.group()
def commits() -> None:
    """View commit history for a repository."""


# ── list ───────────────────────────────────────────────────────────────────


@commits.command("list")
@click.argument("repo")
@click.option("--branch", "-b", default=None, help="Branch/tag/SHA (default: repo default branch).")
@click.option("--author", "-a", default=None, help="Filter by author GitHub login or email.")
@click.option("--path", "-p", default=None, help="Only commits touching this file path.")
@click.option("--since", "-s", default=None, help="ISO 8601 date (e.g. 2024-01-01).")
@click.option("--until", "-u", default=None, help="ISO 8601 date (e.g. 2024-12-31).")
@click.option("--limit", "-n", default=20, show_default=True, help="Max commits to show.")
@click.option("--json", "output_json", is_flag=True, default=False, help="Output raw JSON.")
def commits_list(
    repo: str,
    branch: str | None,
    author: str | None,
    path: str | None,
    since: str | None,
    until: str | None,
    limit: int,
    output_json: bool,
) -> None:
    """List recent commits for OWNER/REPO."""
    c = _client()
    params: dict = {"per_page": min(limit, 100)}
    if branch:
        params["sha"] = branch
    if author:
        params["author"] = author
    if path:
        params["path"] = path
    if since:
        params["since"] = since if "T" in since else f"{since}T00:00:00Z"
    if until:
        params["until"] = until if "T" in until else f"{until}T23:59:59Z"

    try:
        items = list(c.paginate(f"/repos/{repo}/commits", params=params, max_pages=3))[:limit]
    except GitHubAPIError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise SystemExit(1)

    if not items:
        console.print(f"[yellow]No commits found for {repo}.[/yellow]")
        return

    if output_json:
        import json as _json

        console.print(_json.dumps(items, indent=2))
        return

    table = Table(
        title=f"Commits in {repo}" + (f" ({branch})" if branch else ""),
        box=box.ROUNDED,
        border_style="cyan",
        header_style="bold cyan",
        show_lines=False,
    )
    table.add_column("SHA", style="bold yellow", width=9)
    table.add_column("Message", min_width=45)
    table.add_column("Author", width=18)
    table.add_column("Date", width=12)

    for commit in items:
        sha = commit["sha"][:7]
        msg_lines = (commit["commit"]["message"] or "").splitlines()
        subject = msg_lines[0][:72] if msg_lines else "—"
        author_name = (commit.get("author") or {}).get("login") or commit["commit"]["author"].get(
            "name", "—"
        )
        date = (commit["commit"]["author"].get("date") or "")[:10]
        table.add_row(sha, subject, author_name, date)

    console.print(table)


# ── view ───────────────────────────────────────────────────────────────────


@commits.command("view")
@click.argument("repo")
@click.argument("sha")
def commits_view(repo: str, sha: str) -> None:
    """Show full details of a single commit by SHA (or short SHA)."""
    c = _client()
    try:
        commit = c.get(f"/repos/{repo}/commits/{sha}")
    except GitHubAPIError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise SystemExit(1)

    full_sha = commit["sha"]
    git = commit["commit"]
    author = git["author"]
    committer = git["committer"]
    stats = commit.get("stats", {})
    files = commit.get("files", [])

    meta = Table(show_header=False, box=None, padding=(0, 2))
    meta.add_column("Key", style="bold cyan", width=14)
    meta.add_column("Value")
    meta.add_row("SHA", full_sha)
    meta.add_row("Author", f"{author.get('name')} <{author.get('email')}>")
    meta.add_row("Date", (author.get("date") or "")[:19].replace("T", " "))
    meta.add_row("Committer", f"{committer.get('name')} <{committer.get('email')}>")
    meta.add_row("+additions", f"[green]+{stats.get('additions', 0)}[/green]")
    meta.add_row("-deletions", f"[red]-{stats.get('deletions', 0)}[/red]")
    meta.add_row("Total changes", str(stats.get("total", 0)))
    meta.add_row("URL", commit.get("html_url", ""))

    console.print(
        Panel(meta, title=f"[bold yellow]{full_sha[:7]}[/bold yellow]", border_style="yellow")
    )

    # Full commit message
    console.print(Panel(git["message"], title="[dim]Commit Message[/dim]", border_style="dim"))

    # Changed files
    if files:
        ftable = Table(title="Changed Files", box=box.SIMPLE, header_style="bold cyan")
        ftable.add_column("Status", width=10)
        ftable.add_column("File")
        ftable.add_column("+", justify="right", width=8, style="green")
        ftable.add_column("-", justify="right", width=8, style="red")
        for f in files[:50]:
            status_color = {
                "added": "green",
                "removed": "red",
                "modified": "yellow",
                "renamed": "cyan",
                "copied": "blue",
            }.get(f["status"], "white")
            ftable.add_row(
                f"[{status_color}]{f['status']}[/{status_color}]",
                f["filename"],
                str(f.get("additions", 0)),
                str(f.get("deletions", 0)),
            )
        console.print(ftable)


# ── compare ────────────────────────────────────────────────────────────────


@commits.command("compare")
@click.argument("repo")
@click.argument("base")
@click.argument("head")
def commits_compare(repo: str, base: str, head: str) -> None:
    """Compare two commits/branches: BASE...HEAD."""
    c = _client()
    try:
        result = c.get(f"/repos/{repo}/compare/{base}...{head}")
    except GitHubAPIError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise SystemExit(1)

    console.print(
        Panel(
            f"[bold]Status:[/bold]        {result.get('status', '—')}\n"
            f"[bold]Ahead by:[/bold]      {result.get('ahead_by', 0)} commits\n"
            f"[bold]Behind by:[/bold]     {result.get('behind_by', 0)} commits\n"
            f"[bold]Total commits:[/bold] {result.get('total_commits', 0)}\n"
            f"[bold]Files changed:[/bold] {len(result.get('files', []))}",
            title=f"[bold cyan]{base}...{head}[/bold cyan]",
            border_style="cyan",
        )
    )

    commits_data = result.get("commits", [])
    if commits_data:
        table = Table(box=box.SIMPLE, header_style="bold cyan")
        table.add_column("SHA", style="bold yellow", width=9)
        table.add_column("Message", min_width=45)
        table.add_column("Author", width=18)
        for commit in commits_data:
            sha = commit["sha"][:7]
            msg = (commit["commit"]["message"] or "").splitlines()[0][:72]
            author = (commit.get("author") or {}).get("login") or commit["commit"]["author"].get(
                "name", "—"
            )
            table.add_row(sha, msg, author)
        console.print(table)
