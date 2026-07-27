"""
ghcli skills.tdd
=================
Test-Driven Development (TDD) red-green-refactor loop enforcer.

Enforces the strict TDD discipline:
  Phase RED      : Write a failing test first (no implementation yet)
  Phase GREEN    : Write the minimal code to make the test pass
  Phase REFACTOR : Clean up code without breaking tests
  Phase COMMIT   : Commit the passing, clean code

Architecture
------------
  TDDRunner             — high-level façade used by CLI commands
  TDDSession            — stateful session tracking cycles
  TDDCycle              — one red-green-refactor iteration
  TestResult            — result of running a test suite
  TDDReport             — summary of all cycles in a session

Usage (programmatic)
--------------------
    from ghcli.skills.tdd import TDDRunner

    tdd = TDDRunner(test_command="pytest tests/ -v", src_dir="src/")
    session = tdd.new_session("Add user authentication")

    # Cycle 1
    cycle = session.start_cycle("test_login_returns_200")
    cycle.write_test("tests/test_auth.py", test_code)
    result = cycle.run_red()          # must FAIL
    cycle.write_impl("src/auth.py", impl_code)
    result = cycle.run_green()        # must PASS
    cycle.refactor("Extract token validation to helper")
    result = cycle.run_refactor()     # must still PASS
    cycle.commit("feat: add login endpoint")
    session.close_cycle(cycle)

    report = session.report()
    tdd.print_report(report)

Usage (CLI)
-----------
    ghcli skills tdd new "Add user authentication" --test-cmd "pytest tests/ -v"
    ghcli skills tdd cycle SESSION_ID "test_login_returns_200"
    ghcli skills tdd red SESSION_ID CYCLE_ID
    ghcli skills tdd green SESSION_ID CYCLE_ID
    ghcli skills tdd refactor SESSION_ID CYCLE_ID --note "Extract helper"
    ghcli skills tdd commit SESSION_ID CYCLE_ID --message "feat: add login"
    ghcli skills tdd report SESSION_ID
    ghcli skills tdd list
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()

# ── Persistence ───────────────────────────────────────────────────────────────

TDD_DIR = Path.home() / ".ghcli" / "tdd_sessions"


def _session_path(session_id: str) -> Path:
    return TDD_DIR / f"{session_id}.json"


def _save_tdd_session(session: "TDDSession") -> None:
    TDD_DIR.mkdir(parents=True, exist_ok=True)
    _session_path(session.session_id).write_text(json.dumps(session.to_dict(), indent=2))


def _load_tdd_session(session_id: str) -> "TDDSession":
    path = _session_path(session_id)
    if not path.exists():
        raise KeyError(f"TDD session '{session_id}' not found.")
    return TDDSession.from_dict(json.loads(path.read_text()))


def _list_tdd_sessions() -> List[dict]:
    if not TDD_DIR.exists():
        return []
    sessions = []
    for p in sorted(TDD_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            sessions.append(json.loads(p.read_text()))
        except Exception:
            pass
    return sessions


# ── Data classes ──────────────────────────────────────────────────────────────


@dataclass
class TestResult:
    phase: str  # red | green | refactor
    passed: bool
    exit_code: int
    stdout: str
    stderr: str
    duration: float
    timestamp: float = field(default_factory=time.time)

    @property
    def summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return f"[{self.phase.upper()}] {status} in {self.duration:.2f}s (exit {self.exit_code})"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "TestResult":
        return cls(**d)


@dataclass
class TDDCycle:
    cycle_id: str
    test_name: str
    phase: str = "red"  # red | green | refactor | committed | done
    test_file: str = ""
    impl_file: str = ""
    refactor_note: str = ""
    commit_message: str = ""
    results: List[TestResult] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    @property
    def is_complete(self) -> bool:
        return self.phase in ("committed", "done")

    @property
    def phase_badge(self) -> Text:
        mapping = {
            "red": Text("🔴 RED", style="bold red"),
            "green": Text("🟢 GREEN", style="bold green"),
            "refactor": Text("🔵 REFACTOR", style="bold blue"),
            "committed": Text("✓ COMMITTED", style="bold cyan"),
            "done": Text("✓ DONE", style="bold dim"),
        }
        return mapping.get(self.phase, Text(self.phase))

    def to_dict(self) -> dict:
        return {
            "cycle_id": self.cycle_id,
            "test_name": self.test_name,
            "phase": self.phase,
            "test_file": self.test_file,
            "impl_file": self.impl_file,
            "refactor_note": self.refactor_note,
            "commit_message": self.commit_message,
            "results": [r.to_dict() for r in self.results],
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TDDCycle":
        obj = cls(
            cycle_id=d["cycle_id"],
            test_name=d["test_name"],
            phase=d.get("phase", "red"),
            test_file=d.get("test_file", ""),
            impl_file=d.get("impl_file", ""),
            refactor_note=d.get("refactor_note", ""),
            commit_message=d.get("commit_message", ""),
            created_at=d.get("created_at", time.time()),
            completed_at=d.get("completed_at"),
        )
        obj.results = [TestResult.from_dict(r) for r in d.get("results", [])]
        return obj


@dataclass
class TDDReport:
    session_id: str
    title: str
    cycles: List[TDDCycle]
    total_cycles: int
    completed_cycles: int
    total_test_runs: int
    created_at: float
    closed_at: Optional[float]


# ── Test runner ───────────────────────────────────────────────────────────────


class TestRunner:
    """Executes a test command and captures results."""

    def __init__(self, command: str, cwd: Optional[str] = None):
        self.command = command
        self.cwd = cwd or os.getcwd()

    def run(self, phase: str, extra_args: str = "") -> TestResult:
        cmd = f"{self.command} {extra_args}".strip()
        t0 = time.time()
        try:
            result = subprocess.run(
                cmd,
                shell=True,  # nosec B602
                cwd=self.cwd,
                capture_output=True,
                text=True,
                timeout=120,
            )
            duration = time.time() - t0
            return TestResult(
                phase=phase,
                passed=result.returncode == 0,
                exit_code=result.returncode,
                stdout=result.stdout[-3000:],  # keep last 3000 chars
                stderr=result.stderr[-1000:],
                duration=duration,
            )
        except subprocess.TimeoutExpired:
            return TestResult(
                phase=phase,
                passed=False,
                exit_code=-1,
                stdout="",
                stderr="Test run timed out after 120s",
                duration=time.time() - t0,
            )
        except Exception as e:
            return TestResult(
                phase=phase,
                passed=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration=time.time() - t0,
            )


# ── TDD Session ───────────────────────────────────────────────────────────────


class TDDSession:
    """Stateful TDD session tracking all cycles."""

    def __init__(
        self,
        title: str,
        test_command: str = "pytest",
        src_dir: str = ".",
        session_id: Optional[str] = None,
        created_at: Optional[float] = None,
    ):
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self.title = title
        self.test_command = test_command
        self.src_dir = src_dir
        self.cycles: List[TDDCycle] = []
        self.created_at = created_at or time.time()
        self._runner = TestRunner(test_command, cwd=src_dir)

    def start_cycle(self, test_name: str) -> TDDCycle:
        """Begin a new TDD cycle for the given test name."""
        cycle = TDDCycle(
            cycle_id=str(uuid.uuid4())[:6],
            test_name=test_name,
        )
        self.cycles.append(cycle)
        _save_tdd_session(self)
        console.print(
            Panel(
                f"[bold]Cycle ID:[/bold]  [cyan]{cycle.cycle_id}[/cyan]\n"
                f"[bold]Test:[/bold]      {test_name}\n"
                f"[bold]Phase:[/bold]     {cycle.phase_badge}\n\n"
                "[dim]Step 1: Write a FAILING test first.[/dim]\n"
                "[dim]Step 2: Run 'red' to confirm it fails.[/dim]",
                title="[bold red]🔴 New TDD Cycle[/bold red]",
                border_style="red",
            )
        )
        return cycle

    def get_cycle(self, cycle_id: str) -> TDDCycle:
        cycle = next((c for c in self.cycles if c.cycle_id == cycle_id), None)
        if cycle is None:
            raise KeyError(f"Cycle '{cycle_id}' not found.")
        return cycle

    def run_phase(self, cycle_id: str, phase: str, extra_args: str = "") -> TestResult:
        """
        Run tests for a specific phase.
        RED    → test must FAIL (exit != 0)
        GREEN  → test must PASS (exit == 0)
        REFACTOR → test must still PASS (exit == 0)
        """
        cycle = self.get_cycle(cycle_id)
        result = self._runner.run(phase, extra_args)
        cycle.results.append(result)

        if phase == "red":
            if result.passed:
                console.print(
                    "[bold yellow]⚠ RED phase: tests PASSED — but they should FAIL![/bold yellow]\n"
                    "[dim]Your test may already be implemented, or the test is wrong.[/dim]"
                )
            else:
                console.print(
                    "[bold red]✓ RED phase: tests failed as expected.[/bold red] Now write the implementation."
                )
                cycle.phase = "green"

        elif phase == "green":
            if result.passed:
                console.print("[bold green]✓ GREEN phase: tests pass![/bold green] Now refactor.")
                cycle.phase = "refactor"
            else:
                console.print(
                    "[bold red]✗ GREEN phase: tests still failing.[/bold red]\n"
                    "[dim]Fix the implementation and run green again.[/dim]"
                )

        elif phase == "refactor":
            if result.passed:
                console.print(
                    "[bold blue]✓ REFACTOR phase: tests still pass.[/bold blue] Ready to commit."
                )
                cycle.phase = "committed"
            else:
                console.print(
                    "[bold red]✗ REFACTOR broke the tests![/bold red]\n"
                    "[dim]Revert your refactoring changes and try again.[/dim]"
                )

        _save_tdd_session(self)
        self._print_result(result)
        return result

    def write_test(self, cycle_id: str, file_path: str, code: str) -> None:
        """Write test code to a file and record it in the cycle."""
        cycle = self.get_cycle(cycle_id)
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        Path(file_path).write_text(code)
        cycle.test_file = file_path
        _save_tdd_session(self)
        console.print(f"[dim]✓ Test written to {file_path}[/dim]")

    def write_impl(self, cycle_id: str, file_path: str, code: str) -> None:
        """Write implementation code to a file and record it in the cycle."""
        cycle = self.get_cycle(cycle_id)
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        Path(file_path).write_text(code)
        cycle.impl_file = file_path
        _save_tdd_session(self)
        console.print(f"[dim]✓ Implementation written to {file_path}[/dim]")

    def refactor(self, cycle_id: str, note: str) -> None:
        cycle = self.get_cycle(cycle_id)
        cycle.refactor_note = note
        _save_tdd_session(self)
        console.print(f"[blue]✓ Refactor note recorded:[/blue] {note}")

    def commit(self, cycle_id: str, message: str, auto_git: bool = False) -> None:
        cycle = self.get_cycle(cycle_id)
        cycle.commit_message = message
        cycle.phase = "done"
        cycle.completed_at = time.time()
        if auto_git:
            try:
                subprocess.run(["git", "add", "-A"], cwd=self.src_dir, check=True)
                subprocess.run(["git", "commit", "-m", message], cwd=self.src_dir, check=True)
                console.print(f"[green]✓ Committed:[/green] {message}")
            except subprocess.CalledProcessError as e:
                console.print(f"[yellow]⚠ Git commit failed: {e}[/yellow]")
        else:
            console.print(f"[green]✓ Cycle complete.[/green] Commit message: [dim]{message}[/dim]")
        _save_tdd_session(self)

    def report(self) -> TDDReport:
        completed = [c for c in self.cycles if c.is_complete]
        total_runs = sum(len(c.results) for c in self.cycles)
        return TDDReport(
            session_id=self.session_id,
            title=self.title,
            cycles=list(self.cycles),
            total_cycles=len(self.cycles),
            completed_cycles=len(completed),
            total_test_runs=total_runs,
            created_at=self.created_at,
            closed_at=None,
        )

    def _print_result(self, result: TestResult) -> None:
        color = "green" if result.passed else "red"
        status = "PASS" if result.passed else "FAIL"
        console.print(
            Panel(
                f"[bold {color}]{status}[/bold {color}]  exit={result.exit_code}  {result.duration:.2f}s\n\n"
                f"[dim]{result.stdout[-800:]}[/dim]",
                title=f"[bold]Test Run — {result.phase.upper()}[/bold]",
                border_style=color,
            )
        )

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "title": self.title,
            "test_command": self.test_command,
            "src_dir": self.src_dir,
            "cycles": [c.to_dict() for c in self.cycles],
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TDDSession":
        sess = cls(
            title=d["title"],
            test_command=d.get("test_command", "pytest"),
            src_dir=d.get("src_dir", "."),
            session_id=d["session_id"],
            created_at=d.get("created_at"),
        )
        sess.cycles = [TDDCycle.from_dict(c) for c in d.get("cycles", [])]
        return sess


# ── High-level façade ─────────────────────────────────────────────────────────


class TDDRunner:
    """High-level TDD façade."""

    def __init__(self, test_command: str = "pytest", src_dir: str = "."):
        self.test_command = test_command
        self.src_dir = src_dir

    def new_session(self, title: str) -> TDDSession:
        sess = TDDSession(title=title, test_command=self.test_command, src_dir=self.src_dir)
        _save_tdd_session(sess)
        console.print(
            Panel(
                f"[bold]Session ID:[/bold]   [cyan]{sess.session_id}[/cyan]\n"
                f"[bold]Title:[/bold]        {title}\n"
                f"[bold]Test command:[/bold] [dim]{self.test_command}[/dim]\n"
                f"[bold]Source dir:[/bold]   [dim]{self.src_dir}[/dim]\n\n"
                "[dim]TDD Loop: RED → GREEN → REFACTOR → COMMIT[/dim]",
                title="[bold cyan]🧪 New TDD Session[/bold cyan]",
                border_style="cyan",
            )
        )
        return sess

    def load(self, session_id: str) -> TDDSession:
        return _load_tdd_session(session_id)

    def print_report(self, report: TDDReport) -> None:
        console.print(
            Panel(
                f"[bold]Title:[/bold]          {report.title}\n"
                f"[bold]Cycles:[/bold]         {report.completed_cycles}/{report.total_cycles} completed\n"
                f"[bold]Total test runs:[/bold] {report.total_test_runs}",
                title="[bold cyan]🧪 TDD Report[/bold cyan]",
                border_style="cyan",
            )
        )
        if report.cycles:
            table = Table(
                title="Cycles", box=box.ROUNDED, border_style="cyan", header_style="bold cyan"
            )
            table.add_column("ID", width=8)
            table.add_column("Test name", min_width=30)
            table.add_column("Phase", width=14)
            table.add_column("Runs", justify="right", width=6)
            table.add_column("Commit message", min_width=25)
            for c in report.cycles:
                table.add_row(
                    c.cycle_id,
                    c.test_name,
                    str(c.phase_badge),
                    str(len(c.results)),
                    c.commit_message or "—",
                )
            console.print(table)

    def list_sessions(self) -> None:
        sessions = _list_tdd_sessions()
        if not sessions:
            console.print("[yellow]No TDD sessions found.[/yellow]")
            return
        table = Table(
            title="TDD Sessions", box=box.ROUNDED, border_style="cyan", header_style="bold cyan"
        )
        table.add_column("ID", width=10)
        table.add_column("Title", min_width=30)
        table.add_column("Cycles", justify="right", width=8)
        table.add_column("Test command", min_width=20)
        table.add_column("Created", width=12)
        for s in sessions:
            created = time.strftime("%Y-%m-%d", time.localtime(s.get("created_at", 0)))
            table.add_row(
                s["session_id"],
                s["title"],
                str(len(s.get("cycles", []))),
                s.get("test_command", "pytest"),
                created,
            )
        console.print(table)
