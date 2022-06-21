from brownie import reverts
from brownie.test import given, strategy
import pytest


# NOTE: Tests passing with isolation fixture
# TODO: Fix tests to pass even without isolation fixture (?)
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


# min value decided based on min position size for market
# max value limited to 20e18 to allow swapping within 2% slippage
@given(
    amount=strategy('uint256', min_value=2e14, max_value=20e18)
)
def test_update(eth_basis_trade, market, state, feed,
                weth, ovl, alice, amount):
    # deposit weth
    weth.approve(eth_basis_trade.address, amount, {'from': alice})
    eth_basis_trade.depositWeth(amount, {'from': alice})

    # test doesn't unwind when already idle and funding is 0
    with reverts("Already idle"):
        eth_basis_trade.update({'from': alice})

    # build short position so longs earn funding
    ovl.approve(market, ovl.balanceOf(alice), {'from': alice})
    market.build(10e18, 1e18, False, 0, {'from': alice})

    # update vault
    # should go long since funding negative after above short
    pre_update_weth_bal = weth.balanceOf(eth_basis_trade)
    eth_basis_trade.update({'from': alice})
    post_update_weth_bal = weth.balanceOf(eth_basis_trade)

    # test all weth got swapped out
    assert pre_update_weth_bal == amount
    assert post_update_weth_bal == 0

    # test all ovl obtained from swapping got used in building pos
    assert ovl.balanceOf(eth_basis_trade) <= 9

    # test vault holds position
    pos_id = eth_basis_trade.posId()
    assert pos_id == 1
    assert state.position(market, eth_basis_trade, pos_id)[0] > 0

    # build long position so shorts earn funding
    market.build(20e18, 1e18, True, 10e18, {'from': alice})

    # update vault
    # should go idle since funding positive after above long
    tx_idle = eth_basis_trade.update({'from': alice})

    # check if position id 1 got unwound completely
    assert tx_idle.events['Unwind']['positionId'] == 1
    assert tx_idle.events['Unwind']['fraction'] == 1e18

    # test vault swapped out all ovl obtained from unwind
    assert ovl.balanceOf(eth_basis_trade) == 0

    # test vault holds weth
    assert weth.balanceOf(eth_basis_trade) > 0
