# Contributing Guide

Thank you for your interest in contributing to **mech-server**! This guide will help you get set up and ensure your contributions pass all checks.

## Prerequisites

- Python 3.10 or 3.11
- [uv](https://docs.astral.sh/uv/)
- Docker and Docker Compose
- Tendermint `0.34.19`

Install dependencies:

```bash
uv sync
source .venv/bin/activate
```

## Branch Naming

Use kebab-case with two or three words, optionally prefixed with a category:

```
feat/some-feature
fix/some-bug
```

## Creating a Pull Request

- **Target branch:** double-check the PR is opened against the correct branch before submitting.
- **Tag relevant ticket/issue:** describe the purpose of the PR with a reference to the relevant ticket or issue. Attach a label such as `enhancement`, `bug`, or `test`.
- **Include a sensible description:** descriptions help reviewers understand the purpose and context of the proposed changes.
- **Comment non-obvious code** to avoid confusion during review and improve maintainability.
- **Code reviews:** two reviewers will be assigned to a PR.
- **Linters:** make sure every linter passes before committing. See [Pre-commit checks](#pre-commit-checks) below.
- **Tests:** the PR must include tests for any new or updated code. Current coverage is **100%** — maintain it. Run the coverage command to verify:

```bash
uv run pytest tests/ --cov=mtd --cov-report=term-missing --cov-fail-under=100
```

Also mention potential effects on other branches or code that your changes might have.

## Pre-commit Checks

### Changes to `mtd/` or `tests/`

Auto-fix formatting first, then run all checks:

```bash
tox -e black-mtd,isort-mtd
tox -e black-check-mtd,isort-check-mtd,flake8-mtd,mypy-mtd,pylint-mtd
```

### Changes to `packages/` or `utils/`

```bash
tox -e black,isort
tox -e black-check,isort-check,flake8,mypy,pylint,darglint
```

### Common lint pitfalls

- **D403:** docstring first word must be properly capitalized — use an imperative verb (`Return`, `Raise`, `Check`) rather than a CamelCase type name or lowercase word.
- **W1514:** always pass `encoding="utf-8"` to `open()`, `read_text()`, and `write_text()`.
- **pylint inline disable:** must be `# pylint: disable=` (with a space) on the **opening** line of multi-line expressions.

## Before Opening a PR

Run checks in the following order:

```bash
make clean
make format
make code-checks
make security
```

**If you modified an `AbciApp` definition:**

```bash
make abci-docstrings
```

**If you modified files under `packages/`:**

```bash
# Sync third-party packages from IPFS first (required before locking hashes)
uv run autonomy init --reset --author ci --remote --ipfs --ipfs-node "/dns/registry.autonolas.tech/tcp/443/https"
uv run autonomy packages sync

# Then regenerate hashes and run checks
make generators
make common-checks-1
```

**Otherwise (no `packages/` changes):**

```bash
tomte check-copyright --author valory
```

**After committing:**

```bash
make common-checks-2
```

## Running Tests

```bash
uv run pytest tests/                                      # all unit tests
uv run pytest tests/unit/cli/                            # CLI tests only
uv run pytest -vv tests/                                 # verbose
uv run pytest -m "not integration and not e2e" tests/   # skip slow tests
uv run pytest tests/ --cov=mtd --cov-report=term-missing # coverage report
```

Pytest config lives in `tox.ini`. Markers: `integration`, `e2e`.

## Code Conventions

- **License:** Apache-2.0. All files require a Valory copyright header.
- **Formatting:** black + isort, 88-character line length.
- **Docstrings:** Sphinx-style (`:param:`, `:return:`, `:raises:`).
- **Types:** mypy strict (`--disallow-untyped-defs`), Python 3.10 target.
- **Guard clauses** preferred over deep nesting.
- **Import order:** `FUTURE`, `STDLIB`, `THIRDPARTY`, `FIRSTPARTY`, `PACKAGES`, `LOCALFOLDER`.

### Docstring example

```python
def some_method(some_arg: SomeType) -> ReturnType:
    """Do something with the given argument.

    :param some_arg: describe argument.
    :return: value of ReturnType.
    :raises ValueError: if some_arg is invalid.
    """
```

After editing documentation, run `tomte check-spelling` to verify spelling.


## Security

Report security vulnerabilities by emailing `info@valory.xyz`. See [SECURITY.md](SECURITY.md) for the full policy.
