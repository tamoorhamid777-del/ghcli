"""
ghcli files — File operations (view, create, update, delete, list, tree).

Commands:
  list    List files/directories at a path
  view    View file contents with syntax highlighting
  write   Create or update a file (auto-detects existing SHA)
  delete  Delete a file from a repository
  tree    Show the full recursive file tree
"""

from __future__ import annotations

import base64
from pathlib import Path

import click
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.syntax import Syntax
from rich.table import Table

from ghcli.client import GitHubAPIError, GitHubClient

console = Console()

# Map file extensions → Rich Syntax lexer names
_EXT_LEXER: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "jsx",
    ".tsx": "tsx",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "scss",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".md": "markdown",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".fish": "fish",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".rb": "ruby",
    ".php": "php",
    ".sql": "sql",
    ".xml": "xml",
    ".tf": "hcl",
    ".hcl": "hcl",
    ".ini": "ini",
    ".cfg": "ini",
    ".env": "bash",
    ".r": "r",
    ".swift": "swift",
    ".kt": "kotlin",
    ".cs": "csharp",
}

_SPECIAL_NAMES: dict[str, str] = {
    "dockerfile": "dockerfile",
    "makefile": "makefile",
    "gemfile": "ruby",
    "rakefile": "ruby",
    "procfile": "bash",
}


def _client() -> GitHubClient:
    c = GitHubClient()
    c.require_auth()
    return c


def _detect_lexer(filename: str) -> str:
    """Detect the best Rich Syntax lexer for a given filename."""
    name_lower = Path(filename).name.lower()
    if name_lower in _SPECIAL_NAMES:
        return _SPECIAL_NAMES[name_lower]
    ext = Path(filename).suffix.lower()
    return _EXT_LEXER.get(ext, "text")


@click.group()
def files() -> None:
    """View and manage files in a GitHub repository."""


# ── list ───────────────────────────────────────────────────────────────────

@files.command("list")
@click.argument("repo")
@click.option("--path", "-p", default="", help="Directory path within the repo (default: root).")
@click.option("--branch", "-b", default=None, help="Branch/tag/SHA (default: repo default).")
@click.option("--json", "output_json", is_flag=True, default=False, help="Output raw JSON.")
def files_list(repo: str, path: str, branch: str | None, output_json: bool) -> None:
    """List files and directories at PATH in OWNER/REPO."""
    c = _client()
    params: dict = {}
    if branch:
        params["ref"] = branch

    try:
        items = c.get(f"/repos/{repo}/contents/{path}", params=params)
    except GitHubAPIError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise SystemExit(1)

    if isinstance(items, dict):
        # Single file returned — redirect user
        console.print(
            f"[yellow]Path points to a file, not a directory. "
            f"Use [bold]ghcli files view {repo} {path}[/bold][/yellow]"
        )
        return

    dirs = sorted([i for i in items if i["type"] == "dir"], key=lambda x: x["name"])
    file_list = sorted([i for i in items if i["type"] == "file"], key=lambda x: x["name"])

    if output_json:
        import json as _json
        console.print(_json.dumps(items, indent=2))
        return

    table = Table(
        title=f"{repo}/{path or '(root)'}",
        box=box.ROUNDED,
        border_style="cyan",
        header_style="bold cyan",
        show_lines=False,
    )
    table.add_column("Type", width=6)
    table.add_column("Name", min_width=30)
    table.add_column("Size", justify="right", width=10)
    table.add_column("SHA", style="dim", width=10)

    for item in dirs:
        table.add_row(
            "[bold blue]dir[/bold blue]",
            f"[bold blue]{item['name']}/[/bold blue]",
            "—",
            item["sha"][:7],
        )

    for item in file_list:
        size = item.get("size", 0) or 0
        size_str = f"{size:,} B" if size < 1024 else f"{size / 1024:.1f} KB"
        table.add_row("file", item["name"], size_str, item["sha"][:7])

    console.print(table)
    console.print(f"[dim]{len(dirs)} directories, {len(file_list)} files[/dim]")


