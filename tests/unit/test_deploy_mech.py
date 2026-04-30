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

"""Tests for mtd.deploy_mech module."""

import json
from unittest.mock import MagicMock, patch

import click
import pytest
from mtd.deploy_mech import (
    MECH_FACTORY_ADDRESS,
    deploy_mech,
    needs_mech_deployment,
    update_service_after_deploy,
)
from operate.operate_types import Chain

MOD = "mtd.deploy_mech"


def _make_mock_sftxb(
    mech_address: str = "0xMechAddress", agent_id: str = "42"
) -> MagicMock:
    """Create a mock EthSafeTxBuilder with standard return values."""
    mock_sftxb = MagicMock()
    mock_receipt = MagicMock()
    mock_sftxb.new_tx.return_value.add.return_value.settle.return_value = mock_receipt

    mock_contract = MagicMock()
    mock_sftxb.ledger_api.api.eth.contract.return_value = mock_contract

    mock_event = {"args": {"mech": mech_address, "serviceId": 1}}
    mock_contract.events.CreateMech.return_value.process_receipt.return_value = [
        mock_event
    ]
    mock_sftxb.info.return_value = {"canonical_agents": [agent_id]}
    return mock_sftxb


def _make_mock_service(
    home_chain: str = "gnosis",
    marketplace_address: str = "0x735FAAb1c4Ec41128c367AFb5c3baC73509f70bB",
    mech_type: str = "Native",
) -> MagicMock:
    """Create a mock Service with standard env variables."""
    mock_service = MagicMock()
    mock_service.home_chain = home_chain
    mock_service.env_variables = {
        "MECH_TYPE": {"value": mech_type},
        "MECH_MARKETPLACE_ADDRESS": {"value": marketplace_address},
        "MECH_REQUEST_PRICE": {"value": 10000000000000000},
    }
    mock_chain_data = MagicMock()
    mock_chain_data.token = 1
    mock_chain_config = MagicMock()
    mock_chain_config.chain_data = mock_chain_data
    mock_service.chain_configs = {home_chain: mock_chain_config}
    return mock_service


