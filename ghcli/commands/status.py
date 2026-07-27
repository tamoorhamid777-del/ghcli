"""Status command — show auth status, current user, and API rate limits."""
from __future__ import annotations

import json
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from ghcli.client import GitHubClient
from ghcli.auth_store import load_token

console = Console()


@click.command()
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON.")
def status(as_json: bool) -> None:
    """Show authentication status, current user, and API rate limits."""
    token = load_token()
    if not token:
        if as_json:
            click.echo(json.dumps({"authenticated": False}))
        else:
            console.print(Panel("[red]✗ Not authenticated[/red]\nRun [cyan]ghcli auth setup[/cyan] to get started.", title="ghcli status"))
        return

    client = GitHubClient(token)

    # Fetch user + rate limit in parallel-ish (sequential is fine here)
    try:
        user = client.get("/user")
    except Exception as e:
        console.print(f"[red]Failed to fetch user: {e}[/red]")
        return

    try:
        rate = client.get("/rate_limit")
    except Exception:
        rate = {}

    if as_json:
        click.echo(json.dumps({"user": user, "rate_limit": rate}, indent=2))
        return

    # User panel
    console.print(Panel(
        f"[bold green]✓ Authenticated[/bold green]\n"
        f"  Login:    [cyan]{user.get('login')}[/cyan]\n"
        f"  Name:     {user.get('name') or '(not set)'}\n"
        f"  Email:    {user.get('email') or '(private)'}\n"
        f"  Plan:     {user.get('plan', {}).get('name', 'unknown') if user.get('plan') else 'unknown'}\n"
        f"  Profile:  {user.get('html_url')}",
        title="ghcli status",
        border_style="green",
    ))

    # Rate limit table
    resources = rate.get("resources", {})
    if resources:
        table = Table(title="API Rate Limits", box=box.ROUNDED)
        table.add_column("Resource", style="cyan")
        table.add_column("Used", justify="right")
        table.add_column("Limit", justify="right")
        table.add_column("Remaining", justify="right")
        table.add_column("Resets At")
        import datetime
        for name, info in resources.items():
            used = info.get("limit", 0) - info.get("remaining", 0)
            reset_ts = info.get("reset", 0)
            reset_str = datetime.datetime.fromtimestamp(reset_ts).strftime("%H:%M:%S") if reset_ts else ""
            remaining = info.get("remaining", 0)
            color = "green" if remaining > 100 else "yellow" if remaining > 10 else "red"
            table.add_row(
                name,
                str(used),
                str(info.get("limit", 0)),
                f"[{color}]{remaining}[/{color}]",
                reset_str,
            )
        console.print(table)
