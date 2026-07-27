"""Tests for ghcli issues create / close / reopen / comment commands."""

from __future__ import annotations

import json
from unittest.mock import patch

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


MOCK_ISSUE = {
    "number": 42,
    "title": "Fix the bug",
    "body": "This is a bug report.",
    "state": "open",
    "html_url": "https://github.com/owner/repo/issues/42",
    "user": {"login": "testuser"},
    "labels": [],
    "assignees": [],
    "comments": 0,
    "created_at": "2024-07-27T10:00:00Z",
    "updated_at": "2024-07-27T10:00:00Z",
}


# ── issues create ──────────────────────────────────────────────────────────


def test_issues_create_basic(runner, mock_token):
    """issues create with --title creates an issue and shows number + URL."""
    with patch("ghcli.client.GitHubClient.post", return_value=MOCK_ISSUE):
        result = runner.invoke(
            cli,
            ["issues", "create", "owner/repo", "--title", "Fix the bug"],
        )
    assert result.exit_code == 0
    assert "42" in result.output
    assert "github.com" in result.output or "Issue" in result.output


def test_issues_create_with_body(runner, mock_token):
    """issues create --body passes body to API."""
    with patch("ghcli.client.GitHubClient.post", return_value=MOCK_ISSUE) as mock_post:
        result = runner.invoke(
            cli,
            [
                "issues",
                "create",
                "owner/repo",
                "--title",
                "Fix the bug",
                "--body",
                "Detailed description here",
            ],
        )
    assert result.exit_code == 0
    payload = mock_post.call_args[1].get("json") or mock_post.call_args[0][1]
    assert payload.get("body") == "Detailed description here"


def test_issues_create_with_labels(runner, mock_token):
    """issues create --label passes labels to API."""
    with patch("ghcli.client.GitHubClient.post", return_value=MOCK_ISSUE) as mock_post:
        result = runner.invoke(
            cli,
            [
                "issues",
                "create",
                "owner/repo",
                "--title",
                "Bug",
                "--label",
                "bug",
                "--label",
                "help wanted",
            ],
        )
    assert result.exit_code == 0
    payload = mock_post.call_args[1].get("json") or mock_post.call_args[0][1]
    assert "bug" in payload.get("labels", [])
    assert "help wanted" in payload.get("labels", [])


def test_issues_create_with_assignees(runner, mock_token):
    """issues create --assignee passes assignees to API."""
    with patch("ghcli.client.GitHubClient.post", return_value=MOCK_ISSUE) as mock_post:
        result = runner.invoke(
            cli,
            [
                "issues",
                "create",
                "owner/repo",
                "--title",
                "Task",
                "--assignee",
                "alice",
                "--assignee",
                "bob",
            ],
        )
    assert result.exit_code == 0
    payload = mock_post.call_args[1].get("json") or mock_post.call_args[0][1]
    assert "alice" in payload.get("assignees", [])
    assert "bob" in payload.get("assignees", [])


def test_issues_create_missing_title(runner, mock_token):
    """issues create without --title fails with usage error."""
    result = runner.invoke(cli, ["issues", "create", "owner/repo"])
    assert result.exit_code != 0
    assert "title" in result.output.lower() or "Missing" in result.output


def test_issues_create_api_error(runner, mock_token):
    """issues create shows error on API failure."""
    from ghcli.client import GitHubAPIError

    with patch(
        "ghcli.client.GitHubClient.post",
        side_effect=GitHubAPIError("Validation Failed", 422),
    ):
        result = runner.invoke(
            cli,
            ["issues", "create", "owner/repo", "--title", "Bad issue"],
        )
    assert result.exit_code != 0 or "✗" in result.output


# ── issues close ───────────────────────────────────────────────────────────


def test_issues_close(runner, mock_token):
    """issues close patches state to closed."""
    closed_issue = {**MOCK_ISSUE, "state": "closed"}
    with patch("ghcli.client.GitHubClient.patch", return_value=closed_issue):
        result = runner.invoke(cli, ["issues", "close", "owner/repo", "42"])
    assert result.exit_code == 0
    assert "closed" in result.output.lower() or "42" in result.output


def test_issues_close_with_comment(runner, mock_token):
    """issues close --comment posts a comment before closing."""
    closed_issue = {**MOCK_ISSUE, "state": "closed"}
    with patch("ghcli.client.GitHubClient.post", return_value={"id": 1}) as mock_post:
        with patch("ghcli.client.GitHubClient.patch", return_value=closed_issue):
            result = runner.invoke(
                cli,
                ["issues", "close", "owner/repo", "42", "--comment", "Closing this."],
            )
    assert result.exit_code == 0
    mock_post.assert_called_once()


# ── issues reopen ──────────────────────────────────────────────────────────


def test_issues_reopen(runner, mock_token):
    """issues reopen patches state to open."""
    with patch("ghcli.client.GitHubClient.patch", return_value=MOCK_ISSUE):
        result = runner.invoke(cli, ["issues", "reopen", "owner/repo", "42"])
    assert result.exit_code == 0
    assert "reopen" in result.output.lower() or "42" in result.output


# ── issues comment ─────────────────────────────────────────────────────────


def test_issues_comment(runner, mock_token):
    """issues comment posts a comment to an issue."""
    mock_comment = {
        "id": 55555,
        "html_url": "https://github.com/owner/repo/issues/42#issuecomment-55555",
        "body": "Great work!",
    }
    with patch("ghcli.client.GitHubClient.post", return_value=mock_comment):
        result = runner.invoke(
            cli,
            ["issues", "comment", "owner/repo", "42", "--body", "Great work!"],
        )
    assert result.exit_code == 0
    assert "Comment added" in result.output or "55555" in result.output


# ── help ───────────────────────────────────────────────────────────────────


def test_issues_help(runner):
    """issues --help shows all subcommands."""
    result = runner.invoke(cli, ["issues", "--help"])
    assert result.exit_code == 0
    for sub in ("list", "view", "create", "close", "reopen", "comment"):
        assert sub in result.output