class TestDeployMech:
    """Tests for the deploy_mech function."""

    @patch(f"{MOD}.requests")
    def test_deploy_mech_success(self, mock_requests: MagicMock) -> None:
        """Test successful mech deployment."""
        mock_requests.get.return_value.json.return_value = {"abi": []}
        mock_service = _make_mock_service()
        mock_sftxb = _make_mock_sftxb()

        mech_address, agent_id = deploy_mech(sftxb=mock_sftxb, service=mock_service)

        assert mech_address == "0xMechAddress"
        assert agent_id == "42"
        mock_sftxb.new_tx.assert_called_once()

    @patch(f"{MOD}.requests")
    def test_deploy_mech_default_marketplace_fallback(
        self, mock_requests: MagicMock
    ) -> None:
        """Test that unsupported marketplace address falls back to first known for chain."""
        mock_requests.get.return_value.json.return_value = {"abi": []}
        mock_service = _make_mock_service(marketplace_address="0xUnsupportedAddress")
        mock_sftxb = _make_mock_sftxb(mech_address="0xFallbackMech", agent_id="99")

        mech_address, agent_id = deploy_mech(sftxb=mock_sftxb, service=mock_service)

        assert mech_address == "0xFallbackMech"
        assert agent_id == "99"

    @patch(f"{MOD}.requests")
    def test_deploy_mech_polygon_native(self, mock_requests: MagicMock) -> None:
        """Test deployment on Polygon with Native mech type."""
        mock_requests.get.return_value.json.return_value = {"abi": []}
        mock_service = _make_mock_service(
            home_chain="polygon",
            marketplace_address="0x343F2B005cF6D70bA610CD9F1F1927049414B582",
            mech_type="Native",
        )
        mock_sftxb = _make_mock_sftxb()

        mech_address, agent_id = deploy_mech(sftxb=mock_sftxb, service=mock_service)

        assert mech_address == "0xMechAddress"
        assert agent_id == "42"

    @patch(f"{MOD}.requests")
    def test_deploy_mech_polygon_token_usdc(self, mock_requests: MagicMock) -> None:
        """Test deployment on Polygon with TokenUSDC mech type."""
        mock_requests.get.return_value.json.return_value = {"abi": []}
        mock_service = _make_mock_service(
            home_chain="polygon",
            marketplace_address="0x343F2B005cF6D70bA610CD9F1F1927049414B582",
            mech_type="TokenUSDC",
        )
        mock_sftxb = _make_mock_sftxb(mech_address="0xUSDCMech", agent_id="77")

        mech_address, agent_id = deploy_mech(sftxb=mock_sftxb, service=mock_service)

        assert mech_address == "0xUSDCMech"
        assert agent_id == "77"

    @patch(f"{MOD}.requests")
    def test_deploy_mech_optimism(self, mock_requests: MagicMock) -> None:
        """Test deployment on Optimism."""
        mock_requests.get.return_value.json.return_value = {"abi": []}
        mock_service = _make_mock_service(
            home_chain="optimism",
            marketplace_address="0x46C0D07F55d4F9B5Eed2Fc9680B5953e5fd7b461",
            mech_type="Native",
        )
        mock_sftxb = _make_mock_sftxb()

        mech_address, agent_id = deploy_mech(sftxb=mock_sftxb, service=mock_service)

        assert mech_address == "0xMechAddress"
        assert agent_id == "42"

    @patch(f"{MOD}.requests")
    def test_deploy_mech_base(self, mock_requests: MagicMock) -> None:
        """Test deployment on Base."""
        mock_requests.get.return_value.json.return_value = {"abi": []}
        mock_service = _make_mock_service(
            home_chain="base",
            marketplace_address="0xf24eE42edA0fc9b33B7D41B06Ee8ccD2Ef7C5020",
            mech_type="Native",
        )
        mock_sftxb = _make_mock_sftxb()

        mech_address, agent_id = deploy_mech(sftxb=mock_sftxb, service=mock_service)

        assert mech_address == "0xMechAddress"
        assert agent_id == "42"

    @patch(f"{MOD}.requests")
    def test_deploy_mech_raises_on_network_error(
        self, mock_requests: MagicMock
    ) -> None:
        """Raise ClickException when the ABI request fails with a network error."""
        mock_requests.RequestException = Exception
        mock_requests.get.side_effect = Exception("connection refused")
        mock_service = _make_mock_service()
        mock_sftxb = _make_mock_sftxb()

        with pytest.raises(
            click.ClickException, match="Failed to fetch MechMarketplace ABI"
        ):
            deploy_mech(sftxb=mock_sftxb, service=mock_service)

    @patch(f"{MOD}.requests")
    def test_deploy_mech_raises_on_missing_abi_key(
        self, mock_requests: MagicMock
    ) -> None:
        """Raise ClickException when the ABI response is missing the 'abi' key."""
        mock_requests.RequestException = type("RequestException", (Exception,), {})
        mock_requests.get.return_value.json.return_value = {"notabi": []}
        mock_service = _make_mock_service()
        mock_sftxb = _make_mock_sftxb()

        with pytest.raises(click.ClickException, match="Unexpected response format"):
            deploy_mech(sftxb=mock_sftxb, service=mock_service)

    def test_deploy_mech_raises_for_unrecognised_chain(self) -> None:
        """Raise ClickException when Chain.from_string rejects the chain string."""
        mock_service = _make_mock_service(home_chain="badchain")
        mock_sftxb = _make_mock_sftxb()

        with pytest.raises(click.ClickException, match="badchain"):
            deploy_mech(sftxb=mock_sftxb, service=mock_service)

    @patch(f"{MOD}.Chain.from_string", return_value="unconfigured_chain")
    def test_deploy_mech_raises_when_chain_not_in_factory_map(
        self, _mock_from_string: MagicMock
    ) -> None:
        """Raise ClickException when Chain.from_string returns a chain with no factory addresses."""
        mock_service = _make_mock_service(home_chain="gnosis")
        mock_sftxb = _make_mock_sftxb()

        with pytest.raises(click.ClickException, match="gnosis"):
            deploy_mech(sftxb=mock_sftxb, service=mock_service)

    @patch(f"{MOD}.requests")
    def test_deploy_mech_fallback_polygon(self, mock_requests: MagicMock) -> None:
        """Test fallback on Polygon uses first known marketplace for that chain."""
        mock_requests.get.return_value.json.return_value = {"abi": []}
        mock_service = _make_mock_service(
            home_chain="polygon",
            marketplace_address="0xUnknownPolygonMarketplace",
            mech_type="Native",
        )
        mock_sftxb = _make_mock_sftxb(mech_address="0xPolygonFallback", agent_id="55")

        mech_address, agent_id = deploy_mech(sftxb=mock_sftxb, service=mock_service)

        assert mech_address == "0xPolygonFallback"
        assert agent_id == "55"


