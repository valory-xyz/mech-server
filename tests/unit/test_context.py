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
"""Tests for mech context helpers."""

from pathlib import Path

import pytest

from mtd.context import build_context, get_default_workspace


def test_get_default_workspace() -> None:
    """Default workspace should point to ~/.operate-mech."""
    assert get_default_workspace() == Path("~/.operate-mech").expanduser().resolve()


def test_context_is_initialized_false_then_true(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Context init flag should reflect marker/config/env presence."""
    monkeypatch.setenv("HOME", str(tmp_path))
    context = build_context()
    context.ensure_workspace_exists()

    assert context.is_initialized() is False

    context.config_dir.mkdir(parents=True, exist_ok=True)
    context.env_path.write_text("", encoding="utf-8")
    context.initialized_marker_path.write_text("initialized\n", encoding="utf-8")

    assert context.is_initialized() is True


def test_chain_env_path_returns_expected_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Return a chain-specific env file path under workspace root."""
    monkeypatch.setenv("HOME", str(tmp_path))
    context = build_context()

    result = context.chain_env_path("gnosis")

    assert result == context.workspace_path / ".env.gnosis"
