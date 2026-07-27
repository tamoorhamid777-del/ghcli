"""
ghcli skills.agent_browser
===========================
Autonomous web navigation — clicks, form fills, screenshots, and data
extraction from live web applications.

Supports two backends (auto-detected at runtime):
  1. Playwright  (preferred) — async, fast, modern
  2. Selenium    (fallback)  — classic, widely available

Architecture
------------
  AgentBrowser          — high-level façade used by CLI commands
  BrowserBackend        — abstract base for Playwright / Selenium adapters
  PlaywrightBackend     — Playwright implementation
  SeleniumBackend       — Selenium implementation
  BrowserAction         — dataclass describing a recorded action
  BrowserSession        — context manager wrapping a browser lifecycle

Usage (programmatic)
--------------------
    from ghcli.skills.agent_browser import AgentBrowser

    browser = AgentBrowser()
    with browser.session() as page:
        page.navigate("https://github.com/login")
        page.fill("#login_field", "myuser")
        page.fill("#password", "mypass")
        page.click('[name="commit"]')
        page.wait_for_selector(".header-user-avatar")
        snap = page.snapshot()          # returns HTML source
        shot = page.screenshot()        # returns PNG bytes path
        data = page.extract_text("h1")  # CSS selector → text

Usage (CLI)
-----------
    ghcli skills browser navigate https://github.com
    ghcli skills browser screenshot https://github.com --out /tmp/gh.png
    ghcli skills browser fill https://example.com/form \
        --field "#name=Alice" --field "#email=alice@example.com" \
        --submit "#submit-btn"
    ghcli skills browser extract https://github.com --selector "h1"
"""

from __future__ import annotations

import abc
import base64
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

# ── Action log ────────────────────────────────────────────────────────────────

@dataclass
class BrowserAction:
    action: str          # navigate | click | fill | wait | screenshot | extract
    target: str = ""     # URL or CSS selector
    value: str = ""      # fill value or empty
    timestamp: float = field(default_factory=time.time)
    success: bool = True
    error: str = ""

    def __str__(self) -> str:
        status = "✓" if self.success else "✗"
        parts = [f"[{status}] {self.action}"]
        if self.target:
            parts.append(f"  target={self.target!r}")
        if self.value:
            parts.append(f"  value={self.value!r}")
        if self.error:
            parts.append(f"  error={self.error!r}")
        return "  ".join(parts)


# ── Abstract backend ──────────────────────────────────────────────────────────

class BrowserBackend(abc.ABC):
    """Abstract interface that both Playwright and Selenium adapters implement."""

    @abc.abstractmethod
    def start(self, headless: bool = True) -> None: ...

    @abc.abstractmethod
    def stop(self) -> None: ...

    @abc.abstractmethod
    def navigate(self, url: str) -> None: ...

    @abc.abstractmethod
    def click(self, selector: str) -> None: ...

    @abc.abstractmethod
    def fill(self, selector: str, value: str) -> None: ...

    @abc.abstractmethod
    def wait_for_selector(self, selector: str, timeout: float = 10.0) -> None: ...

    @abc.abstractmethod
    def wait_for_navigation(self, timeout: float = 15.0) -> None: ...

    @abc.abstractmethod
    def snapshot(self) -> str:
        """Return the current page HTML source."""
        ...

    @abc.abstractmethod
    def screenshot(self, path: Optional[str] = None) -> str:
        """Save a PNG screenshot; return the file path."""
        ...

    @abc.abstractmethod
    def extract_text(self, selector: str) -> List[str]:
        """Return text content of all elements matching selector."""
        ...

    @abc.abstractmethod
    def extract_attribute(self, selector: str, attribute: str) -> List[str]: ...

    @abc.abstractmethod
    def evaluate(self, script: str) -> Any:
        """Execute JavaScript and return the result."""
        ...

    @abc.abstractmethod
    def current_url(self) -> str: ...

    @abc.abstractmethod
    def title(self) -> str: ...


# ── Playwright backend ────────────────────────────────────────────────────────

