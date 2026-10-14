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
"""Tests for packaged runtime resources."""

import json
from pathlib import Path

import pytest
from mtd.context import build_context
from mtd.resources import (
    copy_runtime_templates_to_workspace,
    iter_runtime_templates,
    read_text_resource,
    refresh_chain_config,
)

OLD_RELEASE_CONFIG = {
    "name": "Mech",
    "hash": "bafybeiold",
    "service_version": "v0.34.3",
    "agent_release": {"repository": {"version": "v0.0.1"}},
    "home_chain": "gnosis",
    "env_variables": {
        "METADATA_HASH": {"value": "f0170abc", "provision_type": "fixed"},
        "GNOSIS_LEDGER_RPC": {"value": "https://rpc.example", "provision_type": "user"},
    },
}


def test_read_text_resource() -> None:
    """Runtime env template should be loadable from package resources."""
    content = read_text_resource("mtd.templates.runtime", ".example.env")
    assert "DEFAULT_CHAIN_ID" in content


def test_iter_runtime_templates_contains_chain_configs() -> None:
    """Runtime templates iterator should include chain config templates."""
    template_names = {name for name, _ in iter_runtime_templates()}
    assert "config_mech_gnosis.json" in template_names
    assert "config_mech_base.json" in template_names


def test_copy_runtime_templates_to_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Copying runtime templates should materialize expected files."""
    monkeypatch.setenv("HOME", str(tmp_path))
    context = build_context()
    copy_runtime_templates_to_workspace(context)

    assert (context.config_dir / "config_mech_gnosis.json").exists()
    assert (context.workspace_path / ".example.env").exists()


def test_copy_runtime_templates_skips_existing_without_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Skip writing a template when the target already exists and force=False."""
    monkeypatch.setenv("HOME", str(tmp_path))
    context = build_context()
    # First copy to create all files
    copy_runtime_templates_to_workspace(context)
    config = context.config_dir / "config_mech_gnosis.json"
    original_content = config.read_text(encoding="utf-8")
    # Overwrite with sentinel content
    config.write_text("SENTINEL", encoding="utf-8")

    # Second copy without force → should NOT overwrite
    copy_runtime_templates_to_workspace(context, force=False)

    assert config.read_text(encoding="utf-8") == "SENTINEL"

    # Third copy with force=True → should overwrite
    copy_runtime_templates_to_workspace(context, force=True)

    assert config.read_text(encoding="utf-8") == original_content


def test_refresh_chain_config_moves_an_old_workspace_to_this_release(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Release-owned keys follow the packaged template; the operator's values stay."""
    monkeypatch.setenv("HOME", str(tmp_path))
    context = build_context()
    context.config_dir.mkdir(parents=True)
    config = context.config_dir / "config_mech_gnosis.json"
    config.write_text(json.dumps(OLD_RELEASE_CONFIG), encoding="utf-8")
    packaged = json.loads(read_text_resource("mtd.templates.runtime", config.name))

    changed = refresh_chain_config(context=context, chain_config="gnosis")

    result = json.loads(config.read_text(encoding="utf-8"))
    assert result["hash"] == packaged["hash"]
    assert result["service_version"] == packaged["service_version"]
    assert result["agent_release"] == packaged["agent_release"]
    assert result["env_variables"]["METADATA_HASH"]["value"] == "f0170abc"
    assert (
        result["env_variables"]["GNOSIS_LEDGER_RPC"]["value"] == "https://rpc.example"
    )
    assert (
        result["env_variables"]["MECH_TERMS_URL"]
        == packaged["env_variables"]["MECH_TERMS_URL"]
    )
    assert changed[:3] == ["hash", "service_version", "agent_release"]
    assert "MECH_TERMS_URL" in changed
    assert "METADATA_HASH" not in changed


def test_refresh_chain_config_leaves_a_current_workspace_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A copy that already matches the release is neither changed nor rewritten."""
    monkeypatch.setenv("HOME", str(tmp_path))
    context = build_context()
    copy_runtime_templates_to_workspace(context)
    config = context.config_dir / "config_mech_gnosis.json"
    before = config.read_text(encoding="utf-8")

    assert not refresh_chain_config(context=context, chain_config="gnosis")
    assert config.read_text(encoding="utf-8") == before
