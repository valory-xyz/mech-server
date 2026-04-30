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

"""Workspace bootstrap helpers."""

import shutil
from pathlib import Path

import click
from mtd.context import MtdContext
from mtd.resources import copy_runtime_templates_to_workspace, read_text_resource


def initialize_workspace(context: MtdContext, force: bool = False) -> None:
    """Initialize or refresh the default workspace layout."""
    context.ensure_workspace_exists()

    copy_runtime_templates_to_workspace(context=context, force=force)

    if force or not context.env_path.exists():
        env_template = read_text_resource("mtd.templates.runtime", ".example.env")
        context.env_path.write_text(env_template, encoding="utf-8")

    packaged_root = Path(__file__).resolve().parent.parent / "packages"
    if not packaged_root.exists():
        raise click.ClickException(
            "Packaged tools directory not found in installation. Reinstall package."
        )

    if force and context.packages_dir.exists():
        shutil.rmtree(context.packages_dir)
    if not context.packages_dir.exists():
        shutil.copytree(
            packaged_root,
            context.packages_dir,
            ignore=shutil.ignore_patterns("echo"),
        )

    context.initialized_marker_path.write_text("initialized\n", encoding="utf-8")
