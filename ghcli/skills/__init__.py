"""
ghcli skills — Pluggable capability modules for the GitHub CLI.

Available skills:
  mcp_connector    — Model Context Protocol client/server scaffolding
  agent_browser    — Autonomous web navigation (Playwright / Selenium)
  debugger         — Systematic multi-phase root cause analysis
  deep_research    — Multi-step search & data extraction
  brainstorm_prd   — Interactive PRD generation workflow
  tdd              — Test-Driven Development red-green-refactor loop
  parallel_dispatch — Asyncio/multiprocessing parallel agent dispatcher
"""

from ghcli.skills.mcp_connector import MCPConnector
from ghcli.skills.agent_browser import AgentBrowser
from ghcli.skills.debugger import Debugger
from ghcli.skills.deep_research import DeepResearcher
from ghcli.skills.brainstorm_prd import BrainstormPRD
from ghcli.skills.tdd import TDDRunner
from ghcli.skills.parallel_dispatch import ParallelDispatcher

__all__ = [
    "MCPConnector",
    "AgentBrowser",
    "Debugger",
    "DeepResearcher",
    "BrainstormPRD",
    "TDDRunner",
    "ParallelDispatcher",
]
