"""Tests for ghcli status command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from ghcli.commands.status import status


@pytest.fixture()
def runner():
    return CliRunner()


@pytest.fixture()
def mock_client():
    with patch("ghcli.commands.status.GitHubClient") as MockClient:
        client = MagicMock()
        MockClient.return_value = client
        yield client


@pytest.fixture()
def mock_user():
    return {
        "login": "testuser",
        "name": "Test User",
        "email": "test@example.com",
        "html_url": "https://github.com/testuser",
        "plan": {"name": "free"},
    }


@pytest.fixture()
def mock_rate():
    return {
        "resources": {
            "core": {"limit": 5000, "remaining": 4900, "reset": 9999999999},
            "search": {"limit": 30, "remaining": 28, "reset": 9999999999},
        }
    }


class TestStatusNotAuthenticated:
    def test_not_authenticated_table(self, runner):
        with patch("ghcli.commands.status.load_token", return_value=None):
            result = runner.invoke(status, [])
        assert result.exit_code == 0
        assert "Not authenticated" in result.output or "not authenticated" in result.output.lower()

    def test_not_authenticated_json(self, runner):
        with patch("ghcli.commands.status.load_token", return_value=None):
            result = runner.invoke(status, ["--json"])
        assert result.exit_code == 0
        import json

        data = json.loads(result.output)
        assert data["authenticated"] is False


class TestStatusAuthenticated:
    def test_status_table(self, runner, mock_client, mock_user, mock_rate):
        with patch("ghcli.commands.status.load_token", return_value="ghp_test"):
            mock_client.get.side_effect = [mock_user, mock_rate]
            result = runner.invoke(status, [])
        assert result.exit_code == 0
        assert "testuser" in result.output

    def test_status_json(self, runner, mock_client, mock_user, mock_rate):
        with patch("ghcli.commands.status.load_token", return_value="ghp_test"):
            mock_client.get.side_effect = [mock_user, mock_rate]
            result = runner.invoke(status, ["--json"])
        assert result.exit_code == 0
        import json

        data = json.loads(result.output)
        assert "user" in data
        assert data["user"]["login"] == "testuser"

    def test_status_rate_limit_table(self, runner, mock_client, mock_user, mock_rate):
        with patch("ghcli.commands.status.load_token", return_value="ghp_test"):
            mock_client.get.side_effect = [mock_user, mock_rate]
            result = runner.invoke(status, [])
        assert result.exit_code == 0
        assert "core" in result.output or "Rate" in result.output

    def test_status_user_fetch_error(self, runner, mock_client):
        with patch("ghcli.commands.status.load_token", return_value="ghp_test"):
            mock_client.get.side_effect = Exception("network error")
            result = runner.invoke(status, [])
        assert result.exit_code == 0
        assert "Failed" in result.output or "error" in result.output.lower()

    def test_status_rate_limit_fetch_error(self, runner, mock_client, mock_user):
        """Rate limit failure should not crash — gracefully degrade."""
        with patch("ghcli.commands.status.load_token", return_value="ghp_test"):
            mock_client.get.side_effect = [mock_user, Exception("rate limit error")]
            result = runner.invoke(status, [])
        assert result.exit_code == 0
        assert "testuser" in result.output

    def test_status_no_plan(self, runner, mock_client, mock_rate):
        user_no_plan = {
            "login": "testuser",
            "name": "Test User",
            "email": None,
            "html_url": "https://github.com/testuser",
            "plan": None,
        }
        with patch("ghcli.commands.status.load_token", return_value="ghp_test"):
            mock_client.get.side_effect = [user_no_plan, mock_rate]
            result = runner.invoke(status, [])
        assert result.exit_code == 0
        assert "testuser" in result.output

    def test_status_empty_resources(self, runner, mock_client, mock_user):
        rate_empty = {"resources": {}}
        with patch("ghcli.commands.status.load_token", return_value="ghp_test"):
            mock_client.get.side_effect = [mock_user, rate_empty]
            result = runner.invoke(status, [])
        assert result.exit_code == 0
