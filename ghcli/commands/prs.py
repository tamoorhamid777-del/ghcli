"""
ghcli prs — Pull Request management commands.

Commands:
  list    List pull requests
  view    View a PR in detail (files, reviews, optional diff)
  create  Create a new pull request
  merge   Merge a pull request
  close   Close a PR without merging
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


def _state_badge(state: str, merged: bool = False) -> Text:
    if merged:
        return Text("⬡ merged", style="bold magenta")
    if state == "open":
        return Text("● open", style="bold green")
    return Text("✗ closed", style="bold red")


def _review_badge(state: str) -> Text:
    mapping: dict[str, Text] = {
        "APPROVED": Text("✓ approved", style="bold green"),
        "CHANGES_REQUESTED": Text("✗ changes requested", style="bold red"),
        "COMMENTED": Text("💬 commented", style="bold yellow"),
        "DISMISSED": Text("— dismissed", style="dim"),
        "PENDING": Text("⏳ pending", style="dim"),
    }
    return mapping.get(state, Text(state, style="dim"))


@click.group()
def prs() -> None:
    """Manage GitHub pull requests."""


# ── list ───────────────────────────────────────────────────────────────────

@prs.command("list")
@click.argument("repo")
@click.option(
    "--state",
    default="open",
    type=click.Choice(["open", "closed", "all"]),
    show_default=True,
)
@click.option("--base", "-b", default=None, help="Filter by base branch.")
@click.option("--head", "-H", default=None, help="Filter by head branch (user:branch).")
@click.option(
    "--sort",
    default="created",
    type=click.Choice(["created", "updated", "popularity", "long-running"]),
    show_default=True,
)
@click.option("--limit", "-n", default=20, show_default=True)
@click.option("--json", "output_json", is_flag=True, default=False, help="Output raw JSON.")
def prs_list(
    repo: str,
    state: str,
    base: str | None,
    head: str | None,
    sort: str,
    limit: int,
    output_json: bool,
) -> None:
    """List pull requests for OWNER/REPO."""
    c = _client()
    params: dict = {"state": state, "sort": sort, "per_page": min(limit, 100)}
    if base:
        params["base"] = base
    if head:
        params["head"] = head

    try:
        items = list(c.paginate(f"/repos/{repo}/pulls", params=params, max_pages=3))[:limit]
    except GitHubAPIError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise SystemExit(1)

    if not items:
        console.print(f"[yellow]No {state} pull requests found in {repo}.[/yellow]")
        return

    if output_json:
        import json as _json
        console.print(_json.dumps(items, indent=2))
        return

    table = Table(
        title=f"Pull Requests in {repo} ({state}) — {len(items)} shown",
        box=box.ROUNDED,
        border_style="cyan",
        header_style="bold cyan",
        show_lines=False,
    )
    table.add_column("#", style="dim", width=6, justify="right")
    table.add_column("Title", min_width=35)
    table.add_column("State", width=12)
    table.add_column("Author", width=16)
    table.add_column("Base ← Head", width=28)
    table.add_column("💬", justify="right", width=5)
    table.add_column("Updated", width=12)

    for pr in items:
        merged = bool(pr.get("merged_at"))
        branch_info = f"{pr['base']['ref']} ← {pr['head']['ref']}"
        table.add_row(
            f"#{pr['number']}",
            pr["title"],
            _state_badge(pr["state"], merged),
            pr["user"]["login"],
            branch_info,
            str(pr.get("comments", 0)),
            (pr.get("updated_at") or "")[:10],
        )

    console.print(table)


# ── view ───────────────────────────────────────────────────────────────────

@prs.command("view")
@click.argument("repo")
@click.argument("number", type=int)
@click.option("--diff", "-d", is_flag=True, help="Show the unified diff.")
def prs_view(repo: str, number: int, diff: bool) -> None:
    """View a pull request in detail (metadata, files, reviews)."""
    c = _client()
    try:
        pr = c.get(f"/repos/{repo}/pulls/{number}")
        reviews = c.get(f"/repos/{repo}/pulls/{number}/reviews") or []
        files = c.get(f"/repos/{repo}/pulls/{number}/files") or []
    except GitHubAPIError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise SystemExit(1)

    merged = bool(pr.get("merged_at"))
    labels = ", ".join(lbl["name"] for lbl in pr.get("labels", [])) or "—"
    reviewers = ", ".join(r["login"] for r in pr.get("requested_reviewers", [])) or "—"

    meta = Table(show_header=False, box=None, padding=(0, 2))
    meta.add_column("Key", style="bold cyan", width=16)
    meta.add_column("Value")
    meta.add_row("Number", f"#{pr['number']}")
    meta.add_row("State", str(_state_badge(pr["state"], merged)))
    meta.add_row("Author", pr["user"]["login"])
    meta.add_row("Base ← Head", f"{pr['base']['ref']} ← {pr['head']['ref']}")
    meta.add_row("Reviewers", reviewers)
    meta.add_row("Labels", labels)
    meta.add_row("Commits", str(pr.get("commits", 0)))
    meta.add_row("Changed files", str(pr.get("changed_files", 0)))
    meta.add_row("+additions", f"[green]+{pr.get('additions', 0)}[/green]")
    meta.add_row("-deletions", f"[red]-{pr.get('deletions', 0)}[/red]")
    meta.add_row("Mergeable", str(pr.get("mergeable", "unknown")))
    meta.add_row("Created", (pr.get("created_at") or "")[:10])
    meta.add_row("Updated", (pr.get("updated_at") or "")[:10])
    meta.add_row("URL", pr.get("html_url", ""))

    console.print(
        Panel(
            meta,
            title=f"[bold cyan]PR #{pr['number']}: {pr['title']}[/bold cyan]",
            border_style="cyan",
        )
    )

    if pr.get("body"):
        console.print(
            Panel(Markdown(pr["body"]), title="[dim]Description[/dim]", border_style="dim")
        )

    # Changed files table
    if files:
        ftable = Table(title="Changed Files", box=box.SIMPLE, header_style="bold cyan")
        ftable.add_column("Status", width=10)
        ftable.add_column("File")
        ftable.add_column("+", justify="right", width=8, style="green")
        ftable.add_column("-", justify="right", width=8, style="red")
        for f in files[:30]:
            status_color = {
                "added": "green",
                "removed": "red",
                "modified": "yellow",
                "renamed": "cyan",
            }.get(f["status"], "white")
            ftable.add_row(
                f"[{status_color}]{f['status']}[/{status_color}]",
                f["filename"],
                str(f.get("additions", 0)),
                str(f.get("deletions", 0)),
            )
        console.print(ftable)

    # Reviews table
    if reviews:
        rtable = Table(title="Reviews", box=box.SIMPLE, header_style="bold cyan")
        rtable.add_column("Reviewer", width=20)
        rtable.add_column("State")
        rtable.add_column("Submitted", width=12)
        for rev in reviews:
            rtable.add_row(
                rev["user"]["login"],
                str(_review_badge(rev["state"])),
                (rev.get("submitted_at") or "")[:10],
            )
        console.print(rtable)

    # Unified diff (uses get_diff helper — correct Accept header)
    if diff:
        try:
            diff_text = c.get_diff(f"/repos/{repo}/pulls/{number}")
            console.print(
                Panel(
                    diff_text[:8000],
                    title="[dim]Diff (truncated at 8000 chars)[/dim]",
                    border_style="dim",
                )
            )
        except Exception as exc:
            console.print(f"[yellow]Could not fetch diff: {exc}[/yellow]")


# ── create ─────────────────────────────────────────────────────────────────

@prs.command("create")
@click.argument("repo")
@click.option("--title", "-t", required=True, help="PR title.")
@click.option("--body", "-b", default="", help="PR description (Markdown).")
@click.option("--head", "-H", required=True, help="Head branch (source). Format: branch or user:branch.")
@click.option("--base", "-B", default="main", show_default=True, help="Base branch (target).")
@click.option("--draft/--no-draft", default=False, show_default=True, help="Open as draft PR.")
@click.option("--label", "-l", multiple=True, help="Label(s) to apply.")
@click.option("--assignee", "-a", multiple=True, help="Assignee(s).")
@click.option("--reviewer", "-r", multiple=True, help="Reviewer(s).")
def prs_create(
    repo: str,
    title: str,
    body: str,
    head: str,
    base: str,
    draft: bool,
    label: tuple,
    assignee: tuple,
    reviewer: tuple,
) -> None:
    """Create a new pull request in OWNER/REPO."""
    c = _client()
    payload: dict = {
        "title": title,
        "head": head,
        "base": base,
        "draft": draft,
    }
    if body:
        payload["body"] = body

    try:
        pr = c.post(f"/repos/{repo}/pulls", json=payload)

        # Apply labels / assignees / reviewers via separate calls
        if label:
            c.post(f"/repos/{repo}/issues/{pr['number']}/labels", json={"labels": list(label)})
        if assignee:
            c.patch(f"/repos/{repo}/issues/{pr['number']}", json={"assignees": list(assignee)})
        if reviewer:
            c.post(
                f"/repos/{repo}/pulls/{pr['number']}/requested_reviewers",
                json={"reviewers": list(reviewer)},
            )
    except GitHubAPIError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise SystemExit(1)

    console.print(
        Panel(
            f"[bold green]✓ Pull request created![/bold green]\n\n"
            f"  [bold]#{pr['number']}[/bold]: {pr['title']}\n"
            f"  {pr['base']['ref']} ← {pr['head']['ref']}\n"
            f"  [dim]{pr['html_url']}[/dim]",
            title="[bold cyan]New Pull Request[/bold cyan]",
            border_style="green",
        )
    )


# ── merge ──────────────────────────────────────────────────────────────────

@prs.command("merge")
@click.argument("repo")
@click.argument("number", type=int)
@click.option(
    "--method",
    default="merge",
    type=click.Choice(["merge", "squash", "rebase"]),
    show_default=True,
    help="Merge method.",
)
@click.option("--message", "-m", default=None, help="Commit message.")
def prs_merge(repo: str, number: int, method: str, message: str | None) -> None:
    """Merge pull request NUMBER."""
    c = _client()
    payload: dict = {"merge_method": method}
    if message:
        payload["commit_message"] = message

    try:
        result = c.put(f"/repos/{repo}/pulls/{number}/merge", json=payload)
        sha = (result or {}).get("sha", "")
        console.print(
            f"[bold green]✓ PR #{number} merged[/bold green] via [cyan]{method}[/cyan]  "
            f"[dim]{sha[:7]}[/dim]"
        )
    except GitHubAPIError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise SystemExit(1)


# ── close ──────────────────────────────────────────────────────────────────

@prs.command("close")
@click.argument("repo")
@click.argument("number", type=int)
def prs_close(repo: str, number: int) -> None:
    """Close (without merging) pull request NUMBER."""
    c = _client()
    try:
        pr = c.patch(f"/repos/{repo}/pulls/{number}", json={"state": "closed"})
        console.print(f"[bold green]✓ PR #{pr['number']} closed.[/bold green]")
    except GitHubAPIError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise SystemExit(1)
