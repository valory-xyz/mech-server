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
from importlib import resources
from types import SimpleNamespace
from typing import Any, Iterable, List
from unittest.mock import MagicMock, patch

import click
import pytest
from mtd.deploy_mech import (
    MECH_FACTORY_ADDRESS,
    MECH_TYPE_PAYMENT_TYPE,
    deploy_mech,
    needs_mech_deployment,
    update_service_after_deploy,
)
from operate.operate_types import Chain

MOD = "mtd.deploy_mech"

GNOSIS_MARKETPLACE = "0x735FAAb1c4Ec41128c367AFb5c3baC73509f70bB"
GNOSIS_LEGACY_MARKETPLACE = "0xad380C51cd5297FbAE43494dD5D407A2a3260b58"
BASE_MARKETPLACE = "0xf24eE42edA0fc9b33B7D41B06Ee8ccD2Ef7C5020"
POLYGON_MARKETPLACE = "0x343F2B005cF6D70bA610CD9F1F1927049414B582"
OPTIMISM_MARKETPLACE = "0x46C0D07F55d4F9B5Eed2Fc9680B5953e5fd7b461"

GNOSIS_NATIVE_FACTORY_NEW = "0x5270c0797a9D0c59163cF570129E5808BE7927FA"
GNOSIS_NATIVE_FACTORY_OLD = "0x8b299c20F87e3fcBfF0e1B86dC0acC06AB6993EF"
GNOSIS_TOKEN_FACTORY = "0x31ffDC795FDF36696B8eDF7583A3D115995a45FA"  # nosec B105
GNOSIS_NEVERMINED_FACTORY = "0x65fd74C29463afe08c879a3020323DD7DF02DA57"
GNOSIS_LEGACY_NATIVE_FACTORY = "0x42f43be9E5E50df51b86C5c6427223ff565f40C6"

BASE_NATIVE_FACTORY_NEW = "0xf8a8C985f46Ab6204e6A40845e73a6119f0458ED"
POLYGON_NATIVE_FACTORY_NEW = "0x40dABcF2DEEc7241749B320cbC5ca69544a90d68"
POLYGON_USDC_FACTORY_NEW = "0x749cdf4bF2e55269b3d1bC4b4408e34689c96B67"
POLYGON_USDC_FACTORY_OLD = "0x85899f9d8C058A5BBBaF344ea0f0b63c0CcBe851"
POLYGON_TOKEN_FACTORY = "0xa0DA53447C0f6C4987964d8463da7e6628B30f82"  # nosec B105
POLYGON_NEVERMINED_FACTORY = "0x43fB32f25dce34EB76c78C7A42C8F40F84BCD237"
OPTIMISM_NATIVE_FACTORY_NEW = "0xaaFBeef195BDAb1Bb6f3Dc9cEbA875Cd72499230"

A_BALANCE_TRACKER = "0x21cE6799A22A3Da84B7c44a814a9c79ab1d2A50D"
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
RPC_ERROR = "rpc endpoint unreachable"

DEFAULT_MECH_REQUEST_PRICE = 10000000000000000


