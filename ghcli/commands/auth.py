"""
ghcli auth — GitHub token management commands.

Commands:
  setup   Configure a GitHub Personal Access Token
  status  Show current authentication status
  logout  Remove the stored token
"""

from __future__ import annotations

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from ghcli.auth_store import delete_token, load_token, save_token, token_is_set
from ghcli.client import GitHubAPIError, GitHubClient

console = Console()


@click.group()
def auth() -> None:
    """Manage GitHub authentication (personal access token)."""


# ── setup ──────────────────────────────────────────────────────────────────

@auth.command("setup")
@click.option(
    "--token", "-t",
    default=None,
    help="GitHub PAT (omit to be prompted securely).",
)
def auth_setup(token: str | None) -> None:
    """
    Configure your GitHub Personal Access Token.

    \b
    How to create a token:
      1. Go to https://github.com/settings/tokens
      2. Click 'Generate new token (classic)'
      3. Select scopes: repo, read:user, read:org
      4. Copy the token and run: ghcli auth setup
    """
    if not token:
        console.print(
            Panel(
                "[bold]GitHub Personal Access Token Setup[/bold]\n\n"
                "Create a token at: [link=https://github.com/settings/tokens]"
                "https://github.com/settings/tokens[/link]\n\n"
                "Recommended scopes: [cyan]repo[/cyan], [cyan]read:user[/cyan], "
                "[cyan]read:org[/cyan], [cyan]workflow[/cyan]",
                title="[bold cyan]ghcli auth[/bold cyan]",
                border_style="cyan",
            )
        )
        token = Prompt.ask("[bold]Paste your GitHub token[/bold]", password=True)

    token = (token or "").strip()
    if not token:
        console.print("[red]✗ Token cannot be empty.[/red]")
        raise SystemExit(1)

    # Validate the token against the API before saving
    console.print("[dim]Validating token with GitHub API…[/dim]")
    client = GitHubClient(token=token)
    try:
        user = client.get("/user")
    except GitHubAPIError as e:
        console.print(f"[red]✗ Token validation failed: {e}[/red]")
        raise SystemExit(1)

    backend = save_token(token)
    console.print(
        f"\n[bold green]✓ Authenticated as [cyan]{user['login']}[/cyan] "
        f"({user.get('name') or 'no name set'})[/bold green]"
    )
    console.print(f"  [dim]Email:        {user.get('email') or 'hidden'}[/dim]")
    console.print(f"  [dim]Public repos: {user.get('public_repos', 0)}[/dim]")
    console.print(f"  [dim]Token stored: {backend}[/dim]")


# ── status ─────────────────────────────────────────────────────────────────

@auth.command("status")
def auth_status() -> None:
    """Show current authentication status."""
    token = load_token()
    if not token:
        console.print(
            "[yellow]⚠ Not authenticated.[/yellow]  "
            "Run [bold]ghcli auth setup[/bold] to configure."
        )
        return

    console.print("[dim]Checking token…[/dim]")
    client = GitHubClient()
    try:
        user = client.get("/user")
    except GitHubAPIError as e:
        console.print(f"[red]✗ Token is invalid or expired: {e}[/red]")
        return

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="bold cyan")
    table.add_column("Value")
    table.add_row("Status", "[bold green]✓ Authenticated[/bold green]")
    table.add_row("Username", user["login"])
    table.add_row("Name", user.get("name") or "—")
    table.add_row("Email", user.get("email") or "hidden")
    table.add_row("Public repos", str(user.get("public_repos", 0)))
    table.add_row("Private repos", str(user.get("total_private_repos", 0)))
    table.add_row("Followers", str(user.get("followers", 0)))
    table.add_row("Following", str(user.get("following", 0)))
    table.add_row("Account URL", user.get("html_url", ""))
    console.print(
        Panel(table, title="[bold cyan]Auth Status[/bold cyan]", border_style="cyan")
    )


# ── logout ─────────────────────────────────────────────────────────────────

@auth.command("logout")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
def auth_logout(yes: bool) -> None:
    """Remove the stored GitHub token."""
    if not token_is_set():
        console.print("[yellow]No token stored.[/yellow]")
        return
    if not yes and not Confirm.ask("[bold red]Remove stored GitHub token?[/bold red]"):
        console.print("[dim]Aborted.[/dim]")
        return
    delete_token()
    console.print("[green]✓ Token removed.[/green]")
