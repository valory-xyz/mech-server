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
"""Tests for add-tool command."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from mtd.commands.add_tool_cmd import add_tool


MOCK_PATH = "mtd.commands.add_tool_cmd"


class TestAddToolCommand:
    """Tests for add-tool command."""

    @patch(f"{MOCK_PATH}.get_package_manager")
    @patch(f"{MOCK_PATH}.generate_tool")
    @patch(f"{MOCK_PATH}.require_initialized")
    @patch(f"{MOCK_PATH}.get_mtd_context")
    def test_add_tool_success(
        self,
        mock_get_context: MagicMock,
        mock_require_initialized: MagicMock,
        mock_generate: MagicMock,
        mock_pkg_manager: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test successful tool addition."""
        context = MagicMock()
        context.packages_dir = tmp_path / "packages"
        mock_get_context.return_value = context

        mock_manager_instance = MagicMock()
        mock_pkg_manager.return_value = mock_manager_instance
        mock_manager_instance.update_package_hashes.return_value = mock_manager_instance

        runner = CliRunner()
        result = runner.invoke(add_tool, ["myauthor", "mytool"])

        assert result.exit_code == 0
        mock_require_initialized.assert_called_once_with(context)
        mock_generate.assert_called_once_with(
            "myauthor", "mytool", "A mech tool.", context.packages_dir
        )

    @patch(f"{MOCK_PATH}.generate_tool")
    @patch(f"{MOCK_PATH}.require_initialized")
    @patch(f"{MOCK_PATH}.get_mtd_context")
    def test_add_tool_with_skip_lock(
        self,
        mock_get_context: MagicMock,
        mock_require_initialized: MagicMock,
        mock_generate: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test tool addition with --skip-lock."""
        context = MagicMock()
        context.packages_dir = tmp_path / "packages"
        mock_get_context.return_value = context

        runner = CliRunner()
        result = runner.invoke(add_tool, ["myauthor", "mytool", "--skip-lock"])

        assert result.exit_code == 0
        mock_require_initialized.assert_called_once_with(context)
        mock_generate.assert_called_once()

    @patch(f"{MOCK_PATH}.generate_tool")
    @patch(f"{MOCK_PATH}.require_initialized")
    @patch(f"{MOCK_PATH}.get_mtd_context")
    def test_add_tool_with_custom_packages_dir(
        self,
        mock_get_context: MagicMock,
        mock_require_initialized: MagicMock,
        mock_generate: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test add-tool with explicit --packages-dir override."""
        context = MagicMock()
        context.packages_dir = tmp_path / "ignored"
        mock_get_context.return_value = context

        custom_packages = tmp_path / "custom_packages"

        runner = CliRunner()
        result = runner.invoke(
            add_tool,
            [
                "myauthor",
                "mytool",
                "--skip-lock",
                "--packages-dir",
                str(custom_packages),
            ],
        )

        assert result.exit_code == 0
        mock_require_initialized.assert_called_once_with(context)
        mock_generate.assert_called_once_with(
            "myauthor", "mytool", "A mech tool.", custom_packages
        )