def _make_mock_sftxb(
    mech_address: str = "0xMechAddress",
    agent_id: str = "42",
    enabled_factories: Iterable[str] = (),
    balance_tracker: str = A_BALANCE_TRACKER,
    failing_read: str = "",
) -> MagicMock:
    """Create a mock EthSafeTxBuilder whose marketplace reads are configurable.

    :param mech_address: address reported by the CreateMech event.
    :param agent_id: canonical agent id reported for the service.
    :param enabled_factories: factory addresses the marketplace reports as enabled.
    :param balance_tracker: address returned for any queried payment type.
    :param failing_read: name of the marketplace view whose call() raises instead.
    :return: the configured mock.
    """
    enabled = {address.lower() for address in enabled_factories}
    mock_sftxb = MagicMock()
    mock_receipt = MagicMock()
    mock_sftxb.new_tx.return_value.add.return_value.settle.return_value = mock_receipt

    mock_contract = MagicMock()
    mock_contract.encode_abi.return_value = "0xdeadbeef"

    def _raise_rpc_error() -> None:
        """Stand in for a failing RPC call.

        :raises ConnectionError: always, as the configured transport failure.
        """
        raise ConnectionError(RPC_ERROR)

    def _factories_call(address: str) -> SimpleNamespace:
        """Serve mapMechFactories for one candidate.

        :param address: candidate factory address being probed.
        :return: object whose call() answers the probe.
        """
        if failing_read == "mapMechFactories":
            return SimpleNamespace(call=_raise_rpc_error)
        return SimpleNamespace(call=lambda: address.lower() in enabled)

    def _trackers_call(_payment_type: str) -> SimpleNamespace:
        """Serve mapPaymentTypeBalanceTrackers for one payment type.

        :param _payment_type: payment type being looked up.
        :return: object whose call() answers the lookup.
        """
        if failing_read == "mapPaymentTypeBalanceTrackers":
            return SimpleNamespace(call=_raise_rpc_error)
        return SimpleNamespace(call=lambda: balance_tracker)

    mock_contract.functions.mapMechFactories.side_effect = _factories_call
    mock_contract.functions.mapPaymentTypeBalanceTrackers.side_effect = _trackers_call
    mock_sftxb.ledger_api.api.eth.contract.return_value = mock_contract

    mock_event = {"args": {"mech": mech_address, "serviceId": 1}}
    mock_contract.events.CreateMech.return_value.process_receipt.return_value = [
        mock_event
    ]
    mock_sftxb.info.return_value = {"canonical_agents": [agent_id]}
    return mock_sftxb


def _make_mock_service(
    home_chain: str = "gnosis",
    marketplace_address: str = GNOSIS_MARKETPLACE,
    mech_type: str = "Native",
) -> MagicMock:
    """Create a mock Service with standard env variables.

    :param home_chain: service home chain name.
    :param marketplace_address: MECH_MARKETPLACE_ADDRESS env value.
    :param mech_type: MECH_TYPE env value.
    :return: the configured mock.
    """
    mock_service = MagicMock()
    mock_service.home_chain = home_chain
    mock_service.env_variables = {
        "MECH_TYPE": {"value": mech_type},
        "MECH_MARKETPLACE_ADDRESS": {"value": marketplace_address},
        "MECH_REQUEST_PRICE": {"value": DEFAULT_MECH_REQUEST_PRICE},
    }
    mock_chain_data = MagicMock()
    mock_chain_data.token = 1
    mock_chain_config = MagicMock()
    mock_chain_config.chain_data = mock_chain_data
    mock_service.chain_configs = {home_chain: mock_chain_config}
    return mock_service


def _factory_used(mock_sftxb: MagicMock) -> Any:
    """Return the factory address the create() call was encoded with.

    :param mock_sftxb: mock whose marketplace contract encoded the call.
    :return: the factory address passed to create().
    """
    contract = mock_sftxb.ledger_api.api.eth.contract.return_value
    return contract.encode_abi.call_args.kwargs["args"][1]


def _balance_trackers_queried(mock_sftxb: MagicMock) -> List[Any]:
    """Return the payment types the balance tracker mapping was read for.

    :param mock_sftxb: mock whose marketplace contract served the reads.
    :return: list of payment types queried, in call order.
    """
    contract = mock_sftxb.ledger_api.api.eth.contract.return_value
    return [
        call.args[0]
        for call in contract.functions.mapPaymentTypeBalanceTrackers.call_args_list
    ]


