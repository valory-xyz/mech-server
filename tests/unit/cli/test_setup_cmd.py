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
"""Tests for setup command."""

from unittest.mock import MagicMock, patch

from click.testing import CliRunner
from mtd.commands.setup_cmd import setup as setup_command

MOD = "mtd.commands.setup_cmd"


class TestSetupCommand:
    """Tests for setup command."""

    @patch(f"{MOD}.run_setup")
    @patch(f"{MOD}.initialize_workspace")
    @patch(f"{MOD}.get_mtd_context")
    def test_setup_success_initialized_workspace(
        self,
        mock_get_context: MagicMock,
        mock_initialize_workspace: MagicMock,
        mock_run_setup: MagicMock,
    ) -> None:
        """Setup should run without re-initializing already initialized workspace."""
        context = MagicMock()
        context.is_initialized.return_value = True
        mock_get_context.return_value = context

        runner = CliRunner()
        result = runner.invoke(setup_command, ["-c", "gnosis"])

        assert result.exit_code == 0
        mock_initialize_workspace.assert_not_called()
        mock_run_setup.assert_called_once_with(chain_config="gnosis", context=context)

    @patch(f"{MOD}.run_setup")
    @patch(f"{MOD}.initialize_workspace")
    @patch(f"{MOD}.get_mtd_context")
    def test_setup_bootstraps_uninitialized_workspace(
        self,
        mock_get_context: MagicMock,
        mock_initialize_workspace: MagicMock,
        mock_run_setup: MagicMock,
    ) -> None:
        """Setup should auto-bootstrap workspace when not initialized."""
        context = MagicMock()
        context.is_initialized.return_value = False
        mock_get_context.return_value = context

        runner = CliRunner()
        result = runner.invoke(setup_command, ["-c", "gnosis"])

        assert result.exit_code == 0
        assert "Workspace not initialized" in result.output
        mock_initialize_workspace.assert_called_once_with(context=context, force=False)
        mock_run_setup.assert_called_once_with(chain_config="gnosis", context=context)

    def test_setup_missing_chain_config(self) -> None:
        """Test setup without required chain-config option."""
        runner = CliRunner()
        result = runner.invoke(setup_command, [])

        assert result.exit_code != 0

    def test_setup_invalid_chain_config(self) -> None:
        """Test setup with invalid chain config."""
        runner = CliRunner()
        result = runner.invoke(setup_command, ["-c", "invalid_chain"])

        assert result.exit_code != 0

    def test_setup_help(self) -> None:
        """Test setup help output."""
        runner = CliRunner()
        result = runner.invoke(setup_command, ["--help"])

        assert result.exit_code == 0
        assert "chain-config" in result.output
        assert "Full first-time setup for a mech AI agent" in result.output
