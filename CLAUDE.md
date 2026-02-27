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
mech prepare-metadata             # Generate metadata.json and publish to IPFS
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
# First, sync all third-party packages from IPFS (required before locking hashes)
poetry run autonomy init --reset --author ci --remote --ipfs --ipfs-node "/dns/registry.autonolas.tech/tcp/443/https"
poetry run autonomy packages sync

# Then regenerate hashes and run generators
make generators           # copyright headers + ABCI docstrings + package lock + doc hashes
make common-checks-1      # copyright, doc links, hash/package/doc-hash/service checks
```

> **Note:** `make generators` calls `autonomy packages lock` internally, which requires all
> third-party packages to be present locally. Always run `autonomy packages sync` first or it
> will fail with "Skill configuration not found" errors.
>
> **Important:** `pyproject.toml` dependency versions are driven by the AEA package configs
> under `packages/` — specifically `packages/valory/agents/mech/aea-config.yaml`. The
> `check_dependencies.py` script (`tox -e check-dependencies`) enforces consistency between
> `aea-config.yaml`, all synced third-party packages, and `pyproject.toml`. Any version
> constraint in `pyproject.toml` must agree with every package in the full IPFS dependency
> tree; if there is a conflict the script fails and overwrites `pyproject.toml` with the
> "winning" version from the packages.

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
poetry run pytest tests/                                      # all unit tests
poetry run pytest tests/unit/cli/                            # CLI tests only
poetry run pytest -vv tests/                                 # verbose
poetry run pytest -m "not integration and not e2e" tests/   # skip slow tests
poetry run pytest tests/ --cov=mtd --cov-report=term-missing # coverage report
```

Current state: **170 tests, 100% line coverage (880/880 statements).** Maintain 100% when adding new code — run the coverage command to verify before committing.

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
- `mech-client==0.19.1` — mech interaction client
- `safe-eth-py^7.18.0` — Gnosis Safe on-chain operations
- `ipfshttpclient==0.8.0a2` — IPFS uploads
- `click==8.1.8` — CLI framework

---

## Architecture

### Layers

```
CLI entry point  ──►  commands/  ──►  core modules  ──►  external services
  cli.py                *.py           setup_flow.py       olas-operate-middleware
  (Click group)         context_utils  deploy_mech.py      IPFS
                        require_init   services/metadata/  Gnosis Safe / web3
                                       workspace.py        autonomy CLI
```

### Context (`mtd/context.py`)

`MtdContext` is a **frozen dataclass** that holds every resolved workspace path. It is created
once per CLI invocation inside the `cli` group callback in `cli.py` and stored in
`ctx.obj["mtd_context"]`. All subcommands retrieve it via `get_mtd_context(ctx)` in
`context_utils.py`.

```
~/.operate-mech/          ← workspace_path / operate_dir
  .env                    ← env_path      (runtime env vars filled by setup_flow)
  .mech_initialized       ← marker file   (presence = workspace is set up)
  config/                 ← config_dir    (chain JSON configs)
  keys/                   ← operate's encrypted key store (read-only by mtd)
  ethereum_private_key.txt  ← decrypted agent key (written by _create_private_key_files)
  keys.json               ← decrypted key bundle (written by _create_private_key_files)
  metadata.json           ← metadata_path (generated / uploaded)
  packages/               ← packages_dir  (user's custom tools)
  services/               ← operate service config (JSON written by operate)
```

`is_initialized()` returns `True` only when the marker file, `config/`, and `.env` all exist.
`workspace_cwd()` is a context manager that `chdir`s to `workspace_path` and sets `OPERATE_HOME`
for the duration of an operate subprocess call, restoring both on exit.

### CLI → command wiring (`mtd/cli.py`, `mtd/commands/`)

```
cli (group) ─┬─ setup          setup_cmd.py   → setup_flow.run_setup_flow()
             ├─ run            run_cmd.py     → operate / autonomy subprocesses
             ├─ stop           stop_cmd.py    → operate subprocess
             ├─ deploy-mech    deploy_mech_cmd.py → deploy_mech.deploy_mech()
             ├─ prepare-metadata  prepare_metadata_cmd.py → generate + publish pipeline
             ├─ update-metadata update_metadata_cmd.py → update_onchain
             └─ add-tool       add_tool_cmd.py → Template scaffolding
```

Every command that touches a workspace calls `require_initialized(context)` before doing any
work; this raises a `ClickException` with a helpful message rather than failing deep inside.

### Setup flow (`mtd/setup_flow.py`)

The most complex module — orchestrates the full first-time setup in order:

1. `workspace.py:bootstrap_workspace()` — copies runtime templates from the package
   (`mtd/templates/runtime/`) into the workspace directory via `resources.py`.
2. Calls into `olas-operate-middleware` to create/fund the on-chain service. operate writes its
   own JSON config under `~/.operate-mech/services/`.
3. `_sanitize_local_quickstart_user_args()` — patches the operate config with any values
   already present in a local `.env` (used in quickstart / re-setup scenarios).
4. `_setup_env()` / `_read_and_update_env()` — reads the operate config JSON, computes derived
   values (`SAFE_CONTRACT_ADDRESS`, `ALL_PARTICIPANTS`, `MECH_TO_MAX_DELIVERY_RATE`), and fills
   `.env` by iterating over the template lines from `config/`.
