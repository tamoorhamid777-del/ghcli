"""
ghcli skills.debugger
======================
Systematic multi-phase root cause analysis (RCA) engine.

Enforces the discipline of:
  Phase 1 — REPRODUCE   : confirm the bug is real and repeatable
  Phase 2 — ISOLATE     : narrow the failure surface
  Phase 3 — HYPOTHESIZE : form ranked, falsifiable hypotheses
  Phase 4 — VERIFY      : run targeted experiments to confirm/reject
  Phase 5 — FIX         : apply the minimal change; write a regression test
  Phase 6 — DOCUMENT    : record findings in a structured report

Architecture
------------
  Debugger              — high-level façade used by CLI commands
  DebugSession          — stateful session tracking phases and findings
  DebugPhase            — enum of the six phases
  Finding               — dataclass for a single observation
  Hypothesis            — dataclass for a ranked hypothesis
  DebugReport           — final structured report

Usage (programmatic)
--------------------
    from ghcli.skills.debugger import Debugger

    dbg = Debugger()
    session = dbg.new_session(title="Login fails with 500 on prod")

    session.reproduce("curl -X POST /api/login -d '{...}' → HTTP 500")
    session.isolate("Only fails when email contains a + sign")
    session.hypothesize("URL-encoding bug in email parser", confidence=0.8)
    session.hypothesize("Database constraint on email column", confidence=0.4)
    session.verify("H1", passed=True,
                   evidence="Removing + from email → 200 OK")
    session.fix("Encode email before passing to SQL layer",
                test="test_login_with_plus_email")
    report = session.close()
    dbg.print_report(report)

Usage (CLI)
-----------
    ghcli skills debug new "Login fails with 500"
    ghcli skills debug reproduce SESSION_ID "curl ... → 500"
    ghcli skills debug isolate  SESSION_ID "Only with + in email"
    ghcli skills debug hypothesize SESSION_ID "URL-encoding bug" --confidence 0.8
    ghcli skills debug verify SESSION_ID H1 --passed --evidence "..."
    ghcli skills debug fix SESSION_ID "Encode email" --test "test_login_plus"
    ghcli skills debug report SESSION_ID
    ghcli skills debug list
"""

from __future__ import annotations

import enum
import json
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

DEBUG_DIR = Path.home() / ".ghcli" / "debug_sessions"


def _session_path(session_id: str) -> Path:
    return DEBUG_DIR / f"{session_id}.json"


def _save_session(session: "DebugSession") -> None:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    _session_path(session.session_id).write_text(json.dumps(session.to_dict(), indent=2))


def _load_session(session_id: str) -> "DebugSession":
    path = _session_path(session_id)
    if not path.exists():
        raise KeyError(f"Debug session '{session_id}' not found.")
    data = json.loads(path.read_text())
    return DebugSession.from_dict(data)


