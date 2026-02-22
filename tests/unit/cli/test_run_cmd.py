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

from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from mtd.commands.run_cmd import run


MOCK_PATH = "mtd.commands.run_cmd"


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
