"""
GitHub REST API client — thin wrapper around `requests` with:
  - Automatic auth header injection
  - Rate-limit awareness (429 / 403 + X-RateLimit-Remaining: 0)
  - Link-header pagination helper
  - Typed GitHubAPIError with status_code
  - delete_with_body() for the Contents DELETE endpoint
  - get_diff() for unified-diff Accept header
"""

from __future__ import annotations

import hashlib
import time
from typing import Any, Generator, Optional

import requests

from ghcli.auth_store import load_token

# ---------------------------------------------------------------------------
# Simple in-process TTL cache
# ---------------------------------------------------------------------------
_CACHE: dict[str, tuple[Any, float]] = {}
_CACHE_TTL = 30  # seconds — GET responses cached for 30s by default


def _cache_key(method: str, url: str, params: dict | None) -> str:
    raw = f"{method}:{url}:{sorted((params or {}).items())}"
    return hashlib.md5(raw.encode(), usedforsecurity=False).hexdigest()  # noqa: S324


def clear_cache() -> None:
    """Clear the in-process response cache."""
    _CACHE.clear()


GITHUB_API = "https://api.github.com"
DEFAULT_TIMEOUT = 20  # seconds
VERSION = "1.0.0"


class GitHubAPIError(Exception):
    """Raised when the GitHub API returns a non-2xx response."""

    def __init__(
        self,
        message: str,
        status_code: int = 0,
        response: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response = response or {}

    def __str__(self) -> str:
        if self.status_code:
            return f"HTTP {self.status_code}: {super().__str__()}"
        return super().__str__()


class GitHubClient:
    """
    Authenticated GitHub REST API client.

    Usage::

        client = GitHubClient()           # reads token from store / env
        client = GitHubClient(token=...) # explicit token override
    """

    def __init__(self, token: Optional[str] = None) -> None:
        self._token: str | None = token or load_token()
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": f"ghcli/{VERSION}",
            }
        )
        if self._token:
            self._session.headers["Authorization"] = f"Bearer {self._token}"

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    def _url(self, path: str) -> str:
        """Prepend the base URL unless path is already absolute."""
        if path.startswith("http"):
            return path
        return f"{GITHUB_API}{path}"

    def _raise_for_status(self, resp: requests.Response) -> None:
        """Parse GitHub error body and raise GitHubAPIError for non-2xx."""
        if resp.ok:
            return
        try:
            body = resp.json()
            message = body.get("message", resp.text)
            errors = body.get("errors", [])
            if errors:
                details = "; ".join(
                    e.get("message", str(e)) if isinstance(e, dict) else str(e) for e in errors
                )
                message = f"{message} — {details}"
        except Exception:
            message = resp.text or resp.reason or "Unknown error"
        raise GitHubAPIError(message, status_code=resp.status_code)

    def _handle_rate_limit(self, resp: requests.Response) -> None:
        """Raise a friendly error when rate-limited."""
        if resp.status_code in (429, 403):
            reset_at = resp.headers.get("X-RateLimit-Reset")
            remaining = resp.headers.get("X-RateLimit-Remaining", "1")
            if remaining == "0" and reset_at:
                wait = max(0, int(reset_at) - int(time.time())) + 1
                reset_time = time.strftime("%H:%M:%S", time.localtime(int(reset_at)))
                raise GitHubAPIError(
                    f"Rate limit exceeded. Resets in {wait}s (at {reset_time}). "
                    "Set GITHUB_TOKEN to a token with higher limits.",
                    status_code=resp.status_code,
                )

    def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        json: Any = None,
        data: Any = None,
        extra_headers: dict | None = None,
    ) -> requests.Response:
        url = self._url(path)
        headers: dict = {}
        if extra_headers:
            headers.update(extra_headers)
        # Check cache for GET requests
        cache_key = _cache_key(method, url, params) if method == "GET" else None
        if cache_key:
            cached = _CACHE.get(cache_key)
            if cached and time.time() - cached[1] < _CACHE_TTL:
                # Return a mock response-like object from cache
                class _CachedResp:
                    ok = True
                    status_code = 200
                    content = b"cached"
                    headers: dict = {}

                    def json(self_inner):
                        return cached[0]

                    def text(self_inner):
                        return str(cached[0])

                return _CachedResp()

        # Retry with exponential backoff
        max_retries = 3
        backoff = 1.0
        last_exc: Exception | None = None
        for attempt in range(max_retries):
            try:
                resp = self._session.request(
                    method,
                    url,
                    params=params,
                    json=json,
                    data=data,
                    headers=headers if headers else None,
                    timeout=DEFAULT_TIMEOUT,
                )
                self._handle_rate_limit(resp)
                self._raise_for_status(resp)
                # Store in cache for GET
                if cache_key and resp.ok and resp.content:
                    try:
                        _CACHE[cache_key] = (resp.json(), time.time())
                    except Exception:
                        pass
                return resp
            except GitHubAPIError as e:
                if e.status_code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                    time.sleep(backoff)
                    backoff *= 2
                    last_exc = e
                    continue
                raise
            except requests.exceptions.ConnectionError as e:
                if attempt < max_retries - 1:
                    time.sleep(backoff)
                    backoff *= 2
                    last_exc = e
                    continue
                raise
        raise last_exc  # type: ignore

    # ------------------------------------------------------------------
    # Public CRUD methods
    # ------------------------------------------------------------------

    def get(self, path: str, params: dict | None = None) -> Any:
        resp = self._request("GET", path, params=params)
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    def post(self, path: str, json: Any = None) -> Any:
        resp = self._request("POST", path, json=json)
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    def patch(self, path: str, json: Any = None) -> Any:
        resp = self._request("PATCH", path, json=json)
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    def put(self, path: str, json: Any = None) -> Any:
        resp = self._request("PUT", path, json=json)
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    def delete(self, path: str) -> None:
        """DELETE without a request body (e.g. delete a repo)."""
        self._request("DELETE", path)

    def delete_with_body(self, path: str, json: Any = None) -> Any:
        """
        DELETE with a JSON request body.

        Required by the GitHub Contents API
        (DELETE /repos/{owner}/{repo}/contents/{path})
        which needs ``{"message": "...", "sha": "..."}`` in the body.
        """
        resp = self._request("DELETE", path, json=json)
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    # ------------------------------------------------------------------
    # Pagination helper
    # ------------------------------------------------------------------

    def paginate(
        self,
        path: str,
        params: dict | None = None,
        max_pages: int = 10,
    ) -> Generator[Any, None, None]:
        """
        Yield items from a paginated GitHub endpoint.

        Follows ``Link: <url>; rel="next"`` headers automatically.
        Stops after *max_pages* pages to prevent runaway requests.
        """
        params = dict(params or {})
        params.setdefault("per_page", 100)
        url: str | None = self._url(path)
        pages = 0

        while url and pages < max_pages:
            resp = self._request("GET", url, params=params if pages == 0 else None)
            data = resp.json()
            if isinstance(data, list):
                yield from data
            elif isinstance(data, dict):
                # Some endpoints wrap items (e.g. search results)
                items = data.get("items") or data.get("workflows") or data.get("jobs")
                if items is not None:
                    yield from items
                else:
                    yield data

            pages += 1

            # Parse Link header for next page URL
            link_header = resp.headers.get("Link", "")
            url = None
            for part in link_header.split(","):
                part = part.strip()
                if 'rel="next"' in part:
                    url = part.split(";")[0].strip().strip("<>")
                    break

    # ------------------------------------------------------------------
    # Auth helper
    # ------------------------------------------------------------------

    def require_auth(self) -> None:
        """Raise a friendly error if no token is configured."""
        if not self._token:
            raise GitHubAPIError(
                "Not authenticated. Run [bold]ghcli auth setup[/bold] first.\n"
                "Or set the GITHUB_TOKEN environment variable.",
                status_code=401,
            )

    # ------------------------------------------------------------------
    # Diff helper (uses a different Accept header)
    # ------------------------------------------------------------------

    def get_diff(self, path: str) -> str:
        """Fetch a unified diff from a GitHub endpoint (PR or commit)."""
        resp = self._request(
            "GET",
            path,
            extra_headers={"Accept": "application/vnd.github.v3.diff"},
        )
        return resp.text