# ── view ───────────────────────────────────────────────────────────────────

@files.command("view")
@click.argument("repo")
@click.argument("path")
@click.option("--branch", "-b", default=None, help="Branch/tag/SHA.")
@click.option("--raw", "-r", is_flag=True, help="Print raw content without syntax highlighting.")
@click.option("--save", "-s", default=None, help="Save content to a local file.")
def files_view(
    repo: str,
    path: str,
    branch: str | None,
    raw: bool,
    save: str | None,
) -> None:
    """View the contents of a file in OWNER/REPO with syntax highlighting."""
    c = _client()
    params: dict = {}
    if branch:
        params["ref"] = branch

    try:
        item = c.get(f"/repos/{repo}/contents/{path}", params=params)
    except GitHubAPIError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise SystemExit(1)

    if isinstance(item, list):
        console.print(
            f"[yellow]Path is a directory. "
            f"Use [bold]ghcli files list {repo} --path {path}[/bold][/yellow]"
        )
        return

    if item.get("encoding") != "base64":
        console.print(f"[yellow]Unsupported encoding: {item.get('encoding')}[/yellow]")
        return

    content = base64.b64decode(item["content"]).decode("utf-8", errors="replace")

    if save:
        Path(save).write_text(content, encoding="utf-8")
        console.print(f"[bold green]✓ Saved to [cyan]{save}[/cyan][/bold green]")
        return

    if raw:
        console.print(content)
        return

    lexer = _detect_lexer(path)
    syntax = Syntax(content, lexer, theme="monokai", line_numbers=True, word_wrap=False)
    console.print(
        Panel(
            syntax,
            title=(
                f"[bold cyan]{repo}/{path}[/bold cyan]  "
                f"[dim]({item.get('size', 0):,} bytes | sha: {item['sha'][:7]})[/dim]"
            ),
            border_style="cyan",
        )
    )


# ── write (create / update) ────────────────────────────────────────────────

@files.command("write")
@click.argument("repo")
@click.argument("path")
@click.option("--message", "-m", required=True, help="Commit message.")
@click.option("--content", "-c", default=None, help="File content as a string.")
@click.option(
    "--file", "-f", "local_file",
    default=None,
    type=click.Path(exists=True),
    help="Read content from a local file.",
)
@click.option("--branch", "-b", default=None, help="Branch to commit to (default: repo default).")
def files_write(
    repo: str,
    path: str,
    message: str,
    content: str | None,
    local_file: str | None,
    branch: str | None,
) -> None:
    """
    Create or update a file in OWNER/REPO.

    Provide content via --content or --file. If the file already exists,
    its current SHA is fetched automatically for the update.
    """
    c = _client()

    if not content and not local_file:
        console.print("[red]✗ Provide --content or --file.[/red]")
        raise SystemExit(1)

    raw_bytes: bytes
    if local_file:
        raw_bytes = Path(local_file).read_bytes()
    else:
        raw_bytes = (content or "").encode("utf-8")

    encoded = base64.b64encode(raw_bytes).decode("ascii")

    # Check if file already exists (need its SHA for updates)
    params: dict = {}
    if branch:
        params["ref"] = branch

    existing_sha: str | None = None
    try:
        existing = c.get(f"/repos/{repo}/contents/{path}", params=params)
        if isinstance(existing, dict):
            existing_sha = existing.get("sha")
    except GitHubAPIError as e:
        if e.status_code != 404:
            console.print(f"[red]✗ {e}[/red]")
            raise SystemExit(1)
        # 404 means file doesn't exist yet — that's fine for create

    payload: dict = {"message": message, "content": encoded}
    if existing_sha:
        payload["sha"] = existing_sha
    if branch:
        payload["branch"] = branch

    action = "Updated" if existing_sha else "Created"

    try:
        result = c.put(f"/repos/{repo}/contents/{path}", json=payload)
        commit_sha = result["commit"]["sha"][:7] if result else "—"
        console.print(
            Panel(
                f"[bold green]✓ {action} file![/bold green]\n\n"
                f"  [bold]{repo}/{path}[/bold]\n"
                f"  Commit: [yellow]{commit_sha}[/yellow]\n"
                f"  Message: {message}",
                title=f"[bold cyan]File {action}[/bold cyan]",
                border_style="green",
            )
        )
    except GitHubAPIError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise SystemExit(1)


