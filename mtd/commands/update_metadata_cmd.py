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

"""Update-metadata command for updating the metadata hash on-chain."""

import click
from mtd.commands.context_utils import (
    SUPPORTED_CHAINS,
    get_mtd_context,
    require_initialized,
)
from mtd.services.metadata.update_onchain import update_metadata_onchain


@click.command(name="update-metadata")
@click.option(
    "-c",
    "--chain-config",
    type=click.Choice(SUPPORTED_CHAINS, case_sensitive=False),
    required=True,
    help="Target chain for the metadata update.",
)
@click.pass_context
def update_metadata(ctx: click.Context, chain_config: str) -> None:
    """Update the metadata hash on-chain via Safe transaction.

    Example: mech update-metadata -c gnosis

    :param ctx: click context carrying the resolved MtdContext.
    :param chain_config: target chain name (e.g. ``gnosis``) for the metadata update.
    """
    context = get_mtd_context(ctx)
    require_initialized(context)

    click.echo("Updating metadata hash on-chain...")
    success, tx_hash = update_metadata_onchain(
        env_path=context.chain_env_path(chain_config),
        private_key_path=context.keys_dir / "ethereum_private_key.txt",
    )
    click.echo(f"Success: {success}")
    click.echo(f"Tx Hash: {tx_hash}")
