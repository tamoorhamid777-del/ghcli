"""Tests for ghcli notifications commands."""
from __future__ import annotations
from unittest.mock import MagicMock, patch
from click.testing import CliRunner
from ghcli.commands.notifications import notifications

MOCK_NOTIFS = [{"id": "1", "repository": {"full_name": "owner/repo"}, "subject": {"type": "Issue", "title": "Bug found"}, "updated_at": "2026-01-01T00:00:00Z"}]

def make_client(get_val=None):
    client = MagicMock()
    client.get.return_value = get_val
    client.patch.return_value = None
    client.put.return_value = None
    return client

def test_notifications_list():
    runner = CliRunner()
    with patch("ghcli.commands.notifications.GitHubClient") as MockClient:
        MockClient.return_value = make_client(get_val=MOCK_NOTIFS)
        result = runner.invoke(notifications, ["list"])
    assert result.exit_code == 0
    assert "Bug found" in result.output

def test_notifications_list_empty():
    runner = CliRunner()
    with patch("ghcli.commands.notifications.GitHubClient") as MockClient:
        MockClient.return_value = make_client(get_val=[])
        result = runner.invoke(notifications, ["list"])
    assert result.exit_code == 0
    assert "No unread" in result.output

def test_notifications_read():
    runner = CliRunner()
    with patch("ghcli.commands.notifications.GitHubClient") as MockClient:
        MockClient.return_value = make_client()
        result = runner.invoke(notifications, ["read", "123"])
    assert result.exit_code == 0
    assert "marked as read" in result.output

def test_notifications_read_all():
    runner = CliRunner()
    with patch("ghcli.commands.notifications.GitHubClient") as MockClient:
        MockClient.return_value = make_client()
        result = runner.invoke(notifications, ["read-all", "--yes"])
    assert result.exit_code == 0
    assert "All notifications" in result.output
