import pytest
from brownie import interface, chain, Contract
from brownie import EthBasisTrade, TestMintRouter, web3
from brownie_tokens import MintableForkToken
import numpy as np


@pytest.fixture(scope="module")
def ovl_v1_core(pm):
    return pm("overlay-market/v1-core@1.0.0-beta.2")


@pytest.fixture(scope="module")
def ovl_v1_periphery(pm):
    return pm("overlay-market/v1-periphery@1.0.0-beta.3")


@pytest.fixture(scope="module")
def gov(accounts):
    yield accounts[0]


@pytest.fixture(scope="module")
def alice(accounts):
    yield accounts[1]


@pytest.fixture(scope="module")
def bob(accounts):
    yield accounts[2]


@pytest.fixture(scope="module")
def rando1(accounts):
    yield accounts[3]


@pytest.fixture(scope="module")
def rando2(accounts):
    yield accounts[4]


@pytest.fixture(scope="module")
def fee_recipient(accounts):
    yield accounts[4]


@pytest.fixture(scope="module")
def minter_role():
    yield web3.solidityKeccak(['string'], ["MINTER"])


@pytest.fixture(scope="module")
def burner_role():
    yield web3.solidityKeccak(['string'], ["BURNER"])


@pytest.fixture(scope="module")
def governor_role():
    yield web3.solidityKeccak(['string'], ["GOVERNOR"])


@pytest.fixture(scope="module", params=[8000000])
def create_token(ovl_v1_core, gov, alice, bob, request):
    sup = request.param

    def create_token(supply=sup):
        ovl = ovl_v1_core.OverlayV1Token
        tok = gov.deploy(ovl)
        tok.mint(gov, supply * 10 ** tok.decimals(), {"from": gov})
        tok.transfer(alice, (supply/2) * 10 ** tok.decimals(), {"from": gov})
        tok.transfer(bob, (supply/2) * 10 ** tok.decimals(), {"from": gov})
        return tok

    yield create_token


@pytest.fixture(scope="module")
def ovl(create_token):
    yield create_token()


def load_contract(address, load=False):
    if load:
        return Contract.from_explorer(address)
    else:
        try:
            return Contract(address)
        except ValueError:
            return Contract.from_explorer(address)


@pytest.fixture(scope="module")
def dai():
    yield load_contract("0x6B175474E89094C44Da98b954EedeAC495271d0F")


@pytest.fixture(scope="module")
def weth():
    yield load_contract("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2")


@pytest.fixture(scope="module", params=[(400000*1e18)])
def alice_weth(alice, weth, request):
    amount = request.param
    weth_token = MintableForkToken(weth.address)
    weth_token._mint_for_testing(alice, amount)
    yield alice


@pytest.fixture(scope="module", params=[(400000*1e18)])
def bob_weth(bob, weth, request):
    amount = request.param
    weth_token = MintableForkToken(weth.address)
    weth_token._mint_for_testing(bob, amount)
    yield bob


@pytest.fixture(scope="module")
def uni_v3_factory():
    yield load_contract("0x1F98431c8aD98523631AE4a59f267346ea31F984")


@pytest.fixture(scope="module", params=[(3000)])
def create_univ3_oe_pool(alice, ovl, weth, uni_v3_factory, request,
                         alice_weth, bob_weth, mint_router):
    fees = request.param

    def create_univ3_oe_pool(owner=alice, token_a=ovl,
                             token_b=weth, fee=fees):
        # deploy OVL/WETH pool
        tx = interface\
                .IUniswapV3Factory(uni_v3_factory.address)\
                .createPool(token_a, token_b, fee, {"from": owner})
        pool = interface.IUniswapV3PoolActions(tx.return_value)
        # initialize pool with initial price. 1 WETH ~= 1 OVL
        pool.initialize(7.9220240490215315e28, {"from": owner})
        # tx to increase cardinality errors with "timeout" under
        # default settings. therefore changed `timeout` setting in
        # network_config.yaml for mainnet-fork to 180 (default: 120)
        pool.increaseObservationCardinalityNext(310, {"from": owner})
        return pool

    yield create_univ3_oe_pool


