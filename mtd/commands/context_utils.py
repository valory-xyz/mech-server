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

"""Helpers for accessing mech click context."""

import click
from mtd.context import SUPPORTED_CHAINS  # noqa: F401  # pylint: disable=unused-import
from mtd.context import (
    MtdContext,
    build_context,
)
from mtd.context import (  # noqa: F401  # pylint: disable=unused-import
    workspace_cwd as _workspace_cwd,
)


def get_mtd_context(ctx: click.Context) -> MtdContext:
    """Get mech context from click context object."""
    ctx_obj = ctx.ensure_object(dict)
    context = ctx_obj.get("mtd_context")
    if isinstance(context, MtdContext):
        return context

    fallback = build_context()
    ctx_obj["mtd_context"] = fallback
    return fallback


def require_initialized(context: MtdContext) -> None:
    """Raise if workspace is not initialized."""
    if not context.is_initialized():
        raise click.ClickException(
            f"Workspace is not initialized: {context.workspace_path}. "
            "Run 'mech setup -c <chain>' first."
        )
