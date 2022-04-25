from brownie import chain
from brownie_tokens import MintableForkToken
from brownie.test import given, strategy
import pytest

# `amount` range of values:
# min value: based on minCollateral setting in factory
# max value: based on spot pool liquidity as set in conftest.py
@given(
    amount=strategy('uint256', min_value=5e14, max_value=5e18)
)
def test_update_sets_pre_post_variables(eth_basis_trade, amount, ovl, weth, alice):
    # approve weth for spending
    weth.approve(eth_basis_trade.address, weth.balanceOf(alice), {'from': alice})
    # deposit weth to basis trade contract
    eth_basis_trade.depositWeth(amount, {'from': alice})

    pre_weth_balance = weth.balanceOf(eth_basis_trade)
    pre_ovl_balance = ovl.balanceOf(eth_basis_trade)
    pre_pos_id = eth_basis_trade.depositorIdPre()

    assert pre_weth_balance == amount
    assert pre_ovl_balance == 0
    assert pre_pos_id == 0
    assert eth_basis_trade.currState() == 0

    # call update function with `True`
    eth_basis_trade.update(True, {'from': alice})

    post_true_weth_balance = weth.balanceOf(eth_basis_trade)
    post_true_ovl_balance = ovl.balanceOf(eth_basis_trade)
    post_true_pos_id = eth_basis_trade.depositorIdPre()

    assert post_true_weth_balance == 0
    # following assertion proves that fee calc is
    # working fine since all the OVL got used
    assert post_true_ovl_balance == 0 
    assert post_true_pos_id == 0
    assert eth_basis_trade.currState() == 1

    # call update function with `False`
    eth_basis_trade.update(False, {'from': alice})

    post_false_weth_balance = weth.balanceOf(eth_basis_trade)
    post_false_ovl_balance = ovl.balanceOf(eth_basis_trade)
    post_false_pos_id = eth_basis_trade.depositorIdPre()

    assert post_false_weth_balance > 0
    assert post_false_weth_balance < pre_weth_balance
    assert post_false_ovl_balance == 0
    assert post_false_pos_id == 0
    assert eth_basis_trade.currState() == 0



@given(
    amount1=strategy('uint256', min_value=5e14, max_value=5e18),
    amount2=strategy('uint256', min_value=5e14, max_value=5e18),
)
def test_update_splits_pnl(eth_basis_trade,
                           ovl,
                           market,
                           weth,
                           alice,
                           bob,
                           rando1,
                           rando2,
                           amount1,
                           amount2):
    
    # test when basis trade is LOSS making
    weth_token = MintableForkToken(weth.address)
    weth_token._mint_for_testing(rando1, amount1)
    weth.approve(eth_basis_trade.address, weth.balanceOf(alice), {'from': alice})
    weth.approve(eth_basis_trade.address, weth.balanceOf(rando1), {'from': rando1})
    eth_basis_trade.depositWeth(amount2, {'from': alice})
    eth_basis_trade.depositWeth(amount1, {'from': rando1})

    eth_basis_trade.update(True, {'from': alice})
    
    eth_basis_trade.update(False, {'from': alice})
    post_false_amount = eth_basis_trade.totalPre()

    indiv_amount = eth_basis_trade.depositorInfoPre(alice) + eth_basis_trade.depositorInfoPre(rando1)
    assert indiv_amount <= post_false_amount # sum of indiv should never be greater than total
    assert pytest.approx(indiv_amount) == post_false_amount # yet, should be ~equal to total

    # test when basis trade is PROFIT making
    weth_token._mint_for_testing(rando2, amount1)
    weth.approve(eth_basis_trade.address, weth.balanceOf(bob), {'from': bob})
    weth.approve(eth_basis_trade.address, weth.balanceOf(rando2), {'from': rando2})

    # add some more depositors (cuz why not?)
    eth_basis_trade.depositWeth(amount2, {'from': bob})
    eth_basis_trade.depositWeth(amount1, {'from': rando2})

    pre_trade_amount = eth_basis_trade.totalPre()

    # call update with true
    eth_basis_trade.update(True, {'from': bob})

    # approval for building position on overlay
    ovl.approve(market, ovl.balanceOf(bob), {'from': bob})
    # build short positions so long position of vault earns funding
    market.build(40e18, 1e18, False, 0, {'from': bob})
    chain.mine(timedelta=120*60*60)
    market.build(25e18, 1e18, False, 0, {'from': bob})
    chain.mine(timedelta=120*60*60)
    
    # call update with false
    eth_basis_trade.update(False, {'from': bob})
    post_false_amount = eth_basis_trade.totalPre()

    indiv_amount = eth_basis_trade.depositorInfoPre(alice) + eth_basis_trade.depositorInfoPre(rando1)\
                   + eth_basis_trade.depositorInfoPre(bob) + eth_basis_trade.depositorInfoPre(rando2)
    
    assert pre_trade_amount < post_false_amount # makes sure basis trade is profit making
    assert indiv_amount <= post_false_amount # sum of indiv should never be greater than total
    assert pytest.approx(indiv_amount) == post_false_amount # yet, should be ~equal to total