class TestMechFactoryAddress:
    """Tests for MECH_FACTORY_ADDRESS structure."""

    def test_all_chains_present(self) -> None:
        """All supported chains are in MECH_FACTORY_ADDRESS."""
        assert Chain.GNOSIS in MECH_FACTORY_ADDRESS
        assert Chain.BASE in MECH_FACTORY_ADDRESS
        assert Chain.POLYGON in MECH_FACTORY_ADDRESS
        assert Chain.OPTIMISM in MECH_FACTORY_ADDRESS

    def test_all_chains_have_native_and_token(self) -> None:
        """Every chain has at least Native and Token factory types."""
        for chain, marketplaces in MECH_FACTORY_ADDRESS.items():
            for mp_addr, factories in marketplaces.items():
                assert "Native" in factories, f"Missing Native for {chain} / {mp_addr}"
                assert "Token" in factories, f"Missing Token for {chain} / {mp_addr}"

    def test_polygon_has_token_usdc(self) -> None:
        """Polygon supports TokenUSDC mech type."""
        for factories in MECH_FACTORY_ADDRESS[Chain.POLYGON].values():
            assert "TokenUSDC" in factories

    def test_token_usdc_not_on_other_chains(self) -> None:
        """Test that TokenUSDC is only on Polygon, not other chains."""
        for chain in (Chain.GNOSIS, Chain.BASE, Chain.OPTIMISM):
            for factories in MECH_FACTORY_ADDRESS[chain].values():
                assert (
                    "TokenUSDC" not in factories
                ), f"TokenUSDC should not be on {chain}"


class TestNeedsMechDeployment:
    """Tests for needs_mech_deployment."""

    def test_needs_mech_deployment_true(self) -> None:
        """Service with empty AGENT_ID/MECH_TO_CONFIG needs deployment."""
        mock_service = MagicMock()
        mock_service.env_variables = {
            "AGENT_ID": {"value": ""},
            "MECH_TO_CONFIG": {"value": ""},
            "MECH_MARKETPLACE_ADDRESS": {"value": "0x123"},
        }

        assert needs_mech_deployment(mock_service) is True

    def test_needs_mech_deployment_false_already_deployed(self) -> None:
        """Service with filled values does not need deployment."""
        mock_service = MagicMock()
        mock_service.env_variables = {
            "AGENT_ID": {"value": "42"},
            "MECH_TO_CONFIG": {"value": '{"0xMech":{}}'},
            "MECH_MARKETPLACE_ADDRESS": {"value": "0x123"},
        }

        assert needs_mech_deployment(mock_service) is False

    def test_needs_mech_deployment_false_missing_vars(self) -> None:
        """Service without required vars does not need deployment."""
        mock_service = MagicMock()
        mock_service.env_variables = {
            "SOME_OTHER_VAR": {"value": "hello"},
        }

        assert needs_mech_deployment(mock_service) is False

    def test_needs_mech_deployment_true_agent_id_empty(self) -> None:
        """Service with empty AGENT_ID but filled MECH_TO_CONFIG needs deployment."""
        mock_service = MagicMock()
        mock_service.env_variables = {
            "AGENT_ID": {"value": ""},
            "MECH_TO_CONFIG": {"value": '{"0xMech":{}}'},
            "MECH_MARKETPLACE_ADDRESS": {"value": "0x123"},
        }

        assert needs_mech_deployment(mock_service) is True

    def test_needs_mech_deployment_true_mech_to_config_empty(self) -> None:
        """Service with filled AGENT_ID but empty MECH_TO_CONFIG needs deployment."""
        mock_service = MagicMock()
        mock_service.env_variables = {
            "AGENT_ID": {"value": "42"},
            "MECH_TO_CONFIG": {"value": ""},
            "MECH_MARKETPLACE_ADDRESS": {"value": "0x123"},
        }

        assert needs_mech_deployment(mock_service) is True


