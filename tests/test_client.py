"""Tests for ghcli.client — caching, retry, pagination, error handling."""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest
import requests

from ghcli.client import (
    GitHubAPIError,
    GitHubClient,
    _CACHE,
    _cache_key,
    clear_cache,
)


@pytest.fixture(autouse=True)
def clear_cache_before_each():
    """Ensure cache is empty before every test."""
    clear_cache()
    yield
    clear_cache()


@pytest.fixture()
def client():
    return GitHubClient(token="ghp_test_token_12345")


class TestCacheKey:
    def test_same_inputs_same_key(self):
        k1 = _cache_key("GET", "https://api.github.com/user", {"per_page": 10})
        k2 = _cache_key("GET", "https://api.github.com/user", {"per_page": 10})
        assert k1 == k2

    def test_different_method_different_key(self):
        k1 = _cache_key("GET", "https://api.github.com/user", {})
        k2 = _cache_key("POST", "https://api.github.com/user", {})
        assert k1 != k2

    def test_different_url_different_key(self):
        k1 = _cache_key("GET", "https://api.github.com/user", {})
        k2 = _cache_key("GET", "https://api.github.com/repos", {})
        assert k1 != k2

    def test_none_params(self):
        k = _cache_key("GET", "https://api.github.com/user", None)
        assert isinstance(k, str)


class TestClearCache:
    def test_clear_empties_cache(self):
        _CACHE["test_key"] = ({"data": 1}, time.time() + 30)
        clear_cache()
        assert len(_CACHE) == 0


class TestGitHubAPIError:
    def test_str_with_status(self):
        err = GitHubAPIError("Not Found", 404)
        assert "404" in str(err)
        assert "Not Found" in str(err)

    def test_str_without_status(self):
        err = GitHubAPIError("Something went wrong")
        assert "Something went wrong" in str(err)

    def test_response_stored(self):
        err = GitHubAPIError("Bad Request", 400, {"message": "Validation Failed"})
        assert err.response == {"message": "Validation Failed"}
        assert err.status_code == 400


class TestGitHubClientInit:
    def test_init_with_token(self):
        c = GitHubClient(token="ghp_abc123")
        assert c._token == "ghp_abc123"

    def test_init_without_token_loads_from_store(self):
        with patch("ghcli.client.load_token", return_value="ghp_from_store"):
            c = GitHubClient()
        assert c._token == "ghp_from_store"

    def test_require_auth_raises_when_no_token(self):
        with patch("ghcli.client.load_token", return_value=None):
            c = GitHubClient(token=None)
        from ghcli.client import GitHubAPIError
        with pytest.raises(GitHubAPIError):
            c.require_auth()

    def test_require_auth_passes_with_token(self):
        c = GitHubClient(token="ghp_test")
        c.require_auth()  # should not raise


