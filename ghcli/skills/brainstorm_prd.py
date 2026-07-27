"""
ghcli skills.brainstorm_prd
============================
Interactive brainstorming and Product Requirements Document (PRD) generator.

Workflow
--------
  Phase 1 — INTERVIEW   : Ask structured questions to understand the product
  Phase 2 — BRAINSTORM  : Generate feature ideas and alternatives
  Phase 3 — PRIORITIZE  : Score and rank features (MoSCoW / RICE)
  Phase 4 — DRAFT PRD   : Produce a structured PRD document
  Phase 5 — REVIEW      : Present PRD for approval / revision
  Phase 6 — APPROVED    : PRD locked; ready for implementation

Architecture
------------
  BrainstormPRD         — high-level façade used by CLI commands
  PRDSession            — stateful session tracking interview + PRD
  PRDQuestion           — a single interview question + answer
  Feature               — a product feature with priority score
  PRDDocument           — the final structured PRD

Usage (programmatic)
--------------------
    from ghcli.skills.brainstorm_prd import BrainstormPRD

    prd = BrainstormPRD()
    session = prd.new_session("GitHub CLI skill marketplace")

    # Answer interview questions
    session.answer("problem", "Developers can't easily share CLI skills")
    session.answer("users", "CLI power users, DevOps engineers")
    session.answer("success", "100 published skills in 3 months")

    # Add features
    session.add_feature("Skill registry API", must_have=True, effort=3, impact=9)
    session.add_feature("CLI publish command", must_have=True, effort=2, impact=8)
    session.add_feature("Skill search", must_have=False, effort=2, impact=7)

    doc = session.generate_prd()
    prd.print_prd(doc)
    prd.export_markdown(doc, "prd_skill_marketplace.md")

Usage (CLI)
-----------
    ghcli skills prd new "GitHub CLI skill marketplace"
    ghcli skills prd interview SESSION_ID
    ghcli skills prd feature SESSION_ID "Skill registry API" --must-have --effort 3 --impact 9
    ghcli skills prd generate SESSION_ID
    ghcli skills prd export SESSION_ID --out prd.md
    ghcli skills prd list
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

console = Console()

# ── Persistence ───────────────────────────────────────────────────────────────

PRD_DIR = Path.home() / ".ghcli" / "prd_sessions"


def _session_path(session_id: str) -> Path:
    return PRD_DIR / f"{session_id}.json"


def _save_prd_session(session: "PRDSession") -> None:
    PRD_DIR.mkdir(parents=True, exist_ok=True)
    _session_path(session.session_id).write_text(json.dumps(session.to_dict(), indent=2))


def _load_prd_session(session_id: str) -> "PRDSession":
    path = _session_path(session_id)
    if not path.exists():
        raise KeyError(f"PRD session '{session_id}' not found.")
    return PRDSession.from_dict(json.loads(path.read_text()))


def _list_prd_sessions() -> List[dict]:
    if not PRD_DIR.exists():
        return []
    sessions = []
    for p in sorted(PRD_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            sessions.append(json.loads(p.read_text()))
        except Exception:
            pass
    return sessions


# ── Interview questions ───────────────────────────────────────────────────────

INTERVIEW_QUESTIONS: List[Dict[str, str]] = [
    {"key": "problem", "question": "What problem does this product solve?"},
    {"key": "users", "question": "Who are the primary users / personas?"},
    {"key": "pain_points", "question": "What are the top 3 pain points users face today?"},
    {"key": "solution", "question": "Describe your proposed solution in 2-3 sentences."},
    {"key": "success", "question": "How will you measure success? (KPIs / metrics)"},
    {"key": "constraints", "question": "What are the key constraints? (time, budget, tech)"},
    {"key": "competitors", "question": "Who are the main competitors or alternatives?"},
    {"key": "differentiator", "question": "What makes this product unique / better?"},
    {"key": "timeline", "question": "What is the target launch timeline?"},
    {"key": "out_of_scope", "question": "What is explicitly OUT of scope for v1?"},
]


# ── Data classes ──────────────────────────────────────────────────────────────


@dataclass
class PRDQuestion:
    key: str
    question: str
    answer: str = ""
    answered: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "PRDQuestion":
        return cls(**d)


@dataclass
class Feature:
    name: str
    description: str = ""
    must_have: bool = False  # MoSCoW: Must / Should / Could / Won't
    moscow: str = "should"  # must | should | could | wont
    effort: int = 3  # 1 (trivial) – 10 (huge)
    impact: int = 5  # 1 (low) – 10 (high)
    confidence: float = 0.7  # 0.0 – 1.0 (RICE confidence)
    reach: int = 100  # estimated users reached

    @property
    def rice_score(self) -> float:
        """RICE = (Reach × Impact × Confidence) / Effort"""
        if self.effort == 0:
            return 0.0
        return (self.reach * self.impact * self.confidence) / self.effort

    @property
    def moscow_badge(self) -> str:
        colors = {"must": "bold red", "should": "bold yellow", "could": "cyan", "wont": "dim"}
        labels = {
            "must": "Must Have",
            "should": "Should Have",
            "could": "Could Have",
            "wont": "Won't Have",
        }
        color = colors.get(self.moscow, "white")
        label = labels.get(self.moscow, self.moscow)
        return f"[{color}]{label}[/{color}]"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Feature":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class PRDDocument:
    session_id: str
    product_name: str
    answers: Dict[str, str]
    features: List[Feature]
    created_at: float
    version: int = 1
    status: str = "draft"  # draft | approved

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "product_name": self.product_name,
            "answers": self.answers,
            "features": [f.to_dict() for f in self.features],
            "created_at": self.created_at,
            "version": self.version,
            "status": self.status,
        }

    def to_markdown(self) -> str:
        lines = [
            f"# Product Requirements Document",
            f"## {self.product_name}",
            f"",
            f"**Version:** {self.version}  |  **Status:** {self.status.upper()}  |  "
            f"**Date:** {time.strftime('%Y-%m-%d', time.localtime(self.created_at))}",
            f"",
            f"---",
            f"",
            f"## 1. Problem Statement",
            f"",
            self.answers.get("problem", "_Not answered_"),
            f"",
            f"## 2. Target Users",
            f"",
            self.answers.get("users", "_Not answered_"),
            f"",
            f"## 3. Pain Points",
            f"",
            self.answers.get("pain_points", "_Not answered_"),
            f"",
            f"## 4. Proposed Solution",
            f"",
            self.answers.get("solution", "_Not answered_"),
            f"",
            f"## 5. Success Metrics",
            f"",
            self.answers.get("success", "_Not answered_"),
            f"",
            f"## 6. Constraints",
            f"",
            self.answers.get("constraints", "_Not answered_"),
            f"",
            f"## 7. Competitive Landscape",
            f"",
            self.answers.get("competitors", "_Not answered_"),
            f"",
            f"## 8. Differentiators",
            f"",
            self.answers.get("differentiator", "_Not answered_"),
            f"",
            f"## 9. Timeline",
            f"",
            self.answers.get("timeline", "_Not answered_"),
            f"",
            f"## 10. Out of Scope (v1)",
            f"",
            self.answers.get("out_of_scope", "_Not answered_"),
            f"",
            f"---",
            f"",
            f"## 11. Feature Requirements",
            f"",
            f"| # | Feature | MoSCoW | Effort | Impact | RICE Score |",
            f"|---|---------|--------|--------|--------|------------|",
        ]
        sorted_features = sorted(self.features, key=lambda f: f.rice_score, reverse=True)
        for i, feat in enumerate(sorted_features, 1):
            moscow_labels = {
                "must": "Must Have",
                "should": "Should Have",
                "could": "Could Have",
                "wont": "Won't Have",
            }
            lines.append(
                f"| {i} | {feat.name} | {moscow_labels.get(feat.moscow, feat.moscow)} "
                f"| {feat.effort}/10 | {feat.impact}/10 | {feat.rice_score:.1f} |"
            )
        lines += [
            f"",
            f"---",
            f"",
            f"*Generated by ghcli skills prd*",
        ]
        return "\n".join(lines)


# ── PRD Session ───────────────────────────────────────────────────────────────


class PRDSession:
    """Stateful PRD session."""

    def __init__(
        self,
        product_name: str,
        session_id: Optional[str] = None,
        created_at: Optional[float] = None,
    ):
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self.product_name = product_name
        self.questions: List[PRDQuestion] = [
            PRDQuestion(q["key"], q["question"]) for q in INTERVIEW_QUESTIONS
        ]
        self.features: List[Feature] = []
        self.created_at = created_at or time.time()
        self.status = "interview"  # interview | brainstorm | draft | approved

    def answer(self, key: str, answer: str) -> "PRDSession":
        """Record an answer to an interview question."""
        q = next((q for q in self.questions if q.key == key), None)
        if q is None:
            raise KeyError(f"Question key '{key}' not found.")
        q.answer = answer
        q.answered = True
        _save_prd_session(self)
        return self

    def add_feature(
        self,
        name: str,
        description: str = "",
        must_have: bool = False,
        moscow: str = "should",
        effort: int = 3,
        impact: int = 5,
        confidence: float = 0.7,
        reach: int = 100,
    ) -> Feature:
        if must_have:
            moscow = "must"
        feat = Feature(
            name=name,
            description=description,
            must_have=must_have,
            moscow=moscow,
            effort=effort,
            impact=impact,
            confidence=confidence,
            reach=reach,
        )
        self.features.append(feat)
        _save_prd_session(self)
        return feat

    def generate_prd(self) -> PRDDocument:
        """Generate the PRD document from current session state."""
        answers = {q.key: q.answer for q in self.questions if q.answered}
        doc = PRDDocument(
            session_id=self.session_id,
            product_name=self.product_name,
            answers=answers,
            features=list(self.features),
            created_at=time.time(),
        )
        self.status = "draft"
        _save_prd_session(self)
        return doc

    def approve(self) -> "PRDSession":
        self.status = "approved"
        _save_prd_session(self)
        console.print("[bold green]✓ PRD approved![/bold green] Ready for implementation.")
        return self

    def run_interview(self) -> "PRDSession":
        """Interactive CLI interview — prompts for each unanswered question."""
        console.print(
            Panel(
                f"[bold]Product:[/bold] {self.product_name}\n\n"
                "Answer each question to build your PRD.\n"
                "[dim]Press Enter to skip a question.[/dim]",
                title="[bold cyan]📋 PRD Interview[/bold cyan]",
                border_style="cyan",
            )
        )
        for q in self.questions:
            if q.answered:
                console.print(f"[dim]  ✓ {q.question}[/dim]")
                continue
            answer = Prompt.ask(f"\n[bold cyan]{q.question}[/bold cyan]", default="")
            if answer.strip():
                self.answer(q.key, answer.strip())
        console.print("\n[green]✓ Interview complete.[/green]")
        return self

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "product_name": self.product_name,
            "questions": [q.to_dict() for q in self.questions],
            "features": [f.to_dict() for f in self.features],
            "created_at": self.created_at,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PRDSession":
        sess = cls(
            product_name=d["product_name"],
            session_id=d["session_id"],
            created_at=d["created_at"],
        )
        sess.questions = [PRDQuestion.from_dict(q) for q in d.get("questions", [])]
        sess.features = [Feature.from_dict(f) for f in d.get("features", [])]
        sess.status = d.get("status", "interview")
        return sess


# ── High-level façade ─────────────────────────────────────────────────────────


class BrainstormPRD:
    """High-level PRD generation façade."""

    def new_session(self, product_name: str) -> PRDSession:
        sess = PRDSession(product_name=product_name)
        _save_prd_session(sess)
        console.print(
            Panel(
                f"[bold]Session ID:[/bold] [cyan]{sess.session_id}[/cyan]\n"
                f"[bold]Product:[/bold]    {product_name}\n\n"
                "[dim]Next steps:[/dim]\n"
                f"  [bold]ghcli skills prd interview {sess.session_id}[/bold]  — answer interview questions\n"
                f'  [bold]ghcli skills prd feature {sess.session_id} "Feature name"[/bold]  — add features\n'
                f"  [bold]ghcli skills prd generate {sess.session_id}[/bold]  — generate PRD",
                title="[bold cyan]📋 New PRD Session[/bold cyan]",
                border_style="cyan",
            )
        )
        return sess

    def load(self, session_id: str) -> PRDSession:
        return _load_prd_session(session_id)

    def print_prd(self, doc: PRDDocument) -> None:
        console.print(
            Panel(
                Markdown(doc.to_markdown()),
                title=f"[bold cyan]PRD — {doc.product_name}[/bold cyan]",
                border_style="cyan",
            )
        )

    def print_features(self, sess: PRDSession) -> None:
        if not sess.features:
            console.print("[yellow]No features added yet.[/yellow]")
            return
        table = Table(
            title=f"Features — {sess.product_name}",
            box=box.ROUNDED,
            border_style="cyan",
            header_style="bold cyan",
        )
        table.add_column("#", width=4, justify="right")
        table.add_column("Feature", min_width=25)
        table.add_column("MoSCoW", width=14)
        table.add_column("Effort", justify="right", width=8)
        table.add_column("Impact", justify="right", width=8)
        table.add_column("RICE", justify="right", width=8)
        sorted_features = sorted(sess.features, key=lambda f: f.rice_score, reverse=True)
        for i, feat in enumerate(sorted_features, 1):
            table.add_row(
                str(i),
                feat.name,
                feat.moscow_badge,
                str(feat.effort),
                str(feat.impact),
                f"{feat.rice_score:.1f}",
            )
        console.print(table)

    def export_markdown(self, doc: PRDDocument, path: str) -> None:
        Path(path).write_text(doc.to_markdown())
        console.print(f"[green]✓ PRD exported to {path}[/green]")

    def list_sessions(self) -> None:
        sessions = _list_prd_sessions()
        if not sessions:
            console.print("[yellow]No PRD sessions found.[/yellow]")
            return
        table = Table(
            title="PRD Sessions", box=box.ROUNDED, border_style="cyan", header_style="bold cyan"
        )
        table.add_column("ID", width=10)
        table.add_column("Product", min_width=30)
        table.add_column("Status", width=12)
        table.add_column("Features", justify="right", width=10)
        table.add_column("Created", width=12)
        for s in sessions:
            created = time.strftime("%Y-%m-%d", time.localtime(s.get("created_at", 0)))
            status_colors = {
                "interview": "yellow",
                "brainstorm": "cyan",
                "draft": "blue",
                "approved": "green",
            }
            status = s.get("status", "interview")
            color = status_colors.get(status, "white")
            table.add_row(
                s["session_id"],
                s["product_name"],
                f"[{color}]{status}[/{color}]",
                str(len(s.get("features", []))),
                created,
            )
        console.print(table)
