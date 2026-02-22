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
"""Tests for workspace initialization."""

from pathlib import Path
from unittest.mock import patch

import click
import pytest

from mtd.context import build_context
from mtd.workspace import initialize_workspace


MOD = "mtd.workspace"


def test_initialize_workspace_happy_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Happy path: workspace marker, env file, and packages are created."""
    monkeypatch.setenv("HOME", str(tmp_path))
    context = build_context()

    with patch(f"{MOD}.shutil.copytree"):
        initialize_workspace(context)

    assert context.workspace_path.exists()
    assert context.env_path.exists()
    assert context.initialized_marker_path.exists()
    assert context.initialized_marker_path.read_text() == "initialized\n"


def test_initialize_workspace_skips_existing_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Existing .env is not overwritten without force=True."""
    monkeypatch.setenv("HOME", str(tmp_path))
    context = build_context()
    context.workspace_path.mkdir(parents=True, exist_ok=True)
    context.env_path.write_text("EXISTING=1", encoding="utf-8")

    with patch(f"{MOD}.shutil.copytree"):
        initialize_workspace(context)

    assert context.env_path.read_text(encoding="utf-8") == "EXISTING=1"


def test_initialize_workspace_force_overwrites_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """force=True replaces an existing .env with the template."""
    monkeypatch.setenv("HOME", str(tmp_path))
    context = build_context()
    context.workspace_path.mkdir(parents=True, exist_ok=True)
    context.env_path.write_text("EXISTING=1", encoding="utf-8")

    with patch(f"{MOD}.shutil.copytree"), patch(f"{MOD}.shutil.rmtree"):
        initialize_workspace(context, force=True)

    content = context.env_path.read_text(encoding="utf-8")
    assert "EXISTING=1" not in content
    assert "DEFAULT_CHAIN_ID" in content


def test_initialize_workspace_force_removes_and_recopies_packages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """force=True deletes the existing packages dir and copies afresh."""
    monkeypatch.setenv("HOME", str(tmp_path))
    context = build_context()
    context.packages_dir.mkdir(parents=True, exist_ok=True)

    # Let rmtree actually remove packages_dir so the exists() check triggers copytree
    with patch(f"{MOD}.shutil.copytree") as mock_cp:
        initialize_workspace(context, force=True)

    assert not context.packages_dir.exists()
    mock_cp.assert_called_once()


def test_initialize_workspace_skips_copytree_when_packages_exist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When packages_dir already exists (no force), copytree is not called."""
    monkeypatch.setenv("HOME", str(tmp_path))
    context = build_context()
    context.packages_dir.mkdir(parents=True, exist_ok=True)

    with patch(f"{MOD}.shutil.copytree") as mock_cp:
        initialize_workspace(context)

    mock_cp.assert_not_called()


def test_initialize_workspace_missing_packaged_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Raise ClickException when the bundled packages/ dir is missing."""
    monkeypatch.setenv("HOME", str(tmp_path))
    context = build_context()

    # Point __file__ to a location where no sibling packages/ dir exists
    fake_file = str(tmp_path / "fake" / "mtd" / "workspace.py")
    with patch(f"{MOD}.__file__", fake_file):
        with pytest.raises(click.ClickException, match="Packaged tools"):
            initialize_workspace(context)
