"""ghcli — GitHub CLI entry point. Registers all command groups."""

from __future__ import annotations

import click
from rich.console import Console

from ghcli import __version__

# Core commands
from ghcli.commands.auth import auth

# v1.2.0 commands
from ghcli.commands.comments import comments
from ghcli.commands.commits import commits

# v1.2.1 commands
from ghcli.commands.completions import completions
from ghcli.commands.files import files
from ghcli.commands.gist import gist
from ghcli.commands.issues import issues
from ghcli.commands.notifications import notifications
from ghcli.commands.org import org
from ghcli.commands.prs import prs
from ghcli.commands.release import release
from ghcli.commands.repos import repos

# v1.1.0 commands
from ghcli.commands.search import search
from ghcli.commands.skills import skills
from ghcli.commands.star import star
from ghcli.commands.status import status

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="ghcli")
def cli() -> None:
    """ghcli — A powerful GitHub CLI tool.

    Authenticate first:  ghcli auth setup
    Then explore:        ghcli repos list
    """


# Core commands
cli.add_command(auth)
cli.add_command(repos)
cli.add_command(issues)
cli.add_command(prs)
cli.add_command(commits)
cli.add_command(files)
cli.add_command(skills)

# v1.1.0 commands
cli.add_command(search)
cli.add_command(gist)
cli.add_command(release)
cli.add_command(org)
cli.add_command(notifications)
cli.add_command(star)
cli.add_command(status)

# v1.2.0 commands
cli.add_command(comments)

# v1.2.1 commands
cli.add_command(completions)


@cli.command("version")
def version_cmd() -> None:
    """Show ghcli version."""
    console.print(f"[bold cyan]ghcli[/bold cyan] version [bold]{__version__}[/bold]")


def main() -> None:
    """Package entry point."""
    cli()


if __name__ == "__main__":
    main()
