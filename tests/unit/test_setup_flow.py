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
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import click
import pytest

from mtd.context import build_context
from mtd.setup_flow import (
    _configure_quickstart_env,
    _create_private_key_files,
    _deploy_mech,
    _get_password,
    _normalize_nullable_env_vars,
    _normalize_service_nullable_env_vars,
    _normalize_template_nullable_env_vars,
    _read_and_update_env,
    _sanitize_local_quickstart_user_args,
    _setup_env,
    _setup_private_keys,
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


# ---------------------------------------------------------------------------
# _create_private_key_files
# ---------------------------------------------------------------------------


def test_create_private_key_files_creates_both(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Create both key files when neither exists."""
    monkeypatch.setenv("HOME", str(tmp_path))
    context = build_context()
    data = {"private_key": "0xdeadbeef", "address": "0xabc"}

    _create_private_key_files(data=data, context=context)

    agent_key = context.keys_dir / "ethereum_private_key.txt"
    service_key = context.keys_dir / "keys.json"
    assert agent_key.read_text(encoding="utf-8") == "0xdeadbeef"
    assert json.loads(service_key.read_text(encoding="utf-8")) == [data]


def test_create_private_key_files_skips_existing_agent_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Skip writing agent key when file already exists."""
    monkeypatch.setenv("HOME", str(tmp_path))
    context = build_context()
    context.keys_dir.mkdir(parents=True, exist_ok=True)
    agent_key = context.keys_dir / "ethereum_private_key.txt"
    agent_key.write_text("ORIGINAL", encoding="utf-8")

    _create_private_key_files(
        data={"private_key": "NEW", "address": "0xabc"}, context=context
    )

    assert agent_key.read_text(encoding="utf-8") == "ORIGINAL"


def test_create_private_key_files_skips_existing_service_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Skip writing service key when file already exists."""
    monkeypatch.setenv("HOME", str(tmp_path))
    context = build_context()
    context.keys_dir.mkdir(parents=True, exist_ok=True)
    service_key = context.keys_dir / "keys.json"
    service_key.write_text('[{"original": true}]', encoding="utf-8")

    _create_private_key_files(
        data={"private_key": "NEW", "address": "0xabc"}, context=context
    )

    assert json.loads(service_key.read_text(encoding="utf-8")) == [{"original": True}]


# ---------------------------------------------------------------------------
# _deploy_mech
# ---------------------------------------------------------------------------


def test_deploy_mech_returns_early_when_no_services() -> None:
    """Return immediately when no services are registered."""
    operate = MagicMock()
    manager = MagicMock()
    manager.get_all_services.return_value = ([], None)
    operate.service_manager.return_value = manager

    # needs_mech_deployment is imported lazily inside _deploy_mech, so no
    # patch needed here — the early-return guard fires before it is called.
    with patch("mtd.deploy_mech.deploy_mech") as mock_deploy:
        _deploy_mech(operate)

    mock_deploy.assert_not_called()


def test_deploy_mech_skips_when_already_deployed() -> None:
    """Print skip message when mech is already deployed."""
    operate = MagicMock()
    service = MagicMock()
    manager = MagicMock()
    manager.get_all_services.return_value = ([service], None)
    operate.service_manager.return_value = manager

    with patch("mtd.deploy_mech.needs_mech_deployment", return_value=False), patch(
        "mtd.deploy_mech.deploy_mech"
    ) as mock_deploy:
        _deploy_mech(operate)

    mock_deploy.assert_not_called()


def test_deploy_mech_deploys_when_needed() -> None:
    """Deploy mech and print address when deployment is required."""
    operate = MagicMock()
    service = MagicMock()
    manager = MagicMock()
    manager.get_all_services.return_value = ([service], None)
    operate.service_manager.return_value = manager

    with patch("mtd.deploy_mech.needs_mech_deployment", return_value=True), patch(
        "mtd.deploy_mech.deploy_mech", return_value=("0xmech", 42)
    ) as mock_deploy, patch("mtd.deploy_mech.update_service_after_deploy"):
        _deploy_mech(operate)

    mock_deploy.assert_called_once()


# ---------------------------------------------------------------------------
# _get_password
# ---------------------------------------------------------------------------


def test_get_password_reads_from_env_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Return password stored in workspace .env file."""
    monkeypatch.setenv("HOME", str(tmp_path))
    context = build_context()
    context.workspace_path.mkdir(parents=True, exist_ok=True)
    context.env_path.write_text("OPERATE_PASSWORD=mypassword\n", encoding="utf-8")
    operate = MagicMock()

    result = _get_password(operate=operate, context=context)

    assert result == "mypassword"
    assert operate.password == "mypassword"


def test_get_password_prompts_when_env_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Call ask_password_if_needed and return operate.password when no env file."""
    monkeypatch.setenv("HOME", str(tmp_path))
    context = build_context()
    operate = MagicMock()
    operate.password = "prompted_password"

    with patch(f"{MOD}.ask_password_if_needed"), patch(f"{MOD}.set_key"):
        result = _get_password(operate=operate, context=context)

    assert result == "prompted_password"


def test_get_password_raises_when_operate_password_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Raise ClickException when operate.password is empty after prompt."""
    monkeypatch.setenv("HOME", str(tmp_path))
    context = build_context()
    operate = MagicMock()
    operate.password = ""

    with patch(f"{MOD}.ask_password_if_needed"):
        with pytest.raises(click.ClickException, match="Password could not be set"):
            _get_password(operate=operate, context=context)


# ---------------------------------------------------------------------------
# _setup_private_keys
# ---------------------------------------------------------------------------


def test_setup_private_keys_no_keys_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Do nothing when the operate keys directory does not exist."""
    monkeypatch.setenv("HOME", str(tmp_path))
    context = build_context()

    _setup_private_keys(context=context)  # should not raise


def test_setup_private_keys_empty_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Do nothing when the keys directory is empty."""
    monkeypatch.setenv("HOME", str(tmp_path))
    context = build_context()
    (context.operate_dir / "keys").mkdir(parents=True, exist_ok=True)

    _setup_private_keys(context=context)  # should not raise


def test_setup_private_keys_raises_without_password(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Raise ValueError when OPERATE_PASSWORD is unset."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("OPERATE_PASSWORD", raising=False)
    context = build_context()
    keys_dir = context.operate_dir / "keys"
    keys_dir.mkdir(parents=True, exist_ok=True)
    (keys_dir / "key_file.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="OPERATE_PASSWORD is required"):
        _setup_private_keys(context=context)


def test_setup_private_keys_decrypts_and_creates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Decrypt the key file and delegate to _create_private_key_files."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("OPERATE_PASSWORD", "secret")
    context = build_context()
    keys_dir = context.operate_dir / "keys"
    keys_dir.mkdir(parents=True, exist_ok=True)
    (keys_dir / "key_file.json").write_text("{}", encoding="utf-8")

    mock_key_data = {"private_key": "0xkey", "address": "0xaddr"}
    with patch(f"{MOD}.KeysManager") as mock_km, patch(
        f"{MOD}._create_private_key_files"
    ) as mock_create:
        mock_km.return_value.get_decrypted.return_value = mock_key_data
        _setup_private_keys(context=context)

    mock_create.assert_called_once_with(data=mock_key_data, context=context)


# ---------------------------------------------------------------------------
# _sanitize_local_quickstart_user_args
# ---------------------------------------------------------------------------


def test_sanitize_quickstart_no_name_returns_early(tmp_path: Path) -> None:
    """Return early when template config has no name key."""
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({}), encoding="utf-8")
    context = MagicMock()

    _sanitize_local_quickstart_user_args(context=context, config_path=config_path)

    context.operate_dir.glob.assert_not_called()


def test_sanitize_quickstart_no_quickstart_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Return early when the quickstart config file does not exist."""
    monkeypatch.setenv("HOME", str(tmp_path))
    context = build_context()
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"name": "Mech"}), encoding="utf-8")

    _sanitize_local_quickstart_user_args(context=context, config_path=config_path)


def test_sanitize_quickstart_replaces_empty_user_arg(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Replace empty user arg with the non-empty template default."""
    monkeypatch.setenv("HOME", str(tmp_path))
    context = build_context()
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "name": "Mech",
                "env_variables": {
                    "MY_VAR": {"provision_type": "user", "value": "default_val"},
                },
            }
        ),
        encoding="utf-8",
    )
    quickstart_path = context.operate_dir / "Mech-quickstart-config.json"
    quickstart_path.parent.mkdir(parents=True, exist_ok=True)
    quickstart_path.write_text(
        json.dumps({"user_provided_args": {"MY_VAR": ""}}), encoding="utf-8"
    )

    _sanitize_local_quickstart_user_args(context=context, config_path=config_path)

    result = json.loads(quickstart_path.read_text(encoding="utf-8"))
    assert result["user_provided_args"]["MY_VAR"] == "default_val"


