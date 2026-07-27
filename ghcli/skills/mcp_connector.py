"""
ghcli skills.mcp_connector
===========================
Model Context Protocol (MCP) client/server scaffolding.

Provides a clean interface for the CLI to connect to external MCP tool
providers (file systems, databases, web APIs, custom tool servers) using
the JSON-RPC 2.0 transport that MCP specifies.

Architecture
------------
  MCPConnector          — high-level façade used by CLI commands
  MCPTransport          — low-level JSON-RPC 2.0 over stdio / HTTP
  MCPServerConfig       — dataclass describing a registered server
  MCPToolResult         — typed result returned from a tool call
  MCPRegistry           — persists server configs in ~/.ghcli/mcp.json

Usage (programmatic)
--------------------
    from ghcli.skills.mcp_connector import MCPConnector

    conn = MCPConnector()
    conn.register("filesystem", transport="stdio",
                  command=["npx", "-y", "@modelcontextprotocol/server-filesystem", "/tmp"])
    result = conn.call_tool("filesystem", "read_file", {"path": "/tmp/hello.txt"})
    print(result.content)

Usage (CLI)
-----------
    ghcli skills mcp register --name filesystem --transport stdio \
        --command "npx -y @modelcontextprotocol/server-filesystem /tmp"
    ghcli skills mcp list
    ghcli skills mcp call filesystem read_file --arg path=/tmp/hello.txt
    ghcli skills mcp remove filesystem
"""

from __future__ import annotations

import json
import subprocess
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

# ── Persistence ──────────────────────────────────────────────────────────────

MCP_CONFIG_PATH = Path.home() / ".ghcli" / "mcp.json"


