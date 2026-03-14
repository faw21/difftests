"""CLI entry point for difftests."""

from __future__ import annotations

import sys
from pathlib import Path

import click
import pyperclip
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from . import __version__
from .generator import GenerationResult, GeneratedTest, generate_tests
from .git_utils import (
    DiffResult,
    get_branch_diff,
    get_file_diff,
    get_staged_diff,
    is_git_repo,
)
from .providers import get_provider
from .runner import RunResult, run_test

console = Console()


def _abort(message: str) -> None:
    console.print(f"[bold red]Error:[/bold red] {message}")
    sys.exit(1)


def _display_generated_test(test: GeneratedTest, run_result: RunResult | None = None) -> None:
    """Display a single generated test with syntax highlighting."""
    lang_map = {
        "python": "python",
        "javascript": "javascript",
        "typescript": "typescript",
        "ruby": "ruby",
        "go": "go",
    }
    syntax_lang = lang_map.get(test.language, "python")

    title = f"📝 {test.suggested_filename}  [dim](for {test.source_path})[/dim]"

    if run_result is not None:
        if run_result.passed:
            title += "  [bold green]✅ PASSED[/bold green]"
        else:
            title += "  [bold red]❌ FAILED[/bold red]"

    syntax = Syntax(
        test.test_code,
        syntax_lang,
        theme="monokai",
        line_numbers=True,
        word_wrap=True,
    )
    console.print(Panel(syntax, title=title, border_style="blue"))

    if run_result is not None and not run_result.passed:
        console.print(Panel(
            run_result.output[:2000],
            title="[red]Test Output[/red]",
            border_style="red",
        ))


def _display_summary(result: GenerationResult, run_results: list[RunResult] | None = None) -> None:
    """Display summary table of generated tests."""
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("File", style="cyan")
    table.add_column("Test File", style="blue")
    table.add_column("Framework")
    table.add_column("Lines", justify="right")

    if run_results:
        table.add_column("Status")

    for i, test in enumerate(result.tests):
        run_res = run_results[i] if run_results else None
        status = ""
        if run_res:
            status = "[green]✅ pass[/green]" if run_res.passed else "[red]❌ fail[/red]"

        row = [
            test.source_path,
            test.suggested_filename,
            test.framework,
            str(len(test.test_code.splitlines())),
        ]
        if run_results:
            row.append(status)
        table.add_row(*row)

    console.print(table)

    if result.model_label:
        console.print(f"[dim]Model: {result.model_label}[/dim]")


