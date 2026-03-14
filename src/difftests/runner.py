"""Run generated tests and capture results."""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .generator import GeneratedTest


@dataclass
class RunResult:
    """Result of running a generated test file."""

    source_path: str
    test_path: str
    passed: bool
    output: str
    exit_code: int


def run_test(generated: GeneratedTest, test_dir: str | None = None) -> RunResult:
    """Write test to a temp file and run it with pytest."""
    if test_dir:
        Path(test_dir).mkdir(parents=True, exist_ok=True)
        test_path = str(Path(test_dir) / generated.suggested_filename)
        Path(test_path).write_text(generated.test_code, encoding="utf-8")
        cleanup = False
    else:
        tmp = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=generated.suggested_filename,
            delete=False,
            encoding="utf-8",
        )
        tmp.write(generated.test_code)
        tmp.flush()
        test_path = tmp.name
        cleanup = True

    runner_cmd = _get_runner_cmd(generated.framework, test_path)

    try:
        result = subprocess.run(
            runner_cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        output = result.stdout + result.stderr
        return RunResult(
            source_path=generated.source_path,
            test_path=test_path,
            passed=result.returncode == 0,
            output=output,
            exit_code=result.returncode,
        )
    except subprocess.TimeoutExpired:
        return RunResult(
            source_path=generated.source_path,
            test_path=test_path,
            passed=False,
            output="Test run timed out after 60 seconds.",
            exit_code=1,
        )
    finally:
        if cleanup:
            try:
                Path(test_path).unlink()
            except OSError:
                pass


def _get_runner_cmd(framework: str, test_path: str) -> list[str]:
    if framework in ("pytest", "unittest"):
        return ["python", "-m", "pytest", test_path, "-v", "--tb=short"]
    elif framework in ("jest", "vitest"):
        return ["npx", framework, test_path, "--no-coverage"]
    elif framework == "rspec":
        return ["rspec", test_path]
    elif framework == "go":
        return ["go", "test", test_path]
    else:
        return ["python", "-m", "pytest", test_path, "-v", "--tb=short"]
