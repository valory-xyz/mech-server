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
"""Tests for setup flow behavior."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from mtd.context import build_context
from mtd.setup_flow import (
    _normalize_nullable_env_vars,
    _normalize_service_nullable_env_vars,
    _normalize_template_nullable_env_vars,
    run_setup,
)


MOD = "mtd.setup_flow"


@patch(f"{MOD}.update_metadata_onchain", return_value=(True, "0xabc"))
@patch(f"{MOD}.publish_metadata_to_ipfs", return_value="bafyhash")
@patch(f"{MOD}.generate_metadata")
@patch(f"{MOD}._setup_private_keys")
@patch(f"{MOD}._setup_env")
@patch(f"{MOD}._deploy_mech")
@patch(f"{MOD}.run_service")
@patch(f"{MOD}._configure_quickstart_env")
@patch(f"{MOD}._normalize_template_nullable_env_vars")
@patch(f"{MOD}._sanitize_local_quickstart_user_args")
@patch(f"{MOD}._normalize_service_nullable_env_vars")
@patch(f"{MOD}._get_password", return_value="password")
@patch(f"{MOD}.OperateApp")
def test_run_setup_passes_explicit_operate_home(
    mock_operate_app: MagicMock,
    mock_get_password: MagicMock,
    mock_normalize_service_env_vars: MagicMock,
    mock_sanitize_quickstart: MagicMock,
    mock_normalize_template_env_vars: MagicMock,
    mock_configure_quickstart: MagicMock,
    mock_run_service: MagicMock,
    mock_deploy_mech: MagicMock,
    mock_setup_env: MagicMock,
    mock_setup_private_keys: MagicMock,
    mock_generate_metadata: MagicMock,
    mock_publish_metadata: MagicMock,
    mock_update_metadata: MagicMock,
    tmp_path: Path,
    monkeypatch: MagicMock,
) -> None:
    """run_setup should create OperateApp with explicit workspace home path."""
    monkeypatch.setenv("HOME", str(tmp_path))
    context = build_context()
    context.config_dir.mkdir(parents=True, exist_ok=True)
    context.keys_dir.mkdir(parents=True, exist_ok=True)
    context.packages_dir.mkdir(parents=True, exist_ok=True)

    config_path = context.config_dir / "config_mech_polygon.json"
    config_path.write_text(
        json.dumps({"name": "Mech", "home_chain": "polygon", "chain_configs": {}}),
        encoding="utf-8",
    )

    mock_operate = MagicMock()
    mock_service_manager = MagicMock()
    mock_service_manager.get_all_services.return_value = ([], None)
    mock_operate.service_manager.return_value = mock_service_manager
    mock_operate_app.return_value = mock_operate

    run_setup(chain_config="polygon", context=context)

    mock_operate_app.assert_called_once_with(home=context.operate_dir)
    mock_normalize_service_env_vars.assert_called_once_with(context=context)
    mock_get_password.assert_called_once_with(operate=mock_operate, context=context)
    mock_sanitize_quickstart.assert_called_once_with(
        context=context, config_path=config_path
    )
    mock_normalize_template_env_vars.assert_called_once_with(config_path=config_path)
    mock_configure_quickstart.assert_called_once_with(
        operate=mock_operate, context=context
    )
    mock_run_service.assert_called_once()
    mock_deploy_mech.assert_called_once_with(mock_operate)
    mock_setup_env.assert_called_once_with(context=context)
    mock_setup_private_keys.assert_called_once_with(context=context)
    mock_generate_metadata.assert_called_once_with(
        packages_dir=context.packages_dir, metadata_path=context.metadata_path
    )
    mock_publish_metadata.assert_called_once_with(metadata_path=context.metadata_path)
    mock_update_metadata.assert_called_once_with(
        env_path=context.env_path,
        private_key_path=context.keys_dir / "ethereum_private_key.txt",
    )


def test_normalize_nullable_env_vars_empty_string_converted() -> None:
    """Empty string values for nullable vars are replaced with defaults."""
    env_variables = {
        "ON_CHAIN_SERVICE_ID": {"value": ""},
        "MECH_TO_CONFIG": {"value": ""},
        "MECH_TO_MAX_DELIVERY_RATE": {"value": ""},
    }
    changed = _normalize_nullable_env_vars(env_variables)
    assert changed is True
    assert env_variables["ON_CHAIN_SERVICE_ID"]["value"] == "null"
    assert env_variables["MECH_TO_CONFIG"]["value"] == "{}"
    assert env_variables["MECH_TO_MAX_DELIVERY_RATE"]["value"] == "{}"


def test_normalize_nullable_env_vars_none_value_converted() -> None:
    """None values for nullable vars are replaced with defaults."""
    env_variables = {"ON_CHAIN_SERVICE_ID": {"value": None}}
    changed = _normalize_nullable_env_vars(env_variables)
    assert changed is True
    assert env_variables["ON_CHAIN_SERVICE_ID"]["value"] == "null"


def test_normalize_nullable_env_vars_already_set_unchanged() -> None:
    """Non-empty values are not modified; returns False."""
    env_variables = {
        "ON_CHAIN_SERVICE_ID": {"value": "42"},
        "MECH_TO_CONFIG": {"value": '{"key": "val"}'},
    }
    changed = _normalize_nullable_env_vars(env_variables)
    assert changed is False
    assert env_variables["ON_CHAIN_SERVICE_ID"]["value"] == "42"


def test_normalize_nullable_env_vars_skips_non_dict_entry() -> None:
    """env_data that is not a dict is silently skipped."""
    env_variables = {"ON_CHAIN_SERVICE_ID": "not-a-dict"}
    changed = _normalize_nullable_env_vars(env_variables)
    assert changed is False
    assert env_variables["ON_CHAIN_SERVICE_ID"] == "not-a-dict"


def test_normalize_nullable_env_vars_missing_key_is_skipped() -> None:
    """Nullable var absent from env_variables causes no change."""
    env_variables: dict = {}
    changed = _normalize_nullable_env_vars(env_variables)
    assert changed is False


def test_normalize_template_nullable_env_vars(tmp_path: Path) -> None:
    """Template nullable env vars should be converted from empty strings."""
    config_path = tmp_path / "config_mech_polygon.json"
    config_path.write_text(
        json.dumps(
            {
                "env_variables": {
                    "ON_CHAIN_SERVICE_ID": {"value": ""},
                    "MECH_TO_CONFIG": {"value": ""},
                    "MECH_TO_MAX_DELIVERY_RATE": {"value": ""},
                }
            }
        ),
        encoding="utf-8",
    )

    _normalize_template_nullable_env_vars(config_path=config_path)

    data = json.loads(config_path.read_text(encoding="utf-8"))
    assert data["env_variables"]["ON_CHAIN_SERVICE_ID"]["value"] == "null"
    assert data["env_variables"]["MECH_TO_CONFIG"]["value"] == "{}"
    assert data["env_variables"]["MECH_TO_MAX_DELIVERY_RATE"]["value"] == "{}"


def test_normalize_service_nullable_env_vars(
    tmp_path: Path, monkeypatch: MagicMock
) -> None:
    """Existing service config nullable env vars should be normalized."""
    monkeypatch.setenv("HOME", str(tmp_path))
    context = build_context()
    service_dir = context.operate_dir / "services" / "sc-test"
    service_dir.mkdir(parents=True, exist_ok=True)
    config_path = service_dir / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "env_variables": {
                    "ON_CHAIN_SERVICE_ID": {"value": ""},
                    "MECH_TO_CONFIG": {"value": ""},
                    "MECH_TO_MAX_DELIVERY_RATE": {"value": ""},
                }
            }
        ),
        encoding="utf-8",
    )

    _normalize_service_nullable_env_vars(context=context)

    data = json.loads(config_path.read_text(encoding="utf-8"))
    assert data["env_variables"]["ON_CHAIN_SERVICE_ID"]["value"] == "null"
    assert data["env_variables"]["MECH_TO_CONFIG"]["value"] == "{}"
    assert data["env_variables"]["MECH_TO_MAX_DELIVERY_RATE"]["value"] == "{}"
