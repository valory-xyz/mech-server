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
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Optional, Tuple

import click
from aea.cli.packages import package_type_selector_prompt
from dotenv import dotenv_values, set_key
from mtd.commands.context_utils import (
    SUPPORTED_CHAINS,
    get_mtd_context,
    require_initialized,
)
from mtd.context import MtdContext
from mtd.services.metadata import (
    Benchmark,
    DEFAULT_IPFS_NODE,
    Operator,
    generate_metadata,
    publish_metadata_to_ipfs,
)

from autonomy.cli.packages import get_package_manager


def _clean_packages_dir(packages_dir: Path) -> None:
    """Remove __pycache__ dirs and .DS_Store files before locking/pushing.

    ``generate_metadata`` imports tool modules via ``importlib``, which
    creates ``__pycache__`` directories containing binary ``.pyc`` files.
    If these are present when ``autonomy push-all`` runs they get uploaded
    to IPFS, and the mech's IPFS connection fails with a
    ``UnicodeDecodeError`` when it tries to decode them as UTF-8.

    :param packages_dir: workspace ``packages/`` root to scrub in-place.
    """
    for pycache in packages_dir.rglob("__pycache__"):
        shutil.rmtree(pycache, ignore_errors=True)
    for ds_store in packages_dir.rglob(".DS_Store"):
        ds_store.unlink(missing_ok=True)


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
    subprocess.run(  # nosec B607 — `autonomy` resolves via PATH inside the workspace venv
        ["autonomy", "push-all"],
        check=True,
        cwd=str(workspace_path),
    )
    click.echo("Packages pushed.")


def _compute_tools_to_package_hash(  # pylint: disable=too-many-return-statements
    packages_dir: Path, metadata_path: Path
) -> str:
    """Compute TOOLS_TO_PACKAGE_HASH mapping model names to IPFS hashes.

    Each model name from ALLOWED_TOOLS (e.g. ``openai-gpt-3.5-turbo-instruct``)
    is mapped to the IPFS hash of its parent tool package, rather than mapping
    the tool package name itself.

    :param packages_dir: workspace ``packages/`` root containing ``packages.json``.
    :param metadata_path: path to the generated ``metadata.json`` whose
        ``toolMetadata`` is read to map model names to tool packages.
    :return: JSON-encoded mapping (compact form), or empty string when
        prerequisites are missing or yield no mapping.
    """
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
    package_hash_by_name: dict = {}
    for key, ipfs_hash in dev_packages.items():
        parts = key.split("/")
        if len(parts) != 4 or parts[0] != "custom":
            continue
        tool_name = parts[2]
        package_hash_by_name[tool_name] = ipfs_hash

    if not package_hash_by_name:
        return ""

    if not metadata_path.exists():
        click.echo(
            f"Warning: {metadata_path} not found. "
            "Cannot resolve model names for TOOLS_TO_PACKAGE_HASH."
        )
        return ""

    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        click.echo(f"Warning: {metadata_path} contains invalid JSON. Skipping.")
        return ""

    tool_metadata = metadata.get("toolMetadata", {})
    tools_mapping: dict = {}
    for model_name, meta in tool_metadata.items():
        tool_name = meta.get("name", "")
        ipfs_hash = package_hash_by_name.get(tool_name)
        if ipfs_hash:
            tools_mapping[model_name] = ipfs_hash

    if not tools_mapping:
        return ""

    return json.dumps(tools_mapping, separators=(",", ":"))


def _update_chain_config(
    context: MtdContext, chain: str, updates: dict[str, str]
) -> None:
    """Update env_variables in the chain config template JSON.

    The template at ``config/<chain>.json`` is read by ``mech run`` via
    ``run_service()`` which re-applies its values to the service.  Keeping
    the template in sync prevents ``mech run`` from overwriting values
    that ``_sync_service_env_vars`` wrote to the service ``config.json``.

    :param context: resolved MtdContext used to locate the chain config template.
    :param chain: chain name (e.g. ``gnosis``) selecting the template file.
    :param updates: mapping of env-var name to new value to apply.
    """
    config_path = context.config_dir / f"config_mech_{chain}.json"
    if not config_path.exists():
        return

    config = json.loads(config_path.read_text(encoding="utf-8"))
    env_vars = config.get("env_variables", {})

    changed = False
    for key, value in updates.items():
        entry = env_vars.get(key)
        if isinstance(entry, dict) and entry.get("value") != value:
            entry["value"] = value
            changed = True

    if changed:
        config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        click.echo(f"  Updated chain config template for {chain}")