def _list_sessions() -> List[dict]:
    if not DEBUG_DIR.exists():
        return []
    sessions = []
    for p in sorted(DEBUG_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            data = json.loads(p.read_text())
            sessions.append(data)
        except Exception:
            pass
    return sessions


# ── Enums & data classes ──────────────────────────────────────────────────────


class DebugPhase(str, enum.Enum):
    REPRODUCE = "reproduce"
    ISOLATE = "isolate"
    HYPOTHESIZE = "hypothesize"
    VERIFY = "verify"
    FIX = "fix"
    DOCUMENT = "document"
    CLOSED = "closed"

    @property
    def label(self) -> str:
        labels = {
            "reproduce": "1 · Reproduce",
            "isolate": "2 · Isolate",
            "hypothesize": "3 · Hypothesize",
            "verify": "4 · Verify",
            "fix": "5 · Fix",
            "document": "6 · Document",
            "closed": "✓ Closed",
        }
        return labels[self.value]

    @property
    def color(self) -> str:
        colors = {
            "reproduce": "yellow",
            "isolate": "cyan",
            "hypothesize": "magenta",
            "verify": "blue",
            "fix": "green",
            "document": "white",
            "closed": "dim",
        }
        return colors[self.value]


@dataclass
class Finding:
    phase: str
    description: str
    timestamp: float = field(default_factory=time.time)
    evidence: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Finding":
        return cls(**d)


@dataclass
class Hypothesis:
    id: str
    description: str
    confidence: float = 0.5  # 0.0 – 1.0
    status: str = "pending"  # pending | confirmed | rejected
    evidence: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Hypothesis":
        return cls(**d)

    @property
    def confidence_bar(self) -> str:
        filled = round(self.confidence * 10)
        return "█" * filled + "░" * (10 - filled)

    @property
    def status_badge(self) -> Text:
        mapping = {
            "pending": Text("⏳ pending", style="yellow"),
            "confirmed": Text("✓ confirmed", style="bold green"),
            "rejected": Text("✗ rejected", style="bold red"),
        }
        return mapping.get(self.status, Text(self.status))


@dataclass
class DebugReport:
    session_id: str
    title: str
    root_cause: str
    fix_applied: str
    regression_test: str
    findings: List[Finding]
    hypotheses: List[Hypothesis]
    duration_seconds: float
    created_at: float
    closed_at: float

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "title": self.title,
            "root_cause": self.root_cause,
            "fix_applied": self.fix_applied,
            "regression_test": self.regression_test,
            "findings": [f.to_dict() for f in self.findings],
            "hypotheses": [h.to_dict() for h in self.hypotheses],
            "duration_seconds": self.duration_seconds,
            "created_at": self.created_at,
            "closed_at": self.closed_at,
        }


# ── Debug session ─────────────────────────────────────────────────────────────


