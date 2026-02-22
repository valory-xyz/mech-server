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
"""Tests for context_utils helpers."""

from pathlib import Path
from unittest.mock import MagicMock

import click
import pytest

from mtd.commands.context_utils import get_mtd_context, require_initialized
from mtd.context import MtdContext, build_context


def test_get_mtd_context_returns_existing_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Return the existing MtdContext when already stored in click context obj."""
    monkeypatch.setenv("HOME", str(tmp_path))
    existing = build_context()
    mock_ctx = MagicMock(spec=click.Context)
    mock_ctx.ensure_object.return_value = {"mtd_context": existing}

    result = get_mtd_context(mock_ctx)

    assert result is existing
    assert isinstance(result, MtdContext)


def test_require_initialized_raises_when_workspace_not_initialized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Raise ClickException when the workspace marker file is absent."""
    monkeypatch.setenv("HOME", str(tmp_path))
    context = build_context()
    # initialized_marker_path does not exist → is_initialized() returns False

    with pytest.raises(click.ClickException, match="not initialized"):
        require_initialized(context)
