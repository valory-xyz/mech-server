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
"""Tests for prepare-metadata command."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from mtd.commands.prepare_metadata_cmd import (
    _compute_tools_to_package_hash,
    _lock_packages,
    _push_all_packages,
    _resolve_offchain_url,
    _update_chain_config,
    prepare_metadata,
)


MOCK_PATH = "mtd.commands.prepare_metadata_cmd"


class TestPrepareMetadataCommand:
    """Tests for prepare-metadata command."""

    @patch(f"{MOCK_PATH}._update_chain_config")
    @patch(f"{MOCK_PATH}._compute_tools_to_package_hash", return_value="")
    @patch(f"{MOCK_PATH}.set_key")
    @patch(f"{MOCK_PATH}.publish_metadata_to_ipfs", return_value="f0170abc")
    @patch(f"{MOCK_PATH}.generate_metadata")
    @patch(f"{MOCK_PATH}._push_all_packages")
    @patch(f"{MOCK_PATH}._lock_packages")
    @patch(f"{MOCK_PATH}.require_initialized")
    @patch(f"{MOCK_PATH}.get_mtd_context")
    def test_prepare_metadata_success_with_chain(
        self,
        mock_get_context: MagicMock,
        mock_require_initialized: MagicMock,
        mock_lock_packages: MagicMock,
        mock_push_all: MagicMock,
        mock_generate: MagicMock,
        mock_publish: MagicMock,
        mock_set_key: MagicMock,
        mock_compute_tools: MagicMock,
        mock_update_cfg: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test successful prepare-metadata with explicit chain flag."""
        context = MagicMock()
        context.packages_dir = tmp_path / "packages"
        context.workspace_path = tmp_path
        context.metadata_path = tmp_path / "metadata.json"
        env_path = tmp_path / ".env.gnosis"
        context.chain_env_path.return_value = env_path
        mock_get_context.return_value = context

        runner = CliRunner()
        result = runner.invoke(prepare_metadata, ["-c", "gnosis"])

        assert result.exit_code == 0
        mock_require_initialized.assert_called_once_with(context)
        mock_lock_packages.assert_called_once_with(context.packages_dir)
        mock_push_all.assert_called_once_with(
            context.workspace_path, context.packages_dir
        )
        mock_generate.assert_called_once_with(
            packages_dir=context.packages_dir,
            metadata_path=context.metadata_path,
            offchain_url="",
        )
        mock_publish.assert_called_once()
        mock_set_key.assert_called_once_with(str(env_path), "METADATA_HASH", "f0170abc")
        mock_compute_tools.assert_called_once_with(
            context.packages_dir, context.metadata_path
        )
        expected = {"METADATA_HASH": "f0170abc"}
        mock_update_cfg.assert_called_once_with(context, "gnosis", expected)

    @patch(f"{MOCK_PATH}._update_chain_config")
    @patch(
        f"{MOCK_PATH}._compute_tools_to_package_hash",
        return_value='{"openai-gpt-4":"bafyabc","custom-search":"bafydef"}',
    )
    @patch(f"{MOCK_PATH}.set_key")
    @patch(f"{MOCK_PATH}.publish_metadata_to_ipfs", return_value="f0170abc")
    @patch(f"{MOCK_PATH}.generate_metadata")
    @patch(f"{MOCK_PATH}._push_all_packages")
    @patch(f"{MOCK_PATH}._lock_packages")
    @patch(f"{MOCK_PATH}.require_initialized")
    @patch(f"{MOCK_PATH}.get_mtd_context")
    def test_prepare_metadata_writes_tools_to_package_hash(
        self,
        mock_get_context: MagicMock,
        mock_require_initialized: MagicMock,
        mock_lock_packages: MagicMock,
        mock_push_all: MagicMock,
        mock_generate: MagicMock,
        mock_publish: MagicMock,
        mock_set_key: MagicMock,
        mock_compute_tools: MagicMock,
        mock_update_cfg: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Write TOOLS_TO_PACKAGE_HASH to chain .env when tools mapping is non-empty."""
        context = MagicMock()
        context.packages_dir = tmp_path / "packages"
        context.workspace_path = tmp_path
        context.metadata_path = tmp_path / "metadata.json"
        context.chain_env_path.return_value = tmp_path / ".env.gnosis"
        mock_get_context.return_value = context

        runner = CliRunner()
        result = runner.invoke(prepare_metadata, ["-c", "gnosis"])

        assert result.exit_code == 0
        mock_set_key.assert_any_call(
            str(tmp_path / ".env.gnosis"), "METADATA_HASH", "f0170abc"
        )
        mock_set_key.assert_any_call(
            str(tmp_path / ".env.gnosis"),
            "TOOLS_TO_PACKAGE_HASH",
            '{"openai-gpt-4":"bafyabc","custom-search":"bafydef"}',
        )
        assert mock_set_key.call_count == 2
        mock_update_cfg.assert_called_once_with(
            context,
            "gnosis",
            {
                "METADATA_HASH": "f0170abc",
                "TOOLS_TO_PACKAGE_HASH": '{"openai-gpt-4":"bafyabc",'
                '"custom-search":"bafydef"}',
            },
        )

    @patch(f"{MOCK_PATH}._compute_tools_to_package_hash", return_value="")
    @patch(f"{MOCK_PATH}.set_key")
    @patch(f"{MOCK_PATH}.publish_metadata_to_ipfs", return_value="f0170abc")
    @patch(f"{MOCK_PATH}.generate_metadata")
    @patch(f"{MOCK_PATH}._push_all_packages")
    @patch(f"{MOCK_PATH}._lock_packages")
    @patch(f"{MOCK_PATH}.require_initialized")
    @patch(f"{MOCK_PATH}.get_mtd_context")
    def test_prepare_metadata_updates_all_existing_chain_envs(
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
        """Update METADATA_HASH in all existing chain env files when no -c given."""
        context = MagicMock()
        context.packages_dir = tmp_path / "packages"
        context.workspace_path = tmp_path
        context.metadata_path = tmp_path / "metadata.json"

        gnosis_env = tmp_path / ".env.gnosis"
        base_env = tmp_path / ".env.base"
        gnosis_env.touch()
        base_env.touch()

        def _chain_env_path(chain: str) -> Path:
            return tmp_path / f".env.{chain}"

        context.chain_env_path.side_effect = _chain_env_path
        mock_get_context.return_value = context

        runner = CliRunner()
        result = runner.invoke(prepare_metadata, [])

        assert result.exit_code == 0
        mock_set_key.assert_any_call(str(gnosis_env), "METADATA_HASH", "f0170abc")
        mock_set_key.assert_any_call(str(base_env), "METADATA_HASH", "f0170abc")

    @patch(f"{MOCK_PATH}._compute_tools_to_package_hash", return_value="")
    @patch(f"{MOCK_PATH}.set_key")
    @patch(f"{MOCK_PATH}.publish_metadata_to_ipfs", return_value="f0170abc")
    @patch(f"{MOCK_PATH}.generate_metadata")
    @patch(f"{MOCK_PATH}._push_all_packages")
    @patch(f"{MOCK_PATH}._lock_packages")
    @patch(f"{MOCK_PATH}.require_initialized")
    @patch(f"{MOCK_PATH}.get_mtd_context")
    def test_prepare_metadata_no_chain_files_still_succeeds(
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
        """Succeed without updating any env files when none exist and no -c given."""
        context = MagicMock()
        context.packages_dir = tmp_path / "packages"
        context.workspace_path = tmp_path
        context.metadata_path = tmp_path / "metadata.json"

        def _chain_env_path(chain: str) -> Path:
            return tmp_path / f".env.{chain}"

        context.chain_env_path.side_effect = _chain_env_path
        mock_get_context.return_value = context

        runner = CliRunner()
        result = runner.invoke(prepare_metadata, [])

        assert result.exit_code == 0
        mock_set_key.assert_not_called()

    @patch(f"{MOCK_PATH}._update_chain_config")
    @patch(f"{MOCK_PATH}._compute_tools_to_package_hash", return_value="")
    @patch(f"{MOCK_PATH}.set_key")
    @patch(f"{MOCK_PATH}.publish_metadata_to_ipfs", return_value="f0170abc")
    @patch(f"{MOCK_PATH}.generate_metadata")
    @patch(f"{MOCK_PATH}._push_all_packages")
    @patch(f"{MOCK_PATH}._lock_packages")
    @patch(f"{MOCK_PATH}.require_initialized")
    @patch(f"{MOCK_PATH}.get_mtd_context")
    def test_prepare_metadata_with_explicit_offchain_url(
        self,
        mock_get_context: MagicMock,
        mock_require_initialized: MagicMock,
        mock_lock_packages: MagicMock,
        mock_push_all: MagicMock,
        mock_generate: MagicMock,
        mock_publish: MagicMock,
        mock_set_key: MagicMock,
        mock_compute_tools: MagicMock,
        mock_update_cfg: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Pass --offchain-url to generate and persist to .env."""
        context = MagicMock()
        context.packages_dir = tmp_path / "packages"
        context.workspace_path = tmp_path
        context.metadata_path = tmp_path / "metadata.json"
        env_path = tmp_path / ".env.gnosis"
        context.chain_env_path.return_value = env_path
        mock_get_context.return_value = context

        runner = CliRunner()
        result = runner.invoke(
            prepare_metadata,
            ["-c", "gnosis", "--offchain-url", "https://mech.example.com/"],
        )

        assert result.exit_code == 0
        mock_generate.assert_called_once_with(
            packages_dir=context.packages_dir,
            metadata_path=context.metadata_path,
            offchain_url="https://mech.example.com/",
        )
        mock_set_key.assert_any_call(
            str(env_path), "MECH_OFFCHAIN_URL", "https://mech.example.com/"
        )
        mock_update_cfg.assert_called_once_with(
            context,
            "gnosis",
            {"METADATA_HASH": "f0170abc"},
        )

    @patch(f"{MOCK_PATH}._update_chain_config")
    @patch(f"{MOCK_PATH}._compute_tools_to_package_hash", return_value="")
    @patch(f"{MOCK_PATH}.set_key")
    @patch(f"{MOCK_PATH}.publish_metadata_to_ipfs", return_value="f0170abc")
    @patch(f"{MOCK_PATH}.generate_metadata")
    @patch(f"{MOCK_PATH}._push_all_packages")
    @patch(f"{MOCK_PATH}._lock_packages")
    @patch(f"{MOCK_PATH}.require_initialized")
    @patch(f"{MOCK_PATH}.get_mtd_context")
    def test_prepare_metadata_reads_url_from_env(
        self,
        mock_get_context: MagicMock,
        mock_require_initialized: MagicMock,
        mock_lock_packages: MagicMock,
        mock_push_all: MagicMock,
        mock_generate: MagicMock,
        mock_publish: MagicMock,
        mock_set_key: MagicMock,
        mock_compute_tools: MagicMock,
        mock_update_cfg: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Read MECH_OFFCHAIN_URL from chain .env when --offchain-url not given."""
        context = MagicMock()
        context.packages_dir = tmp_path / "packages"
        context.workspace_path = tmp_path
        context.metadata_path = tmp_path / "metadata.json"
        env_path = tmp_path / ".env.gnosis"
        env_path.write_text(
            "MECH_OFFCHAIN_URL=https://stored.example.com/\n",
            encoding="utf-8",
        )
        context.chain_env_path.return_value = env_path
        mock_get_context.return_value = context

        runner = CliRunner()
        result = runner.invoke(prepare_metadata, ["-c", "gnosis"])

        assert result.exit_code == 0
        mock_generate.assert_called_once_with(
            packages_dir=context.packages_dir,
            metadata_path=context.metadata_path,
            offchain_url="https://stored.example.com/",
        )


class TestUpdateChainConfig:
    """Tests for _update_chain_config."""

    def test_updates_env_vars_in_config_json(self, tmp_path: Path) -> None:
        """Write updated values into the chain config template JSON."""
        context = MagicMock()
        context.config_dir = tmp_path
        config = {
            "env_variables": {
                "METADATA_HASH": {"value": "old_hash", "provision_type": "fixed"},
                "TOOLS_TO_PACKAGE_HASH": {"value": "{}", "provision_type": "fixed"},
            }
        }
        config_path = tmp_path / "config_mech_gnosis.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")

        _update_chain_config(
            context,
            "gnosis",
            {"METADATA_HASH": "new_hash", "TOOLS_TO_PACKAGE_HASH": '{"a":"b"}'},
        )

        result = json.loads(config_path.read_text(encoding="utf-8"))
        assert result["env_variables"]["METADATA_HASH"]["value"] == "new_hash"
        assert result["env_variables"]["TOOLS_TO_PACKAGE_HASH"]["value"] == '{"a":"b"}'

    def test_skips_when_config_missing(self, tmp_path: Path) -> None:
        """Do nothing when the chain config file does not exist."""
        context = MagicMock()
        context.config_dir = tmp_path

        _update_chain_config(context, "gnosis", {"METADATA_HASH": "new"})

    def test_skips_unknown_keys(self, tmp_path: Path) -> None:
        """Ignore keys not present in the config."""
        context = MagicMock()
        context.config_dir = tmp_path
        config = {
            "env_variables": {
                "METADATA_HASH": {"value": "old", "provision_type": "fixed"},
            }
        }
        config_path = tmp_path / "config_mech_gnosis.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")

        _update_chain_config(
            context, "gnosis", {"METADATA_HASH": "new", "UNKNOWN": "ignored"}
        )

        result = json.loads(config_path.read_text(encoding="utf-8"))
        assert result["env_variables"]["METADATA_HASH"]["value"] == "new"
        assert "UNKNOWN" not in result["env_variables"]

    def test_no_write_when_values_unchanged(self, tmp_path: Path) -> None:
        """Do not rewrite the file when all values already match."""
        context = MagicMock()
        context.config_dir = tmp_path
        config = {
            "env_variables": {
                "METADATA_HASH": {"value": "same", "provision_type": "fixed"},
            }
        }
        config_path = tmp_path / "config_mech_gnosis.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        mtime_before = config_path.stat().st_mtime

        _update_chain_config(context, "gnosis", {"METADATA_HASH": "same"})

        assert config_path.stat().st_mtime == mtime_before


class TestResolveOffchainUrl:
    """Tests for _resolve_offchain_url."""

    def test_explicit_url_takes_precedence(self, tmp_path: Path) -> None:
        """Return explicit URL when provided."""
        context = MagicMock()
        result = _resolve_offchain_url("https://explicit.com/", context, "gnosis")
        assert result == "https://explicit.com/"

    def test_reads_from_env_file(self, tmp_path: Path) -> None:
        """Read MECH_OFFCHAIN_URL from chain .env file."""
        context = MagicMock()
        env_path = tmp_path / ".env.gnosis"
        env_path.write_text(
            "MECH_OFFCHAIN_URL=https://from-env.com/\n", encoding="utf-8"
        )
        context.chain_env_path.return_value = env_path

        result = _resolve_offchain_url(None, context, "gnosis")
        assert result == "https://from-env.com/"

    def test_returns_empty_when_no_chain(self) -> None:
        """Return empty string when chain_config is None."""
        context = MagicMock()
        result = _resolve_offchain_url(None, context, None)
        assert result == ""

    def test_returns_empty_when_env_file_missing(self, tmp_path: Path) -> None:
        """Return empty string when chain .env does not exist."""
        context = MagicMock()
        context.chain_env_path.return_value = tmp_path / ".env.gnosis"

        result = _resolve_offchain_url(None, context, "gnosis")
        assert result == ""

    def test_returns_empty_when_env_var_absent(self, tmp_path: Path) -> None:
        """Return empty string when MECH_OFFCHAIN_URL not in .env."""
        context = MagicMock()
        env_path = tmp_path / ".env.gnosis"
        env_path.write_text("OTHER_VAR=something\n", encoding="utf-8")
        context.chain_env_path.return_value = env_path

        result = _resolve_offchain_url(None, context, "gnosis")
        assert result == ""


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

    @staticmethod
    def _write_metadata(tmp_path: Path, tool_metadata: dict) -> Path:
        """Write a metadata.json with the given toolMetadata section."""
        metadata = {"tools": list(tool_metadata.keys()), "toolMetadata": tool_metadata}
        metadata_path = tmp_path / "metadata.json"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
        return metadata_path

    def test_happy_path_maps_model_names(self, tmp_path: Path) -> None:
        """Map each model name from toolMetadata to the tool IPFS hash."""
        packages_json = {
            "dev": {
                "custom/valory/echo/0.1.0": "bafybeiabc",
                "custom/valory/mytool/0.1.0": "bafybeidef",
            }
        }
        (tmp_path / "packages.json").write_text(
            json.dumps(packages_json), encoding="utf-8"
        )
        metadata_path = self._write_metadata(
            tmp_path,
            {
                "openai-gpt-4": {"name": "echo"},
                "openai-gpt-3.5": {"name": "echo"},
                "custom-search": {"name": "mytool"},
            },
        )

        result = _compute_tools_to_package_hash(tmp_path, metadata_path)
        parsed = json.loads(result)

        assert parsed == {
            "openai-gpt-4": "bafybeiabc",
            "openai-gpt-3.5": "bafybeiabc",
            "custom-search": "bafybeidef",
        }

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
        metadata_path = self._write_metadata(
            tmp_path, {"openai-gpt-4": {"name": "echo"}}
        )

        result = _compute_tools_to_package_hash(tmp_path, metadata_path)
        parsed = json.loads(result)

        assert parsed == {"openai-gpt-4": "bafybeiabc"}

    def test_missing_packages_json(self, tmp_path: Path) -> None:
        """Return empty string when packages.json does not exist."""
        metadata_path = tmp_path / "metadata.json"

        result = _compute_tools_to_package_hash(tmp_path, metadata_path)

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
        metadata_path = tmp_path / "metadata.json"

        result = _compute_tools_to_package_hash(tmp_path, metadata_path)

        assert result == ""

    def test_empty_dev_section(self, tmp_path: Path) -> None:
        """Return empty string when dev section is empty."""
        packages_json: dict = {"dev": {}}
        (tmp_path / "packages.json").write_text(
            json.dumps(packages_json), encoding="utf-8"
        )
        metadata_path = tmp_path / "metadata.json"

        result = _compute_tools_to_package_hash(tmp_path, metadata_path)

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
        metadata_path = self._write_metadata(
            tmp_path, {"openai-gpt-4": {"name": "echo"}}
        )

        result = _compute_tools_to_package_hash(tmp_path, metadata_path)
        parsed = json.loads(result)

        assert parsed == {"openai-gpt-4": "bafybeiabc"}

    def test_invalid_packages_json(self, tmp_path: Path) -> None:
        """Return empty string when packages.json contains invalid JSON."""
        (tmp_path / "packages.json").write_text("not valid json{{{", encoding="utf-8")
        metadata_path = tmp_path / "metadata.json"

        result = _compute_tools_to_package_hash(tmp_path, metadata_path)

        assert result == ""

    def test_missing_metadata_json(self, tmp_path: Path) -> None:
        """Return empty string when metadata.json does not exist."""
        packages_json = {"dev": {"custom/valory/echo/0.1.0": "bafybeiabc"}}
        (tmp_path / "packages.json").write_text(
            json.dumps(packages_json), encoding="utf-8"
        )
        metadata_path = tmp_path / "metadata.json"

        result = _compute_tools_to_package_hash(tmp_path, metadata_path)

        assert result == ""

    def test_invalid_metadata_json(self, tmp_path: Path) -> None:
        """Return empty string when metadata.json contains invalid JSON."""
        packages_json = {"dev": {"custom/valory/echo/0.1.0": "bafybeiabc"}}
        (tmp_path / "packages.json").write_text(
            json.dumps(packages_json), encoding="utf-8"
        )
        metadata_path = tmp_path / "metadata.json"
        metadata_path.write_text("not valid json{{{", encoding="utf-8")

        result = _compute_tools_to_package_hash(tmp_path, metadata_path)

        assert result == ""

    def test_model_without_matching_package(self, tmp_path: Path) -> None:
        """Skip model names whose tool name has no entry in packages.json."""
        packages_json = {"dev": {"custom/valory/echo/0.1.0": "bafybeiabc"}}
        (tmp_path / "packages.json").write_text(
            json.dumps(packages_json), encoding="utf-8"
        )
        metadata_path = self._write_metadata(
            tmp_path,
            {
                "openai-gpt-4": {"name": "echo"},
                "unknown-model": {"name": "nonexistent"},
            },
        )

        result = _compute_tools_to_package_hash(tmp_path, metadata_path)
        parsed = json.loads(result)

        assert parsed == {"openai-gpt-4": "bafybeiabc"}