def test_sanitize_quickstart_preserves_set_user_arg(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Leave user arg unchanged when it is already set."""
    monkeypatch.setenv("HOME", str(tmp_path))
    context = build_context()
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "name": "Mech",
                "env_variables": {
                    "MY_VAR": {"provision_type": "user", "value": "default_val"},
                },
            }
        ),
        encoding="utf-8",
    )
    quickstart_path = context.operate_dir / "Mech-quickstart-config.json"
    quickstart_path.parent.mkdir(parents=True, exist_ok=True)
    quickstart_path.write_text(
        json.dumps({"user_provided_args": {"MY_VAR": "user_value"}}), encoding="utf-8"
    )

    _sanitize_local_quickstart_user_args(context=context, config_path=config_path)

    result = json.loads(quickstart_path.read_text(encoding="utf-8"))
    assert result["user_provided_args"]["MY_VAR"] == "user_value"


# ---------------------------------------------------------------------------
# _read_and_update_env
# ---------------------------------------------------------------------------


def test_read_and_update_env_missing_home_chain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Raise ValueError when home_chain is absent from data."""
    monkeypatch.setenv("HOME", str(tmp_path))
    context = build_context()

    with patch(f"{MOD}.read_text_resource", return_value=""):
        with pytest.raises(ValueError, match="home_chain"):
            _read_and_update_env(data={}, context=context)


def test_read_and_update_env_unsupported_chain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Raise ValueError for an unrecognised home_chain value."""
    monkeypatch.setenv("HOME", str(tmp_path))
    context = build_context()

    with patch(f"{MOD}.read_text_resource", return_value=""):
        with pytest.raises(ValueError, match="Unsupported"):
            _read_and_update_env(data={"home_chain": "badchain"}, context=context)


def test_read_and_update_env_missing_safe_address(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Raise ValueError when the safe address is absent or empty."""
    monkeypatch.setenv("HOME", str(tmp_path))
    context = build_context()
    data: dict = {
        "home_chain": "gnosis",
        "chain_configs": {"gnosis": {"chain_data": {"multisig": ""}}},
    }

    with patch(f"{MOD}.read_text_resource", return_value=""):
        with pytest.raises(ValueError, match="safe address"):
            _read_and_update_env(data=data, context=context)


def test_read_and_update_env_missing_chain_rpc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Raise ValueError when the chain RPC env var is missing."""
    monkeypatch.setenv("HOME", str(tmp_path))
    context = build_context()
    context.workspace_path.mkdir(parents=True, exist_ok=True)
    context.env_path.touch()
    data: dict = {
        "home_chain": "gnosis",
        "chain_configs": {"gnosis": {"chain_data": {"multisig": "0xsafe"}}},
        "agent_addresses": ["0xagent"],
        "env_variables": {
            "MECH_TO_MAX_DELIVERY_RATE": {"value": "{}"},
            "GNOSIS_LEDGER_RPC_0": {"value": ""},
        },
    }

    with patch(f"{MOD}.read_text_resource", return_value="KEY=\n"):
        with pytest.raises(ValueError, match="GNOSIS_LEDGER_RPC_0"):
            _read_and_update_env(data=data, context=context)


def test_read_and_update_env_writes_env_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Write the env file with computed values on the happy path."""
    monkeypatch.setenv("HOME", str(tmp_path))
    context = build_context()
    context.workspace_path.mkdir(parents=True, exist_ok=True)
    context.env_path.touch()
    data: dict = {
        "home_chain": "gnosis",
        "chain_configs": {"gnosis": {"chain_data": {"multisig": "0xsafe"}}},
        "agent_addresses": ["0xagent"],
        "env_variables": {
            "MECH_TO_MAX_DELIVERY_RATE": {"value": "{}"},
            "GNOSIS_LEDGER_RPC_0": {"value": "https://rpc.gnosis.io"},
        },
    }

    with patch(f"{MOD}.read_text_resource", return_value="SAFE_CONTRACT_ADDRESS=\n"):
        _read_and_update_env(data=data, context=context)

    content = context.env_path.read_text(encoding="utf-8")
    assert "SAFE_CONTRACT_ADDRESS=0xsafe" in content


# ---------------------------------------------------------------------------
# _setup_env
# ---------------------------------------------------------------------------


def test_setup_env_raises_when_no_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Raise FileNotFoundError when no operate service config files exist."""
    monkeypatch.setenv("HOME", str(tmp_path))
    context = build_context()
    context.operate_dir.mkdir(parents=True, exist_ok=True)

    with pytest.raises(FileNotFoundError, match="No operate config found"):
        _setup_env(context=context)


# ---------------------------------------------------------------------------
# _configure_quickstart_env
# ---------------------------------------------------------------------------


def test_configure_quickstart_env_sets_password_and_attended(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Set OPERATE_PASSWORD and ATTENDED env vars after getting password."""
    monkeypatch.setenv("HOME", str(tmp_path))
    context = build_context()
    operate = MagicMock()

    with patch(f"{MOD}._get_password", return_value="mypassword") as mock_pwd:
        _configure_quickstart_env(operate=operate, context=context)

    mock_pwd.assert_called_once_with(operate=operate, context=context)
    assert os.environ["OPERATE_PASSWORD"] == "mypassword"
    assert os.environ["ATTENDED"] == "true"


# ---------------------------------------------------------------------------
# _sanitize_local_quickstart_user_args — additional branches
# ---------------------------------------------------------------------------


def test_sanitize_quickstart_user_args_not_dict_returns_early(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Return early when user_provided_args is not a dict."""
    monkeypatch.setenv("HOME", str(tmp_path))
    context = build_context()
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"name": "Mech"}), encoding="utf-8")
    quickstart_path = context.operate_dir / "Mech-quickstart-config.json"
    quickstart_path.parent.mkdir(parents=True, exist_ok=True)
    quickstart_path.write_text(
        json.dumps({"user_provided_args": "notadict"}), encoding="utf-8"
    )

    _sanitize_local_quickstart_user_args(context=context, config_path=config_path)

    # File should be unchanged (no replacement occurred)
    result = json.loads(quickstart_path.read_text(encoding="utf-8"))
    assert result["user_provided_args"] == "notadict"


def test_sanitize_quickstart_skips_non_user_provision_type(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Skip env vars whose provision_type is not 'user'."""
    monkeypatch.setenv("HOME", str(tmp_path))
    context = build_context()
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "name": "Mech",
                "env_variables": {
                    "MY_VAR": {"provision_type": "system", "value": "default"},
                },
            }
        ),
        encoding="utf-8",
    )
    quickstart_path = context.operate_dir / "Mech-quickstart-config.json"
    quickstart_path.parent.mkdir(parents=True, exist_ok=True)
    quickstart_path.write_text(
        json.dumps({"user_provided_args": {"MY_VAR": ""}}), encoding="utf-8"
    )

    _sanitize_local_quickstart_user_args(context=context, config_path=config_path)

    result = json.loads(quickstart_path.read_text(encoding="utf-8"))
    assert result["user_provided_args"]["MY_VAR"] == ""


