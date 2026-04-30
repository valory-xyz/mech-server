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

from pathlib import Path

import pytest
from mtd.context import build_context
from mtd.resources import (
    copy_runtime_templates_to_workspace,
    iter_runtime_templates,
    read_text_resource,
)


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
