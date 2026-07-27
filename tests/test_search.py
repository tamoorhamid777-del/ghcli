"""Tests for ghcli search commands."""
from __future__ import annotations
from unittest.mock import MagicMock, patch
from click.testing import CliRunner
from ghcli.commands.search import search

MOCK_REPOS = {"total_count": 1, "items": [{"full_name": "owner/repo", "stargazers_count": 42, "language": "Python", "description": "A test repo"}]}
MOCK_ISSUES = {"total_count": 1, "items": [{"number": 1, "title": "Test issue", "repository_url": "https://api.github.com/repos/owner/repo", "state": "open"}]}
MOCK_USERS = {"total_count": 1, "items": [{"login": "testuser", "type": "User", "html_url": "https://github.com/testuser"}]}

def make_client(return_value):
    client = MagicMock()
    client.get.return_value = return_value
    return client

def test_search_repos():
    runner = CliRunner()
    with patch("ghcli.commands.search.GitHubClient") as MockClient:
        MockClient.return_value = make_client(MOCK_REPOS)
        result = runner.invoke(search, ["repos", "python cli"])
    assert result.exit_code == 0
    assert "owner/repo" in result.output

def test_search_repos_json():
    runner = CliRunner()
    with patch("ghcli.commands.search.GitHubClient") as MockClient:
        MockClient.return_value = make_client(MOCK_REPOS)
        result = runner.invoke(search, ["repos", "python cli", "--json"])
    assert result.exit_code == 0
    assert "owner/repo" in result.output

def test_search_issues():
    runner = CliRunner()
    with patch("ghcli.commands.search.GitHubClient") as MockClient:
        MockClient.return_value = make_client(MOCK_ISSUES)
        result = runner.invoke(search, ["issues", "bug"])
    assert result.exit_code == 0
    assert "Test issue" in result.output

def test_search_users():
    runner = CliRunner()
    with patch("ghcli.commands.search.GitHubClient") as MockClient:
        MockClient.return_value = make_client(MOCK_USERS)
        result = runner.invoke(search, ["users", "testuser"])
    assert result.exit_code == 0
    assert "testuser" in result.output

def test_search_no_auth():
    runner = CliRunner()
    from ghcli.client import GitHubAPIError
    with patch("ghcli.commands.search.GitHubClient") as MockClient:
        MockClient.return_value.require_auth.side_effect = SystemExit(1)
        result = runner.invoke(search, ["repos", "python"])
    assert result.exit_code == 1