class DebugSession:
    """
    Stateful debug session tracking all phases, findings, and hypotheses.
    Persists to ~/.ghcli/debug_sessions/<id>.json after every mutation.
    """

    def __init__(
        self,
        title: str,
        session_id: Optional[str] = None,
        created_at: Optional[float] = None,
    ):
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self.title = title
        self.phase = DebugPhase.REPRODUCE
        self.findings: List[Finding] = []
        self.hypotheses: List[Hypothesis] = []
        self.root_cause: str = ""
        self.fix_applied: str = ""
        self.regression_test: str = ""
        self.created_at: float = created_at or time.time()
        self.closed_at: Optional[float] = None
        self._hyp_counter = 0

    # ── Phase transitions ─────────────────────────────────────────────────

    def _advance_phase(self, target: DebugPhase) -> None:
        self.phase = target
        _save_session(self)

    def reproduce(self, description: str, evidence: str = "") -> "DebugSession":
        """Record reproduction steps. Advances to ISOLATE."""
        self.findings.append(Finding(DebugPhase.REPRODUCE.value, description, evidence=evidence))
        self._advance_phase(DebugPhase.ISOLATE)
        console.print(
            f"[yellow]✓ Reproduce recorded.[/yellow] Phase → [cyan]{DebugPhase.ISOLATE.label}[/cyan]"
        )
        return self

    def isolate(self, description: str, evidence: str = "") -> "DebugSession":
        """Record isolation findings. Advances to HYPOTHESIZE."""
        self.findings.append(Finding(DebugPhase.ISOLATE.value, description, evidence=evidence))
        self._advance_phase(DebugPhase.HYPOTHESIZE)
        console.print(
            f"[cyan]✓ Isolation recorded.[/cyan] Phase → [magenta]{DebugPhase.HYPOTHESIZE.label}[/magenta]"
        )
        return self

    def hypothesize(self, description: str, confidence: float = 0.5) -> str:
        """Add a hypothesis. Returns its ID (H1, H2, …)."""
        self._hyp_counter += 1
        hyp_id = f"H{self._hyp_counter}"
        self.hypotheses.append(
            Hypothesis(
                id=hyp_id,
                description=description,
                confidence=max(0.0, min(1.0, confidence)),
            )
        )
        _save_session(self)
        console.print(
            f"[magenta]✓ Hypothesis {hyp_id} added[/magenta] "
            f"(confidence {confidence:.0%}): {description}"
        )
        return hyp_id

    def verify(self, hyp_id: str, passed: bool, evidence: str = "") -> "DebugSession":
        """
        Record verification result for a hypothesis.
        If passed=True, advances to FIX.
        """
        hyp = next((h for h in self.hypotheses if h.id == hyp_id), None)
        if hyp is None:
            raise KeyError(f"Hypothesis '{hyp_id}' not found.")
        hyp.status = "confirmed" if passed else "rejected"
        hyp.evidence = evidence
        self.findings.append(
            Finding(
                DebugPhase.VERIFY.value,
                f"{hyp_id} {'confirmed' if passed else 'rejected'}: {hyp.description}",
                evidence=evidence,
            )
        )
        if passed:
            self.root_cause = hyp.description
            self._advance_phase(DebugPhase.FIX)
            console.print(
                f"[green]✓ {hyp_id} confirmed.[/green] Root cause identified. "
                f"Phase → [green]{DebugPhase.FIX.label}[/green]"
            )
        else:
            _save_session(self)
            console.print(f"[red]✗ {hyp_id} rejected.[/red] Continue verifying other hypotheses.")
        return self

    def fix(self, description: str, test: str = "") -> "DebugSession":
        """Record the fix applied. Advances to DOCUMENT."""
        self.fix_applied = description
        self.regression_test = test
        self.findings.append(Finding(DebugPhase.FIX.value, description, evidence=test))
        self._advance_phase(DebugPhase.DOCUMENT)
        console.print(
            f"[green]✓ Fix recorded.[/green] Phase → [white]{DebugPhase.DOCUMENT.label}[/white]"
        )
        return self

    def close(self) -> DebugReport:
        """Finalize the session and return a DebugReport."""
        self.closed_at = time.time()
        self.phase = DebugPhase.CLOSED
        _save_session(self)
        return DebugReport(
            session_id=self.session_id,
            title=self.title,
            root_cause=self.root_cause,
            fix_applied=self.fix_applied,
            regression_test=self.regression_test,
            findings=list(self.findings),
            hypotheses=list(self.hypotheses),
            duration_seconds=self.closed_at - self.created_at,
            created_at=self.created_at,
            closed_at=self.closed_at,
        )

    # ── Serialization ─────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "title": self.title,
            "phase": self.phase.value,
            "findings": [f.to_dict() for f in self.findings],
            "hypotheses": [h.to_dict() for h in self.hypotheses],
            "root_cause": self.root_cause,
            "fix_applied": self.fix_applied,
            "regression_test": self.regression_test,
            "created_at": self.created_at,
            "closed_at": self.closed_at,
            "_hyp_counter": self._hyp_counter,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DebugSession":
        sess = cls(title=d["title"], session_id=d["session_id"], created_at=d["created_at"])
        sess.phase = DebugPhase(d["phase"])
        sess.findings = [Finding.from_dict(f) for f in d.get("findings", [])]
        sess.hypotheses = [Hypothesis.from_dict(h) for h in d.get("hypotheses", [])]
        sess.root_cause = d.get("root_cause", "")
        sess.fix_applied = d.get("fix_applied", "")
        sess.regression_test = d.get("regression_test", "")
        sess.closed_at = d.get("closed_at")
        sess._hyp_counter = d.get("_hyp_counter", len(sess.hypotheses))
        return sess


# ── High-level façade ─────────────────────────────────────────────────────────


