"""Tests for ghcli prs create / merge / close commands."""

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


MOCK_PR = {
    "number": 7,
    "title": "Add new feature",
    "body": "This PR adds a new feature.",
    "state": "open",
    "html_url": "https://github.com/owner/repo/pull/7",
    "user": {"login": "testuser"},
    "base": {"ref": "main"},
    "head": {"ref": "feature-branch"},
    "labels": [],
    "assignees": [],
    "requested_reviewers": [],
    "comments": 0,
    "commits": 1,
    "changed_files": 2,
    "additions": 50,
    "deletions": 10,
    "merged_at": None,
    "mergeable": True,
    "created_at": "2024-07-27T10:00:00Z",
    "updated_at": "2024-07-27T10:00:00Z",
}


# ── prs create ─────────────────────────────────────────────────────────────


def test_prs_create_basic(runner, mock_token):
    """prs create with required flags creates a PR and shows number + URL."""
    with patch("ghcli.client.GitHubClient.post", return_value=MOCK_PR):
        result = runner.invoke(
            cli,
            [
                "prs",
                "create",
                "owner/repo",
                "--title",
                "Add new feature",
                "--head",
                "feature-branch",
                "--base",
                "main",
            ],
        )
    assert result.exit_code == 0
    assert "7" in result.output
    assert "github.com" in result.output or "Pull request" in result.output


def test_prs_create_draft(runner, mock_token):
    """prs create --draft passes draft=True to API."""
    with patch("ghcli.client.GitHubClient.post", return_value=MOCK_PR) as mock_post:
        result = runner.invoke(
            cli,
            [
                "prs",
                "create",
                "owner/repo",
                "--title",
                "WIP feature",
                "--head",
                "wip-branch",
                "--draft",
            ],
        )
    assert result.exit_code == 0
    payload = mock_post.call_args[1].get("json") or mock_post.call_args[0][1]
    assert payload.get("draft") is True


def test_prs_create_with_body(runner, mock_token):
    """prs create --body passes body to API."""
    with patch("ghcli.client.GitHubClient.post", return_value=MOCK_PR) as mock_post:
        result = runner.invoke(
            cli,
            [
                "prs",
                "create",
                "owner/repo",
                "--title",
                "Feature",
                "--head",
                "feat",
                "--body",
                "Detailed description",
            ],
        )
    assert result.exit_code == 0
    payload = mock_post.call_args[1].get("json") or mock_post.call_args[0][1]
    assert payload.get("body") == "Detailed description"


def test_prs_create_missing_head(runner, mock_token):
    """prs create without --head fails with usage error."""
    result = runner.invoke(
        cli,
        ["prs", "create", "owner/repo", "--title", "Feature"],
    )
    assert result.exit_code != 0
    assert "head" in result.output.lower() or "Missing" in result.output


def test_prs_create_missing_title(runner, mock_token):
    """prs create without --title fails with usage error."""
    result = runner.invoke(
        cli,
        ["prs", "create", "owner/repo", "--head", "feat"],
    )
    assert result.exit_code != 0
    assert "title" in result.output.lower() or "Missing" in result.output


def test_prs_create_api_error(runner, mock_token):
    """prs create shows error on API failure."""
    from ghcli.client import GitHubAPIError

    with patch(
        "ghcli.client.GitHubClient.post",
        side_effect=GitHubAPIError("No commits between main and feat", 422),
    ):
        result = runner.invoke(
            cli,
            [
                "prs",
                "create",
                "owner/repo",
                "--title",
                "Empty PR",
                "--head",
                "feat",
            ],
        )
    assert result.exit_code != 0 or "✗" in result.output


# ── prs merge ──────────────────────────────────────────────────────────────


def test_prs_merge_default(runner, mock_token):
    """prs merge uses merge method by default."""
    merge_result = {
        "sha": "abc1234def5678",
        "merged": True,
        "message": "Pull Request successfully merged",
    }
    with patch("ghcli.client.GitHubClient.put", return_value=merge_result) as mock_put:
        result = runner.invoke(cli, ["prs", "merge", "owner/repo", "7"])
    assert result.exit_code == 0
    assert "merged" in result.output.lower() or "7" in result.output
    payload = mock_put.call_args[1].get("json") or mock_put.call_args[0][1]
    assert payload.get("merge_method") == "merge"


def test_prs_merge_squash(runner, mock_token):
    """prs merge --method squash uses squash method."""
    merge_result = {
        "sha": "abc1234def5678",
        "merged": True,
        "message": "Pull Request successfully merged",
    }
    with patch("ghcli.client.GitHubClient.put", return_value=merge_result) as mock_put:
        result = runner.invoke(
            cli,
            ["prs", "merge", "owner/repo", "7", "--method", "squash"],
        )
    assert result.exit_code == 0
    payload = mock_put.call_args[1].get("json") or mock_put.call_args[0][1]
    assert payload.get("merge_method") == "squash"


def test_prs_merge_rebase(runner, mock_token):
    """prs merge --method rebase uses rebase method."""
    merge_result = {
        "sha": "abc1234def5678",
        "merged": True,
        "message": "Pull Request successfully merged",
    }
    with patch("ghcli.client.GitHubClient.put", return_value=merge_result) as mock_put:
        result = runner.invoke(
            cli,
            ["prs", "merge", "owner/repo", "7", "--method", "rebase"],
        )
    assert result.exit_code == 0
    payload = mock_put.call_args[1].get("json") or mock_put.call_args[0][1]
    assert payload.get("merge_method") == "rebase"


def test_prs_merge_with_message(runner, mock_token):
    """prs merge --message passes commit message."""
    merge_result = {"sha": "abc1234def5678", "merged": True, "message": "Merged"}
    with patch("ghcli.client.GitHubClient.put", return_value=merge_result) as mock_put:
        result = runner.invoke(
            cli,
            ["prs", "merge", "owner/repo", "7", "--message", "Custom merge commit"],
        )
    assert result.exit_code == 0
    payload = mock_put.call_args[1].get("json") or mock_put.call_args[0][1]
    assert payload.get("commit_message") == "Custom merge commit"


def test_prs_merge_api_error(runner, mock_token):
    """prs merge shows error when PR is not mergeable."""
    from ghcli.client import GitHubAPIError

    with patch(
        "ghcli.client.GitHubClient.put",
        side_effect=GitHubAPIError("Pull Request is not mergeable", 405),
    ):
        result = runner.invoke(cli, ["prs", "merge", "owner/repo", "7"])
    assert result.exit_code != 0 or "✗" in result.output


# ── prs close ──────────────────────────────────────────────────────────────


def test_prs_close(runner, mock_token):
    """prs close patches state to closed."""
    closed_pr = {**MOCK_PR, "state": "closed"}
    with patch("ghcli.client.GitHubClient.patch", return_value=closed_pr):
        result = runner.invoke(cli, ["prs", "close", "owner/repo", "7"])
    assert result.exit_code == 0
    assert "closed" in result.output.lower() or "7" in result.output


# ── help ───────────────────────────────────────────────────────────────────


def test_prs_help(runner):
    """prs --help shows all subcommands."""
    result = runner.invoke(cli, ["prs", "--help"])
    assert result.exit_code == 0
    for sub in ("list", "view", "create", "merge", "close"):
        assert sub in result.output
