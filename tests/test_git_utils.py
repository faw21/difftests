"""Tests for git_utils module."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from difftests.git_utils import (
    DiffResult,
    FileDiff,
    _detect_language,
    _parse_diff_into_files,
    get_branch_diff,
    get_file_diff,
    get_staged_diff,
    is_git_repo,
)


class TestDetectLanguage:
    def test_python(self):
        assert _detect_language("src/foo.py") == "python"

    def test_javascript(self):
        assert _detect_language("app.js") == "javascript"

    def test_typescript(self):
        assert _detect_language("component.ts") == "typescript"

    def test_tsx(self):
        assert _detect_language("app.tsx") == "typescript"

    def test_go(self):
        assert _detect_language("main.go") == "go"

    def test_ruby(self):
        assert _detect_language("model.rb") == "ruby"

    def test_unknown(self):
        assert _detect_language("file.xyz") == "python"

    def test_case_insensitive(self):
        assert _detect_language("FILE.PY") == "python"


class TestParseDiffIntoFiles:
    def test_parses_single_file(self):
        diff = (
            "diff --git a/src/auth.py b/src/auth.py\n"
            "index abc..def 100644\n"
            "--- a/src/auth.py\n"
            "+++ b/src/auth.py\n"
            "@@ -1,3 +1,5 @@\n"
            " def foo():\n"
            "+    return 42\n"
        )
        with patch("difftests.git_utils._get_file_content", return_value="def foo():\n    return 42"):
            files = _parse_diff_into_files(diff)
        assert len(files) == 1
        assert files[0].path == "src/auth.py"
        assert files[0].language == "python"

    def test_skips_non_testable_files(self):
        diff = (
            "diff --git a/README.md b/README.md\n"
            "--- a/README.md\n"
            "+++ b/README.md\n"
            "@@ -1 +1 @@\n"
            "+# Updated\n"
        )
        with patch("difftests.git_utils._get_file_content", return_value=""):
            files = _parse_diff_into_files(diff)
        assert len(files) == 0

    def test_parses_multiple_files(self):
        diff = (
            "diff --git a/src/a.py b/src/a.py\n"
            "--- a/src/a.py\n"
            "+++ b/src/a.py\n"
            "@@ -0,0 +1 @@\n"
            "+x = 1\n"
            "diff --git a/src/b.js b/src/b.js\n"
            "--- a/src/b.js\n"
            "+++ b/src/b.js\n"
            "@@ -0,0 +1 @@\n"
            "+const y = 2;\n"
        )
        with patch("difftests.git_utils._get_file_content", return_value=""):
            files = _parse_diff_into_files(diff)
        assert len(files) == 2
        assert files[0].path == "src/a.py"
        assert files[1].path == "src/b.js"


class TestDiffResult:
    def test_is_empty_when_no_files(self):
        result = DiffResult()
        assert result.is_empty is True

    def test_not_empty_with_files(self):
        result = DiffResult(files=[FileDiff(path="a.py", diff_text="+")])
        assert result.is_empty is False

    def test_file_count(self):
        result = DiffResult(files=[
            FileDiff(path="a.py", diff_text="+"),
            FileDiff(path="b.py", diff_text="+"),
        ])
        assert result.file_count == 2


class TestIsGitRepo:
    def test_returns_true_in_git_repo(self, tmp_path):
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        with patch("difftests.git_utils._run_git", return_value="true\n"):
            assert is_git_repo() is True

    def test_returns_false_outside_git_repo(self):
        with patch("difftests.git_utils._run_git", side_effect=RuntimeError("not a git repo")):
            assert is_git_repo() is False


class TestGetStagedDiff:
    def test_returns_empty_when_no_staged(self):
        with patch("difftests.git_utils._run_git", return_value=""):
            result = get_staged_diff()
        assert result.is_empty is True

    def test_returns_diff_when_staged(self):
        mock_diff = (
            "diff --git a/src/foo.py b/src/foo.py\n"
            "--- a/src/foo.py\n"
            "+++ b/src/foo.py\n"
            "@@ -1 +1 @@\n"
            "+def bar(): pass\n"
        )
        with patch("difftests.git_utils._run_git", return_value=mock_diff), \
             patch("difftests.git_utils._get_file_content", return_value="def bar(): pass"):
            result = get_staged_diff()
        assert not result.is_empty
        assert result.files[0].path == "src/foo.py"


class TestGetBranchDiff:
    def test_returns_diff_vs_branch(self):
        mock_diff = (
            "diff --git a/src/auth.py b/src/auth.py\n"
            "--- a/src/auth.py\n"
            "+++ b/src/auth.py\n"
            "@@ -0,0 +1 @@\n"
            "+def login(): pass\n"
        )
        with patch("difftests.git_utils._run_git", return_value=mock_diff), \
             patch("difftests.git_utils._get_file_content", return_value="def login(): pass"):
            result = get_branch_diff("main")
        assert not result.is_empty

    def test_falls_back_when_origin_fails(self):
        call_count = 0

        def mock_run(args, cwd=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("no remote 'origin'")
            return ""

        with patch("difftests.git_utils._run_git", side_effect=mock_run):
            result = get_branch_diff("main")
        assert result.is_empty
