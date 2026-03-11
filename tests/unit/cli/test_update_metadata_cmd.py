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
"""Tests for update-metadata command."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from mtd.commands.update_metadata_cmd import update_metadata

MOCK_PATH = "mtd.commands.update_metadata_cmd"


class TestUpdateMetadataCommand:
    """Tests for update-metadata command."""

    @patch(f"{MOCK_PATH}.update_metadata_onchain", return_value=(True, "0xtx"))
    @patch(f"{MOCK_PATH}.require_initialized")
    @patch(f"{MOCK_PATH}.get_mtd_context")
    def test_update_metadata_success(
        self,
        mock_get_context: MagicMock,
        mock_require_initialized: MagicMock,
        mock_update: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test successful update-metadata with chain flag."""
        context = MagicMock()
        context.chain_env_path.return_value = tmp_path / ".env.gnosis"
        context.keys_dir = tmp_path / "keys"
        mock_get_context.return_value = context

        runner = CliRunner()
        result = runner.invoke(update_metadata, ["-c", "gnosis"])

        assert result.exit_code == 0
        mock_require_initialized.assert_called_once_with(context)
        context.chain_env_path.assert_called_once_with("gnosis")
        mock_update.assert_called_once_with(
            env_path=tmp_path / ".env.gnosis",
            private_key_path=context.keys_dir / "ethereum_private_key.txt",
        )

    def test_update_metadata_missing_chain_config(self) -> None:
        """Fail when required chain-config option is missing."""
        runner = CliRunner()
        result = runner.invoke(update_metadata, [])

        assert result.exit_code != 0

    def test_update_metadata_invalid_chain_config(self) -> None:
        """Fail when chain-config value is not a supported chain."""
        runner = CliRunner()
        result = runner.invoke(update_metadata, ["-c", "invalid_chain"])

        assert result.exit_code != 0

    def test_update_metadata_help(self) -> None:
        """Test update-metadata help output."""
        runner = CliRunner()
        result = runner.invoke(update_metadata, ["--help"])

        assert result.exit_code == 0
        assert "Update the metadata hash on-chain" in result.output
        assert "chain-config" in result.output
