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
"""Tests for _validate_metadata_file edge cases."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from mtd.services.metadata.publish import (
    _validate_metadata_file,
    publish_metadata_to_ipfs,
)

PUB_MOD = "mtd.services.metadata.publish"


VALID_PROPERTIES = {
    "requestId": {"type": "str", "description": "request id"},
    "result": {"type": "str", "description": "result"},
    "prompt": {"type": "str", "description": "prompt"},
}

VALID_OUTPUT_SCHEMA = {
    "properties": VALID_PROPERTIES,
    "required": ["requestId", "result", "prompt"],
    "type": "object",
}

VALID_TOOL = {
    "name": "echo",
    "description": "Echo tool",
    "input": {"type": "str", "description": "Input prompt"},
    "output": {
        "type": "str",
        "description": "Output result",
        "schema": VALID_OUTPUT_SCHEMA,
    },
}

VALID_METADATA = {
    "name": "Olas Mech",
    "description": "A mech service",
    "inputFormat": "str",
    "outputFormat": "str",
    "image": "https://example.com/img.png",
    "tools": ["echo"],
    "toolMetadata": {"echo": VALID_TOOL},
}


def _write(tmp_path: Path, data: dict) -> Path:
    """Write dict as JSON and return path."""
    p = tmp_path / "metadata.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def test_validate_valid_metadata(tmp_path: Path) -> None:
    """Valid metadata should return (True, '')."""
    ok, msg = _validate_metadata_file(_write(tmp_path, VALID_METADATA))
    assert ok is True
    assert msg == ""


def test_validate_valid_metadata_with_url(tmp_path: Path) -> None:
    """Valid metadata with optional url field should return (True, '')."""
    data = {**VALID_METADATA, "url": "https://example.com"}
    ok, msg = _validate_metadata_file(_write(tmp_path, data))
    assert ok is True
    assert msg == ""


def test_validate_metadata_with_wrong_url_type(tmp_path: Path) -> None:
    """Return (False, error) when url field has wrong type."""
    data = {**VALID_METADATA, "url": 123}
    ok, msg = _validate_metadata_file(_write(tmp_path, data))
    assert ok is False
    assert "url" in msg


def test_validate_valid_metadata_schema_without_required(tmp_path: Path) -> None:
    """Valid metadata with an output schema that omits 'required' should return (True, '')."""
    schema_no_required = {
        k: v for k, v in VALID_OUTPUT_SCHEMA.items() if k != "required"
    }
    output_no_required = {**VALID_TOOL["output"], "schema": schema_no_required}  # type: ignore[dict-item]
    tool_no_required = {**VALID_TOOL, "output": output_no_required}
    data = {**VALID_METADATA, "toolMetadata": {"echo": tool_no_required}}
    ok, msg = _validate_metadata_file(_write(tmp_path, data))
    assert ok is True
    assert msg == ""


def test_validate_file_not_found(tmp_path: Path) -> None:
    """Non-existent file returns (False, error)."""
    ok, msg = _validate_metadata_file(tmp_path / "missing.json")
    assert ok is False
    assert "not found" in msg


def test_validate_invalid_json(tmp_path: Path) -> None:
    """File with invalid JSON returns (False, error)."""
    p = tmp_path / "metadata.json"
    p.write_text("{not valid json", encoding="utf-8")
    ok, msg = _validate_metadata_file(p)
    assert ok is False
    assert "invalid JSON" in msg


@pytest.mark.parametrize("missing_key", list(VALID_METADATA.keys()))
def test_validate_missing_top_level_key(tmp_path: Path, missing_key: str) -> None:
    """Missing any top-level key returns (False, error)."""
    data = {k: v for k, v in VALID_METADATA.items() if k != missing_key}
    ok, msg = _validate_metadata_file(_write(tmp_path, data))
    assert ok is False
    assert missing_key in msg


def test_validate_wrong_top_level_type(tmp_path: Path) -> None:
    """Wrong type for a top-level key returns (False, error)."""
    data = {**VALID_METADATA, "name": 42}
    ok, msg = _validate_metadata_file(_write(tmp_path, data))
    assert ok is False
    assert "str" in msg


def test_validate_tools_metadata_count_mismatch(tmp_path: Path) -> None:
    """Return (False, error) when tools and toolMetadata lengths differ."""
    data = {**VALID_METADATA, "tools": ["echo", "other"]}
    ok, msg = _validate_metadata_file(_write(tmp_path, data))
    assert ok is False
    assert "Number of tools" in msg


def test_validate_tool_missing_from_metadata(tmp_path: Path) -> None:
    """Tool listed in tools but absent from toolMetadata returns (False, error)."""
    data = {**VALID_METADATA, "tools": ["unknown"], "toolMetadata": {"unknown": {}}}
    ok, msg = _validate_metadata_file(_write(tmp_path, data))
    assert ok is False
    assert "Missing key in toolsMetadata" in msg


def test_validate_missing_tool_schema_key(tmp_path: Path) -> None:
    """Return (False, error) for toolMetadata entry missing a required key."""
    broken_tool = {k: v for k, v in VALID_TOOL.items() if k != "name"}
    data = {**VALID_METADATA, "toolMetadata": {"echo": broken_tool}}
    ok, msg = _validate_metadata_file(_write(tmp_path, data))
    assert ok is False
    assert "'name'" in msg


def test_validate_wrong_tool_schema_type(tmp_path: Path) -> None:
    """Wrong type inside toolMetadata returns (False, error)."""
    broken_tool = {**VALID_TOOL, "name": 123}
    data = {**VALID_METADATA, "toolMetadata": {"echo": broken_tool}}
    ok, msg = _validate_metadata_file(_write(tmp_path, data))
    assert ok is False
    assert "str" in msg


def test_validate_missing_input_key(tmp_path: Path) -> None:
    """Tool input missing a required key returns (False, error)."""
    broken_input = {"type": "str"}  # missing 'description'
    broken_tool = {**VALID_TOOL, "input": broken_input}
    data = {**VALID_METADATA, "toolMetadata": {"echo": broken_tool}}
    ok, msg = _validate_metadata_file(_write(tmp_path, data))
    assert ok is False
    assert "input" in msg


def test_validate_wrong_input_type(tmp_path: Path) -> None:
    """Wrong type in tool input returns (False, error)."""
    broken_input = {"type": 42, "description": "x"}
    broken_tool = {**VALID_TOOL, "input": broken_input}
    data = {**VALID_METADATA, "toolMetadata": {"echo": broken_tool}}
    ok, msg = _validate_metadata_file(_write(tmp_path, data))
    assert ok is False
    assert "str" in msg


def test_validate_missing_output_key(tmp_path: Path) -> None:
    """Tool output missing a required key returns (False, error)."""
    broken_output = {"type": "str", "description": "x"}  # missing 'schema'
    broken_tool = {**VALID_TOOL, "output": broken_output}
    data = {**VALID_METADATA, "toolMetadata": {"echo": broken_tool}}
    ok, msg = _validate_metadata_file(_write(tmp_path, data))
    assert ok is False
    assert "output" in msg


def test_validate_missing_output_schema_key(tmp_path: Path) -> None:
    """Return (False, error) when tool output schema is missing a required key."""
    broken_schema = {k: v for k, v in VALID_OUTPUT_SCHEMA.items() if k != "type"}
    broken_output = {**VALID_TOOL["output"], "schema": broken_schema}  # type: ignore[dict-item]
    broken_tool = {**VALID_TOOL, "output": broken_output}
    data = {**VALID_METADATA, "toolMetadata": {"echo": broken_tool}}
    ok, msg = _validate_metadata_file(_write(tmp_path, data))
    assert ok is False
    assert "schema" in msg


def test_validate_properties_count_mismatch(tmp_path: Path) -> None:
    """Return (False, error) when properties and required have different lengths."""
    broken_schema = {
        **VALID_OUTPUT_SCHEMA,
        "required": ["requestId", "result"],  # 2 items, properties has 3
    }
    broken_output = {**VALID_TOOL["output"], "schema": broken_schema}  # type: ignore[dict-item]
    broken_tool = {**VALID_TOOL, "output": broken_output}
    data = {**VALID_METADATA, "toolMetadata": {"echo": broken_tool}}
    ok, msg = _validate_metadata_file(_write(tmp_path, data))
    assert ok is False
    assert "Number of properties" in msg


def test_validate_missing_properties_key(tmp_path: Path) -> None:
    """Return (False, error) when schema properties is missing a required key."""
    # Remove requestId from properties but keep required count equal (2 == 2)
    broken_props = {k: v for k, v in VALID_PROPERTIES.items() if k != "requestId"}
    broken_schema = {
        **VALID_OUTPUT_SCHEMA,
        "properties": broken_props,
        "required": ["result", "prompt"],
    }
    broken_output = {**VALID_TOOL["output"], "schema": broken_schema}  # type: ignore[dict-item]
    broken_tool = {**VALID_TOOL, "output": broken_output}
    data = {**VALID_METADATA, "toolMetadata": {"echo": broken_tool}}
    ok, msg = _validate_metadata_file(_write(tmp_path, data))
    assert ok is False
    assert "requestId" in msg


def test_validate_wrong_properties_data_type(tmp_path: Path) -> None:
    """Wrong type in a property entry returns (False, error)."""
    broken_props = {
        **VALID_PROPERTIES,
        "requestId": {"type": 999, "description": "x"},
    }
    broken_schema = {**VALID_OUTPUT_SCHEMA, "properties": broken_props}
    broken_output = {**VALID_TOOL["output"], "schema": broken_schema}  # type: ignore[dict-item]
    broken_tool = {**VALID_TOOL, "output": broken_output}
    data = {**VALID_METADATA, "toolMetadata": {"echo": broken_tool}}
    ok, msg = _validate_metadata_file(_write(tmp_path, data))
    assert ok is False
    assert "str" in msg


def test_validate_tool_key_in_tools_but_absent_from_toolmetadata(
    tmp_path: Path,
) -> None:
    """Return (False, error) when tool name is in tools but not a key in toolMetadata."""
    # counts match (1 == 1) but "toolA" is not a key in toolMetadata
    data = {**VALID_METADATA, "tools": ["toolA"], "toolMetadata": {"toolB": VALID_TOOL}}
    ok, msg = _validate_metadata_file(_write(tmp_path, data))
    assert ok is False
    assert "toolA" in msg


def test_validate_wrong_output_field_type(tmp_path: Path) -> None:
    """Return (False, error) when an output field has the wrong type."""
    broken_output = {**VALID_TOOL["output"], "type": 42}  # type: ignore[dict-item]
    broken_tool = {**VALID_TOOL, "output": broken_output}
    data = {**VALID_METADATA, "toolMetadata": {"echo": broken_tool}}
    ok, msg = _validate_metadata_file(_write(tmp_path, data))
    assert ok is False
    assert "str" in msg


def test_validate_wrong_output_schema_key_type(tmp_path: Path) -> None:
    """Return (False, error) when an output schema key has the wrong type."""
    broken_schema = {**VALID_OUTPUT_SCHEMA, "required": "notalist"}  # type: ignore[dict-item]
    broken_output = {**VALID_TOOL["output"], "schema": broken_schema}  # type: ignore[dict-item]
    broken_tool = {**VALID_TOOL, "output": broken_output}
    data = {**VALID_METADATA, "toolMetadata": {"echo": broken_tool}}
    ok, msg = _validate_metadata_file(_write(tmp_path, data))
    assert ok is False
    assert "str" in msg


def test_validate_wrong_output_schema_properties_type(tmp_path: Path) -> None:
    """Return (False, error) when output schema 'properties' has the wrong type."""
    broken_schema = {**VALID_OUTPUT_SCHEMA, "properties": "notadict"}  # type: ignore[dict-item]
    broken_output = {**VALID_TOOL["output"], "schema": broken_schema}  # type: ignore[dict-item]
    broken_tool = {**VALID_TOOL, "output": broken_output}
    data = {**VALID_METADATA, "toolMetadata": {"echo": broken_tool}}
    ok, msg = _validate_metadata_file(_write(tmp_path, data))
    assert ok is False
    assert "Dict" in msg


def test_validate_wrong_properties_value_type(tmp_path: Path) -> None:
    """Return (False, error) when a property entry is not a dict."""
    broken_props = {**VALID_PROPERTIES, "requestId": "notadict"}  # type: ignore[dict-item]
    broken_schema = {**VALID_OUTPUT_SCHEMA, "properties": broken_props}
    broken_output = {**VALID_TOOL["output"], "schema": broken_schema}  # type: ignore[dict-item]
    broken_tool = {**VALID_TOOL, "output": broken_output}
    data = {**VALID_METADATA, "toolMetadata": {"echo": broken_tool}}
    ok, msg = _validate_metadata_file(_write(tmp_path, data))
    assert ok is False
    assert "Dict" in msg


def test_validate_missing_property_sub_key(tmp_path: Path) -> None:
    """Return (False, error) when a property entry is missing type or description."""
    broken_props = {
        **VALID_PROPERTIES,
        "requestId": {"type": "str"},
    }  # missing description
    broken_schema = {**VALID_OUTPUT_SCHEMA, "properties": broken_props}
    broken_output = {**VALID_TOOL["output"], "schema": broken_schema}  # type: ignore[dict-item]
    broken_tool = {**VALID_TOOL, "output": broken_output}
    data = {**VALID_METADATA, "toolMetadata": {"echo": broken_tool}}
    ok, msg = _validate_metadata_file(_write(tmp_path, data))
    assert ok is False
    assert "description" in msg


# ---------------------------------------------------------------------------
# publish_metadata_to_ipfs error paths
# ---------------------------------------------------------------------------


def test_publish_metadata_raises_when_validation_fails(tmp_path: Path) -> None:
    """Raise ValueError when metadata file fails validation."""
    invalid = _write(tmp_path, {"name": "only-name"})
    with pytest.raises(ValueError):
        publish_metadata_to_ipfs(metadata_path=invalid)


def test_publish_metadata_raises_on_ipfs_exception(tmp_path: Path) -> None:
    """Raise RuntimeError when the IPFS client raises an exception."""
    valid = _write(tmp_path, {**VALID_METADATA})
    with patch(f"{PUB_MOD}.IPFSTool") as mock_ipfs:
        mock_ipfs.return_value.client.add.side_effect = OSError("IPFS unavailable")
        with pytest.raises(RuntimeError, match="Error pushing metadata to ipfs"):
            publish_metadata_to_ipfs(metadata_path=valid)


def test_publish_metadata_raises_when_hash_key_missing(tmp_path: Path) -> None:
    """Raise RuntimeError when the IPFS response has no 'Hash' key."""
    valid = _write(tmp_path, {**VALID_METADATA})
    with patch(f"{PUB_MOD}.IPFSTool") as mock_ipfs:
        mock_ipfs.return_value.client.add.return_value = {"NotHash": "somecid"}
        with pytest.raises(RuntimeError, match="not found in ipfs response"):
            publish_metadata_to_ipfs(metadata_path=valid)
