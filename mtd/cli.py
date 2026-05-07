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

"""The mech tools dev CLI's entry point."""

import click
from mtd.commands import add_tool, prepare_metadata, run, setup, stop, update_metadata
from mtd.context import build_context


@click.group()
@click.pass_context
def cli(ctx: click.Context) -> None:
    """CLI to create, deploy and manage Mechs on the Olas Marketplace."""
    ctx.ensure_object(dict)
    ctx.obj["mtd_context"] = build_context()


cli.add_command(add_tool)
cli.add_command(setup)
cli.add_command(run)
cli.add_command(stop)
cli.add_command(prepare_metadata)
cli.add_command(update_metadata)