@pytest.fixture(scope="module")
def init_univ3_oe_pool(create_univ3_oe_pool):
    yield create_univ3_oe_pool()


@pytest.fixture(scope="module", params=[(1000e18, -36000, 36000)])
def pool_w_lps(init_univ3_oe_pool, weth, ovl, alice_weth,
               bob_weth, mint_router, request):
    amount, tick_lower, tick_upper = request.param
    # approve weth and ovl spending to pool contract
    weth.approve(mint_router.address,
                 weth.balanceOf(alice_weth), {'from': alice_weth})
    ovl.approve(mint_router.address,
                ovl.balanceOf(alice_weth), {'from': alice_weth})
    weth.approve(mint_router.address,
                 weth.balanceOf(bob_weth), {'from': bob_weth})
    ovl.approve(mint_router.address,
                ovl.balanceOf(bob_weth), {'from': bob_weth})
    # provide liquidity
    mint_router.mint(init_univ3_oe_pool.address, tick_lower, tick_upper,
                     amount, {"from": alice_weth})
    mint_router.mint(init_univ3_oe_pool.address, tick_lower, tick_upper,
                     amount, {"from": bob_weth})
    yield init_univ3_oe_pool


@pytest.fixture(scope="module", params=[(1e17, 9e17, 1e16, 80, 90)])
def pool_w_swaps(pool_w_lps, mint_router, alice, bob, request):
    start, stop, step, num_swaps, lag = request.param
    # define func for swaps. lag between swaps so 1h TWAP is possible
    sz_rng = np.arange(start, stop, step=step)
    adds = [alice, bob]
    def swap(pool=pool_w_lps, size_range=sz_rng, addresses=adds,
             num_of_swaps=num_swaps, lag=lag):
        for i in range(num_of_swaps):
            size = np.random.choice(size_range, size=1)[0]
            addr = np.random.choice(addresses, size=1)[0]
            zero_or_one = np.random.choice([True, False], size=1)[0]
            if zero_or_one:
                # tried to use zero_or_one as an input to `swap` but was
                # erroring with: Cannot convert bool_ 'False' to bool
                mint_router.swap(pool, True, size, {'from': addr})
            else:
                mint_router.swap(pool, False, size, {'from': addr})
            chain.mine(timedelta=lag)
            print(f'Executing swap number: {i}')
        return pool
    yield swap


@pytest.fixture(scope="module")
def univ3_oe_pool(pool_w_swaps):
    yield pool_w_swaps()


@pytest.fixture(scope="module")
def univ3_oe_pool_immutables(univ3_oe_pool):
    yield interface.IUniswapV3PoolImmutables(univ3_oe_pool.address)


@pytest.fixture(scope="module")
def mint_router(gov):
    yield gov.deploy(TestMintRouter)


@pytest.fixture(scope="module")
def univ3_swap_router():
    yield load_contract("0xE592427A0AEce92De3Edee1F18E0157C05861564", True)


@pytest.fixture(scope="module", params=[(600, 3600, 300, 15)])
def create_feed_factory(ovl_v1_core, gov, ovl, univ3_oe_pool,
                        uni_v3_factory, request):

    micro, macro, observation_cardinality_min, avg_block_time = request.param

    def create_feed_factory():
        # deploy feed factory
        ovl_uni_feed_factory = ovl_v1_core.OverlayV1UniswapV3Factory
        feed_factory = gov.deploy(ovl_uni_feed_factory, ovl, uni_v3_factory,
                                  micro, macro,
                                  observation_cardinality_min,
                                  avg_block_time)
        return feed_factory

    yield create_feed_factory


