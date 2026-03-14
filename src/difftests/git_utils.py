"""Git utilities for extracting diffs and file context."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FileDiff:
    """Represents a single file's changes."""

    path: str
    diff_text: str
    original_content: str = ""
    language: str = "python"


@dataclass
class DiffResult:
    """Collection of file diffs from git."""

    files: list[FileDiff] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return len(self.files) == 0

    @property
    def file_count(self) -> int:
        return len(self.files)


_LANGUAGE_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "javascript",
    ".tsx": "typescript",
    ".rb": "ruby",
    ".go": "go",
    ".java": "java",
    ".cs": "csharp",
    ".rs": "rust",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
}

_TESTABLE_EXTENSIONS = set(_LANGUAGE_MAP.keys())


def _detect_language(path: str) -> str:
    ext = Path(path).suffix.lower()
    return _LANGUAGE_MAP.get(ext, "python")


def _run_git(args: list[str], cwd: str | None = None) -> str:
    result = subprocess.run(
        ["git"] + args,
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return result.stdout


def is_git_repo() -> bool:
    try:
        _run_git(["rev-parse", "--is-inside-work-tree"])
        return True
    except (RuntimeError, FileNotFoundError):
        return False


def _get_file_content(path: str) -> str:
    """Get current content of a file."""
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeDecodeError):
        return ""


def _parse_diff_into_files(diff_text: str) -> list[FileDiff]:
    """Split a full git diff into per-file FileDiff objects."""
    files: list[FileDiff] = []
    current_path: str | None = None
    current_lines: list[str] = []

    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            if current_path and current_lines:
                ext = Path(current_path).suffix.lower()
                if ext in _TESTABLE_EXTENSIONS:
                    files.append(FileDiff(
                        path=current_path,
                        diff_text="\n".join(current_lines),
                        original_content=_get_file_content(current_path),
                        language=_detect_language(current_path),
                    ))
            current_path = None
            current_lines = [line]
        elif line.startswith("+++ b/") and current_path is None:
            current_path = line[6:]
            current_lines.append(line)
        else:
            current_lines.append(line)

    if current_path and current_lines:
        ext = Path(current_path).suffix.lower()
        if ext in _TESTABLE_EXTENSIONS:
            files.append(FileDiff(
                path=current_path,
                diff_text="\n".join(current_lines),
                original_content=_get_file_content(current_path),
                language=_detect_language(current_path),
            ))

    return files


def get_staged_diff() -> DiffResult:
    """Get diff of staged changes."""
    diff_text = _run_git(["diff", "--cached"])
    if not diff_text.strip():
        return DiffResult()
    return DiffResult(files=_parse_diff_into_files(diff_text))


def get_branch_diff(base: str) -> DiffResult:
    """Get diff of all changes vs base branch."""
    try:
        diff_text = _run_git(["diff", f"origin/{base}...HEAD"])
    except RuntimeError:
        diff_text = ""

    if not diff_text.strip():
        # Try without origin/ prefix
        try:
            diff_text = _run_git(["diff", f"{base}...HEAD"])
        except RuntimeError:
            try:
                diff_text = _run_git(["diff", base])
            except RuntimeError:
                diff_text = ""

    if not diff_text.strip():
        return DiffResult()
    return DiffResult(files=_parse_diff_into_files(diff_text))


def get_file_diff(file_path: str, base: str | None = None) -> DiffResult:
    """Get diff for a specific file."""
    if base:
        diff_text = _run_git(["diff", f"origin/{base}...HEAD", "--", file_path])
        if not diff_text.strip():
            diff_text = _run_git(["diff", base, "--", file_path])
    else:
        diff_text = _run_git(["diff", "--cached", "--", file_path])
        if not diff_text.strip():
            diff_text = _run_git(["diff", "HEAD", "--", file_path])

    if not diff_text.strip():
        # Just show full file content as "new file"
        content = _get_file_content(file_path)
        if content:
            lang = _detect_language(file_path)
            return DiffResult(files=[FileDiff(
                path=file_path,
                diff_text=f"--- /dev/null\n+++ b/{file_path}\n" + "\n".join(f"+{l}" for l in content.splitlines()),
                original_content=content,
                language=lang,
            )])
        return DiffResult()

    return DiffResult(files=_parse_diff_into_files(diff_text))
