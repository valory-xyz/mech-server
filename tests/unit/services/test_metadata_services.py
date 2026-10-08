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
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest
from mtd.services.metadata.generate import (
    Benchmark,
    Operator,
    _import_module_from_path,
    generate_metadata,
)
from mtd.services.metadata.publish import publish_metadata_to_ipfs
from mtd.services.metadata.update_onchain import update_metadata_onchain

MECH_NAME = "Test Mech"
ECHO_TOOL = "echo"
BENCHMARK_URL = "https://analytics.example/v1/metrics/mech/100/0xabc"
SAMPLE_OPERATOR = Operator(
    name="Valory", domain="valory.xyz", contact="mechs@valory.xyz"
)
SAMPLE_BENCHMARK = Benchmark(
    metric="accuracy", value=0.83, window="30d", url=BENCHMARK_URL
)
# QmYwAP... is a CIDv0, which is always dag-pb; its sha2-256 digest follows.
DAG_PB_CID_V0 = "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
DAG_PB_DIGEST_HEX = "9d6c2be50f706953479ab9df2ce3edca90b68053c00b3004b7f0accbe1e8eedf"
RAW_CID_V1 = "bafkreie5nqv6kd3qnfjupgvz34woh3oksc3iau6abmyajn7qvtf6d2ho34"


def _make_echo_packages(tmp_path: Path) -> Path:
    """Create a packages tree with a single ``echo`` tool and return its root."""
    packages_dir = tmp_path / "packages"
    tool_dir = packages_dir / "alice" / "customs" / ECHO_TOOL
    tool_dir.mkdir(parents=True)
    (tool_dir / "component.yaml").write_text(
        "author: alice\nname: echo\ndescription: Echo tool\n", encoding="utf-8"
    )
    (tool_dir / "echo.py").write_text("ALLOWED_TOOLS = ['echo']\n", encoding="utf-8")
    return packages_dir


def _generate(tmp_path: Path, **overrides: Any) -> Dict[str, Any]:
    """Generate a manifest for the echo packages tree and return it parsed."""
    kwargs: Dict[str, Any] = {
        "metadata_path": tmp_path / "metadata.json",
        "name": MECH_NAME,
    }
    kwargs.update(overrides)
    if "packages_dir" not in kwargs:
        kwargs["packages_dir"] = _make_echo_packages(tmp_path)
    output = generate_metadata(**kwargs)
    return json.loads(output.read_text(encoding="utf-8"))


def _write_minimal_metadata(tmp_path: Path) -> Path:
    """Write the smallest manifest that passes publish validation."""
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
    return metadata_path


# ---------------------------------------------------------------------------
# generate_metadata
# ---------------------------------------------------------------------------


def test_generate_metadata_creates_file(tmp_path: Path) -> None:
    """Generate metadata should scan tools and write metadata file."""
    packages_dir = _make_echo_packages(tmp_path)
    metadata_path = tmp_path / "metadata.json"

    output = generate_metadata(
        packages_dir=packages_dir, metadata_path=metadata_path, name=MECH_NAME
    )

    assert output == metadata_path
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["tools"] == [ECHO_TOOL]
    assert metadata["name"] == MECH_NAME


def test_generate_metadata_includes_url_when_provided(tmp_path: Path) -> None:
    """Generate metadata should include offchain URL when provided."""
    metadata = _generate(tmp_path, offchain_url="https://mech.example.com/")
    assert metadata["url"] == "https://mech.example.com/"


def test_generate_metadata_default_url_empty(tmp_path: Path) -> None:
    """Generate metadata should have empty URL when none provided."""
    metadata = _generate(tmp_path)
    assert metadata["url"] == ""


