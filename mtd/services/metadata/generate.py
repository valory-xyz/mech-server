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

"""Metadata generation service."""

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List

import yaml


CUSTOMS = "customs"
INIT_PY = "__init__.py"
COMPONENT_YAML = "component.yaml"
TOOLS_IDENTIFIERS = frozenset(["ALLOWED_TOOLS", "AVAILABLE_TOOLS"])
METADATA_TEMPLATE: Dict[str, Any] = {
    "name": "Autonolas Mech III",
    "description": "The mech executes AI tasks requested on-chain and delivers the results to the requester.",
    "inputFormat": "ipfs-v0.1",
    "outputFormat": "ipfs-v0.1",
    "image": "tbd",
    "tools": [],
    "toolMetadata": {},
}
INPUT_SCHEMA = {
    "type": "text",
    "description": "The text to make a prediction on",
}
OUTPUT_SCHEMA = {
    "type": "object",
    "description": "A JSON object containing the prediction and confidence",
    "schema": {
        "type": "object",
        "properties": {
            "requestId": {
                "type": "integer",
                "description": "Unique identifier for the request",
            },
            "result": {
                "type": "string",
                "description": "Result information in JSON format as a string",
                "example": '{\n  "p_yes": 0.6,\n  "p_no": 0.4,\n  "confidence": 0.8,\n  "info_utility": 0.6\n}',
            },
            "prompt": {
                "type": "string",
                "description": "The prompt used to make the prediction.",
            },
        },
        "required": ["requestId", "result", "prompt"],
    },
}


def _import_module_from_path(module_name: str, file_path: Path) -> ModuleType:
    """Import a module from path."""
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module {module_name!r} from {file_path!s}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _build_tools_data(packages_dir: Path) -> List[Dict[str, Any]]:
    """Build tool entries by scanning packages customs folders."""
    tools_data: List[Dict[str, Any]] = []

    customs_folders = [
        path
        for path in packages_dir.rglob("*")
        if path.is_dir() and path.name == CUSTOMS
    ]
    for customs_folder in customs_folders:
        for tool_folder in [item for item in customs_folder.iterdir() if item.is_dir()]:
            tool_entry: Dict[str, Any] = {}
            for file_path in tool_folder.iterdir():
                if not file_path.is_file():
                    continue

                if file_path.name == INIT_PY:
                    continue

                if file_path.name == COMPONENT_YAML:
                    component = yaml.safe_load(file_path.read_text(encoding="utf-8"))
                    tool_entry["author"] = component.get("author")
                    tool_entry["tool_name"] = component.get("name")
                    tool_entry["description"] = component.get("description")
                    continue

                if file_path.suffix != ".py":
                    continue

                module = _import_module_from_path(file_path.name, file_path)
                for identifier in TOOLS_IDENTIFIERS:
                    tools = getattr(module, identifier, None)
                    if isinstance(tools, list):
                        tool_entry["allowed_tools"] = tools
                        break

            if tool_entry:
                tools_data.append(tool_entry)

    return tools_data


def _build_metadata(tools_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build metadata document from tools data."""
    result: Dict[str, Any] = {
        **METADATA_TEMPLATE,
        "tools": [],
        "toolMetadata": {},
    }

    for entry in tools_data:
        for tool in entry.get("allowed_tools", []):
            if tool not in result["tools"]:
                result["tools"].append(tool)
            result["toolMetadata"][tool] = {
                "name": entry.get("tool_name", ""),
                "description": entry.get("description", ""),
                "input": INPUT_SCHEMA,
                "output": OUTPUT_SCHEMA,
            }

    return result


def generate_metadata(packages_dir: Path, metadata_path: Path) -> Path:
    """Generate metadata from package customs and write to path."""
    if not packages_dir.exists():
        raise FileNotFoundError(
            f"Packages directory not found: {packages_dir}. Use 'mech add-tool' first or run in --dev mode."
        )

    tools_data = _build_tools_data(packages_dir=packages_dir)
    metadata = _build_metadata(tools_data=tools_data)
    metadata_path.write_text(json.dumps(metadata, indent=4), encoding="utf-8")
    return metadata_path
