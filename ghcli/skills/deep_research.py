"""
ghcli skills.deep_research
===========================
Multi-step deep research and data extraction engine.

Executes structured research plans across multiple sources:
  - Web search (DuckDuckGo, SerpAPI, Brave Search)
  - GitHub API (repos, issues, code search)
  - arXiv / Semantic Scholar (academic papers)
  - Wikipedia / Wikidata
  - Custom REST APIs

Architecture
------------
  DeepResearcher         — high-level façade used by CLI commands
  ResearchPlan           — ordered list of ResearchStep objects
  ResearchStep           — a single query against a named source
  ResearchResult         — typed result from one step
  ResearchReport         — aggregated findings from all steps
  SourceAdapter          — abstract base for source-specific adapters
  WebSearchAdapter       — DuckDuckGo / SerpAPI / Brave
  GitHubSearchAdapter    — GitHub code/repo/issue search
  ArxivAdapter           — arXiv paper search
  WikipediaAdapter       — Wikipedia article fetch

Usage (programmatic)
--------------------
    from ghcli.skills.deep_research import DeepResearcher

    researcher = DeepResearcher()
    plan = researcher.plan("asyncio performance Python 3.12")
    plan.add_step("web",    "asyncio performance improvements Python 3.12")
    plan.add_step("arxiv",  "asyncio event loop optimization")
    plan.add_step("github", "asyncio benchmark repo:python/cpython")
    report = researcher.execute(plan)
    researcher.print_report(report)

Usage (CLI)
-----------
    ghcli skills research query "asyncio performance Python 3.12"
    ghcli skills research query "asyncio" --source web --source arxiv
    ghcli skills research query "asyncio" --source github --limit 5
    ghcli skills research extract https://example.com --selector "article p"
"""

from __future__ import annotations

import abc
import json
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests
from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

console = Console()

DEFAULT_TIMEOUT = 15
DEFAULT_HEADERS = {"User-Agent": "ghcli/2.0.0 (research-skill; +https://github.com/ghcli)"}


# ── Data classes ──────────────────────────────────────────────────────────────


@dataclass
class ResearchStep:
    source: str  # "web" | "github" | "arxiv" | "wikipedia" | "url"
    query: str
    limit: int = 5
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResearchResult:
    source: str
    query: str
    items: List[Dict[str, Any]]
    error: Optional[str] = None
    elapsed: float = 0.0

    @property
    def success(self) -> bool:
        return self.error is None

    def __len__(self) -> int:
        return len(self.items)


@dataclass
class ResearchReport:
    topic: str
    results: List[ResearchResult]
    created_at: float = field(default_factory=time.time)

    @property
    def total_items(self) -> int:
        return sum(len(r) for r in self.results)

    @property
    def successful_sources(self) -> int:
        return sum(1 for r in self.results if r.success)

    def all_items(self) -> List[Dict[str, Any]]:
        items = []
        for r in self.results:
            for item in r.items:
                items.append({**item, "_source": r.source})
        return items


class ResearchPlan:
    def __init__(self, topic: str):
        self.topic = topic
        self.steps: List[ResearchStep] = []

    def add_step(self, source: str, query: str, limit: int = 5, **extra) -> "ResearchPlan":
        self.steps.append(ResearchStep(source=source, query=query, limit=limit, extra=extra))
        return self

    def add_default_steps(self, limit: int = 5) -> "ResearchPlan":
        """Add a sensible default set of steps for the topic."""
        self.add_step("web", self.topic, limit=limit)
        self.add_step("github", self.topic, limit=limit)
        self.add_step("wikipedia", self.topic, limit=1)
        return self


# ── Source adapters ───────────────────────────────────────────────────────────


class SourceAdapter(abc.ABC):
    name: str = "base"

    @abc.abstractmethod
    def search(self, query: str, limit: int = 5, **kwargs) -> List[Dict[str, Any]]: ...


