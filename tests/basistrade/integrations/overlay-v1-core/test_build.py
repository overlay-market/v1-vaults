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

    with reverts('!owner'):
        eth_basis_trade.buildOvlPosition(amount, 10e18, {'from': bob})


# min value decided based on min position size for market
# max value limited to 20e18 to allow swapping within 2% slippage
@given(
    amount=strategy('uint256', min_value=2e14, max_value=20e18)
)
def test_build_fees(eth_basis_trade, ovl, alice, amount):

    # transfer ovl to eth_basis_trade
    ovl.approve(eth_basis_trade.address, amount, {'from': alice})
    ovl.transfer(eth_basis_trade, amount, {'from': alice})

    # build position
    tx_build = eth_basis_trade.buildOvlPosition(amount, 10e18, {'from': alice})

    tot_amount_transferred = tx_build.events['Transfer'][0]['value']
    assert pytest.approx(tot_amount_transferred) == amount

    fees_exp = eth_basis_trade.getOverlayTradingFee(amount)[1]
    fees_obs = tx_build.events['Transfer'][1]['value']
    assert fees_exp == fees_obs

    tfr = 750000000000000
    col_calc = amount/(1e18 + tfr)
    fees_calc = col_calc * tfr

    assert pytest.approx(fees_calc) == fees_obs


# min value decided based on min position size for market
# max value limited to 20e18 to allow swapping within 2% slippage
@given(
    amount=strategy('uint256', min_value=2e14, max_value=20e18)
)
def test_pos_built_as_expected(eth_basis_trade, market, state,
                               ovl, alice, amount):

    # transfer ovl to eth_basis_trade
    ovl.approve(eth_basis_trade.address, amount, {'from': alice})
    ovl.transfer(eth_basis_trade, amount, {'from': alice})

    # get position stats expected
    collateral = eth_basis_trade.getOverlayTradingFee(amount)[0]
    mid_price = state.mid(market)
    exp_oi = (collateral/mid_price) * 1e18
    fraction_oi = state.fractionOfCapOi(market, exp_oi)
    exp_price = state.ask(market, fraction_oi)

    # build position
    tx_build = eth_basis_trade.buildOvlPosition(amount, 10e18, {'from': alice})

    assert tx_build.events['Build']['sender'] == eth_basis_trade
    assert tx_build.events['Build']['positionId'] == 0
    assert pytest.approx(tx_build.events['Build']['oi']) == exp_oi
    assert tx_build.events['Build']['debt'] == 0
    assert tx_build.events['Build']['isLong'] is True
    assert pytest.approx(tx_build.events['Build']['price']) == exp_price
