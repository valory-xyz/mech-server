<h1 align="center">
    <b>Mech Server</b>
</h1>

<p align="center">
  <a href="https://pypi.org/project/mech-server/">
    <img alt="PyPI" src="https://img.shields.io/pypi/v/mech-server">
  </a>
  <a href="https://pypi.org/project/mech-server/">
    <img alt="PyPI - Python Version" src="https://img.shields.io/pypi/pyversions/mech-server">
  </a>
  <a href="https://pypi.org/project/mech-server/">
    <img alt="PyPI - Wheel" src="https://img.shields.io/pypi/wheel/mech-server">
  </a>
  <a href="https://github.com/valory-xyz/mech-server/blob/main/LICENSE">
    <img alt="License" src="https://img.shields.io/pypi/l/mech-server">
  </a>
  <a href="https://pypi.org/project/mech-server/">
    <img alt="Downloads" src="https://img.shields.io/pypi/dm/mech-server">
  </a>
</p>
<p align="center">
  <a href="https://github.com/valory-xyz/mech-server/actions/workflows/common_checks.yaml">
    <img alt="Sanity checks and tests" src="https://github.com/valory-xyz/mech-server/workflows/main_workflow/badge.svg?branch=main">
  </a>
  <a href="https://codecov.io/gh/valory-xyz/mech-server">
    <img alt="Coverage" src="https://codecov.io/gh/valory-xyz/mech-server/graph/badge.svg">
  </a>
  <a href="https://flake8.pycqa.org">
    <img alt="flake8" src="https://img.shields.io/badge/lint-flake8-yellow">
  </a>
  <a href="https://github.com/python/mypy">
    <img alt="mypy" src="https://img.shields.io/badge/static%20check-mypy-blue">
  </a>
  <a href="https://github.com/psf/black">
    <img alt="Black" src="https://img.shields.io/badge/code%20style-black-black">
  </a>
  <a href="https://github.com/PyCQA/bandit">
    <img alt="bandit" src="https://img.shields.io/badge/security-bandit-lightgrey">
  </a>
</p>

