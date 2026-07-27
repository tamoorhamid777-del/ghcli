"""
Tests for ghcli auth commands.
"""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from ghcli.main import cli


class TestAuthSetup:
    """Tests for `ghcli auth setup`."""

    def test_setup_with_valid_token(self, cli_runner):
        """Test successful token setup with a valid token."""
        mock_user = {
            "login": "testuser",
            "name": "Test User",
            "email": "test@example.com",
            "public_repos": 5,
        }

        with patch("ghcli.commands.auth.GitHubClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.get.return_value = mock_user
            mock_client_cls.return_value = mock_client

            with patch("ghcli.commands.auth.save_token") as mock_save:
                result = cli_runner.invoke(cli, ["auth", "setup", "--token", "ghp_validtoken123"])

        assert result.exit_code == 0
        assert "testuser" in result.output
        mock_save.assert_called_once_with("ghp_validtoken123")

    def test_setup_with_empty_token_fails(self, cli_runner):
        """Test that an empty token is rejected (mock Rich Prompt so it never blocks)."""
        # Rich's Prompt.ask ignores Click's input stream; mock it to return ""
        with patch("ghcli.commands.auth.Prompt.ask", return_value=""):
            result = cli_runner.invoke(cli, ["auth", "setup"])
        assert "empty" in result.output.lower() or "cannot" in result.output.lower()

    def test_setup_with_invalid_token_fails(self, cli_runner):
        """Test that an invalid token shows an error."""
        from ghcli.client import GitHubAPIError

        with patch("ghcli.commands.auth.GitHubClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.get.side_effect = GitHubAPIError("401 Unauthorized")
            mock_client_cls.return_value = mock_client

            result = cli_runner.invoke(cli, ["auth", "setup", "--token", "ghp_badtoken"])

        assert result.exit_code != 0 or any(
            w in result.output.lower() for w in ("failed", "invalid", "error", "401")
        )


class TestAuthStatus:
    """Tests for `ghcli auth status`."""

    def test_status_when_not_authenticated(self, cli_runner):
        """Test status output when no token is stored."""
        with patch("ghcli.commands.auth.load_token", return_value=None):
            result = cli_runner.invoke(cli, ["auth", "status"])

        assert result.exit_code == 0
        assert "not authenticated" in result.output.lower() or "setup" in result.output.lower()

    def test_status_when_authenticated(self, cli_runner, mock_github_user):
        """Test status output when a valid token is stored."""
        with patch("ghcli.commands.auth.load_token", return_value="ghp_test"):
            with patch("ghcli.commands.auth.GitHubClient") as mock_client_cls:
                mock_client = MagicMock()
                mock_client.get.return_value = mock_github_user
                mock_client_cls.return_value = mock_client

                result = cli_runner.invoke(cli, ["auth", "status"])

        assert result.exit_code == 0
        assert "testuser" in result.output


class TestAuthLogout:
    """Tests for `ghcli auth logout`."""

    def test_logout_when_no_token(self, cli_runner):
        """Test logout when no token is stored."""
        with patch("ghcli.commands.auth.token_is_set", return_value=False):
            result = cli_runner.invoke(cli, ["auth", "logout"])

        assert result.exit_code == 0
        assert "no token" in result.output.lower()

    def test_logout_confirmed(self, cli_runner):
        """Test successful logout with user confirmation."""
        with patch("ghcli.commands.auth.token_is_set", return_value=True):
            with patch("ghcli.commands.auth.delete_token") as mock_delete:
                # Simulate user confirming with 'y'
                result = cli_runner.invoke(cli, ["auth", "logout"], input="y\n")

        assert result.exit_code == 0
        mock_delete.assert_called_once()
