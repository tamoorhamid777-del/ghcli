"""
Shared pytest fixtures for ghcli tests.
"""

import pytest
from click.testing import CliRunner
from unittest.mock import patch


@pytest.fixture
def cli_runner():
    """Provide a Click test runner."""
    return CliRunner()


@pytest.fixture
def mock_token():
    """Mock a stored GitHub token so tests don't need a real keyring."""
    with patch("ghcli.auth_store.load_token", return_value="ghp_test_token_12345"):
        with patch("ghcli.auth_store.token_is_set", return_value=True):
            yield "ghp_test_token_12345"


@pytest.fixture
def mock_github_user():
    """Return a mock GitHub user API response."""
    return {
        "login": "testuser",
        "name": "Test User",
        "email": "test@example.com",
        "public_repos": 42,
        "total_private_repos": 10,
        "followers": 100,
        "following": 50,
    }


@pytest.fixture
def mock_repo():
    """Return a mock GitHub repository API response."""
    return {
        "id": 123456,
        "name": "my-repo",
        "full_name": "testuser/my-repo",
        "description": "A test repository",
        "private": False,
        "html_url": "https://github.com/testuser/my-repo",
        "clone_url": "https://github.com/testuser/my-repo.git",
        "ssh_url": "git@github.com:testuser/my-repo.git",
        "stargazers_count": 42,
        "forks_count": 7,
        "open_issues_count": 3,
        "language": "Python",
        "default_branch": "main",
        "topics": ["python", "cli", "github"],
        "updated_at": "2024-07-27T12:00:00Z",
        "created_at": "2024-01-01T00:00:00Z",
    }
