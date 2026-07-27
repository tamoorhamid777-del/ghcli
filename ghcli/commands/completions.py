"""Shell completion command — output completion scripts for bash/zsh/fish."""

from __future__ import annotations

import os
import subprocess
import sys

import click
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

console = Console()

SHELLS = ("bash", "zsh", "fish")

INSTALL_INSTRUCTIONS = {
    "bash": (
        "# Add to ~/.bashrc or ~/.bash_profile:\n"
        'eval "$(_GHCLI_COMPLETE=bash_source ghcli)"\n\n'
        "# Or save to a file:\n"
        "_GHCLI_COMPLETE=bash_source ghcli > ~/.ghcli-complete.bash\n"
        'echo "source ~/.ghcli-complete.bash" >> ~/.bashrc'
    ),
    "zsh": (
        "# Add to ~/.zshrc:\n"
        'eval "$(_GHCLI_COMPLETE=zsh_source ghcli)"\n\n'
        "# Or save to a file:\n"
        "_GHCLI_COMPLETE=zsh_source ghcli > ~/.ghcli-complete.zsh\n"
        'echo "source ~/.ghcli-complete.zsh" >> ~/.zshrc'
    ),
    "fish": (
        "# Save to fish completions directory:\n"
        "_GHCLI_COMPLETE=fish_source ghcli > ~/.config/fish/completions/ghcli.fish"
    ),
}


def _generate_completion(shell: str) -> str:
    """Generate completion script for the given shell via Click's mechanism."""
    env_var = f"_GHCLI_COMPLETE={shell}_source"
    try:
        result = subprocess.run(
            ["ghcli"],
            env={**os.environ, "_GHCLI_COMPLETE": f"{shell}_source"},
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout
    except Exception as exc:
        return f"# Error generating completion: {exc}\n"


@click.group()
def completions() -> None:
    """Generate and install shell completion scripts."""


@completions.command("generate")
@click.argument("shell", type=click.Choice(SHELLS, case_sensitive=False))
@click.option("--install", is_flag=True, help="Show installation instructions.")
def completions_generate(shell: str, install: bool) -> None:
    """Generate a completion script for SHELL (bash/zsh/fish).

    \b
    Examples:
      ghcli completions generate bash
      ghcli completions generate zsh --install
      ghcli completions generate fish
    """
    shell = shell.lower()
    script = _generate_completion(shell)

    if install:
        console.print(
            Panel(
                INSTALL_INSTRUCTIONS[shell],
                title=f"[bold cyan]Install {shell} completion[/bold cyan]",
                border_style="cyan",
            )
        )
        return

    # Print the raw script so it can be eval'd or redirected
    click.echo(script, nl=False)


@completions.command("install")
@click.argument("shell", type=click.Choice(SHELLS, case_sensitive=False), required=False)
def completions_install(shell: str | None) -> None:
    """Show installation instructions for your shell.

    Auto-detects your shell if SHELL argument is omitted.
    """
    if shell is None:
        detected = os.path.basename(os.environ.get("SHELL", "bash"))
        shell = detected if detected in SHELLS else "bash"
        console.print(f"[dim]Auto-detected shell: [cyan]{shell}[/cyan][/dim]\n")

    shell = shell.lower()
    console.print(
        Panel(
            INSTALL_INSTRUCTIONS[shell],
            title=f"[bold cyan]Install {shell} completion[/bold cyan]",
            border_style="cyan",
        )
    )
    console.print(
        "\n[dim]After adding the line above, restart your shell or run "
        f"[cyan]source ~/.{shell}rc[/cyan] (bash/zsh) to activate.[/dim]"
    )
