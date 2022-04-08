from brownie import chain


def test_ovl_fixture(ovl):
    assert ovl.decimals() == 18
    assert ovl.name() == "Overlay"
    assert ovl.symbol() == "OVL"
    assert ovl.totalSupply() == 8000000000000000000000000


def test_factory_fixture(factory, ovl, fee_recipient, market, feed_factory):
    assert factory.ovl() == ovl
    assert factory.feeRecipient() == fee_recipient

    assert factory.isFeedFactory(feed_factory) is True
    assert factory.isMarket(market) is True


def test_feed_fixture(feed, feed_factory):
    assert feed.microWindow() == 600
    assert feed.macroWindow() == 3600
    assert feed_factory.isFeed(feed) is True


def test_market_fixture(market, feed, ovl, factory, gov):
    # check addresses set properly
    assert market.ovl() == ovl
    assert market.feed() == feed
    assert market.factory() == factory

    # risk params
    assert market.k() == 1220000000000
    assert market.lmbda() == 500000000000000000
    assert market.delta() == 2500000000000000
    assert market.capPayoff() == 5000000000000000000
    assert market.capNotional() == 800000000000000000000000
    assert market.capLeverage() == 5000000000000000000
    assert market.circuitBreakerWindow() == 2592000
    assert market.circuitBreakerMintTarget() == 66670000000000000000000
    assert market.maintenanceMarginFraction() == 100000000000000000
    assert market.maintenanceMarginBurnRate() == 100000000000000000
    assert market.liquidationFeeRate() == 10000000000000000
    assert market.tradingFeeRate() == 750000000000000
    assert market.minCollateral() == 100000000000000
    assert market.priceDriftUpperLimit() == 25000000000000

    # check market has minter and burner roles on ovl token
    assert ovl.hasRole(ovl.MINTER_ROLE(), market) is True
    assert ovl.hasRole(ovl.BURNER_ROLE(), market) is True

    # check oi related quantities are zero
    assert market.oiLong() == 0
    assert market.oiShort() == 0
    assert market.oiLongShares() == 0
    assert market.oiShortShares() == 0

    # check no positions exist
    assert market.nextPositionId() == 0

    # check timestamp update last is same as block when market was deployed
    assert market.timestampUpdateLast() == chain[-1]["timestamp"]


def test_eth_basis_trade(eth_basis_trade, univ3_swap_router,
                         weth, ovl, univ3_oe_pool, market):
    assert eth_basis_trade.swapRouter() == univ3_swap_router
    assert eth_basis_trade.WETH9() == weth
    assert eth_basis_trade.ovl() == ovl
    assert eth_basis_trade.pool() == univ3_oe_pool
    assert eth_basis_trade.ovlMarket() == market
