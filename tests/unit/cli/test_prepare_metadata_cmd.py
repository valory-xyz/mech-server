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

# Stacked `@patch` decorators inject MagicMocks as positional args; not every
# patch is directly asserted on, but each is required to neutralize a side
# effect during the test.
# pylint: disable=unused-argument

import json
from contextlib import ExitStack, contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Iterator, List
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner
from mtd.commands.prepare_metadata_cmd import (
    _build_benchmarks,
    _build_operator,
    _clean_packages_dir,
    _compute_tools_to_package_hash,
    _lock_packages,
    _push_all_packages,
    _resolve_offchain_url,
    _update_chain_config,
    prepare_metadata,
)
from mtd.services.metadata import Benchmark, Operator

MOCK_PATH = "mtd.commands.prepare_metadata_cmd"
MECH_NAME = "Test Mech"
NAME_ARGS = ["--name", MECH_NAME]
BENCHMARK_URL = "https://analytics.example/v1/metrics/mech/100/0xabc"
OPERATOR_ARGS = ["--operator-name", "Valory", "--operator-domain", "valory.xyz"]
BENCHMARK_ARGS = [
    "--benchmark-url",
    BENCHMARK_URL,
    "--benchmark",
    "openai-gpt-4",
    "accuracy",
    "0.83",
    "30d",
]
# Pipeline steps that touch the filesystem, IPFS or the chain; stubbed in
# every command-level test so only argument handling runs for real.
PIPELINE_STEPS = (
    "get_mtd_context",
    "require_initialized",
    "_lock_packages",
    "_push_all_packages",
    "generate_metadata",
    "publish_metadata_to_ipfs",
    "set_key",
    "_compute_tools_to_package_hash",
    "_update_chain_config",
)


@contextmanager
def _patched_pipeline(tmp_path: Path) -> Iterator[SimpleNamespace]:
    """Stub every pipeline step and yield the mocks by name, without the leading underscore."""
    with ExitStack() as stack:
        mocks = SimpleNamespace(
            **{
                step.lstrip("_"): stack.enter_context(patch(f"{MOCK_PATH}.{step}"))
                for step in PIPELINE_STEPS
            }
        )
        mocks.publish_metadata_to_ipfs.return_value = "f0170abc"
        mocks.compute_tools_to_package_hash.return_value = ""
        context = MagicMock()
        context.packages_dir = tmp_path / "packages"
        context.workspace_path = tmp_path
        context.metadata_path = tmp_path / "metadata.json"
        context.chain_env_path.return_value = tmp_path / ".env.gnosis"
        mocks.get_mtd_context.return_value = context
        mocks.context = context
        yield mocks