@click.command()
@click.version_option(__version__, prog_name="difftests")
@click.option(
    "--staged",
    "mode",
    flag_value="staged",
    default=True,
    help="Generate tests for staged changes (default)",
)
@click.option(
    "--diff",
    "base_branch",
    metavar="BRANCH",
    default=None,
    help="Generate tests for all changes vs BRANCH (e.g. --diff main)",
)
@click.option(
    "--file",
    "file_path",
    metavar="FILE",
    default=None,
    help="Generate tests for a specific file",
)
@click.option(
    "--framework",
    type=click.Choice(
        ["pytest", "unittest", "jest", "vitest", "rspec", "go"],
        case_sensitive=False,
    ),
    default=None,
    help="Test framework to use (auto-detected from language if not set)",
)
@click.option(
    "--provider",
    type=click.Choice(["claude", "openai", "ollama"], case_sensitive=False),
    default="claude",
    show_default=True,
    envvar="DIFFTESTS_PROVIDER",
    help="LLM provider",
)
@click.option(
    "--model",
    default=None,
    envvar="DIFFTESTS_MODEL",
    help="Model name (uses provider default if not set)",
)
@click.option(
    "--context",
    "context_text",
    metavar="TEXT",
    default=None,
    help="Additional context (e.g. 'This module handles auth, be thorough with security')",
)
@click.option(
    "--output",
    "output_dir",
    metavar="DIR",
    default=None,
    help="Save generated tests to this directory",
)
@click.option(
    "--run",
    "run_tests",
    is_flag=True,
    default=False,
    help="Run generated tests immediately after generation",
)
@click.option(
    "--copy",
    is_flag=True,
    default=False,
    help="Copy generated tests to clipboard",
)
@click.option(
    "--raw",
    is_flag=True,
    default=False,
    help="Print raw test code only (no panels, for piping)",
)
def main(
    mode: str,
    base_branch: str | None,
    file_path: str | None,
    framework: str | None,
    provider: str,
    model: str | None,
    context_text: str | None,
    output_dir: str | None,
    run_tests: bool,
    copy: bool,
    raw: bool,
) -> None:
    """AI-powered test generator from git diffs.

    Analyzes your staged changes (or diff vs a branch) and generates
    tests covering what you just wrote.

    Examples:

      difftests                          # tests for staged changes
      difftests --diff main              # tests for all changes vs main
      difftests --file src/auth.py       # tests for a specific file
      difftests --framework pytest       # force pytest (auto-detected otherwise)
      difftests --run                    # generate AND run the tests
      difftests --output tests/          # save to tests/ directory
      difftests --provider ollama        # use local Ollama (no API key)
    """
    if not is_git_repo():
        _abort("Not inside a git repository.")

    # Get diff
    try:
        if file_path:
            diff: DiffResult = get_file_diff(file_path, base=base_branch)
        elif base_branch:
            diff = get_branch_diff(base=base_branch)
        else:
            diff = get_staged_diff()
    except RuntimeError as e:
        _abort(str(e))
        return

    if diff.is_empty:
        if base_branch:
            console.print(f"[yellow]No changes found vs '{base_branch}'.[/yellow]")
        elif file_path:
            console.print(f"[yellow]No changes found in '{file_path}'.[/yellow]")
        else:
            console.print(
                "[yellow]No staged changes. Use 'git add' to stage files, "
                "or use --diff BRANCH to review all changes.[/yellow]"
            )
        sys.exit(0)

    if not raw:
        mode_desc = (
            f"[cyan]{file_path}[/cyan]"
            if file_path
            else f"changes vs [cyan]{base_branch}[/cyan]"
            if base_branch
            else "staged changes"
        )
        console.print(
            f"[dim]Generating tests for {mode_desc} · "
            f"{diff.file_count} file(s)[/dim]"
        )
        console.print(f"[dim]Provider: {provider}[/dim]")
        console.print("[dim]Thinking...[/dim]")

    # Get provider
    try:
        llm = get_provider(provider, model=model)
    except ValueError as e:
        _abort(str(e))
        return

    model_label = f"{provider}/{model or 'default'}"

    # Generate tests
    try:
        result = generate_tests(
            diff=diff,
            provider=llm,
            framework=framework,
            context=context_text,
            model_label=model_label,
        )
    except Exception as e:
        _abort(f"Test generation failed: {e}")
        return

    if result.is_empty:
        console.print("[yellow]No testable files found in the diff.[/yellow]")
        sys.exit(0)

    # Raw mode: just print code
    if raw:
        for test in result.tests:
            print(test.test_code)
        return

    # Save to output directory if requested
    if output_dir:
        Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Optionally run tests
    run_results: list[RunResult] | None = None
    if run_tests:
        run_results = []
        for test in result.tests:
            run_result = run_test(test, test_dir=output_dir)
            run_results.append(run_result)

    elif output_dir:
        # Save without running
        for test in result.tests:
            out_path = Path(output_dir) / test.suggested_filename
            out_path.write_text(test.test_code, encoding="utf-8")
            console.print(f"[green]Saved:[/green] {out_path}")

    # Display results
    for i, test in enumerate(result.tests):
        run_res = run_results[i] if run_results else None
        _display_generated_test(test, run_result=run_res)

    # Summary table
    if len(result.tests) > 1 or run_results:
        console.print()
        _display_summary(result, run_results=run_results)

    # Copy to clipboard
    if copy:
        all_code = "\n\n".join(t.test_code for t in result.tests)
        try:
            pyperclip.copy(all_code)
            console.print("[green]✓ Copied to clipboard[/green]")
        except Exception:
            console.print("[yellow]Could not copy to clipboard.[/yellow]")

    # Exit code based on test run results
    if run_results and any(not r.passed for r in run_results):
        sys.exit(1)
