from brownie import reverts
from brownie.test import given, strategy
import pytest


# NOTE: Tests passing with isolation fixture
# TODO: Fix tests to pass even without isolation fixture (?)
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


@given(
    amount=strategy('uint256', min_value=2e14, max_value=20e18)
)
def test_onlyOwner(eth_basis_trade, alice, bob, ovl, amount):
    # transfer ovl to eth_basis_trade
    ovl.approve(eth_basis_trade.address, amount, {'from': alice})
    ovl.transfer(eth_basis_trade, amount, {'from': alice})

    eth_basis_trade.buildOvlPosition(amount, 10e18, {'from': alice})
    eth_basis_trade.unwindOvlPosition(0, 1e18, 0, {'from': alice})

    with reverts('!owner'):
        eth_basis_trade.unwindOvlPosition(0, 1e18, 0, {'from': bob})


# min value decided based on min position size for market
# max value limited to 20e18 to allow swapping within 2% slippage
@given(
    amount=strategy('uint256', min_value=2e14, max_value=20e18)
)
def test_pos_unwind_as_expected(mock_eth_basis_trade, mock_market,
                                state, mock_feed, weth, ovl,
                                alice, amount):
    # transfer ovl to eth_basis_trade
    ovl.approve(mock_eth_basis_trade.address, amount, {'from': alice})
    ovl.transfer(mock_eth_basis_trade, amount, {'from': alice})

    # build position
    tx = mock_eth_basis_trade.buildOvlPosition(amount, 10e18, {'from': alice})

    # set price on mock feed
    build_price = tx.events['Build']['price']
    mock_feed.setPrice(1.1*build_price, {"from": alice})

    # get position stats expected
    exp_value = state.value(mock_market, mock_eth_basis_trade, 0)
    exp_cost = state.cost(mock_market, mock_eth_basis_trade, 0)
    exp_mint = exp_value - exp_cost
    oi = state.oi(mock_market, mock_eth_basis_trade, 0)
    fraction_oi = state.fractionOfCapOi(mock_market, oi)
    exp_price = state.bid(mock_market, fraction_oi)

    # unwind position
    tx_unwind = mock_eth_basis_trade.unwindOvlPosition(
                                        0, 1e18, 0, {'from': alice})
    unw_events = tx_unwind.events['Unwind']
    assert unw_events['sender'] == mock_eth_basis_trade
    assert unw_events['positionId'] == 0
    assert unw_events['fraction'] == 1e18
    assert pytest.approx(unw_events['mint'], rel=1e-4) == exp_mint
    assert pytest.approx(unw_events['price'], rel=1e-4) == exp_price
