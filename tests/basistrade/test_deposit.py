from brownie import reverts
from brownie_tokens import MintableForkToken
from brownie.test import given, strategy


@given(
    amount=strategy('uint256', min_value=1e14, max_value=100000e18)
)
def test_deposit(alice, bob, eth_basis_trade, weth, amount):
    # mint weth token to alice's address
    weth_token = MintableForkToken(weth.address)
    weth_token._mint_for_testing(alice, amount)
    # approve weth for spending
    weth.approve(eth_basis_trade.address, amount, {'from': alice})
    # deposit weth to basis trade contract
    eth_basis_trade.depositWeth(amount, {'from': alice})
    # tests
    assert weth.balanceOf(eth_basis_trade) == amount
    
    # bob's deposit should revert since not owner
    weth_token._mint_for_testing(bob, amount)
    weth.approve(eth_basis_trade.address, amount, {'from': bob})
    with reverts("!owner"):
        eth_basis_trade.depositWeth(amount, {'from': bob})
