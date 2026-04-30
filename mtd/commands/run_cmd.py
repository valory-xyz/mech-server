# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2025-2026 Valory AG
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
# ------------------------------------------------------------------------------

"""Run command for starting the mech agent service."""

import json
import subprocess
from pathlib import Path

import click
from mtd.commands.context_utils import (
    SUPPORTED_CHAINS,
    _workspace_cwd,
    get_mtd_context,
    require_initialized,
)
from mtd.context import MtdContext
from operate.cli import OperateApp
from operate.quickstart.run_service import run_service


def _push_all_packages(context: MtdContext) -> None:
    """Push local packages to IPFS so service hashes resolve during runtime."""
    if not context.packages_dir.exists():
        raise click.ClickException(
            "Dev mode requires a local packages directory in the workspace. "
            "Initialize/copy packages first or run without --dev."
        )

    click.echo("Pushing local packages...")
    subprocess.run(
        ["autonomy", "push-all"],
        check=True,
        cwd=str(context.workspace_path),
    )


def _get_latest_service_hash(context: MtdContext) -> str:
    """Get the latest service hash from autonomy packages."""
    subprocess.run(
        ["autonomy", "packages", "lock", "--check"],
        check=False,
        capture_output=True,
        text=True,
        cwd=str(context.workspace_path),
    )

    packages_file = context.packages_dir / "packages.json"
    if packages_file.exists():
        packages = json.loads(packages_file.read_text(encoding="utf-8"))
        for key, hash_val in packages.get("dev", {}).items():
            if "service" in key and "mech" in key:
                return hash_val

    raise click.ClickException(
        f"Could not determine latest service hash from {packages_file}."
    )


def _run_dev_mode(config_path: Path, context: MtdContext) -> None:
    """Dev mode: push local packages, update config hash, run via middleware."""
    _push_all_packages(context=context)

    new_hash = _get_latest_service_hash(context=context)

    click.echo(f"Updating config template with hash: {new_hash}")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["hash"] = new_hash
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    click.echo("Starting service in dev mode (host deployment)...")
    with _workspace_cwd(context):
        operate = OperateApp(home=context.operate_dir)
        operate.setup()
        run_service(  # pylint: disable=unexpected-keyword-arg
            operate=operate,
            config_path=config_path,
            build_only=False,
            skip_dependency_check=False,
            use_docker=False,
        )


@click.command()
@click.option(
    "-c",
    "--chain-config",
    type=click.Choice(SUPPORTED_CHAINS, case_sensitive=False),
    required=True,
    help="Target chain for the mech agent.",
)
@click.option(
    "--dev",
    is_flag=True,
    default=False,
    help="Dev mode: push local packages to IPFS, then run on host (no Docker).",
)
@click.pass_context
def run(ctx: click.Context, chain_config: str, dev: bool) -> None:
    """Run the mech AI agent.

    In production mode (default), runs via Docker deployment.
    In dev mode (--dev), pushes local packages to IPFS and runs
    on the host (Tendermint + agent process, no Docker).

    Examples:
        mech run -c gnosis
        mech run -c gnosis --dev

    :param ctx: click context carrying the resolved MtdContext.
    :param chain_config: target chain name (e.g. ``gnosis``) for the agent run.
    :param dev: if True, push local packages to IPFS and run on host instead of Docker.
    """
    context = get_mtd_context(ctx)
    require_initialized(context)

    config_path = context.config_dir / f"config_mech_{chain_config}.json"
    if not config_path.exists():
        raise click.ClickException(f"Missing template config: {config_path}")

    if dev:
        _run_dev_mode(config_path=config_path, context=context)
        return

    with _workspace_cwd(context):
        operate = OperateApp(home=context.operate_dir)
        operate.setup()
        run_service(
            operate=operate,
            config_path=config_path,
            build_only=False,
            skip_dependency_check=False,
        )
