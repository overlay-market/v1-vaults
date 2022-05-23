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
def test_pos_unwind_as_expected(eth_basis_trade, market, state, feed,
                                weth, ovl, alice, amount):
    # transfer ovl to eth_basis_trade
    ovl.approve(eth_basis_trade.address, amount, {'from': alice})
    ovl.transfer(eth_basis_trade, amount, {'from': alice})

    # build position
    eth_basis_trade.buildOvlPosition(amount, 10e18, {'from': alice})

    # get position stats expected
    exp_value = state.value(market, eth_basis_trade, 0)
    exp_cost = state.cost(market, eth_basis_trade, 0)
    exp_mint = exp_value - exp_cost
    oi = state.oi(market, eth_basis_trade, 0)
    fraction_oi = state.fractionOfCapOi(market, oi)
    exp_price = state.bid(market, fraction_oi)

    # unwind position
    tx_unwind = eth_basis_trade.unwindOvlPosition(0, 1e18, 0, {'from': alice})

    assert tx_unwind.events['Unwind']['sender'] == eth_basis_trade
    assert tx_unwind.events['Unwind']['positionId'] == 0
    assert tx_unwind.events['Unwind']['fraction'] == 1e18
    assert pytest.approx(tx_unwind.events['Unwind']['mint']) == exp_mint
    assert pytest.approx(tx_unwind.events['Unwind']['price']) == exp_price
