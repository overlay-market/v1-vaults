from brownie.test import given, strategy

# `amount` range of values:
# min value: based on minCollateral setting in factory
# max value: based on spot pool liquidity as set in conftest.py
@given(
    amount=strategy('uint256', min_value=5e14, max_value=5e18)
)
def test_update_first_call(eth_basis_trade, amount, ovl, weth, alice):
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

    # call update function with `True`
    eth_basis_trade.update(True, {'from': alice})

    post_true_weth_balance = weth.balanceOf(eth_basis_trade)
    post_true_ovl_balance = ovl.balanceOf(eth_basis_trade)
    post_true_pos_id = eth_basis_trade.depositorIdPre()

    assert post_true_weth_balance == 0
    assert post_true_ovl_balance == 0
    assert post_true_pos_id == 0

    # call update function with `False`
    eth_basis_trade.update(False, {'from': alice})

    post_false_weth_balance = weth.balanceOf(eth_basis_trade)
    post_false_ovl_balance = ovl.balanceOf(eth_basis_trade)
    post_false_pos_id = eth_basis_trade.depositorIdPre()

    assert post_false_weth_balance > 0
    assert post_false_weth_balance < pre_weth_balance
    assert post_false_ovl_balance == 0
    assert post_false_pos_id == 0