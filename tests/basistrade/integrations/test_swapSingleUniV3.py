from brownie import reverts
from brownie.test import given, strategy


@given(
    amount=strategy('uint256', min_value=2e14, max_value=20e18)
)
def test_onlyOwner(eth_basis_trade, alice, bob, weth, amount):
    # deposit weth
    weth.approve(eth_basis_trade.address, amount, {'from': alice})
    eth_basis_trade.depositWeth(amount, {'from': alice})

    eth_basis_trade.swapSingleUniV3(amount/2, False, {'from': alice})

    with reverts('!owner'):
        eth_basis_trade.swapSingleUniV3(amount/2, False, {'from': bob})


@given(
    amount=strategy('uint256', min_value=2e14, max_value=20e18)
)
def test_swap_amounts(eth_basis_trade, ovl, weth, alice,
                      univ3_oe_pool, amount):
    # deposit weth
    weth.approve(eth_basis_trade.address, amount, {'from': alice})
    eth_basis_trade.depositWeth(amount, {'from': alice})

    # test weth to ovl swap
    weth_res_pre = weth.balanceOf(univ3_oe_pool)
    ovl_res_pre = ovl.balanceOf(univ3_oe_pool)

    eth_basis_trade.swapSingleUniV3(amount, False, {'from': alice})

    weth_res_post = weth.balanceOf(univ3_oe_pool)
    ovl_res_post = ovl.balanceOf(univ3_oe_pool)

    ovl_bal = ovl.balanceOf(eth_basis_trade)

    assert amount == weth_res_post - weth_res_pre
    assert ovl_bal == ovl_res_pre - ovl_res_post

    # test ovl to weth swap
    weth_res_pre = weth.balanceOf(univ3_oe_pool)
    ovl_res_pre = ovl.balanceOf(univ3_oe_pool)

    eth_basis_trade.swapSingleUniV3(ovl_bal, True, {'from': alice})

    weth_res_post = weth.balanceOf(univ3_oe_pool)
    ovl_res_post = ovl.balanceOf(univ3_oe_pool)

    assert ovl_bal == ovl_res_post - ovl_res_pre
    assert weth.balanceOf(eth_basis_trade) == weth_res_pre - weth_res_post


def test_swap_slippage_weth_to_ovl(eth_basis_trade, ovl,
                                   weth, alice, univ3_oe_pool):

    # successful swap
    weth_res_pre = weth.balanceOf(univ3_oe_pool)
    ovl_res_pre = ovl.balanceOf(univ3_oe_pool)
    k = weth_res_pre * ovl_res_pre

    # calc amount resulting in 2% price impact
    amount = (k/(0.98 * weth_res_pre)) - ovl_res_pre

    # deposit weth
    weth.approve(eth_basis_trade.address, amount, {'from': alice})
    eth_basis_trade.depositWeth(amount, {'from': alice})

    # swap successful since within 2% slippage
    eth_basis_trade.swapSingleUniV3(amount, False, {'from': alice})

    # failing swap
    weth_res_pre = weth.balanceOf(univ3_oe_pool)
    ovl_res_pre = ovl.balanceOf(univ3_oe_pool)
    k = weth_res_pre * ovl_res_pre

    # calc amount resulting in >2% price impact
    amount = (k/(0.979 * weth_res_pre)) - ovl_res_pre

    # deposit weth
    weth.approve(eth_basis_trade.address, amount, {'from': alice})
    eth_basis_trade.depositWeth(amount, {'from': alice})

    # swap fails because >2% slippage
    with reverts('Too little received'):
        eth_basis_trade.swapSingleUniV3(amount, False, {'from': alice})


def test_swap_slippage_ovl_to_weth(eth_basis_trade, ovl,
                                   weth, alice, univ3_oe_pool):

    # successful swap
    weth_res_pre = weth.balanceOf(univ3_oe_pool)
    ovl_res_pre = ovl.balanceOf(univ3_oe_pool)
    k = weth_res_pre * ovl_res_pre

    # calc amount resulting in 2% price impact
    amount = (k/(0.98 * ovl_res_pre)) - weth_res_pre

    # transfer ovl to eth_basis_trade to swap it later
    ovl.approve(eth_basis_trade.address, amount, {'from': alice})
    ovl.transfer(eth_basis_trade, amount, {'from': alice})

    # swap successful since within 2% slippage
    eth_basis_trade.swapSingleUniV3(amount, True, {'from': alice})

    # failing swap
    weth_res_pre = weth.balanceOf(univ3_oe_pool)
    ovl_res_pre = ovl.balanceOf(univ3_oe_pool)
    k = weth_res_pre * ovl_res_pre

    # calc amount resulting in >2% price impact
    amount = (k/(0.979 * ovl_res_pre)) - weth_res_pre

    # transfer ovl to eth_basis_trade to swap it later
    ovl.approve(eth_basis_trade.address, amount, {'from': alice})
    ovl.transfer(eth_basis_trade, amount, {'from': alice})

    # swap fails because >2% slippage
    with reverts('Too little received'):
        eth_basis_trade.swapSingleUniV3(amount, True, {'from': alice})