def _generate_kwargs(mocks: SimpleNamespace) -> dict:
    """Return the keyword arguments the command passed to generate_metadata."""
    mocks.generate_metadata.assert_called_once()
    return mocks.generate_metadata.call_args.kwargs


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
        result = runner.invoke(prepare_metadata, [*NAME_ARGS, "-c", "gnosis"])

        assert result.exit_code == 0
        mock_require_initialized.assert_called_once_with(context)
        mock_lock_packages.assert_called_once_with(context.packages_dir)
        mock_push_all.assert_called_once_with(
            context.workspace_path, context.packages_dir
        )
        mock_generate.assert_called_once_with(
            packages_dir=context.packages_dir,
            metadata_path=context.metadata_path,
            name=MECH_NAME,
            offchain_url="",
            operator=None,
            benchmarks={},
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
        result = runner.invoke(prepare_metadata, [*NAME_ARGS, "-c", "gnosis"])

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
        result = runner.invoke(prepare_metadata, NAME_ARGS)

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
        result = runner.invoke(prepare_metadata, NAME_ARGS)

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
            [*NAME_ARGS, "-c", "gnosis", "--offchain-url", "https://mech.example.com/"],
        )

        assert result.exit_code == 0
        mock_generate.assert_called_once_with(
            packages_dir=context.packages_dir,
            metadata_path=context.metadata_path,
            name=MECH_NAME,
            offchain_url="https://mech.example.com/",
            operator=None,
            benchmarks={},
        )
        mock_set_key.assert_any_call(
            str(env_path), "MECH_OFFCHAIN_URL", "https://mech.example.com/"
        )
        mock_update_cfg.assert_called_once_with(
            context,
            "gnosis",
            {
                "METADATA_HASH": "f0170abc",
                "SERVICE_ENDPOINT_BASE": "https://mech.example.com/",
            },
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
        result = runner.invoke(prepare_metadata, [*NAME_ARGS, "-c", "gnosis"])

        assert result.exit_code == 0
        mock_generate.assert_called_once_with(
            packages_dir=context.packages_dir,
            metadata_path=context.metadata_path,
            name=MECH_NAME,
            offchain_url="https://stored.example.com/",
            operator=None,
            benchmarks={},
        )


class TestPrepareMetadataNameFlag:
    """``--name`` is required and is what the manifest gets."""

    def test_missing_name_is_a_usage_error_before_any_work(
        self, tmp_path: Path
    ) -> None:
        """Without --name click exits with usage error 2 and nothing runs."""
        with _patched_pipeline(tmp_path) as mocks:
            result = CliRunner().invoke(prepare_metadata, ["-c", "gnosis"])

        assert result.exit_code == 2
        assert "--name" in result.output
        mocks.lock_packages.assert_not_called()
        mocks.generate_metadata.assert_not_called()

    def test_name_is_passed_to_generate(self, tmp_path: Path) -> None:
        """The --name value reaches generate_metadata unchanged."""
        with _patched_pipeline(tmp_path) as mocks:
            result = CliRunner().invoke(prepare_metadata, ["--name", "Olas Mech II"])

        assert result.exit_code == 0
        assert _generate_kwargs(mocks)["name"] == "Olas Mech II"

    def test_blank_name_from_generate_becomes_click_error(self, tmp_path: Path) -> None:
        """A ValueError raised by generate_metadata is shown as a CLI error, exit 1."""
        with _patched_pipeline(tmp_path) as mocks:
            mocks.generate_metadata.side_effect = ValueError(
                "Mech name must not be empty"
            )
            result = CliRunner().invoke(prepare_metadata, ["--name", "  "])

        assert result.exit_code == 1
        assert "Mech name must not be empty" in result.output
        mocks.publish_metadata_to_ipfs.assert_not_called()


class TestPrepareMetadataOperatorFlags:
    """``--operator-*`` flags build the operator block."""

    def test_operator_flags_build_operator(self, tmp_path: Path) -> None:
        """Name, domain and contact reach generate_metadata as one Operator."""
        args = [*NAME_ARGS, *OPERATOR_ARGS, "--operator-contact", "mechs@valory.xyz"]
        with _patched_pipeline(tmp_path) as mocks:
            result = CliRunner().invoke(prepare_metadata, args)

        assert result.exit_code == 0
        assert _generate_kwargs(mocks)["operator"] == Operator(
            name="Valory", domain="valory.xyz", contact="mechs@valory.xyz"
        )

    def test_operator_without_contact(self, tmp_path: Path) -> None:
        """Contact stays None when the flag is not given."""
        with _patched_pipeline(tmp_path) as mocks:
            result = CliRunner().invoke(prepare_metadata, [*NAME_ARGS, *OPERATOR_ARGS])

        assert result.exit_code == 0
        assert _generate_kwargs(mocks)["operator"] == Operator(
            name="Valory", domain="valory.xyz"
        )

    @pytest.mark.parametrize(
        "args, reason",
        [
            (["--operator-name", "Valory"], "must be given together"),
            (["--operator-domain", "valory.xyz"], "must be given together"),
            (["--operator-contact", "x@valory.xyz"], "requires --operator-name"),
            (
                [
                    "--operator-name",
                    "Valory",
                    "--operator-domain",
                    "https://valory.xyz",
                ],
                "not a bare hostname: it must not include a scheme",
            ),
            (
                ["--operator-name", "Valory", "--operator-domain", "valory.xyz/"],
                "must not include a path",
            ),
        ],
    )
    def test_invalid_operator_flags_fail_before_locking(
        self, tmp_path: Path, args: List[str], reason: str
    ) -> None:
        """Incomplete or invalid operator flags exit 1 with the reason, before any IPFS work."""
        with _patched_pipeline(tmp_path) as mocks:
            result = CliRunner().invoke(prepare_metadata, [*NAME_ARGS, *args])

        assert result.exit_code == 1
        assert reason in result.output
        mocks.lock_packages.assert_not_called()
        mocks.generate_metadata.assert_not_called()


class TestPrepareMetadataBenchmarkFlags:
    """``--benchmark`` and ``--benchmark-url`` build per-tool benchmarks."""

    def test_benchmark_flags_build_benchmarks(self, tmp_path: Path) -> None:
        """Each --benchmark becomes a Benchmark keyed by tool, all sharing --benchmark-url."""
        args = [
            *NAME_ARGS,
            *BENCHMARK_ARGS,
            "--benchmark",
            "claude",
            "accuracy",
            "0.5",
            "all",
        ]
        with _patched_pipeline(tmp_path) as mocks:
            result = CliRunner().invoke(prepare_metadata, args)

        assert result.exit_code == 0
        assert _generate_kwargs(mocks)["benchmarks"] == {
            "openai-gpt-4": Benchmark(
                metric="accuracy", value=0.83, window="30d", url=BENCHMARK_URL
            ),
            "claude": Benchmark(
                metric="accuracy", value=0.5, window="all", url=BENCHMARK_URL
            ),
        }

    @pytest.mark.parametrize(
        "args, reason",
        [
            (BENCHMARK_ARGS[2:], "--benchmark requires --benchmark-url"),
            (BENCHMARK_ARGS[:2], "--benchmark-url requires at least one --benchmark"),
            (
                [
                    *BENCHMARK_ARGS[:2],
                    "--benchmark",
                    "openai-gpt-4",
                    "accuracy",
                    "1.01",
                    "30d",
                ],
                "Invalid --benchmark for 'openai-gpt-4': Benchmark value must be between 0 and 1, got 1.01",
            ),
            (
                [
                    *BENCHMARK_ARGS[:2],
                    "--benchmark",
                    "openai-gpt-4",
                    "accuracy",
                    "0.5",
                    "60d",
                ],
                "window must be one of 7d, 30d, 90d, all",
            ),
            (
                [
                    *BENCHMARK_ARGS,
                    "--benchmark",
                    "openai-gpt-4",
                    "accuracy",
                    "0.5",
                    "7d",
                ],
                "given more than once",
            ),
        ],
    )
    def test_invalid_benchmark_flags_fail_before_locking(
        self, tmp_path: Path, args: List[str], reason: str
    ) -> None:
        """Incomplete or invalid benchmark flags exit 1 with the reason, before any IPFS work."""
        with _patched_pipeline(tmp_path) as mocks:
            result = CliRunner().invoke(prepare_metadata, [*NAME_ARGS, *args])

        assert result.exit_code == 1
        assert reason in result.output
        mocks.lock_packages.assert_not_called()
        mocks.generate_metadata.assert_not_called()

    def test_non_numeric_benchmark_value_is_a_usage_error(self, tmp_path: Path) -> None:
        """Click rejects a VALUE that is not a float with usage error 2."""
        args = [
            *NAME_ARGS,
            *BENCHMARK_ARGS[:2],
            "--benchmark",
            "openai-gpt-4",
            "accuracy",
            "high",
            "30d",
        ]
        with _patched_pipeline(tmp_path):
            result = CliRunner().invoke(prepare_metadata, args)

        assert result.exit_code == 2
        assert "high" in result.output

    def test_unknown_tool_from_generate_becomes_click_error(
        self, tmp_path: Path
    ) -> None:
        """generate_metadata's unknown-tool ValueError surfaces as a CLI error and stops publishing."""
        with _patched_pipeline(tmp_path) as mocks:
            mocks.generate_metadata.side_effect = ValueError(
                "Benchmark given for unknown tool 'openai-gpt-4'. Tools in this manifest: echo"
            )
            result = CliRunner().invoke(prepare_metadata, [*NAME_ARGS, *BENCHMARK_ARGS])

        assert result.exit_code == 1
        assert "unknown tool 'openai-gpt-4'" in result.output
        mocks.publish_metadata_to_ipfs.assert_not_called()


class TestBuildOperator:
    """Tests for _build_operator."""

    def test_returns_none_when_no_flag_given(self) -> None:
        """No operator flags means no operator block."""
        assert _build_operator(None, None, None) is None

    def test_builds_operator_with_contact(self) -> None:
        """All three flags populate the Operator."""
        assert _build_operator("Valory", "valory.xyz", "x@valory.xyz") == Operator(
            name="Valory", domain="valory.xyz", contact="x@valory.xyz"
        )


class TestBuildBenchmarks:
    """Tests for _build_benchmarks."""

    def test_returns_empty_when_no_flag_given(self) -> None:
        """No benchmark flags means no benchmarks."""
        assert len(_build_benchmarks((), None)) == 0

    def test_shares_url_across_tools(self) -> None:
        """Every entry gets the single --benchmark-url."""
        result = _build_benchmarks(
            (("a", "accuracy", 0.1, "7d"), ("b", "brier", 1.0, "90d")), BENCHMARK_URL
        )

        assert {tool: b.url for tool, b in result.items()} == {
            "a": BENCHMARK_URL,
            "b": BENCHMARK_URL,
        }
        assert result["b"] == Benchmark(
            metric="brier", value=1.0, window="90d", url=BENCHMARK_URL
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

    def test_explicit_url_takes_precedence(self) -> None:
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


class TestCleanPackagesDir:
    """Tests for _clean_packages_dir."""

    def test_removes_pycache_dirs(self, tmp_path: Path) -> None:
        """Remove __pycache__ directories from the packages tree."""
        pycache = tmp_path / "valory" / "customs" / "echo" / "__pycache__"
        pycache.mkdir(parents=True)
        (pycache / "echo.cpython-311.pyc").write_bytes(b"\x80\x00\x00\x00")

        _clean_packages_dir(tmp_path)

        assert not pycache.exists()

    def test_removes_ds_store_files(self, tmp_path: Path) -> None:
        """Remove .DS_Store files from the packages tree."""
        ds_store = tmp_path / "valory" / "customs" / ".DS_Store"
        ds_store.parent.mkdir(parents=True)
        ds_store.write_bytes(b"\x00\x00\x00\x01")

        _clean_packages_dir(tmp_path)

        assert not ds_store.exists()

    def test_noop_when_clean(self, tmp_path: Path) -> None:
        """Do nothing when there are no __pycache__ or .DS_Store entries."""
        tool_dir = tmp_path / "valory" / "customs" / "echo"
        tool_dir.mkdir(parents=True)
        (tool_dir / "echo.py").write_text("print('hi')", encoding="utf-8")

        _clean_packages_dir(tmp_path)

        assert (tool_dir / "echo.py").exists()


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

    def test_no_models_match_any_package(self, tmp_path: Path) -> None:
        """Return empty string when no model names match any package."""
        packages_json = {"dev": {"custom/valory/echo/0.1.0": "bafybeiabc"}}
        (tmp_path / "packages.json").write_text(
            json.dumps(packages_json), encoding="utf-8"
        )
        metadata_path = self._write_metadata(
            tmp_path,
            {"unknown-model": {"name": "nonexistent"}},
        )

        result = _compute_tools_to_package_hash(tmp_path, metadata_path)

        assert result == ""
