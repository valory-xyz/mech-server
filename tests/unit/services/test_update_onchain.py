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
"""Tests for update_onchain service."""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mtd.services.metadata.update_onchain import (
    _fetch_metadata_hash,
    _load_contract,
    _load_env,
    _send_safe_tx,
    update_metadata_onchain,
)


MOD = "mtd.services.metadata.update_onchain"

_VALID_ENV = {
    "DEFAULT_CHAIN_ID": "GNOSIS",
    "GNOSIS_LEDGER_RPC_0": "http://localhost:8545",
    "GNOSIS_LEDGER_CHAIN_ID": "100",
    "COMPLEMENTARY_SERVICE_METADATA_ADDRESS": "0xaddr",
    "METADATA_HASH": "f01701220" + "ab" * 32,
    "ON_CHAIN_SERVICE_ID": "42",
    "SAFE_CONTRACT_ADDRESS": "0xsafe",
}


# ---------------------------------------------------------------------------
# _load_env
# ---------------------------------------------------------------------------


def test_load_env_raises_when_no_default_chain_id(tmp_path: Path) -> None:
    """Raise ValueError when DEFAULT_CHAIN_ID is absent from environment."""
    env_path = tmp_path / ".env"
    env_path.write_text("", encoding="utf-8")
    with patch(f"{MOD}.dotenv.load_dotenv"), patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="DEFAULT_CHAIN_ID"):
            _load_env(env_path)


def test_load_env_raises_when_chain_rpc_missing(tmp_path: Path) -> None:
    """Raise ValueError when the chain RPC env var is missing."""
    env_path = tmp_path / ".env"
    env_path.write_text("", encoding="utf-8")
    env = {"DEFAULT_CHAIN_ID": "GNOSIS"}
    with patch(f"{MOD}.dotenv.load_dotenv"), patch.dict(os.environ, env, clear=True):
        with pytest.raises(ValueError, match="GNOSIS_LEDGER_RPC_0"):
            _load_env(env_path)


def test_load_env_raises_when_chain_id_missing(tmp_path: Path) -> None:
    """Raise ValueError when the chain ID env var is missing."""
    env_path = tmp_path / ".env"
    env_path.write_text("", encoding="utf-8")
    env = {"DEFAULT_CHAIN_ID": "GNOSIS", "GNOSIS_LEDGER_RPC_0": "http://rpc"}
    with patch(f"{MOD}.dotenv.load_dotenv"), patch.dict(os.environ, env, clear=True):
        with pytest.raises(ValueError, match="GNOSIS_LEDGER_CHAIN_ID"):
            _load_env(env_path)


def test_load_env_raises_when_required_value_empty(tmp_path: Path) -> None:
    """Raise ValueError when a required key has an empty value."""
    env_path = tmp_path / ".env"
    env_path.write_text("", encoding="utf-8")
    env = {
        "DEFAULT_CHAIN_ID": "GNOSIS",
        "GNOSIS_LEDGER_RPC_0": "http://rpc",
        "GNOSIS_LEDGER_CHAIN_ID": "100",
        # COMPLEMENTARY_SERVICE_METADATA_ADDRESS intentionally absent
    }
    with patch(f"{MOD}.dotenv.load_dotenv"), patch.dict(os.environ, env, clear=True):
        with pytest.raises(ValueError, match="COMPLEMENTARY_SERVICE_METADATA_ADDRESS"):
            _load_env(env_path)


def test_load_env_returns_dict_when_all_vars_present(tmp_path: Path) -> None:
    """Return the runtime env dict when all required variables are present."""
    env_path = tmp_path / ".env"
    env_path.write_text("", encoding="utf-8")
    with patch(f"{MOD}.dotenv.load_dotenv"), patch.dict(
        os.environ, _VALID_ENV, clear=True
    ):
        result = _load_env(env_path)

    assert result["CHAIN_RPC"] == "http://localhost:8545"
    assert result["CHAIN_ID"] == "100"
    assert result["ON_CHAIN_SERVICE_ID"] == "42"
    assert result["SAFE_CONTRACT_ADDRESS"] == "0xsafe"


# ---------------------------------------------------------------------------
# _fetch_metadata_hash
# ---------------------------------------------------------------------------


def test_fetch_metadata_hash_raises_for_empty_cid() -> None:
    """Raise ValueError when multibase decode yields empty bytes."""
    with patch(f"{MOD}.multibase.decode", return_value=b""):
        with pytest.raises(ValueError, match="Invalid or empty metadata hash CID"):
            _fetch_metadata_hash("f0invalid")


def test_fetch_metadata_hash_returns_bytes_for_valid_cid() -> None:
    """Return extracted hash bytes for a well-formed CID."""
    # multicodec.remove_prefix returns 35 null bytes:
    # hex is 70 chars; [6:] = 64 chars = 32 bytes
    with patch(f"{MOD}.multibase.decode", return_value=b"x" * 10), patch(
        f"{MOD}.multicodec.remove_prefix", return_value=bytes(35)
    ):
        result = _fetch_metadata_hash("f01701220")

    assert isinstance(result, bytes)
    assert len(result) == 32


# ---------------------------------------------------------------------------
# update_metadata_onchain
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# _load_contract
# ---------------------------------------------------------------------------


