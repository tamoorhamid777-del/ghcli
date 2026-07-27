"""
ghcli issues — Issue management commands.

Commands:
  list     List issues in a repository
  view     View a single issue with comments
  create   Create a new issue
  close    Close an issue (with optional comment)
  reopen   Reopen a closed issue
  comment  Add a comment to an issue
"""

from __future__ import annotations

import click
from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ghcli.client import GitHubAPIError, GitHubClient

console = Console()


def _client() -> GitHubClient:
    c = GitHubClient()
    c.require_auth()
    return c


def _state_badge(state: str) -> Text:
    if state == "open":
        return Text("● open", style="bold green")
    return Text("✓ closed", style="bold red")


@click.group()
def issues() -> None:
    """Manage GitHub issues."""


# ── list ───────────────────────────────────────────────────────────────────

@issues.command("list")
@click.argument("repo")
@click.option(
    "--state",
    default="open",
    type=click.Choice(["open", "closed", "all"]),
    show_default=True,
)
@click.option("--label", "-l", default=None, help="Filter by label.")
@click.option("--assignee", "-a", default=None, help="Filter by assignee username.")
@click.option("--limit", "-n", default=20, show_default=True, help="Max issues to show.")
@click.option(
    "--sort",
    default="created",
    type=click.Choice(["created", "updated", "comments"]),
    show_default=True,
)
@click.option("--json", "output_json", is_flag=True, default=False, help="Output raw JSON.")
def issues_list(
    repo: str,
    state: str,
    label: str | None,
    assignee: str | None,
    limit: int,
    sort: str,
    output_json: bool,
) -> None:
    """List issues for OWNER/REPO."""
    c = _client()
    params: dict = {"state": state, "sort": sort, "per_page": min(limit, 100)}
    if label:
        params["labels"] = label
    if assignee:
        params["assignee"] = assignee

    try:
        items = list(c.paginate(f"/repos/{repo}/issues", params=params, max_pages=3))[:limit]
        # GitHub issues endpoint also returns PRs — filter them out
        items = [i for i in items if "pull_request" not in i]
    except GitHubAPIError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise SystemExit(1)

    if not items:
        console.print(f"[yellow]No {state} issues found in {repo}.[/yellow]")
        return

    if output_json:
        import json as _json
        console.print(_json.dumps(items, indent=2))
        return

    table = Table(
        title=f"Issues in {repo} ({state}) — {len(items)} shown",
        box=box.ROUNDED,
        border_style="cyan",
        header_style="bold cyan",
        show_lines=False,
    )
    table.add_column("#", style="dim", width=6, justify="right")
    table.add_column("Title", min_width=35)
    table.add_column("State", width=10)
    table.add_column("Author", width=16)
    table.add_column("Assignee", width=16)
    table.add_column("💬", justify="right", width=5)
    table.add_column("Updated", width=12)

    for issue in items:
        assignees = ", ".join(a["login"] for a in issue.get("assignees", [])) or "—"
        table.add_row(
            f"#{issue['number']}",
            issue["title"],
            _state_badge(issue["state"]),
            issue["user"]["login"],
            assignees,
            str(issue.get("comments", 0)),
            (issue.get("updated_at") or "")[:10],
        )

    console.print(table)


# ── view ───────────────────────────────────────────────────────────────────

@issues.command("view")
@click.argument("repo")
@click.argument("number", type=int)
def issues_view(repo: str, number: int) -> None:
    """View a single issue by number (includes comments)."""
    c = _client()
    try:
        issue = c.get(f"/repos/{repo}/issues/{number}")
        comments = list(c.paginate(f"/repos/{repo}/issues/{number}/comments", max_pages=2))
    except GitHubAPIError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise SystemExit(1)

    labels = ", ".join(lbl["name"] for lbl in issue.get("labels", [])) or "—"
    assignees = ", ".join(a["login"] for a in issue.get("assignees", [])) or "—"

    header = Table(show_header=False, box=None, padding=(0, 2))
    header.add_column("Key", style="bold cyan", width=12)
    header.add_column("Value")
    header.add_row("Number", f"#{issue['number']}")
    header.add_row("State", str(_state_badge(issue["state"])))
    header.add_row("Author", issue["user"]["login"])
    header.add_row("Assignees", assignees)
    header.add_row("Labels", labels)
    header.add_row("Comments", str(issue.get("comments", 0)))
    header.add_row("Created", (issue.get("created_at") or "")[:10])
    header.add_row("Updated", (issue.get("updated_at") or "")[:10])
    header.add_row("URL", issue.get("html_url", ""))

    console.print(
        Panel(
            header,
            title=f"[bold cyan]#{issue['number']}: {issue['title']}[/bold cyan]",
            border_style="cyan",
        )
    )

    if issue.get("body"):
        console.print(
            Panel(Markdown(issue["body"]), title="[dim]Description[/dim]", border_style="dim")
        )

    for comment in comments:
        console.print(
            Panel(
                Markdown(comment.get("body") or "_(empty)_"),
                title=(
                    f"[dim]{comment['user']['login']} — "
                    f"{(comment.get('created_at') or '')[:10]}[/dim]"
                ),
                border_style="dim",
            )
        )


