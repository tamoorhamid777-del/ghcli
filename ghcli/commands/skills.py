"""
ghcli skills — CLI command group exposing all 7 skill modules.

Commands
--------
  ghcli skills list                          — list all available skills
  ghcli skills mcp  ...                      — MCP connector commands
  ghcli skills browser ...                   — Agent browser commands
  ghcli skills debug ...                     — Systematic debugger commands
  ghcli skills research ...                  — Deep research commands
  ghcli skills prd ...                       — Brainstorm & PRD commands
  ghcli skills tdd ...                       — TDD runner commands
  ghcli skills dispatch ...                  — Parallel dispatcher commands
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Optional

import click
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

# ── Top-level group ───────────────────────────────────────────────────────────


@click.group()
def skills():
    """
    \b
    ghcli skills — Pluggable capability modules.

    \b
    Available skills:
      mcp       Model Context Protocol client/server scaffolding
      browser   Autonomous web navigation (Playwright / Selenium)
      debug     Systematic multi-phase root cause analysis
      research  Deep multi-source research & data extraction
      prd       Interactive brainstorming & PRD generation
      tdd       Test-Driven Development red-green-refactor loop
      dispatch  Parallel agent task dispatcher (asyncio / multiprocessing)
    """


@skills.command("list")
def skills_list():
    """List all available skill modules."""
    table = Table(
        title="ghcli Skill Modules",
        box=box.ROUNDED,
        border_style="cyan",
        header_style="bold cyan",
    )
    table.add_column("Skill", style="bold", width=12)
    table.add_column("Description", min_width=50)
    table.add_column("Key commands", min_width=40)
    rows = [
        (
            "mcp",
            "Model Context Protocol client/server scaffolding",
            "register, list, call, tools, remove",
        ),
        (
            "browser",
            "Autonomous web navigation (Playwright / Selenium)",
            "navigate, screenshot, fill, extract",
        ),
        (
            "debug",
            "Systematic multi-phase root cause analysis",
            "new, reproduce, isolate, hypothesize, verify, fix, report",
        ),
        ("research", "Deep multi-source research & data extraction", "query, extract, export"),
        (
            "prd",
            "Interactive brainstorming & PRD generation",
            "new, interview, feature, generate, export, approve",
        ),
        (
            "tdd",
            "Test-Driven Development red-green-refactor loop",
            "new, cycle, red, green, refactor, commit, report",
        ),
        ("dispatch", "Parallel agent task dispatcher", "run, status, report, list"),
    ]
    for skill, desc, cmds in rows:
        table.add_row(skill, desc, f"[dim]{cmds}[/dim]")
    console.print(table)
    console.print("\n[dim]Run [bold]ghcli skills <skill> --help[/bold] for detailed usage.[/dim]")


# ═══════════════════════════════════════════════════════════════════════════════
# MCP CONNECTOR
# ═══════════════════════════════════════════════════════════════════════════════


@skills.group("mcp")
def mcp():
    """Model Context Protocol (MCP) client/server scaffolding."""


@mcp.command("register")
@click.option("--name", "-n", required=True, help="Server name (unique identifier).")
@click.option(
    "--transport",
    "-t",
    default="stdio",
    type=click.Choice(["stdio", "http", "sse"]),
    show_default=True,
)
@click.option(
    "--command",
    "-c",
    default=None,
    help="Command to launch stdio server (e.g. 'npx -y @mcp/server-filesystem /tmp').",
)
@click.option("--url", "-u", default="", help="HTTP/SSE endpoint URL.")
@click.option("--description", "-d", default="", help="Human-readable description.")
@click.option("--timeout", default=30, show_default=True, help="Request timeout in seconds.")
def mcp_register(name, transport, command, url, description, timeout):
    """Register a new MCP server."""
    from ghcli.skills.mcp_connector import MCPConnector

    conn = MCPConnector()
    cmd_list = command.split() if command else []
    cfg = conn.register(
        name=name,
        transport=transport,
        command=cmd_list,
        url=url,
        description=description,
        timeout=timeout,
    )
    console.print(f"[bold green]✓ MCP server '{name}' registered.[/bold green]")
    console.print(f"  Transport: [cyan]{cfg.transport}[/cyan]")
    if cfg.command:
        console.print(f"  Command:   [dim]{' '.join(cfg.command)}[/dim]")
    if cfg.url:
        console.print(f"  URL:       [dim]{cfg.url}[/dim]")


@mcp.command("list")
def mcp_list():
    """List all registered MCP servers."""
    from ghcli.skills.mcp_connector import MCPConnector

    MCPConnector().print_servers()


@mcp.command("tools")
@click.argument("server")
def mcp_tools(server):
    """List tools available on SERVER."""
    from ghcli.skills.mcp_connector import MCPConnector

    MCPConnector().print_tools(server)


@mcp.command("call")
@click.argument("server")
@click.argument("tool")
@click.option("--arg", "-a", multiple=True, help="Tool argument as key=value (repeatable).")
def mcp_call(server, tool, arg):
    """Call TOOL on SERVER with optional arguments."""
    from ghcli.skills.mcp_connector import MCPConnector

    args = {}
    for a in arg:
        if "=" in a:
            k, v = a.split("=", 1)
            args[k] = v
        else:
            console.print(f"[yellow]⚠ Ignoring malformed arg: {a!r} (expected key=value)[/yellow]")
    conn = MCPConnector()
    result = conn.call_tool(server, tool, args)
    conn.print_result(result)


@mcp.command("remove")
@click.argument("server")
def mcp_remove(server):
    """Unregister SERVER."""
    from ghcli.skills.mcp_connector import MCPConnector

    removed = MCPConnector().remove(server)
    if removed:
        console.print(f"[green]✓ Server '{server}' removed.[/green]")
    else:
        console.print(f"[yellow]Server '{server}' not found.[/yellow]")


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT BROWSER
# ═══════════════════════════════════════════════════════════════════════════════


@skills.group("browser")
def browser():
    """Autonomous web navigation (Playwright / Selenium)."""


@browser.command("navigate")
@click.argument("url")
@click.option(
    "--backend",
    default=None,
    type=click.Choice(["playwright", "selenium"]),
    help="Browser backend (auto-detected if omitted).",
)
@click.option("--no-headless", is_flag=True, help="Show browser window.")
def browser_navigate(url, backend, no_headless):
    """Navigate to URL and print the page title."""
    from ghcli.skills.agent_browser import AgentBrowser

    ab = AgentBrowser(backend=backend, headless=not no_headless)
    with ab.session() as page:
        page.navigate(url)
        page.wait_for_navigation()
        title = page.title()
        current = page.current_url()
    console.print(f"[bold green]✓ Navigated to:[/bold green] {current}")
    console.print(f"  Title: [cyan]{title}[/cyan]")


@browser.command("screenshot")
@click.argument("url")
@click.option("--out", "-o", default=None, help="Output PNG path (default: /tmp/ghcli_<ts>.png).")
@click.option("--backend", default=None, type=click.Choice(["playwright", "selenium"]))
def browser_screenshot(url, out, backend):
    """Take a screenshot of URL."""
    from ghcli.skills.agent_browser import AgentBrowser

    ab = AgentBrowser(backend=backend)
    path = ab.navigate_and_screenshot(url, out=out)
    console.print(f"[green]✓ Screenshot:[/green] {path}")


@browser.command("extract")
@click.argument("url")
@click.option("--selector", "-s", required=True, help="CSS selector to extract text from.")
@click.option("--backend", default=None, type=click.Choice(["playwright", "selenium"]))
def browser_extract(url, selector, backend):
    """Extract text from elements matching SELECTOR on URL."""
    from ghcli.skills.agent_browser import AgentBrowser

    ab = AgentBrowser(backend=backend)
    texts = ab.extract(url, selector)
    if not texts:
        console.print(f"[yellow]No elements matched selector: {selector!r}[/yellow]")
        return
    for i, text in enumerate(texts, 1):
        console.print(f"[dim]{i}.[/dim] {text}")


@browser.command("fill")
@click.argument("url")
@click.option(
    "--field",
    "-f",
    multiple=True,
    help="Field as selector=value (repeatable). E.g. --field '#email=alice@example.com'",
)
@click.option("--submit", "-s", required=True, help="CSS selector of the submit button.")
@click.option("--wait", "-w", default=None, help="CSS selector to wait for after submit.")
@click.option("--backend", default=None, type=click.Choice(["playwright", "selenium"]))
def browser_fill(url, field, submit, wait, backend):
    """Fill a form on URL and click the submit button."""
    from ghcli.skills.agent_browser import AgentBrowser

    fields = {}
    for f in field:
        if "=" in f:
            sel, val = f.split("=", 1)
            fields[sel] = val
    ab = AgentBrowser(backend=backend)
    html = ab.fill_and_submit(url, fields, submit, wait_after=wait)
    console.print(f"[green]✓ Form submitted.[/green] Page HTML length: {len(html)} chars")


# ═══════════════════════════════════════════════════════════════════════════════
# SYSTEMATIC DEBUGGER
# ═══════════════════════════════════════════════════════════════════════════════


@skills.group("debug")
def debug():
    """Systematic multi-phase root cause analysis."""


@debug.command("new")
@click.argument("title")
def debug_new(title):
    """Start a new debug session with TITLE."""
    from ghcli.skills.debugger import Debugger

    Debugger().new_session(title)


@debug.command("list")
def debug_list():
    """List all debug sessions."""
    from ghcli.skills.debugger import Debugger

    Debugger().list_sessions()


@debug.command("show")
@click.argument("session_id")
def debug_show(session_id):
    """Show details of a debug session."""
    from ghcli.skills.debugger import Debugger

    dbg = Debugger()
    sess = dbg.load(session_id)
    dbg.print_session(sess)


@debug.command("reproduce")
@click.argument("session_id")
@click.argument("description")
@click.option("--evidence", "-e", default="", help="Supporting evidence.")
def debug_reproduce(session_id, description, evidence):
    """Record reproduction steps for SESSION_ID."""
    from ghcli.skills.debugger import Debugger

    sess = Debugger().load(session_id)
    sess.reproduce(description, evidence=evidence)


@debug.command("isolate")
@click.argument("session_id")
@click.argument("description")
@click.option("--evidence", "-e", default="")
def debug_isolate(session_id, description, evidence):
    """Record isolation findings for SESSION_ID."""
    from ghcli.skills.debugger import Debugger

    sess = Debugger().load(session_id)
    sess.isolate(description, evidence=evidence)


@debug.command("hypothesize")
@click.argument("session_id")
@click.argument("description")
@click.option(
    "--confidence", "-c", default=0.5, type=float, show_default=True, help="Confidence 0.0–1.0."
)
def debug_hypothesize(session_id, description, confidence):
    """Add a hypothesis to SESSION_ID."""
    from ghcli.skills.debugger import Debugger

    sess = Debugger().load(session_id)
    hyp_id = sess.hypothesize(description, confidence=confidence)
    console.print(f"[dim]Hypothesis ID: {hyp_id}[/dim]")


@debug.command("verify")
@click.argument("session_id")
@click.argument("hyp_id")
@click.option("--passed/--failed", required=True, help="Did the hypothesis hold?")
@click.option("--evidence", "-e", default="")
def debug_verify(session_id, hyp_id, passed, evidence):
    """Record verification result for HYP_ID in SESSION_ID."""
    from ghcli.skills.debugger import Debugger

    sess = Debugger().load(session_id)
    sess.verify(hyp_id, passed=passed, evidence=evidence)


@debug.command("fix")
@click.argument("session_id")
@click.argument("description")
@click.option("--test", "-t", default="", help="Regression test name or file.")
def debug_fix(session_id, description, test):
    """Record the fix applied in SESSION_ID."""
    from ghcli.skills.debugger import Debugger

    sess = Debugger().load(session_id)
    sess.fix(description, test=test)


@debug.command("report")
@click.argument("session_id")
def debug_report(session_id):
    """Generate and display the final debug report."""
    from ghcli.skills.debugger import Debugger

    dbg = Debugger()
    sess = dbg.load(session_id)
    report = sess.close()
    dbg.print_report(report)


# ═══════════════════════════════════════════════════════════════════════════════
# DEEP RESEARCH
# ═══════════════════════════════════════════════════════════════════════════════


@skills.group("research")
def research():
    """Deep multi-source research & data extraction."""


@research.command("query")
@click.argument("query")
@click.option(
    "--source",
    "-s",
    multiple=True,
    help="Sources to query (repeatable). Choices: web, github, arxiv, wikipedia, url. "
    "Default: web, github, wikipedia.",
)
@click.option("--limit", "-n", default=5, show_default=True, help="Results per source.")
@click.option("--export", "-o", default=None, help="Export results to JSON file.")
def research_query(query, source, limit, export):
    """Run a deep research query across multiple sources."""
    from ghcli.skills.deep_research import DeepResearcher

    sources = list(source) if source else ["web", "github", "wikipedia"]
    researcher = DeepResearcher()
    report = researcher.quick_search(query, sources=sources, limit=limit)
    researcher.print_report(report)
    if export:
        researcher.export_json(report, export)


@research.command("extract")
@click.argument("url")
@click.option("--selector", "-s", default="", help="CSS selector (for browser-based extraction).")
def research_extract(url, selector):
    """Fetch and extract text content from URL."""
    from ghcli.skills.deep_research import DeepResearcher, URLExtractAdapter

    adapter = URLExtractAdapter()
    items = adapter.search(url, limit=1)
    for item in items:
        console.print(
            Panel(
                item.get("snippet", ""), title=f"[bold cyan]{url}[/bold cyan]", border_style="cyan"
            )
        )


# ═══════════════════════════════════════════════════════════════════════════════
# BRAINSTORM & PRD
# ═══════════════════════════════════════════════════════════════════════════════


@skills.group("prd")
def prd():
    """Interactive brainstorming & Product Requirements Document generation."""


@prd.command("new")
@click.argument("product_name")
def prd_new(product_name):
    """Start a new PRD session for PRODUCT_NAME."""
    from ghcli.skills.brainstorm_prd import BrainstormPRD

    BrainstormPRD().new_session(product_name)


@prd.command("list")
def prd_list():
    """List all PRD sessions."""
    from ghcli.skills.brainstorm_prd import BrainstormPRD

    BrainstormPRD().list_sessions()


@prd.command("interview")
@click.argument("session_id")
def prd_interview(session_id):
    """Run the interactive interview for SESSION_ID."""
    from ghcli.skills.brainstorm_prd import BrainstormPRD

    sess = BrainstormPRD().load(session_id)
    sess.run_interview()


@prd.command("answer")
@click.argument("session_id")
@click.argument("key")
@click.argument("answer")
def prd_answer(session_id, key, answer):
    """Record an answer for interview question KEY in SESSION_ID."""
    from ghcli.skills.brainstorm_prd import BrainstormPRD

    sess = BrainstormPRD().load(session_id)
    sess.answer(key, answer)
    console.print(f"[green]✓ Answer recorded for '{key}'.[/green]")


@prd.command("feature")
@click.argument("session_id")
@click.argument("name")
@click.option("--description", "-d", default="")
@click.option(
    "--moscow",
    default="should",
    type=click.Choice(["must", "should", "could", "wont"]),
    show_default=True,
)
@click.option("--effort", default=3, type=int, show_default=True, help="Effort 1–10.")
@click.option("--impact", default=5, type=int, show_default=True, help="Impact 1–10.")
@click.option("--confidence", default=0.7, type=float, show_default=True)
@click.option("--reach", default=100, type=int, show_default=True)
def prd_feature(session_id, name, description, moscow, effort, impact, confidence, reach):
    """Add a feature to SESSION_ID."""
    from ghcli.skills.brainstorm_prd import BrainstormPRD

    sess = BrainstormPRD().load(session_id)
    feat = sess.add_feature(
        name=name,
        description=description,
        moscow=moscow,
        effort=effort,
        impact=impact,
        confidence=confidence,
        reach=reach,
    )
    console.print(f"[green]✓ Feature added:[/green] {name}  RICE={feat.rice_score:.1f}")


@prd.command("features")
@click.argument("session_id")
def prd_features(session_id):
    """List features for SESSION_ID ranked by RICE score."""
    from ghcli.skills.brainstorm_prd import BrainstormPRD

    prd_obj = BrainstormPRD()
    sess = prd_obj.load(session_id)
    prd_obj.print_features(sess)


@prd.command("generate")
@click.argument("session_id")
def prd_generate(session_id):
    """Generate the PRD document for SESSION_ID."""
    from ghcli.skills.brainstorm_prd import BrainstormPRD

    prd_obj = BrainstormPRD()
    sess = prd_obj.load(session_id)
    doc = sess.generate_prd()
    prd_obj.print_prd(doc)


@prd.command("export")
@click.argument("session_id")
@click.option("--out", "-o", default="prd.md", show_default=True, help="Output Markdown file.")
def prd_export(session_id, out):
    """Export the PRD for SESSION_ID to a Markdown file."""
    from ghcli.skills.brainstorm_prd import BrainstormPRD

    prd_obj = BrainstormPRD()
    sess = prd_obj.load(session_id)
    doc = sess.generate_prd()
    prd_obj.export_markdown(doc, out)


@prd.command("approve")
@click.argument("session_id")
def prd_approve(session_id):
    """Mark the PRD for SESSION_ID as approved."""
    from ghcli.skills.brainstorm_prd import BrainstormPRD

    BrainstormPRD().load(session_id).approve()


# ═══════════════════════════════════════════════════════════════════════════════
# TDD RUNNER
# ═══════════════════════════════════════════════════════════════════════════════


@skills.group("tdd")
def tdd():
    """Test-Driven Development red-green-refactor loop enforcer."""


@tdd.command("new")
@click.argument("title")
@click.option("--test-cmd", "-t", default="pytest", show_default=True, help="Test runner command.")
@click.option(
    "--src-dir",
    "-d",
    default=".",
    show_default=True,
    help="Source directory (cwd for test runner).",
)
def tdd_new(title, test_cmd, src_dir):
    """Start a new TDD session with TITLE."""
    from ghcli.skills.tdd import TDDRunner

    TDDRunner(test_command=test_cmd, src_dir=src_dir).new_session(title)


@tdd.command("list")
def tdd_list():
    """List all TDD sessions."""
    from ghcli.skills.tdd import TDDRunner

    TDDRunner().list_sessions()


@tdd.command("cycle")
@click.argument("session_id")
@click.argument("test_name")
def tdd_cycle(session_id, test_name):
    """Start a new TDD cycle for TEST_NAME in SESSION_ID."""
    from ghcli.skills.tdd import TDDRunner

    sess = TDDRunner().load(session_id)
    cycle = sess.start_cycle(test_name)
    console.print(f"[dim]Cycle ID: {cycle.cycle_id}[/dim]")


@tdd.command("red")
@click.argument("session_id")
@click.argument("cycle_id")
@click.option("--args", default="", help="Extra args to pass to the test runner.")
def tdd_red(session_id, cycle_id, args):
    """Run tests in RED phase (expect failure)."""
    from ghcli.skills.tdd import TDDRunner

    sess = TDDRunner().load(session_id)
    sess.run_phase(cycle_id, "red", extra_args=args)


@tdd.command("green")
@click.argument("session_id")
@click.argument("cycle_id")
@click.option("--args", default="")
def tdd_green(session_id, cycle_id, args):
    """Run tests in GREEN phase (expect pass)."""
    from ghcli.skills.tdd import TDDRunner

    sess = TDDRunner().load(session_id)
    sess.run_phase(cycle_id, "green", extra_args=args)


@tdd.command("refactor")
@click.argument("session_id")
@click.argument("cycle_id")
@click.option("--note", "-n", default="", help="Describe what you refactored.")
@click.option("--args", default="")
def tdd_refactor(session_id, cycle_id, note, args):
    """Run tests in REFACTOR phase and record a note."""
    from ghcli.skills.tdd import TDDRunner

    sess = TDDRunner().load(session_id)
    if note:
        sess.refactor(cycle_id, note)
    sess.run_phase(cycle_id, "refactor", extra_args=args)


@tdd.command("commit")
@click.argument("session_id")
@click.argument("cycle_id")
@click.option("--message", "-m", required=True, help="Git commit message.")
@click.option("--git/--no-git", default=False, show_default=True, help="Actually run git commit.")
def tdd_commit(session_id, cycle_id, message, git):
    """Mark cycle as committed (optionally run git commit)."""
    from ghcli.skills.tdd import TDDRunner

    sess = TDDRunner().load(session_id)
    sess.commit(cycle_id, message, auto_git=git)


@tdd.command("report")
@click.argument("session_id")
def tdd_report(session_id):
    """Show the TDD report for SESSION_ID."""
    from ghcli.skills.tdd import TDDRunner

    runner = TDDRunner()
    sess = runner.load(session_id)
    report = sess.report()
    runner.print_report(report)


# ═══════════════════════════════════════════════════════════════════════════════
# PARALLEL DISPATCHER
# ═══════════════════════════════════════════════════════════════════════════════


@skills.group("dispatch")
def dispatch():
    """Parallel agent task dispatcher (asyncio / multiprocessing)."""


@dispatch.command("run")
@click.option("--goal", "-g", required=True, help="High-level goal description.")
@click.option(
    "--task",
    "-t",
    multiple=True,
    help="Shell command sub-task (repeatable). E.g. --task 'pytest tests/'",
)
@click.option("--workers", "-w", default=8, show_default=True, help="Max concurrent workers.")
@click.option(
    "--mode",
    default="async",
    type=click.Choice(["async", "process", "sync"]),
    show_default=True,
    help="Execution mode.",
)
@click.option(
    "--timeout", default=60.0, type=float, show_default=True, help="Per-task timeout in seconds."
)
def dispatch_run(goal, task, workers, mode, timeout):
    """Run shell command sub-tasks in parallel."""
    from ghcli.skills.parallel_dispatch import ParallelDispatcher

    if not task:
        console.print("[red]✗ No tasks specified. Use --task 'command'[/red]")
        raise SystemExit(1)
    dispatcher = ParallelDispatcher(max_workers=workers)
    plan = dispatcher.plan(goal)
    for i, cmd in enumerate(task):
        plan.add_shell_task(name=f"task_{i+1}", command=cmd, timeout=timeout)

    if mode == "async":
        report = asyncio.run(dispatcher.execute_async(plan))
    elif mode == "process":
        report = dispatcher.execute_process(plan)
    else:
        report = dispatcher.execute_sync(plan)

    dispatcher.print_report(report)
    if report.failed > 0:
        raise SystemExit(1)


@dispatch.command("list")
def dispatch_list():
    """List all dispatch plans."""
    from ghcli.skills.parallel_dispatch import ParallelDispatcher

    ParallelDispatcher().list_plans()
