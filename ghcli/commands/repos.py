"""
ghcli repos — Repository management commands.

Commands:
  list    List repositories
  view    Show detailed repo info
  create  Create a new repository
  delete  Delete a repository (irreversible)
  clone   Clone a repository locally
  fork    Fork a repository
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import click
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table
from rich.text import Text

from ghcli.client import GitHubAPIError, GitHubClient

console = Console()


def _client() -> GitHubClient:
    c = GitHubClient()
    c.require_auth()
    return c


def _visibility_badge(private: bool) -> Text:
    if private:
        return Text("private", style="bold red")
    return Text("public", style="bold green")


@click.group()
def repos() -> None:
    """Manage GitHub repositories."""


# ── list ───────────────────────────────────────────────────────────────────


@repos.command("list")
@click.option("--user", "-u", default=None, help="GitHub username (default: authenticated user).")
@click.option("--org", "-o", default=None, help="Organization name.")
@click.option(
    "--type",
    "repo_type",
    default="all",
    type=click.Choice(["all", "owner", "member", "public", "private", "forks", "sources"]),
    show_default=True,
    help="Filter by repo type.",
)
@click.option(
    "--sort",
    default="updated",
    type=click.Choice(["created", "updated", "pushed", "full_name"]),
    show_default=True,
)
@click.option("--limit", "-n", default=30, show_default=True, help="Max repos to show.")
@click.option("--json", "output_json", is_flag=True, default=False, help="Output raw JSON.")
def repos_list(
    user: str | None, org: str | None, repo_type: str, sort: str, limit: int, output_json: bool
) -> None:
    """List repositories for the authenticated user, a specific user, or an org."""
    c = _client()
    try:
        if org:
            path = f"/orgs/{org}/repos"
            params: dict = {"type": repo_type, "sort": sort, "per_page": min(limit, 100)}
        elif user:
            path = f"/users/{user}/repos"
            params = {"type": repo_type, "sort": sort, "per_page": min(limit, 100)}
        else:
            path = "/user/repos"
            params = {"type": repo_type, "sort": sort, "per_page": min(limit, 100)}

        items = list(c.paginate(path, params=params, max_pages=5))[:limit]
    except GitHubAPIError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise SystemExit(1)

    if not items:
        console.print("[yellow]No repositories found.[/yellow]")
        return

    if output_json:
        import json as _json

        console.print(_json.dumps(items, indent=2))
        return

    table = Table(
        title=f"Repositories ({len(items)})",
        box=box.ROUNDED,
        border_style="cyan",
        show_lines=False,
        header_style="bold cyan",
    )
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("Repository", min_width=30)
    table.add_column("Visibility", width=10)
    table.add_column("⭐", justify="right", width=6)
    table.add_column("🍴", justify="right", width=6)
    table.add_column("Language", width=14)
    table.add_column("Updated", width=12)

    for i, repo in enumerate(items, 1):
        updated = (repo.get("updated_at") or "")[:10]
        lang = repo.get("language") or "—"
        table.add_row(
            str(i),
            f"[bold]{repo['full_name']}[/bold]",
            _visibility_badge(repo.get("private", False)),
            str(repo.get("stargazers_count", 0)),
            str(repo.get("forks_count", 0)),
            lang,
            updated,
        )

    console.print(table)


# ── view ───────────────────────────────────────────────────────────────────


@repos.command("view")
@click.argument("repo")
def repos_view(repo: str) -> None:
    """Show detailed info about OWNER/REPO."""
    c = _client()
    if "/" not in repo:
        me = c.get("/user")
        repo = f"{me['login']}/{repo}"
    try:
        r = c.get(f"/repos/{repo}")
    except GitHubAPIError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise SystemExit(1)

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="bold cyan", width=18)
    table.add_column("Value")

    table.add_row("Full name", r["full_name"])
    table.add_row("Description", r.get("description") or "—")
    table.add_row("Visibility", str(_visibility_badge(r.get("private", False))))
    table.add_row("Stars", str(r.get("stargazers_count", 0)))
    table.add_row("Forks", str(r.get("forks_count", 0)))
    table.add_row("Open issues", str(r.get("open_issues_count", 0)))
    table.add_row("Language", r.get("language") or "—")
    table.add_row("Default branch", r.get("default_branch", "main"))
    table.add_row("Clone URL", r.get("clone_url", ""))
    table.add_row("SSH URL", r.get("ssh_url", ""))
    table.add_row("Homepage", r.get("homepage") or "—")
    table.add_row("Created", (r.get("created_at") or "")[:10])
    table.add_row("Updated", (r.get("updated_at") or "")[:10])
    table.add_row("Topics", ", ".join(r.get("topics", [])) or "—")
    table.add_row("License", (r.get("license") or {}).get("name") or "—")
    table.add_row("Archived", "yes" if r.get("archived") else "no")
    table.add_row("Disabled", "yes" if r.get("disabled") else "no")

    console.print(
        Panel(table, title=f"[bold cyan]{r['full_name']}[/bold cyan]", border_style="cyan")
    )


# ── create ─────────────────────────────────────────────────────────────────


@repos.command("create")
@click.argument("name")
@click.option("--description", "-d", default="", help="Repository description.")
@click.option("--private/--public", default=False, show_default=True, help="Visibility.")
@click.option(
    "--auto-init/--no-auto-init", default=True, show_default=True, help="Initialize with README."
)
@click.option("--gitignore", default=None, help="Gitignore template (e.g. Python, Node).")
@click.option(
    "--license", "license_template", default=None, help="License template (e.g. mit, apache-2.0)."
)
@click.option(
    "--org", "-o", default=None, help="Create under an organization instead of your account."
)
def repos_create(
    name: str,
    description: str,
    private: bool,
    auto_init: bool,
    gitignore: str | None,
    license_template: str | None,
    org: str | None,
) -> None:
    """Create a new GitHub repository named NAME."""
    c = _client()
    payload: dict = {
        "name": name,
        "description": description,
        "private": private,
        "auto_init": auto_init,
    }
    if gitignore:
        payload["gitignore_template"] = gitignore
    if license_template:
        payload["license_template"] = license_template

    try:
        if org:
            repo = c.post(f"/orgs/{org}/repos", json=payload)
        else:
            repo = c.post("/user/repos", json=payload)
    except GitHubAPIError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise SystemExit(1)

    vis = "private" if private else "public"
    console.print(
        Panel(
            f"[bold green]✓ Repository created![/bold green]\n\n"
            f"  [bold]{repo['full_name']}[/bold]  [{vis}]\n\n"
            f"  Clone (HTTPS): [cyan]{repo.get('clone_url', '')}[/cyan]\n"
            f"  Clone (SSH):   [cyan]{repo.get('ssh_url', '')}[/cyan]\n\n"
            f"  [dim]ghcli repos clone {repo['full_name']}[/dim]",
            title="[bold cyan]New Repository[/bold cyan]",
            border_style="green",
        )
    )


# ── delete ─────────────────────────────────────────────────────────────────


@repos.command("delete")
@click.argument("repo")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
def repos_delete(repo: str, yes: bool) -> None:
    """Delete OWNER/REPO (irreversible!)."""
    c = _client()
    if "/" not in repo:
        me = c.get("/user")
        repo = f"{me['login']}/{repo}"

    if not yes:
        console.print(
            f"[bold red]⚠ This will permanently delete [white]{repo}[/white] "
            "and all its data![/bold red]"
        )
        if not Confirm.ask(f"Delete [bold]{repo}[/bold]?"):
            console.print("[dim]Aborted.[/dim]")
            return

    try:
        c.delete(f"/repos/{repo}")
        console.print(f"[green]✓ Repository [bold]{repo}[/bold] deleted.[/green]")
    except GitHubAPIError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise SystemExit(1)


# ── clone ──────────────────────────────────────────────────────────────────


@repos.command("clone")
@click.argument("repo")
@click.option("--dest", "-d", default=None, help="Destination directory (default: repo name).")
@click.option("--ssh/--https", default=False, show_default=True, help="Use SSH instead of HTTPS.")
@click.option("--depth", default=None, type=int, help="Shallow clone depth.")
def repos_clone(repo: str, dest: str | None, ssh: bool, depth: int | None) -> None:
    """Clone OWNER/REPO to your local machine."""
    c = _client()
    if "/" not in repo:
        me = c.get("/user")
        repo = f"{me['login']}/{repo}"

    try:
        r = c.get(f"/repos/{repo}")
    except GitHubAPIError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise SystemExit(1)

    clone_url = r["ssh_url"] if ssh else r["clone_url"]
    dest_dir = dest or repo.split("/")[-1]

    cmd = ["git", "clone", clone_url]
    if depth:
        cmd += ["--depth", str(depth)]
    cmd.append(dest_dir)

    console.print(f"[dim]Running: {' '.join(cmd)}[/dim]")
    try:
        subprocess.run(cmd, check=True)
        console.print(f"\n[bold green]✓ Cloned into [cyan]{dest_dir}/[/cyan][/bold green]")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]✗ git clone failed (exit {e.returncode})[/red]")
        raise SystemExit(1)
    except FileNotFoundError:
        console.print("[red]✗ git not found. Please install Git.[/red]")
        raise SystemExit(1)


# ── fork ───────────────────────────────────────────────────────────────────


@repos.command("fork")
@click.argument("repo")
@click.option("--org", "-o", default=None, help="Fork into an organization.")
def repos_fork(repo: str, org: str | None) -> None:
    """Fork OWNER/REPO into your account (or an org)."""
    c = _client()
    payload: dict = {}
    if org:
        payload["organization"] = org

    try:
        forked = c.post(f"/repos/{repo}/forks", json=payload)
        console.print(
            f"[bold green]✓ Forked to [cyan]{forked['full_name']}[/cyan][/bold green]\n"
            "  [dim]Note: fork may take a few seconds to be ready.[/dim]"
        )
    except GitHubAPIError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise SystemExit(1)