# ── delete ─────────────────────────────────────────────────────────────────

@files.command("delete")
@click.argument("repo")
@click.argument("path")
@click.option("--message", "-m", required=True, help="Commit message.")
@click.option("--branch", "-b", default=None, help="Branch to commit to.")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation.")
def files_delete(
    repo: str,
    path: str,
    message: str,
    branch: str | None,
    yes: bool,
) -> None:
    """Delete a file from OWNER/REPO."""
    c = _client()

    if not yes and not Confirm.ask(f"[bold red]Delete [white]{repo}/{path}[/white]?[/bold red]"):
        console.print("[dim]Aborted.[/dim]")
        return

    params: dict = {}
    if branch:
        params["ref"] = branch

    # Fetch the file's current SHA (required by GitHub API)
    try:
        existing = c.get(f"/repos/{repo}/contents/{path}", params=params)
        sha = existing["sha"]
    except GitHubAPIError as e:
        console.print(f"[red]✗ Could not fetch file SHA: {e}[/red]")
        raise SystemExit(1)

    payload: dict = {"message": message, "sha": sha}
    if branch:
        payload["branch"] = branch

    # Use delete_with_body — the GitHub Contents API requires a JSON body on DELETE
    try:
        c.delete_with_body(f"/repos/{repo}/contents/{path}", json=payload)
        console.print(f"[bold green]✓ Deleted [cyan]{repo}/{path}[/cyan][/bold green]")
    except GitHubAPIError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise SystemExit(1)


# ── tree ───────────────────────────────────────────────────────────────────

@files.command("tree")
@click.argument("repo")
@click.option("--branch", "-b", default=None, help="Branch/tag/SHA.")
@click.option(
    "--recursive/--no-recursive",
    default=True,
    show_default=True,
    help="Fetch full recursive tree.",
)
@click.option("--limit", "-n", default=200, show_default=True, help="Max entries to display.")
def files_tree(repo: str, branch: str | None, recursive: bool, limit: int) -> None:
    """Show the full file tree of OWNER/REPO."""
    c = _client()

    try:
        repo_info = c.get(f"/repos/{repo}")
        ref = branch or repo_info["default_branch"]
        branch_info = c.get(f"/repos/{repo}/branches/{ref}")
        tree_sha = branch_info["commit"]["commit"]["tree"]["sha"]
        params: dict = {}
        if recursive:
            params["recursive"] = "1"
        tree = c.get(f"/repos/{repo}/git/trees/{tree_sha}", params=params)
    except GitHubAPIError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise SystemExit(1)

    items = (tree.get("tree") or [])[:limit]
    truncated = tree.get("truncated", False)

    table = Table(
        title=f"Tree: {repo} @ {ref}",
        box=box.ROUNDED,
        border_style="cyan",
        header_style="bold cyan",
        show_lines=False,
    )
    table.add_column("Type", width=6)
    table.add_column("Path", min_width=40)
    table.add_column("Size", justify="right", width=10)

    for item in items:
        if item["type"] == "tree":
            table.add_row(
                "[bold blue]📁[/bold blue]",
                f"[bold blue]{item['path']}/[/bold blue]",
                "—",
            )
        else:
            size = item.get("size") or 0
            size_str = f"{size:,} B" if size < 1024 else f"{size / 1024:.1f} KB"
            table.add_row("📄", item["path"], size_str)

    console.print(table)
    if truncated:
        console.print(
            "[yellow]⚠ Tree was truncated by GitHub (>100k entries). "
            "Use --no-recursive for large repos.[/yellow]"
        )
    console.print(f"[dim]{len(items)} entries shown[/dim]")
