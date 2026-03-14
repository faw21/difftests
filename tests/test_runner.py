"""Tests for the test runner module."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from difftests.generator import GeneratedTest
from difftests.runner import RunResult, _get_runner_cmd, run_test


class TestGetRunnerCmd:
    def test_pytest_framework(self):
        cmd = _get_runner_cmd("pytest", "/tmp/test_foo.py")
        assert "pytest" in cmd
        assert "/tmp/test_foo.py" in cmd

    def test_unittest_framework(self):
        cmd = _get_runner_cmd("unittest", "/tmp/test_foo.py")
        assert "pytest" in cmd  # we use pytest to run unittest too

    def test_jest_framework(self):
        cmd = _get_runner_cmd("jest", "/tmp/foo.test.js")
        assert "jest" in cmd

    def test_vitest_framework(self):
        cmd = _get_runner_cmd("vitest", "/tmp/foo.test.ts")
        assert "vitest" in cmd

    def test_rspec_framework(self):
        cmd = _get_runner_cmd("rspec", "/tmp/foo_spec.rb")
        assert "rspec" in cmd

    def test_go_framework(self):
        cmd = _get_runner_cmd("go", "/tmp/foo_test.go")
        assert "go" in cmd

    def test_unknown_defaults_to_pytest(self):
        cmd = _get_runner_cmd("unknown", "/tmp/test.py")
        assert "pytest" in cmd


class TestRunResult:
    def test_passed_is_true(self):
        result = RunResult(
            source_path="a.py",
            test_path="/tmp/test_a.py",
            passed=True,
            output="1 passed",
            exit_code=0,
        )
        assert result.passed is True

    def test_failed_is_false(self):
        result = RunResult(
            source_path="a.py",
            test_path="/tmp/test_a.py",
            passed=False,
            output="1 failed",
            exit_code=1,
        )
        assert result.passed is False


class TestRunTest:
    def _make_test(self, code: str = "def test_x(): assert True") -> GeneratedTest:
        return GeneratedTest(
            source_path="src/auth.py",
            test_code=code,
            framework="pytest",
            language="python",
        )

    def test_runs_passing_test(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "1 passed"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = run_test(self._make_test())

        assert result.passed is True
        assert result.exit_code == 0

    def test_runs_failing_test(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "1 failed"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = run_test(self._make_test("def test_x(): assert False"))

        assert result.passed is False
        assert result.exit_code == 1

    def test_handles_timeout(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(["pytest"], 60)):
            result = run_test(self._make_test())

        assert result.passed is False
        assert "timed out" in result.output.lower()

    def test_saves_to_output_dir(self, tmp_path):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = run_test(self._make_test(), test_dir=str(tmp_path))

        assert Path(result.test_path).exists()
        assert str(tmp_path) in result.test_path

    def test_output_contains_stdout_and_stderr(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "stdout text"
        mock_result.stderr = "stderr text"

        with patch("subprocess.run", return_value=mock_result):
            result = run_test(self._make_test())

        assert "stdout text" in result.output
        assert "stderr text" in result.output

    def test_temp_file_cleaned_up(self, tmp_path):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = run_test(self._make_test(), test_dir=None)

        # temp file should be cleaned up
        assert not Path(result.test_path).exists()

    def test_source_path_preserved(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        test = self._make_test()

        with patch("subprocess.run", return_value=mock_result):
            result = run_test(test)

        assert result.source_path == "src/auth.py"
