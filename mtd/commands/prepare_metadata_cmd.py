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

"""Prepare-metadata command for generating and publishing metadata to IPFS."""

import json
import subprocess
from pathlib import Path
from typing import Optional

import click
from aea.cli.packages import package_type_selector_prompt
from dotenv import set_key

from autonomy.cli.packages import get_package_manager
from mtd.commands.context_utils import (
    SUPPORTED_CHAINS,
    get_mtd_context,
    require_initialized,
)
from mtd.services.metadata import (
    DEFAULT_IPFS_NODE,
    generate_metadata,
    publish_metadata_to_ipfs,
)


def _lock_packages(packages_dir: Path) -> None:
    """Lock package hashes in packages.json after user edits."""
    packages_json = packages_dir / "packages.json"
    if not packages_json.exists():
        click.echo(
            f"Warning: {packages_json} not found, skipping lock. "
            "Run 'mech add-tool' without --skip-lock to generate it."
        )
        return
    click.echo("Locking packages...")
    get_package_manager(packages_dir).update_package_hashes(
        package_type_selector_prompt
    ).dump()
    click.echo("Packages locked.")


def _push_all_packages(workspace_path: Path, packages_dir: Path) -> None:
    """Push all local packages to IPFS."""
    packages_json = packages_dir / "packages.json"
    if not packages_json.exists():
        click.echo(
            f"Warning: {packages_json} not found, skipping push. "
            "Run 'mech add-tool' without --skip-lock to generate it."
        )
        return
    click.echo("Pushing packages to IPFS...")
    subprocess.run(
        ["autonomy", "push-all"],
        check=True,
        cwd=str(workspace_path),
    )
    click.echo("Packages pushed.")


def _compute_tools_to_package_hash(packages_dir: Path) -> str:
    """Compute TOOLS_TO_PACKAGE_HASH from workspace packages.json."""
    packages_json_path = packages_dir / "packages.json"
    if not packages_json_path.exists():
        click.echo(
            f"Warning: {packages_json_path} not found. "
            "TOOLS_TO_PACKAGE_HASH will not be updated. "
            "Run 'mech add-tool' without --skip-lock to generate it."
        )
        return ""

    try:
        packages_data = json.loads(packages_json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        click.echo(f"Warning: {packages_json_path} contains invalid JSON. Skipping.")
        return ""

    dev_packages = packages_data.get("dev", {})
    tools_mapping: dict = {}
    for key, ipfs_hash in dev_packages.items():
        parts = key.split("/")
        if len(parts) != 4 or parts[0] != "custom":
            continue
        tool_name = parts[2]
        tools_mapping[tool_name] = ipfs_hash

    if not tools_mapping:
        return ""

    return json.dumps(tools_mapping, separators=(",", ":"))


@click.command(name="prepare-metadata")
@click.option(
    "-c",
    "--chain-config",
    type=click.Choice(SUPPORTED_CHAINS, case_sensitive=False),
    required=False,
    default=None,
    help="Target chain whose .env to update. Updates all chain envs when omitted.",
)
@click.option(
    "--ipfs-node",
    type=str,
    default=DEFAULT_IPFS_NODE,
    help="IPFS node address.",
)
@click.pass_context
def prepare_metadata(
    ctx: click.Context, chain_config: Optional[str], ipfs_node: str
) -> None:
    """Generate metadata.json from packages and publish to IPFS.

    Locks package hashes, pushes all packages to IPFS, generates
    metadata, publishes it, and updates chain .env files with
    METADATA_HASH and TOOLS_TO_PACKAGE_HASH.

    Examples:
        mech prepare-metadata
        mech prepare-metadata -c gnosis
    """
    context = get_mtd_context(ctx)
    require_initialized(context)

    _lock_packages(context.packages_dir)
    _push_all_packages(context.workspace_path, context.packages_dir)

    click.echo("Generating metadata...")
    generate_metadata(
        packages_dir=context.packages_dir, metadata_path=context.metadata_path
    )

    click.echo("Publishing metadata to IPFS...")
    metadata_hash = publish_metadata_to_ipfs(
        metadata_path=context.metadata_path,
        ipfs_node=ipfs_node,
    )

    if chain_config:
        chains = [chain_config]
    else:
        chains = [c for c in SUPPORTED_CHAINS if context.chain_env_path(c).exists()]

    for chain in chains:
        set_key(str(context.chain_env_path(chain)), "METADATA_HASH", metadata_hash)
    click.echo(f"Metadata hash: {metadata_hash}")

    click.echo("Computing tools-to-package-hash mapping...")
    tools_hash_value = _compute_tools_to_package_hash(context.packages_dir)
    if tools_hash_value:
        for chain in chains:
            set_key(
                str(context.chain_env_path(chain)),
                "TOOLS_TO_PACKAGE_HASH",
                tools_hash_value,
            )
        click.echo(f"Tools-to-package-hash: {tools_hash_value}")
