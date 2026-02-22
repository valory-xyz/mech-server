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

from mtd.commands.add_tool_cmd import INIT_FILENAME, add_tool, generate_tool_file


MOCK_PATH = "mtd.commands.add_tool_cmd"


class TestGenerateToolFile:
    """Direct tests for generate_tool_file template rendering."""

    def test_non_init_file_written_only_to_tool_path(self, tmp_path: Path) -> None:
        """Non-__init__ file is written once at tool_path/filename."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        (template_dir / "tool.template").write_text(
            "tool: $tool_name", encoding="utf-8"
        )

        packages_dir = tmp_path / "packages"
        packages_dir.mkdir()
        tool_path = packages_dir / "author" / "customs" / "my_tool"
        tool_path.mkdir(parents=True)

        with patch(f"{MOCK_PATH}.TEMPLATES_PATH", template_dir):
            generate_tool_file(
                "tool.template",
                {"tool_name": "my_tool"},
                "my_tool.py",
                tool_path,
                packages_dir,
            )

        assert (tool_path / "my_tool.py").read_text(encoding="utf-8") == "tool: my_tool"
        # parent dirs should NOT have my_tool.py
        assert not (tool_path.parent / "my_tool.py").exists()

    def test_init_file_cascades_up_to_packages_dir(self, tmp_path: Path) -> None:
        """__init__.py is written at tool_path and every ancestor up to packages_dir."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        (template_dir / "init.template").write_text("# init", encoding="utf-8")

        packages_dir = tmp_path / "packages"
        author_dir = packages_dir / "author"
        customs_dir = author_dir / "customs"
        tool_path = customs_dir / "my_tool"
        tool_path.mkdir(parents=True)

        with patch(f"{MOCK_PATH}.TEMPLATES_PATH", template_dir):
            generate_tool_file(
                "init.template",
                {},
                INIT_FILENAME,
                tool_path,
                packages_dir,
            )

        # Written at each level up to (but not including) packages_dir
        assert (tool_path / INIT_FILENAME).exists()
        assert (customs_dir / INIT_FILENAME).exists()
        assert (author_dir / INIT_FILENAME).exists()
        assert not (packages_dir / INIT_FILENAME).exists()

    def test_template_substitution_applied(self, tmp_path: Path) -> None:
        """Template variables are substituted in the output."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        (template_dir / "config.template").write_text(
            "author: $authorname\nyear: $year", encoding="utf-8"
        )
        packages_dir = tmp_path / "packages"
        packages_dir.mkdir()
        tool_path = packages_dir / "author" / "customs" / "tool"
        tool_path.mkdir(parents=True)

        with patch(f"{MOCK_PATH}.TEMPLATES_PATH", template_dir):
            generate_tool_file(
                "config.template",
                {"authorname": "valory", "year": "2026"},
                "component.yaml",
                tool_path,
                packages_dir,
            )

        content = (tool_path / "component.yaml").read_text(encoding="utf-8")
        assert "author: valory" in content
        assert "year: 2026" in content


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
