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
import re
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List, Mapping, Optional, Tuple
from urllib.parse import urlparse

import yaml

CUSTOMS = "customs"
INIT_PY = "__init__.py"
COMPONENT_YAML = "component.yaml"
TOOLS_IDENTIFIERS = frozenset(["ALLOWED_TOOLS", "AVAILABLE_TOOLS"])
BENCHMARK_WINDOWS = ("7d", "30d", "90d", "all")
MAX_HOSTNAME_LENGTH = 253
_HOSTNAME_LABEL = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")
METADATA_TEMPLATE: Dict[str, Any] = {
    "description": "The mech executes AI tasks requested on-chain and delivers the results to the requester.",
    "inputFormat": "ipfs-v0.1",
    "outputFormat": "ipfs-v0.1",
    "image": "tbd",
    "url": "",
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


def _hostname_error(domain: str) -> Optional[str]:
    """Return why ``domain`` is not a lowercase dotted bare hostname, or None."""
    if not domain:
        return "it is empty"
    if "://" in domain:
        return "it must not include a scheme"
    if "/" in domain or "?" in domain or "#" in domain:
        return "it must not include a path"
    if ":" in domain or "@" in domain:
        return "it must not include a port or credentials"
    if domain.endswith("."):
        return "it must not end with a dot"
    if len(domain) > MAX_HOSTNAME_LENGTH:
        return f"it exceeds {MAX_HOSTNAME_LENGTH} characters"
    if domain != domain.lower():
        return "it must be lowercase"
    if "." not in domain:
        return "it must contain at least one dot"
    for label in domain.split("."):
        if not _HOSTNAME_LABEL.fullmatch(label):
            return f"label {label!r} is not a valid hostname label"
    return None


def _is_https_url(url: str) -> bool:
    """Return True for an ``https://`` URL with a host and no whitespace."""
    if any(char.isspace() for char in url):
        return False
    parsed = urlparse(url)
    return parsed.scheme == "https" and bool(parsed.netloc)


FieldTypes = Mapping[str, Tuple[type, ...]]


def _require_fields(
    data: Any, what: str, required: FieldTypes, optional: FieldTypes
) -> Dict[str, Any]:
    """Check that ``data`` is an object holding exactly the known fields with the right types."""
    if not isinstance(data, dict):
        raise ValueError(f"{what} must be an object, got {type(data).__name__}")
    unknown = sorted(set(data) - set(required) - set(optional))
    if unknown:
        raise ValueError(f"Unknown {what.lower()} field(s): {', '.join(unknown)}")
    for key in required:
        if key not in data:
            raise ValueError(f"Missing {what.lower()} field {key!r}")
    for key, expected in {**required, **optional}.items():
        if key not in data:
            continue
        value = data[key]
        if isinstance(value, bool) or not isinstance(value, expected):
            allowed = " or ".join(t.__name__ for t in expected)
            raise ValueError(
                f"{what} field {key!r} must be {allowed}, got {type(value).__name__}"
            )
    return data


@dataclass(frozen=True)
class Operator:
    """Who runs the mech. ``domain`` is the host serving the ERC-8004 domain proof."""

    name: str
    domain: str
    contact: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate the block."""
        if not self.name.strip():
            raise ValueError("Operator name must not be empty")
        error = _hostname_error(self.domain)
        if error is not None:
            raise ValueError(
                f"Operator domain {self.domain!r} is not a bare hostname: {error}"
            )
        if self.contact is not None and not self.contact.strip():
            raise ValueError("Operator contact must not be blank when given")

    def to_dict(self) -> Dict[str, str]:
        """Return the manifest ``operator`` object."""
        result = {"name": self.name, "domain": self.domain}
        if self.contact is not None:
            result["contact"] = self.contact
        return result

    @classmethod
    def from_dict(cls, data: Any) -> "Operator":
        """Build from a manifest ``operator`` object, rejecting unknown or mistyped fields."""
        fields = _require_fields(
            data,
            "Operator",
            required={"name": (str,), "domain": (str,)},
            optional={"contact": (str,)},
        )
        return cls(
            name=fields["name"], domain=fields["domain"], contact=fields.get("contact")
        )


@dataclass(frozen=True)
class Benchmark:
    """A tool's score link; ``value`` is None when no figure exists for the window yet."""

    metric: str
    window: str
    url: str
    value: Optional[float] = None

    def __post_init__(self) -> None:
        """Validate the block."""
        if not self.metric.strip():
            raise ValueError("Benchmark metric must not be empty")
        if self.value is not None:
            self._check_value(self.value)
        if self.window not in BENCHMARK_WINDOWS:
            raise ValueError(
                f"Benchmark window must be one of {', '.join(BENCHMARK_WINDOWS)}, "
                f"got {self.window!r}"
            )
        if not _is_https_url(self.url):
            raise ValueError(
                f"Benchmark url must be an https URL with a host, got {self.url!r}"
            )

    @staticmethod
    def _check_value(value: Any) -> None:
        """Require a number in 0..1; bool is excluded even though it subclasses int."""
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(
                f"Benchmark value must be a number, got {type(value).__name__}"
            )
        if not 0 <= value <= 1:
            raise ValueError(f"Benchmark value must be between 0 and 1, got {value}")

    def to_dict(self) -> Dict[str, Any]:
        """Return the manifest ``benchmark`` object, without ``value`` when there is none."""
        result: Dict[str, Any] = {"metric": self.metric}
        if self.value is not None:
            result["value"] = self.value
        result["window"] = self.window
        result["url"] = self.url
        return result

    @classmethod
    def from_dict(cls, data: Any) -> "Benchmark":
        """Build from a manifest ``benchmark`` object, rejecting unknown or mistyped fields."""
        fields = _require_fields(
            data,
            "Benchmark",
            required={"metric": (str,), "window": (str,), "url": (str,)},
            optional={"value": (int, float)},
        )
        return cls(
            metric=fields["metric"],
            window=fields["window"],
            url=fields["url"],
            value=fields.get("value"),
        )


def _import_module_from_path(module_name: str, file_path: Path) -> ModuleType:
    """Import a module from path."""
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module {module_name!r} from {file_path!s}")

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except SyntaxError as exc:
        raise RuntimeError(
            f"Syntax error in module {module_name!r} at {file_path}: {exc}"
        ) from exc
    except Exception as exc:  # pylint: disable=broad-except
        raise RuntimeError(
            f"Failed to load module {module_name!r} from {file_path}: {exc}"
        ) from exc
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


def _build_metadata(
    tools_data: List[Dict[str, Any]],
    name: str,
    operator: Optional[Operator] = None,
    benchmarks: Optional[Mapping[str, Benchmark]] = None,
) -> Dict[str, Any]:
    """Build metadata document from tools data.

    :param tools_data: tool entries as returned by ``_build_tools_data``.
    :param name: human-readable mech name; there is no default.
    :param operator: optional operator block.
    :param benchmarks: optional per-tool benchmarks keyed by tool name; every
        key must be a tool present in the generated manifest.
    :return: the manifest as a JSON-serialisable dict.
    """
    result: Dict[str, Any] = {"name": name, **METADATA_TEMPLATE}
    if operator is not None:
        result["operator"] = operator.to_dict()
    result["tools"] = []
    result["toolMetadata"] = {}

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

    for tool, benchmark in (benchmarks or {}).items():
        if tool not in result["toolMetadata"]:
            raise ValueError(
                f"Benchmark given for unknown tool {tool!r}. "
                f"Tools in this manifest: {', '.join(result['tools']) or '(none)'}"
            )
        result["toolMetadata"][tool]["benchmark"] = benchmark.to_dict()

    return result


def generate_metadata(  # pylint: disable=too-many-arguments
    packages_dir: Path,
    metadata_path: Path,
    name: str,
    offchain_url: str = "",
    operator: Optional[Operator] = None,
    benchmarks: Optional[Mapping[str, Benchmark]] = None,
) -> Path:
    """Generate metadata from package customs and write to path.

    :param packages_dir: workspace ``packages/`` root to scan for tools.
    :param metadata_path: where to write the manifest.
    :param name: human-readable mech name; must not be blank.
    :param offchain_url: public URL serving off-chain requests, or empty.
    :param operator: optional operator block.
    :param benchmarks: optional per-tool benchmarks keyed by tool name.
    :return: ``metadata_path``.
    :raises FileNotFoundError: when ``packages_dir`` does not exist.
    :raises ValueError: when ``name`` is blank or a benchmark names an unknown tool.
    """
    if not name.strip():
        raise ValueError("Mech name must not be empty")
    if not packages_dir.exists():
        raise FileNotFoundError(
            f"Packages directory not found: {packages_dir}. "
            "Use 'mech add-tool' first or run in --dev mode."
        )

    tools_data = _build_tools_data(packages_dir=packages_dir)
    metadata = _build_metadata(
        tools_data=tools_data, name=name, operator=operator, benchmarks=benchmarks
    )
    if offchain_url:
        metadata["url"] = offchain_url
    metadata_path.write_text(json.dumps(metadata, indent=4), encoding="utf-8")
    return metadata_path