class TestFactorySelection:
    """Tests for choosing the factory the marketplace currently accepts."""

    @patch(f"{MOD}.requests")
    def test_picks_old_factory_while_only_it_is_enabled(
        self, mock_requests: MagicMock
    ) -> None:
        """Before the marketplace upgrade the previously deployed factory is used."""
        mock_requests.get.return_value.json.return_value = {"abi": []}
        mock_service = _make_mock_service()
        mock_sftxb = _make_mock_sftxb(
            enabled_factories=[GNOSIS_NATIVE_FACTORY_OLD],
        )

        deploy_mech(sftxb=mock_sftxb, service=mock_service)

        assert _factory_used(mock_sftxb) == GNOSIS_NATIVE_FACTORY_OLD

    @patch(f"{MOD}.requests")
    def test_picks_new_factory_once_only_it_is_enabled(
        self, mock_requests: MagicMock
    ) -> None:
        """After the marketplace upgrade the newly deployed factory is used."""
        mock_requests.get.return_value.json.return_value = {"abi": []}
        mock_service = _make_mock_service()
        mock_sftxb = _make_mock_sftxb(
            enabled_factories=[GNOSIS_NATIVE_FACTORY_NEW],
        )

        deploy_mech(sftxb=mock_sftxb, service=mock_service)

        assert _factory_used(mock_sftxb) == GNOSIS_NATIVE_FACTORY_NEW

    @patch(f"{MOD}.requests")
    def test_prefers_newest_factory_when_both_are_enabled(
        self, mock_requests: MagicMock
    ) -> None:
        """With both factories enabled the newest candidate wins."""
        mock_requests.get.return_value.json.return_value = {"abi": []}
        mock_service = _make_mock_service()
        mock_sftxb = _make_mock_sftxb(
            enabled_factories=[
                GNOSIS_NATIVE_FACTORY_OLD,
                GNOSIS_NATIVE_FACTORY_NEW,
            ],
        )

        deploy_mech(sftxb=mock_sftxb, service=mock_service)

        assert _factory_used(mock_sftxb) == GNOSIS_NATIVE_FACTORY_NEW

    @patch(f"{MOD}.requests")
    def test_refuses_when_no_candidate_is_enabled(
        self, mock_requests: MagicMock
    ) -> None:
        """Refuse with chain, marketplace, mech type and candidates named."""
        mock_requests.get.return_value.json.return_value = {"abi": []}
        mock_service = _make_mock_service()
        mock_sftxb = _make_mock_sftxb(enabled_factories=[])

        with pytest.raises(click.ClickException) as exc_info:
            deploy_mech(sftxb=mock_sftxb, service=mock_service)

        message = str(exc_info.value)
        assert "gnosis" in message
        assert GNOSIS_MARKETPLACE in message
        assert "Native" in message
        assert GNOSIS_NATIVE_FACTORY_NEW in message
        assert GNOSIS_NATIVE_FACTORY_OLD in message
        mock_sftxb.new_tx.assert_not_called()

    @pytest.mark.parametrize(
        ("mech_type", "factory"),
        [
            ("Token", GNOSIS_TOKEN_FACTORY),
            ("Nevermined", GNOSIS_NEVERMINED_FACTORY),
        ],
    )
    @patch(f"{MOD}.requests")
    def test_single_candidate_mech_type_is_used_when_enabled(
        self, mock_requests: MagicMock, mech_type: str, factory: str
    ) -> None:
        """A mech type with one known factory deploys with it when enabled.

        :param mock_requests: patched requests module serving the marketplace ABI.
        :param mech_type: MECH_TYPE under test.
        :param factory: the single known factory for that mech type.
        """
        mock_requests.get.return_value.json.return_value = {"abi": []}
        mock_service = _make_mock_service(mech_type=mech_type)
        mock_sftxb = _make_mock_sftxb(enabled_factories=[factory])

        deploy_mech(sftxb=mock_sftxb, service=mock_service)

        assert _factory_used(mock_sftxb) == factory

    @pytest.mark.parametrize(
        ("mech_type", "factory"),
        [
            ("Token", GNOSIS_TOKEN_FACTORY),
            ("Nevermined", GNOSIS_NEVERMINED_FACTORY),
        ],
    )
    @patch(f"{MOD}.requests")
    def test_single_candidate_mech_type_refuses_when_disabled(
        self, mock_requests: MagicMock, mech_type: str, factory: str
    ) -> None:
        """A mech type with one known factory refuses once it is disabled.

        :param mock_requests: patched requests module serving the marketplace ABI.
        :param mech_type: MECH_TYPE under test.
        :param factory: the single known factory for that mech type.
        """
        mock_requests.get.return_value.json.return_value = {"abi": []}
        mock_service = _make_mock_service(mech_type=mech_type)
        mock_sftxb = _make_mock_sftxb(enabled_factories=[])

        with pytest.raises(click.ClickException) as exc_info:
            deploy_mech(sftxb=mock_sftxb, service=mock_service)

        assert factory in str(exc_info.value)
        mock_sftxb.new_tx.assert_not_called()

    @patch(f"{MOD}.requests")
    def test_refuses_unsupported_marketplace_address(
        self, mock_requests: MagicMock
    ) -> None:
        """An unknown marketplace address is refused, never redirected."""
        mock_requests.get.return_value.json.return_value = {"abi": []}
        mock_service = _make_mock_service(marketplace_address="0xUnsupportedAddress")
        mock_sftxb = _make_mock_sftxb(
            enabled_factories=[
                GNOSIS_NATIVE_FACTORY_NEW,
                GNOSIS_LEGACY_NATIVE_FACTORY,
            ],
        )

        with pytest.raises(click.ClickException) as exc_info:
            deploy_mech(sftxb=mock_sftxb, service=mock_service)

        message = str(exc_info.value)
        assert "0xUnsupportedAddress" in message
        assert "gnosis" in message
        assert GNOSIS_MARKETPLACE in message
        assert GNOSIS_LEGACY_MARKETPLACE in message
        mock_sftxb.new_tx.assert_not_called()

    @patch(f"{MOD}.requests")
    def test_refuses_mech_type_with_no_configured_factory(
        self, mock_requests: MagicMock
    ) -> None:
        """A mech type the chain's marketplace does not offer is refused."""
        mock_requests.get.return_value.json.return_value = {"abi": []}
        mock_service = _make_mock_service(mech_type="TokenUSDC")
        mock_sftxb = _make_mock_sftxb(
            enabled_factories=[GNOSIS_NATIVE_FACTORY_NEW],
        )

        with pytest.raises(click.ClickException) as exc_info:
            deploy_mech(sftxb=mock_sftxb, service=mock_service)

        message = str(exc_info.value)
        assert "TokenUSDC" in message
        assert "Native" in message
        mock_sftxb.new_tx.assert_not_called()

    @pytest.mark.parametrize(
        ("home_chain", "marketplace", "mech_type", "factory"),
        [
            ("base", BASE_MARKETPLACE, "Native", BASE_NATIVE_FACTORY_NEW),
            ("polygon", POLYGON_MARKETPLACE, "Native", POLYGON_NATIVE_FACTORY_NEW),
            ("polygon", POLYGON_MARKETPLACE, "TokenUSDC", POLYGON_USDC_FACTORY_NEW),
            ("polygon", POLYGON_MARKETPLACE, "Token", POLYGON_TOKEN_FACTORY),
            (
                "polygon",
                POLYGON_MARKETPLACE,
                "Nevermined",
                POLYGON_NEVERMINED_FACTORY,
            ),
            ("optimism", OPTIMISM_MARKETPLACE, "Native", OPTIMISM_NATIVE_FACTORY_NEW),
            (
                "gnosis",
                GNOSIS_LEGACY_MARKETPLACE,
                "Native",
                GNOSIS_LEGACY_NATIVE_FACTORY,
            ),
        ],
    )
    @patch(f"{MOD}.requests")
    def test_each_chain_and_mech_type_resolves_its_enabled_factory(
        self,
        mock_requests: MagicMock,
        home_chain: str,
        marketplace: str,
        mech_type: str,
        factory: str,
    ) -> None:
        """Every supported chain and mech type deploys with its enabled factory.

        :param mock_requests: patched requests module serving the marketplace ABI.
        :param home_chain: service home chain name.
        :param marketplace: configured marketplace address.
        :param mech_type: MECH_TYPE under test.
        :param factory: the factory expected to be selected.
        """
        mock_requests.get.return_value.json.return_value = {"abi": []}
        mock_service = _make_mock_service(
            home_chain=home_chain,
            marketplace_address=marketplace,
            mech_type=mech_type,
        )
        mock_sftxb = _make_mock_sftxb(enabled_factories=[factory])

        deploy_mech(sftxb=mock_sftxb, service=mock_service)

        assert _factory_used(mock_sftxb) == factory

    @patch(f"{MOD}.requests")
    def test_older_candidate_is_not_probed_once_newest_is_enabled(
        self, mock_requests: MagicMock
    ) -> None:
        """Probing stops at the first enabled candidate."""
        mock_requests.get.return_value.json.return_value = {"abi": []}
        mock_service = _make_mock_service()
        mock_sftxb = _make_mock_sftxb(
            enabled_factories=[
                GNOSIS_NATIVE_FACTORY_NEW,
                GNOSIS_NATIVE_FACTORY_OLD,
            ],
        )

        deploy_mech(sftxb=mock_sftxb, service=mock_service)

        contract = mock_sftxb.ledger_api.api.eth.contract.return_value
        probed = [
            call.args[0] for call in contract.functions.mapMechFactories.call_args_list
        ]
        assert probed == [GNOSIS_NATIVE_FACTORY_NEW]