class PlaywrightBackend(BrowserBackend):
    """Playwright-based browser backend (async API wrapped synchronously)."""

    def __init__(self):
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None

    def start(self, headless: bool = True) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise RuntimeError(
                "Playwright not installed. Run: pip install playwright && playwright install chromium"
            )
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=headless)
        self._context = self._browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        self._page = self._context.new_page()

    def stop(self) -> None:
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()

    def navigate(self, url: str) -> None:
        assert self._page
        self._page.goto(url, wait_until="domcontentloaded", timeout=30_000)

    def click(self, selector: str) -> None:
        assert self._page
        self._page.click(selector, timeout=10_000)

    def fill(self, selector: str, value: str) -> None:
        assert self._page
        self._page.fill(selector, value, timeout=10_000)

    def wait_for_selector(self, selector: str, timeout: float = 10.0) -> None:
        assert self._page
        self._page.wait_for_selector(selector, timeout=int(timeout * 1000))

    def wait_for_navigation(self, timeout: float = 15.0) -> None:
        assert self._page
        self._page.wait_for_load_state("networkidle", timeout=int(timeout * 1000))

    def snapshot(self) -> str:
        assert self._page
        return self._page.content()

    def screenshot(self, path: Optional[str] = None) -> str:
        assert self._page
        if path is None:
            path = f"/tmp/ghcli_screenshot_{int(time.time())}.png"
        self._page.screenshot(path=path, full_page=True)
        return path

    def extract_text(self, selector: str) -> List[str]:
        assert self._page
        elements = self._page.query_selector_all(selector)
        return [el.inner_text() for el in elements]

    def extract_attribute(self, selector: str, attribute: str) -> List[str]:
        assert self._page
        elements = self._page.query_selector_all(selector)
        return [el.get_attribute(attribute) or "" for el in elements]

    def evaluate(self, script: str) -> Any:
        assert self._page
        return self._page.evaluate(script)

    def current_url(self) -> str:
        assert self._page
        return self._page.url

    def title(self) -> str:
        assert self._page
        return self._page.title()


# ── Selenium backend ──────────────────────────────────────────────────────────

class SeleniumBackend(BrowserBackend):
    """Selenium WebDriver backend (Chrome/Chromium)."""

    def __init__(self):
        self._driver = None

    def start(self, headless: bool = True) -> None:
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
        except ImportError:
            raise RuntimeError(
                "Selenium not installed. Run: pip install selenium"
            )
        opts = Options()
        if headless:
            opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--window-size=1280,800")
        self._driver = webdriver.Chrome(options=opts)

    def stop(self) -> None:
        if self._driver:
            self._driver.quit()

    def navigate(self, url: str) -> None:
        assert self._driver
        self._driver.get(url)

    def click(self, selector: str) -> None:
        from selenium.webdriver.common.by import By
        assert self._driver
        self._driver.find_element(By.CSS_SELECTOR, selector).click()

    def fill(self, selector: str, value: str) -> None:
        from selenium.webdriver.common.by import By
        assert self._driver
        el = self._driver.find_element(By.CSS_SELECTOR, selector)
        el.clear()
        el.send_keys(value)

    def wait_for_selector(self, selector: str, timeout: float = 10.0) -> None:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        assert self._driver
        WebDriverWait(self._driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )

    def wait_for_navigation(self, timeout: float = 15.0) -> None:
        time.sleep(1.5)  # Selenium has no built-in networkidle; simple sleep

    def snapshot(self) -> str:
        assert self._driver
        return self._driver.page_source

    def screenshot(self, path: Optional[str] = None) -> str:
        assert self._driver
        if path is None:
            path = f"/tmp/ghcli_screenshot_{int(time.time())}.png"
        self._driver.save_screenshot(path)
        return path

    def extract_text(self, selector: str) -> List[str]:
        from selenium.webdriver.common.by import By
        assert self._driver
        return [el.text for el in self._driver.find_elements(By.CSS_SELECTOR, selector)]

    def extract_attribute(self, selector: str, attribute: str) -> List[str]:
        from selenium.webdriver.common.by import By
        assert self._driver
        return [
            el.get_attribute(attribute) or ""
            for el in self._driver.find_elements(By.CSS_SELECTOR, selector)
        ]

    def evaluate(self, script: str) -> Any:
        assert self._driver
        return self._driver.execute_script(script)

    def current_url(self) -> str:
        assert self._driver
        return self._driver.current_url

    def title(self) -> str:
        assert self._driver
        return self._driver.title


# ── Session context manager ───────────────────────────────────────────────────