A CLI to create, deploy and manage Mechs — AI agents that execute tasks on-chain for payment — on the [Olas Marketplace](https://olas.network/mech-marketplace).

> **Note:** The codebase uses the term *service* (from the underlying Open Autonomy framework) interchangeably with *AI agent*.

## Quick Start

```bash
pip install mech-server
mech setup -c <chain>      # first-time setup; prompts for RPC URL and wallet funding
# edit ~/.operate-mech/.env and set your API keys
mech run -c <chain>        # run via Docker
mech stop -c <chain>       # stop when done
```

## Supported Chains

| Chain | Native | OLAS Token | USDC Token | Nevermined |
|-------|--------|------------|------------|------------|
| Gnosis | ✅ | ✅ | ❌ | ✅ |
| Base | ✅ | ✅ | ❌ | ✅ |
| Polygon | ✅ | ✅ | ✅ | ✅ |
| Optimism | ✅ | ✅ | ❌ | ✅ |

The mech payment type is selected at deployment time via the `MECH_TYPE` env variable.

## Requirements

- [Python](https://www.python.org/) `>=3.10, <3.12`
- [Poetry](https://python-poetry.org/docs/)
- [Docker Engine](https://docs.docker.com/engine/install/) + [Docker Compose](https://docs.docker.com/compose/install/)
- [Tendermint](https://docs.tendermint.com/v0.34/introduction/install.html) `==0.34.19` (only for `--dev` mode)

## Commands

| Command | Description |
|---|---|
| `mech setup -c <chain>` | Full first-time setup: agent build, mech deployment, env config, key setup, metadata generation, IPFS publish, and on-chain update |
| `mech run -c <chain>` | Run the mech AI agent via Docker |
| `mech run -c <chain> --dev` | Dev mode: push local packages to IPFS, then run on host (no Docker) |
| `mech stop -c <chain>` | Stop a running mech AI agent |
| `mech deploy-mech -c <chain>` | Deploy a mech on the marketplace (runs automatically during setup) |
| `mech push-metadata` | Generate `metadata.json` from packages and publish to IPFS |
| `mech update-metadata` | Update the metadata hash on-chain via Safe transaction |
| `mech add-tool <author> <name>` | Scaffold a new mech tool |

## What `mech setup` does

`mech setup` runs the following steps in order:

1. **Agent build** — creates the AI agent via `olas-operate-middleware` (skipped if already set up)
2. **Mech deployment** — deploys a mech on the marketplace (skipped if already deployed)
3. **Env configuration** — writes `~/.operate-mech/.env` with required variables
4. **Private key setup** — configures operator and agent keys
5. **Metadata generation** — generates `metadata.json` from package definitions
6. **IPFS publish** — pushes metadata to IPFS
7. **On-chain update** — updates the metadata hash on-chain via Safe transaction

## Adding a tool

```bash
mech add-tool <author> <tool_name> -d "My tool description"
```

Implement the tool in `~/.operate-mech/packages/<author>/customs/<tool_name>/<tool_name>.py`, then publish and register on-chain:

```bash
mech push-metadata
mech update-metadata
```

See the [documentation](https://stack.olas.network) for the full tool creation, publishing, and on-chain registration workflow.

## Troubleshooting

- **`setup` auto-bootstraps the workspace** if it is missing; `run` and `stop` still require an initialized workspace.
- **`--dev` mode** requires `packages/` inside the workspace and a running Tendermint instance.

1. **Issue**: `0xa25d...` not in list of participants

    **Solution**: Make sure the private keys inside `keys.json` match the address in `ALL_PARTICIPANTS` in the workspace `.env`.

2. **Issue**: `No module named 'anthropic'`

    **Solution**: List the dependency under `dependencies` in the tool's `component.yaml`, pinned to a specific version.

3. **Issue**: Tool changes not reflected

    **Solution**: After any change to tools or configs, run:
    ```bash
    poetry run autonomy packages lock
    mech push-metadata
    mech update-metadata
    ```

4. **Issue**: env formatting issues

    **Solution**: No whitespace in dicts/lists — they must be single-line strings. Check for non-standard quote characters (`\u201c`/`\u201d`).
    ```
    MECH_TO_CONFIG='{"0xbead38e4C4777341bB3FD44e8cd4D1ba1a7Ad9D7":{"use_dynamic_pricing":false,"is_marketplace_mech":true}}'
    ```

5. **Issue**: `ValueError: {'code': -32603, 'message': 'Filter with id: ... does not exist.'}` or `AlreadyKnown`

    **Solution**: Check your RPC URL or switch to a different provider.

6. **Issue**: `Service ''api_key'' not found in KeyChain`

    **Solution**: Check the key names inside the `API_KEYS` env variable.

7. **Issue**: `Error: Number of agent instances cannot be greater than available keys`

    **Solution**: RPC values must be on a single line in `.env`:
    ```
    ETHEREUM_LEDGER_RPC_0="https://1rpc.io/gnosis"
    ```

8. **Issue**: `Tool <tool_name> is not supported`

    **Solution**: Make sure `tool_name` is listed in `ALLOWED_TOOLS` inside the tool's Python file.

9. **Issue**: `Incompatible counter_callback`

    **Solution**: Either have your model added to [the supported list](https://github.com/valory-xyz/mech/blob/main/packages/valory/skills/task_execution/utils/benchmarks.py#L31) or remove `counter_callback` from your tool.

10. **Issue**: Port already in use (`listen tcp 127.0.0.1:26658: bind: address already in use`) — `--dev` mode only

    **Solution**:
    ```bash
    lsof -i :26658
    kill -9 <process_id>
    ```

## Documentation

Find the full tutorial (Hello World, creating and publishing tools, sending requests) at [stack.olas.network](https://stack.olas.network).