class TestBalanceTrackerPrecondition:
    """Tests for the balance tracker check that create() enforces on-chain."""

    @patch(f"{MOD}.requests")
    def test_refuses_when_payment_type_has_no_balance_tracker(
        self, mock_requests: MagicMock
    ) -> None:
        """Refuse before sending a create() the marketplace would reject."""
        mock_requests.get.return_value.json.return_value = {"abi": []}
        mock_service = _make_mock_service()
        mock_sftxb = _make_mock_sftxb(
            enabled_factories=[GNOSIS_NATIVE_FACTORY_NEW],
            balance_tracker=ZERO_ADDRESS,
        )

        with pytest.raises(click.ClickException) as exc_info:
            deploy_mech(sftxb=mock_sftxb, service=mock_service)

        message = str(exc_info.value)
        assert "balance tracker" in message
        assert "Native" in message
        assert MECH_TYPE_PAYMENT_TYPE["Native"] in message
        mock_sftxb.new_tx.assert_not_called()

    @patch(f"{MOD}.requests")
    def test_proceeds_when_payment_type_has_a_balance_tracker(
        self, mock_requests: MagicMock
    ) -> None:
        """The mech type's payment type is the one checked."""
        mock_requests.get.return_value.json.return_value = {"abi": []}
        mock_service = _make_mock_service(
            home_chain="polygon",
            marketplace_address=POLYGON_MARKETPLACE,
            mech_type="TokenUSDC",
        )
        mock_sftxb = _make_mock_sftxb(
            enabled_factories=[POLYGON_USDC_FACTORY_NEW],
        )

        deploy_mech(sftxb=mock_sftxb, service=mock_service)

        assert _balance_trackers_queried(mock_sftxb) == [
            MECH_TYPE_PAYMENT_TYPE["TokenUSDC"]
        ]
        mock_sftxb.new_tx.assert_called_once()

    @patch(f"{MOD}.requests")
    def test_skips_check_for_mech_type_without_a_fixed_payment_type(
        self, mock_requests: MagicMock
    ) -> None:
        """Nevermined mechs are created without a balance tracker pre-check."""
        mock_requests.get.return_value.json.return_value = {"abi": []}
        mock_service = _make_mock_service(mech_type="Nevermined")
        mock_sftxb = _make_mock_sftxb(
            enabled_factories=[GNOSIS_NEVERMINED_FACTORY],
            balance_tracker=ZERO_ADDRESS,
        )

        deploy_mech(sftxb=mock_sftxb, service=mock_service)

        assert _balance_trackers_queried(mock_sftxb) == []
        mock_sftxb.new_tx.assert_called_once()


