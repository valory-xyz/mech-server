# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2023-2025 Valory AG
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

"""Mech deployment on the mech marketplace."""

import json
from typing import Any, Dict, Tuple

import click
import requests
from aea_ledger_ethereum import Web3
from operate.operate_types import Chain
from operate.services.protocol import EthSafeTxBuilder
from operate.services.service import Service
from operate.utils.gnosis import SafeOperation

MECH_MARKETPLACE_JSON_URL = (
    "https://raw.githubusercontent.com/valory-xyz/mech-quickstart/"
    "refs/heads/main/contracts/MechMarketplace.json"
)
DEFAULT_TIMEOUT = 30

# Registry of MechFactory contract addresses, nested as:
#   chain -> marketplace_address -> mech_type -> ordered candidate factories
# where:
#   chain             = Chain enum (from olas-operate-middleware)
#   marketplace_address = value of the MECH_MARKETPLACE_ADDRESS env variable
#   mech_type         = value of MECH_TYPE ("Native", "Token", "Nevermined", etc.)
#   candidates        = MechFactory addresses, newest deployment first
# A marketplace only accepts a factory it has enabled, and which factories are
# enabled changes with marketplace upgrades, so the candidates are probed
# on-chain and the first enabled one is used.
# Sources: https://github.com/valory-xyz/mech-quickstart/tree/main/contracts
#          https://github.com/valory-xyz/autonolas-marketplace/pull/211
# nosec B105 — public on-chain factory addresses, not secrets; bandit
# pattern-matches "Token": "0x..." as hardcoded credentials.
MECH_FACTORY_ADDRESS: Dict[Chain, Dict[str, Dict[str, Tuple[str, ...]]]] = {
    Chain.GNOSIS: {
        "0xad380C51cd5297FbAE43494dD5D407A2a3260b58": {
            "Native": ("0x42f43be9E5E50df51b86C5c6427223ff565f40C6",),
            "Token": ("0x161b862568E900Dd9d8c64364F3B83a43792e50f",),  # nosec B105
            "Nevermined": ("0xCB26B91B0E21ADb04FFB6e5f428f41858c64936A",),
        },
        "0x735FAAb1c4Ec41128c367AFb5c3baC73509f70bB": {
            "Native": (
                "0x5270c0797a9D0c59163cF570129E5808BE7927FA",
                "0x8b299c20F87e3fcBfF0e1B86dC0acC06AB6993EF",
            ),
            "Token": ("0x31ffDC795FDF36696B8eDF7583A3D115995a45FA",),  # nosec B105
            "Nevermined": ("0x65fd74C29463afe08c879a3020323DD7DF02DA57",),
        },
    },
    Chain.BASE: {
        "0xf24eE42edA0fc9b33B7D41B06Ee8ccD2Ef7C5020": {
            "Native": (
                "0xf8a8C985f46Ab6204e6A40845e73a6119f0458ED",
                "0x2E008211f34b25A7d7c102403c6C2C3B665a1abe",
            ),
            "Token": ("0x97371B1C0cDA1D04dFc43DFb50a04645b7Bc9BEe",),  # nosec B105
            "TokenUSDC": (
                "0x17D8B863F6c4601d67A87FDa04D53849c5F9Ce00",
                "0x5B70A66fe68c4c86FFd724B58cc56049c70e9D3D",
            ),
            "Nevermined": ("0x847bBE8b474e0820215f818858e23F5f5591855A",),
        },
    },
    Chain.POLYGON: {
        "0x343F2B005cF6D70bA610CD9F1F1927049414B582": {
            "Native": (
                "0x40dABcF2DEEc7241749B320cbC5ca69544a90d68",
                "0x87f89F94033305791B6269AE2F9cF4e09983E56e",
            ),
            "Token": ("0xa0DA53447C0f6C4987964d8463da7e6628B30f82",),  # nosec B105
            "TokenUSDC": (
                "0x749cdf4bF2e55269b3d1bC4b4408e34689c96B67",
                "0x85899f9d8C058A5BBBaF344ea0f0b63c0CcBe851",
            ),
            "Nevermined": ("0x43fB32f25dce34EB76c78C7A42C8F40F84BCD237",),
        },
    },
    Chain.OPTIMISM: {
        "0x46C0D07F55d4F9B5Eed2Fc9680B5953e5fd7b461": {
            "Native": (
                "0xaaFBeef195BDAb1Bb6f3Dc9cEbA875Cd72499230",
                "0xf76953444C35F1FcE2F6CA1b167173357d3F5C17",
            ),
            "Token": ("0x26Ea2dC7ce1b41d0AD0E0521535655d7a94b684c",),  # nosec B105
            "TokenUSDC": (
                "0xf78b3C22A204Da5d9a0B080C5D3d695AF4918886",
                "0x93111f6C267068A5d7356114D61d0f09bFD53a54",
            ),
            "Nevermined": ("0x02C26437B292D86c5F4F21bbCcE0771948274f84",),
        },
    },
}

