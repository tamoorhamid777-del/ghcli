"""Tests for ghcli comments command."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from ghcli.main import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_token():
    with patch("ghcli.auth_store.load_token", return_value="ghp_test_token"):
        yield


# ── comments create ────────────────────────────────────────────────────────


def test_comments_create_success(runner, mock_token):
    """comments create posts a comment and shows the URL."""
    mock_comment = {
        "id": 999001,
        "html_url": "https://github.com/owner/repo/issues/42#issuecomment-999001",
        "body": "Looks good!",
        "user": {"login": "testuser"},
        "created_at": "2024-07-27T10:00:00Z",
    }
    with patch("ghcli.client.GitHubClient.post", return_value=mock_comment):
        result = runner.invoke(
            cli,
            ["comments", "create", "owner/repo", "42", "--body", "Looks good!"],
        )
    assert result.exit_code == 0
    assert "Comment added" in result.output or "999001" in result.output


def test_comments_create_json(runner, mock_token):
    """comments create --json outputs raw JSON."""
    mock_comment = {
        "id": 999002,
        "html_url": "https://github.com/owner/repo/issues/1#issuecomment-999002",
        "body": "Test",
        "user": {"login": "testuser"},
        "created_at": "2024-07-27T10:00:00Z",
    }
    with patch("ghcli.client.GitHubClient.post", return_value=mock_comment):
        result = runner.invoke(
            cli,
            ["comments", "create", "owner/repo", "1", "--body", "Test", "--json"],
        )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["id"] == 999002


def test_comments_create_api_error(runner, mock_token):
    """comments create shows error on API failure."""
    from ghcli.client import GitHubAPIError
    with patch(
        "ghcli.client.GitHubClient.post",
        side_effect=GitHubAPIError("Not Found", 404),
    ):
        result = runner.invoke(
            cli,
            ["comments", "create", "owner/repo", "99", "--body", "hi"],
        )
    assert result.exit_code != 0 or "✗" in result.output or "Not Found" in result.output


# ── comments list ──────────────────────────────────────────────────────────


def test_comments_list_success(runner, mock_token):
    """comments list shows a table of comments."""
    mock_comments = [
        {
            "id": 1001,
            "body": "First comment",
            "user": {"login": "alice"},
            "created_at": "2024-07-01T00:00:00Z",
            "html_url": "https://github.com/owner/repo/issues/5#issuecomment-1001",
        },
        {
            "id": 1002,
            "body": "Second comment",
            "user": {"login": "bob"},
            "created_at": "2024-07-02T00:00:00Z",
            "html_url": "https://github.com/owner/repo/issues/5#issuecomment-1002",
        },
    ]
    with patch("ghcli.client.GitHubClient._request") as mock_req:
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.content = b"data"
        mock_resp.json.return_value = mock_comments
        mock_resp.headers = {}
        mock_req.return_value = mock_resp
        result = runner.invoke(cli, ["comments", "list", "owner/repo", "5"])
    assert result.exit_code == 0
    assert "alice" in result.output or "First comment" in result.output or "1001" in result.output


def test_comments_list_json(runner, mock_token):
    """comments list --json outputs raw JSON."""
    mock_comments = [
        {
            "id": 2001,
            "body": "JSON comment",
            "user": {"login": "carol"},
            "created_at": "2024-07-01T00:00:00Z",
            "html_url": "https://github.com/owner/repo/issues/7#issuecomment-2001",
        }
    ]
    with patch("ghcli.client.GitHubClient._request") as mock_req:
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.content = b"data"
        mock_resp.json.return_value = mock_comments
        mock_resp.headers = {}
        mock_req.return_value = mock_resp
        result = runner.invoke(cli, ["comments", "list", "owner/repo", "7", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert data[0]["id"] == 2001


def test_comments_list_empty(runner, mock_token):
    """comments list shows friendly message when no comments."""
    with patch("ghcli.client.GitHubClient._request") as mock_req:
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.content = b"[]"
        mock_resp.json.return_value = []
        mock_resp.headers = {}
        mock_req.return_value = mock_resp
        result = runner.invoke(cli, ["comments", "list", "owner/repo", "99"])
    assert result.exit_code == 0
    assert "No comments" in result.output


# ── comments delete ────────────────────────────────────────────────────────


def test_comments_delete_with_yes(runner, mock_token):
    """comments delete --yes skips confirmation and deletes."""
    with patch("ghcli.client.GitHubClient.delete", return_value=None):
        result = runner.invoke(
            cli,
            ["comments", "delete", "owner/repo", "999001", "--yes"],
        )
    assert result.exit_code == 0
    assert "deleted" in result.output.lower() or "999001" in result.output


def test_comments_delete_abort(runner, mock_token):
    """comments delete aborts when user says no."""
    with patch("ghcli.client.GitHubClient.delete", return_value=None):
        result = runner.invoke(
            cli,
            ["comments", "delete", "owner/repo", "999001"],
            input="n\n",
        )
    # Should abort without deleting
    assert result.exit_code != 0 or "Aborted" in result.output or "abort" in result.output.lower()


# ── help ───────────────────────────────────────────────────────────────────


def test_comments_help(runner):
    """comments --help shows subcommands."""
    result = runner.invoke(cli, ["comments", "--help"])
    assert result.exit_code == 0
    assert "create" in result.output
    assert "list" in result.output
    assert "delete" in result.output
