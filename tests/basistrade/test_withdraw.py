from brownie import chain
from brownie_tokens import MintableForkToken
from brownie.test import given, strategy
import pytest
import brownie


# NOTE: Tests passing with isolation fixture
# TODO: Fix tests to pass even without isolation fixture (?)
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


@given(
    amount1=strategy('uint256', min_value=5e14, max_value=5e18),
    amount2=strategy('uint256', min_value=5e14, max_value=5e18),
    amount3=strategy('uint256', min_value=5e14, max_value=5e18),
    amount4=strategy('uint256', min_value=5e14, max_value=5e18),
)
def test_withdraw_idle(eth_basis_trade, weth, alice, bob,
                       rando1, rando2, amount1, amount2, amount3):

    weth_token = MintableForkToken(weth.address)
    weth_token._mint_for_testing(rando1, amount1)
    weth_token._mint_for_testing(rando2, amount2 + amount3)
    weth.approve(eth_basis_trade.address, weth.balanceOf(alice), {'from': alice})
    weth.approve(eth_basis_trade.address, weth.balanceOf(rando1), {'from': rando1})
    weth.approve(eth_basis_trade.address, weth.balanceOf(rando2), {'from': rando2})
    weth.approve(eth_basis_trade.address, weth.balanceOf(bob), {'from': bob})

    # DEPOSITS TO VAULT
    eth_basis_trade.depositWeth(amount1, {'from': rando1})
    eth_basis_trade.depositWeth(amount2, {'from': rando2})

    # test depositorInfoPre
    og_deposit_rando1 = eth_basis_trade.depositorInfoPre(rando1)[0]
    og_deposit_rando2 = eth_basis_trade.depositorInfoPre(rando2)[0]
    total = og_deposit_rando1 + og_deposit_rando2
    # test depositorInfoPre: amounts
    assert amount1 == og_deposit_rando1
    assert amount2 == og_deposit_rando2
    assert total == eth_basis_trade.totalPre()
    # test depositorInfoPre: arrIdx
    assert eth_basis_trade.depositorInfoPre(rando1)[1] == 0
    assert eth_basis_trade.depositorInfoPre(rando2)[1] == 1

    # test depositorAddressPre
    assert eth_basis_trade.depositorAddressPre(0) == rando1.address
    assert eth_basis_trade.depositorAddressPre(1) == rando2.address

    # WITHDRAW 75%
    tx_wd = eth_basis_trade.withdrawIdle(7.5e17, {'from': rando1})

    # test depositorInfoPre
    rem_deposit_rando1 = eth_basis_trade.depositorInfoPre(rando1)[0]
    total = rem_deposit_rando1 + eth_basis_trade.depositorInfoPre(rando2)[0]
    assert total == eth_basis_trade.totalPre()
    assert pytest.approx((amount1*(1-0.75)) + amount2) == eth_basis_trade.totalPre()
    # test depositorInfoPre: amounts
    assert pytest.approx((1-0.75)*amount1) == rem_deposit_rando1
    assert amount2 == eth_basis_trade.depositorInfoPre(rando2)[0]
    # test depositorInfoPre: arrIdx
    assert eth_basis_trade.depositorInfoPre(rando1)[1] == 0
    assert eth_basis_trade.depositorInfoPre(rando2)[1] == 1

    # test depositorAddressPre
    assert eth_basis_trade.depositorAddressPre(0) == rando1.address
    assert eth_basis_trade.depositorAddressPre(1) == rando2.address

    # test event
    obs_withdraw_amount = tx_wd.events['WithdrawIdle']['amount']
    exp_withdraw_amount = 0.75*amount1
    assert pytest.approx(obs_withdraw_amount) == exp_withdraw_amount

    # WITHDRAW REMAINDER COMPLETELY
    tx_wd = eth_basis_trade.withdrawIdle(1e18, {'from': rando1})

    # test depositorInfoPre
    rem_deposit_rando1 = eth_basis_trade.depositorInfoPre(rando1)[0]
    total = rem_deposit_rando1 + eth_basis_trade.depositorInfoPre(rando2)[0]
    assert total == eth_basis_trade.totalPre()
    assert amount2 == eth_basis_trade.totalPre()
    # test depositorInfoPre: amounts
    assert 0 == rem_deposit_rando1
    assert amount2 == eth_basis_trade.depositorInfoPre(rando2)[0]
    # test depositorInfoPre: arrIdx
    assert eth_basis_trade.depositorInfoPre(rando1)[1] == 0
    assert eth_basis_trade.depositorInfoPre(rando2)[1] == 0

    # test depositorAddressPre
    assert eth_basis_trade.depositorAddressPre(0) == rando2.address
    with brownie.reverts():
        eth_basis_trade.depositorAddressPre(1)

    # CALL UPDATE WITH TRUE
    tx_true = eth_basis_trade.update(True, {'from': rando1})

    # CALL UPDATE WITH FALSE
    tx_false = eth_basis_trade.update(False, {'from': rando2})

    rando2_amount_updated = eth_basis_trade.depositorInfoPre(rando2)[0]

    # ANOTHER DEPOSIT BY RANDO2
    eth_basis_trade.depositWeth(amount3, {'from': rando2})
    rando2_amount_toppedup = amount3 + rando2_amount_updated

    # test depositorInfoPre: amounts
    rando2_amount_new = eth_basis_trade.depositorInfoPre(rando2)[0]
    assert rando2_amount_new == amount3 + rando2_amount_updated
    assert pytest.approx(rando2_amount_new) == eth_basis_trade.totalPre()
    # test depositorInfoPre: arrIdx
    assert eth_basis_trade.depositorInfoPre(rando2)[1] == 0
    with brownie.reverts():
        eth_basis_trade.depositorAddressPre(1)

    # WITHDRAW 25%
    tx_wd = eth_basis_trade.withdrawIdle(2.5e17, {'from': rando2})

    # test depositorInfoPre
    rem_deposit_rando2 = eth_basis_trade.depositorInfoPre(rando2)[0]
    total = rem_deposit_rando2
    assert pytest.approx(total) == eth_basis_trade.totalPre()
    assert pytest.approx(rando2_amount_toppedup*(1-0.25)) == eth_basis_trade.totalPre()
    # test depositorInfoPre: amounts
    assert pytest.approx((1-0.25)*rando2_amount_toppedup) == rem_deposit_rando2
    # test depositorInfoPre: arrIdx
    assert eth_basis_trade.depositorInfoPre(rando2)[1] == 0

    # test depositorAddressPre
    assert eth_basis_trade.depositorAddressPre(0) == rando2.address
    with brownie.reverts():
        eth_basis_trade.depositorAddressPre(1)

    # test event
    obs_withdraw_amount = tx_wd.events['WithdrawIdle']['amount']
    exp_withdraw_amount = rando2_amount_toppedup*0.25
    assert pytest.approx(obs_withdraw_amount) == exp_withdraw_amount

    # WITHDRAW REMAINDER COMPLETELY
    tx_wd = eth_basis_trade.withdrawIdle(1e18, {'from': rando2})

    # test depositorInfoPre
    rem_deposit_rando2 = eth_basis_trade.depositorInfoPre(rando2)[0]
    total = eth_basis_trade.depositorInfoPre(rando2)[0]
    assert pytest.approx(total) == 0
    assert eth_basis_trade.totalPre() <= 10
    # test depositorInfoPre: amounts
    assert 0 == rem_deposit_rando2
    # test depositorInfoPre: arrIdx
    assert eth_basis_trade.depositorInfoPre(rando2)[1] == 0

    # test depositorAddressPre
    with brownie.reverts():
        eth_basis_trade.depositorAddressPre(0)