def test_load_contract_reads_abi_and_returns_contract(tmp_path: Path) -> None:
    """Read ABI JSON file and return a web3 contract instance."""
    abi_dir = tmp_path / "abis"
    abi_dir.mkdir()
    (abi_dir / "TestContract.json").write_text(
        json.dumps({"abi": [{"name": "changeHash"}]}), encoding="utf-8"
    )

    mock_web3 = MagicMock()
    mock_web3.eth.contract.return_value = "contract_instance"

    result = _load_contract(mock_web3, abi_dir, "0xaddr", "TestContract")

    assert result == "contract_instance"
    mock_web3.eth.contract.assert_called_once_with(
        address="0xaddr", abi=[{"name": "changeHash"}]
    )


# ---------------------------------------------------------------------------
# _send_safe_tx
# ---------------------------------------------------------------------------


@patch(f"{MOD}.Safe")
def test_send_safe_tx_returns_receipt(mock_safe_cls: MagicMock) -> None:
    """Return the transaction receipt on a successful Safe transaction."""
    mock_web3 = MagicMock()
    mock_ethereum_client = MagicMock()

    mock_safe = MagicMock()
    mock_safe_tx = MagicMock()
    mock_safe.build_multisig_tx.return_value = mock_safe_tx
    mock_safe_tx.execute.return_value = (b"txhash", None)
    mock_receipt = MagicMock()
    mock_web3.eth.wait_for_transaction_receipt.return_value = mock_receipt
    mock_safe_cls.return_value = mock_safe

    receipt = _send_safe_tx(
        web3_client=mock_web3,
        ethereum_client=mock_ethereum_client,
        tx_data="0x1234",
        to_address="0xto",
        safe_address="0xsafe",
        signer_pkey="0xkey",
        gas=100000,
    )

    assert receipt is mock_receipt
    mock_safe_tx.sign.assert_called_once_with("0xkey")


@patch(f"{MOD}.Safe")
def test_send_safe_tx_raises_runtime_error_on_execute_failure(
    mock_safe_cls: MagicMock,
) -> None:
    """Raise RuntimeError when safe_tx.execute raises an exception."""
    mock_web3 = MagicMock()
    mock_ethereum_client = MagicMock()

    mock_safe = MagicMock()
    mock_safe_tx = MagicMock()
    mock_safe.build_multisig_tx.return_value = mock_safe_tx
    mock_safe_tx.execute.side_effect = OSError("network down")
    mock_safe_cls.return_value = mock_safe

    with pytest.raises(
        RuntimeError, match="Exception while sending a safe transaction"
    ):
        _send_safe_tx(
            web3_client=mock_web3,
            ethereum_client=mock_ethereum_client,
            tx_data="0x1234",
            to_address="0xto",
            safe_address="0xsafe",
            signer_pkey="0xkey",
            gas=100000,
        )


# ---------------------------------------------------------------------------
# update_metadata_onchain — tx_receipt is None branch
# ---------------------------------------------------------------------------


@patch(f"{MOD}._send_safe_tx", return_value=None)
@patch(f"{MOD}._load_contract")
@patch(f"{MOD}.Safe")
@patch(f"{MOD}.EthereumClient")
@patch(f"{MOD}.Web3")
@patch(f"{MOD}._fetch_metadata_hash", return_value=b"hash")
@patch(
    f"{MOD}._load_env",
    return_value={
        "CHAIN_RPC": "http://localhost:8545",
        "CHAIN_ID": "1",
        "COMPLEMENTARY_SERVICE_METADATA_ADDRESS": "0xaddr",
        "METADATA_HASH": "f0170",
        "ON_CHAIN_SERVICE_ID": "1",
        "SAFE_CONTRACT_ADDRESS": "0xsafe",
    },
)
def test_update_metadata_raises_when_tx_receipt_is_none(
    _mock_load_env: MagicMock,
    _mock_fetch: MagicMock,
    mock_web3_cls: MagicMock,
    _mock_eth_client: MagicMock,
    mock_safe_cls: MagicMock,
    mock_load_contract: MagicMock,
    _mock_send: MagicMock,
    tmp_path: Path,
) -> None:
    """Raise RuntimeError when _send_safe_tx returns None."""
    env_path = tmp_path / ".env"
    env_path.touch()
    key_path = tmp_path / "key.txt"
    key_path.write_text("0xprivatekey", encoding="utf-8")

    mock_web3 = MagicMock()
    mock_web3.to_checksum_address.return_value = "0xsafe"
    mock_web3.to_wei.return_value = 3
    mock_web3_cls.return_value = mock_web3

    mock_safe = MagicMock()
    mock_safe.retrieve_nonce.return_value = 0
    mock_safe_cls.return_value = mock_safe

    mock_contract = MagicMock()
    mock_fn = MagicMock()
    mock_fn.build_transaction.return_value = {"data": "0x1234"}
    mock_contract.functions.changeHash.return_value = mock_fn
    mock_load_contract.return_value = mock_contract

    with pytest.raises(RuntimeError, match="no transaction receipt"):
        update_metadata_onchain(env_path=env_path, private_key_path=key_path)


def test_update_metadata_onchain_raises_when_private_key_empty(
    tmp_path: Path,
) -> None:
    """Raise ValueError when the private key file contains only whitespace."""
    env_path = tmp_path / ".env"
    env_path.touch()
    key_path = tmp_path / "key.txt"
    key_path.write_text("   ", encoding="utf-8")

    with patch(f"{MOD}._load_env", return_value=_VALID_ENV):
        with pytest.raises(ValueError, match="Private key file is empty"):
            update_metadata_onchain(env_path=env_path, private_key_path=key_path)