# PAYMENT_TYPE constant of the OlasMech implementation each mech type deploys.
# The marketplace reverts a create() whose payment type has no balance tracker
# registered, so this is pre-checked where the mech type pins the payment type.
# The Nevermined mech type is deliberately absent: its factory deploys the
# native or the USDC subscription mech depending on the chain, so the payment
# type is not determined by the mech type alone.
# Source: https://github.com/valory-xyz/autonolas-marketplace/tree/main/contracts
MECH_TYPE_PAYMENT_TYPE: Dict[str, str] = {
    "Native": "0xba699a34be8fe0e7725e93dcbce1701b0211a8ca61330aaeb8a05bf2ec7abed1",
    "Token": (  # nosec B105
        "0x3679d66ef546e66ce9057c4a052f317b135bc8e8c509638f7966edfd4fcf45e9"
    ),
    "TokenUSDC": "0x6406bb5f31a732f898e1ce9fdd988a80a808d36ab5d9a4a4805a8be8d197d5e3",
}


def _select_mech_factory(
    contract: Any,
    chain_name: str,
    marketplace_address: str,
    mech_type: str,
    candidates: Tuple[str, ...],
) -> str:
    """Return the first candidate MechFactory the marketplace has enabled.

    :param contract: web3 contract bound to the configured MechMarketplace.
    :param chain_name: home chain name, used in the error message.
    :param marketplace_address: configured MechMarketplace address.
    :param mech_type: value of the MECH_TYPE env variable.
    :param candidates: known MechFactory addresses, newest deployment first.
    :return: address of the enabled MechFactory to create the mech with.
    :raises ClickException: if the marketplace has none of the candidates enabled.
    """
    for candidate in candidates:
        enabled = contract.functions.mapMechFactories(
            Web3.to_checksum_address(candidate)
        ).call()
        if enabled:
            return candidate
    raise click.ClickException(
        f"No enabled mech factory for mech type '{mech_type}' on chain "
        f"'{chain_name}' marketplace '{marketplace_address}'. "
        f"Factories tried: {', '.join(candidates)}."
    )


def _check_balance_tracker(
    contract: Any,
    chain_name: str,
    marketplace_address: str,
    mech_type: str,
) -> None:
    """Check the marketplace has a balance tracker for this mech type's payment type.

    :param contract: web3 contract bound to the configured MechMarketplace.
    :param chain_name: home chain name, used in the error message.
    :param marketplace_address: configured MechMarketplace address.
    :param mech_type: value of the MECH_TYPE env variable.
    :raises ClickException: if the payment type has no balance tracker registered.
    """
    payment_type = MECH_TYPE_PAYMENT_TYPE.get(mech_type)
    if payment_type is None:
        return
    tracker = contract.functions.mapPaymentTypeBalanceTrackers(payment_type).call()
    if int(str(tracker), 16) != 0:
        return
    raise click.ClickException(
        f"Marketplace '{marketplace_address}' on chain '{chain_name}' has no "
        f"balance tracker registered for the payment type of mech type "
        f"'{mech_type}' ({payment_type}). Creating the mech would be rejected "
        "until the marketplace owner registers one."
    )


