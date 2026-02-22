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
"""Tests for run command."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner

from mtd.commands.run_cmd import _get_latest_service_hash, run


MOCK_PATH = "mtd.commands.run_cmd"


class TestGetLatestServiceHash:
    """Tests for _get_latest_service_hash."""

    @patch(f"{MOCK_PATH}.subprocess.run")
    def test_raises_when_packages_json_missing(
        self, mock_subproc: MagicMock, tmp_path: Path
    ) -> None:
        """Raise ClickException when packages.json does not exist."""
        context = MagicMock()
        context.workspace_path = tmp_path
        context.packages_dir = tmp_path / "packages"
        # packages.json is deliberately not created

        with pytest.raises(click.ClickException, match="Could not determine"):
            _get_latest_service_hash(context)

    @patch(f"{MOCK_PATH}.subprocess.run")
    def test_raises_when_no_matching_hash(
        self, mock_subproc: MagicMock, tmp_path: Path
    ) -> None:
        """Raise ClickException when packages.json has no service/mech entry."""
        context = MagicMock()
        context.workspace_path = tmp_path
        context.packages_dir = tmp_path / "packages"
        context.packages_dir.mkdir()
        (context.packages_dir / "packages.json").write_text(
            json.dumps({"dev": {"author/connection/name/0.1.0": "abc123"}}),
            encoding="utf-8",
        )

        with pytest.raises(click.ClickException, match="Could not determine"):
            _get_latest_service_hash(context)

    @patch(f"{MOCK_PATH}.subprocess.run")
    def test_returns_matching_service_hash(
        self, mock_subproc: MagicMock, tmp_path: Path
    ) -> None:
        """Returns the first hash matching 'service' and 'mech' in the key."""
        context = MagicMock()
        context.workspace_path = tmp_path
        context.packages_dir = tmp_path / "packages"
        context.packages_dir.mkdir()
        (context.packages_dir / "packages.json").write_text(
            json.dumps(
                {
                    "dev": {
                        "valory/service/mech/0.1.0": "bafymechhash",
                        "valory/skill/other/0.1.0": "otherhash",
                    }
                }
            ),
            encoding="utf-8",
        )

        result = _get_latest_service_hash(context)

        assert result == "bafymechhash"


class TestRunCommand:
    """Tests for run command."""

    @patch(f"{MOCK_PATH}.run_service")
    @patch(f"{MOCK_PATH}.OperateApp")
    @patch(f"{MOCK_PATH}.require_initialized")
    @patch(f"{MOCK_PATH}.get_mtd_context")
    def test_run_success(
        self,
        mock_get_context: MagicMock,
        mock_require_initialized: MagicMock,
        mock_operate: MagicMock,
        mock_run_service: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test successful run in production mode."""
        context = MagicMock()
        context.workspace_path = tmp_path
        context.config_dir = tmp_path / "config"
        context.config_dir.mkdir(parents=True)
        (context.config_dir / "config_mech_gnosis.json").write_text(
            "{}", encoding="utf-8"
        )
        mock_get_context.return_value = context

        mock_app = MagicMock()
        mock_operate.return_value = mock_app

        runner = CliRunner()
        result = runner.invoke(run, ["-c", "gnosis"])

        assert result.exit_code == 0
        mock_require_initialized.assert_called_once_with(context)
        mock_run_service.assert_called_once()

    def test_run_missing_chain_config(self) -> None:
        """Test run without required chain-config option."""
        runner = CliRunner()
        result = runner.invoke(run, [])
        assert result.exit_code != 0

    @patch(f"{MOCK_PATH}._run_dev_mode")
    @patch(f"{MOCK_PATH}.require_initialized")
    @patch(f"{MOCK_PATH}.get_mtd_context")
    def test_run_dev_flag_delegates(
        self,
        mock_get_context: MagicMock,
        mock_require_initialized: MagicMock,
        mock_dev_mode: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test that --dev flag delegates to _run_dev_mode."""
        context = MagicMock()
        context.config_dir = tmp_path / "config"
        context.config_dir.mkdir(parents=True)
        (context.config_dir / "config_mech_gnosis.json").write_text(
            "{}", encoding="utf-8"
        )
        mock_get_context.return_value = context

        runner = CliRunner()
        result = runner.invoke(run, ["-c", "gnosis", "--dev"])

        assert result.exit_code == 0
        mock_require_initialized.assert_called_once_with(context)
        mock_dev_mode.assert_called_once()
