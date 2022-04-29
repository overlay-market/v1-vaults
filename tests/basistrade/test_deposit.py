from brownie_tokens import MintableForkToken
from brownie.test import given, strategy


@given(
    amount=strategy('uint256', min_value=1e14, max_value=100000e18)
)
def test_deposit(rando1, eth_basis_trade, weth, amount):
    # mint weth token to rando1's address
    weth_token = MintableForkToken(weth.address)
    weth_token._mint_for_testing(rando1, amount)
    rando1_initial_balance = weth.balanceOf(rando1)
    # approve weth for spending
    weth.approve(eth_basis_trade.address, amount, {'from': rando1})
    # deposit weth to basis trade contract
    eth_basis_trade.depositWeth(amount, {'from': rando1})
    # tests
    assert weth.balanceOf(eth_basis_trade) == rando1_initial_balance