class TestUpdateServiceAfterDeploy:
    """Tests for update_service_after_deploy."""

    def test_update_service_after_deploy(self) -> None:
        """Verify env variables are updated correctly."""
        mock_service = MagicMock()
        mock_service.home_chain = "gnosis"
        mock_chain_config = MagicMock()
        mock_chain_config.chain_data.token = 123
        mock_chain_config.ledger_config.rpc = "https://rpc.gnosis.test"
        mock_service.chain_configs = {"gnosis": mock_chain_config}
        mock_service.env_variables = {
            "MECH_REQUEST_PRICE": {"value": 10000000000000000},
        }

        update_service_after_deploy(mock_service, "0xMechAddr", "42")

        mock_service.update_env_variables_values.assert_called_once()
        call_args = mock_service.update_env_variables_values.call_args[0][0]

        assert call_args["AGENT_ID"] == "42"
        mech_to_config = json.loads(call_args["MECH_TO_CONFIG"])
        assert "0xMechAddr" in mech_to_config
        assert mech_to_config["0xMechAddr"]["use_dynamic_pricing"] is False
        assert mech_to_config["0xMechAddr"]["is_marketplace_mech"] is True

        mech_to_max = json.loads(call_args["MECH_TO_MAX_DELIVERY_RATE"])
        assert mech_to_max["0xMechAddr"] == 10000000000000000
        assert call_args["ON_CHAIN_SERVICE_ID"] == 123
        assert call_args["ETHEREUM_LEDGER_RPC_0"] == "https://rpc.gnosis.test"
        assert call_args["GNOSIS_LEDGER_RPC_0"] == "https://rpc.gnosis.test"

    def test_update_service_after_deploy_default_price(self) -> None:
        """Verify default price when MECH_REQUEST_PRICE is missing."""
        mock_service = MagicMock()
        mock_service.home_chain = "base"
        mock_chain_config = MagicMock()
        mock_chain_config.chain_data.token = 7
        mock_chain_config.ledger_config.rpc = "https://rpc.base.test"
        mock_service.chain_configs = {"base": mock_chain_config}
        mock_service.env_variables = {}

        update_service_after_deploy(mock_service, "0xMech", "1")

        call_args = mock_service.update_env_variables_values.call_args[0][0]
        mech_to_max = json.loads(call_args["MECH_TO_MAX_DELIVERY_RATE"])
        assert mech_to_max["0xMech"] == 10000000000000000
        assert call_args["ON_CHAIN_SERVICE_ID"] == 7
        assert call_args["ETHEREUM_LEDGER_RPC_0"] == "https://rpc.base.test"
        assert call_args["BASE_LEDGER_RPC_0"] == "https://rpc.base.test"

    def test_update_service_after_deploy_raises_on_false_return(self) -> None:
        """Raise RuntimeError when update_env_variables_values returns False."""
        mock_service = MagicMock()
        mock_service.home_chain = "gnosis"
        mock_chain_config = MagicMock()
        mock_chain_config.chain_data.token = 1
        mock_chain_config.ledger_config.rpc = "https://rpc.gnosis.test"
        mock_service.chain_configs = {"gnosis": mock_chain_config}
        mock_service.env_variables = {}
        mock_service.update_env_variables_values.return_value = False

        with pytest.raises(RuntimeError, match="env variable update failed"):
            update_service_after_deploy(mock_service, "0xMech", "42")