def test_generate_metadata_omits_operator_and_benchmark_by_default(
    tmp_path: Path,
) -> None:
    """Neither new field appears unless asked for; existing fields are unchanged."""
    metadata = _generate(tmp_path)

    assert "operator" not in metadata
    assert "benchmark" not in metadata["toolMetadata"][ECHO_TOOL]
    assert set(metadata) == {
        "name",
        "description",
        "inputFormat",
        "outputFormat",
        "image",
        "url",
        "tools",
        "toolMetadata",
    }
    assert set(metadata["toolMetadata"][ECHO_TOOL]) == {
        "name",
        "description",
        "input",
        "output",
    }


def test_generate_metadata_writes_operator_block(tmp_path: Path) -> None:
    """The operator block is emitted under the spec's exact field names."""
    metadata = _generate(tmp_path, operator=SAMPLE_OPERATOR)

    assert metadata["operator"] == {
        "name": "Valory",
        "domain": "valory.xyz",
        "contact": "mechs@valory.xyz",
    }


def test_generate_metadata_operator_without_contact_omits_key(tmp_path: Path) -> None:
    """``contact`` is optional and is left out rather than written as null."""
    metadata = _generate(
        tmp_path, operator=Operator(name="Valory", domain="valory.xyz")
    )

    assert metadata["operator"] == {"name": "Valory", "domain": "valory.xyz"}


def test_generate_metadata_writes_per_tool_benchmark(tmp_path: Path) -> None:
    """The benchmark object lands inside toolMetadata.<tool> with the spec's names."""
    metadata = _generate(tmp_path, benchmarks={ECHO_TOOL: SAMPLE_BENCHMARK})

    assert metadata["toolMetadata"][ECHO_TOOL]["benchmark"] == {
        "metric": "accuracy",
        "value": 0.83,
        "window": "30d",
        "url": BENCHMARK_URL,
    }
    assert metadata["toolMetadata"][ECHO_TOOL]["name"] == ECHO_TOOL
    assert metadata["tools"] == [ECHO_TOOL]


def test_generate_metadata_with_all_new_fields_keeps_existing_ones(
    tmp_path: Path,
) -> None:
    """Operator, benchmark and url can all be set at once without disturbing each other."""
    metadata = _generate(
        tmp_path,
        offchain_url="https://mech.example.com/",
        operator=SAMPLE_OPERATOR,
        benchmarks={ECHO_TOOL: SAMPLE_BENCHMARK},
    )

    assert metadata["url"] == "https://mech.example.com/"
    assert metadata["operator"]["domain"] == "valory.xyz"
    assert metadata["toolMetadata"][ECHO_TOOL]["benchmark"]["value"] == 0.83


def test_generate_metadata_rejects_benchmark_for_unknown_tool(tmp_path: Path) -> None:
    """A benchmark keyed by a tool the manifest does not list is an error."""
    with pytest.raises(ValueError, match="unknown tool 'missing'"):
        _generate(tmp_path, benchmarks={"missing": SAMPLE_BENCHMARK})


@pytest.mark.parametrize("name", ["", "   "])
def test_generate_metadata_rejects_blank_name(tmp_path: Path, name: str) -> None:
    """There is no default mech name; a blank one is refused before scanning."""
    with pytest.raises(ValueError, match="Mech name must not be empty"):
        generate_metadata(
            packages_dir=tmp_path / "nonexistent",
            metadata_path=tmp_path / "metadata.json",
            name=name,
        )


def test_generate_metadata_raises_when_packages_dir_missing(tmp_path: Path) -> None:
    """Raise FileNotFoundError when packages_dir does not exist."""
    with pytest.raises(FileNotFoundError, match="Packages directory not found"):
        generate_metadata(
            packages_dir=tmp_path / "nonexistent",
            metadata_path=tmp_path / "metadata.json",
            name=MECH_NAME,
        )


def test_generate_metadata_skips_non_py_init_and_non_file(tmp_path: Path) -> None:
    """Skip __init__.py, non-py files, and subdirectories inside a tool folder."""
    packages_dir = _make_echo_packages(tmp_path)
    tool_dir = packages_dir / "alice" / "customs" / ECHO_TOOL
    (tool_dir / "__init__.py").write_text("", encoding="utf-8")
    (tool_dir / "notes.txt").write_text("some notes", encoding="utf-8")
    (tool_dir / "subdir").mkdir()

    metadata = _generate(tmp_path, packages_dir=packages_dir)

    assert metadata["tools"] == [ECHO_TOOL]


