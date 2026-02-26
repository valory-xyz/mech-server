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
"""Tests for metadata service modules."""

import importlib.util
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mtd.services.metadata.generate import _import_module_from_path, generate_metadata
from mtd.services.metadata.publish import publish_metadata_to_ipfs
from mtd.services.metadata.update_onchain import update_metadata_onchain


def test_generate_metadata_creates_file(tmp_path: Path) -> None:
    """Generate metadata should scan tools and write metadata file."""
    packages_dir = tmp_path / "packages"
    tool_dir = packages_dir / "alice" / "customs" / "echo"
    tool_dir.mkdir(parents=True)

    (tool_dir / "component.yaml").write_text(
        "author: alice\nname: echo\ndescription: Echo tool\n",
        encoding="utf-8",
    )
    (tool_dir / "echo.py").write_text(
        "ALLOWED_TOOLS = ['echo']\n",
        encoding="utf-8",
    )

    metadata_path = tmp_path / "metadata.json"
    output = generate_metadata(packages_dir=packages_dir, metadata_path=metadata_path)

    assert output == metadata_path
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert "echo" in metadata["tools"]


def test_generate_metadata_includes_url_when_provided(tmp_path: Path) -> None:
    """Generate metadata should include offchain URL when provided."""
    packages_dir = tmp_path / "packages"
    tool_dir = packages_dir / "alice" / "customs" / "echo"
    tool_dir.mkdir(parents=True)

    (tool_dir / "component.yaml").write_text(
        "author: alice\nname: echo\ndescription: Echo tool\n",
        encoding="utf-8",
    )
    (tool_dir / "echo.py").write_text(
        "ALLOWED_TOOLS = ['echo']\n",
        encoding="utf-8",
    )

    metadata_path = tmp_path / "metadata.json"
    generate_metadata(
        packages_dir=packages_dir,
        metadata_path=metadata_path,
        offchain_url="https://mech.example.com/",
    )

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["url"] == "https://mech.example.com/"


def test_generate_metadata_default_url_empty(tmp_path: Path) -> None:
    """Generate metadata should have empty URL when none provided."""
    packages_dir = tmp_path / "packages"
    tool_dir = packages_dir / "alice" / "customs" / "echo"
    tool_dir.mkdir(parents=True)

    (tool_dir / "component.yaml").write_text(
        "author: alice\nname: echo\ndescription: Echo tool\n",
        encoding="utf-8",
    )
    (tool_dir / "echo.py").write_text(
        "ALLOWED_TOOLS = ['echo']\n",
        encoding="utf-8",
    )

    metadata_path = tmp_path / "metadata.json"
    generate_metadata(packages_dir=packages_dir, metadata_path=metadata_path)

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["url"] == ""


def test_generate_metadata_raises_when_packages_dir_missing(tmp_path: Path) -> None:
    """Raise FileNotFoundError when packages_dir does not exist."""
    with pytest.raises(FileNotFoundError, match="Packages directory not found"):
        generate_metadata(
            packages_dir=tmp_path / "nonexistent",
            metadata_path=tmp_path / "metadata.json",
        )


def test_generate_metadata_skips_non_py_init_and_non_file(tmp_path: Path) -> None:
    """Skip __init__.py, non-py files, and subdirectories inside a tool folder."""
    packages_dir = tmp_path / "packages"
    tool_dir = packages_dir / "alice" / "customs" / "echo"
    tool_dir.mkdir(parents=True)

    (tool_dir / "component.yaml").write_text(
        "author: alice\nname: echo\ndescription: Echo tool\n", encoding="utf-8"
    )
    (tool_dir / "echo.py").write_text("ALLOWED_TOOLS = ['echo']\n", encoding="utf-8")
    # These should all be skipped without error:
    (tool_dir / "__init__.py").write_text("", encoding="utf-8")
    (tool_dir / "notes.txt").write_text("some notes", encoding="utf-8")
    (tool_dir / "subdir").mkdir()

    metadata_path = tmp_path / "metadata.json"
    generate_metadata(packages_dir=packages_dir, metadata_path=metadata_path)

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert "echo" in metadata["tools"]


def test_import_module_from_path_raises_when_spec_is_none(tmp_path: Path) -> None:
    """Raise RuntimeError when importlib cannot build a spec for the file."""
    dummy = tmp_path / "dummy.py"
    dummy.write_text("x = 1", encoding="utf-8")

    with patch.object(importlib.util, "spec_from_file_location", return_value=None):
        with pytest.raises(RuntimeError, match="Cannot load module"):
            _import_module_from_path("dummy", dummy)