# ── create ─────────────────────────────────────────────────────────────────

@issues.command("create")
@click.argument("repo")
@click.option("--title", "-t", required=True, help="Issue title.")
@click.option("--body", "-b", default="", help="Issue body (Markdown).")
@click.option("--label", "-l", multiple=True, help="Label(s) to apply (repeatable).")
@click.option("--assignee", "-a", multiple=True, help="Assignee(s) (repeatable).")
@click.option("--milestone", "-m", default=None, type=int, help="Milestone number.")
def issues_create(
    repo: str,
    title: str,
    body: str,
    label: tuple,
    assignee: tuple,
    milestone: int | None,
) -> None:
    """Create a new issue in OWNER/REPO."""
    c = _client()
    payload: dict = {"title": title}
    if body:
        payload["body"] = body
    if label:
        payload["labels"] = list(label)
    if assignee:
        payload["assignees"] = list(assignee)
    if milestone:
        payload["milestone"] = milestone

    try:
        issue = c.post(f"/repos/{repo}/issues", json=payload)
    except GitHubAPIError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise SystemExit(1)

    console.print(
        Panel(
            f"[bold green]✓ Issue created![/bold green]\n\n"
            f"  [bold]#{issue['number']}[/bold]: {issue['title']}\n"
            f"  [dim]{issue['html_url']}[/dim]",
            title="[bold cyan]New Issue[/bold cyan]",
            border_style="green",
        )
    )


# ── close ──────────────────────────────────────────────────────────────────

@issues.command("close")
@click.argument("repo")
@click.argument("number", type=int)
@click.option("--comment", "-c", default=None, help="Optional closing comment.")
def issues_close(repo: str, number: int, comment: str | None) -> None:
    """Close issue NUMBER in OWNER/REPO."""
    c = _client()
    try:
        if comment:
            c.post(f"/repos/{repo}/issues/{number}/comments", json={"body": comment})
        issue = c.patch(f"/repos/{repo}/issues/{number}", json={"state": "closed"})
        console.print(
            f"[bold green]✓ Issue #{issue['number']} closed.[/bold green]  "
            f"[dim]{issue['html_url']}[/dim]"
        )
    except GitHubAPIError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise SystemExit(1)


# ── reopen ─────────────────────────────────────────────────────────────────

@issues.command("reopen")
@click.argument("repo")
@click.argument("number", type=int)
def issues_reopen(repo: str, number: int) -> None:
    """Reopen a closed issue."""
    c = _client()
    try:
        issue = c.patch(f"/repos/{repo}/issues/{number}", json={"state": "open"})
        console.print(f"[bold green]✓ Issue #{issue['number']} reopened.[/bold green]")
    except GitHubAPIError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise SystemExit(1)


# ── comment ────────────────────────────────────────────────────────────────

@issues.command("comment")
@click.argument("repo")
@click.argument("number", type=int)
@click.option("--body", "-b", required=True, help="Comment body (Markdown).")
def issues_comment(repo: str, number: int, body: str) -> None:
    """Add a comment to issue NUMBER."""
    c = _client()
    try:
        comment = c.post(f"/repos/{repo}/issues/{number}/comments", json={"body": body})
        console.print(
            f"[bold green]✓ Comment added.[/bold green]  [dim]{comment['html_url']}[/dim]"
        )
    except GitHubAPIError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise SystemExit(1)