def test_sanitize_quickstart_skips_env_var_absent_from_user_args(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Skip env vars that are not present in user_provided_args."""
    monkeypatch.setenv("HOME", str(tmp_path))
    context = build_context()
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "name": "Mech",
                "env_variables": {
                    "MISSING_VAR": {"provision_type": "user", "value": "default"},
                },
            }
        ),
        encoding="utf-8",
    )
    quickstart_path = context.operate_dir / "Mech-quickstart-config.json"
    quickstart_path.parent.mkdir(parents=True, exist_ok=True)
    quickstart_path.write_text(json.dumps({"user_provided_args": {}}), encoding="utf-8")

    _sanitize_local_quickstart_user_args(context=context, config_path=config_path)

    result = json.loads(quickstart_path.read_text(encoding="utf-8"))
    assert result["user_provided_args"] == {}


# ---------------------------------------------------------------------------
# run_setup — missing config path
# ---------------------------------------------------------------------------


@patch(f"{MOD}._workspace_cwd")
@patch(f"{MOD}.OperateApp")
def test_run_setup_raises_when_config_missing(
    mock_operate_app: MagicMock,
    mock_cwd: MagicMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Raise ClickException when the chain config template file is absent."""
    monkeypatch.setenv("HOME", str(tmp_path))
    context = build_context()
    context.config_dir.mkdir(parents=True, exist_ok=True)
    # config_mech_polygon.json deliberately not created

    with pytest.raises(click.ClickException, match="Missing template config"):
        run_setup(chain_config="polygon", context=context)
