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

"""Metadata on-chain update service."""

import json
import os
from importlib import resources as importlib_resources
from pathlib import Path
from typing import Dict, Optional, Tuple

import dotenv
from aea.helpers.multiformat import multibase_decode, multicodec_remove_prefix
from safe_eth.eth import EthereumClient  # pylint: disable=import-error
from safe_eth.safe import Safe  # pylint: disable=import-error
from web3 import Web3
from web3.constants import ADDRESS_ZERO
from web3.contract import Contract
from web3.types import TxReceipt


def _load_env(env_path: Path) -> Dict[str, str]:
    """Load and validate required runtime env values."""
    dotenv.load_dotenv(dotenv_path=str(env_path), override=True)

    default_chain = (os.environ.get("DEFAULT_CHAIN_ID") or "").strip().upper()
    if not default_chain:
        raise ValueError("Missing DEFAULT_CHAIN_ID in environment.")

    chain_rpc = os.environ.get(f"{default_chain}_LEDGER_RPC_0", "")
    chain_id = os.environ.get(f"{default_chain}_LEDGER_CHAIN_ID", "")
    if not chain_rpc:
        raise ValueError(
            f"Missing RPC for chain {default_chain}: {default_chain}_LEDGER_RPC_0"
        )
    if not chain_id:
        raise ValueError(
            f"Missing chain id for chain {default_chain}: {default_chain}_LEDGER_CHAIN_ID"
        )

    required = {
        "CHAIN_RPC": chain_rpc,
        "CHAIN_ID": chain_id,
        "COMPLEMENTARY_SERVICE_METADATA_ADDRESS": os.environ.get(
            "COMPLEMENTARY_SERVICE_METADATA_ADDRESS", ""
        ),
        "METADATA_HASH": os.environ.get("METADATA_HASH", ""),
        "ON_CHAIN_SERVICE_ID": os.environ.get("ON_CHAIN_SERVICE_ID", ""),
        "SAFE_CONTRACT_ADDRESS": os.environ.get("SAFE_CONTRACT_ADDRESS", ""),
    }

    for required_key, value in required.items():
        if not value:
            raise ValueError(f"Missing {required_key} in environment.")

    return required


def _load_contract(
    web3_client: Web3,
    contract_address: str,
    abi_file: str,
    abi_dir: Optional[Path] = None,
) -> Contract:
    """Load a contract from an ABI file bundled in mtd.abis or a custom directory."""
    if abi_dir is not None:
        abi_text = (abi_dir / f"{abi_file}.json").read_text(encoding="utf-8")
    else:
        abi_text = (
            importlib_resources.files("mtd.abis")
            .joinpath(f"{abi_file}.json")
            .read_text(encoding="utf-8")
        )
    contract_abi = json.loads(abi_text)["abi"]
    return web3_client.eth.contract(address=contract_address, abi=contract_abi)


def _fetch_metadata_hash(metadata_hash: str) -> bytes:
    """Convert metadata CID to bytes for contract call."""
    cid_bytes = multibase_decode(metadata_hash.encode("ascii"))
    if not cid_bytes:
        raise ValueError(f"Invalid or empty metadata hash CID: {metadata_hash!r}")
    multihash_bytes = multicodec_remove_prefix(cid_bytes)
    hex_multihash = multihash_bytes.hex()
    metadata_str = hex_multihash[6:]
    return bytes.fromhex(metadata_str)


def _send_safe_tx(
    web3_client: Web3,
    ethereum_client: EthereumClient,
    tx_data: str,
    to_address: str,
    safe_address: str,
    signer_pkey: str,
    gas: int,
    value: int = 0,
) -> Optional[TxReceipt]:
    """Send a Safe transaction."""
    safe = Safe(  # pylint: disable=abstract-class-instantiated
        safe_address, ethereum_client
    )
    safe_tx = safe.build_multisig_tx(
        to=to_address,
        value=value,
        data=bytes.fromhex(tx_data[2:]),
        operation=0,
        safe_tx_gas=gas,
        base_gas=0,
        gas_price=0,
        gas_token=ADDRESS_ZERO,
        refund_receiver=ADDRESS_ZERO,
    )
    safe_tx.sign(signer_pkey)
    try:
        tx_hash, _ = safe_tx.execute(signer_pkey)
        return web3_client.eth.wait_for_transaction_receipt(tx_hash)
    except Exception as e:  # pylint: disable=broad-except
        raise RuntimeError(f"Exception while sending a safe transaction: {e}") from e


def update_metadata_onchain(
    env_path: Path,
    private_key_path: Path,
    abi_dir: Optional[Path] = None,
) -> Tuple[bool, str]:
    """Update metadata hash on-chain and return (success, tx_hash)."""
    runtime = _load_env(env_path=env_path)

    signer_pkey = private_key_path.read_text(encoding="utf-8").strip()
    if not signer_pkey:
        raise ValueError("Private key file is empty.")

    web3_client = Web3(Web3.HTTPProvider(runtime["CHAIN_RPC"]))
    ethereum_client = EthereumClient(runtime["CHAIN_RPC"])

    contract = _load_contract(
        web3_client=web3_client,
        contract_address=runtime["COMPLEMENTARY_SERVICE_METADATA_ADDRESS"],
        abi_file="ComplementaryServiceMetadata",
        abi_dir=abi_dir,
    )

    metadata_bytes = _fetch_metadata_hash(runtime["METADATA_HASH"])
    safe_address = web3_client.to_checksum_address(runtime["SAFE_CONTRACT_ADDRESS"])

    safe = Safe(  # pylint: disable=abstract-class-instantiated
        safe_address, ethereum_client
    )
    safe_nonce = safe.retrieve_nonce()

    function = contract.functions.changeHash(
        int(runtime["ON_CHAIN_SERVICE_ID"]), metadata_bytes
    )
    transaction = function.build_transaction(
        {
            "chainId": int(runtime["CHAIN_ID"]),
            "gas": 100000,
            "gasPrice": web3_client.to_wei("3", "gwei"),
            "nonce": safe_nonce,
        }
    )

    tx_receipt = _send_safe_tx(
        web3_client=web3_client,
        ethereum_client=ethereum_client,
        tx_data=transaction["data"],
        to_address=runtime["COMPLEMENTARY_SERVICE_METADATA_ADDRESS"],
        safe_address=safe_address,
        signer_pkey=signer_pkey,
        gas=100000,
    )
    if tx_receipt is None:
        raise RuntimeError(
            "Safe transaction execution failed; no transaction receipt returned."
        )

    return (bool(tx_receipt.status), tx_receipt.transactionHash.hex())
