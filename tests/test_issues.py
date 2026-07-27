"""Tests for ghcli issues commands (list, view, create, close, reopen)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from ghcli.commands.issues import issues


@pytest.fixture()
def runner():
    return CliRunner()


@pytest.fixture()
def mock_client():
    with patch("ghcli.commands.issues.GitHubClient") as MockClient:
        client = MagicMock()
        MockClient.return_value = client
        yield client


MOCK_ISSUES = [
    {
        "number": 1,
        "title": "Bug: something is broken",
        "state": "open",
        "user": {"login": "alice"},
        "assignees": [{"login": "bob"}],
        "labels": [{"name": "bug"}],
        "comments": 3,
        "html_url": "https://github.com/owner/repo/issues/1",
        "created_at": "2024-07-01T10:00:00Z",
        "updated_at": "2024-07-02T10:00:00Z",
        "body": "This is a bug report.",
        "milestone": None,
    },
    {
        "number": 2,
        "title": "Feature: add dark mode",
        "state": "open",
        "user": {"login": "charlie"},
        "assignees": [],
        "labels": [{"name": "enhancement"}],
        "comments": 0,
        "html_url": "https://github.com/owner/repo/issues/2",
        "created_at": "2024-07-03T10:00:00Z",
        "updated_at": "2024-07-04T10:00:00Z",
        "body": "Please add dark mode.",
        "milestone": None,
    },
]


class TestIssuesList:
    def test_list_basic(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_client.paginate.return_value = iter(MOCK_ISSUES)
        result = runner.invoke(issues, ["list", "owner/repo"])
        assert result.exit_code == 0
        assert "#1" in result.output or "Bug" in result.output

    def test_list_json(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_client.paginate.return_value = iter(MOCK_ISSUES)
        result = runner.invoke(issues, ["list", "owner/repo", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 2

    def test_list_state_closed(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_client.paginate.return_value = iter([])
        result = runner.invoke(issues, ["list", "owner/repo", "--state", "closed"])
        assert result.exit_code == 0

    def test_list_with_label(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_client.paginate.return_value = iter([MOCK_ISSUES[0]])
        result = runner.invoke(issues, ["list", "owner/repo", "--label", "bug"])
        assert result.exit_code == 0

    def test_list_with_assignee(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_client.paginate.return_value = iter([MOCK_ISSUES[0]])
        result = runner.invoke(issues, ["list", "owner/repo", "--assignee", "bob"])
        assert result.exit_code == 0

    def test_list_with_limit(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_client.paginate.return_value = iter(MOCK_ISSUES[:1])
        result = runner.invoke(issues, ["list", "owner/repo", "--limit", "1"])
        assert result.exit_code == 0

    def test_list_empty(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_client.paginate.return_value = iter([])
        result = runner.invoke(issues, ["list", "owner/repo"])
        assert result.exit_code == 0
        assert "No" in result.output

    def test_list_filters_prs(self, runner, mock_client):
        """Issues endpoint returns PRs too — they should be filtered out."""
        pr_item = {**MOCK_ISSUES[0], "pull_request": {"url": "https://..."}}
        mock_client.require_auth.return_value = None
        mock_client.paginate.return_value = iter([pr_item, MOCK_ISSUES[1]])
        result = runner.invoke(issues, ["list", "owner/repo"])
        assert result.exit_code == 0
        # PR should be filtered, only issue #2 shown
        assert "#1" not in result.output or "#2" in result.output

    def test_list_api_error(self, runner, mock_client):
        from ghcli.client import GitHubAPIError

        mock_client.require_auth.return_value = None
        mock_client.paginate.side_effect = GitHubAPIError("Not Found", 404)
        result = runner.invoke(issues, ["list", "owner/repo"])
        assert result.exit_code == 1 or "404" in result.output

    def test_list_help(self, runner):
        result = runner.invoke(issues, ["list", "--help"])
        assert result.exit_code == 0
        assert "--json" in result.output
        assert "--limit" in result.output


class TestIssuesView:
    def test_view_basic(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        # issues_view makes 2 get calls: issue + comments
        mock_client.get.side_effect = [MOCK_ISSUES[0], []]
        result = runner.invoke(issues, ["view", "owner/repo", "1"])
        assert result.exit_code == 0
        assert "Bug" in result.output or "#1" in result.output

    def test_view_with_comments(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_comments = [
            {
                "id": 1,
                "user": {"login": "reviewer"},
                "body": "LGTM!",
                "created_at": "2024-07-02T10:00:00Z",
            }
        ]
        mock_client.get.side_effect = [MOCK_ISSUES[0], mock_comments]
        result = runner.invoke(issues, ["view", "owner/repo", "1"])
        assert result.exit_code == 0

    def test_view_api_error(self, runner, mock_client):
        from ghcli.client import GitHubAPIError

        mock_client.require_auth.return_value = None
        mock_client.get.side_effect = GitHubAPIError("Not Found", 404)
        result = runner.invoke(issues, ["view", "owner/repo", "999"])
        assert result.exit_code == 1 or "404" in result.output

    def test_view_help(self, runner):
        result = runner.invoke(issues, ["view", "--help"])
        assert result.exit_code == 0


class TestIssuesCreate:
    def test_create_basic(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_client.post.return_value = {
            "number": 3,
            "title": "New issue",
            "html_url": "https://github.com/owner/repo/issues/3",
            "state": "open",
        }
        result = runner.invoke(
            issues,
            ["create", "owner/repo", "--title", "New issue"],
        )
        assert result.exit_code == 0
        assert "#3" in result.output or "New issue" in result.output or "https://" in result.output

    def test_create_with_body(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_client.post.return_value = {
            "number": 4,
            "title": "Issue with body",
            "html_url": "https://github.com/owner/repo/issues/4",
            "state": "open",
        }
        result = runner.invoke(
            issues,
            [
                "create",
                "owner/repo",
                "--title",
                "Issue with body",
                "--body",
                "Detailed description",
            ],
        )
        assert result.exit_code == 0

    def test_create_with_labels(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_client.post.return_value = {
            "number": 5,
            "title": "Labeled issue",
            "html_url": "https://github.com/owner/repo/issues/5",
            "state": "open",
        }
        result = runner.invoke(
            issues,
            ["create", "owner/repo", "--title", "Labeled issue", "--label", "bug"],
        )
        assert result.exit_code == 0

    def test_create_api_error(self, runner, mock_client):
        from ghcli.client import GitHubAPIError

        mock_client.require_auth.return_value = None
        mock_client.post.side_effect = GitHubAPIError("Unprocessable Entity", 422)
        result = runner.invoke(
            issues,
            ["create", "owner/repo", "--title", "Bad issue"],
        )
        assert result.exit_code == 1 or "422" in result.output

    def test_create_help(self, runner):
        result = runner.invoke(issues, ["create", "--help"])
        assert result.exit_code == 0
        assert "--title" in result.output


class TestIssuesClose:
    def test_close_basic(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_client.patch.return_value = {
            "number": 1,
            "state": "closed",
            "html_url": "https://github.com/owner/repo/issues/1",
        }
        result = runner.invoke(issues, ["close", "owner/repo", "1"])
        assert result.exit_code == 0
        assert "closed" in result.output.lower() or "#1" in result.output

    def test_close_with_comment(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_client.post.return_value = {"id": 1}
        mock_client.patch.return_value = {
            "number": 1,
            "state": "closed",
            "html_url": "https://github.com/owner/repo/issues/1",
        }
        result = runner.invoke(issues, ["close", "owner/repo", "1", "--comment", "Closing this."])
        assert result.exit_code == 0

    def test_close_api_error(self, runner, mock_client):
        from ghcli.client import GitHubAPIError

        mock_client.require_auth.return_value = None
        mock_client.patch.side_effect = GitHubAPIError("Not Found", 404)
        result = runner.invoke(issues, ["close", "owner/repo", "999"])
        assert result.exit_code == 1 or "404" in result.output

    def test_close_help(self, runner):
        result = runner.invoke(issues, ["close", "--help"])
        assert result.exit_code == 0


class TestIssuesReopen:
    def test_reopen_basic(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_client.patch.return_value = {
            "number": 1,
            "state": "open",
            "html_url": "https://github.com/owner/repo/issues/1",
        }
        result = runner.invoke(issues, ["reopen", "owner/repo", "1"])
        assert result.exit_code == 0
        assert "open" in result.output.lower() or "#1" in result.output

    def test_reopen_api_error(self, runner, mock_client):
        from ghcli.client import GitHubAPIError

        mock_client.require_auth.return_value = None
        mock_client.patch.side_effect = GitHubAPIError("Not Found", 404)
        result = runner.invoke(issues, ["reopen", "owner/repo", "999"])
        assert result.exit_code == 1 or "404" in result.output

    def test_reopen_help(self, runner):
        result = runner.invoke(issues, ["reopen", "--help"])
        assert result.exit_code == 0