# ---------------------------------------------------------------------------
# Operator
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "domain", ["valory.xyz", "mechs.valory.xyz", "a1-b2.example", "x.y"]
)
def test_operator_accepts_bare_hostnames(domain: str) -> None:
    """Lowercase dotted hostnames, with or without subdomains, are accepted as given."""
    assert Operator(name="Valory", domain=domain).domain == domain


@pytest.mark.parametrize(
    "domain, reason",
    [
        ("", "it is empty"),
        ("https://valory.xyz", "must not include a scheme"),
        ("valory.xyz/", "must not include a path"),
        ("valory.xyz/.well-known", "must not include a path"),
        ("valory.xyz?x=1", "must not include a path"),
        ("valory.xyz.", "must not end with a dot"),
        ("VALORY.xyz", "must be lowercase"),
        ("www.Valory.XYZ", "must be lowercase"),
        ("localhost", "must contain at least one dot"),
        ("valory.xyz:443", "must not include a port"),
        ("user@valory.xyz", "must not include a port or credentials"),
        ("valory .xyz", "not a valid hostname label"),
        ("valory.xyz\n", "not a valid hostname label"),
        ("valory\n.xyz", "not a valid hostname label"),
        ("\tvalory.xyz", "not a valid hostname label"),
        ("-valory.xyz", "not a valid hostname label"),
        ("valory-.xyz", "not a valid hostname label"),
        ("valory..xyz", "not a valid hostname label"),
        ("val_ory.xyz", "not a valid hostname label"),
        ("a" * 64 + ".xyz", "not a valid hostname label"),
        (".".join(["a" * 60] * 5), "exceeds 253 characters"),
    ],
)
def test_operator_rejects_non_bare_hostnames(domain: str, reason: str) -> None:
    """Schemes, paths, ports, capitals, dotless hosts and bad labels are refused with a reason."""
    with pytest.raises(ValueError, match=reason):
        Operator(name="Valory", domain=domain)


@pytest.mark.parametrize("name", ["", "  "])
def test_operator_rejects_blank_name(name: str) -> None:
    """The operator name is free text but may not be blank."""
    with pytest.raises(ValueError, match="Operator name must not be empty"):
        Operator(name=name, domain="valory.xyz")


def test_operator_rejects_blank_contact() -> None:
    """A contact that is given must carry something; omit it instead of blanking it."""
    with pytest.raises(ValueError, match="contact must not be blank"):
        Operator(name="Valory", domain="valory.xyz", contact=" ")


def test_operator_from_dict_round_trips() -> None:
    """``from_dict`` reads what ``to_dict`` wrote, with and without contact."""
    assert Operator.from_dict(SAMPLE_OPERATOR.to_dict()) == SAMPLE_OPERATOR
    bare = Operator(name="Valory", domain="valory.xyz")
    assert Operator.from_dict(bare.to_dict()) == bare


@pytest.mark.parametrize(
    "data, reason",
    [
        ("Valory", "must be an object"),
        (["Valory"], "must be an object"),
        ({"domain": "valory.xyz"}, "Missing operator field 'name'"),
        ({"name": "Valory"}, "Missing operator field 'domain'"),
        ({"name": "Valory", "domian": "valory.xyz"}, "Unknown operator field"),
        ({"name": 1, "domain": "valory.xyz"}, "field 'name' must be str"),
        (
            {"name": "Valory", "domain": "valory.xyz", "contact": 5},
            "'contact' must be str",
        ),
        ({"name": "Valory", "domain": "https://valory.xyz"}, "not a bare hostname"),
    ],
)
def test_operator_from_dict_rejects_malformed_input(data: Any, reason: str) -> None:
    """Hand-written operator objects fail for missing, misspelt, mistyped or invalid fields."""
    with pytest.raises(ValueError, match=reason):
        Operator.from_dict(data)