class TestMarketplaceReadFailures:
    """Tests for surfacing a failed marketplace read as a CLI error."""

    @patch(f"{MOD}.requests")
    def test_refuses_when_factory_probe_cannot_be_read(
        self, mock_requests: MagicMock
    ) -> None:
        """A failed mapMechFactories read is reported, not raised as a traceback."""
        mock_requests.get.return_value.json.return_value = {"abi": []}
        mock_service = _make_mock_service()
        mock_sftxb = _make_mock_sftxb(
            enabled_factories=[GNOSIS_NATIVE_FACTORY_NEW],
            failing_read="mapMechFactories",
        )

        with pytest.raises(click.ClickException) as exc_info:
            deploy_mech(sftxb=mock_sftxb, service=mock_service)

        message = str(exc_info.value)
        assert "mapMechFactories" in message
        assert "gnosis" in message
        assert GNOSIS_MARKETPLACE in message
        assert RPC_ERROR in message
        mock_sftxb.new_tx.assert_not_called()

    @patch(f"{MOD}.requests")
    def test_refuses_when_balance_tracker_cannot_be_read(
        self, mock_requests: MagicMock
    ) -> None:
        """A failed mapPaymentTypeBalanceTrackers read is reported the same way."""
        mock_requests.get.return_value.json.return_value = {"abi": []}
        mock_service = _make_mock_service()
        mock_sftxb = _make_mock_sftxb(
            enabled_factories=[GNOSIS_NATIVE_FACTORY_NEW],
            failing_read="mapPaymentTypeBalanceTrackers",
        )

        with pytest.raises(click.ClickException) as exc_info:
            deploy_mech(sftxb=mock_sftxb, service=mock_service)

        message = str(exc_info.value)
        assert "mapPaymentTypeBalanceTrackers" in message
        assert "gnosis" in message
        assert GNOSIS_MARKETPLACE in message
        assert RPC_ERROR in message
        mock_sftxb.new_tx.assert_not_called()