def test_import_module_from_path_raises_on_syntax_error(tmp_path: Path) -> None:
    """Raise RuntimeError wrapping SyntaxError when the module has invalid syntax."""
    bad = tmp_path / "bad.py"
    bad.write_text("def broken(: pass", encoding="utf-8")

    with pytest.raises(RuntimeError, match="Syntax error in module"):
        _import_module_from_path("bad", bad)


def test_import_module_from_path_raises_on_import_error(tmp_path: Path) -> None:
    """Raise RuntimeError wrapping ImportError when the module has a bad import."""
    bad = tmp_path / "bad_import.py"
    bad.write_text("import nonexistent_package_xyz\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="Failed to load module"):
        _import_module_from_path("bad_import", bad)


@patch(
    "mtd.services.metadata.publish.multicodec.remove_prefix",
    return_value=bytes.fromhex("1220" + "ab" * 32),
)
@patch("mtd.services.metadata.publish.multibase.decode", return_value=b"dummy")
@patch("mtd.services.metadata.publish.to_v1", return_value="cidv1")
@patch("mtd.services.metadata.publish.IPFSTool")
def test_publish_metadata_returns_hash(
    mock_ipfs_tool: MagicMock,
    _mock_to_v1: MagicMock,
    _mock_decode: MagicMock,
    _mock_remove_prefix: MagicMock,
    tmp_path: Path,
) -> None:
    """Publish metadata should return on-chain hash string."""
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "name": "name",
                "description": "desc",
                "inputFormat": "ipfs-v0.1",
                "outputFormat": "ipfs-v0.1",
                "image": "tbd",
                "tools": [],
                "toolMetadata": {},
            }
        ),
        encoding="utf-8",
    )

    mock_ipfs_tool.return_value.client.add.return_value = {"Hash": "cid"}

    metadata_hash = publish_metadata_to_ipfs(metadata_path=metadata_path)

    assert metadata_hash.startswith("f01701220")


@patch("mtd.services.metadata.update_onchain._send_safe_tx")
@patch("mtd.services.metadata.update_onchain._load_contract")
@patch("mtd.services.metadata.update_onchain.Safe")
@patch("mtd.services.metadata.update_onchain.EthereumClient")
@patch("mtd.services.metadata.update_onchain.Web3")
@patch(
    "mtd.services.metadata.update_onchain._fetch_metadata_hash", return_value=b"hash"
)
@patch(
    "mtd.services.metadata.update_onchain._load_env",
    return_value={
        "CHAIN_RPC": "http://localhost:8545",
        "CHAIN_ID": "1",
        "COMPLEMENTARY_SERVICE_METADATA_ADDRESS": "0x0000000000000000000000000000000000000001",
        "METADATA_HASH": "f0170",
        "ON_CHAIN_SERVICE_ID": "1",
        "SAFE_CONTRACT_ADDRESS": "0x0000000000000000000000000000000000000002",
    },
)
def test_update_metadata_onchain_returns_tx(
    _mock_load_env: MagicMock,
    _mock_fetch_hash: MagicMock,
    mock_web3_cls: MagicMock,
    _mock_eth_client_cls: MagicMock,
    mock_safe_cls: MagicMock,
    mock_load_contract: MagicMock,
    mock_send_safe_tx: MagicMock,
    tmp_path: Path,
) -> None:
    """Onchain update should return success and tx hash."""
    env_path = tmp_path / ".env"
    env_path.write_text("", encoding="utf-8")
    key_path = tmp_path / "ethereum_private_key.txt"
    key_path.write_text("0xabc", encoding="utf-8")

    mock_web3 = MagicMock()
    mock_web3.to_checksum_address.return_value = (
        "0x0000000000000000000000000000000000000002"
    )
    mock_web3.to_wei.return_value = 1
    mock_web3_cls.return_value = mock_web3

    mock_safe = MagicMock()
    mock_safe.retrieve_nonce.return_value = 7
    mock_safe_cls.return_value = mock_safe

    mock_contract = MagicMock()
    mock_fn = MagicMock()
    mock_fn.build_transaction.return_value = {"data": "0x1234"}
    mock_contract.functions.changeHash.return_value = mock_fn
    mock_load_contract.return_value = mock_contract

    tx_receipt = MagicMock()
    tx_receipt.status = 1
    tx_receipt.transactionHash.hex.return_value = "0xtx"
    mock_send_safe_tx.return_value = tx_receipt

    success, tx_hash = update_metadata_onchain(
        env_path=env_path, private_key_path=key_path
    )

    assert success is True
    assert tx_hash == "0xtx"