class TestGitHubClientGet:
    def test_get_success(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"login": "testuser"}
        mock_resp.headers = {}
        mock_resp.content = b'{"login": "testuser"}'
        mock_resp.ok = True
        with patch("requests.Session.request", return_value=mock_resp):
            result = client.get("/user")
        assert result == {"login": "testuser"}

    def test_get_uses_cache_on_second_call(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"login": "testuser"}
        mock_resp.headers = {}
        mock_resp.content = b'{"login": "testuser"}'
        mock_resp.ok = True
        with patch("requests.Session.request", return_value=mock_resp) as mock_req:
            client.get("/user")
            client.get("/user")
        # Second call should hit cache — only 1 real HTTP request
        assert mock_req.call_count == 1

    def test_get_cache_expires_after_ttl(self, client):
        """Cache should miss after TTL expires."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"login": "testuser"}
        mock_resp.headers = {}
        mock_resp.content = b'{"login": "testuser"}'
        mock_resp.ok = True
        import ghcli.client as client_module
        original_ttl = client_module._CACHE_TTL
        try:
            client_module._CACHE_TTL = 0  # expire immediately
            with patch("requests.Session.request", return_value=mock_resp) as mock_req:
                client.get("/user")
                time.sleep(0.01)
                client.get("/user")
            assert mock_req.call_count == 2
        finally:
            client_module._CACHE_TTL = original_ttl

    def test_get_404_raises_api_error(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.json.return_value = {"message": "Not Found"}
        mock_resp.headers = {}
        mock_resp.content = b'{"message": "Not Found"}'
        mock_resp.ok = False
        with patch("requests.Session.request", return_value=mock_resp):
            with pytest.raises(GitHubAPIError) as exc_info:
                client.get("/repos/owner/nonexistent")
        assert exc_info.value.status_code == 404

    def test_get_401_raises_api_error(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.json.return_value = {"message": "Bad credentials"}
        mock_resp.headers = {}
        mock_resp.content = b'{"message": "Bad credentials"}'
        mock_resp.ok = False
        with patch("requests.Session.request", return_value=mock_resp):
            with pytest.raises(GitHubAPIError) as exc_info:
                client.get("/user")
        assert exc_info.value.status_code == 401

    def test_get_204_returns_none(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_resp.headers = {}
        mock_resp.content = b""
        mock_resp.ok = True
        with patch("requests.Session.request", return_value=mock_resp):
            result = client.get("/some/endpoint")
        assert result is None


class TestGitHubClientPost:
    def test_post_success(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"id": 1, "name": "new-repo"}
        mock_resp.headers = {}
        mock_resp.content = b'{"id": 1}'
        mock_resp.ok = True
        with patch("requests.Session.request", return_value=mock_resp):
            result = client.post("/user/repos", json={"name": "new-repo"})
        assert result["name"] == "new-repo"

    def test_post_422_raises_api_error(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 422
        mock_resp.json.return_value = {"message": "Validation Failed"}
        mock_resp.headers = {}
        mock_resp.content = b'{"message": "Validation Failed"}'
        mock_resp.ok = False
        with patch("requests.Session.request", return_value=mock_resp):
            with pytest.raises(GitHubAPIError) as exc_info:
                client.post("/user/repos", json={"name": ""})
        assert exc_info.value.status_code == 422


class TestGitHubClientDelete:
    def test_delete_success(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_resp.headers = {}
        mock_resp.content = b""
        mock_resp.ok = True
        with patch("requests.Session.request", return_value=mock_resp):
            # delete returns None (no body)
            client.delete("/repos/owner/repo")

    def test_delete_404_raises(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.json.return_value = {"message": "Not Found"}
        mock_resp.headers = {}
        mock_resp.content = b'{"message": "Not Found"}'
        mock_resp.ok = False
        with patch("requests.Session.request", return_value=mock_resp):
            with pytest.raises(GitHubAPIError):
                client.delete("/repos/owner/nonexistent")


class TestGitHubClientPatch:
    def test_patch_success(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": 1, "name": "updated-repo"}
        mock_resp.headers = {}
        mock_resp.content = b'{"id": 1}'
        mock_resp.ok = True
        with patch("requests.Session.request", return_value=mock_resp):
            result = client.patch("/repos/owner/repo", json={"name": "updated-repo"})
        assert result["name"] == "updated-repo"


class TestGitHubClientPaginate:
    def test_paginate_single_page(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{"id": 1}, {"id": 2}]
        mock_resp.headers = {}  # No Link header = single page
        mock_resp.content = b"[...]"
        mock_resp.ok = True
        with patch("requests.Session.request", return_value=mock_resp):
            results = list(client.paginate("/user/repos"))
        assert len(results) == 2

    def test_paginate_max_pages(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{"id": i} for i in range(10)]
        mock_resp.headers = {}
        mock_resp.content = b"[...]"
        mock_resp.ok = True
        with patch("requests.Session.request", return_value=mock_resp):
            results = list(client.paginate("/user/repos", max_pages=1))
        assert len(results) == 10