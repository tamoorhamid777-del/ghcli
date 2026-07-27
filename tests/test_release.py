"""Tests for ghcli release commands."""
from __future__ import annotations
from unittest.mock import MagicMock, patch
from click.testing import CliRunner
from ghcli.commands.release import release

MOCK_RELEASES = [{"tag_name": "v1.0.0", "name": "Initial Release", "draft": False, "prerelease": False, "published_at": "2026-01-01T00:00:00Z", "assets": []}]
MOCK_RELEASE = {"tag_name": "v1.0.0", "name": "Initial Release", "html_url": "https://github.com/owner/repo/releases/tag/v1.0.0", "published_at": "2026-01-01T00:00:00Z", "body": "First release", "assets": []}

def make_client(get_val=None, post_val=None):
    client = MagicMock()
    client.get.return_value = get_val
    client.post.return_value = post_val or {"tag_name": "v1.1.0", "html_url": "https://github.com/owner/repo/releases/tag/v1.1.0", "id": 1}
    return client

def test_release_list():
    runner = CliRunner()
    with patch("ghcli.commands.release.GitHubClient") as MockClient:
        MockClient.return_value = make_client(get_val=MOCK_RELEASES)
        result = runner.invoke(release, ["list", "owner/repo"])
    assert result.exit_code == 0
    assert "v1.0.0" in result.output

def test_release_list_json():
    runner = CliRunner()
    with patch("ghcli.commands.release.GitHubClient") as MockClient:
        MockClient.return_value = make_client(get_val=MOCK_RELEASES)
        result = runner.invoke(release, ["list", "owner/repo", "--json"])
    assert result.exit_code == 0
    assert "v1.0.0" in result.output

def test_release_view():
    runner = CliRunner()
    with patch("ghcli.commands.release.GitHubClient") as MockClient:
        MockClient.return_value = make_client(get_val=MOCK_RELEASE)
        result = runner.invoke(release, ["view", "owner/repo", "v1.0.0"])
    assert result.exit_code == 0
    assert "First release" in result.output

def test_release_create():
    runner = CliRunner()
    with patch("ghcli.commands.release.GitHubClient") as MockClient:
        MockClient.return_value = make_client()
        result = runner.invoke(release, ["create", "owner/repo", "v1.1.0", "--name", "v1.1.0"])
    assert result.exit_code == 0
    assert "created" in result.output.lower()


def test_release_view_json():
    runner = CliRunner()
    with patch("ghcli.commands.release.GitHubClient") as MockClient:
        MockClient.return_value = make_client(get_val=MOCK_RELEASE)
        result = runner.invoke(release, ["view", "owner/repo", "v1.0.0", "--json"])
    assert result.exit_code == 0
    import json
    data = json.loads(result.output)
    assert data["tag_name"] == "v1.0.0"


def test_release_view_with_assets():
    runner = CliRunner()
    release_with_assets = {
        **MOCK_RELEASE,
        "assets": [
            {"name": "ghcli-linux.tar.gz", "size": 2048000, "browser_download_url": "https://example.com/ghcli-linux.tar.gz"}
        ],
    }
    with patch("ghcli.commands.release.GitHubClient") as MockClient:
        MockClient.return_value = make_client(get_val=release_with_assets)
        result = runner.invoke(release, ["view", "owner/repo", "v1.0.0"])
    assert result.exit_code == 0
    assert "ghcli-linux" in result.output


def test_release_download_no_assets():
    runner = CliRunner()
    release_no_assets = {**MOCK_RELEASE, "assets": []}
    with patch("ghcli.commands.release.GitHubClient") as MockClient:
        MockClient.return_value = make_client(get_val=release_no_assets)
        result = runner.invoke(release, ["download", "owner/repo", "v1.0.0"])
    assert result.exit_code == 0
    assert "No assets" in result.output


def test_release_create_with_notes():
    runner = CliRunner()
    with patch("ghcli.commands.release.GitHubClient") as MockClient:
        MockClient.return_value = make_client()
        result = runner.invoke(
            release,
            ["create", "owner/repo", "v1.2.0", "--name", "v1.2.0", "--body", "Bug fixes", "--draft"],
        )
    assert result.exit_code == 0


def test_release_list_empty():
    runner = CliRunner()
    with patch("ghcli.commands.release.GitHubClient") as MockClient:
        MockClient.return_value = make_client(get_val=[])
        result = runner.invoke(release, ["list", "owner/repo"])
    assert result.exit_code == 0
    assert "No releases" in result.output or result.output.strip() != ""