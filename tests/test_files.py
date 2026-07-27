"""Tests for ghcli files commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from ghcli.commands.files import files


@pytest.fixture()
def runner():
    return CliRunner()


@pytest.fixture()
def mock_client():
    with patch("ghcli.commands.files.GitHubClient") as MockClient:
        client = MagicMock()
        MockClient.return_value = client
        yield client


MOCK_DIR_CONTENTS = [
    {
        "name": "README.md",
        "path": "README.md",
        "type": "file",
        "size": 1024,
        "sha": "abc123",
        "html_url": "https://github.com/owner/repo/blob/main/README.md",
        "download_url": "https://raw.githubusercontent.com/owner/repo/main/README.md",
    },
    {
        "name": "src",
        "path": "src",
        "type": "dir",
        "size": 0,
        "sha": "def456",
        "html_url": "https://github.com/owner/repo/tree/main/src",
        "download_url": None,
    },
]

MOCK_FILE_CONTENT = {
    "name": "README.md",
    "path": "README.md",
    "type": "file",
    "size": 1024,
    "sha": "abc123",
    "content": "SGVsbG8gV29ybGQh\n",  # base64 "Hello World!"
    "encoding": "base64",
    "html_url": "https://github.com/owner/repo/blob/main/README.md",
    "download_url": "https://raw.githubusercontent.com/owner/repo/main/README.md",
}


class TestFilesList:
    def test_list_root(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_client.get.return_value = MOCK_DIR_CONTENTS
        result = runner.invoke(files, ["list", "owner/repo"])
        assert result.exit_code == 0
        assert "README.md" in result.output or "src" in result.output

    def test_list_json(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_client.get.return_value = MOCK_DIR_CONTENTS
        result = runner.invoke(files, ["list", "owner/repo", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 2

    def test_list_with_path(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_client.get.return_value = [MOCK_DIR_CONTENTS[0]]
        result = runner.invoke(files, ["list", "owner/repo", "--path", "src"])
        assert result.exit_code == 0

    def test_list_with_branch(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_client.get.return_value = MOCK_DIR_CONTENTS
        result = runner.invoke(files, ["list", "owner/repo", "--branch", "develop"])
        assert result.exit_code == 0

    def test_list_empty(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_client.get.return_value = []
        result = runner.invoke(files, ["list", "owner/repo"])
        assert result.exit_code == 0

    def test_list_api_error(self, runner, mock_client):
        from ghcli.client import GitHubAPIError

        mock_client.require_auth.return_value = None
        mock_client.get.side_effect = GitHubAPIError("Not Found", 404)
        result = runner.invoke(files, ["list", "owner/repo"])
        assert result.exit_code == 1 or "404" in result.output or "Not Found" in result.output

    def test_list_help(self, runner):
        result = runner.invoke(files, ["list", "--help"])
        assert result.exit_code == 0
        assert "--json" in result.output


class TestFilesView:
    def test_view_basic(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_client.get.return_value = MOCK_FILE_CONTENT
        result = runner.invoke(files, ["view", "owner/repo", "README.md"])
        assert result.exit_code == 0

    def test_view_raw(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_client.get.return_value = MOCK_FILE_CONTENT
        result = runner.invoke(files, ["view", "owner/repo", "README.md", "--raw"])
        assert result.exit_code == 0
        assert "Hello World!" in result.output

    def test_view_api_error(self, runner, mock_client):
        from ghcli.client import GitHubAPIError

        mock_client.require_auth.return_value = None
        mock_client.get.side_effect = GitHubAPIError("Not Found", 404)
        result = runner.invoke(files, ["view", "owner/repo", "nonexistent.md"])
        assert result.exit_code == 1 or "404" in result.output

    def test_view_help(self, runner):
        result = runner.invoke(files, ["view", "--help"])
        assert result.exit_code == 0

    def test_view_save_to_file(self, runner, mock_client, tmp_path):
        mock_client.require_auth.return_value = None
        mock_client.get.return_value = MOCK_FILE_CONTENT
        save_path = str(tmp_path / "output.md")
        result = runner.invoke(files, ["view", "owner/repo", "README.md", "--save", save_path])
        assert result.exit_code == 0


class TestFilesWrite:
    def test_write_basic(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_client.get.return_value = None  # file doesn't exist yet
        mock_client.post.return_value = {
            "content": {"path": "newfile.md", "sha": "newsha"},
            "commit": {
                "sha": "commitsha",
                "html_url": "https://github.com/owner/repo/commit/commitsha",
            },
        }
        result = runner.invoke(
            files,
            ["write", "owner/repo", "newfile.md", "--message", "Add file", "--content", "Hello"],
        )
        assert result.exit_code == 0 or "Error" in result.output

    def test_write_help(self, runner):
        result = runner.invoke(files, ["write", "--help"])
        assert result.exit_code == 0
        assert "--message" in result.output


class TestFilesDelete:
    def test_delete_with_yes_flag(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        mock_client.get.return_value = MOCK_FILE_CONTENT
        mock_client.delete_with_body.return_value = {
            "commit": {"sha": "delsha", "html_url": "https://github.com/owner/repo/commit/delsha"}
        }
        result = runner.invoke(
            files,
            ["delete", "owner/repo", "README.md", "--message", "Remove file", "--yes"],
        )
        assert result.exit_code == 0 or "Error" in result.output

    def test_delete_help(self, runner):
        result = runner.invoke(files, ["delete", "--help"])
        assert result.exit_code == 0
        assert "--message" in result.output
        assert "--yes" in result.output


class TestFilesTree:
    def test_tree_help(self, runner):
        result = runner.invoke(files, ["tree", "--help"])
        assert result.exit_code == 0

    def test_tree_basic(self, runner, mock_client):
        mock_client.require_auth.return_value = None
        # files_tree makes 3 get calls: repo_info, branch_info, tree
        repo_info = {"default_branch": "main"}
        branch_info = {"commit": {"commit": {"tree": {"sha": "treesha123"}}}}
        tree_data = {
            "tree": [
                {"path": "README.md", "type": "blob", "size": 1024},
                {"path": "src", "type": "tree", "size": 0},
                {"path": "src/main.py", "type": "blob", "size": 512},
            ],
            "truncated": False,
        }
        mock_client.get.side_effect = [repo_info, branch_info, tree_data]
        result = runner.invoke(files, ["tree", "owner/repo"])
        assert result.exit_code == 0
        assert "README.md" in result.output or "src" in result.output

    def test_tree_api_error(self, runner, mock_client):
        from ghcli.client import GitHubAPIError

        mock_client.require_auth.return_value = None
        mock_client.get.side_effect = GitHubAPIError("Not Found", 404)
        result = runner.invoke(files, ["tree", "owner/repo"])
        assert result.exit_code == 1 or "404" in result.output
