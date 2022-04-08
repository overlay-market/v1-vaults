from brownie import chain
from .utils import RiskParameter


def test_ovl_fixture(ovl):
    assert ovl.decimals() == 18
    assert ovl.name() == "Overlay"
    assert ovl.symbol() == "OVL"
    assert ovl.totalSupply() == 8000000000000000000000000


def test_token_fixtures(weth):
    assert weth.name() == "Wrapped Ether"


def test_pool_fixtures(univ3_oe_pool_immutables, uni_v3_factory, weth, ovl):
    assert univ3_oe_pool_immutables.fee() == 3000
    # token0 and token1 are sorted by address
    assert univ3_oe_pool_immutables.token0() == weth
    assert univ3_oe_pool_immutables.token1() == ovl
    assert univ3_oe_pool_immutables == uni_v3_factory.getPool(ovl, weth, 3000)


def test_factory_fixture(factory, ovl, fee_recipient, market, feed_factory):
    assert factory.ovl() == ovl
    assert factory.feeRecipient() == fee_recipient

    assert factory.isFeedFactory(feed_factory) is True
    assert factory.isMarket(market) is True


def test_feed_fixture(feed, univ3_oe_pool, ovl, weth,
                      feed_factory):
    assert feed.marketPool() == univ3_oe_pool
    assert feed.ovlXPool() == univ3_oe_pool
    assert feed.ovl() == ovl
    assert feed.x() == weth
    assert feed.marketBaseAmount() == 1000000000000000000
    assert feed.marketBaseToken() == ovl
    assert feed.marketQuoteToken() == weth
    assert feed.microWindow() == 600
    assert feed.macroWindow() == 3600

    assert feed_factory.isFeed(feed) is True


def test_market_fixture(market, feed, ovl, factory, gov,
                        minter_role, burner_role):
    # check addresses set properly
    assert market.ovl() == ovl
    assert market.feed() == feed
    assert market.factory() == factory

    # risk params
    expect_params = [
        1220000000000,
        500000000000000000,
        2500000000000000,
        5000000000000000000,
        800000000000000000000000,
        5000000000000000000,
        2592000,
        66670000000000000000000,
        100000000000000000,
        100000000000000000,
        10000000000000000,
        750000000000000,
        100000000000000,
        25000000000000,
        15
    ]
    actual_params = [market.params(name.value) for name in RiskParameter]
    assert expect_params == actual_params

    # check market has minter and burner roles on ovl token
    assert ovl.hasRole(minter_role, market) is True
    assert ovl.hasRole(burner_role, market) is True

    # check oi related quantities are zero
    assert market.oiLong() == 0
    assert market.oiShort() == 0
    assert market.oiLongShares() == 0
    assert market.oiShortShares() == 0

    # check timestamp update last is same as block when market was deployed
    assert market.timestampUpdateLast() == chain[-1]["timestamp"]


def test_eth_basis_trade(eth_basis_trade, univ3_swap_router,
                         weth, ovl, univ3_oe_pool, market):
    assert eth_basis_trade.swapRouter() == univ3_swap_router
    assert eth_basis_trade.WETH9() == weth
    assert eth_basis_trade.ovl() == ovl
    assert eth_basis_trade.pool() == univ3_oe_pool
    assert eth_basis_trade.ovlMarket() == market