class WebSearchAdapter(SourceAdapter):
    """
    Web search via DuckDuckGo Instant Answer API (no key required).
    Falls back to SerpAPI or Brave if SERPAPI_KEY / BRAVE_SEARCH_KEY env vars are set.
    """

    name = "web"

    def search(self, query: str, limit: int = 5, **kwargs) -> List[Dict[str, Any]]:
        import os

        serpapi_key = os.environ.get("SERPAPI_KEY")
        brave_key = os.environ.get("BRAVE_SEARCH_KEY")

        if serpapi_key:
            return self._serpapi(query, limit, serpapi_key)
        if brave_key:
            return self._brave(query, limit, brave_key)
        return self._duckduckgo(query, limit)

    def _duckduckgo(self, query: str, limit: int) -> List[Dict[str, Any]]:
        url = "https://api.duckduckgo.com/"
        params = {"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"}
        resp = requests.get(url, params=params, headers=DEFAULT_HEADERS, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        items = []
        # Abstract (top result)
        if data.get("Abstract"):
            items.append(
                {
                    "title": data.get("Heading", query),
                    "url": data.get("AbstractURL", ""),
                    "snippet": data["Abstract"],
                    "source": "DuckDuckGo Abstract",
                }
            )
        # Related topics
        for topic in data.get("RelatedTopics", [])[:limit]:
            if isinstance(topic, dict) and topic.get("Text"):
                items.append(
                    {
                        "title": topic.get("Text", "")[:80],
                        "url": topic.get("FirstURL", ""),
                        "snippet": topic.get("Text", ""),
                        "source": "DuckDuckGo",
                    }
                )
        return items[:limit]

    def _serpapi(self, query: str, limit: int, key: str) -> List[Dict[str, Any]]:
        url = "https://serpapi.com/search"
        params = {"q": query, "api_key": key, "num": limit, "engine": "google"}
        resp = requests.get(url, params=params, headers=DEFAULT_HEADERS, timeout=DEFAULT_TIMEOUT)  # type: ignore[arg-type]
        resp.raise_for_status()
        data = resp.json()
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("link", ""),
                "snippet": r.get("snippet", ""),
                "source": "SerpAPI/Google",
            }
            for r in data.get("organic_results", [])[:limit]
        ]

    def _brave(self, query: str, limit: int, key: str) -> List[Dict[str, Any]]:
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {**DEFAULT_HEADERS, "Accept": "application/json", "X-Subscription-Token": key}
        params = {"q": query, "count": limit}
        resp = requests.get(url, params=params, headers=headers, timeout=DEFAULT_TIMEOUT)  # type: ignore[arg-type]
        resp.raise_for_status()
        data = resp.json()
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("description", ""),
                "source": "Brave Search",
            }
            for r in data.get("web", {}).get("results", [])[:limit]
        ]


class GitHubSearchAdapter(SourceAdapter):
    """GitHub code / repo / issue search via the REST API."""

    name = "github"

    def __init__(self, token: Optional[str] = None):
        import os

        self._token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

    def _headers(self) -> dict:
        h = {**DEFAULT_HEADERS, "Accept": "application/vnd.github+json"}
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        return h

    def search(
        self, query: str, limit: int = 5, kind: str = "repositories", **kwargs
    ) -> List[Dict[str, Any]]:
        """
        kind: "repositories" | "code" | "issues" | "commits"
        """
        url = f"https://api.github.com/search/{kind}"
        params = {"q": query, "per_page": min(limit, 30)}
        resp = requests.get(url, params=params, headers=self._headers(), timeout=DEFAULT_TIMEOUT)  # type: ignore[arg-type]
        resp.raise_for_status()
        data = resp.json()
        items = []
        for item in data.get("items", [])[:limit]:
            if kind == "repositories":
                items.append(
                    {
                        "title": item.get("full_name", ""),
                        "url": item.get("html_url", ""),
                        "snippet": item.get("description", "") or "",
                        "stars": item.get("stargazers_count", 0),
                        "language": item.get("language", ""),
                        "source": "GitHub Repos",
                    }
                )
            elif kind == "code":
                items.append(
                    {
                        "title": item.get("path", ""),
                        "url": item.get("html_url", ""),
                        "snippet": item.get("repository", {}).get("full_name", ""),
                        "source": "GitHub Code",
                    }
                )
            elif kind == "issues":
                items.append(
                    {
                        "title": item.get("title", ""),
                        "url": item.get("html_url", ""),
                        "snippet": (item.get("body") or "")[:200],
                        "state": item.get("state", ""),
                        "source": "GitHub Issues",
                    }
                )
        return items


class ArxivAdapter(SourceAdapter):
    """arXiv paper search via the Atom API."""

    name = "arxiv"

    def search(self, query: str, limit: int = 5, **kwargs) -> List[Dict[str, Any]]:
        import xml.etree.ElementTree as ET

        url = "https://export.arxiv.org/api/query"
        params = {
            "search_query": f"all:{urllib.parse.quote(query)}",
            "start": 0,
            "max_results": limit,
            "sortBy": "relevance",
        }
        resp = requests.get(url, params=params, headers=DEFAULT_HEADERS, timeout=DEFAULT_TIMEOUT)  # type: ignore[arg-type]
        resp.raise_for_status()
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(resp.text)  # nosec B314
        items = []
        for entry in root.findall("atom:entry", ns)[:limit]:
            title = (entry.findtext("atom:title", "", ns) or "").strip().replace("\n", " ")
            summary = (entry.findtext("atom:summary", "", ns) or "").strip()[:300]
            link_el = entry.find("atom:id", ns)
            url_val = link_el.text if link_el is not None else ""
            authors = [a.findtext("atom:name", "", ns) for a in entry.findall("atom:author", ns)]
            items.append(
                {
                    "title": title,
                    "url": url_val,
                    "snippet": summary,
                    "authors": ", ".join(authors[:3]),
                    "source": "arXiv",
                }
            )
        return items


