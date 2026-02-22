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

from mtd.commands.run_cmd import (
    _get_latest_service_hash,
    _push_all_packages,
    _run_dev_mode,
    run,
)


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

    @patch(f"{MOCK_PATH}.require_initialized")
    @patch(f"{MOCK_PATH}.get_mtd_context")
    def test_run_raises_when_config_file_missing(
        self,
        mock_get_context: MagicMock,
        mock_require_initialized: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Raise ClickException when the chain config template file is absent."""
        context = MagicMock()
        context.config_dir = tmp_path / "config"
        context.config_dir.mkdir(parents=True)
        # config_mech_gnosis.json deliberately not created
        mock_get_context.return_value = context

        runner = CliRunner()
        result = runner.invoke(run, ["-c", "gnosis"])

        assert result.exit_code != 0


class TestPushAllPackages:
    """Tests for _push_all_packages."""

    def test_raises_when_packages_dir_missing(self, tmp_path: Path) -> None:
        """Raise ClickException when packages_dir does not exist."""
        context = MagicMock()
        context.packages_dir = tmp_path / "nonexistent"

        with pytest.raises(click.ClickException, match="Dev mode requires"):
            _push_all_packages(context=context)

    @patch(f"{MOCK_PATH}.subprocess.run")
    def test_runs_autonomy_push_all_when_packages_dir_exists(
        self, mock_subproc: MagicMock, tmp_path: Path
    ) -> None:
        """Run autonomy push-all when packages_dir exists."""
        context = MagicMock()
        context.packages_dir = tmp_path / "packages"
        context.packages_dir.mkdir()
        context.workspace_path = tmp_path

        _push_all_packages(context=context)

        mock_subproc.assert_called_once_with(
            ["autonomy", "push-all"],
            check=True,
            cwd=str(tmp_path),
        )


class TestRunDevMode:
    """Tests for _run_dev_mode."""

    @patch(f"{MOCK_PATH}.run_service")
    @patch(f"{MOCK_PATH}.OperateApp")
    @patch(f"{MOCK_PATH}._workspace_cwd")
    @patch(f"{MOCK_PATH}._get_latest_service_hash", return_value="bafynew")
    @patch(f"{MOCK_PATH}._push_all_packages")
    def test_updates_config_hash_and_runs_service(
        self,
        mock_push: MagicMock,
        mock_get_hash: MagicMock,
        mock_cwd: MagicMock,
        mock_operate: MagicMock,
        mock_run_service: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Update config hash with latest service hash and invoke run_service."""
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"hash": "old"}), encoding="utf-8")

        context = MagicMock()
        context.workspace_path = tmp_path
        context.operate_dir = tmp_path / "operate"

        _run_dev_mode(config_path=config_path, context=context)

        config = json.loads(config_path.read_text(encoding="utf-8"))
        assert config["hash"] == "bafynew"
        mock_push.assert_called_once_with(context=context)
        mock_run_service.assert_called_once()
