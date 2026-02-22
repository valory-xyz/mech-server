# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2025 Valory AG
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

"""Push-metadata command for generating and publishing metadata to IPFS."""

import click
from dotenv import set_key

from mtd.commands.context_utils import get_mtd_context, require_initialized
from mtd.services.metadata import (
    DEFAULT_IPFS_NODE,
    generate_metadata,
    publish_metadata_to_ipfs,
)


@click.command(name="push-metadata")
@click.option(
    "--ipfs-node",
    type=str,
    default=DEFAULT_IPFS_NODE,
    help="IPFS node address.",
)
@click.pass_context
def push_metadata(ctx: click.Context, ipfs_node: str) -> None:
    """Generate metadata.json from packages and publish to IPFS.

    Example: mech push-metadata
    """
    context = get_mtd_context(ctx)
    require_initialized(context)

    click.echo("Generating metadata...")
    generate_metadata(
        packages_dir=context.packages_dir, metadata_path=context.metadata_path
    )

    click.echo("Publishing metadata to IPFS...")
    metadata_hash = publish_metadata_to_ipfs(
        metadata_path=context.metadata_path,
        ipfs_node=ipfs_node,
    )
    set_key(str(context.env_path), "METADATA_HASH", metadata_hash)
    click.echo(f"Metadata hash: {metadata_hash}")
