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

"""Package resource utilities for runtime templates."""

from importlib import resources
from pathlib import Path
from typing import Iterable, Tuple

from mtd.context import MtdContext


RUNTIME_RESOURCE_PACKAGE = "mtd.templates.runtime"


def read_text_resource(package: str, name: str) -> str:
    """Read a text resource from package data."""
    return resources.files(package).joinpath(name).read_text(encoding="utf-8")


def iter_runtime_templates() -> Iterable[Tuple[str, str]]:
    """Iterate runtime template resources as (name, content)."""
    runtime_dir = resources.files(RUNTIME_RESOURCE_PACKAGE)
    for item in runtime_dir.iterdir():
        if item.is_file():
            yield item.name, item.read_text(encoding="utf-8")


def copy_runtime_templates_to_workspace(
    context: MtdContext, force: bool = False
) -> None:
    """Copy packaged runtime templates into a workspace."""
    context.ensure_workspace_exists()
    context.config_dir.mkdir(parents=True, exist_ok=True)
    context.keys_dir.mkdir(parents=True, exist_ok=True)
    context.operate_dir.mkdir(parents=True, exist_ok=True)

    for name, content in iter_runtime_templates():
        target: Path
        if name.startswith("config_mech_") and name.endswith(".json"):
            target = context.config_dir / name
        elif name == ".example.env":
            target = context.workspace_path / name
        elif name.startswith("metadata"):
            target = context.workspace_path / name
        else:
            continue

        if target.exists() and not force:
            continue
        target.write_text(content, encoding="utf-8")
