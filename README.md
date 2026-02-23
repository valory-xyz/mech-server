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
    <img alt="Sanity checks and tests" src="https://github.com/valory-xyz/mech-server/actions/workflows/common_checks.yaml/badge.svg?branch=main">
  </a>
  <a href="https://codecov.io/gh/valory-xyz/mech-server">
    <img alt="Coverage" src="https://img.shields.io/codecov/c/github/valory-xyz/mech-server">
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
mech setup -c <chain>
mech run -c <chain>
```

## Supported Chains

| Chain | Native | OLAS Token | USDC Token | Nevermined |
|-------|--------|------------|------------|------------|
| Gnosis | yes | yes | - | yes |
| Base | yes | yes | - | yes |
| Polygon | yes | yes | yes | yes |
| Optimism | yes | yes | - | yes |

## Requirements

- [Python](https://www.python.org/) `>=3.10, <3.12`
- [Poetry](https://python-poetry.org/docs/)
- [Docker Engine](https://docs.docker.com/engine/install/) + [Docker Compose](https://docs.docker.com/compose/install/)

## Commands

| Command | Description |
|---|---|
| `mech setup -c <chain>` | Full first-time setup: workspace, agent build, mech deployment, env config, key setup |
| `mech add-tool <author> <name>` | Scaffold a new mech tool |
| `mech push-metadata` | Lock packages, push to IPFS, generate and publish metadata |
| `mech update-metadata` | Update the metadata hash on-chain via Safe transaction |
| `mech run -c <chain>` | Run the mech AI agent via Docker |
| `mech stop -c <chain>` | Stop a running mech AI agent |

## Developing a new tool

### New service (no existing mech)

1. Set up the workspace and deploy the mech on-chain:
    ```bash
    mech setup -c <chain>
    ```

2. Scaffold a tool:
    ```bash
    mech add-tool <author> <tool_name> -d "Tool description"
    ```

3. Implement the tool logic in `~/.operate-mech/packages/<author>/customs/<tool_name>/<tool_name>.py`. The scaffold generates a working stub with the correct structure:
    ```python
    ALLOWED_TOOLS = ["tool_name"]

    def run(**kwargs: Any) -> MechResponse:
        prompt = kwargs.get("prompt")
        if prompt is None:
            return error_response("No prompt has been given.")
        result = do_work(prompt)
        return result, prompt, None, None, None
    ```

4. If your tool requires API keys or other secrets, add them to `~/.operate-mech/.env`.

5. Publish metadata and update the on-chain registry:
    ```bash
    mech push-metadata
    mech update-metadata
    ```

6. Run:
    ```bash
    mech run -c <chain>
    ```

### Existing service (mech already running)

1. Stop the service:
    ```bash
    mech stop -c <chain>
    ```

2. Scaffold, implement, and set any required API keys (same as steps 2–4 above).

3. Publish and update:
    ```bash
    mech push-metadata
    mech update-metadata
    ```

4. Restart:
    ```bash
    mech run -c <chain>
    ```

## Documentation

Find the full tutorial (tool development, publishing, sending requests) at [stack.olas.network](https://stack.olas.network).
