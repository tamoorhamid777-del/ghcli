"""Tests for ghcli org commands."""
from __future__ import annotations
from unittest.mock import MagicMock, patch
from click.testing import CliRunner
from ghcli.commands.org import org

MOCK_ORGS = [{"login": "myorg", "id": 123, "url": "https://api.github.com/orgs/myorg"}]
MOCK_MEMBERS = [{"login": "member1", "type": "User", "html_url": "https://github.com/member1"}]
MOCK_REPOS = [{"name": "repo1", "stargazers_count": 5, "language": "Python", "private": False, "updated_at": "2026-01-01T00:00:00Z"}]
MOCK_ORG = {"login": "myorg", "name": "My Org", "description": "Test org", "public_repos": 10, "html_url": "https://github.com/myorg"}

def make_client(return_value):
    client = MagicMock()
    client.get.return_value = return_value
    return client

def test_org_list():
    runner = CliRunner()
    with patch("ghcli.commands.org.GitHubClient") as MockClient:
        MockClient.return_value = make_client(MOCK_ORGS)
        result = runner.invoke(org, ["list"])
    assert result.exit_code == 0
    assert "myorg" in result.output

def test_org_members():
    runner = CliRunner()
    with patch("ghcli.commands.org.GitHubClient") as MockClient:
        MockClient.return_value = make_client(MOCK_MEMBERS)
        result = runner.invoke(org, ["members", "myorg"])
    assert result.exit_code == 0
    assert "member1" in result.output

def test_org_repos():
    runner = CliRunner()
    with patch("ghcli.commands.org.GitHubClient") as MockClient:
        MockClient.return_value = make_client(MOCK_REPOS)
        result = runner.invoke(org, ["repos", "myorg"])
    assert result.exit_code == 0
    assert "repo1" in result.output

def test_org_view():
    runner = CliRunner()
    with patch("ghcli.commands.org.GitHubClient") as MockClient:
        MockClient.return_value = make_client(MOCK_ORG)
        result = runner.invoke(org, ["view", "myorg"])
    assert result.exit_code == 0
    assert "myorg" in result.output