def deploy_mech(sftxb: EthSafeTxBuilder, service: Service) -> Tuple[str, str]:
    """Deploy a new Mech on-chain via the MechMarketplace contract.

    :param sftxb: configured Safe-tx builder used to broadcast the marketplace call.
    :param service: operate service whose chain/marketplace settings drive the deploy.
    :return: tuple of (mech_address, agent_id) parsed from the CreateMech event.
    :raises ClickException: if the chain, marketplace, mech type or factory is not usable.
    """
    try:
        chain = Chain.from_string(service.home_chain)
    except Exception as exc:
        raise click.ClickException(
            f"Unsupported chain '{service.home_chain}' for mech deployment. "
            "Supported chains: gnosis, base, polygon, optimism."
        ) from exc
    if chain not in MECH_FACTORY_ADDRESS:
        raise click.ClickException(
            f"Chain '{service.home_chain}' has no mech factory addresses configured. "
            "Supported chains: gnosis, base, polygon, optimism."
        )

    mech_type = service.env_variables.get("MECH_TYPE", {}).get("value", "Native")
    try:
        response = requests.get(MECH_MARKETPLACE_JSON_URL, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        abi = response.json()["abi"]
    except requests.RequestException as exc:
        raise click.ClickException(
            f"Failed to fetch MechMarketplace ABI from {MECH_MARKETPLACE_JSON_URL}: {exc}"
        ) from exc
    except (KeyError, ValueError) as exc:
        raise click.ClickException(
            f"Unexpected response format from {MECH_MARKETPLACE_JSON_URL}: {exc}"
        ) from exc
    mech_marketplace_address = service.env_variables["MECH_MARKETPLACE_ADDRESS"][
        "value"
    ]
    marketplaces = MECH_FACTORY_ADDRESS[chain]
    if mech_marketplace_address not in marketplaces:
        raise click.ClickException(
            f"Marketplace address '{mech_marketplace_address}' is not supported "
            f"on chain '{service.home_chain}'. "
            f"Supported addresses: {', '.join(marketplaces)}."
        )
    candidates = marketplaces[mech_marketplace_address].get(mech_type, ())
    if not candidates:
        raise click.ClickException(
            f"Mech type '{mech_type}' has no mech factory configured on chain "
            f"'{service.home_chain}' marketplace '{mech_marketplace_address}'. "
            f"Supported mech types: "
            f"{', '.join(marketplaces[mech_marketplace_address])}."
        )

    mech_request_price = int(
        service.env_variables.get("MECH_REQUEST_PRICE", {}).get(
            "value", 10000000000000000
        )
    )
    contract = sftxb.ledger_api.api.eth.contract(
        address=Web3.to_checksum_address(mech_marketplace_address), abi=abi
    )
    mech_factory_address = _select_mech_factory(
        contract=contract,
        chain_name=service.home_chain,
        marketplace_address=mech_marketplace_address,
        mech_type=mech_type,
        candidates=candidates,
    )
    _check_balance_tracker(
        contract=contract,
        chain_name=service.home_chain,
        marketplace_address=mech_marketplace_address,
        mech_type=mech_type,
    )
    data = bytes.fromhex(
        contract.encode_abi(
            "create",
            args=[
                service.chain_configs[service.home_chain].chain_data.token,
                Web3.to_checksum_address(mech_factory_address),
                mech_request_price.to_bytes(32, byteorder="big"),
            ],
        )[2:]
    )
    tx_dict = {
        "to": mech_marketplace_address,
        "data": data,
        "value": 0,
        "operation": SafeOperation.CALL,
    }
    receipt = sftxb.new_tx().add(tx_dict).settle()
    event = contract.events.CreateMech().process_receipt(receipt)[0]
    mech_address = event["args"]["mech"]
    agent_id = sftxb.info(token_id=event["args"]["serviceId"])["canonical_agents"][0]
    return mech_address, agent_id


def needs_mech_deployment(service: Service) -> bool:
    """Check if the service needs a mech deployment."""
    required_vars = ["AGENT_ID", "MECH_TO_CONFIG", "MECH_MARKETPLACE_ADDRESS"]
    if not all(var in service.env_variables for var in required_vars):
        return False
    return (
        not service.env_variables["AGENT_ID"]["value"]
        or not service.env_variables["MECH_TO_CONFIG"]["value"]
    )


def update_service_after_deploy(
    service: Service, mech_address: str, agent_id: str
) -> None:
    """Update service env variables after mech deployment."""
    mech_request_price = int(
        service.env_variables.get("MECH_REQUEST_PRICE", {}).get(
            "value", 10000000000000000
        )
    )
    home_chain = service.home_chain
    chain_config = service.chain_configs[home_chain]
    chain_rpc = chain_config.ledger_config.rpc
    chain_rpc_env_var = f"{home_chain.upper()}_LEDGER_RPC_0"
    result = service.update_env_variables_values(
        {
            "AGENT_ID": agent_id,
            "MECH_TO_CONFIG": json.dumps(
                {
                    mech_address: {
                        "use_dynamic_pricing": False,
                        "is_marketplace_mech": True,
                    }
                },
                separators=(",", ":"),
            ),
            "MECH_TO_MAX_DELIVERY_RATE": json.dumps(
                {mech_address: mech_request_price},
                separators=(",", ":"),
            ),
            "ON_CHAIN_SERVICE_ID": chain_config.chain_data.token,
            "ETHEREUM_LEDGER_RPC_0": chain_rpc,
            chain_rpc_env_var: chain_rpc,
        }
    )
    if result is False:
        raise RuntimeError("Service env variable update failed after mech deployment.")
