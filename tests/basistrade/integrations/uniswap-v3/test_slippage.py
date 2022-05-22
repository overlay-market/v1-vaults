from pytest import approx
from brownie import interface
from brownie.test import given, strategy


@given(
    tick=strategy('int24', min_value=-36000, max_value=36000),
    base_amount=strategy('uint256', min_value=2e14, max_value=20e18)
)
def test_get_quote_at_tick_for_ovlweth(ovl, weth, eth_basis_trade,
                                       tick, base_amount):
    # from Uniswap whitepaper: price = 1.0001^tick
    base_token = weth
    quote_token = ovl

    # flip expect tick based off uniswap convention of base/quote if need to
    expect_sign = -1 if base_token.address > quote_token.address else 1
    expect_quote_amount = int(base_amount * 1.0001 ** (expect_sign * tick))

    actual_quote_amount = eth_basis_trade.getQuoteAtTick(
        tick, base_amount, base_token, quote_token
    )
    assert approx(expect_quote_amount) == actual_quote_amount

    base_token = ovl
    quote_token = weth

    # flip expect tick based off uniswap convention of base/quote if need to
    expect_sign = -1 if base_token.address > quote_token.address else 1
    expect_quote_amount = int(base_amount * 1.0001 ** (expect_sign * tick))

    actual_quote_amount = eth_basis_trade.getQuoteAtTick(
        tick, base_amount, base_token, quote_token
    )
    assert approx(expect_quote_amount) == actual_quote_amount


@given(
    to_ovl=strategy('bool')
)
def test_getOffsetTick(eth_basis_trade, univ3_oe_pool, to_ovl):

    pool_state = interface.IUniswapV3PoolState(univ3_oe_pool)
    _, tick, _, _, _, _, _ = pool_state.slot0()
    obs_result = eth_basis_trade.getOffsetTick(to_ovl)
    if to_ovl:
        assert obs_result == tick - 200
    else:
        assert obs_result == tick + 200
