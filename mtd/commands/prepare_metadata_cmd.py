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
import requests
from aea.cli.packages import package_type_selector_prompt
from dotenv import dotenv_values, set_key
from mtd.commands.context_utils import (
    SUPPORTED_CHAINS,
    get_mtd_context,
    require_initialized,
)
from mtd.context import MtdContext
from mtd.resources import refresh_chain_config
from mtd.services.metadata import (
    Benchmark,
    DEFAULT_IPFS_NODE,
    ExpectedCost,
    Operator,
    PAYMENT_ASSETS,
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

    refresh_chain_config(context=context, chain_config=chain)
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


BenchmarkArg = Tuple[str, str, str]
ExpectedCostArg = Tuple[str, str]

# The asset a mech of each MECH_TYPE is paid in, as readers of the manifest
# name it. Nevermined mechs are not listed: the type does not say whether
# the subscription is settled in the native token or in USDC.
PAYMENT_ASSET_BY_MECH_TYPE = {
    "Native": "native",
    "Token": "olas",  # nosec B105
    "TokenUSDC": "usdc",
}

# The marketplace serves every service's ERC-8004 registration file, which
# carries the agent id under ``registrations``. Keyed by chain config name.
ERC8004_REGISTRATION_URL = (
    "https://marketplace.olas.network/api/erc8004/{network}/ai-agents/{service_id}"
)
ERC8004_NETWORK_SLUGS = {
    "gnosis": "gnosis",
    "base": "base",
    "polygon": "polygon",
    "optimism": "op-mainnet",
}
ERC8004_LOOKUP_TIMEOUT = 10


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

    :param entries: ``(tool, metric, window)`` tuples from ``--benchmark``.
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
    for tool, metric, window in entries:
        if tool in benchmarks:
            raise click.ClickException(
                f"Tool {tool!r} is given more than once in --benchmark."
            )
        try:
            benchmarks[tool] = Benchmark(metric=metric, window=window, url=url)
        except ValueError as exc:
            raise click.ClickException(
                f"Invalid --benchmark for {tool!r}: {exc}"
            ) from exc
    return benchmarks


def _read_chain_env(context: MtdContext, chain_config: Optional[str], key: str) -> str:
    """Read ``key`` from the chain .env file, or empty when there is none."""
    if not chain_config:
        return ""
    env_path = context.chain_env_path(chain_config)
    if not env_path.exists():
        return ""
    return (dotenv_values(str(env_path)).get(key) or "").strip()


def _read_mech_type(context: MtdContext, chain_config: Optional[str]) -> str:
    """Read ``MECH_TYPE`` from the chain config template, or empty when unknown."""
    if not chain_config:
        return ""
    config_path = context.config_dir / f"config_mech_{chain_config}.json"
    if not config_path.exists():
        return ""
    config = json.loads(config_path.read_text(encoding="utf-8"))
    entry = config.get("env_variables", {}).get("MECH_TYPE")
    if not isinstance(entry, dict):
        return ""
    return str(entry.get("value") or "").strip()


def _resolve_payment_asset(
    explicit_asset: Optional[str],
    context: MtdContext,
    chain_config: Optional[str],
) -> str:
    """Name the asset the expected costs are stated in: the flag, else the mech's type.

    :param explicit_asset: value of ``--expected-cost-asset``.
    :param context: resolved MtdContext used to locate the chain config.
    :param chain_config: target chain, or None.
    :return: one of ``PAYMENT_ASSETS``.
    :raises ClickException: when neither the flag nor ``MECH_TYPE`` names an asset.
    """
    if explicit_asset:
        return explicit_asset
    mech_type = _read_mech_type(context, chain_config)
    asset = PAYMENT_ASSET_BY_MECH_TYPE.get(mech_type)
    if asset is None:
        if mech_type:
            why = f"MECH_TYPE {mech_type!r} in the {chain_config} config does not name one"
        else:
            why = "no chain config with MECH_TYPE was found (pass -c)"
        raise click.ClickException(
            f"Cannot tell the payment asset for --expected-cost: {why}. "
            f"Pass --expected-cost-asset {', '.join(PAYMENT_ASSETS)}."
        )
    return asset


def _read_tool_floors(
    context: MtdContext, chain_config: Optional[str]
) -> Dict[str, int]:
    """Read the per-tool price floors from ``TOOLS_TO_PRICING`` in the chain .env.

    :param context: resolved MtdContext used to locate the chain .env.
    :param chain_config: target chain, or None.
    :return: price by tool name in base units; empty when the variable is unset.
    :raises ClickException: when the variable is not a JSON object of tool to integer.
    """
    raw = _read_chain_env(context, chain_config, "TOOLS_TO_PRICING")
    if not raw:
        return {}
    try:
        return {str(tool): int(price) for tool, price in json.loads(raw).items()}
    except (ValueError, TypeError, AttributeError) as exc:
        raise click.ClickException(
            f"TOOLS_TO_PRICING in the {chain_config} .env is not a JSON object "
            f"of tool name to integer price: {exc}"
        ) from exc


def _build_expected_costs(
    entries: Tuple[ExpectedCostArg, ...], asset: str, floors: Dict[str, int]
) -> Dict[str, ExpectedCost]:
    """Turn repeated ``--expected-cost`` flags into per-tool expected costs.

    :param entries: ``(tool, amount)`` tuples from ``--expected-cost``.
    :param asset: the asset every amount is stated in.
    :param floors: the tools' configured prices, from ``TOOLS_TO_PRICING``.
    :return: expected costs keyed by tool name; empty when no flag was passed.
    :raises ClickException: when an entry is repeated, malformed, or below
        the tool's configured price.
    """
    costs: Dict[str, ExpectedCost] = {}
    for tool, amount in entries:
        if tool in costs:
            raise click.ClickException(
                f"Tool {tool!r} is given more than once in --expected-cost."
            )
        try:
            costs[tool] = ExpectedCost(asset=asset, amount=amount)
        except ValueError as exc:
            raise click.ClickException(
                f"Invalid --expected-cost for {tool!r}: {exc}"
            ) from exc
        floor = floors.get(tool)
        if floor is not None and int(amount) < floor:
            raise click.ClickException(
                f"--expected-cost for {tool!r} is {amount}, below the tool's "
                f"configured price {floor} in TOOLS_TO_PRICING. Clients size "
                f"their cap from the expected cost and the mech refuses a cap "
                f"below the price, so publish at least {floor}."
            )
    return costs


def _resolve_expected_costs(
    entries: Tuple[ExpectedCostArg, ...],
    explicit_asset: Optional[str],
    context: MtdContext,
    chain_config: Optional[str],
) -> Dict[str, ExpectedCost]:
    """Resolve the asset and floors for ``--expected-cost`` and build the entries.

    :param entries: ``(tool, amount)`` tuples from ``--expected-cost``.
    :param explicit_asset: value of ``--expected-cost-asset``.
    :param context: resolved MtdContext.
    :param chain_config: target chain, or None.
    :return: expected costs keyed by tool name; empty when no flag was passed.
    :raises ClickException: when the flags are incomplete or invalid.
    """
    if not entries:
        if explicit_asset is not None:
            raise click.ClickException(
                "--expected-cost-asset requires at least one --expected-cost."
            )
        return {}
    asset = _resolve_payment_asset(explicit_asset, context, chain_config)
    floors = _read_tool_floors(context, chain_config)
    costs = _build_expected_costs(entries, asset, floors)
    click.echo(f"Expected cost asset: {asset}")
    return costs


def _resolve_offchain_url(
    explicit_url: Optional[str],
    context: MtdContext,
    chain_config: Optional[str],
) -> str:
    """Resolve the offchain URL from CLI option or chain .env file."""
    if explicit_url:
        return explicit_url
    return _read_chain_env(context, chain_config, "MECH_OFFCHAIN_URL")


def _resolve_terms_url(
    explicit_url: Optional[str],
    context: MtdContext,
    chain_config: Optional[str],
) -> str:
    """Resolve the terms URL from CLI option or chain .env file."""
    if explicit_url:
        return explicit_url
    return _read_chain_env(context, chain_config, "MECH_TERMS_URL")


def _resolve_erc8004_agent_id(
    explicit_id: Optional[int],
    context: MtdContext,
    chain_config: Optional[str],
) -> Optional[int]:
    """Resolve the service's ERC-8004 agent id, which is not the service id.

    Reads it from the marketplace's registration file for the service when
    not given. Best effort: a lookup that fails leaves the id unset and says
    so, since the mech serves its domain proof only once the id is known.

    :param explicit_id: the id passed on the command line, if any.
    :param context: resolved MtdContext used to locate the chain .env.
    :param chain_config: target chain, or None.
    :return: the agent id, or None when it could not be resolved.
    """
    if explicit_id is not None:
        return explicit_id
    network = ERC8004_NETWORK_SLUGS.get(chain_config or "")
    service_id = _read_chain_env(context, chain_config, "ON_CHAIN_SERVICE_ID")
    if network is None or not service_id.isdigit():
        return None
    url = ERC8004_REGISTRATION_URL.format(network=network, service_id=service_id)
    try:
        response = requests.get(url, timeout=ERC8004_LOOKUP_TIMEOUT)
        response.raise_for_status()
        registrations = response.json().get("registrations") or []
        agent_id = registrations[0]["agentId"]
    except (requests.RequestException, ValueError, LookupError, TypeError) as exc:
        click.echo(
            f"Could not resolve the ERC-8004 agent id for service {service_id} "
            f"from {url}: {exc}. Pass --erc8004-agent-id to set it."
        )
        return None
    if isinstance(agent_id, bool) or not isinstance(agent_id, int) or agent_id < 0:
        click.echo(f"Unexpected ERC-8004 agent id {agent_id!r} at {url}; ignoring.")
        return None
    return agent_id


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
    "--terms-url",
    type=str,
    default=None,
    help=(
        "https link to the operator's terms, written to the metadata and "
        "advertised on off-chain responses. Falls back to MECH_TERMS_URL."
    ),
)
@click.option(
    "--erc8004-agent-id",
    type=int,
    default=None,
    help=(
        "The service's ERC-8004 agent id, served in the domain proof. Not the "
        "Olas service id. Resolved from the marketplace when omitted."
    ),
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
    type=(str, str, str),
    multiple=True,
    metavar="TOOL METRIC WINDOW",
    help=(
        "Per-tool benchmark link, e.g. --benchmark openai-gpt-4 accuracy 30d. "
        "WINDOW is 7d, 30d, 90d or all; the live figure is read from "
        "--benchmark-url, so no value is written. Repeatable; "
        "requires --benchmark-url."
    ),
)
@click.option(
    "--expected-cost",
    "expected_costs",
    type=(str, str),
    multiple=True,
    metavar="TOOL AMOUNT",
    help=(
        "What a tool usually costs, as guidance for requesters choosing a "
        "cap, e.g. --expected-cost openai-gpt-4 12000000000000000. AMOUNT is "
        "a decimal integer in the base units of the mech's payment asset (wei "
        "for native and OLAS, 6-decimal units for USDC), at or above the "
        "tool's price in TOOLS_TO_PRICING. Repeatable."
    ),
)
@click.option(
    "--expected-cost-asset",
    type=click.Choice(PAYMENT_ASSETS),
    default=None,
    help=(
        "Asset the --expected-cost amounts are stated in. Read from MECH_TYPE "
        "in the chain config when omitted."
    ),
)
@click.pass_context
def prepare_metadata(  # pylint: disable=too-many-arguments,too-many-locals,too-many-statements
    ctx: click.Context,
    chain_config: Optional[str],
    ipfs_node: str,
    offchain_url: Optional[str],
    terms_url: Optional[str],
    erc8004_agent_id: Optional[int],
    mech_name: str,
    operator_name: Optional[str],
    operator_domain: Optional[str],
    operator_contact: Optional[str],
    benchmark_url: Optional[str],
    benchmarks: Tuple[BenchmarkArg, ...],
    expected_costs: Tuple[ExpectedCostArg, ...],
    expected_cost_asset: Optional[str],
) -> None:
    """Generate metadata.json from packages and publish to IPFS.

    Generates metadata from the local packages, locks package hashes,
    pushes all packages to IPFS, publishes the metadata, and updates
    chain .env files with METADATA_HASH and TOOLS_TO_PACKAGE_HASH.
    Every input is validated before anything is pushed.

    Examples:
        mech prepare-metadata --name "My Mech"
        mech prepare-metadata --name "My Mech" -c gnosis
        mech prepare-metadata --name "My Mech" -c gnosis --offchain-url <url>
        mech prepare-metadata --name "My Mech" -c gnosis --operator-name Valory --operator-domain valory.xyz
        mech prepare-metadata --name "My Mech" -c gnosis --benchmark-url <url> --benchmark openai-gpt-4 accuracy 30d
        mech prepare-metadata --name "My Mech" -c gnosis --expected-cost openai-gpt-4 12000000000000000

    :param ctx: click context carrying the resolved MtdContext.
    :param chain_config: target chain whose .env to update (None = all chains).
    :param ipfs_node: IPFS node multiaddr to publish to.
    :param offchain_url: public off-chain URL to embed in metadata; falls back
        to ``MECH_OFFCHAIN_URL`` from the chain .env when omitted.
    :param terms_url: link to the operator's terms; falls back to
        ``MECH_TERMS_URL`` from the chain .env when omitted.
    :param erc8004_agent_id: the service's ERC-8004 agent id; resolved from
        the marketplace's registration file when omitted.
    :param mech_name: human-readable mech name written to the metadata.
    :param operator_name: operator name; paired with ``operator_domain``.
    :param operator_domain: bare hostname serving the operator's domain proof.
    :param operator_contact: optional operator contact.
    :param benchmark_url: analytics endpoint shared by every benchmark entry.
    :param benchmarks: ``(tool, metric, window)`` tuples, one per tool.
    :param expected_costs: ``(tool, amount)`` tuples, one per tool.
    :param expected_cost_asset: asset the amounts are stated in; read from
        ``MECH_TYPE`` in the chain config when omitted.
    """
    context = get_mtd_context(ctx)
    require_initialized(context)

    if not mech_name.strip():
        raise click.ClickException("--name must not be blank.")
    operator = _build_operator(operator_name, operator_domain, operator_contact)
    tool_benchmarks = _build_benchmarks(benchmarks, benchmark_url)
    tool_expected_costs = _resolve_expected_costs(
        expected_costs, expected_cost_asset, context, chain_config
    )

    resolved_url = _resolve_offchain_url(offchain_url, context, chain_config)
    if resolved_url:
        click.echo(f"Including offchain URL in metadata: {resolved_url}")
    resolved_terms_url = _resolve_terms_url(terms_url, context, chain_config)
    if resolved_terms_url:
        click.echo(f"Including terms URL in metadata: {resolved_terms_url}")
    resolved_agent_id = _resolve_erc8004_agent_id(
        erc8004_agent_id, context, chain_config
    )
    if resolved_agent_id is not None:
        click.echo(f"ERC-8004 agent id: {resolved_agent_id}")

    click.echo("Generating metadata...")
    try:
        generate_metadata(
            packages_dir=context.packages_dir,
            metadata_path=context.metadata_path,
            name=mech_name,
            offchain_url=resolved_url,
            operator=operator,
            benchmarks=tool_benchmarks,
            terms_url=resolved_terms_url,
            expected_costs=tool_expected_costs,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    _clean_packages_dir(context.packages_dir)

    _lock_packages(context.packages_dir)
    _push_all_packages(context.workspace_path, context.packages_dir)

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
        if terms_url:
            set_key(str(context.chain_env_path(chain)), "MECH_TERMS_URL", terms_url)
        if resolved_agent_id is not None:
            set_key(
                str(context.chain_env_path(chain)),
                "ERC8004_AGENT_ID",
                str(resolved_agent_id),
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
        if resolved_terms_url:
            svc_updates["MECH_TERMS_URL"] = resolved_terms_url
        if resolved_agent_id is not None:
            svc_updates["ERC8004_AGENT_ID"] = str(resolved_agent_id)
        _update_chain_config(context, chain_config, svc_updates)
    click.echo("Done.")
