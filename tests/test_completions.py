"""Tests for ghcli completions command."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from click.testing import CliRunner

from ghcli.commands.completions import completions


@pytest.fixture()
def runner():
    return CliRunner()


class TestCompletionsHelp:
    def test_completions_help(self, runner):
        result = runner.invoke(completions, ["--help"])
        assert result.exit_code == 0
        assert "completion" in result.output.lower()

    def test_generate_help(self, runner):
        result = runner.invoke(completions, ["generate", "--help"])
        assert result.exit_code == 0
        assert "bash" in result.output
        assert "zsh" in result.output
        assert "fish" in result.output

    def test_install_help(self, runner):
        result = runner.invoke(completions, ["install", "--help"])
        assert result.exit_code == 0


class TestCompletionsGenerate:
    def test_generate_bash(self, runner):
        with patch("ghcli.commands.completions._generate_completion", return_value="# bash completion\n"):
            result = runner.invoke(completions, ["generate", "bash"])
        assert result.exit_code == 0

    def test_generate_zsh(self, runner):
        with patch("ghcli.commands.completions._generate_completion", return_value="# zsh completion\n"):
            result = runner.invoke(completions, ["generate", "zsh"])
        assert result.exit_code == 0

    def test_generate_fish(self, runner):
        with patch("ghcli.commands.completions._generate_completion", return_value="# fish completion\n"):
            result = runner.invoke(completions, ["generate", "fish"])
        assert result.exit_code == 0

    def test_generate_invalid_shell(self, runner):
        result = runner.invoke(completions, ["generate", "powershell"])
        assert result.exit_code != 0

    def test_generate_with_install_flag(self, runner):
        result = runner.invoke(completions, ["generate", "bash", "--install"])
        assert result.exit_code == 0
        assert "bashrc" in result.output or "bash" in result.output.lower()

    def test_generate_zsh_install_instructions(self, runner):
        result = runner.invoke(completions, ["generate", "zsh", "--install"])
        assert result.exit_code == 0
        assert "zshrc" in result.output or "zsh" in result.output.lower()

    def test_generate_fish_install_instructions(self, runner):
        result = runner.invoke(completions, ["generate", "fish", "--install"])
        assert result.exit_code == 0
        assert "fish" in result.output.lower()


class TestCompletionsInstall:
    def test_install_bash(self, runner):
        result = runner.invoke(completions, ["install", "bash"])
        assert result.exit_code == 0
        assert "bash" in result.output.lower()

    def test_install_zsh(self, runner):
        result = runner.invoke(completions, ["install", "zsh"])
        assert result.exit_code == 0
        assert "zsh" in result.output.lower()

    def test_install_fish(self, runner):
        result = runner.invoke(completions, ["install", "fish"])
        assert result.exit_code == 0
        assert "fish" in result.output.lower()

    def test_install_auto_detect(self, runner):
        """Without shell arg, should auto-detect from $SHELL env var."""
        with patch.dict("os.environ", {"SHELL": "/bin/bash"}):
            result = runner.invoke(completions, ["install"])
        assert result.exit_code == 0
        assert "bash" in result.output.lower()

    def test_install_auto_detect_unknown_shell(self, runner):
        """Unknown shell falls back to bash."""
        with patch.dict("os.environ", {"SHELL": "/bin/tcsh"}):
            result = runner.invoke(completions, ["install"])
        assert result.exit_code == 0