@pytest.fixture(scope="module")
def feed_factory(create_feed_factory):
    yield create_feed_factory()


@pytest.fixture(scope="module")
def create_feed(ovl_v1_core, feed_factory, weth, ovl, alice):
    def create_feed():
        market_base_token = ovl
        market_quote_token = weth
        ovlweth_base_token = weth
        ovlweth_quote_token = ovl
        market_fee = 3000
        market_base_amount = 1000000000000000000  # 1e18

        tx = feed_factory.deployFeed(market_base_token,
                                     market_quote_token,
                                     market_fee,
                                     market_base_amount,
                                     ovlweth_base_token,
                                     ovlweth_quote_token,
                                     market_fee,
                                     {"from": alice})
        feed_addr = tx.return_value
        return ovl_v1_core.OverlayV1UniswapV3Feed.at(feed_addr)

    yield create_feed


@pytest.fixture(scope="module")
def feed(create_feed):
    yield create_feed()


@pytest.fixture(scope="module", params=[(
    1220000000000,  # k
    500000000000000000,  # lmbda
    2500000000000000,  # delta
    5000000000000000000,  # capPayoff
    800000000000000000000000,  # capNotional
    5000000000000000000,  # capLeverage
    2592000,  # circuitBreakerWindow
    66670000000000000000000,  # circuitBreakerMintTarget
    100000000000000000,  # maintenanceMarginFraction
    100000000000000000,  # maintenanceMarginBurnRate
    10000000000000000,  # liquidationFeeRate
    750000000000000,  # tradingFeeRate
    100000000000000,  # minCollateral
    25000000000000,  # priceDriftUpperLimit
    15,  # averageBlockTime
)])
def create_factory(ovl_v1_core, gov, fee_recipient, ovl, feed_factory, feed,
                   governor_role, request):
    params = request.param

    def create_factory(tok=ovl, recipient=fee_recipient, risk_params=params):
        ovl_factory = ovl_v1_core.OverlayV1Factory

        # create the market factory
        factory = gov.deploy(ovl_factory, tok, recipient)

        # grant market factory token admin role
        tok.grantRole(tok.DEFAULT_ADMIN_ROLE(), factory, {"from": gov})

        # grant gov the governor role on token to access factory methods
        tok.grantRole(governor_role, gov, {"from": gov})

        # add feed factory as approved for market factory to deploy markets on
        factory.addFeedFactory(feed_factory, {"from": gov})

        # deploy a market on feed
        factory.deployMarket(feed_factory, feed, risk_params, {"from": gov})

        return factory

    yield create_factory


@pytest.fixture(scope="module")
def factory(create_factory):
    yield create_factory()


@pytest.fixture(scope="module")
def market(ovl_v1_core, gov, feed, factory):
    market_addr = factory.getMarket(feed)
    market = ovl_v1_core.OverlayV1Market.at(market_addr)
    yield market


@pytest.fixture(scope="module")
def create_state(alice, ovl_v1_periphery):
    def create_state(factory, deployer=alice):
        state = deployer.deploy(ovl_v1_periphery.OverlayV1State, factory)
        return state
    yield create_state


@pytest.fixture(scope="module")
def state(create_state, factory):
    yield create_state(factory)


@pytest.fixture(scope="module")
def create_eth_basis_trade(univ3_swap_router, weth, ovl,
                           univ3_oe_pool, market, alice, state):

    def create_eth_basis_trade(
                        swap_router=univ3_swap_router.address,
                        weth=weth.address,
                        ovl=ovl.address,
                        pool=univ3_oe_pool.address,
                        mrkt=market.address,
                        st=state.address
                        ):
        basistrade = alice.deploy(EthBasisTrade, swap_router,
                                  weth, ovl, pool, mrkt, st)
        return basistrade
    yield create_eth_basis_trade


@pytest.fixture(scope="module")
def eth_basis_trade(create_eth_basis_trade):
    yield create_eth_basis_trade()