class BrowserSession:
    """
    Wraps a BrowserBackend lifecycle and records all actions.

    Use as a context manager:
        with AgentBrowser().session() as page:
            page.navigate("https://example.com")
    """

    def __init__(self, backend: BrowserBackend, headless: bool = True):
        self._backend = backend
        self._headless = headless
        self.actions: List[BrowserAction] = []

    def _record(self, action: str, target: str = "", value: str = "",
                success: bool = True, error: str = "") -> None:
        self.actions.append(BrowserAction(action, target, value, success=success, error=error))

    def navigate(self, url: str) -> "BrowserSession":
        try:
            self._backend.navigate(url)
            self._record("navigate", target=url)
        except Exception as e:
            self._record("navigate", target=url, success=False, error=str(e))
            raise
        return self

    def click(self, selector: str) -> "BrowserSession":
        try:
            self._backend.click(selector)
            self._record("click", target=selector)
        except Exception as e:
            self._record("click", target=selector, success=False, error=str(e))
            raise
        return self

    def fill(self, selector: str, value: str) -> "BrowserSession":
        try:
            self._backend.fill(selector, value)
            self._record("fill", target=selector, value=value)
        except Exception as e:
            self._record("fill", target=selector, value=value, success=False, error=str(e))
            raise
        return self

    def wait_for_selector(self, selector: str, timeout: float = 10.0) -> "BrowserSession":
        self._backend.wait_for_selector(selector, timeout)
        self._record("wait", target=selector)
        return self

    def wait_for_navigation(self, timeout: float = 15.0) -> "BrowserSession":
        self._backend.wait_for_navigation(timeout)
        self._record("wait_nav")
        return self

    def snapshot(self) -> str:
        html = self._backend.snapshot()
        self._record("snapshot")
        return html

    def screenshot(self, path: Optional[str] = None) -> str:
        shot_path = self._backend.screenshot(path)
        self._record("screenshot", target=shot_path)
        return shot_path

    def extract_text(self, selector: str) -> List[str]:
        texts = self._backend.extract_text(selector)
        self._record("extract", target=selector, value=f"{len(texts)} elements")
        return texts

    def extract_attribute(self, selector: str, attribute: str) -> List[str]:
        return self._backend.extract_attribute(selector, attribute)

    def evaluate(self, script: str) -> Any:
        return self._backend.evaluate(script)

    def current_url(self) -> str:
        return self._backend.current_url()

    def title(self) -> str:
        return self._backend.title()

    def print_action_log(self) -> None:
        console.print(Panel(
            "\n".join(str(a) for a in self.actions),
            title="[bold cyan]Browser Action Log[/bold cyan]",
            border_style="cyan",
        ))

    def __enter__(self) -> "BrowserSession":
        self._backend.start(headless=self._headless)
        return self

    def __exit__(self, *_) -> None:
        self._backend.stop()


# ── High-level façade ─────────────────────────────────────────────────────────

class AgentBrowser:
    """
    High-level browser automation façade.

    Auto-selects Playwright (preferred) or Selenium (fallback).
    """

    def __init__(self, backend: Optional[str] = None, headless: bool = True):
        """
        Args:
            backend:  "playwright" | "selenium" | None (auto-detect)
            headless: Run without a visible window (default True)
        """
        self._headless = headless
        self._backend_name = backend or self._detect_backend()

    @staticmethod
    def _detect_backend() -> str:
        try:
            import playwright  # noqa: F401
            return "playwright"
        except ImportError:
            pass
        try:
            import selenium  # noqa: F401
            return "selenium"
        except ImportError:
            pass
        raise RuntimeError(
            "No browser backend found.\n"
            "Install Playwright:  pip install playwright && playwright install chromium\n"
            "  OR\n"
            "Install Selenium:    pip install selenium"
        )

    def _make_backend(self) -> BrowserBackend:
        if self._backend_name == "playwright":
            return PlaywrightBackend()
        elif self._backend_name == "selenium":
            return SeleniumBackend()
        raise ValueError(f"Unknown backend: {self._backend_name!r}")

    @contextmanager
    def session(self) -> Generator[BrowserSession, None, None]:
        """Context manager that yields a BrowserSession."""
        backend = self._make_backend()
        sess = BrowserSession(backend, headless=self._headless)
        with sess:
            yield sess

    # ── Convenience one-shot methods ──────────────────────────────────────

    def navigate_and_screenshot(self, url: str, out: Optional[str] = None) -> str:
        """Navigate to URL, take a screenshot, return the file path."""
        with self.session() as page:
            page.navigate(url)
            page.wait_for_navigation()
            path = page.screenshot(out)
        console.print(f"[green]✓ Screenshot saved:[/green] {path}")
        return path

    def extract(self, url: str, selector: str) -> List[str]:
        """Navigate to URL and extract text from all elements matching selector."""
        with self.session() as page:
            page.navigate(url)
            page.wait_for_navigation()
            texts = page.extract_text(selector)
        return texts

    def fill_and_submit(
        self,
        url: str,
        fields: Dict[str, str],
        submit_selector: str,
        wait_after: Optional[str] = None,
    ) -> str:
        """
        Navigate to URL, fill form fields, click submit, return page HTML.

        Args:
            url:             Page URL
            fields:          {css_selector: value} mapping
            submit_selector: CSS selector of the submit button
            wait_after:      Optional CSS selector to wait for after submit
        """
        with self.session() as page:
            page.navigate(url)
            for selector, value in fields.items():
                page.fill(selector, value)
            page.click(submit_selector)
            if wait_after:
                page.wait_for_selector(wait_after)
            else:
                page.wait_for_navigation()
            html = page.snapshot()
        return html

    def run_script(self, url: str, script: str) -> Any:
        """Navigate to URL and execute JavaScript, returning the result."""
        with self.session() as page:
            page.navigate(url)
            page.wait_for_navigation()
            result = page.evaluate(script)
        return result

    def print_backend_info(self) -> None:
        console.print(Panel(
            f"Backend: [bold cyan]{self._backend_name}[/bold cyan]\n"
            f"Headless: [bold]{'yes' if self._headless else 'no'}[/bold]",
            title="[bold cyan]AgentBrowser[/bold cyan]",
            border_style="cyan",
        ))
