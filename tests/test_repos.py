"""Tests for ghcli repos commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from ghcli.commands.repos import repos

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def runner():
    return CliRunner()


@pytest.fixture()
def mock_client():
    """Return a patched GitHubClient that never hits the network."""
    with patch("ghcli.commands.repos.GitHubClient") as MockClient:
        client = MagicMock()
        MockClient.return_value = client
        yield client


# ---------------------------------------------------------------------------
# repos list
# ---------------------------------------------------------------------------


class TestReposList:
    def test_list_returns_table(self, runner, mock_client):
        """repos list should display a table with repo names."""
        mock_client.require_auth.return_value = None
        # repos list uses c.paginate(), not c.get()
        mock_client.paginate.return_value = iter(
            [
                {
                    "full_name": "tamoorhamid777-del/ghcli",
                    "private": False,
                    "description": "A GitHub CLI",
                    "stargazers_count": 5,
                    "forks_count": 1,
                    "language": "Python",
                    "updated_at": "2026-07-27T00:00:00Z",
                    "html_url": "https://github.com/tamoorhamid777-del/ghcli",
                }
            ]
        )
        result = runner.invoke(repos, ["list"])
        assert result.exit_code == 0
        assert "ghcli" in result.output

    def test_list_empty_repos(self, runner, mock_client):
        """repos list with no repos should exit cleanly."""
        mock_client.require_auth.return_value = None
        mock_client.paginate.return_value = iter([])
        result = runner.invoke(repos, ["list"])
        assert result.exit_code == 0

    def test_list_api_error(self, runner, mock_client):
        """repos list should handle API errors gracefully."""
        from ghcli.client import GitHubAPIError

        mock_client.require_auth.return_value = None
        mock_client.paginate.side_effect = GitHubAPIError("Not Found", 404)
        result = runner.invoke(repos, ["list"])
        # Should exit non-zero or print an error message
        assert result.exit_code != 0 or "404" in result.output or "Not Found" in result.output


# ---------------------------------------------------------------------------
# repos create
# ---------------------------------------------------------------------------


class TestReposCreate:
    def test_create_public_repo(self, runner, mock_client):
        """repos create should display the new repo details."""
        mock_client.require_auth.return_value = None
        mock_client.post.return_value = {
            "full_name": "tamoorhamid777-del/new-repo",
            "private": False,
            "html_url": "https://github.com/tamoorhamid777-del/new-repo",
            "description": "A test repo",
            "clone_url": "https://github.com/tamoorhamid777-del/new-repo.git",
            "ssh_url": "git@github.com:tamoorhamid777-del/new-repo.git",
        }
        result = runner.invoke(repos, ["create", "new-repo", "--description", "A test repo"])
        assert result.exit_code == 0
        assert "new-repo" in result.output

    def test_create_private_repo(self, runner, mock_client):
        """repos create --private should work without errors."""
        mock_client.require_auth.return_value = None
        mock_client.post.return_value = {
            "full_name": "tamoorhamid777-del/secret-repo",
            "private": True,
            "html_url": "https://github.com/tamoorhamid777-del/secret-repo",
            "description": "",
            "clone_url": "https://github.com/tamoorhamid777-del/secret-repo.git",
            "ssh_url": "git@github.com:tamoorhamid777-del/secret-repo.git",
        }
        result = runner.invoke(repos, ["create", "secret-repo", "--private"])
        assert result.exit_code == 0

    def test_create_api_error(self, runner, mock_client):
        """repos create should handle API errors gracefully."""
        from ghcli.client import GitHubAPIError

        mock_client.require_auth.return_value = None
        mock_client.post.side_effect = GitHubAPIError("Repository already exists", 422)
        result = runner.invoke(repos, ["create", "existing-repo"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# repos view
# ---------------------------------------------------------------------------


class TestReposView:
    def test_view_existing_repo(self, runner, mock_client):
        """repos view should display detailed repo information."""
        mock_client.require_auth.return_value = None
        mock_client.get.return_value = {
            "full_name": "tamoorhamid777-del/ghcli",
            "private": False,
            "description": "A GitHub CLI",
            "stargazers_count": 5,
            "forks_count": 1,
            "open_issues_count": 2,
            "language": "Python",
            "default_branch": "main",
            "created_at": "2026-07-27T00:00:00Z",
            "updated_at": "2026-07-27T00:00:00Z",
            "pushed_at": "2026-07-27T00:00:00Z",
            "html_url": "https://github.com/tamoorhamid777-del/ghcli",
            "clone_url": "https://github.com/tamoorhamid777-del/ghcli.git",
            "ssh_url": "git@github.com:tamoorhamid777-del/ghcli.git",
            "topics": ["python", "cli"],
            "license": {"name": "MIT License"},
            "archived": False,
            "disabled": False,
            "homepage": None,
        }
        result = runner.invoke(repos, ["view", "tamoorhamid777-del/ghcli"])
        assert result.exit_code == 0
        assert "ghcli" in result.output

    def test_view_nonexistent_repo(self, runner, mock_client):
        """repos view should handle 404 gracefully."""
        from ghcli.client import GitHubAPIError

        mock_client.require_auth.return_value = None
        mock_client.get.side_effect = GitHubAPIError("Not Found", 404)
        result = runner.invoke(repos, ["view", "nobody/nonexistent"])
        assert result.exit_code != 0