# ---------------------------------------------------------------------------
# Benchmark
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", [0, 1, 0.0, 1.0, 0.83])
def test_benchmark_accepts_values_in_unit_interval(value: float) -> None:
    """Both endpoints and interior values are allowed, as int or float."""
    assert (
        Benchmark(metric="accuracy", value=value, window="30d", url=BENCHMARK_URL).value
        == value
    )


@pytest.mark.parametrize("value", [1.0001, 1.5, -0.1, -1, 100])
def test_benchmark_rejects_values_outside_unit_interval(value: float) -> None:
    """Anything above 1 or below 0 is refused, naming the offending value."""
    with pytest.raises(ValueError, match=f"between 0 and 1, got {value}"):
        Benchmark(metric="accuracy", value=value, window="30d", url=BENCHMARK_URL)


@pytest.mark.parametrize("value", [True, False, "0.5"])
def test_benchmark_rejects_non_numeric_values(value: Any) -> None:
    """Booleans and strings are not numbers, even though bool subclasses int."""
    with pytest.raises(ValueError, match="must be a number"):
        Benchmark(metric="accuracy", value=value, window="30d", url=BENCHMARK_URL)


@pytest.mark.parametrize("window", ["7d", "30d", "90d", "all"])
def test_benchmark_accepts_spec_windows(window: str) -> None:
    """Exactly the four spec windows are accepted."""
    assert (
        Benchmark(metric="accuracy", value=0.5, window=window, url=BENCHMARK_URL).window
        == window
    )


@pytest.mark.parametrize("window", ["", "1d", "30D", "30", "60d", "ALL", "30d "])
def test_benchmark_rejects_other_windows(window: str) -> None:
    """Windows are matched exactly: no other sizes, no case or whitespace variants."""
    with pytest.raises(ValueError, match="window must be one of 7d, 30d, 90d, all"):
        Benchmark(metric="accuracy", value=0.5, window=window, url=BENCHMARK_URL)


@pytest.mark.parametrize("metric", ["", " "])
def test_benchmark_rejects_blank_metric(metric: str) -> None:
    """The metric name is free text but may not be blank."""
    with pytest.raises(ValueError, match="metric must not be empty"):
        Benchmark(metric=metric, value=0.5, window="30d", url=BENCHMARK_URL)


@pytest.mark.parametrize(
    "url",
    [
        BENCHMARK_URL,
        "https://analytics.example",
        "https://analytics.example:8443/v1/metrics/mech/100/0xabc?window=30d",
    ],
)
def test_benchmark_accepts_https_urls_with_a_host(url: str) -> None:
    """Any https URL with a host is accepted, with or without port, path or query."""
    assert Benchmark(metric="accuracy", window="30d", url=url).url == url


@pytest.mark.parametrize(
    "url",
    [
        "",
        "analytics.example/v1",
        "ftp://analytics.example",
        "http://analytics.example/v1/metrics/mech/100/0xabc",
        "https://",
        "https:///v1/metrics",
        "https://x y",
        "https://analytics.example/v1 ",
        "https://analytics.example/v1\n",
    ],
)
def test_benchmark_rejects_urls_that_are_not_https_with_a_host(url: str) -> None:
    """Only https reaches buyers; a scheme alone, another scheme, or whitespace is refused."""
    with pytest.raises(ValueError, match="must be an https URL with a host"):
        Benchmark(metric="accuracy", value=0.5, window="30d", url=url)


def test_benchmark_from_dict_round_trips() -> None:
    """``from_dict`` reads what ``to_dict`` wrote, with and without a value."""
    assert Benchmark.from_dict(SAMPLE_BENCHMARK.to_dict()) == SAMPLE_BENCHMARK
    unmeasured = Benchmark(metric="accuracy", window="7d", url=BENCHMARK_URL)
    assert Benchmark.from_dict(unmeasured.to_dict()) == unmeasured


