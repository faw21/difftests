"""Tests for the CLI module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from difftests.cli import main
from difftests.generator import GenerationResult, GeneratedTest
from difftests.git_utils import DiffResult, FileDiff


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_diff_one_file():
    return DiffResult(files=[
        FileDiff(
            path="src/auth.py",
            diff_text="+def login(user, pwd):\n+    return True",
            original_content="def login(user, pwd):\n    return True\n",
            language="python",
        )
    ])


@pytest.fixture
def mock_generated_result():
    return GenerationResult(
        tests=[GeneratedTest(
            source_path="src/auth.py",
            test_code=(
                "import pytest\n"
                "from src.auth import login\n\n"
                "def test_login_returns_true():\n"
                "    assert login('user', 'pwd') is True\n"
            ),
            framework="pytest",
            language="python",
        )],
        model_label="claude/default",
    )


class TestMainCLI:
    def test_version(self, runner):
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_fails_outside_git_repo(self, runner):
        with patch("difftests.cli.is_git_repo", return_value=False):
            result = runner.invoke(main, [])
        assert result.exit_code == 1
        assert "git repository" in result.output.lower()

    def test_shows_no_staged_message(self, runner):
        with patch("difftests.cli.is_git_repo", return_value=True), \
             patch("difftests.cli.get_staged_diff", return_value=DiffResult()):
            result = runner.invoke(main, [])
        assert result.exit_code == 0
        assert "staged" in result.output.lower()

    def test_generates_tests_for_staged(self, runner, mock_diff_one_file, mock_generated_result):
        with patch("difftests.cli.is_git_repo", return_value=True), \
             patch("difftests.cli.get_staged_diff", return_value=mock_diff_one_file), \
             patch("difftests.cli.get_provider", return_value=MagicMock()), \
             patch("difftests.cli.generate_tests", return_value=mock_generated_result):
            result = runner.invoke(main, [])
        assert result.exit_code == 0
        assert "test_auth" in result.output or "auth" in result.output

    def test_diff_branch_mode(self, runner, mock_diff_one_file, mock_generated_result):
        with patch("difftests.cli.is_git_repo", return_value=True), \
             patch("difftests.cli.get_branch_diff", return_value=mock_diff_one_file) as mock_branch, \
             patch("difftests.cli.get_provider", return_value=MagicMock()), \
             patch("difftests.cli.generate_tests", return_value=mock_generated_result):
            result = runner.invoke(main, ["--diff", "main"])
        assert result.exit_code == 0
        mock_branch.assert_called_once_with(base="main")

    def test_file_mode(self, runner, mock_diff_one_file, mock_generated_result):
        with patch("difftests.cli.is_git_repo", return_value=True), \
             patch("difftests.cli.get_file_diff", return_value=mock_diff_one_file) as mock_file, \
             patch("difftests.cli.get_provider", return_value=MagicMock()), \
             patch("difftests.cli.generate_tests", return_value=mock_generated_result):
            result = runner.invoke(main, ["--file", "src/auth.py"])
        assert result.exit_code == 0
        mock_file.assert_called_once_with("src/auth.py", base=None)

    def test_raw_mode_prints_only_code(self, runner, mock_diff_one_file, mock_generated_result):
        with patch("difftests.cli.is_git_repo", return_value=True), \
             patch("difftests.cli.get_staged_diff", return_value=mock_diff_one_file), \
             patch("difftests.cli.get_provider", return_value=MagicMock()), \
             patch("difftests.cli.generate_tests", return_value=mock_generated_result):
            result = runner.invoke(main, ["--raw"])
        assert result.exit_code == 0
        # Raw mode should not contain Rich panel formatting
        assert "Provider:" not in result.output
        assert "def test_login" in result.output

    def test_provider_invalid(self, runner, mock_diff_one_file):
        with patch("difftests.cli.is_git_repo", return_value=True), \
             patch("difftests.cli.get_staged_diff", return_value=mock_diff_one_file):
            result = runner.invoke(main, ["--provider", "invalid_provider"])
        assert result.exit_code != 0

    def test_copy_clipboard(self, runner, mock_diff_one_file, mock_generated_result):
        with patch("difftests.cli.is_git_repo", return_value=True), \
             patch("difftests.cli.get_staged_diff", return_value=mock_diff_one_file), \
             patch("difftests.cli.get_provider", return_value=MagicMock()), \
             patch("difftests.cli.generate_tests", return_value=mock_generated_result), \
             patch("difftests.cli.pyperclip.copy") as mock_copy:
            result = runner.invoke(main, ["--copy"])
        assert result.exit_code == 0
        mock_copy.assert_called_once()

    def test_output_dir_saves_file(self, runner, mock_diff_one_file, mock_generated_result, tmp_path):
        with patch("difftests.cli.is_git_repo", return_value=True), \
             patch("difftests.cli.get_staged_diff", return_value=mock_diff_one_file), \
             patch("difftests.cli.get_provider", return_value=MagicMock()), \
             patch("difftests.cli.generate_tests", return_value=mock_generated_result):
            result = runner.invoke(main, ["--output", str(tmp_path)])
        assert result.exit_code == 0
        saved_files = list(tmp_path.iterdir())
        assert len(saved_files) == 1
        assert "auth" in saved_files[0].name

    def test_provider_error_shown(self, runner, mock_diff_one_file):
        with patch("difftests.cli.is_git_repo", return_value=True), \
             patch("difftests.cli.get_staged_diff", return_value=mock_diff_one_file), \
             patch("difftests.cli.get_provider", side_effect=ValueError("API key not set")):
            result = runner.invoke(main, [])
        assert result.exit_code == 1
        assert "API key" in result.output

    def test_generation_error_shown(self, runner, mock_diff_one_file):
        with patch("difftests.cli.is_git_repo", return_value=True), \
             patch("difftests.cli.get_staged_diff", return_value=mock_diff_one_file), \
             patch("difftests.cli.get_provider", return_value=MagicMock()), \
             patch("difftests.cli.generate_tests", side_effect=Exception("LLM unavailable")):
            result = runner.invoke(main, [])
        assert result.exit_code == 1
        assert "failed" in result.output.lower() or "unavailable" in result.output.lower()
