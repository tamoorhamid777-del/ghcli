#!/usr/bin/env python3
"""
ghcli — A GitHub CLI client built with Click + Rich.

Entry point: ``ghcli`` (installed via pyproject.toml console_scripts).
"""

from __future__ import annotations

import click
from rich.console import Console

from ghcli import __version__
from ghcli.commands.auth import auth
from ghcli.commands.repos import repos
from ghcli.commands.issues import issues
from ghcli.commands.prs import prs
from ghcli.commands.commits import commits
from ghcli.commands.files import files
from ghcli.commands.skills import skills

console = Console()

BANNER = """
[bold cyan]
  ██████╗ ██╗  ██╗ ██████╗██╗     ██╗
 ██╔════╝ ██║  ██║██╔════╝██║     ██║
 ██║  ███╗███████║██║     ██║     ██║
 ██║   ██║██╔══██║██║     ██║     ██║
 ╚██████╔╝██║  ██║╚██████╗███████╗██║
  ╚═════╝ ╚═╝  ╚═╝ ╚═════╝╚══════╝╚═╝
[/bold cyan]
[dim]GitHub CLI Client — Interact with GitHub from your terminal[/dim]
"""


@click.group()
@click.version_option(version=__version__, prog_name="ghcli")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """
    \b
    ghcli — GitHub CLI Client
    Manage repos, issues, PRs, commits, and files from your terminal.

    \b
    Quick Start:
      ghcli auth setup              Set up your GitHub token
      ghcli repos list              List your repositories
      ghcli issues list OWNER/REPO  List open issues
      ghcli prs list OWNER/REPO     List open pull requests
      ghcli commits list OWNER/REPO View recent commits
      ghcli files list OWNER/REPO   Browse repository files
      ghcli skills --help           Explore skill modules (MCP, Browser, TDD…)

    \b
    Run any command with --help for full options:
      ghcli repos --help
      ghcli issues create --help
    """
    ctx.ensure_object(dict)


# ── Register all command groups ────────────────────────────────────────────
cli.add_command(auth)
cli.add_command(repos)
cli.add_command(issues)
cli.add_command(prs)
cli.add_command(commits)
cli.add_command(files)
cli.add_command(skills)


# ── Standalone commands ────────────────────────────────────────────────────

@cli.command("banner")
def show_banner() -> None:
    """Show the ghcli ASCII banner."""
    console.print(BANNER)


@cli.command("whoami")
def whoami() -> None:
    """Show the currently authenticated GitHub user."""
    from ghcli.client import GitHubClient, GitHubAPIError

    client = GitHubClient()
    try:
        client.require_auth()
        user = client.get("/user")
        console.print(
            f"[bold green]✓[/bold green] Authenticated as "
            f"[bold cyan]{user['login']}[/bold cyan] "
            f"({user.get('name') or 'no name set'})"
        )
    except GitHubAPIError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise SystemExit(1)


def main() -> None:
    """Package entry point."""
    cli(obj={})


if __name__ == "__main__":
    main()