class Debugger:
    """High-level debugging façade."""

    def new_session(self, title: str) -> DebugSession:
        sess = DebugSession(title=title)
        _save_session(sess)
        console.print(
            Panel(
                f"[bold]Session ID:[/bold] [cyan]{sess.session_id}[/cyan]\n"
                f"[bold]Title:[/bold]      {title}\n"
                f"[bold]Phase:[/bold]      [{DebugPhase.REPRODUCE.color}]{DebugPhase.REPRODUCE.label}[/{DebugPhase.REPRODUCE.color}]\n\n"
                "[dim]Next step: record reproduction steps with[/dim]\n"
                f'  [bold]ghcli skills debug reproduce {sess.session_id} "<steps>"[/bold]',
                title="[bold cyan]🐛 New Debug Session[/bold cyan]",
                border_style="cyan",
            )
        )
        return sess

    def load(self, session_id: str) -> DebugSession:
        return _load_session(session_id)

    def print_session(self, sess: DebugSession) -> None:
        phase_color = sess.phase.color
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Key", style="bold cyan", width=16)
        table.add_column("Value")
        table.add_row("Session ID", sess.session_id)
        table.add_row("Title", sess.title)
        table.add_row("Phase", f"[{phase_color}]{sess.phase.label}[/{phase_color}]")
        table.add_row("Root cause", sess.root_cause or "—")
        table.add_row("Fix applied", sess.fix_applied or "—")
        table.add_row("Regression test", sess.regression_test or "—")
        console.print(
            Panel(
                table,
                title=f"[bold cyan]Debug Session {sess.session_id}[/bold cyan]",
                border_style="cyan",
            )
        )

        if sess.findings:
            ftable = Table(title="Findings", box=box.SIMPLE, header_style="bold cyan")
            ftable.add_column("Phase", width=16)
            ftable.add_column("Description")
            for f in sess.findings:
                ftable.add_row(
                    f"[{DebugPhase(f.phase).color}]{DebugPhase(f.phase).label}[/{DebugPhase(f.phase).color}]",
                    f.description,
                )
            console.print(ftable)

        if sess.hypotheses:
            htable = Table(title="Hypotheses", box=box.SIMPLE, header_style="bold cyan")
            htable.add_column("ID", width=5)
            htable.add_column("Description")
            htable.add_column("Confidence", width=14)
            htable.add_column("Status", width=16)
            for h in sess.hypotheses:
                htable.add_row(h.id, h.description, h.confidence_bar, str(h.status_badge))
            console.print(htable)

    def print_report(self, report: DebugReport) -> None:
        duration = f"{report.duration_seconds:.1f}s"
        content = (
            f"[bold]Root cause:[/bold]      {report.root_cause or '—'}\n"
            f"[bold]Fix applied:[/bold]     {report.fix_applied or '—'}\n"
            f"[bold]Regression test:[/bold] {report.regression_test or '—'}\n"
            f"[bold]Duration:[/bold]        {duration}\n"
            f"[bold]Findings:[/bold]        {len(report.findings)}\n"
            f"[bold]Hypotheses:[/bold]      {len(report.hypotheses)}"
        )
        console.print(
            Panel(
                content,
                title=f"[bold green]✓ Debug Report — {report.title}[/bold green]",
                border_style="green",
            )
        )

    def list_sessions(self) -> None:
        sessions = _list_sessions()
        if not sessions:
            console.print("[yellow]No debug sessions found.[/yellow]")
            return
        table = Table(
            title="Debug Sessions", box=box.ROUNDED, border_style="cyan", header_style="bold cyan"
        )
        table.add_column("ID", width=10)
        table.add_column("Title", min_width=30)
        table.add_column("Phase", width=18)
        table.add_column("Hypotheses", justify="right", width=12)
        table.add_column("Created", width=12)
        for s in sessions:
            phase = DebugPhase(s.get("phase", "reproduce"))
            created = time.strftime("%Y-%m-%d", time.localtime(s.get("created_at", 0)))
            table.add_row(
                s["session_id"],
                s["title"],
                f"[{phase.color}]{phase.label}[/{phase.color}]",
                str(len(s.get("hypotheses", []))),
                created,
            )
        console.print(table)
