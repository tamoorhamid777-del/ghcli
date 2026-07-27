"""Tests for ghcli star commands."""
from __future__ import annotations
from unittest.mock import MagicMock, patch
from click.testing import CliRunner
from ghcli.commands.star import star

MOCK_STARRED = [{"full_name": "owner/repo", "stargazers_count": 100, "language": "Python", "description": "A cool repo"}]

def make_client(get_val=None):
    client = MagicMock()
    client.get.return_value = get_val
    client.put.return_value = None
    client.delete.return_value = None
    return client

def test_star_list():
    runner = CliRunner()
    with patch("ghcli.commands.star.GitHubClient") as MockClient:
        MockClient.return_value = make_client(get_val=MOCK_STARRED)
        result = runner.invoke(star, ["list"])
    assert result.exit_code == 0
    assert "owner/repo" in result.output

def test_star_list_json():
    runner = CliRunner()
    with patch("ghcli.commands.star.GitHubClient") as MockClient:
        MockClient.return_value = make_client(get_val=MOCK_STARRED)
        result = runner.invoke(star, ["list", "--json"])
    assert result.exit_code == 0
    assert "owner/repo" in result.output

def test_star_add():
    runner = CliRunner()
    with patch("ghcli.commands.star.GitHubClient") as MockClient:
        MockClient.return_value = make_client()
        result = runner.invoke(star, ["add", "owner/repo"])
    assert result.exit_code == 0
    assert "Starred" in result.output

def test_star_remove():
    runner = CliRunner()
    with patch("ghcli.commands.star.GitHubClient") as MockClient:
        MockClient.return_value = make_client()
        result = runner.invoke(star, ["remove", "owner/repo"])
    assert result.exit_code == 0
    assert "Unstarred" in result.output