BenchmarkArg = Tuple[str, str, float, str]


def _build_operator(
    name: Optional[str], domain: Optional[str], contact: Optional[str]
) -> Optional[Operator]:
    """Turn the ``--operator-*`` flags into an Operator, or None when none were given.

    :param name: value of ``--operator-name``.
    :param domain: value of ``--operator-domain``.
    :param contact: value of ``--operator-contact``.
    :return: the operator block, or None when no operator flag was passed.
    :raises ClickException: when the flags are incomplete or invalid.
    """
    if name is None and domain is None:
        if contact is not None:
            raise click.ClickException(
                "--operator-contact requires --operator-name and --operator-domain."
            )
        return None
    if name is None or domain is None:
        raise click.ClickException(
            "--operator-name and --operator-domain must be given together."
        )
    try:
        return Operator(name=name, domain=domain, contact=contact)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc


def _build_benchmarks(
    entries: Tuple[BenchmarkArg, ...], url: Optional[str]
) -> Dict[str, Benchmark]:
    """Turn repeated ``--benchmark`` flags plus ``--benchmark-url`` into per-tool benchmarks.

    :param entries: ``(tool, metric, value, window)`` tuples from ``--benchmark``.
    :param url: value of ``--benchmark-url``, shared by every entry.
    :return: benchmarks keyed by tool name; empty when no flag was passed.
    :raises ClickException: when the flags are incomplete or invalid.
    """
    if not entries:
        if url is not None:
            raise click.ClickException(
                "--benchmark-url requires at least one --benchmark."
            )
        return {}
    if url is None:
        raise click.ClickException("--benchmark requires --benchmark-url.")
    benchmarks: Dict[str, Benchmark] = {}
    for tool, metric, value, window in entries:
        if tool in benchmarks:
            raise click.ClickException(
                f"Tool {tool!r} is given more than once in --benchmark."
            )
        try:
            benchmarks[tool] = Benchmark(
                metric=metric, value=value, window=window, url=url
            )
        except ValueError as exc:
            raise click.ClickException(
                f"Invalid --benchmark for {tool!r}: {exc}"
            ) from exc
    return benchmarks


