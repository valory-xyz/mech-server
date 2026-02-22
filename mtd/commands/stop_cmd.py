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

"""Stop command for stopping the mech agent service."""

import click
from operate.cli import OperateApp
from operate.quickstart.stop_service import stop_service

from mtd.commands.context_utils import (
    SUPPORTED_CHAINS,
    _workspace_cwd,
    get_mtd_context,
    require_initialized,
)


@click.command()
@click.option(
    "-c",
    "--chain-config",
    type=click.Choice(SUPPORTED_CHAINS, case_sensitive=False),
    required=True,
    help="Target chain for the mech agent.",
)
@click.pass_context
def stop(ctx: click.Context, chain_config: str) -> None:
    """Stop a running mech AI agent.

    Example: mech stop -c gnosis
    """
    context = get_mtd_context(ctx)
    require_initialized(context)

    config_path = context.config_dir / f"config_mech_{chain_config}.json"
    if not config_path.exists():
        raise click.ClickException(f"Missing template config: {config_path}")

    with _workspace_cwd(context):
        operate = OperateApp(home=context.operate_dir)
        operate.setup()
        stop_service(operate=operate, config_path=config_path)
