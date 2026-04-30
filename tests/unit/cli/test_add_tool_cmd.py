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

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner
from mtd.commands.add_tool_cmd import (
    INIT_FILENAME,
    _read_template,
    add_tool,
    generate_tool,
    generate_tool_file,
)

MOCK_PATH = "mtd.commands.add_tool_cmd"


class TestGenerateToolFile:
    """Direct tests for generate_tool_file template rendering."""

    def test_non_init_file_written_only_to_tool_path(self, tmp_path: Path) -> None:
        """Non-__init__ file is written once at tool_path/filename."""
        packages_dir = tmp_path / "packages"
        packages_dir.mkdir()
        tool_path = packages_dir / "author" / "customs" / "my_tool"
        tool_path.mkdir(parents=True)

        with patch(f"{MOCK_PATH}._read_template", return_value="tool: $tool_name"):
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
        packages_dir = tmp_path / "packages"
        author_dir = packages_dir / "author"
        customs_dir = author_dir / "customs"
        tool_path = customs_dir / "my_tool"
        tool_path.mkdir(parents=True)

        with patch(f"{MOCK_PATH}._read_template", return_value="# init"):
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
        packages_dir = tmp_path / "packages"
        packages_dir.mkdir()
        tool_path = packages_dir / "author" / "customs" / "tool"
        tool_path.mkdir(parents=True)

        with patch(
            f"{MOCK_PATH}._read_template",
            return_value="author: $authorname\nyear: $year",
        ):
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

    def test_generate_tool_calls_file_generator_for_each_template(
        self, tmp_path: Path
    ) -> None:
        """generate_tool delegates to generate_tool_file for every template."""
        packages_dir = tmp_path / "packages"

        with patch(f"{MOCK_PATH}.generate_tool_file") as mock_gen:
            generate_tool("alice", "mytool", "My tool description.", packages_dir)

        # init, config, and tool templates → 3 calls
        assert mock_gen.call_count == 3
        # Tool directory should have been created
        tool_path = packages_dir / "alice" / "customs" / "mytool"
        assert tool_path.is_dir()

    def test_read_template_uses_importlib_resources(self) -> None:
        """_read_template reads content via importlib.resources."""
        with patch(f"{MOCK_PATH}.resources") as mock_resources:
            mock_resources.files.return_value.joinpath.return_value.read_text.return_value = (
                "template content"
            )
            result = _read_template("tool.template")

        assert result == "template content"
        mock_resources.files.assert_called_once_with("mtd.templates")
        mock_resources.files.return_value.joinpath.assert_called_once_with(
            "tool.template"
        )


class TestScaffoldOutput:
    """Tests that verify the real scaffold generates correct, runnable tool code."""

    def test_scaffold_contains_allowed_tools(self, tmp_path: Path) -> None:
        """Generated tool file must define ALLOWED_TOOLS."""
        packages_dir = tmp_path / "packages"
        generate_tool("myauthor", "my_tool", "A test tool.", packages_dir)

        tool_py = packages_dir / "myauthor" / "customs" / "my_tool" / "my_tool.py"
        content = tool_py.read_text(encoding="utf-8")
        assert "ALLOWED_TOOLS" in content

    def test_scaffold_allowed_tools_matches_tool_name(self, tmp_path: Path) -> None:
        """ALLOWED_TOOLS in the generated file must contain the tool name."""
        packages_dir = tmp_path / "packages"
        generate_tool("myauthor", "my_tool", "A test tool.", packages_dir)

        tool_py = packages_dir / "myauthor" / "customs" / "my_tool" / "my_tool.py"
        spec = importlib.util.spec_from_file_location("my_tool", tool_py)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]

        assert hasattr(module, "ALLOWED_TOOLS")
        assert isinstance(module.ALLOWED_TOOLS, list)
        assert "my_tool" in module.ALLOWED_TOOLS

    def test_scaffold_run_returns_mech_response(self, tmp_path: Path) -> None:
        """Generated run() must return a 5-tuple with result and prompt."""
        packages_dir = tmp_path / "packages"
        generate_tool("myauthor", "my_tool", "A test tool.", packages_dir)

        tool_py = packages_dir / "myauthor" / "customs" / "my_tool" / "my_tool.py"
        spec = importlib.util.spec_from_file_location("my_tool", tool_py)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]

        result = module.run(prompt="test prompt")
        assert isinstance(result, tuple)
        assert len(result) == 5
        assert result[1] == "test prompt"

    def test_scaffold_run_handles_missing_prompt(self, tmp_path: Path) -> None:
        """Generated run() must return a 5-tuple error when prompt is missing."""
        packages_dir = tmp_path / "packages"
        generate_tool("myauthor", "my_tool", "A test tool.", packages_dir)

        tool_py = packages_dir / "myauthor" / "customs" / "my_tool" / "my_tool.py"
        spec = importlib.util.spec_from_file_location("my_tool", tool_py)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]

        result = module.run()
        assert isinstance(result, tuple)
        assert len(result) == 5
        assert isinstance(result[0], str)


class TestAddToolCommand:
    """Tests for add-tool command."""

    @patch(f"{MOCK_PATH}.get_package_manager")
    @patch(f"{MOCK_PATH}.require_initialized")
    @patch(f"{MOCK_PATH}.generate_tool")
    @patch(f"{MOCK_PATH}.get_mtd_context")
    def test_add_tool_success(
        self,
        mock_get_context: MagicMock,
        mock_generate: MagicMock,
        mock_require_initialized: MagicMock,
        mock_pkg_manager: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test successful tool addition with lock."""
        context = MagicMock()
        context.packages_dir = tmp_path / "packages"
        context.packages_dir.mkdir(parents=True)
        (context.packages_dir / "packages.json").write_text("{}", encoding="utf-8")
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
        mock_pkg_manager.assert_called_once()

    @patch(f"{MOCK_PATH}.require_initialized")
    @patch(f"{MOCK_PATH}.generate_tool")
    @patch(f"{MOCK_PATH}.get_mtd_context")
    def test_add_tool_with_skip_lock(
        self,
        mock_get_context: MagicMock,
        mock_generate: MagicMock,
        mock_require_initialized: MagicMock,
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

    @patch(f"{MOCK_PATH}.require_initialized")
    @patch(f"{MOCK_PATH}.generate_tool")
    @patch(f"{MOCK_PATH}.get_mtd_context")
    def test_add_tool_with_custom_packages_dir(
        self,
        mock_get_context: MagicMock,
        mock_generate: MagicMock,
        mock_require_initialized: MagicMock,
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
