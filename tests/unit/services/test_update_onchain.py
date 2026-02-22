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

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from mtd.services.metadata.update_onchain import (
    _fetch_metadata_hash,
    _load_env,
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


def test_fetch_metadata_hash_returns_empty_bytes_for_empty_cid() -> None:
    """Return b'' when multibase decode yields empty bytes."""
    with patch(f"{MOD}.multibase.decode", return_value=b""):
        result = _fetch_metadata_hash("f0invalid")
    assert result == b""


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
