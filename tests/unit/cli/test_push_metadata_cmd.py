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
"""Tests for push-metadata command."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from mtd.commands.push_metadata_cmd import (
    _compute_tools_to_package_hash,
    _lock_packages,
    _push_all_packages,
    push_metadata,
)


MOCK_PATH = "mtd.commands.push_metadata_cmd"


class TestPushMetadataCommand:
    """Tests for push-metadata command."""

    @patch(f"{MOCK_PATH}._compute_tools_to_package_hash", return_value="")
    @patch(f"{MOCK_PATH}.set_key")
    @patch(f"{MOCK_PATH}.publish_metadata_to_ipfs", return_value="f0170abc")
    @patch(f"{MOCK_PATH}.generate_metadata")
    @patch(f"{MOCK_PATH}._push_all_packages")
    @patch(f"{MOCK_PATH}._lock_packages")
    @patch(f"{MOCK_PATH}.require_initialized")
    @patch(f"{MOCK_PATH}.get_mtd_context")
    def test_push_metadata_success(
        self,
        mock_get_context: MagicMock,
        mock_require_initialized: MagicMock,
        mock_lock_packages: MagicMock,
        mock_push_all: MagicMock,
        mock_generate: MagicMock,
        mock_publish: MagicMock,
        mock_set_key: MagicMock,
        mock_compute_tools: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test successful push-metadata."""
        context = MagicMock()
        context.packages_dir = tmp_path / "packages"
        context.workspace_path = tmp_path
        context.metadata_path = tmp_path / "metadata.json"
        context.env_path = tmp_path / ".env"
        mock_get_context.return_value = context

        runner = CliRunner()
        result = runner.invoke(push_metadata, [])

        assert result.exit_code == 0
        mock_require_initialized.assert_called_once_with(context)
        mock_lock_packages.assert_called_once_with(context.packages_dir)
        mock_push_all.assert_called_once_with(
            context.workspace_path, context.packages_dir
        )
        mock_generate.assert_called_once_with(
            packages_dir=context.packages_dir,
            metadata_path=context.metadata_path,
        )
        mock_publish.assert_called_once()
        mock_set_key.assert_called_once_with(
            str(context.env_path), "METADATA_HASH", "f0170abc"
        )
        mock_compute_tools.assert_called_once_with(context.packages_dir)

    @patch(
        f"{MOCK_PATH}._compute_tools_to_package_hash",
        return_value='{"echo":"bafyabc","mytool":"bafydef"}',
    )
    @patch(f"{MOCK_PATH}.set_key")
    @patch(f"{MOCK_PATH}.publish_metadata_to_ipfs", return_value="f0170abc")
    @patch(f"{MOCK_PATH}.generate_metadata")
    @patch(f"{MOCK_PATH}._push_all_packages")
    @patch(f"{MOCK_PATH}._lock_packages")
    @patch(f"{MOCK_PATH}.require_initialized")
    @patch(f"{MOCK_PATH}.get_mtd_context")
    def test_push_metadata_writes_tools_to_package_hash(
        self,
        mock_get_context: MagicMock,
        mock_require_initialized: MagicMock,
        mock_lock_packages: MagicMock,
        mock_push_all: MagicMock,
        mock_generate: MagicMock,
        mock_publish: MagicMock,
        mock_set_key: MagicMock,
        mock_compute_tools: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Write TOOLS_TO_PACKAGE_HASH to .env when tools mapping is non-empty."""
        context = MagicMock()
        context.packages_dir = tmp_path / "packages"
        context.workspace_path = tmp_path
        context.metadata_path = tmp_path / "metadata.json"
        context.env_path = tmp_path / ".env"
        mock_get_context.return_value = context

        runner = CliRunner()
        result = runner.invoke(push_metadata, [])

        assert result.exit_code == 0
        mock_set_key.assert_any_call(str(context.env_path), "METADATA_HASH", "f0170abc")
        mock_set_key.assert_any_call(
            str(context.env_path),
            "TOOLS_TO_PACKAGE_HASH",
            '{"echo":"bafyabc","mytool":"bafydef"}',
        )
        assert mock_set_key.call_count == 2


class TestLockPackages:
    """Tests for _lock_packages."""

    @patch(f"{MOCK_PATH}.get_package_manager")
    def test_lock_packages_calls_update_and_dump(
        self,
        mock_get_pm: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Call update_package_hashes and dump on the package manager."""
        (tmp_path / "packages.json").write_text("{}", encoding="utf-8")
        mock_pm = MagicMock()
        mock_pm.update_package_hashes.return_value = mock_pm
        mock_get_pm.return_value = mock_pm

        _lock_packages(tmp_path)

        mock_get_pm.assert_called_once_with(tmp_path)
        mock_pm.update_package_hashes.assert_called_once()
        mock_pm.dump.assert_called_once()

    @patch(f"{MOCK_PATH}.get_package_manager")
    def test_lock_packages_skips_when_no_packages_json(
        self,
        mock_get_pm: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Skip locking when packages.json does not exist."""
        _lock_packages(tmp_path)

        mock_get_pm.assert_not_called()


class TestPushAllPackages:
    """Tests for _push_all_packages."""

    @patch(f"{MOCK_PATH}.subprocess.run")
    def test_push_all_packages_runs_autonomy_push_all(
        self,
        mock_run: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Run autonomy push-all in the workspace directory."""
        packages_dir = tmp_path / "packages"
        packages_dir.mkdir()
        (packages_dir / "packages.json").write_text("{}", encoding="utf-8")

        _push_all_packages(tmp_path, packages_dir)

        mock_run.assert_called_once_with(
            ["autonomy", "push-all"],
            check=True,
            cwd=str(tmp_path),
        )

    @patch(f"{MOCK_PATH}.subprocess.run")
    def test_push_all_packages_skips_when_no_packages_json(
        self,
        mock_run: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Skip push when packages.json does not exist."""
        packages_dir = tmp_path / "packages"
        packages_dir.mkdir()

        _push_all_packages(tmp_path, packages_dir)

        mock_run.assert_not_called()


class TestComputeToolsToPackageHash:
    """Tests for _compute_tools_to_package_hash."""

    def test_happy_path_two_custom_tools(self, tmp_path: Path) -> None:
        """Return JSON mapping for two custom tool entries."""
        packages_json = {
            "dev": {
                "custom/valory/echo/0.1.0": "bafybeiabc",
                "custom/valory/mytool/0.1.0": "bafybeidef",
            }
        }
        (tmp_path / "packages.json").write_text(
            json.dumps(packages_json), encoding="utf-8"
        )

        result = _compute_tools_to_package_hash(tmp_path)
        parsed = json.loads(result)

        assert parsed == {"echo": "bafybeiabc", "mytool": "bafybeidef"}

    def test_skips_non_custom_entries(self, tmp_path: Path) -> None:
        """Exclude agent and service entries from the mapping."""
        packages_json = {
            "dev": {
                "custom/valory/echo/0.1.0": "bafybeiabc",
                "agent/valory/mech/0.1.0": "bafybeiagent",
                "service/valory/mech/0.1.0": "bafybeiservice",
            }
        }
        (tmp_path / "packages.json").write_text(
            json.dumps(packages_json), encoding="utf-8"
        )

        result = _compute_tools_to_package_hash(tmp_path)
        parsed = json.loads(result)

        assert parsed == {"echo": "bafybeiabc"}

    def test_missing_packages_json(self, tmp_path: Path) -> None:
        """Return empty string when packages.json does not exist."""
        result = _compute_tools_to_package_hash(tmp_path)

        assert result == ""

    def test_no_custom_tools(self, tmp_path: Path) -> None:
        """Return empty string when dev section has only non-custom entries."""
        packages_json = {
            "dev": {
                "agent/valory/mech/0.1.0": "bafybeiagent",
            }
        }
        (tmp_path / "packages.json").write_text(
            json.dumps(packages_json), encoding="utf-8"
        )

        result = _compute_tools_to_package_hash(tmp_path)

        assert result == ""

    def test_empty_dev_section(self, tmp_path: Path) -> None:
        """Return empty string when dev section is empty."""
        packages_json: dict = {"dev": {}}
        (tmp_path / "packages.json").write_text(
            json.dumps(packages_json), encoding="utf-8"
        )

        result = _compute_tools_to_package_hash(tmp_path)

        assert result == ""

    def test_malformed_key_skipped(self, tmp_path: Path) -> None:
        """Skip entries with fewer than 4 path segments."""
        packages_json = {
            "dev": {
                "custom/echo": "bafybeibroken",
                "custom/valory/echo/0.1.0": "bafybeiabc",
            }
        }
        (tmp_path / "packages.json").write_text(
            json.dumps(packages_json), encoding="utf-8"
        )

        result = _compute_tools_to_package_hash(tmp_path)
        parsed = json.loads(result)

        assert parsed == {"echo": "bafybeiabc"}

    def test_invalid_json(self, tmp_path: Path) -> None:
        """Return empty string when packages.json contains invalid JSON."""
        (tmp_path / "packages.json").write_text("not valid json{{{", encoding="utf-8")

        result = _compute_tools_to_package_hash(tmp_path)

        assert result == ""
