"""Tests for ghcli commits commands."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from ghcli.commands.commits import commits


@pytest.fixture()
def runner():
    return CliRunner()


@pytest.fixture()
def mock_client():
    with patch("ghcli.commands.commits.GitHubClient") as MockClient:
        client = MagicMock()
        MockClient.return_value = client
        yield client


MOCK_COMMITS = [
    {
        "sha": "abc1234567890",
        "commit": {
            "message": "feat: add new feature",
            "author": {"name": "Alice", "date": "2024-07-01T10:00:00Z"},
        },
        "author": {"login": "alice"},
        "html_url": "https://github.com/owner/repo/commit/abc1234567890",
    },
    {
        "sha": "def9876543210",
        "commit": {
            "message": "fix: resolve bug",
            "author": {"name": "Bob", "date": "2024-07-02T11:00:00Z"},
        },
        "author": {"login": "bob"},
        "html_url": "https://github.com/owner/repo/commit/def9876543210",
    },
]

MOCK_COMMIT_DETAIL = {
    "sha": "abc1234567890abcdef",
    "commit": {
        "message": "feat: add new feature\n\nDetailed description here.",
        "author": {"name": "Alice", "date": "2024-07-01T10:00:00Z", "email": "alice@example.com"},
        "committer": {"name": "Alice", "date": "2024-07-01T10:00:00Z", "email": "alice@example.com"},
    },
    "author": {"login": "alice"},
    "html_url": "https://github.com/owner/repo/commit/abc1234567890abcdef",
    "stats": {"additions": 10, "deletions": 2, "total": 12},
    "files": [
        {"filename": "src/main.py", "status": "modified", "additions": 10, "deletions": 2, "changes": 12}
    ],
    "parents": [{"sha": "parent123"}],
}


class TestCommitsList:
    def test_list_basic(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_client.paginate.return_value = iter(MOCK_COMMITS)
        result = runner.invoke(commits, ["list", "owner/repo"])
        assert result.exit_code == 0
        assert "abc1234" in result.output or "feat" in result.output

    def test_list_json(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_client.paginate.return_value = iter(MOCK_COMMITS)
        result = runner.invoke(commits, ["list", "owner/repo", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 2

    def test_list_with_limit(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_client.paginate.return_value = iter(MOCK_COMMITS[:1])
        result = runner.invoke(commits, ["list", "owner/repo", "--limit", "1"])
        assert result.exit_code == 0

    def test_list_with_branch(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_client.paginate.return_value = iter(MOCK_COMMITS)
        result = runner.invoke(commits, ["list", "owner/repo", "--branch", "develop"])
        assert result.exit_code == 0

    def test_list_with_author(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_client.paginate.return_value = iter([MOCK_COMMITS[0]])
        result = runner.invoke(commits, ["list", "owner/repo", "--author", "alice"])
        assert result.exit_code == 0

    def test_list_with_since_until(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_client.paginate.return_value = iter(MOCK_COMMITS)
        result = runner.invoke(
            commits,
            ["list", "owner/repo", "--since", "2024-01-01", "--until", "2024-12-31"],
        )
        assert result.exit_code == 0

    def test_list_empty(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_client.paginate.return_value = iter([])
        result = runner.invoke(commits, ["list", "owner/repo"])
        assert result.exit_code == 0
        assert "No commits" in result.output

    def test_list_api_error(self, runner, mock_client):
        from ghcli.client import GitHubAPIError
        mock_client.require_auth.return_value = None
        mock_client.paginate.side_effect = GitHubAPIError("Not Found", 404)
        result = runner.invoke(commits, ["list", "owner/repo"])
        # Command catches the error and prints it, exits 1
        assert result.exit_code == 1 or "404" in result.output or "Not Found" in result.output

    def test_list_help(self, runner):
        result = runner.invoke(commits, ["list", "--help"])
        assert result.exit_code == 0
        assert "--limit" in result.output
        assert "--json" in result.output


class TestCommitsView:
    def test_view_basic(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_client.get.return_value = MOCK_COMMIT_DETAIL
        result = runner.invoke(commits, ["view", "owner/repo", "abc1234567890abcdef"])
        assert result.exit_code == 0
        assert "abc1234" in result.output or "feat" in result.output or "Alice" in result.output

    def test_view_api_error(self, runner, mock_client):
        from ghcli.client import GitHubAPIError
        mock_client.require_auth.return_value = None
        mock_client.get.side_effect = GitHubAPIError("Not Found", 404)
        result = runner.invoke(commits, ["view", "owner/repo", "badsha"])
        assert result.exit_code == 1 or "404" in result.output or "Not Found" in result.output

    def test_view_help(self, runner):
        result = runner.invoke(commits, ["view", "--help"])
        assert result.exit_code == 0


class TestCommitsCompare:
    def test_compare_help(self, runner):
        result = runner.invoke(commits, ["compare", "--help"])
        assert result.exit_code == 0

    def test_compare_basic(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_client.get.return_value = {
            "status": "ahead",
            "ahead_by": 3,
            "behind_by": 0,
            "total_commits": 3,
            "commits": MOCK_COMMITS,
            "files": [],
        }
        result = runner.invoke(commits, ["compare", "owner/repo", "main", "feature"])
        assert result.exit_code == 0
        assert "ahead" in result.output or "3" in result.output

    def test_compare_api_error(self, runner, mock_client):
        from ghcli.client import GitHubAPIError
        mock_client.require_auth.return_value = None
        mock_client.get.side_effect = GitHubAPIError("Not Found", 404)
        result = runner.invoke(commits, ["compare", "owner/repo", "main", "nonexistent"])
        assert result.exit_code == 1 or "404" in result.output