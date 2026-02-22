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

"""Add-tool command for scaffolding new mech tools."""

from importlib import resources
from pathlib import Path
from string import Template
from time import localtime
from typing import Dict

import click
from aea.cli.packages import package_type_selector_prompt

from autonomy.cli.packages import get_package_manager
from mtd.commands.context_utils import get_mtd_context, require_initialized


CUSTOMS_DIR = "customs"
PY_SUFFIX = ".py"
INIT_FILENAME = f"__init__{PY_SUFFIX}"
CONFIG_FILENAME = "component.yaml"
TEMPLATE_SUFFIX = ".template"
TEMPLATES_PACKAGE = "mtd.templates"
INIT_TEMPLATE = f"init{TEMPLATE_SUFFIX}"
CONFIG_TEMPLATE = f"config{TEMPLATE_SUFFIX}"
TOOL_TEMPLATE = f"tool{TEMPLATE_SUFFIX}"
WRITE_MODE = "w"


def _read_template(template_name: str) -> str:
    """Read a scaffolding template from the mtd.templates package."""
    return (
        resources.files(TEMPLATES_PACKAGE)
        .joinpath(template_name)
        .read_text(encoding="utf-8")
    )


def generate_tool_file(
    template_name: str,
    template_params: Dict[str, str],
    filename: str,
    tool_path: Path,
    packages_dir: Path,
) -> None:
    """Generate a file from a template."""
    template = Template(_read_template(template_name))
    content = template.substitute(**template_params)

    if filename != INIT_FILENAME:
        with open(tool_path / filename, WRITE_MODE, encoding="utf-8") as file:
            file.write(content)
            return

    current = tool_path
    while current != packages_dir:
        with open(current / filename, WRITE_MODE, encoding="utf-8") as file:
            file.write(content)
            current = current.parent


def generate_tool(
    author: str,
    tool_name: str,
    tool_description: str,
    packages_dir: Path,
) -> None:
    """Generate the tool files."""
    template_to_file = {
        INIT_TEMPLATE: INIT_FILENAME,
        CONFIG_TEMPLATE: CONFIG_FILENAME,
        TOOL_TEMPLATE: f"{tool_name}{PY_SUFFIX}",
    }

    template_params = {
        "year": str(localtime().tm_year),
        "authorname": author,
        "tool_name": tool_name,
        "tool_description": tool_description,
    }

    tool_path = packages_dir / author / CUSTOMS_DIR / tool_name
    tool_path.mkdir(parents=True, exist_ok=True)

    for template, filename in template_to_file.items():
        generate_tool_file(template, template_params, filename, tool_path, packages_dir)


@click.command()
@click.argument("author", type=str)
@click.argument("tool_name", type=str)
@click.option(
    "-d",
    "--tool-description",
    type=str,
    default="A mech tool.",
    required=False,
    help="The tool's description.",
)
@click.option(
    "-s",
    "--skip-lock",
    type=bool,
    is_flag=True,
    default=False,
    required=False,
    help="Whether locking packages should be skipped after creating the tool template.",
)
@click.option(
    "--packages-dir",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    default=None,
    help="Optional custom packages directory. Defaults to <workspace>/packages.",
)
@click.pass_context
def add_tool(
    ctx: click.Context,
    author: str,
    tool_name: str,
    tool_description: str,
    skip_lock: bool,
    packages_dir: Path,
) -> None:
    """Add a new mech tool."""
    context = get_mtd_context(ctx)
    require_initialized(context)

    target_packages_dir = packages_dir or context.packages_dir
    target_packages_dir.mkdir(parents=True, exist_ok=True)

    click.echo(f"Adding tool: {author}/{tool_name}.")
    generate_tool(author, tool_name, tool_description, target_packages_dir)
    click.echo(f"Tool {author}/{tool_name} added at {target_packages_dir}.")

    if skip_lock:
        return

    click.echo("Locking packages...")
    get_package_manager(target_packages_dir).update_package_hashes(
        package_type_selector_prompt
    ).dump()
    click.echo("Packages locked.")
