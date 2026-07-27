"""Tests for ghcli prs commands (list, view, create, merge, close)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from ghcli.commands.prs import prs


@pytest.fixture()
def runner():
    return CliRunner()


@pytest.fixture()
def mock_client():
    with patch("ghcli.commands.prs.GitHubClient") as MockClient:
        client = MagicMock()
        MockClient.return_value = client
        yield client


MOCK_PRS = [
    {
        "number": 1,
        "title": "feat: add new feature",
        "state": "open",
        "draft": False,
        "user": {"login": "alice"},
        "head": {"label": "alice:feature-branch", "ref": "feature-branch", "sha": "headsha"},
        "base": {"label": "owner:main", "ref": "main", "sha": "basesha"},
        "html_url": "https://github.com/owner/repo/pull/1",
        "created_at": "2024-07-01T10:00:00Z",
        "updated_at": "2024-07-02T10:00:00Z",
        "body": "This PR adds a new feature.",
        "labels": [],
        "assignees": [],
        "requested_reviewers": [],
        "comments": 2,
        "review_comments": 1,
        "commits": 3,
        "additions": 50,
        "deletions": 10,
        "changed_files": 5,
        "mergeable": True,
        "merged": False,
        "merged_at": None,
        "merge_commit_sha": None,
    },
    {
        "number": 2,
        "title": "fix: resolve bug",
        "state": "open",
        "draft": True,
        "user": {"login": "bob"},
        "head": {"label": "bob:bugfix", "ref": "bugfix", "sha": "bugsha"},
        "base": {"label": "owner:main", "ref": "main", "sha": "basesha"},
        "html_url": "https://github.com/owner/repo/pull/2",
        "created_at": "2024-07-03T10:00:00Z",
        "updated_at": "2024-07-04T10:00:00Z",
        "body": "Fixes a bug.",
        "labels": [{"name": "bug"}],
        "assignees": [],
        "requested_reviewers": [],
        "comments": 0,
        "review_comments": 0,
        "commits": 1,
        "additions": 5,
        "deletions": 2,
        "changed_files": 1,
        "mergeable": False,
        "merged": False,
        "merged_at": None,
        "merge_commit_sha": None,
    },
]


class TestPrsList:
    def test_list_basic(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_client.paginate.return_value = iter(MOCK_PRS)
        result = runner.invoke(prs, ["list", "owner/repo"])
        assert result.exit_code == 0
        assert "#1" in result.output or "feat" in result.output

    def test_list_json(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_client.paginate.return_value = iter(MOCK_PRS)
        result = runner.invoke(prs, ["list", "owner/repo", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 2

    def test_list_state_closed(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_client.paginate.return_value = iter([])
        result = runner.invoke(prs, ["list", "owner/repo", "--state", "closed"])
        assert result.exit_code == 0

    def test_list_with_limit(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_client.paginate.return_value = iter(MOCK_PRS[:1])
        result = runner.invoke(prs, ["list", "owner/repo", "--limit", "1"])
        assert result.exit_code == 0

    def test_list_empty(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_client.paginate.return_value = iter([])
        result = runner.invoke(prs, ["list", "owner/repo"])
        assert result.exit_code == 0
        assert "No" in result.output

    def test_list_api_error(self, runner, mock_client):
        from ghcli.client import GitHubAPIError

        mock_client.require_auth.return_value = None
        mock_client.paginate.side_effect = GitHubAPIError("Not Found", 404)
        result = runner.invoke(prs, ["list", "owner/repo"])
        assert result.exit_code == 1 or "404" in result.output or "Not Found" in result.output

    def test_list_help(self, runner):
        result = runner.invoke(prs, ["list", "--help"])
        assert result.exit_code == 0
        assert "--json" in result.output
        assert "--limit" in result.output


class TestPrsView:
    def test_view_basic(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        # prs_view makes 3 get calls: pr, reviews, files
        mock_client.get.side_effect = [MOCK_PRS[0], [], []]
        result = runner.invoke(prs, ["view", "owner/repo", "1"])
        assert result.exit_code == 0
        assert "feat" in result.output or "#1" in result.output

    def test_view_with_files(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_files = [
            {"filename": "src/main.py", "status": "modified", "additions": 5, "deletions": 2}
        ]
        mock_client.get.side_effect = [MOCK_PRS[0], [], mock_files]
        result = runner.invoke(prs, ["view", "owner/repo", "1"])
        assert result.exit_code == 0

    def test_view_api_error(self, runner, mock_client):
        from ghcli.client import GitHubAPIError

        mock_client.require_auth.return_value = None
        mock_client.get.side_effect = GitHubAPIError("Not Found", 404)
        result = runner.invoke(prs, ["view", "owner/repo", "999"])
        assert result.exit_code == 1 or "404" in result.output

    def test_view_help(self, runner):
        result = runner.invoke(prs, ["view", "--help"])
        assert result.exit_code == 0


class TestPrsCreate:
    def test_create_basic(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_client.post.return_value = {
            "number": 3,
            "title": "feat: new PR",
            "html_url": "https://github.com/owner/repo/pull/3",
            "state": "open",
            "draft": False,
            "base": {"ref": "main"},
            "head": {"ref": "feature-branch"},
        }
        result = runner.invoke(
            prs,
            [
                "create",
                "owner/repo",
                "--title",
                "feat: new PR",
                "--head",
                "feature-branch",
                "--base",
                "main",
            ],
        )
        assert result.exit_code == 0
        assert "#3" in result.output or "new PR" in result.output or "https://" in result.output

    def test_create_draft(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_client.post.return_value = {
            "number": 4,
            "title": "WIP: draft PR",
            "html_url": "https://github.com/owner/repo/pull/4",
            "state": "open",
            "draft": True,
            "base": {"ref": "main"},
            "head": {"ref": "wip-branch"},
        }
        result = runner.invoke(
            prs,
            [
                "create",
                "owner/repo",
                "--title",
                "WIP: draft PR",
                "--head",
                "wip-branch",
                "--base",
                "main",
                "--draft",
            ],
        )
        assert result.exit_code == 0

    def test_create_api_error(self, runner, mock_client):
        from ghcli.client import GitHubAPIError

        mock_client.require_auth.return_value = None
        mock_client.post.side_effect = GitHubAPIError("Unprocessable Entity", 422)
        result = runner.invoke(
            prs,
            [
                "create",
                "owner/repo",
                "--title",
                "bad PR",
                "--head",
                "nonexistent",
                "--base",
                "main",
            ],
        )
        assert result.exit_code == 1 or "422" in result.output or "Error" in result.output

    def test_create_help(self, runner):
        result = runner.invoke(prs, ["create", "--help"])
        assert result.exit_code == 0
        assert "--title" in result.output
        assert "--head" in result.output


class TestPrsMerge:
    def test_merge_basic(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_client.put.return_value = {
            "merged": True,
            "message": "Pull Request successfully merged",
            "sha": "mergesha123",
        }
        result = runner.invoke(prs, ["merge", "owner/repo", "1"])
        assert result.exit_code == 0
        assert "merged" in result.output.lower() or "success" in result.output.lower()

    def test_merge_squash(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_client.put.return_value = {
            "merged": True,
            "message": "Pull Request successfully merged",
            "sha": "squashsha",
        }
        result = runner.invoke(prs, ["merge", "owner/repo", "1", "--method", "squash"])
        assert result.exit_code == 0

    def test_merge_rebase(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_client.put.return_value = {
            "merged": True,
            "message": "Pull Request successfully merged",
            "sha": "rebasesha",
        }
        result = runner.invoke(prs, ["merge", "owner/repo", "1", "--method", "rebase"])
        assert result.exit_code == 0

    def test_merge_api_error(self, runner, mock_client):
        from ghcli.client import GitHubAPIError

        mock_client.require_auth.return_value = None
        mock_client.put.side_effect = GitHubAPIError("Method Not Allowed", 405)
        result = runner.invoke(prs, ["merge", "owner/repo", "1"])
        assert result.exit_code == 1 or "405" in result.output or "Error" in result.output

    def test_merge_help(self, runner):
        result = runner.invoke(prs, ["merge", "--help"])
        assert result.exit_code == 0
        assert "--method" in result.output


class TestPrsClose:
    def test_close_help(self, runner):
        result = runner.invoke(prs, ["close", "--help"])
        assert result.exit_code == 0

    def test_close_basic(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_client.patch.return_value = {
            "number": 1,
            "state": "closed",
            "html_url": "https://github.com/owner/repo/pull/1",
        }
        result = runner.invoke(prs, ["close", "owner/repo", "1"])
        assert result.exit_code == 0
        assert "closed" in result.output.lower() or "#1" in result.output
