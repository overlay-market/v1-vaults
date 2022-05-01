from brownie import chain, reverts
from brownie_tokens import MintableForkToken
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
def test_withdraw_modifer(eth_basis_trade, market, state, feed, weth, ovl, alice, bob, amount):
    # deposit weth
    weth.approve(eth_basis_trade.address, amount, {'from': alice})
    eth_basis_trade.depositWeth(amount, {'from': alice})
    
    # build short position so longs earn funding
    ovl.approve(market, ovl.balanceOf(alice), {'from': alice})
    market.build(10e18, 1e18, False, 0, {'from': alice})
    
    # update vault
    # should go long since funding negative after above short
    pre_update_weth_bal = weth.balanceOf(eth_basis_trade)
    eth_basis_trade.update({'from': alice})
    post_update_weth_bal = weth.balanceOf(eth_basis_trade)

    # withdraw by bob fails since not owner
    with reverts("!owner"):
        eth_basis_trade.withdraw({'from': bob})


@given(
    amount=strategy('uint256', min_value=2e14, max_value=20e18)
)
def test_withdraw_long(eth_basis_trade, market, weth, ovl, alice, amount):
    # deposit weth
    weth.approve(eth_basis_trade.address, amount, {'from': alice})
    eth_basis_trade.depositWeth(amount, {'from': alice})
    
    # build short position so longs earn funding
    ovl.approve(market, ovl.balanceOf(alice), {'from': alice})
    market.build(10e18, 1e18, False, 0, {'from': alice})
    
    # update vault
    # should go long since funding negative after above short
    eth_basis_trade.update({'from': alice})

    # withdraw
    alice_prev_bal = weth.balanceOf(alice)
    tx_wd = eth_basis_trade.withdraw({'from': alice})
    alice_post_bal = weth.balanceOf(alice)

    # test position id 1 is completely withdrawn
    assert tx_wd.events['Unwind']['positionId'] == 1
    assert tx_wd.events['Unwind']['fraction'] == 1e18

    # test contract holds no ovl or weth
    assert weth.balanceOf(eth_basis_trade) == 0
    assert ovl.balanceOf(eth_basis_trade) == 0

    # test weth transferred to alice from vault
    assert tx_wd.events['Transfer'][5]['src'] == eth_basis_trade.address
    assert tx_wd.events['Transfer'][5]['dst'] == alice.address
    assert tx_wd.events['Transfer'][5]['wad'] == alice_post_bal - alice_prev_bal


@given(
    amount=strategy('uint256', min_value=2e14, max_value=20e18)
)
def test_withdraw_idle(eth_basis_trade, market, weth, ovl, alice, amount):
    # deposit weth
    weth.approve(eth_basis_trade.address, amount, {'from': alice})
    eth_basis_trade.depositWeth(amount, {'from': alice})
    
    # build short position so longs earn funding
    ovl.approve(market, ovl.balanceOf(alice), {'from': alice})
    market.build(10e18, 1e18, False, 0, {'from': alice})
    
    # update vault
    # should go long since funding negative after above short
    eth_basis_trade.update({'from': alice})

    # build long position so shorts earn funding
    market.build(20e18, 1e18, True, 10e18, {'from': alice})

    # update vault again
    # should go idle since funding positive after above long
    eth_basis_trade.update({'from': alice})

    # withdraw in idle state
    vault_weth_bal = weth.balanceOf(eth_basis_trade)
    alice_pre_bal = weth.balanceOf(alice)
    eth_basis_trade.withdraw({'from': alice})
    alice_post_bal = weth.balanceOf(alice)

    assert vault_weth_bal == alice_post_bal - alice_pre_bal