@given(
    amount1=strategy('uint256', min_value=5e14, max_value=5e18),
    amount2=strategy('uint256', min_value=5e14, max_value=5e18),
    amount3=strategy('uint256', min_value=5e14, max_value=5e18),
    amount4=strategy('uint256', min_value=5e14, max_value=5e18),
)
def test_update_splits_pnl_for_deposits_made_post_update(eth_basis_trade,
                                                         ovl,
                                                         univ3_oe_pool,
                                                         market,
                                                         weth,
                                                         alice,
                                                         bob,
                                                         rando1,
                                                         rando2,
                                                         amount1,
                                                         amount2,
                                                         amount3,
                                                         amount4):
    weth_token = MintableForkToken(weth.address)
    weth_token._mint_for_testing(rando1, amount1)
    weth_token._mint_for_testing(rando2, amount2)
    weth.approve(eth_basis_trade.address, weth.balanceOf(alice), {'from': alice})
    weth.approve(eth_basis_trade.address, weth.balanceOf(rando1), {'from': rando1})
    weth.approve(eth_basis_trade.address, weth.balanceOf(rando2), {'from': rando2})
    weth.approve(eth_basis_trade.address, weth.balanceOf(bob), {'from': bob})
    eth_basis_trade.depositWeth(amount1, {'from': rando1})
    eth_basis_trade.depositWeth(amount2, {'from': rando2})

    # call update with True
    tx_true = eth_basis_trade.update(True, {'from': rando1})

    assert eth_basis_trade.depositorAddressPre(0) == rando1.address
    assert eth_basis_trade.depositorAddressPre(1) == rando2.address
    assert eth_basis_trade.getDepositorAddressPreLength() == 2

    og_deposit_rando1 = eth_basis_trade.depositorInfoPre(rando1)
    og_deposit_rando2 = eth_basis_trade.depositorInfoPre(rando2)
    total = og_deposit_rando1 + og_deposit_rando2
    assert pytest.approx(total) == eth_basis_trade.totalPre()

    # new depositors to vault
    eth_basis_trade.depositWeth(amount3, {'from': alice})
    og_deposit_alice = eth_basis_trade.depositorInfoPost(alice)[0]
    assert og_deposit_alice == amount3
    assert eth_basis_trade.depositorAddressPost(0) == alice.address
    eth_basis_trade.depositWeth(amount4, {'from': bob})
    og_deposit_bob = eth_basis_trade.depositorInfoPost(bob)[0]
    assert og_deposit_bob == amount4
    assert eth_basis_trade.depositorAddressPost(1) == bob.address

    # build positions on overlay so funding is earned by vault depositors
    ovl.approve(market, ovl.balanceOf(bob), {'from': bob})
    market.build(100e18, 1e18, False, 0, {'from': bob})
    chain.mine(timedelta=240*60*60)
    market.build(50e18, 1e18, False, 0, {'from': bob})
    chain.mine(timedelta=120*60*60)
    
    # call update with False
    tx_false = eth_basis_trade.update(False, {'from': alice})

    # check whether depositor array updated
    assert eth_basis_trade.depositorAddressPre(0) == rando1.address
    assert eth_basis_trade.depositorAddressPre(1) == rando2.address
    assert eth_basis_trade.depositorAddressPre(2) == alice.address
    assert eth_basis_trade.depositorAddressPre(3) == bob.address
    assert eth_basis_trade.getDepositorAddressPreLength() == 4

    # check if total adds up
    total_new = eth_basis_trade.depositorInfoPre(rando1)\
                + eth_basis_trade.depositorInfoPre(rando2)\
                + eth_basis_trade.depositorInfoPre(alice)\
                + eth_basis_trade.depositorInfoPre(bob)
    
    assert pytest.approx(total_new) == eth_basis_trade.totalPre()
    assert total_new < eth_basis_trade.totalPre()

    # check contract has at least as many as totalPre weth
    assert weth.balanceOf(eth_basis_trade) >= eth_basis_trade.totalPre()
    
    # check if each depositor made a profit as expected
    assert og_deposit_rando1 < eth_basis_trade.depositorInfoPre(rando1)
    assert og_deposit_rando2 < eth_basis_trade.depositorInfoPre(rando2)
    assert og_deposit_alice < eth_basis_trade.depositorInfoPre(alice)
    assert og_deposit_bob < eth_basis_trade.depositorInfoPre(bob)

# def test_update_splits_pnl_after_withdraw():

# def test_update_builds_and_unwinds_expected_amounts():


