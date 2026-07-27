"""Tests for ghcli gist commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from ghcli.commands.gist import gist

MOCK_GISTS = [
    {
        "id": "abc123def456",
        "description": "My gist",
        "public": True,
        "files": {"test.py": {}},
        "updated_at": "2026-01-01T00:00:00Z",
    }
]
MOCK_GIST = {
    "id": "abc123def456",
    "description": "My gist",
    "public": True,
    "files": {"test.py": {"content": "print('hello')", "language": "Python"}},
    "updated_at": "2026-01-01T00:00:00Z",
}


def make_client(get_val=None, post_val=None):
    client = MagicMock()
    client.get.return_value = get_val
    client.post.return_value = post_val or {
        "id": "abc123",
        "html_url": "https://gist.github.com/abc123",
    }
    return client


def test_gist_list():
    runner = CliRunner()
    with patch("ghcli.commands.gist.GitHubClient") as MockClient:
        MockClient.return_value = make_client(get_val=MOCK_GISTS)
        result = runner.invoke(gist, ["list"])
    assert result.exit_code == 0
    assert "My gist" in result.output


def test_gist_list_json():
    runner = CliRunner()
    with patch("ghcli.commands.gist.GitHubClient") as MockClient:
        MockClient.return_value = make_client(get_val=MOCK_GISTS)
        result = runner.invoke(gist, ["list", "--json"])
    assert result.exit_code == 0
    assert "abc123def456" in result.output


def test_gist_view():
    runner = CliRunner()
    with patch("ghcli.commands.gist.GitHubClient") as MockClient:
        MockClient.return_value = make_client(get_val=MOCK_GIST)
        result = runner.invoke(gist, ["view", "abc123def456"])
    assert result.exit_code == 0


def test_gist_create():
    runner = CliRunner()
    with patch("ghcli.commands.gist.GitHubClient") as MockClient:
        MockClient.return_value = make_client()
        result = runner.invoke(
            gist, ["create", "hello.py", "print('hello')", "--description", "Test"]
        )
    assert result.exit_code == 0
    assert "created" in result.output.lower()


def test_gist_no_auth():
    runner = CliRunner()
    from ghcli.client import GitHubAPIError

    with patch("ghcli.commands.gist.GitHubClient") as MockClient:
        MockClient.return_value.require_auth.side_effect = SystemExit(1)
        result = runner.invoke(gist, ["list"])
    assert result.exit_code == 1