def test_benchmark_without_value_omits_the_key() -> None:
    """No figure yet is written as an absent ``value``, never as 0 or null."""
    unmeasured = Benchmark(metric="accuracy", window="7d", url=BENCHMARK_URL)

    assert unmeasured.to_dict() == {
        "metric": "accuracy",
        "window": "7d",
        "url": BENCHMARK_URL,
    }


def test_benchmark_from_dict_accepts_missing_value() -> None:
    """A benchmark object with metric, window and url but no value is valid."""
    parsed = Benchmark.from_dict(
        {"metric": "accuracy", "window": "7d", "url": BENCHMARK_URL}
    )

    assert parsed.value is None
    assert parsed.window == "7d"


@pytest.mark.parametrize(
    "data, reason",
    [
        (0.83, "must be an object"),
        (
            {"metric": "accuracy", "value": 0.83, "window": "30d"},
            "Missing benchmark field 'url'",
        ),
        (
            {"value": 0.83, "window": "30d", "url": BENCHMARK_URL},
            "Missing benchmark field 'metric'",
        ),
        (
            {
                "metric": "accuracy",
                "value": None,
                "window": "30d",
                "url": BENCHMARK_URL,
            },
            "'value' must be int or float, got NoneType",
        ),
        (
            {
                "metric": "accuracy",
                "value": 0.83,
                "window": "30d",
                "url": BENCHMARK_URL,
                "n": 1,
            },
            "Unknown benchmark field",
        ),
        (
            {
                "metric": "accuracy",
                "value": "0.83",
                "window": "30d",
                "url": BENCHMARK_URL,
            },
            "'value' must be int or float, got str",
        ),
        (
            {
                "metric": "accuracy",
                "value": True,
                "window": "30d",
                "url": BENCHMARK_URL,
            },
            "'value' must be int or float, got bool",
        ),
        (
            {"metric": "accuracy", "value": 1.2, "window": "30d", "url": BENCHMARK_URL},
            "between 0 and 1",
        ),
        (
            {"metric": "accuracy", "value": 0.8, "window": "2d", "url": BENCHMARK_URL},
            "window must be one of",
        ),
    ],
)
def test_benchmark_from_dict_rejects_malformed_input(data: Any, reason: str) -> None:
    """Hand-written benchmark objects fail for missing, extra, mistyped or out-of-range fields."""
    with pytest.raises(ValueError, match=reason):
        Benchmark.from_dict(data)


# ---------------------------------------------------------------------------
# Module import errors
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# publish_metadata_to_ipfs
# ---------------------------------------------------------------------------


def _publish_with_ipfs_hash(metadata_path: Path, ipfs_hash: str) -> str:
    """Publish with the IPFS client stubbed to return ``ipfs_hash``."""
    with patch("mtd.services.metadata.publish.IPFSTool") as mock_ipfs_tool:
        mock_ipfs_tool.return_value.client.add.return_value = {"Hash": ipfs_hash}
        return publish_metadata_to_ipfs(metadata_path=metadata_path)


def test_publish_metadata_returns_onchain_hash_for_dag_pb_id(tmp_path: Path) -> None:
    """A dag-pb id becomes ``f01701220`` plus the bare sha2-256 digest; the real CID helpers run."""
    metadata_hash = _publish_with_ipfs_hash(
        _write_minimal_metadata(tmp_path), DAG_PB_CID_V0
    )

    assert metadata_hash == "f01701220" + DAG_PB_DIGEST_HEX


def test_publish_metadata_rejects_raw_codec_id(tmp_path: Path) -> None:
    """A raw-codec id is refused: the contract rebuilds ids as dag-pb, so it would be unreadable."""
    with pytest.raises(ValueError, match="'raw' content id .* Only 'dag-pb'"):
        _publish_with_ipfs_hash(_write_minimal_metadata(tmp_path), RAW_CID_V1)


# ---------------------------------------------------------------------------
# update_metadata_onchain
# ---------------------------------------------------------------------------


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
