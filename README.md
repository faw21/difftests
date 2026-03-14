# difftests

**AI test generator from git diffs — write tests for what you just changed.**

Stop writing tests from scratch. `difftests` analyzes your git diff and generates
tests that cover exactly what you changed — including edge cases and error conditions.

## Install

```bash
pip install difftests
```

Set your API key (or use Ollama for zero-cost local generation:

```bash
export ANTHROPIC_API_KEY=your-key   # Claude (default)
export OPENAI_API_KEY=your-key      # or OpenAI
# or use --provider ollama           # local, no API key needed
```

## Usage

```bash
# Generate tests for staged changes (most common)
difftests

# Generate tests for all changes vs main branch
difftests --diff main

# Generate tests for a specific file
difftests --file src/auth.py

# Specify the test framework (auto-detected by default)
difftests --framework pytest     # default for Python
difftests --framework jest       # for JavaScript
difftests --framework vitest     # for TypeScript
difftests --framework rspec      # for Ruby
difftests --framework go         # for Go

# Save generated tests to a directory
difftests --output tests/

# Generate AND run tests immediately
difftests --run

# Copy to clipboard
difftests --copy

# Add context for better generation
difftests --context "This is a payment module, be thorough with security tests"

# Use local Ollama (free, no API key)
difftests --provider ollama --model qwen2.5:7b

# Raw output for piping
difftests --raw > tests/test_new.py
```

## Frameworks

| Language | Default | Alternatives |
|----------|---------|--------------|
| Python | `pytest` | `unittest` |
| JavaScript | `jest` | |
| TypeScript | `vitest` | `jest` |
| Ruby | `rspec` | |
| Go | `go` | |

## What Makes difftests Different

**Understands your diff, not just your code.** difftests focuses on the *exact
functions and methods you changed*, not random parts of your codebase. The AI is shown:

1. The git diff (what changed)
2. The full file content (context)
3. Instructions to focus on edge cases, error conditions, and security

**Works with any LLM.** Claude, OpenAI, or local Ollama — bring your own model.

**Generates real tests, not boilerplate.** The AI is explicitly instructed to:
- Test edge cases (null, empty, boundary values)
- Test error conditions (`pytest.raises`, exception handling)
- Mock external dependencies (databases, HTTP, file I/O)
- Use the framework's best practices (not generic asserts)

## Developer Workflow Integration

difftests works best as part of the AI-powered developer workflow:

```bash
# 1. Morning: generate standup from yesterday's commits
standup-ai ~/projects/myapp

# 2. Write code, then review before committing
critiq                          # AI review of staged changes
difftests --staged              # generate tests for what you just wrote
pytest tests/                   # run them

# 3. Generate conventional commit message
gpr --commit-run

# 4. Generate PR description
gpr

# 5. Review a teammate's PR (also generate tests for their changes)
difftests --diff main --output tests/
prcat 42

# 6. At release: generate CHANGELOG
changelog-ai --from v0.1.0 --prepend CHANGELOG.md
```

## Providers

| Provider | Command | Notes |
|----------|---------|-------|
| Claude (default) | `--provider claude` | Best results; requires `ANTHROPIC_API_KEY` |
| OpenAI | `--provider openai` | Requires `OPENAI_API_KEY` |
| Ollama | `--provider ollama` | Free, runs locally; no API key needed |

## Related Tools

- [critiq](https://github.com/faw21/critiq) — AI code reviewer (find issues before pushing)
- [critiq-action](https://github.com/faw21/critiq-action) — critiq as a GitHub Action for CI
- [gpr](https://github.com/faw21/gpr) — AI commit messages + PR descriptions
- [prcat](https://github.com/faw21/prcat) — AI reviewer for teammates' pull requests
- [gitbrief](https://github.com/faw21/gitbrief) — git-history-aware context packer for LLMs
- [standup-ai](https://github.com/faw21/standup-ai) — daily standup from git commits
- [changelog-ai](https://github.com/faw21/changelog-ai) — AI-generated CHANGELOG
- [chronicle](https://github.com/faw21/chronicle) — AI git history narrator
- [testfix](https://github.com/faw21/testfix) — AI test fixer — automatically fix failing tests

- [mergefix](https://github.com/faw21/mergefix) — AI merge conflict resolver: fix all conflicts with one command

## License

MIT