def _resolve_offchain_url(
    explicit_url: Optional[str],
    context: MtdContext,
    chain_config: Optional[str],
) -> str:
    """Resolve the offchain URL from CLI option or chain .env file."""
    if explicit_url:
        return explicit_url
    if chain_config:
        env_path = context.chain_env_path(chain_config)
        if env_path.exists():
            env_values = dotenv_values(str(env_path))
            return (env_values.get("MECH_OFFCHAIN_URL") or "").strip()
    return ""


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
@click.option(
    "--offchain-url",
    type=str,
    default=None,
    help="Public URL where the mech serves off-chain requests.",
)
@click.option(
    "--name",
    "mech_name",
    type=str,
    required=True,
    help="Human-readable mech name written to the metadata.",
)
@click.option(
    "--operator-name",
    type=str,
    default=None,
    help="Operator running the mech. Requires --operator-domain.",
)
@click.option(
    "--operator-domain",
    type=str,
    default=None,
    help=(
        "Lowercase bare hostname (no scheme or path) serving the operator's "
        "/.well-known/agent-registration.json. Requires --operator-name."
    ),
)
@click.option(
    "--operator-contact",
    type=str,
    default=None,
    help="Optional operator contact, such as an email address.",
)
@click.option(
    "--benchmark-url",
    type=str,
    default=None,
    help="Analytics endpoint shared by every --benchmark entry.",
)
@click.option(
    "--benchmark",
    "benchmarks",
    type=(str, str, float, str),
    multiple=True,
    metavar="TOOL METRIC VALUE WINDOW",
    help=(
        "Per-tool benchmark, e.g. --benchmark openai-gpt-4 accuracy 0.83 30d. "
        "VALUE is 0..1, WINDOW is 7d, 30d, 90d or all. Repeatable; "
        "requires --benchmark-url."
    ),
)
@click.pass_context
def prepare_metadata(  # pylint: disable=too-many-arguments,too-many-locals
    ctx: click.Context,
    chain_config: Optional[str],
    ipfs_node: str,
    offchain_url: Optional[str],
    mech_name: str,
    operator_name: Optional[str],
    operator_domain: Optional[str],
    operator_contact: Optional[str],
    benchmark_url: Optional[str],
    benchmarks: Tuple[BenchmarkArg, ...],
) -> None:
    """Generate metadata.json from packages and publish to IPFS.

    Locks package hashes, pushes all packages to IPFS, generates
    metadata, publishes it, and updates chain .env files with
    METADATA_HASH and TOOLS_TO_PACKAGE_HASH.

    Examples:
        mech prepare-metadata --name "My Mech"
        mech prepare-metadata --name "My Mech" -c gnosis
        mech prepare-metadata --name "My Mech" -c gnosis --offchain-url <url>
        mech prepare-metadata --name "My Mech" -c gnosis --operator-name Valory --operator-domain valory.xyz
        mech prepare-metadata --name "My Mech" -c gnosis --benchmark-url <url> --benchmark openai-gpt-4 accuracy 0.83 30d

    :param ctx: click context carrying the resolved MtdContext.
    :param chain_config: target chain whose .env to update (None = all chains).
    :param ipfs_node: IPFS node multiaddr to publish to.
    :param offchain_url: public off-chain URL to embed in metadata; falls back
        to ``MECH_OFFCHAIN_URL`` from the chain .env when omitted.
    :param mech_name: human-readable mech name written to the metadata.
    :param operator_name: operator name; paired with ``operator_domain``.
    :param operator_domain: bare hostname serving the operator's domain proof.
    :param operator_contact: optional operator contact.
    :param benchmark_url: analytics endpoint shared by every benchmark entry.
    :param benchmarks: ``(tool, metric, value, window)`` tuples, one per tool.
    """
    context = get_mtd_context(ctx)
    require_initialized(context)

    operator = _build_operator(operator_name, operator_domain, operator_contact)
    tool_benchmarks = _build_benchmarks(benchmarks, benchmark_url)

    _clean_packages_dir(context.packages_dir)
    _lock_packages(context.packages_dir)
    _push_all_packages(context.workspace_path, context.packages_dir)

    resolved_url = _resolve_offchain_url(offchain_url, context, chain_config)
    if resolved_url:
        click.echo(f"Including offchain URL in metadata: {resolved_url}")

    click.echo("Generating metadata...")
    try:
        generate_metadata(
            packages_dir=context.packages_dir,
            metadata_path=context.metadata_path,
            name=mech_name,
            offchain_url=resolved_url,
            operator=operator,
            benchmarks=tool_benchmarks,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    _clean_packages_dir(context.packages_dir)

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
        if offchain_url:
            set_key(
                str(context.chain_env_path(chain)),
                "MECH_OFFCHAIN_URL",
                offchain_url,
            )
    click.echo(f"Metadata hash: {metadata_hash}")

    click.echo("Computing tools-to-package-hash mapping...")
    tools_hash_value = _compute_tools_to_package_hash(
        context.packages_dir, context.metadata_path
    )
    if tools_hash_value:
        for chain in chains:
            set_key(
                str(context.chain_env_path(chain)),
                "TOOLS_TO_PACKAGE_HASH",
                tools_hash_value,
            )
        click.echo(f"Tools-to-package-hash: {tools_hash_value}")

    if chain_config:
        click.echo("Syncing service config...")
        svc_updates: dict[str, str] = {"METADATA_HASH": metadata_hash}
        if tools_hash_value:
            svc_updates["TOOLS_TO_PACKAGE_HASH"] = tools_hash_value
        if resolved_url:
            svc_updates["SERVICE_ENDPOINT_BASE"] = resolved_url
        _update_chain_config(context, chain_config, svc_updates)
    click.echo("Done.")
