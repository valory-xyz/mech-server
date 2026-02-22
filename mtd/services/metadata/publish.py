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

"""Metadata publish service."""

import json
from pathlib import Path
from typing import Dict, List, Tuple

from aea.helpers.cid import to_v1
from aea_cli_ipfs.ipfs_utils import IPFSTool
from multibase import multibase
from multicodec import multicodec


PREFIX = "f01701220"
IPFS_PREFIX_LENGTH = 6
RESPONSE_KEY = "Hash"
DEFAULT_IPFS_NODE = "/dns/registry.autonolas.tech/tcp/443/https"

metadata_schema = {
    "name": str,
    "description": str,
    "inputFormat": str,
    "outputFormat": str,
    "image": str,
    "tools": List,
    "toolMetadata": Dict,
}

tool_schema = {
    "name": str,
    "description": str,
    "input": Dict,
    "output": Dict,
}
tool_input_schema = {
    "type": str,
    "description": str,
}
tool_output_schema = {"type": str, "description": str, "schema": Dict}

output_schema_schema = {
    "properties": Dict,
    "required": List,
    "type": str,
}

properties_schema = {
    "requestId": Dict,
    "result": Dict,
    "prompt": Dict,
}

properties_data_schema = {
    "type": str,
    "description": str,
}


def _validate_metadata_file(  # pylint: disable=too-many-return-statements,too-many-statements
    file_path: Path,
) -> Tuple[bool, str]:  # pylint: disable=too-many-return-statements,too-many-statements
    status = False
    try:
        metadata: Dict = json.loads(file_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return (status, f"Error: Metadata file not found at {file_path}")
    except json.JSONDecodeError:
        return (status, "Error: Metadata file contains invalid JSON.")

    for key, expected_type in metadata_schema.items():
        if key not in metadata:
            return (status, f"Missing key in metadata json: {key!r}")

        if not isinstance(metadata[key], expected_type):
            expected = expected_type.__name__
            actual = type(metadata[key]).__name__
            return (
                status,
                f"Invalid type for key in metadata json. Expected {expected!r}, but got {actual!r}",
            )

    tools = metadata["tools"]
    tools_metadata = metadata["toolMetadata"]
    if len(tools) != len(tools_metadata):
        return (
            status,
            "Number of tools does not match number of keys in 'toolMetadata'. "
            f"Expected {len(tools)} but got {len(tools_metadata)}.",
        )

    for tool in tools:
        if tool not in tools_metadata:
            return (status, f"Missing toolsMetadata for tool: {tool!r}")

        for key, expected_type in tool_schema.items():
            data = tools_metadata[tool]
            if key not in data:
                return (status, f"Missing key in toolsMetadata: {key!r}")

            if not isinstance(data[key], expected_type):
                expected = expected_type.__name__
                actual = type(data[key]).__name__
                return (
                    status,
                    f"Invalid type for key in toolsMetadata. Expected {expected!r}, but got {actual!r}.",
                )

            if key == "input":
                for i_key, i_expected_type in tool_input_schema.items():
                    input_data = data[key]
                    if i_key not in input_data:
                        return (status, f"Missing key for {tool} -> input: {i_key!r}")
                    if not isinstance(input_data[i_key], i_expected_type):
                        i_expected = i_expected_type.__name__
                        i_actual = type(input_data[i_key]).__name__
                        return (
                            status,
                            f"Invalid type for {i_key!r} in {tool} -> input. Expected {i_expected!r}, but got {i_actual!r}.",
                        )

            elif key == "output":
                for o_key, o_expected_type in tool_output_schema.items():
                    output_data = data[key]
                    if o_key not in output_data:
                        return (status, f"Missing key for {tool} -> output: {o_key!r}")
                    if not isinstance(output_data[o_key], o_expected_type):
                        o_expected = o_expected_type.__name__
                        o_actual = type(output_data[o_key]).__name__
                        return (
                            status,
                            f"Invalid type for {o_key!r} in {tool} -> output. Expected {o_expected!r}, but got {o_actual!r}.",
                        )

                    if o_key == "schema":
                        output_schema_data = output_data[o_key]
                        for s_key, s_expected_type in output_schema_schema.items():
                            if s_key not in output_schema_data:
                                return (
                                    status,
                                    f"Missing key for {tool} -> output -> schema: {s_key!r}",
                                )
                            if not isinstance(
                                output_schema_data[s_key], s_expected_type
                            ):
                                s_expected = s_expected_type.__name__
                                s_actual = type(output_schema_data[s_key]).__name__
                                return (
                                    status,
                                    f"Invalid type for {s_key!r} in {tool} -> output -> schema. Expected {s_expected!r}, but got {s_actual!r}.",
                                )

                        if "required" in output_schema_data:
                            properties_data = output_schema_data.get("properties", {})
                            required = output_schema_data.get("required", [])
                            if len(properties_data) != len(required):
                                return (
                                    status,
                                    "Number of properties data does not match number of keys in 'required'. "
                                    f"Expected {len(required)} but got {len(properties_data)}.",
                                )

                            for p_key, p_expected_type in properties_schema.items():
                                if p_key not in properties_data:
                                    return (
                                        status,
                                        f"Missing key for {tool} -> output -> schema -> properties: {p_key!r}",
                                    )
                                if not isinstance(
                                    properties_data[p_key], p_expected_type
                                ):
                                    p_expected = p_expected_type.__name__
                                    p_actual = type(properties_data[p_key]).__name__
                                    return (
                                        status,
                                        f"Invalid type for {p_key!r} in {tool} -> output -> schema -> properties. Expected {p_expected!r}, but got {p_actual!r}.",
                                    )

                                for (
                                    pd_key,
                                    pd_expected_type,
                                ) in properties_data_schema.items():
                                    property_data = properties_data[p_key]
                                    if pd_key not in property_data:
                                        return (
                                            status,
                                            f"Missing key in properties -> {p_key}: {pd_key!r}",
                                        )
                                    if not isinstance(
                                        property_data[pd_key], pd_expected_type
                                    ):
                                        expected = pd_expected_type.__name__
                                        actual = type(property_data[pd_key]).__name__
                                        return (
                                            status,
                                            f"Invalid type for key in properties. Expected {expected!r}, but got {actual!r}",
                                        )

    return (True, "")


def publish_metadata_to_ipfs(
    metadata_path: Path, ipfs_node: str = DEFAULT_IPFS_NODE
) -> str:
    """Publish metadata file to IPFS and return on-chain metadata hash."""
    status, error_msg = _validate_metadata_file(metadata_path)
    if not status:
        raise ValueError(error_msg)

    try:
        response = IPFSTool(addr=ipfs_node).client.add(
            str(metadata_path), pin=True, recursive=True, wrap_with_directory=False
        )
    except Exception as e:  # pylint: disable=broad-except
        raise RuntimeError(f"Error pushing metadata to ipfs: {e}") from e

    if RESPONSE_KEY not in response:
        raise RuntimeError(f"Key {RESPONSE_KEY!r} not found in ipfs response")

    cid_bytes = multibase.decode(to_v1(response[RESPONSE_KEY]))
    multihash_bytes = multicodec.remove_prefix(cid_bytes)
    hex_multihash = multihash_bytes.hex()
    return PREFIX + hex_multihash[IPFS_PREFIX_LENGTH:]
