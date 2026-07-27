"""
ghcli skills.parallel_dispatch
================================
Parallel agent dispatcher — splits large goals into sub-tasks and
executes them concurrently using asyncio (I/O-bound) or
multiprocessing (CPU-bound).

Architecture
------------
  ParallelDispatcher    — high-level façade used by CLI commands
  DispatchPlan          — a goal decomposed into AgentTask objects
  AgentTask             — a single sub-task with its worker function
  TaskResult            — result from one completed sub-task
  DispatchReport        — aggregated results from all sub-tasks
  AsyncWorkerPool       — asyncio-based concurrent executor
  ProcessWorkerPool     — multiprocessing-based concurrent executor
  SubprocessWorker      — runs a shell command as a sub-task

Usage (programmatic)
--------------------
    import asyncio
    from ghcli.skills.parallel_dispatch import ParallelDispatcher, AgentTask

    dispatcher = ParallelDispatcher(max_workers=4)

    # Define sub-tasks
    async def fetch_repo_info(task):
        import aiohttp
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://api.github.com/repos/{task.args['repo']}") as r:
                return await r.json()

    plan = dispatcher.plan("Fetch info for multiple repos")
    plan.add_async_task("fetch_django",  fetch_repo_info, args={"repo": "django/django"})
    plan.add_async_task("fetch_flask",   fetch_repo_info, args={"repo": "pallets/flask"})
    plan.add_async_task("fetch_fastapi", fetch_repo_info, args={"repo": "tiangolo/fastapi"})

    report = asyncio.run(dispatcher.execute_async(plan))
    dispatcher.print_report(report)

    # Shell command sub-tasks (subprocess-based)
    plan2 = dispatcher.plan("Run linters in parallel")
    plan2.add_shell_task("flake8",  "flake8 src/")
    plan2.add_shell_task("mypy",    "mypy src/")
    plan2.add_shell_task("bandit",  "bandit -r src/")
    report2 = asyncio.run(dispatcher.execute_async(plan2))

Usage (CLI)
-----------
    ghcli skills dispatch run --goal "Lint and test" \
        --task "flake8 src/" --task "mypy src/" --task "pytest tests/"
    ghcli skills dispatch status PLAN_ID
    ghcli skills dispatch report PLAN_ID
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import os
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Coroutine, Dict, List, Optional, Union

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

console = Console()

# ── Persistence ───────────────────────────────────────────────────────────────

DISPATCH_DIR = Path.home() / ".ghcli" / "dispatch_plans"


def _plan_path(plan_id: str) -> Path:
    return DISPATCH_DIR / f"{plan_id}.json"


def _save_plan(plan: "DispatchPlan") -> None:
    DISPATCH_DIR.mkdir(parents=True, exist_ok=True)
    _plan_path(plan.plan_id).write_text(json.dumps(plan.to_dict(), indent=2))


def _load_plan(plan_id: str) -> "DispatchPlan":
    path = _plan_path(plan_id)
    if not path.exists():
        raise KeyError(f"Dispatch plan '{plan_id}' not found.")
    return DispatchPlan.from_dict(json.loads(path.read_text()))


def _list_plans() -> List[dict]:
    if not DISPATCH_DIR.exists():
        return []
    plans = []
    for p in sorted(DISPATCH_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            plans.append(json.loads(p.read_text()))
        except Exception:
            pass
    return plans


# ── Data classes ──────────────────────────────────────────────────────────────


@dataclass
class TaskResult:
    task_id: str
    task_name: str
    success: bool
    output: Any
    error: Optional[str]
    duration: float
    started_at: float
    finished_at: float

    @property
    def status_badge(self) -> str:
        return "[bold green]✓ OK[/bold green]" if self.success else "[bold red]✗ FAIL[/bold red]"

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "success": self.success,
            "output": str(self.output)[:500] if self.output is not None else None,
            "error": self.error,
            "duration": self.duration,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


@dataclass
class AgentTask:
    task_id: str
    name: str
    kind: str  # "async_fn" | "sync_fn" | "shell"
    fn: Optional[Callable] = None
    shell_cmd: str = ""
    args: Dict[str, Any] = field(default_factory=dict)
    timeout: float = 60.0
    cwd: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "kind": self.kind,
            "shell_cmd": self.shell_cmd,
            "args": self.args,
            "timeout": self.timeout,
            "cwd": self.cwd,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AgentTask":
        return cls(
            task_id=d["task_id"],
            name=d["name"],
            kind=d["kind"],
            shell_cmd=d.get("shell_cmd", ""),
            args=d.get("args", {}),
            timeout=d.get("timeout", 60.0),
            cwd=d.get("cwd"),
        )


@dataclass
class DispatchReport:
    plan_id: str
    goal: str
    results: List[TaskResult]
    total_tasks: int
    succeeded: int
    failed: int
    wall_time: float
    created_at: float

    @property
    def success_rate(self) -> float:
        if self.total_tasks == 0:
            return 0.0
        return self.succeeded / self.total_tasks

    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "goal": self.goal,
            "results": [r.to_dict() for r in self.results],
            "total_tasks": self.total_tasks,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "wall_time": self.wall_time,
            "created_at": self.created_at,
        }


# ── Dispatch plan ─────────────────────────────────────────────────────────────


class DispatchPlan:
    """A goal decomposed into parallel sub-tasks."""

    def __init__(self, goal: str, plan_id: Optional[str] = None):
        self.plan_id = plan_id or str(uuid.uuid4())[:8]
        self.goal = goal
        self.tasks: List[AgentTask] = []
        self.created_at = time.time()
        self.status = "pending"  # pending | running | done | failed

    def add_async_task(
        self,
        name: str,
        fn: Callable[["AgentTask"], Coroutine],
        args: Optional[Dict[str, Any]] = None,
        timeout: float = 60.0,
    ) -> "DispatchPlan":
        """Add an async coroutine task."""
        self.tasks.append(
            AgentTask(
                task_id=str(uuid.uuid4())[:6],
                name=name,
                kind="async_fn",
                fn=fn,
                args=args or {},
                timeout=timeout,
            )
        )
        return self

    def add_sync_task(
        self,
        name: str,
        fn: Callable[["AgentTask"], Any],
        args: Optional[Dict[str, Any]] = None,
        timeout: float = 60.0,
    ) -> "DispatchPlan":
        """Add a synchronous function task (run in thread pool)."""
        self.tasks.append(
            AgentTask(
                task_id=str(uuid.uuid4())[:6],
                name=name,
                kind="sync_fn",
                fn=fn,
                args=args or {},
                timeout=timeout,
            )
        )
        return self

    def add_shell_task(
        self,
        name: str,
        command: str,
        cwd: Optional[str] = None,
        timeout: float = 60.0,
    ) -> "DispatchPlan":
        """Add a shell command task."""
        self.tasks.append(
            AgentTask(
                task_id=str(uuid.uuid4())[:6],
                name=name,
                kind="shell",
                shell_cmd=command,
                cwd=cwd,
                timeout=timeout,
            )
        )
        return self

    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "goal": self.goal,
            "tasks": [t.to_dict() for t in self.tasks],
            "created_at": self.created_at,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DispatchPlan":
        plan = cls(goal=d["goal"], plan_id=d["plan_id"])
        plan.tasks = [AgentTask.from_dict(t) for t in d.get("tasks", [])]
        plan.created_at = d.get("created_at", time.time())
        plan.status = d.get("status", "pending")
        return plan


# ── Async worker pool ─────────────────────────────────────────────────────────


class AsyncWorkerPool:
    """
    Executes a mix of async, sync, and shell tasks concurrently using asyncio.

    - async_fn tasks  → awaited directly
    - sync_fn tasks   → run in a thread pool via loop.run_in_executor
    - shell tasks     → run via asyncio.create_subprocess_shell
    """

    def __init__(self, max_workers: int = 8):
        self.max_workers = max_workers

    async def _run_async_task(self, task: AgentTask) -> TaskResult:
        started = time.time()
        try:
            assert task.fn is not None
            output = await asyncio.wait_for(task.fn(task), timeout=task.timeout)
            return TaskResult(
                task_id=task.task_id,
                task_name=task.name,
                success=True,
                output=output,
                error=None,
                duration=time.time() - started,
                started_at=started,
                finished_at=time.time(),
            )
        except asyncio.TimeoutError:
            return TaskResult(
                task_id=task.task_id,
                task_name=task.name,
                success=False,
                output=None,
                error=f"Timed out after {task.timeout}s",
                duration=time.time() - started,
                started_at=started,
                finished_at=time.time(),
            )
        except Exception as e:
            return TaskResult(
                task_id=task.task_id,
                task_name=task.name,
                success=False,
                output=None,
                error=str(e),
                duration=time.time() - started,
                started_at=started,
                finished_at=time.time(),
            )

    async def _run_sync_task(self, task: AgentTask, loop: asyncio.AbstractEventLoop) -> TaskResult:
        started = time.time()
        try:
            assert task.fn is not None
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                output = await asyncio.wait_for(
                    loop.run_in_executor(executor, lambda: task.fn(task)),  # type: ignore[misc]
                    timeout=task.timeout,
                )
            return TaskResult(
                task_id=task.task_id,
                task_name=task.name,
                success=True,
                output=output,
                error=None,
                duration=time.time() - started,
                started_at=started,
                finished_at=time.time(),
            )
        except asyncio.TimeoutError:
            return TaskResult(
                task_id=task.task_id,
                task_name=task.name,
                success=False,
                output=None,
                error=f"Timed out after {task.timeout}s",
                duration=time.time() - started,
                started_at=started,
                finished_at=time.time(),
            )
        except Exception as e:
            return TaskResult(
                task_id=task.task_id,
                task_name=task.name,
                success=False,
                output=None,
                error=str(e),
                duration=time.time() - started,
                started_at=started,
                finished_at=time.time(),
            )

    async def _run_shell_task(self, task: AgentTask) -> TaskResult:
        started = time.time()
        try:
            proc = await asyncio.create_subprocess_shell(
                task.shell_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=task.cwd or os.getcwd(),
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=task.timeout)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                return TaskResult(
                    task_id=task.task_id,
                    task_name=task.name,
                    success=False,
                    output=None,
                    error=f"Timed out after {task.timeout}s",
                    duration=time.time() - started,
                    started_at=started,
                    finished_at=time.time(),
                )
            success = proc.returncode == 0
            output = stdout.decode(errors="replace")[-2000:]
            error = stderr.decode(errors="replace")[-500:] if not success else None
            return TaskResult(
                task_id=task.task_id,
                task_name=task.name,
                success=success,
                output=output,
                error=error,
                duration=time.time() - started,
                started_at=started,
                finished_at=time.time(),
            )
        except Exception as e:
            return TaskResult(
                task_id=task.task_id,
                task_name=task.name,
                success=False,
                output=None,
                error=str(e),
                duration=time.time() - started,
                started_at=started,
                finished_at=time.time(),
            )

    async def execute(self, tasks: List[AgentTask]) -> List[TaskResult]:
        loop = asyncio.get_event_loop()
        semaphore = asyncio.Semaphore(self.max_workers)

        async def bounded(task: AgentTask) -> TaskResult:
            async with semaphore:
                if task.kind == "async_fn":
                    return await self._run_async_task(task)
                elif task.kind == "sync_fn":
                    return await self._run_sync_task(task, loop)
                elif task.kind == "shell":
                    return await self._run_shell_task(task)
                else:
                    return TaskResult(
                        task_id=task.task_id,
                        task_name=task.name,
                        success=False,
                        output=None,
                        error=f"Unknown task kind: {task.kind}",
                        duration=0,
                        started_at=time.time(),
                        finished_at=time.time(),
                    )

        return await asyncio.gather(*[bounded(t) for t in tasks])


# ── Process worker pool (CPU-bound) ───────────────────────────────────────────


class ProcessWorkerPool:
    """
    Executes shell tasks in separate processes using multiprocessing.
    Best for CPU-bound work where the GIL is a bottleneck.
    """

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers

    @staticmethod
    def _run_shell(args: tuple) -> dict:
        cmd, cwd, timeout = args
        started = time.time()
        try:
            result = subprocess.run(
                cmd,
                shell=True,  # nosec B602
                cwd=cwd or os.getcwd(),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return {
                "success": result.returncode == 0,
                "output": result.stdout[-2000:],
                "error": result.stderr[-500:] if result.returncode != 0 else None,
                "duration": time.time() - started,
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output": None,
                "error": f"Timed out after {timeout}s",
                "duration": time.time() - started,
            }
        except Exception as e:
            return {
                "success": False,
                "output": None,
                "error": str(e),
                "duration": time.time() - started,
            }

    def execute(self, tasks: List[AgentTask]) -> List[TaskResult]:
        shell_tasks = [t for t in tasks if t.kind == "shell"]
        args_list = [(t.shell_cmd, t.cwd, t.timeout) for t in shell_tasks]
        results = []
        with concurrent.futures.ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._run_shell, args): task
                for args, task in zip(args_list, shell_tasks)
            }
            for future, task in futures.items():
                started = time.time()
                try:
                    r = future.result(timeout=task.timeout + 5)
                    results.append(
                        TaskResult(
                            task_id=task.task_id,
                            task_name=task.name,
                            success=r["success"],
                            output=r["output"],
                            error=r["error"],
                            duration=r["duration"],
                            started_at=started,
                            finished_at=time.time(),
                        )
                    )
                except Exception as e:
                    results.append(
                        TaskResult(
                            task_id=task.task_id,
                            task_name=task.name,
                            success=False,
                            output=None,
                            error=str(e),
                            duration=time.time() - started,
                            started_at=started,
                            finished_at=time.time(),
                        )
                    )
        return results


# ── High-level façade ─────────────────────────────────────────────────────────


class ParallelDispatcher:
    """
    High-level parallel dispatch façade.

    Supports:
      - execute_async(plan)    → asyncio-based (I/O-bound, mixed tasks)
      - execute_process(plan)  → multiprocessing (CPU-bound shell tasks)
      - execute_sync(plan)     → sequential fallback (for debugging)
    """

    def __init__(self, max_workers: int = 8):
        self.max_workers = max_workers
        self._async_pool = AsyncWorkerPool(max_workers=max_workers)
        self._process_pool = ProcessWorkerPool(max_workers=max_workers)

    def plan(self, goal: str) -> DispatchPlan:
        p = DispatchPlan(goal=goal)
        _save_plan(p)
        return p

    async def execute_async(self, plan: DispatchPlan, verbose: bool = True) -> DispatchReport:
        """Execute all tasks concurrently using asyncio."""
        plan.status = "running"
        _save_plan(plan)
        wall_start = time.time()

        if verbose:
            console.print(
                Panel(
                    f"[bold]Goal:[/bold]    {plan.goal}\n"
                    f"[bold]Tasks:[/bold]   {len(plan.tasks)}\n"
                    f"[bold]Workers:[/bold] {self.max_workers}",
                    title="[bold cyan]⚡ Parallel Dispatch[/bold cyan]",
                    border_style="cyan",
                )
            )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
            transient=True,
        ) as progress:
            prog_task = progress.add_task(
                f"Running {len(plan.tasks)} tasks…", total=len(plan.tasks)
            )

            async def tracked(task: AgentTask) -> TaskResult:
                result = (
                    await self._async_pool._run_async_task(task)
                    if task.kind == "async_fn"
                    else (
                        await self._async_pool._run_shell_task(task)
                        if task.kind == "shell"
                        else await self._async_pool._run_sync_task(task, asyncio.get_event_loop())
                    )
                )
                progress.advance(prog_task)
                return result

            results = await asyncio.gather(*[tracked(t) for t in plan.tasks])

        wall_time = time.time() - wall_start
        succeeded = sum(1 for r in results if r.success)
        failed = len(results) - succeeded
        plan.status = "done" if failed == 0 else "failed"
        _save_plan(plan)

        report = DispatchReport(
            plan_id=plan.plan_id,
            goal=plan.goal,
            results=list(results),
            total_tasks=len(results),
            succeeded=succeeded,
            failed=failed,
            wall_time=wall_time,
            created_at=time.time(),
        )
        return report

    def execute_process(self, plan: DispatchPlan) -> DispatchReport:
        """Execute shell tasks in separate processes (CPU-bound)."""
        wall_start = time.time()
        results = self._process_pool.execute(plan.tasks)
        wall_time = time.time() - wall_start
        succeeded = sum(1 for r in results if r.success)
        return DispatchReport(
            plan_id=plan.plan_id,
            goal=plan.goal,
            results=results,
            total_tasks=len(results),
            succeeded=succeeded,
            failed=len(results) - succeeded,
            wall_time=wall_time,
            created_at=time.time(),
        )

    def execute_sync(self, plan: DispatchPlan) -> DispatchReport:
        """Execute tasks sequentially (useful for debugging)."""
        results = []
        for task in plan.tasks:
            started = time.time()
            if task.kind == "shell":
                r = subprocess.run(
                    task.shell_cmd,
                    shell=True,  # nosec B602
                    cwd=task.cwd or os.getcwd(),
                    capture_output=True,
                    text=True,
                    timeout=task.timeout,
                )
                results.append(
                    TaskResult(
                        task_id=task.task_id,
                        task_name=task.name,
                        success=r.returncode == 0,
                        output=r.stdout[-2000:],
                        error=r.stderr[-500:] if r.returncode != 0 else None,
                        duration=time.time() - started,
                        started_at=started,
                        finished_at=time.time(),
                    )
                )
            elif task.kind in ("async_fn", "sync_fn") and task.fn:
                try:
                    if task.kind == "async_fn":
                        output = asyncio.run(task.fn(task))
                    else:
                        output = task.fn(task)
                    results.append(
                        TaskResult(
                            task_id=task.task_id,
                            task_name=task.name,
                            success=True,
                            output=output,
                            error=None,
                            duration=time.time() - started,
                            started_at=started,
                            finished_at=time.time(),
                        )
                    )
                except Exception as e:
                    results.append(
                        TaskResult(
                            task_id=task.task_id,
                            task_name=task.name,
                            success=False,
                            output=None,
                            error=str(e),
                            duration=time.time() - started,
                            started_at=started,
                            finished_at=time.time(),
                        )
                    )
        succeeded = sum(1 for r in results if r.success)
        return DispatchReport(
            plan_id=plan.plan_id,
            goal=plan.goal,
            results=results,
            total_tasks=len(results),
            succeeded=succeeded,
            failed=len(results) - succeeded,
            wall_time=sum(r.duration for r in results),
            created_at=time.time(),
        )

    # ── Display helpers ───────────────────────────────────────────────────

    def print_report(self, report: DispatchReport) -> None:
        rate_color = (
            "green"
            if report.success_rate == 1.0
            else "yellow" if report.success_rate >= 0.5 else "red"
        )
        console.print(
            Panel(
                f"[bold]Goal:[/bold]         {report.goal}\n"
                f"[bold]Tasks:[/bold]        {report.total_tasks}\n"
                f"[bold]Succeeded:[/bold]    [{rate_color}]{report.succeeded}[/{rate_color}]\n"
                f"[bold]Failed:[/bold]       [{'red' if report.failed else 'dim'}]{report.failed}[/{'red' if report.failed else 'dim'}]\n"
                f"[bold]Wall time:[/bold]    {report.wall_time:.2f}s\n"
                f"[bold]Success rate:[/bold] [{rate_color}]{report.success_rate:.0%}[/{rate_color}]",
                title="[bold cyan]⚡ Dispatch Report[/bold cyan]",
                border_style="cyan",
            )
        )
        table = Table(
            title="Task Results", box=box.ROUNDED, border_style="cyan", header_style="bold cyan"
        )
        table.add_column("Task", min_width=20)
        table.add_column("Status", width=12)
        table.add_column("Duration", justify="right", width=10)
        table.add_column("Output / Error", min_width=40)
        for r in report.results:
            output_preview = (str(r.output or "")[:80] + "…") if r.output else ""
            error_preview = (r.error or "")[:80]
            detail = output_preview if r.success else f"[red]{error_preview}[/red]"
            table.add_row(r.task_name, r.status_badge, f"{r.duration:.2f}s", detail)
        console.print(table)

    def list_plans(self) -> None:
        plans = _list_plans()
        if not plans:
            console.print("[yellow]No dispatch plans found.[/yellow]")
            return
        table = Table(
            title="Dispatch Plans", box=box.ROUNDED, border_style="cyan", header_style="bold cyan"
        )
        table.add_column("ID", width=10)
        table.add_column("Goal", min_width=30)
        table.add_column("Tasks", justify="right", width=8)
        table.add_column("Status", width=10)
        table.add_column("Created", width=12)
        for p in plans:
            created = time.strftime("%Y-%m-%d", time.localtime(p.get("created_at", 0)))
            status_colors = {
                "pending": "yellow",
                "running": "cyan",
                "done": "green",
                "failed": "red",
            }
            status = p.get("status", "pending")
            color = status_colors.get(status, "white")
            table.add_row(
                p["plan_id"],
                p["goal"],
                str(len(p.get("tasks", []))),
                f"[{color}]{status}[/{color}]",
                created,
            )
        console.print(table)