5. `_setup_private_keys()` — reads operate's encrypted key file from `~/.operate-mech/keys/`,
   prompts for (or reads from env) the operate password, decrypts, and calls
   `_create_private_key_files()` to write `ethereum_private_key.txt` and `keys.json`.
6. `_deploy_mech()` — calls `deploy_mech.needs_mech_deployment()` and if needed runs
   `deploy_mech.deploy_mech()` followed by `update_service_after_deploy()`.
7. Writes the `.mech_initialized` marker to mark the workspace as ready.

### Mech deployment (`mtd/deploy_mech.py`)

Standalone module for on-chain mech registration. Key data structure:

```python
MECH_FACTORY_ADDRESS = {
    Chain.GNOSIS: { marketplace_address: { mech_type: factory_address } },
    Chain.BASE:   { ... },
    ...
}
```

`deploy_mech()` flow:
1. Validates `service.home_chain` → `Chain` enum; checks chain is in the factory map.
2. Fetches the `MechMarketplace` ABI from GitHub (with error handling).
3. Looks up `mech_factory_address` from the table (falls back to first known address if the
   configured marketplace address is unrecognised).
4. Builds and sends a `create` call to the marketplace contract via `EthSafeTxBuilder`.
5. Parses the `CreateMech` event from the receipt to extract `mech_address` and `agent_id`.

### Metadata pipeline (`mtd/services/metadata/`)

Three-stage pipeline, each stage in its own module:

```
generate.py           publish.py               update_onchain.py
─────────────         ──────────────────────   ─────────────────────
scan packages/        validate metadata JSON   load .env
  customs/*/          upload to IPFS           build web3 contract call
import .py files      return on-chain hash     send via Gnosis Safe tx
read component.yaml                            return (success, tx_hash)
build metadata.json
```

`generate.py` uses `importlib.util.spec_from_file_location` to dynamically import each tool's
Python file and extract `ALLOWED_TOOLS` / `AVAILABLE_TOOLS`. All exceptions from `exec_module`
(SyntaxError, ImportError, etc.) are caught and re-raised as `RuntimeError` with context.

`publish.py` validates the metadata through a hierarchy of focused helpers
(`_validate_metadata_structure` → `_validate_tool_entry` → `_validate_tool_input` /
`_validate_tool_output` → `_validate_output_schema` → `_validate_schema_properties`), each
returning `Optional[str]` (None = ok, string = error message).

### `packages/` directory and PyPI installation

`packages/` serves a dual role: AEA component definitions (agents, services, customs) used at
dev time, and the initial content seeded into every new workspace.

**How it reaches the user after `pip install mech-server`:**

```
pyproject.toml: [[tool.poetry.packages]] include = "packages"
    ↓
site-packages/packages/   (AEA components land alongside mtd/)
    ↓
mech init  →  workspace.py:initialize_workspace()
    Path(__file__).parent.parent / "packages"  ←  resolves to site-packages/packages/
    shutil.copytree(...)  →  ~/.operate-mech/packages/
```

`mech setup` then calls `run_service(..., build_only=True)` which fetches the mech agent
definition from **IPFS** using the hash in `config_mech_<chain>.json` — the local `packages/`
content is NOT needed by the operate middleware at that point.

**What the workspace `packages/` is used for at runtime:**

| Use case | Requires `~/.operate-mech/packages/` |
|----------|--------------------------------------|
| `generate_metadata` | Yes — scans `packages/valory/customs/` for tool definitions |
| `mech add-tool` | Yes — writes new tool scaffold there |
| `mech run --dev` | Yes — `autonomy push-all` reads it to push to IPFS |
| `mech run` (production Docker) | No — operate fetches from IPFS by hash |
| `mech setup` | No — operate fetches from IPFS by hash |

**Fragile assumption:** `workspace.py` uses `Path(__file__).parent.parent / "packages"` (not
`importlib.resources`) to locate the bundled `packages/`. This works as long as `packages/`
continues to be installed one level above the `mtd/` package in `site-packages/`. If the wheel
layout ever changes, `initialize_workspace()` will raise a `ClickException("Packaged tools
directory not found")` immediately.

### Templates (`mtd/templates/`)

Two kinds:

| Directory | Purpose | Loaded by |
|-----------|---------|-----------|
| `templates/runtime/` | Chain configs, `.example.env`, `metadata.template.json` | `resources.py` via `importlib.resources` → copied to workspace at setup |
| `templates/*.template` | Code scaffolding (init, config, tool Python file) | `add_tool_cmd._read_template()` via `importlib.resources` |

Both use `importlib.resources.files("mtd.templates[.runtime]")` so they work correctly when
installed from PyPI (not just from source).

### Error handling strategy

| Exception type | When to use |
|----------------|-------------|
| `ValueError` | Bad or missing input (env vars, config keys, invalid data) |
| `RuntimeError` | Execution / network failure (IPFS, Safe tx, module load) |
| `click.ClickException` | User-facing CLI errors (invalid chain, fetch failure, not-initialized) |
| `FileNotFoundError` | Missing required files (packages dir, operate config) |
