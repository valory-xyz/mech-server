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
"""Tests for the CLI entry point."""

from click.testing import CliRunner
from mtd.cli import cli


def test_cli_group_callback_executes_on_subcommand() -> None:
    """Group callback should build mtd_context when a subcommand is invoked."""
    runner = CliRunner()
    result = runner.invoke(cli, ["setup", "--help"])
    assert result.exit_code == 0


class TestCli:
    """Tests for the CLI group."""

    def test_help(self) -> None:
        """Test CLI help output lists all commands."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "init" not in result.output
        assert "deploy-mech" not in result.output
        assert "add-tool" in result.output
        assert "setup" in result.output
        assert "run" in result.output
        assert "stop" in result.output
        assert "prepare-metadata" in result.output
        assert "update-metadata" in result.output

    def test_no_workspace_option(self) -> None:
        """CLI help should not expose workspace override option."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "--workspace" not in result.output

    def test_no_command(self) -> None:
        """Test CLI with no subcommand shows help."""
        runner = CliRunner()
        result = runner.invoke(cli, [])

        assert result.exit_code == 0
        assert "Usage" in result.output

    def test_invalid_command(self) -> None:
        """Test CLI with unknown command."""
        runner = CliRunner()
        result = runner.invoke(cli, ["nonexistent"])

        assert result.exit_code != 0
