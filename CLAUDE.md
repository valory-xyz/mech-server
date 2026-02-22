# CLAUDE.md

## Project Overview

**mech-server** is a developer toolkit for the [Olas](https://olas.network/) Mech ecosystem. It provides:
- The `mech` CLI for setting up, running, and managing mech agent services
- Core mech logic and tool scaffolding
- Metadata generation, IPFS publishing, and on-chain updates via Safe transactions

Built on top of [Open Autonomy](https://github.com/valory-xyz/open-autonomy) (FSM-based agent framework) and [olas-operate-middleware](https://github.com/valory-xyz/olas-operate-middleware) (workspace/Docker orchestration).

**Supported chains:** gnosis, base, polygon, optimism

---

## Repository Structure

```
mech-server/
├── mtd/                        # Main package ("Mech Tools Dev")
│   ├── __init__.py             # Package init with __version__
│   ├── cli.py                  # Click CLI entry point (`mech` command)
│   ├── context.py              # MtdContext dataclass, workspace path resolution
│   ├── setup_flow.py           # Orchestrates full `mech setup` flow
│   ├── deploy_mech.py          # Mech marketplace deployment logic
│   ├── resources.py            # Loads bundled templates/configs
│   ├── workspace.py            # Workspace bootstrap logic
│   ├── commands/               # Individual CLI command implementations
│   ├── services/metadata/      # Metadata gen, IPFS publish, on-chain update
│   └── templates/
│       ├── runtime/            # Chain-specific config templates (gnosis, base, ...)
│       └── *.template          # Code scaffolding templates (config, tool)
├── packages/valory/
│   ├── customs/echo/           # Example custom mech tool
│   ├── agents/mech/            # Mech agent AEA component
│   └── services/mech/          # Mech service AEA component
├── tests/unit/                 # Unit tests
├── utils/                      # Dev utility scripts (check_dependencies, bump, etc.)
├── docs/                       # MkDocs documentation source
├── pyproject.toml              # Poetry config and package metadata
├── tox.ini                     # Tox environments + flake8/isort/mypy/pytest config
└── Makefile                    # All common dev tasks
```

**Default workspace directory at runtime:** `~/.operate-mech/`

---

## Installation

```bash
poetry install
```

Requires Python 3.10–3.11, Poetry, Docker, Docker Compose, and Tendermint `0.34.19`.

---

## CLI Commands

```bash
mech setup -c <chain>          # Full first-time setup
mech run -c <chain>            # Run via Docker (production)
mech run -c <chain> --dev      # Dev mode: push packages to IPFS, run on host
mech stop -c <chain>           # Stop running service
mech deploy-mech -c <chain>    # Deploy mech on marketplace for existing service
mech push-metadata             # Generate metadata.json and publish to IPFS
mech update-metadata           # Update on-chain metadata hash via Safe
mech add-tool <author> <name>   # Scaffold a new tool
```

---

## Development Workflow

### Formatting and checks

```bash
make format          # black + isort (via tomte)
make code-checks     # flake8, mypy, pylint, darglint (via tomte)
make security        # bandit, safety, gitleaks
```

### Before every commit (mandatory)

Always run the `mtd`/`tests` linters before committing any changes to `mtd/` or `tests/`:

```bash
tox -e black-check-mtd,isort-check-mtd,flake8-mtd,mypy-mtd,pylint-mtd
```

To auto-fix formatting first:

```bash
tox -e black-mtd,isort-mtd   # format, then re-run the checks above
```

Common lint pitfalls to watch for:
- **D403**: docstring first word must be properly capitalized — use an imperative verb (`Return`, `Raise`, `Check`) rather than a CamelCase type name or lowercase word
- **W1514**: always pass `encoding="utf-8"` to `open()`, `read_text()`, and `write_text()`
- **pylint inline disable**: must be `# pylint: disable=` (with space) on the **opening** line of multi-line expressions
- **mypy dict-item**: use `# type: ignore[dict-item]` when unpacking a typed dict with overriding keys in tests

### Before opening a PR (run in this order)

```bash
make clean
make format
make code-checks
make security
```

If you modified an `AbciApp` definition:
```bash
make abci-docstrings      # regenerate ABCI docstrings
```

If you modified anything under `packages/`:
```bash
make generators           # copyright headers + ABCI docstrings + package lock + doc hashes
make common-checks-1      # copyright, doc links, hash/package/doc-hash/service checks
```

Otherwise (no `packages/` changes):
```bash
tomte check-copyright --author valory  # just run copyright check
```

After committing:
```bash
make common-checks-2      # check-abci-docstrings, check-abciapp-specs, check-handlers
```

---

## Testing

```bash
poetry run pytest tests/                                      # all unit tests (161 tests)
poetry run pytest tests/unit/cli/                            # CLI tests only
poetry run pytest -vv tests/                                 # verbose
poetry run pytest -m "not integration and not e2e" tests/   # skip slow tests
poetry run pytest tests/ --cov=mtd --cov-report=term-missing # coverage report
```

Current state: **161 tests, 100% line coverage (837/837 statements).** Maintain 100% when adding new code — run the coverage command to verify before committing.

Pytest config in `tox.ini`: log level DEBUG, asyncio mode strict. Markers: `integration`, `e2e`.

---

## Versioning

Version is defined in **two places** — both must be updated together:

1. `pyproject.toml` → `version = "X.Y.Z"`
2. `mtd/__init__.py` → `__version__ = "X.Y.Z"`

Also update `SECURITY.md` to reflect the new supported version.

---

## Releasing

1. Bump the version in `pyproject.toml`, `mtd/__init__.py`, and `SECURITY.md`
2. Commit and push to `main`
3. Create and publish a GitHub release — the `release.yaml` workflow triggers automatically and publishes to PyPI using `PYPI_API_TOKEN`

---

## Code Conventions

- **License:** Apache-2.0; all files require a Valory copyright header
- **Style:** black + isort, 88-char line length, Sphinx-style docstrings
- **Types:** mypy strict (`--disallow-untyped-defs`), Python 3.10 target
- **Guard clauses** preferred over deep nesting
- **Import order:** FUTURE, STDLIB, THIRDPARTY, FIRSTPARTY, PACKAGES, LOCALFOLDER
- **Branch naming:** kebab-case, 2–3 words (e.g. `feat/some-feature`)
- Custom tools live in `packages/valory/customs/<author>/<tool_name>/` with a `component.yaml`

---

## Key Integrations

- `open-autonomy==0.21.11` — FSM agent framework
- `olas-operate-middleware>=0.14.16` — service/workspace orchestration
- `mech-client==0.18.8` — mech interaction client
- `safe-eth-py^7.18.0` — Gnosis Safe on-chain operations
- `ipfshttpclient==0.8.0a2` — IPFS uploads
- `click==8.1.8` — CLI framework