def _load_registry() -> Dict[str, dict]:
    if MCP_CONFIG_PATH.exists():
        try:
            return json.loads(MCP_CONFIG_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_registry(data: Dict[str, dict]) -> None:
    MCP_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    MCP_CONFIG_PATH.write_text(json.dumps(data, indent=2))
    MCP_CONFIG_PATH.chmod(0o600)


# ── Data classes ─────────────────────────────────────────────────────────────


@dataclass
class MCPServerConfig:
    name: str
    transport: str  # "stdio" | "http" | "sse"
    command: List[str] = field(default_factory=list)  # for stdio
    url: str = ""  # for http/sse
    env: Dict[str, str] = field(default_factory=dict)
    timeout: int = 30
    description: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "MCPServerConfig":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class MCPToolResult:
    tool: str
    server: str
    content: Any
    is_error: bool = False
    raw: dict = field(default_factory=dict)

    def __str__(self) -> str:
        if self.is_error:
            return f"[ERROR] {self.tool}@{self.server}: {self.content}"
        if isinstance(self.content, (dict, list)):
            return json.dumps(self.content, indent=2)
        return str(self.content)


# ── Transport layer ───────────────────────────────────────────────────────────


class MCPTransport:
    """
    Thin JSON-RPC 2.0 transport.

    Supports:
      - stdio  : spawns a subprocess, writes to stdin, reads from stdout
      - http   : POST to an HTTP endpoint
      - sse    : Server-Sent Events (read-only; writes via HTTP POST)
    """

    def __init__(self, config: MCPServerConfig):
        self.config = config
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()

    # ── stdio ─────────────────────────────────────────────────────────────

    def _ensure_proc(self) -> subprocess.Popen:
        if self._proc is None or self._proc.poll() is not None:
            import os

            env = {**os.environ, **self.config.env}
            self._proc = subprocess.Popen(
                self.config.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
                bufsize=1,
            )
            # MCP servers send an "initialize" notification on startup; drain it
            self._initialize_stdio()
        return self._proc

    def _initialize_stdio(self) -> None:
        """Send MCP initialize request and drain the response."""
        init_req = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "ghcli", "version": "2.0.0"},
            },
        }
        self._send_stdio(init_req)
        # Send initialized notification
        notif = {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
        assert self._proc and self._proc.stdin
        self._proc.stdin.write(json.dumps(notif) + "\n")
        self._proc.stdin.flush()

    def _send_stdio(self, payload: dict) -> dict:
        proc = self._ensure_proc()
        assert proc.stdin and proc.stdout
        with self._lock:
            proc.stdin.write(json.dumps(payload) + "\n")
            proc.stdin.flush()
            deadline = time.time() + self.config.timeout
            while time.time() < deadline:
                line = proc.stdout.readline()
                if not line:
                    time.sleep(0.05)
                    continue
                try:
                    resp = json.loads(line.strip())
                    if resp.get("id") == payload.get("id"):
                        return resp
                except json.JSONDecodeError:
                    continue
        raise TimeoutError(
            f"MCP stdio server '{self.config.name}' did not respond in {self.config.timeout}s"
        )

    # ── http ──────────────────────────────────────────────────────────────

    def _send_http(self, payload: dict) -> dict:
        resp = requests.post(
            self.config.url,
            json=payload,
            timeout=self.config.timeout,
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        return resp.json()

    # ── public ────────────────────────────────────────────────────────────

    def send(self, method: str, params: dict) -> dict:
        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": method,
            "params": params,
        }
        if self.config.transport == "stdio":
            return self._send_stdio(payload)
        elif self.config.transport in ("http", "sse"):
            return self._send_http(payload)
        else:
            raise ValueError(f"Unknown transport: {self.config.transport!r}")

    def close(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None


# ── High-level connector ──────────────────────────────────────────────────────


class MCPConnector:
    """
    High-level MCP façade.

    Manages a registry of named MCP servers and provides:
      - register / remove / list servers
      - list_tools(server)  → list of available tool names + schemas
      - call_tool(server, tool, args) → MCPToolResult
      - call_resource(server, uri) → raw resource content
    """

    def __init__(self):
        self._registry: Dict[str, MCPServerConfig] = {
            name: MCPServerConfig.from_dict(d) for name, d in _load_registry().items()
        }
        self._transports: Dict[str, MCPTransport] = {}

    # ── Registry management ───────────────────────────────────────────────

    def register(
        self,
        name: str,
        transport: str = "stdio",
        command: Optional[List[str]] = None,
        url: str = "",
        env: Optional[Dict[str, str]] = None,
        timeout: int = 30,
        description: str = "",
    ) -> MCPServerConfig:
        """Register a new MCP server and persist it."""
        cfg = MCPServerConfig(
            name=name,
            transport=transport,
            command=command or [],
            url=url,
            env=env or {},
            timeout=timeout,
            description=description,
        )
        self._registry[name] = cfg
        raw = _load_registry()
        raw[name] = cfg.to_dict()
        _save_registry(raw)
        return cfg

    def remove(self, name: str) -> bool:
        """Unregister a server. Returns True if it existed."""
        if name not in self._registry:
            return False
        del self._registry[name]
        if name in self._transports:
            self._transports[name].close()
            del self._transports[name]
        raw = _load_registry()
        raw.pop(name, None)
        _save_registry(raw)
        return True

    def list_servers(self) -> List[MCPServerConfig]:
        return list(self._registry.values())

    def get_server(self, name: str) -> MCPServerConfig:
        if name not in self._registry:
            raise KeyError(
                f"MCP server '{name}' not registered. Run: ghcli skills mcp register --name {name}"
            )
        return self._registry[name]

    # ── Transport management ──────────────────────────────────────────────

    def _transport(self, name: str) -> MCPTransport:
        if name not in self._transports:
            cfg = self.get_server(name)
            self._transports[name] = MCPTransport(cfg)
        return self._transports[name]

    # ── MCP operations ────────────────────────────────────────────────────

    def list_tools(self, server: str) -> List[dict]:
        """Return the list of tools advertised by the server."""
        resp = self._transport(server).send("tools/list", {})
        return resp.get("result", {}).get("tools", [])

    def call_tool(self, server: str, tool: str, args: Dict[str, Any]) -> MCPToolResult:
        """
        Invoke a tool on the named MCP server.

        Returns an MCPToolResult with .content and .is_error.
        """
        resp = self._transport(server).send(
            "tools/call",
            {"name": tool, "arguments": args},
        )
        result = resp.get("result", {})
        error = resp.get("error")
        if error:
            return MCPToolResult(
                tool=tool,
                server=server,
                content=error.get("message", str(error)),
                is_error=True,
                raw=resp,
            )
        # MCP result.content is a list of content blocks
        content_blocks = result.get("content", [])
        text_parts = [b.get("text", "") for b in content_blocks if b.get("type") == "text"]
        content = "\n".join(text_parts) if text_parts else result
        return MCPToolResult(
            tool=tool,
            server=server,
            content=content,
            is_error=result.get("isError", False),
            raw=resp,
        )

    def call_resource(self, server: str, uri: str) -> Any:
        """Read a resource URI from the server."""
        resp = self._transport(server).send("resources/read", {"uri": uri})
        return resp.get("result", {})

    def list_resources(self, server: str) -> List[dict]:
        resp = self._transport(server).send("resources/list", {})
        return resp.get("result", {}).get("resources", [])

    def close_all(self) -> None:
        for t in self._transports.values():
            t.close()
        self._transports.clear()

    # ── Rich display helpers ──────────────────────────────────────────────

    def print_servers(self) -> None:
        servers = self.list_servers()
        if not servers:
            console.print(
                "[yellow]No MCP servers registered.[/yellow]  "
                "Run [bold]ghcli skills mcp register[/bold] to add one."
            )
            return
        table = Table(
            title="Registered MCP Servers",
            box=box.ROUNDED,
            border_style="cyan",
            header_style="bold cyan",
        )
        table.add_column("Name", style="bold")
        table.add_column("Transport", width=10)
        table.add_column("Command / URL", min_width=40)
        table.add_column("Description")
        for s in servers:
            cmd_or_url = " ".join(s.command) if s.transport == "stdio" else s.url
            table.add_row(s.name, s.transport, cmd_or_url, s.description or "—")
        console.print(table)

    def print_tools(self, server: str) -> None:
        tools = self.list_tools(server)
        if not tools:
            console.print(f"[yellow]No tools found on server '{server}'.[/yellow]")
            return
        table = Table(
            title=f"Tools on '{server}'",
            box=box.ROUNDED,
            border_style="cyan",
            header_style="bold cyan",
        )
        table.add_column("Tool name", style="bold")
        table.add_column("Description")
        for t in tools:
            table.add_row(t.get("name", "?"), t.get("description", "—"))
        console.print(table)

    def print_result(self, result: MCPToolResult) -> None:
        style = "red" if result.is_error else "green"
        title = (
            f"[bold {style}]{'ERROR' if result.is_error else 'RESULT'}[/bold {style}]"
            f" — {result.tool}@{result.server}"
        )
        console.print(Panel(str(result), title=title, border_style=style))