class TestDeployMech:
    """Tests for the deploy_mech function."""

    @patch(f"{MOD}.requests")
    def test_deploy_mech_success(self, mock_requests: MagicMock) -> None:
        """Test successful mech deployment."""
        mock_requests.get.return_value.json.return_value = {"abi": []}
        mock_service = _make_mock_service()
        mock_sftxb = _make_mock_sftxb(
            enabled_factories=[GNOSIS_NATIVE_FACTORY_NEW],
        )

        mech_address, agent_id = deploy_mech(sftxb=mock_sftxb, service=mock_service)

        assert mech_address == "0xMechAddress"
        assert agent_id == "42"
        mock_sftxb.new_tx.assert_called_once()

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


class TestMechFactoryAddress:
    """Tests for MECH_FACTORY_ADDRESS structure."""

    def test_all_chains_present(self) -> None:
        """All supported chains are in MECH_FACTORY_ADDRESS."""
        assert Chain.GNOSIS in MECH_FACTORY_ADDRESS
        assert Chain.BASE in MECH_FACTORY_ADDRESS
        assert Chain.POLYGON in MECH_FACTORY_ADDRESS
        assert Chain.OPTIMISM in MECH_FACTORY_ADDRESS

    def test_every_mech_type_holds_a_non_empty_candidate_list(self) -> None:
        """Every leaf is an ordered tuple of distinct factory addresses."""
        for chain, marketplaces in MECH_FACTORY_ADDRESS.items():
            for mp_addr, mech_types in marketplaces.items():
                for mech_type, candidates in mech_types.items():
                    where = f"{chain} / {mp_addr} / {mech_type}"
                    assert isinstance(candidates, tuple), where
                    assert candidates, where
                    assert len(set(candidates)) == len(candidates), where
                    for candidate in candidates:
                        assert candidate.startswith("0x"), where
                        assert len(candidate) == 42, where

    def test_all_chains_have_native_and_token(self) -> None:
        """Every chain has at least Native and Token factory types."""
        for chain, marketplaces in MECH_FACTORY_ADDRESS.items():
            for mp_addr, mech_types in marketplaces.items():
                assert "Native" in mech_types, f"Missing Native for {chain} / {mp_addr}"
                assert "Token" in mech_types, f"Missing Token for {chain} / {mp_addr}"

    def test_token_usdc_supported_chains(self) -> None:
        """Polygon, Optimism and Base support the TokenUSDC mech type."""
        for chain in (Chain.POLYGON, Chain.OPTIMISM, Chain.BASE):
            for mech_types in MECH_FACTORY_ADDRESS[chain].values():
                assert "TokenUSDC" in mech_types, f"TokenUSDC missing on {chain}"

    def test_token_usdc_not_on_gnosis(self) -> None:
        """Gnosis does not offer the TokenUSDC mech type."""
        for mech_types in MECH_FACTORY_ADDRESS[Chain.GNOSIS].values():
            assert "TokenUSDC" not in mech_types

    def test_upgraded_marketplaces_carry_a_replacement_native_factory(self) -> None:
        """The marketplaces being upgraded list two Native candidates, newest first."""
        upgraded = {
            Chain.GNOSIS: GNOSIS_MARKETPLACE,
            Chain.BASE: BASE_MARKETPLACE,
            Chain.POLYGON: POLYGON_MARKETPLACE,
            Chain.OPTIMISM: OPTIMISM_MARKETPLACE,
        }
        expected_newest = {
            Chain.GNOSIS: GNOSIS_NATIVE_FACTORY_NEW,
            Chain.BASE: BASE_NATIVE_FACTORY_NEW,
            Chain.POLYGON: POLYGON_NATIVE_FACTORY_NEW,
            Chain.OPTIMISM: OPTIMISM_NATIVE_FACTORY_NEW,
        }
        for chain, marketplace in upgraded.items():
            candidates = MECH_FACTORY_ADDRESS[chain][marketplace]["Native"]
            assert len(candidates) == 2, chain
            assert candidates[0] == expected_newest[chain], chain

    def test_legacy_gnosis_marketplace_keeps_single_candidates(self) -> None:
        """The legacy Gnosis marketplace is untouched by the upgrade."""
        for candidates in MECH_FACTORY_ADDRESS[Chain.GNOSIS][
            GNOSIS_LEGACY_MARKETPLACE
        ].values():
            assert len(candidates) == 1

    def test_payment_types_cover_the_fixed_price_mech_types(self) -> None:
        """Only mech types with a chain-independent payment type are pre-checked."""
        assert set(MECH_TYPE_PAYMENT_TYPE) == {"Native", "Token", "TokenUSDC"}
        for payment_type in MECH_TYPE_PAYMENT_TYPE.values():
            assert len(payment_type) == 66
            assert int(payment_type, 16) != 0

    @pytest.mark.parametrize(
        "chain", [Chain.GNOSIS, Chain.BASE, Chain.POLYGON, Chain.OPTIMISM]
    )
    def test_shipped_template_marketplace_is_in_the_table(self, chain: Chain) -> None:
        """Each runtime template ships a marketplace address the table knows.

        :param chain: chain whose runtime config template is checked.
        """
        template = json.loads(
            (
                resources.files("mtd.templates.runtime")
                / f"config_mech_{chain.value}.json"
            ).read_text(encoding="utf-8")
        )
        configured = template["env_variables"]["MECH_MARKETPLACE_ADDRESS"]["value"]
        assert configured in MECH_FACTORY_ADDRESS[chain]


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
