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

"""Tests for deploy-mech command."""

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from mtd.commands.deploy_mech_cmd import deploy_mech_command


MOD = "mtd.commands.deploy_mech_cmd"


class TestDeployMechCommand:
    """Tests for deploy-mech command."""

    @patch(f"{MOD}.update_service_after_deploy")
    @patch(f"{MOD}.deploy_mech", return_value=("0xMechAddr", "42"))
    @patch(f"{MOD}.needs_mech_deployment", return_value=True)
    @patch(f"{MOD}.OperateApp")
    @patch(f"{MOD}.require_initialized")
    def test_deploy_mech_command_success(
        self,
        mock_require: MagicMock,
        mock_operate: MagicMock,
        mock_needs: MagicMock,
        mock_deploy: MagicMock,
        mock_update: MagicMock,
    ) -> None:
        """Test successful mech deployment via CLI."""
        mock_app = MagicMock()
        mock_operate.return_value = mock_app
        mock_manager = MagicMock()
        mock_service = MagicMock()
        mock_service.home_chain = "gnosis"
        mock_service.chain_configs = {"gnosis": MagicMock()}
        mock_manager.get_all_services.return_value = ([mock_service], None)
        mock_app.service_manager.return_value = mock_manager

        runner = CliRunner()
        result = runner.invoke(deploy_mech_command, ["-c", "gnosis"])

        assert result.exit_code == 0
        assert "Deploying mech on marketplace" in result.output
        assert "0xMechAddr" in result.output
        assert "agent_id=42" in result.output
        mock_deploy.assert_called_once()
        mock_update.assert_called_once_with(mock_service, "0xMechAddr", "42")

    @patch(f"{MOD}.OperateApp")
    @patch(f"{MOD}.require_initialized")
    def test_deploy_mech_command_no_service(
        self, mock_require: MagicMock, mock_operate: MagicMock
    ) -> None:
        """Test deploy-mech with no services found raises ClickException."""
        mock_app = MagicMock()
        mock_operate.return_value = mock_app
        mock_manager = MagicMock()
        mock_manager.get_all_services.return_value = ([], None)
        mock_app.service_manager.return_value = mock_manager

        runner = CliRunner()
        result = runner.invoke(deploy_mech_command, ["-c", "gnosis"])

        assert result.exit_code != 0
        assert "No service found" in result.output

    @patch(f"{MOD}.deploy_mech")
    @patch(f"{MOD}.needs_mech_deployment", return_value=False)
    @patch(f"{MOD}.OperateApp")
    @patch(f"{MOD}.require_initialized")
    def test_deploy_mech_command_already_deployed(
        self,
        mock_require: MagicMock,
        mock_operate: MagicMock,
        mock_needs: MagicMock,
        mock_deploy: MagicMock,
    ) -> None:
        """Test deploy-mech skips when mech is already deployed."""
        mock_app = MagicMock()
        mock_operate.return_value = mock_app
        mock_manager = MagicMock()
        mock_service = MagicMock()
        mock_manager.get_all_services.return_value = ([mock_service], None)
        mock_app.service_manager.return_value = mock_manager

        runner = CliRunner()
        result = runner.invoke(deploy_mech_command, ["-c", "gnosis"])

        assert result.exit_code == 0
        assert "already deployed" in result.output
        mock_deploy.assert_not_called()

    def test_deploy_mech_command_help(self) -> None:
        """Test deploy-mech help text."""
        runner = CliRunner()
        result = runner.invoke(deploy_mech_command, ["--help"])

        assert result.exit_code == 0
        assert "chain-config" in result.output
        assert "Deploy a mech on the marketplace" in result.output

    @patch(f"{MOD}.update_service_after_deploy")
    @patch(f"{MOD}.deploy_mech", return_value=("0xMech", "1"))
    @patch(f"{MOD}.needs_mech_deployment", return_value=True)
    @patch(f"{MOD}.OperateApp")
    @patch(f"{MOD}.require_initialized")
    def test_deploy_mech_command_all_chains(
        self,
        mock_require: MagicMock,
        mock_operate: MagicMock,
        mock_needs: MagicMock,
        mock_deploy: MagicMock,
        mock_update: MagicMock,
    ) -> None:
        """Test deploy-mech works for all supported chains."""
        mock_app = MagicMock()
        mock_operate.return_value = mock_app
        mock_manager = MagicMock()
        mock_service = MagicMock()
        mock_service.home_chain = "gnosis"
        mock_service.chain_configs = {"gnosis": MagicMock()}
        mock_manager.get_all_services.return_value = ([mock_service], None)
        mock_app.service_manager.return_value = mock_manager

        for chain in ("gnosis", "base", "polygon", "optimism"):
            runner = CliRunner()
            result = runner.invoke(deploy_mech_command, ["-c", chain])
            assert result.exit_code == 0, f"Failed for chain {chain}: {result.output}"

    def test_deploy_mech_command_invalid_chain(self) -> None:
        """Test deploy-mech with invalid chain config."""
        runner = CliRunner()
        result = runner.invoke(deploy_mech_command, ["-c", "invalid_chain"])

        assert result.exit_code != 0
        assert "Invalid value" in result.output or "invalid_chain" in result.output

    def test_deploy_mech_command_missing_chain(self) -> None:
        """Test deploy-mech without required chain-config option."""
        runner = CliRunner()
        result = runner.invoke(deploy_mech_command, [])

        assert result.exit_code != 0
        assert "Missing option" in result.output or "chain-config" in result.output
