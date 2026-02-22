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

"""Setup command for mech agent service configuration and metadata deployment."""

import click

from mtd.commands.context_utils import SUPPORTED_CHAINS, get_mtd_context
from mtd.setup_flow import run_setup
from mtd.workspace import initialize_workspace


@click.command()
@click.option(
    "-c",
    "--chain-config",
    type=click.Choice(SUPPORTED_CHAINS, case_sensitive=False),
    required=True,
    help="Target chain for the mech agent.",
)
@click.pass_context
def setup(ctx: click.Context, chain_config: str) -> None:
    """Full first-time setup for a mech AI agent.

    Runs the full setup flow: agent build, mech deployment, env
    configuration, private key setup, metadata generation, IPFS
    publish, and on-chain metadata hash update.

    Example: mech setup -c gnosis
    """
    context = get_mtd_context(ctx)
    if not context.is_initialized():
        click.echo("Workspace not initialized. Bootstrapping workspace...")
        initialize_workspace(context=context, force=False)
    run_setup(chain_config=chain_config, context=context)