class WikipediaAdapter(SourceAdapter):
    """Wikipedia article search and extract."""

    name = "wikipedia"

    def search(self, query: str, limit: int = 3, **kwargs) -> List[Dict[str, Any]]:
        # Search for page titles
        search_url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": limit,
            "format": "json",
        }
        resp = requests.get(
            search_url, params=params, headers=DEFAULT_HEADERS, timeout=DEFAULT_TIMEOUT  # type: ignore[arg-type]
        )
        resp.raise_for_status()
        data = resp.json()
        items = []
        for result in data.get("query", {}).get("search", [])[:limit]:
            title = result.get("title", "")
            snippet = (
                result.get("snippet", "")
                .replace('<span class="searchmatch">', "")
                .replace("</span>", "")
            )
            items.append(
                {
                    "title": title,
                    "url": f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}",
                    "snippet": snippet,
                    "source": "Wikipedia",
                }
            )
        return items


class URLExtractAdapter(SourceAdapter):
    """Fetch and extract text from a URL."""

    name = "url"

    def search(
        self, query: str, limit: int = 1, selector: str = "", **kwargs
    ) -> List[Dict[str, Any]]:
        """query is treated as the URL to fetch."""
        resp = requests.get(query, headers=DEFAULT_HEADERS, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        # Basic text extraction (strip HTML tags)
        import re

        text = re.sub(r"<[^>]+>", " ", resp.text)
        text = re.sub(r"\s+", " ", text).strip()[:2000]
        return [{"title": query, "url": query, "snippet": text, "source": "URL"}]


# ── High-level façade ─────────────────────────────────────────────────────────

_ADAPTERS: Dict[str, SourceAdapter] = {
    "web": WebSearchAdapter(),
    "github": GitHubSearchAdapter(),
    "arxiv": ArxivAdapter(),
    "wikipedia": WikipediaAdapter(),
    "url": URLExtractAdapter(),
}


class DeepResearcher:
    """
    High-level research façade.

    Executes a ResearchPlan step-by-step, aggregates results, and
    produces a structured ResearchReport.
    """

    def __init__(self, github_token: Optional[str] = None):
        self._adapters = dict(_ADAPTERS)
        if github_token:
            self._adapters["github"] = GitHubSearchAdapter(token=github_token)

    def plan(self, topic: str) -> ResearchPlan:
        return ResearchPlan(topic=topic)

    def execute(self, plan: ResearchPlan, verbose: bool = True) -> ResearchReport:
        """Run all steps in the plan and return a ResearchReport."""
        results: List[ResearchResult] = []
        for step in plan.steps:
            adapter = self._adapters.get(step.source)
            if adapter is None:
                results.append(
                    ResearchResult(
                        source=step.source,
                        query=step.query,
                        items=[],
                        error=f"Unknown source '{step.source}'. Available: {list(self._adapters)}",
                    )
                )
                continue
            if verbose:
                console.print(
                    f"[dim]  → Querying [bold]{step.source}[/bold]: {step.query!r}…[/dim]"
                )
            t0 = time.time()
            try:
                items = adapter.search(step.query, limit=step.limit, **step.extra)
                results.append(
                    ResearchResult(
                        source=step.source,
                        query=step.query,
                        items=items,
                        elapsed=time.time() - t0,
                    )
                )
            except Exception as e:
                results.append(
                    ResearchResult(
                        source=step.source,
                        query=step.query,
                        items=[],
                        error=str(e),
                        elapsed=time.time() - t0,
                    )
                )
        return ResearchReport(topic=plan.topic, results=results)

    def quick_search(
        self,
        query: str,
        sources: Optional[List[str]] = None,
        limit: int = 5,
    ) -> ResearchReport:
        """Convenience: build and execute a plan in one call."""
        sources = sources or ["web", "github", "wikipedia"]
        plan = self.plan(query)
        for src in sources:
            plan.add_step(src, query, limit=limit)
        return self.execute(plan)

    # ── Display helpers ───────────────────────────────────────────────────

    def print_report(self, report: ResearchReport) -> None:
        console.print(
            Panel(
                f"[bold]Topic:[/bold]    {report.topic}\n"
                f"[bold]Sources:[/bold]  {report.successful_sources}/{len(report.results)} succeeded\n"
                f"[bold]Results:[/bold]  {report.total_items} items",
                title="[bold cyan]🔬 Research Report[/bold cyan]",
                border_style="cyan",
            )
        )
        for result in report.results:
            if result.error:
                console.print(f"[red]  ✗ {result.source}: {result.error}[/red]")
                continue
            table = Table(
                title=f"{result.source.upper()} — {result.query!r} ({len(result)} results, {result.elapsed:.1f}s)",
                box=box.SIMPLE,
                header_style="bold cyan",
                show_lines=True,
            )
            table.add_column("Title", min_width=30)
            table.add_column("URL / Snippet", min_width=50)
            for item in result.items:
                title = item.get("title", "")[:60]
                url = item.get("url", "")
                snippet = item.get("snippet", "")[:120]
                table.add_row(title, f"[dim]{url}[/dim]\n{snippet}")
            console.print(table)

    def export_json(self, report: ResearchReport, path: str) -> None:
        """Export the report to a JSON file."""
        data = {
            "topic": report.topic,
            "created_at": report.created_at,
            "results": [
                {
                    "source": r.source,
                    "query": r.query,
                    "items": r.items,
                    "error": r.error,
                    "elapsed": r.elapsed,
                }
                for r in report.results
            ],
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        console.print(f"[green]✓ Report exported to {path}[/green]")
