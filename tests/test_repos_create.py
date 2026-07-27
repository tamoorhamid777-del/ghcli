"""Tests for ghcli repos create / delete / fork / clone commands."""

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


MOCK_REPO = {
    "id": 111222,
    "name": "new-repo",
    "full_name": "testuser/new-repo",
    "description": "A brand new repo",
    "private": False,
    "html_url": "https://github.com/testuser/new-repo",
    "clone_url": "https://github.com/testuser/new-repo.git",
    "ssh_url": "git@github.com:testuser/new-repo.git",
    "stargazers_count": 0,
    "forks_count": 0,
    "open_issues_count": 0,
    "language": None,
    "default_branch": "main",
    "topics": [],
    "updated_at": "2024-07-27T12:00:00Z",
    "created_at": "2024-07-27T12:00:00Z",
}


# ── repos create ───────────────────────────────────────────────────────────


def test_repos_create_public(runner, mock_token):
    """repos create makes a public repo and shows clone URL."""
    with patch("ghcli.client.GitHubClient.post", return_value=MOCK_REPO):
        result = runner.invoke(
            cli,
            ["repos", "create", "new-repo", "--description", "A brand new repo"],
        )
    assert result.exit_code == 0
    assert "new-repo" in result.output
    assert "clone" in result.output.lower() or "github.com" in result.output


def test_repos_create_private(runner, mock_token):
    """repos create --private creates a private repo."""
    private_repo = {
        **MOCK_REPO,
        "private": True,
        "name": "secret-repo",
        "full_name": "testuser/secret-repo",
    }
    with patch("ghcli.client.GitHubClient.post", return_value=private_repo):
        result = runner.invoke(
            cli,
            ["repos", "create", "secret-repo", "--private"],
        )
    assert result.exit_code == 0
    assert "secret-repo" in result.output


def test_repos_create_with_gitignore(runner, mock_token):
    """repos create --gitignore passes template to API."""
    with patch("ghcli.client.GitHubClient.post", return_value=MOCK_REPO) as mock_post:
        result = runner.invoke(
            cli,
            ["repos", "create", "new-repo", "--gitignore", "Python"],
        )
    assert result.exit_code == 0
    call_kwargs = mock_post.call_args
    payload = call_kwargs[1].get("json") or call_kwargs[0][1]
    assert payload.get("gitignore_template") == "Python"


def test_repos_create_api_error(runner, mock_token):
    """repos create shows error on API failure."""
    from ghcli.client import GitHubAPIError

    with patch(
        "ghcli.client.GitHubClient.post",
        side_effect=GitHubAPIError("Repository already exists", 422),
    ):
        result = runner.invoke(cli, ["repos", "create", "existing-repo"])
    assert result.exit_code != 0 or "✗" in result.output


# ── repos delete ───────────────────────────────────────────────────────────


def test_repos_delete_with_yes(runner, mock_token):
    """repos delete --yes skips confirmation."""
    with patch("ghcli.client.GitHubClient.delete", return_value=None):
        result = runner.invoke(
            cli,
            ["repos", "delete", "testuser/old-repo", "--yes"],
        )
    assert result.exit_code == 0
    assert "deleted" in result.output.lower()


def test_repos_delete_abort(runner, mock_token):
    """repos delete aborts when user says no."""
    with patch("ghcli.client.GitHubClient.delete", return_value=None):
        result = runner.invoke(
            cli,
            ["repos", "delete", "testuser/old-repo"],
            input="n\n",
        )
    assert "Aborted" in result.output or result.exit_code != 0


def test_repos_delete_api_error(runner, mock_token):
    """repos delete shows error on API failure."""
    from ghcli.client import GitHubAPIError

    with patch(
        "ghcli.client.GitHubClient.delete",
        side_effect=GitHubAPIError("Must have admin rights", 403),
    ):
        result = runner.invoke(
            cli,
            ["repos", "delete", "testuser/protected-repo", "--yes"],
        )
    assert result.exit_code != 0 or "✗" in result.output


# ── repos fork ─────────────────────────────────────────────────────────────


def test_repos_fork_success(runner, mock_token):
    """repos fork forks a repo and shows the new name."""
    forked = {**MOCK_REPO, "full_name": "testuser/upstream-repo"}
    with patch("ghcli.client.GitHubClient.post", return_value=forked):
        result = runner.invoke(cli, ["repos", "fork", "upstream/upstream-repo"])
    assert result.exit_code == 0
    assert "Fork" in result.output or "fork" in result.output.lower() or "testuser" in result.output


def test_repos_fork_to_org(runner, mock_token):
    """repos fork --org forks into an organization."""
    forked = {**MOCK_REPO, "full_name": "myorg/upstream-repo"}
    with patch("ghcli.client.GitHubClient.post", return_value=forked) as mock_post:
        result = runner.invoke(
            cli,
            ["repos", "fork", "upstream/upstream-repo", "--org", "myorg"],
        )
    assert result.exit_code == 0
    call_kwargs = mock_post.call_args
    payload = call_kwargs[1].get("json") or call_kwargs[0][1]
    assert payload.get("organization") == "myorg"


# ── repos clone ────────────────────────────────────────────────────────────


def test_repos_clone_success(runner, mock_token):
    """repos clone runs git clone with the HTTPS URL."""
    with patch("ghcli.client.GitHubClient.get", return_value=MOCK_REPO):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = runner.invoke(cli, ["repos", "clone", "testuser/new-repo"])
    assert result.exit_code == 0
    mock_run.assert_called_once()
    cmd = mock_run.call_args[0][0]
    assert "git" in cmd
    assert "clone" in cmd


def test_repos_clone_ssh(runner, mock_token):
    """repos clone --ssh uses the SSH URL."""
    with patch("ghcli.client.GitHubClient.get", return_value=MOCK_REPO):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = runner.invoke(cli, ["repos", "clone", "testuser/new-repo", "--ssh"])
    assert result.exit_code == 0
    cmd = mock_run.call_args[0][0]
    assert "git@github.com" in " ".join(cmd)


def test_repos_clone_shallow(runner, mock_token):
    """repos clone --depth creates a shallow clone."""
    with patch("ghcli.client.GitHubClient.get", return_value=MOCK_REPO):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = runner.invoke(
                cli,
                ["repos", "clone", "testuser/new-repo", "--depth", "1"],
            )
    assert result.exit_code == 0
    cmd = mock_run.call_args[0][0]
    assert "--depth" in cmd
    assert "1" in cmd


# ── help ───────────────────────────────────────────────────────────────────


def test_repos_help(runner):
    """repos --help shows all subcommands."""
    result = runner.invoke(cli, ["repos", "--help"])
    assert result.exit_code == 0
    for sub in ("list", "view", "create", "delete", "fork", "clone"):
        assert sub in result.output
