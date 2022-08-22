import time
from collections import namedtuple

import pytest
from platon._utils.error_code import ERROR_CODE

from lib.funcs import wait_settlement
from tests.conftest import generate_account
from loguru import logger


@pytest.mark.P0
@pytest.mark.compatibility
def test_ROE_001_007_015(normal_aide, deploy_chain):
    """
    1.发起质押和委托
    2.在犹豫期赎回委托
    """
    value = normal_aide.delegate._economic.staking_limit
    address, pk = generate_account(normal_aide, value * 3)
    normal_aide.staking.create_staking(amount=value, benefit_address=address, private_key=pk)

    delegate_address, delegate_pk = generate_account(normal_aide, normal_aide.delegate._economic.delegate_limit * 3)
    assert normal_aide.delegate.delegate(private_key=delegate_pk)['code'] == 0

    assert normal_aide.delegate.withdrew_delegate(private_key=delegate_pk)['code'] == 0


@pytest.mark.P1
def test_ROE_002_059(normal_aide, deploy_chain):
    """
    1.发起质押和委托
    2.赎回委托时 gas too low
    """
    value = normal_aide.delegate._economic.staking_limit
    address, pk = generate_account(normal_aide, value * 3)
    normal_aide.staking.create_staking(amount=value, benefit_address=address, private_key=pk)

    delegate_address, delegate_pk = generate_account(normal_aide, normal_aide.delegate._economic.delegate_limit * 3)
    assert normal_aide.delegate.delegate(private_key=delegate_pk)['code'] == 0

    with pytest.raises(ValueError) as exception_info:
        normal_aide.delegate.withdrew_delegate(txn={"gas": 1}, private_key=delegate_pk)

    assert str(exception_info.value) == "{'code': -32000, 'message': 'intrinsic gas too low'}"

    wait_settlement(normal_aide)
    with pytest.raises(ValueError) as exception_info:
        normal_aide.delegate.withdrew_delegate(txn={"gas": 10}, private_key=delegate_pk)
    assert str(exception_info.value) == "{'code': -32000, 'message': 'intrinsic gas too low'}"


@pytest.mark.P3
def test_ROE_003(normal_aide, deploy_chain):
    """
    1.发起质押和委托
    2.illegal_node_id 赎回委托
    """
    value = normal_aide.delegate._economic.staking_limit
    address, pk = generate_account(normal_aide, value * 3)
    normal_aide.staking.create_staking(amount=value, benefit_address=address, private_key=pk)

    delegate_address, delegate_pk = generate_account(normal_aide, normal_aide.delegate._economic.delegate_limit * 3)
    assert normal_aide.delegate.delegate(private_key=delegate_pk)['code'] == 0

    illegal_node_id = "7ee3276fd6b9c7864eb896310b5393324b6db785a2528c00cc28ca8c" \
                      "3f86fc229a86f138b1f1c8e3a942204c03faeb40e3b22ab11b8983c35dc025de42865990"
    result = normal_aide.delegate.withdrew_delegate(node_id=illegal_node_id, private_key=delegate_pk)
    logger.info(result)
    assert ERROR_CODE[301109] == result['message']


@pytest.mark.P1
def test_ROE_004_055(normal_aide, deploy_chain):
    """
    1.发起质押和委托
    2.赎回委托金额 > 委托金额
    """
    value = normal_aide.delegate._economic.staking_limit
    address, pk = generate_account(normal_aide, value * 3)
    normal_aide.staking.create_staking(amount=value, benefit_address=address, private_key=pk)

    delegate_address, delegate_pk = generate_account(normal_aide, normal_aide.delegate._economic.delegate_limit * 3)
    assert normal_aide.delegate.delegate(private_key=delegate_pk)['code'] == 0

    result = normal_aide.delegate.withdrew_delegate(amount=normal_aide.delegate._economic.delegate_limit + 1,
                                                    private_key=delegate_pk)
    logger.info(result)
    assert ERROR_CODE[301113] == result['message']

    wait_settlement(normal_aide)
    result = normal_aide.delegate.withdrew_delegate(amount=normal_aide.delegate._economic.delegate_limit + 1,
                                                    private_key=delegate_pk)
    logger.info(result)
    assert ERROR_CODE[301113] == result['message']


@pytest.mark.P1
def test_ROE_005_018(normal_aide, deploy_chain):
    """
    1.发起质押和委托
    2.犹豫期赎回质押
    3.等待一个结算周期
    4.赎回委托  ->  赎回的金额进入 锁定期
    5.领取已解锁的委托金
    """
    value = normal_aide.delegate._economic.staking_limit
    address, pk = generate_account(normal_aide, value * 3)
    normal_aide.staking.create_staking(benefit_address=address, private_key=pk)
    StakingBlockNum = normal_aide.staking.staking_info.StakingBlockNum

    delegate_address, delegate_pk = generate_account(normal_aide, normal_aide.delegate._economic.delegate_limit * 3)
    assert normal_aide.delegate.delegate(private_key=delegate_pk)['code'] == 0

    # Return a pledge
    assert normal_aide.staking.withdrew_staking(private_key=pk)['code'] == 0

    # The next two cycle
    wait_settlement(normal_aide)
    amount = normal_aide.platon.get_balance(delegate_address)
    logger.info("The wallet balance:{}".format(amount))
    # 赎回委托信息 需要传入当时质押的StakingBlockNum, *委托金额会进入锁定期
    result = normal_aide.delegate.withdrew_delegate(private_key=delegate_pk, staking_block_identifier=StakingBlockNum)
    logger.info(result)

    wait_settlement(normal_aide)
    res = normal_aide.delegate.redeem_delegate(private_key=delegate_pk)
    logger.info(f"redeem the amount entrusted by the lockup period: {res}")
    amount_after = normal_aide.platon.get_balance(delegate_address)
    logger.info("The wallet balance:{}".format(amount_after))
    delegate_limit = normal_aide.delegate._economic.delegate_limit
    logger.info(f"{delegate_limit} - {(amount_after - amount)} < {normal_aide.web3.toVon(1, 'lat')}")
    assert delegate_limit - (amount_after - amount) < normal_aide.web3.toVon(1, 'lat')


@pytest.mark.P1
def test_ROE_006_008(normal_aide, deploy_chain):
    """
    - 犹豫期
        1.委托账户40 委托30 赎回20
        2.赎回前余额10 赎回后余额30
        3.赎回金额20 - (30 - 10)[交易手续费] < 1lat
    """
    address, pk = generate_account(normal_aide, normal_aide.delegate._economic.staking_limit * 2)
    normal_aide.staking.create_staking(benefit_address=address, private_key=pk)

    value = normal_aide.delegate._economic.delegate_limit
    delegate_address, delegate_pk = generate_account(normal_aide, value * 4)
    assert normal_aide.delegate.delegate(amount=value * 3, private_key=delegate_pk)['code'] == 0

    amount = normal_aide.platon.get_balance(delegate_address)
    logger.info("The wallet balance:{}".format(amount))
    result = normal_aide.delegate.withdrew_delegate(amount=value * 2, private_key=delegate_pk)
    logger.info(result)
    amount_after = normal_aide.platon.get_balance(delegate_address)
    logger.info("The wallet balance:{}".format(amount_after))
    delegate_amount = value * 2
    assert delegate_amount * 2 - (amount_after - amount) < normal_aide.web3.toVon(1, 'lat')


@pytest.mark.P1
def test_ROE_010(normal_aide, deploy_chain):
    """
    - 犹豫期
        1.质押+(锁仓计划1000)
        2.委托
            - 自由金额 500
            - 锁仓金额 500
        3.赎回委托 300 (自由金额 -300)
        4.赎回金额300 - (赎回后-赎回前)[交易手续费] < 1lat
    """
    delegate_address, delegate_pk = generate_account(normal_aide, normal_aide.delegate._economic.staking_limit)
    lockup_amount = normal_aide.web3.toVon(1000, 'lat')
    plan = [{'Epoch': 1, 'Amount': lockup_amount}]
    # Create a lock plan
    result = normal_aide.restricting.restricting(release_address=delegate_address, plans=plan, private_key=delegate_pk)
    logger.info(result)

    msg = normal_aide.restricting.get_restricting_info(delegate_address)
    logger.info(msg)
    # create staking
    staking_address, staking_pk = generate_account(normal_aide, normal_aide.delegate._economic.staking_limit * 2)
    normal_aide.staking.create_staking(benefit_address=staking_address, private_key=staking_pk)

    delegate_amount = normal_aide.web3.toVon(500, 'lat')
    # Lock account authorization
    delegate_result = normal_aide.delegate.delegate(amount=delegate_amount, balance_type=1, private_key=delegate_pk)
    logger.info(delegate_result)
    assert delegate_result['code'] == 0

    # Own capital account entrustment
    result = normal_aide.delegate.delegate(amount=delegate_amount, balance_type=0, private_key=delegate_pk)
    logger.info(result)

    undelegate_amount = normal_aide.web3.toVon(300, 'lat')
    logger.info("The amount of redemption is greater than the entrustment of the free account")
    amount = normal_aide.platon.get_balance(delegate_address)
    logger.info("The wallet balance:{}".format(amount))

    result = normal_aide.delegate.withdrew_delegate(amount=undelegate_amount, private_key=delegate_pk)
    logger.info(result)

    msg = normal_aide.delegate.get_delegate_info(address=delegate_address)
    logger.info(msg)
    amount_after = normal_aide.platon.get_balance(delegate_address)
    logger.info("The wallet balance:{}".format(amount_after))
    assert undelegate_amount - (amount_after - amount) < normal_aide.web3.toVon(1, 'lat')


@pytest.mark.P1
def test_ROE_011(normal_aide, deploy_chain):
    """
    - 犹豫期
        1.质押+锁仓(锁仓1000)
        2.委托
            - 自由金额 500
            - 锁仓金额 500
        3.取消委托 700
        4.查余额会得到 自由金额500
    - 结算期
        1.释放锁仓 500(未质押) + 200(释放) + 300(锁仓)
    """
    delegate_address, delegate_pk = generate_account(normal_aide, normal_aide.delegate._economic.staking_limit)
    restrict_plan_amount = normal_aide.web3.toVon(1000, 'lat')
    plan = [{'Epoch': 1, 'Amount': restrict_plan_amount}]
    # Create a lock plan
    assert normal_aide.restricting.restricting(release_address=delegate_address, plans=plan,
                                               private_key=delegate_pk)['code'] == 0

    restrict_info_1 = normal_aide.restricting.get_restricting_info(delegate_address)
    logger.info(f'restrict_info_1: {restrict_info_1}')
    # create staking
    staking_address, staking_pk = generate_account(normal_aide, normal_aide.delegate._economic.staking_limit * 2)
    normal_aide.staking.create_staking(benefit_address=staking_address, private_key=staking_pk)
    StakingBlockNum = normal_aide.staking.staking_info.StakingBlockNum

    delegate_amount = normal_aide.web3.toVon(500, "lat")
    # Lock account authorization
    assert normal_aide.delegate.delegate(amount=delegate_amount, balance_type=1, private_key=delegate_pk)['code'] == 0
    restrict_info_2 = normal_aide.restricting.get_restricting_info(delegate_address)
    logger.info(f"used restrict staking: {restrict_info_2}")
    assert restrict_info_2['Pledge'] == delegate_amount

    # Own capital account entrustment
    assert normal_aide.delegate.delegate(amount=delegate_amount, balance_type=0, private_key=delegate_pk)['code'] == 0

    undelegate_amount = normal_aide.web3.toVon(700, "lat")
    amount1 = normal_aide.platon.get_balance(delegate_address)
    logger.info("The wallet balance:{}".format(amount1))

    assert normal_aide.delegate.withdrew_delegate(amount=undelegate_amount, staking_block_identifier=StakingBlockNum,
                                                  private_key=delegate_pk)['code'] == 0

    amount2 = normal_aide.platon.get_balance(delegate_address)
    logger.info(f"The wallet balance:{amount2}")
    # 目前只释放 自由金额的500
    assert delegate_amount - (amount2 - amount1) < normal_aide.web3.toVon(1, "lat")

    # The next cycle
    wait_settlement(normal_aide)
    locked_delegate = delegate_amount - (undelegate_amount - delegate_amount)
    restrict_info_3 = normal_aide.restricting.get_restricting_info(delegate_address)
    logger.info(f"restrict_info_3: {restrict_info_3}")

    # The remaining entrusted amount
    assert restrict_info_3['Pledge'] == locked_delegate
    amount3 = normal_aide.platon.get_balance(delegate_address)
    logger.info("The wallet balance:{}".format(amount3))
    assert amount3 - amount2 == restrict_plan_amount - restrict_info_3["debt"]


@pytest.mark.P1
def test_ROE_012(normal_aide, deploy_chain):
    """
    1.发起质押和委托500
    2.赎回委托499 (低于最小委托值则全部赎回)
    """
    staking_address, staking_pk = generate_account(normal_aide, normal_aide.delegate._economic.staking_limit * 2)
    delegate_address, delegate_pk = generate_account(normal_aide, normal_aide.delegate._economic.delegate_limit * 100)
    assert normal_aide.staking.create_staking(benefit_address=staking_address, private_key=staking_pk)['code'] == 0
    delegate_amount = normal_aide.delegate._economic.delegate_limit * 50
    assert normal_aide.delegate.delegate(amount=delegate_amount, balance_type=0, private_key=delegate_pk)['code'] == 0

    amount1 = normal_aide.platon.get_balance(delegate_address)
    logger.info("The wallet balance:{}".format(amount1))

    msg = normal_aide.staking.staking_info

    # After redemptive balance is less than the threshold that entrusts gold, redeem completely
    undelegate_amount = normal_aide.web3.toVon(499, 'lat')
    assert normal_aide.delegate.withdrew_delegate(amount=undelegate_amount, private_key=delegate_pk,
                                                  staking_block_identifier=msg.StakingBlockNum)['code'] == 0

    time.sleep(2)
    amount2 = normal_aide.platon.get_balance(delegate_address)
    logger.info("The wallet balance:{}".format(amount2))
    assert not normal_aide.delegate.get_delegate_info(address=delegate_address,
                                                      staking_block_identifier=msg.StakingBlockNum)
    assert amount1 + delegate_amount - amount2 < normal_aide.web3.toVon(1, "lat")


@pytest.mark.P1
def test_ROE_014(normal_aide, deploy_chain):
    """
    - 犹豫期
        1.锁仓1000 * 10
        2.委托
            - 自由金额 100 * 10
            - 锁仓金额 100 * 10
        3.赎回委托 1991
        4.2000 - 1991 = 9 < 10(最低委托金额)
    """
    staking_addr, staking_pk = generate_account(normal_aide, normal_aide.delegate._economic.staking_limit * 2)
    assert normal_aide.staking.create_staking(benefit_address=staking_addr, private_key=staking_pk)['code'] == 0
    StakingBlockNum = normal_aide.staking.staking_info.StakingBlockNum

    delegate_addr, delegate_pk = generate_account(normal_aide, normal_aide.delegate._economic.staking_limit * 2)

    lockup_amount = normal_aide.delegate._economic.delegate_limit * 1000
    plan = [{'Epoch': 1, 'Amount': lockup_amount}]

    assert normal_aide.restricting.restricting(release_address=delegate_addr,
                                               plans=plan, private_key=delegate_pk)['code'] == 0
    restrict_info = normal_aide.restricting.get_restricting_info(release_address=delegate_addr)
    logger.info(f'restrict_info: {restrict_info}')

    delegate_amount = normal_aide.delegate._economic.delegate_limit * 100

    assert normal_aide.delegate.delegate(amount=delegate_amount, balance_type=1, private_key=delegate_pk)['code'] == 0
    assert normal_aide.delegate.delegate(amount=delegate_amount, balance_type=0, private_key=delegate_pk)['code'] == 0

    undelegate_amount = normal_aide.web3.toVon(1991, "lat")
    amount1 = normal_aide.platon.get_balance(delegate_addr)
    logger.info("The wallet balance:{}".format(amount1))

    assert normal_aide.delegate.withdrew_delegate(amount=undelegate_amount, staking_block_identifier=StakingBlockNum,
                                                  private_key=delegate_pk)['code'] == 0

    assert not normal_aide.delegate.get_delegate_info(address=delegate_addr, staking_block_identifier=StakingBlockNum)

    amount2 = normal_aide.platon.get_balance(delegate_addr)
    logger.info("The wallet balance:{}".format(amount2))
    assert amount1 + delegate_amount - amount2 < normal_aide.web3.toVon(1, "lat")


@pytest.mark.P1
def test_ROE_017(normal_aide, deploy_chain):
    """
    - 犹豫期
        1.发起质押和委托
        2.锁仓计划 500
        3.委托
            - 自由金额 500
            - 锁仓金额 500
        4.赎回委托 1000
        此周期赎回 自由金额500
    - 质押结算期,委托未生效, 释放锁仓计划 500
    """
    staking_addr, staking_pk = generate_account(normal_aide, normal_aide.delegate._economic.staking_limit * 2)
    assert normal_aide.staking.create_staking(benefit_address=staking_addr, private_key=staking_pk)['code'] == 0
    StakingBlockNum = normal_aide.staking.staking_info.StakingBlockNum
    delegate_addr, delegate_pk = generate_account(normal_aide, normal_aide.delegate._economic.staking_limit * 2)

    lockup_amount = normal_aide.web3.toVon(500, "lat")
    plan = [{'Epoch': 1, 'Amount': lockup_amount}]

    assert normal_aide.restricting.restricting(release_address=delegate_addr,
                                               plans=plan, private_key=delegate_pk)['code'] == 0
    restrict_info = normal_aide.restricting.get_restricting_info(release_address=delegate_addr)
    logger.info(f'restrict_info: {restrict_info}')

    delegate_amount = normal_aide.web3.toVon(500, "lat")
    assert normal_aide.delegate.delegate(amount=delegate_amount, balance_type=1, private_key=delegate_pk)['code'] == 0
    assert normal_aide.delegate.delegate(amount=delegate_amount, balance_type=0, private_key=delegate_pk)['code'] == 0

    # Redemptive amount is equal to free account + the entrustment gold of lock storehouse
    undelegate_amount = normal_aide.web3.toVon(1000, "lat")
    amount1 = normal_aide.platon.get_balance(delegate_addr)
    logger.info("The wallet balance:{}".format(amount1))

    assert normal_aide.delegate.withdrew_delegate(amount=undelegate_amount, staking_block_identifier=StakingBlockNum,
                                                  private_key=delegate_pk)['code'] == 0

    amount2 = normal_aide.platon.get_balance(delegate_addr)
    logger.info("The wallet balance:{}".format(amount2))
    assert delegate_amount - (amount2 - amount1) < normal_aide.web3.toVon(1, "lat")

    wait_settlement(normal_aide)

    amount3 = normal_aide.platon.get_balance(delegate_addr)
    logger.info("The wallet balance:{}".format(amount3))
    assert amount3 - amount2 == delegate_amount


def create_staking_delegate_wallet_balance(aide, delegate_amount=None):
    staking_addr, staking_pk = generate_account(aide, aide.delegate._economic.staking_limit * 2)
    assert aide.staking.create_staking(benefit_address=staking_addr, private_key=staking_pk)['code'] == 0
    StakingBlockNum = aide.staking.staking_info.StakingBlockNum

    delegate_addr, delegate_pk = generate_account(aide, aide.delegate._economic.staking_limit * 2)
    if not delegate_amount:
        delegate_amount = aide.delegate._economic.delegate_limit
    assert aide.delegate.delegate(amount=delegate_amount, balance_type=0, private_key=delegate_pk)['code'] == 0
    sta_del_amt = aide.platon.get_balance(delegate_addr)
    logger.info(f"create_staking_delegate wallet balance:{sta_del_amt}")

    StaDel = namedtuple("StaDel", ['staking_addr', 'staking_pk', 'StakingBlockNum', 'delegate_addr', 'delegate_pk',
                                   'sta_del_amt', ])

    return StaDel._make([staking_addr, staking_pk, StakingBlockNum, delegate_addr, delegate_pk, sta_del_amt])


def withdrew_delegate_wallet_balance(aide, staking_block_num, del_addr, del_pk, undelegate_amt=None):
    if not undelegate_amt:
        undelegate_amt = aide.delegate._economic.delegate_limit
    assert aide.delegate.withdrew_delegate(amount=undelegate_amt, staking_block_identifier=staking_block_num,
                                           private_key=del_pk)['code'] == 0
    wit_del_amt = aide.platon.get_balance(del_addr)
    logger.info(f"withdrew_delegate_wallet_balance wallet balance:{wit_del_amt}")
    return wit_del_amt


def redeem_delegate_wallet_balance(aide, del_addr, del_pk):
    assert aide.delegate.redeem_delegate(private_key=del_pk)['code'] == 0
    red_del_amt = aide.platon.get_balance(del_addr)
    logger.info("redeem_delegate_wallet_balance wallet balance:{}".format(red_del_amt))
    return red_del_amt


@pytest.mark.P1
def test_ROE_019_021(normal_aide, deploy_chain):
    """
    - 犹豫期
        1.质押和委托(delegate_limit * 3)
    - 结算期
        1.赎回(delegate_limit * 2)
        2.进入 锁定期(等待至解锁期并领取)
    """
    delegate_amount = normal_aide.delegate._economic.delegate_limit * 3
    sd_gather = create_staking_delegate_wallet_balance(normal_aide, delegate_amount=delegate_amount)
    wait_settlement(normal_aide)

    undelegate_amount = normal_aide.delegate._economic.delegate_limit * 2
    wit_del_amt = withdrew_delegate_wallet_balance(normal_aide, sd_gather.StakingBlockNum,
                                                   sd_gather.delegate_addr,
                                                   sd_gather.delegate_pk, undelegate_amount)
    assert wit_del_amt - sd_gather.sta_del_amt < normal_aide.web3.toVon(1, "lat")

    wait_settlement(normal_aide)

    red_del_amt = redeem_delegate_wallet_balance(normal_aide, sd_gather.delegate_addr, sd_gather.delegate_pk)
    assert undelegate_amount - (red_del_amt - wit_del_amt) < normal_aide.web3.toVon(1, "lat")


@pytest.mark.P0
def test_ROE_020(normal_aide, deploy_chain):
    """
     - 犹豫期
        1.质押和委托(delegate_limit)
    - 结算期
        1.赎回(delegate_limit)
        2.进入 锁定期(等待至解锁期并领取)
    """
    delegate_amount = normal_aide.delegate._economic.delegate_limit
    sd_gather = create_staking_delegate_wallet_balance(normal_aide, delegate_amount=delegate_amount)
    wait_settlement(normal_aide)
    undelegate_amount = normal_aide.delegate._economic.delegate_limit
    wit_del_amt = withdrew_delegate_wallet_balance(normal_aide, sd_gather.StakingBlockNum,
                                                   sd_gather.delegate_addr, sd_gather.delegate_pk,
                                                   undelegate_amount)
    assert wit_del_amt - sd_gather.sta_del_amt < normal_aide.web3.toVon(1, "lat")

    wait_settlement(normal_aide)

    red_del_amt = redeem_delegate_wallet_balance(normal_aide, sd_gather.delegate_addr, sd_gather.delegate_pk)
    assert undelegate_amount - (red_del_amt - wit_del_amt) < normal_aide.web3.toVon(1, "lat")


@pytest.mark.P1
def test_ROE_024(normal_aide, deploy_chain):
    """
    - 犹豫期
        1.发起质押和委托(自由金额500)
        2.锁仓计划1000
        3.发起委托 锁仓500
    - 结算期1
        1.赎回委托700 并查余额- 此时赎回的钱不会到账
    - 结算期2
        1.主动领取锁定期的委托金额
    - 结算期3
        1.释放锁仓计划 锁定金额(500-200) 释放金额(1000 - 锁定金额(500-200))
    """
    delegate_amount = normal_aide.web3.toVon(500, "lat")
    sd_gather = create_staking_delegate_wallet_balance(normal_aide, delegate_amount=delegate_amount)
    # Create a lock plan
    lockup_amount = normal_aide.web3.toVon(1000, "lat")
    plan = [{'Epoch': 3, 'Amount': lockup_amount}]
    assert normal_aide.restricting.restricting(release_address=sd_gather.delegate_addr,
                                               plans=plan, private_key=sd_gather.delegate_pk)['code'] == 0
    restrict_info = normal_aide.restricting.get_restricting_info(release_address=sd_gather.delegate_addr)
    logger.info(f'restrict_info: {restrict_info}')
    assert normal_aide.delegate.delegate(amount=delegate_amount, balance_type=1, private_key=sd_gather.delegate_pk)[
               'code'] == 0

    wait_settlement(normal_aide)
    undelegate_amount = normal_aide.web3.toVon(700, "lat")
    wit_del_amt = withdrew_delegate_wallet_balance(normal_aide, sd_gather.StakingBlockNum,
                                                   sd_gather.delegate_addr, sd_gather.delegate_pk,
                                                   undelegate_amount)

    wait_settlement(normal_aide)
    red_del_amt = redeem_delegate_wallet_balance(normal_aide, sd_gather.delegate_addr, sd_gather.delegate_pk)
    assert delegate_amount - (red_del_amt - wit_del_amt) < normal_aide.web3.toVon(1, "lat")

    wait_settlement(normal_aide)
    locked_delegate = delegate_amount - (undelegate_amount - delegate_amount)
    restrict_info = normal_aide.restricting.get_restricting_info(release_address=sd_gather.delegate_addr)
    logger.info(f'restrict_info: {restrict_info}')
    assert restrict_info["Pledge"] == locked_delegate
    release_restrict_amt = normal_aide.platon.get_balance(sd_gather.delegate_addr)
    logger.info("release_restrict wallet balance:{}".format(release_restrict_amt))
    assert release_restrict_amt - red_del_amt == lockup_amount - restrict_info["debt"]


@pytest.mark.P1
def test_ROE_028(normal_aide, deploy_chain):
    """
    - 犹豫期
        1.质押和委托(toVon(500, "lat"))
    - 结算期1
        1.赎回委托(toVon(500, "lat"))  -> 锁定期
    - 结算期2
        1.领取解锁委托
    """
    delegate_amount = normal_aide.web3.toVon(500, "lat")
    sd_gather = create_staking_delegate_wallet_balance(normal_aide, delegate_amount=delegate_amount)
    wait_settlement(normal_aide)
    wit_del_amt = withdrew_delegate_wallet_balance(normal_aide, sd_gather.StakingBlockNum,
                                                   sd_gather.delegate_addr, sd_gather.delegate_pk,
                                                   delegate_amount)
    assert (wit_del_amt - sd_gather.sta_del_amt) < normal_aide.web3.toVon(1, "lat")

    wait_settlement(normal_aide)
    red_del_amt = redeem_delegate_wallet_balance(normal_aide, sd_gather.delegate_addr, sd_gather.delegate_pk)
    assert delegate_amount - (red_del_amt - wit_del_amt) < normal_aide.web3.toVon(1, "lat")


@pytest.mark.P1
def test_ROE_030(normal_aide, deploy_chain):
    """
    - 犹豫期
        1.发起质押和委托(自由金额500)
        2.锁仓计划500
        3.发起委托 锁仓500
    - 结算期1
        1.赎回委托1000 并查余额- 此时赎回的钱不会到账
    - 结算期2
        1.主动领取锁定期的委托金额
    - 结算期3
        1.释放锁仓计划 锁定金额(500-500) 释放金额(500 - 0)
    """

    delegate_amount = normal_aide.web3.toVon(500, "lat")
    sd_gather = create_staking_delegate_wallet_balance(normal_aide, delegate_amount=delegate_amount)

    lockup_amount = normal_aide.web3.toVon(500, "lat")
    plan = [{'Epoch': 3, 'Amount': lockup_amount}]
    assert normal_aide.restricting.restricting(release_address=sd_gather.delegate_addr,
                                               plans=plan, private_key=sd_gather.delegate_pk)['code'] == 0
    restrict_info = normal_aide.restricting.get_restricting_info(release_address=sd_gather.delegate_addr)
    logger.info(f'restrict_info: {restrict_info}')
    assert normal_aide.delegate.delegate(amount=delegate_amount, balance_type=1, private_key=sd_gather.delegate_pk)[
               'code'] == 0

    wait_settlement(normal_aide)

    undelegate_amount = normal_aide.web3.toVon(1000, "lat")
    wit_del_amt = withdrew_delegate_wallet_balance(normal_aide, sd_gather.StakingBlockNum,
                                                   sd_gather.delegate_addr, sd_gather.delegate_pk,
                                                   undelegate_amount)

    wait_settlement(normal_aide)
    red_del_amt = redeem_delegate_wallet_balance(normal_aide, sd_gather.delegate_addr, sd_gather.delegate_pk)
    assert delegate_amount - (red_del_amt - wit_del_amt) < normal_aide.web3.toVon(1, "lat")

    wait_settlement(normal_aide)
    restrict_info = normal_aide.restricting.get_restricting_info(release_address=sd_gather.delegate_addr)
    logger.info(f'restrict_info: {restrict_info}')
    release_restrict_amt = normal_aide.platon.get_balance(sd_gather.delegate_addr)
    logger.info("release_restrict wallet balance:{}".format(release_restrict_amt))
    assert release_restrict_amt - red_del_amt == delegate_amount


@pytest.mark.P2
def test_ROE_031(normal_aide, deploy_chain):
    """
    # TODO: 和旧逻辑有点不一致
    """
    delegate_amount = normal_aide.delegate._economic.delegate_limit * 2
    sd_gather = create_staking_delegate_wallet_balance(normal_aide, delegate_amount=delegate_amount)
    wait_settlement(normal_aide)
    assert normal_aide.delegate.delegate(balance_type=0, private_key=sd_gather.delegate_pk)['code'] == 0
    assert normal_aide.staking.withdrew_staking(private_key=sd_gather.staking_pk)['code'] == 0
    balance1 = normal_aide.platon.get_balance(sd_gather.delegate_addr)
    logger.info(f"The wallet balance:{balance1}")

    undelegate_amount = normal_aide.delegate._economic.delegate_limit
    wit_del_amt = withdrew_delegate_wallet_balance(normal_aide, sd_gather.StakingBlockNum,
                                                   sd_gather.delegate_addr, sd_gather.delegate_pk, undelegate_amount)
    assert undelegate_amount - (wit_del_amt - balance1) < normal_aide.web3.toVon(1, "lat")


@pytest.mark.P2
def test_ROE_032_035(normal_aide, deploy_chain):
    delegate_amount = normal_aide.delegate._economic.delegate_limit * 2
    sd_gather = create_staking_delegate_wallet_balance(normal_aide, delegate_amount=delegate_amount)
    wait_settlement(normal_aide)

    assert normal_aide.delegate.delegate(amount=delegate_amount, balance_type=0,
                                         private_key=sd_gather.delegate_pk)['code'] == 0

    balance1 = normal_aide.platon.get_balance(sd_gather.delegate_addr)
    logger.info(f"wallet balance:{balance1}")

    undelegate_amount = delegate_amount + normal_aide.web3.toVon(1, "lat")
    wit_del_amt = withdrew_delegate_wallet_balance(normal_aide, sd_gather.StakingBlockNum,
                                                   sd_gather.delegate_addr, sd_gather.delegate_pk, undelegate_amount)
    # 只赎回了犹豫期自由金额 delegate_amount
    assert delegate_amount - (wit_del_amt - balance1) < normal_aide.web3.toVon(1, "lat")
    wait_settlement(normal_aide)
    red_del_amt = redeem_delegate_wallet_balance(normal_aide, sd_gather.delegate_addr, sd_gather.delegate_pk)
    assert normal_aide.web3.toVon(1, "lat") - (red_del_amt - wit_del_amt) < normal_aide.web3.toVon(1, "lat")


@pytest.mark.P2
def test_ROE_033_034(normal_aide, deploy_chain):
    delegate_amount = normal_aide.delegate._economic.delegate_limit * 2
    sd_gather = create_staking_delegate_wallet_balance(normal_aide, delegate_amount=delegate_amount)
    wait_settlement(normal_aide)

    assert normal_aide.delegate.delegate(balance_type=0, private_key=sd_gather.delegate_pk)['code'] == 0
    balance1 = normal_aide.platon.get_balance(sd_gather.delegate_addr)
    logger.info(f"wallet balance:{balance1}")

    wit_del_amt = withdrew_delegate_wallet_balance(normal_aide, sd_gather.StakingBlockNum,
                                                   sd_gather.delegate_addr, sd_gather.delegate_pk)
    wait_settlement(normal_aide)
    red_del_amt = redeem_delegate_wallet_balance(normal_aide, sd_gather.delegate_addr, sd_gather.delegate_pk)
    delegate_limit = normal_aide.delegate._economic.delegate_limit
    assert delegate_limit - (red_del_amt - wit_del_amt) < normal_aide.web3.toVon(1, "lat")


@pytest.mark.P2
def test_ROE_038(normal_aide, deploy_chain):
    delegate_amount = normal_aide.delegate._economic.delegate_limit * 2
    sd_gather = create_staking_delegate_wallet_balance(normal_aide, delegate_amount=delegate_amount)
    wait_settlement(normal_aide)
    # create restricting
    lockup_amount = normal_aide.web3.toVon(500, "lat")
    plan = [{'Epoch': 1, 'Amount': lockup_amount}]
    assert normal_aide.restricting.restricting(release_address=sd_gather.delegate_addr,
                                               plans=plan, private_key=sd_gather.delegate_pk)['code'] == 0
    restrict_info = normal_aide.restricting.get_restricting_info(release_address=sd_gather.delegate_addr)
    logger.info(f'restrict_info: {restrict_info}')

    assert normal_aide.delegate.delegate(balance_type=1, private_key=sd_gather.delegate_pk)['code'] == 0
    assert normal_aide.delegate.delegate(balance_type=0, private_key=sd_gather.delegate_pk)['code'] == 0

    balance1 = normal_aide.platon.get_balance(sd_gather.delegate_addr)
    logger.info(f"wallet balance:{balance1}")

    wit_del_amt = withdrew_delegate_wallet_balance(normal_aide, sd_gather.StakingBlockNum,
                                                   sd_gather.delegate_addr, sd_gather.delegate_pk)

    restrict_info = normal_aide.restricting.get_restricting_info(release_address=sd_gather.delegate_addr)
    logger.info(f'restrict_info: {restrict_info}')

    delegate_limit = normal_aide.delegate._economic.delegate_limit
    assert delegate_limit - (wit_del_amt - balance1) < normal_aide.web3.toVon(1, "lat")
    assert restrict_info["Pledge"] == delegate_limit


@pytest.mark.P2
def test_ROE_039(normal_aide, deploy_chain):
    """

    """
    delegate_amount = normal_aide.delegate._economic.delegate_limit * 2
    sd_gather = create_staking_delegate_wallet_balance(normal_aide, delegate_amount=delegate_amount)
    wait_settlement(normal_aide)

    # create restricting
    lockup_amount = normal_aide.web3.toVon(500, "lat")
    plan = [{'Epoch': 1, 'Amount': lockup_amount}]
    assert normal_aide.restricting.restricting(release_address=sd_gather.delegate_addr,
                                               plans=plan, private_key=sd_gather.delegate_pk)['code'] == 0
    restrict_info = normal_aide.restricting.get_restricting_info(release_address=sd_gather.delegate_addr)
    logger.info(f'restrict_info: {restrict_info}')

    assert normal_aide.delegate.delegate(balance_type=1, private_key=sd_gather.delegate_pk,
                                         amount=delegate_amount)['code'] == 0
    delegate_limit = normal_aide.delegate._economic.delegate_limit
    assert normal_aide.delegate.delegate(balance_type=0, private_key=sd_gather.delegate_pk,
                                         amount=delegate_limit)['code'] == 0

    balance1 = normal_aide.platon.get_balance(sd_gather.delegate_addr)
    logger.info(f"wallet balance:{balance1}")

    restrict_info = normal_aide.restricting.get_restricting_info(release_address=sd_gather.delegate_addr)
    logger.info(f'restrict_info: {restrict_info}')

    wit_del_amt = withdrew_delegate_wallet_balance(normal_aide, sd_gather.StakingBlockNum, sd_gather.delegate_addr,
                                                   sd_gather.delegate_pk, delegate_amount)

    restrict_info = normal_aide.restricting.get_restricting_info(release_address=sd_gather.delegate_addr)
    logger.info(f'restrict_info: {restrict_info}')

    assert delegate_limit - (wit_del_amt - balance1) < normal_aide.web3.toVon(1, "lat")
    assert restrict_info["Pledge"] == delegate_limit

    wait_settlement(normal_aide)
    release_amount = lockup_amount - delegate_limit
    end_balance = normal_aide.platon.get_balance(sd_gather.delegate_addr)
    logger.info(f"wallet balance:{end_balance}")
    assert end_balance == wit_del_amt + release_amount


@pytest.mark.P2
def test_ROE_040(normal_aide, deploy_chain):
    delegate_amount = normal_aide.delegate._economic.delegate_limit * 2
    sd_gather = create_staking_delegate_wallet_balance(normal_aide, delegate_amount=delegate_amount)

    # create restricting
    lockup_amount = normal_aide.web3.toVon(500, "lat")
    plan = [{'Epoch': 2, 'Amount': lockup_amount}]
    assert normal_aide.restricting.restricting(release_address=sd_gather.delegate_addr,
                                               plans=plan, private_key=sd_gather.delegate_pk)['code'] == 0
    restrict_info = normal_aide.restricting.get_restricting_info(release_address=sd_gather.delegate_addr)
    logger.info(f'restrict_info: {restrict_info}')

    assert normal_aide.delegate.delegate(balance_type=1, private_key=sd_gather.delegate_pk,
                                         amount=delegate_amount)['code'] == 0

    balance1 = normal_aide.platon.get_balance(sd_gather.delegate_addr)
    logger.info(f"wallet balance:{balance1}")

    undelegate_amount = delegate_amount + normal_aide.web3.toVon(1, "lat")
    wit_del_amt = withdrew_delegate_wallet_balance(normal_aide, sd_gather.StakingBlockNum, sd_gather.delegate_addr,
                                                   sd_gather.delegate_pk, undelegate_amount)

    assert delegate_amount - (wit_del_amt - balance1) < normal_aide.web3.toVon(1, "lat")
    restrict_info = normal_aide.restricting.get_restricting_info(release_address=sd_gather.delegate_addr)
    logger.info(f'restrict_info: {restrict_info}')
    assert restrict_info['Pledge'] == delegate_amount - normal_aide.web3.toVon(1, "lat")


@pytest.mark.P2
def test_ROE_041(normal_aide, deploy_chain):
    delegate_amount = normal_aide.delegate._economic.delegate_limit * 2
    sd_gather = create_staking_delegate_wallet_balance(normal_aide, delegate_amount=delegate_amount)

    # create restricting
    lockup_amount = normal_aide.web3.toVon(500, "lat")
    plan = [{'Epoch': 2, 'Amount': lockup_amount}]
    assert normal_aide.restricting.restricting(release_address=sd_gather.delegate_addr,
                                               plans=plan, private_key=sd_gather.delegate_pk)['code'] == 0
    assert normal_aide.delegate.delegate(balance_type=1, private_key=sd_gather.delegate_pk,
                                         amount=delegate_amount)['code'] == 0
    restrict_info = normal_aide.restricting.get_restricting_info(release_address=sd_gather.delegate_addr)
    logger.info(f'restrict_info: {restrict_info}')

    balance1 = normal_aide.platon.get_balance(sd_gather.delegate_addr)
    logger.info(f"wallet balance:{balance1}")

    undelegate_amount = delegate_amount * 2
    wit_del_amt = withdrew_delegate_wallet_balance(normal_aide, sd_gather.StakingBlockNum, sd_gather.delegate_addr,
                                                   sd_gather.delegate_pk, undelegate_amount)
    assert delegate_amount - (wit_del_amt - balance1) < normal_aide.web3.toVon(1, "lat")
    restrict_info = normal_aide.restricting.get_restricting_info(release_address=sd_gather.delegate_addr)
    logger.info(f'restrict_info: {restrict_info}')
    assert restrict_info['Pledge'] == 0


@pytest.mark.P2
def test_ROE_042_2(normal_aide, deploy_chain):
    delegate_amount = normal_aide.delegate._economic.delegate_limit * 2
    sd_gather = create_staking_delegate_wallet_balance(normal_aide, delegate_amount=delegate_amount)

    # create restricting
    lockup_amount = normal_aide.web3.toVon(500, "lat")
    plan = [{'Epoch': 3, 'Amount': lockup_amount}]
    assert normal_aide.restricting.restricting(release_address=sd_gather.delegate_addr,
                                               plans=plan, private_key=sd_gather.delegate_pk)['code'] == 0
    restrict_info = normal_aide.restricting.get_restricting_info(release_address=sd_gather.delegate_addr)
    logger.info(f'restrict_info: {restrict_info}')
    assert normal_aide.delegate.delegate(balance_type=1, private_key=sd_gather.delegate_pk,
                                         amount=delegate_amount)['code'] == 0

    wait_settlement(normal_aide)
    assert normal_aide.delegate.delegate(balance_type=0, private_key=sd_gather.delegate_pk,
                                         amount=delegate_amount)['code'] == 0

    balance1 = normal_aide.platon.get_balance(sd_gather.delegate_addr)
    logger.info(f"wallet balance:{balance1}")

    undelegate_amount = delegate_amount * 3
    wit_del_amt = withdrew_delegate_wallet_balance(normal_aide, sd_gather.StakingBlockNum, sd_gather.delegate_addr,
                                                   sd_gather.delegate_pk, undelegate_amount)
    # 1.只提取犹豫期 自由金额 20
    assert delegate_amount - (wit_del_amt - balance1) < normal_aide.web3.toVon(1, "lat")

    restrict_info = normal_aide.restricting.get_restricting_info(release_address=sd_gather.delegate_addr)
    logger.info(f'restrict_info: {restrict_info}')

    wait_settlement(normal_aide)
    # 解锁期 领取自由金额20 锁仓金额的20 要等到锁仓计划释放restrict_info['Pledge'] 质押由20 改变为 0
    restrict_info = normal_aide.restricting.get_restricting_info(release_address=sd_gather.delegate_addr)
    logger.info(f'restrict_info: {restrict_info}')

    red_del_amt = redeem_delegate_wallet_balance(normal_aide, sd_gather.delegate_addr, sd_gather.delegate_pk)
    assert delegate_amount - (red_del_amt - wit_del_amt) < normal_aide.web3.toVon(1, "lat")

    restrict_info = normal_aide.restricting.get_restricting_info(release_address=sd_gather.delegate_addr)
    logger.info(f'restrict_info: {restrict_info}')
    assert restrict_info['Pledge'] == 0

    wait_settlement(normal_aide)
    # 释放锁仓计划 500
    balance2 = normal_aide.platon.get_balance(sd_gather.delegate_addr)
    logger.info(f"wallet balance2:{balance2}")
    assert balance2 - red_del_amt == lockup_amount


@pytest.mark.P1
def test_ROE_042(normal_aide, deploy_chain):
    """
    - 犹豫期
        1.发起质押和委托(200)
        2.锁仓计划 1000
        3.锁仓委托 200
    - 结算期1
        1.发起委托(自由金额300 锁仓300)
        2.赎回委托700
    - 验证:赎回自由金额400 其他等待锁仓计划释放
    """
    delegate_amount = normal_aide.web3.toVon(200, "lat")
    sd_gather = create_staking_delegate_wallet_balance(normal_aide, delegate_amount=delegate_amount)

    lockup_amount = normal_aide.web3.toVon(1000, "lat")
    plan = [{'Epoch': 3, 'Amount': lockup_amount}]
    assert normal_aide.restricting.restricting(release_address=sd_gather.delegate_addr,
                                               plans=plan, private_key=sd_gather.delegate_pk)['code'] == 0
    restrict_info = normal_aide.restricting.get_restricting_info(release_address=sd_gather.delegate_addr)
    logger.info(f'restrict_info: {restrict_info}')
    assert normal_aide.delegate.delegate(amount=delegate_amount, balance_type=1,
                                         private_key=sd_gather.delegate_pk)['code'] == 0

    wait_settlement(normal_aide)
    delegate_amount_2 = normal_aide.web3.toVon(300, "lat")
    assert normal_aide.delegate.delegate(amount=delegate_amount_2, balance_type=0,
                                         private_key=sd_gather.delegate_pk)['code'] == 0
    assert normal_aide.delegate.delegate(amount=delegate_amount_2, balance_type=1,
                                         private_key=sd_gather.delegate_pk)['code'] == 0

    undelegate_amount = normal_aide.web3.toVon(700, "lat")
    wit_del_ago = normal_aide.platon.get_balance(sd_gather.delegate_addr)
    logger.info(f"wit_del_ago: {wit_del_ago}")

    wit_del_amt = withdrew_delegate_wallet_balance(normal_aide, sd_gather.StakingBlockNum,
                                                   sd_gather.delegate_addr, sd_gather.delegate_pk,
                                                   undelegate_amount)
    # 赎回犹豫期自由金额300
    assert delegate_amount_2 - (wit_del_amt - wit_del_ago) < normal_aide.web3.toVon(1, "lat")

    wait_settlement(normal_aide)
    red_del_amt = redeem_delegate_wallet_balance(normal_aide, sd_gather.delegate_addr, sd_gather.delegate_pk)

    other_cycle_amt = undelegate_amount - delegate_amount_2 * 2  # 其他周期100 = 赎回委托700 - 犹豫期(自由金额300 + 锁仓金额300)
    withdrew_amt = delegate_amount_2 + other_cycle_amt  # 赎回总金额 = 自由金额[犹豫期300 + 生效期100]

    assert other_cycle_amt - (red_del_amt - wit_del_amt) < normal_aide.web3.toVon(1, "lat")
    assert withdrew_amt - (red_del_amt - wit_del_ago) < normal_aide.web3.toVon(1, "lat")

    wait_settlement(normal_aide)
    restrict_info = normal_aide.restricting.get_restricting_info(release_address=sd_gather.delegate_addr)
    logger.info(f'restrict_info: {restrict_info}')

    release_restrict_amt = normal_aide.platon.get_balance(sd_gather.delegate_addr)
    logger.info("release_restrict wallet balance:{}".format(release_restrict_amt))
    assert release_restrict_amt - red_del_amt == lockup_amount - restrict_info["debt"]


@pytest.mark.P2
def test_ROE_043(normal_aide, deploy_chain):
    delegate_amount = normal_aide.delegate._economic.delegate_limit * 2
    sd_gather = create_staking_delegate_wallet_balance(normal_aide, delegate_amount=delegate_amount)

    # create restricting
    lockup_amount = normal_aide.web3.toVon(500, "lat")
    plan = [{'Epoch': 3, 'Amount': lockup_amount}]
    assert normal_aide.restricting.restricting(release_address=sd_gather.delegate_addr,
                                               plans=plan, private_key=sd_gather.delegate_pk)['code'] == 0
    restrict_info = normal_aide.restricting.get_restricting_info(release_address=sd_gather.delegate_addr)
    logger.info(f'restrict_info: {restrict_info}')
    assert normal_aide.delegate.delegate(balance_type=1, private_key=sd_gather.delegate_pk,
                                         amount=delegate_amount)['code'] == 0

    wait_settlement(normal_aide)

    assert normal_aide.delegate.delegate(balance_type=0, private_key=sd_gather.delegate_pk,
                                         amount=delegate_amount)['code'] == 0
    assert normal_aide.delegate.delegate(balance_type=1, private_key=sd_gather.delegate_pk,
                                         amount=delegate_amount)['code'] == 0
    balance1 = normal_aide.platon.get_balance(sd_gather.delegate_addr)
    logger.info(f"wallet balance:{balance1}")

    undelegate_amount = delegate_amount * 3
    wit_del_amt = withdrew_delegate_wallet_balance(normal_aide, sd_gather.StakingBlockNum, sd_gather.delegate_addr,
                                                   sd_gather.delegate_pk, undelegate_amount)
    # 犹豫期自由金额20
    assert delegate_amount - (wit_del_amt - balance1) < normal_aide.web3.toVon(1, "lat")
    wait_settlement(normal_aide)
    # 解锁期自由金额20
    red_del_amt = redeem_delegate_wallet_balance(normal_aide, sd_gather.delegate_addr, sd_gather.delegate_pk)
    assert delegate_amount - (red_del_amt - wit_del_amt) < normal_aide.web3.toVon(1, "lat")

    restrict_info = normal_aide.restricting.get_restricting_info(release_address=sd_gather.delegate_addr)
    logger.info(f'restrict_info: {restrict_info}')
    assert restrict_info["Pledge"] == delegate_amount


@pytest.mark.P2
def test_ROE_044(normal_aide, deploy_chain):
    delegate_amount = normal_aide.delegate._economic.delegate_limit * 2
    sd_gather = create_staking_delegate_wallet_balance(normal_aide, delegate_amount=delegate_amount)

    # create restricting
    lockup_amount = normal_aide.web3.toVon(500, "lat")
    plan = [{'Epoch': 3, 'Amount': lockup_amount}]
    assert normal_aide.restricting.restricting(release_address=sd_gather.delegate_addr,
                                               plans=plan, private_key=sd_gather.delegate_pk)['code'] == 0
    restrict_info = normal_aide.restricting.get_restricting_info(release_address=sd_gather.delegate_addr)
    logger.info(f'restrict_info: {restrict_info}')
    assert normal_aide.delegate.delegate(balance_type=1, private_key=sd_gather.delegate_pk,
                                         amount=delegate_amount)['code'] == 0

    wait_settlement(normal_aide)

    assert normal_aide.delegate.delegate(balance_type=0, private_key=sd_gather.delegate_pk,
                                         amount=delegate_amount)['code'] == 0
    assert normal_aide.delegate.delegate(balance_type=1, private_key=sd_gather.delegate_pk,
                                         amount=delegate_amount)['code'] == 0
    balance1 = normal_aide.platon.get_balance(sd_gather.delegate_addr)
    logger.info(f"wallet balance:{balance1}")

    undelegate_amount = normal_aide.delegate._economic.delegate_limit * 7
    wit_del_amt = withdrew_delegate_wallet_balance(normal_aide, sd_gather.StakingBlockNum, sd_gather.delegate_addr,
                                                   sd_gather.delegate_pk, undelegate_amount)

    assert delegate_amount - (wit_del_amt - balance1) < normal_aide.web3.toVon(1, "lat")
    wait_settlement(normal_aide)
    red_del_amt = redeem_delegate_wallet_balance(normal_aide, sd_gather.delegate_addr, sd_gather.delegate_pk)
    assert delegate_amount - (red_del_amt - wit_del_amt) < normal_aide.web3.toVon(1, "lat")

    restrict_info = normal_aide.restricting.get_restricting_info(release_address=sd_gather.delegate_addr)
    logger.info(f'restrict_info: {restrict_info}')
    assert restrict_info['Pledge'] == normal_aide.delegate._economic.delegate_limit


@pytest.mark.P2
def test_ROE_045(normal_aide, deploy_chain):
    delegate_amount = normal_aide.delegate._economic.delegate_limit * 2
    sd_gather = create_staking_delegate_wallet_balance(normal_aide, delegate_amount=delegate_amount)

    wait_settlement(normal_aide)
    assert normal_aide.delegate.delegate(balance_type=0, private_key=sd_gather.delegate_pk,
                                         amount=delegate_amount)['code'] == 0

    balance1 = normal_aide.platon.get_balance(sd_gather.delegate_addr)
    logger.info(f"wallet balance:{balance1}")

    wit_del_amt = withdrew_delegate_wallet_balance(normal_aide, sd_gather.StakingBlockNum, sd_gather.delegate_addr,
                                                   sd_gather.delegate_pk, delegate_amount)
    assert delegate_amount - (wit_del_amt - balance1) < normal_aide.web3.toVon(1, "lat")


@pytest.mark.P2
def test_ROE_048(normal_aide, deploy_chain):
    delegate_amount = normal_aide.delegate._economic.delegate_limit * 2
    sd_gather = create_staking_delegate_wallet_balance(normal_aide, delegate_amount=delegate_amount)

    wait_settlement(normal_aide)
    assert normal_aide.delegate.delegate(balance_type=0, private_key=sd_gather.delegate_pk,
                                         amount=delegate_amount)['code'] == 0

    balance1 = normal_aide.platon.get_balance(sd_gather.delegate_addr)
    logger.info(f"wallet balance:{balance1}")

    undelegate_amount = delegate_amount * 2
    wit_del_amt = withdrew_delegate_wallet_balance(normal_aide, sd_gather.StakingBlockNum, sd_gather.delegate_addr,
                                                   sd_gather.delegate_pk, undelegate_amount)
    assert delegate_amount - (wit_del_amt - balance1) < normal_aide.web3.toVon(1, "lat")

    wait_settlement(normal_aide)

    red_del_amt = redeem_delegate_wallet_balance(normal_aide, sd_gather.delegate_addr, sd_gather.delegate_pk)
    assert delegate_amount - (red_del_amt - wit_del_amt) < normal_aide.web3.toVon(1, "lat")


@pytest.mark.P2
def test_ROE_049(normal_aide, deploy_chain):
    delegate_amount = normal_aide.delegate._economic.delegate_limit * 2
    sd_gather = create_staking_delegate_wallet_balance(normal_aide, delegate_amount=delegate_amount)

    wait_settlement(normal_aide)

    # create restricting
    lockup_amount = normal_aide.web3.toVon(500, "lat")
    plan = [{'Epoch': 2, 'Amount': lockup_amount}]
    assert normal_aide.restricting.restricting(release_address=sd_gather.delegate_addr,
                                               plans=plan, private_key=sd_gather.delegate_pk)['code'] == 0
    restrict_info = normal_aide.restricting.get_restricting_info(release_address=sd_gather.delegate_addr)
    logger.info(f'restrict_info: {restrict_info}')
    assert normal_aide.delegate.delegate(balance_type=1, private_key=sd_gather.delegate_pk,
                                         amount=delegate_amount)['code'] == 0
    assert normal_aide.delegate.delegate(balance_type=0, private_key=sd_gather.delegate_pk,
                                         amount=delegate_amount)['code'] == 0

    balance1 = normal_aide.platon.get_balance(sd_gather.delegate_addr)
    logger.info(f"wallet balance:{balance1}")

    undelegate_amount = delegate_amount * 3
    wit_del_amt = withdrew_delegate_wallet_balance(normal_aide, sd_gather.StakingBlockNum, sd_gather.delegate_addr,
                                                   sd_gather.delegate_pk, undelegate_amount)
    assert delegate_amount - (wit_del_amt - balance1) < normal_aide.web3.toVon(1, "lat")

    wait_settlement(normal_aide)

    red_del_amt = redeem_delegate_wallet_balance(normal_aide, sd_gather.delegate_addr, sd_gather.delegate_pk)
    assert delegate_amount - (red_del_amt - wit_del_amt) < normal_aide.web3.toVon(1, "lat")

    restrict_info = normal_aide.restricting.get_restricting_info(release_address=sd_gather.delegate_addr)
    logger.info(f'restrict_info: {restrict_info}')
    assert restrict_info['Pledge'] == 0


@pytest.mark.P1
def test_ROE_056_057(normal_aide, init_aide, deploy_chain):
    """
    关闭节点后 领取委托
    """
    delegate_amount = normal_aide.delegate._economic.delegate_limit * 2
    delegate_limit = normal_aide.delegate._economic.delegate_limit
    normal_aide_node_id = normal_aide.node.node_id
    sd_gather = create_staking_delegate_wallet_balance(normal_aide, delegate_amount=delegate_amount)
    wait_settlement(normal_aide)

    normal_aide.node.stop()
    wait_settlement(init_aide)

    # 1.共识节点去查普通节点的 质押信息
    staking_info = init_aide.staking.get_candidate_info(node_id=normal_aide.node.node_id)
    print(f"node.stop staking_info: {staking_info}")

    balance_1 = init_aide.platon.get_balance(sd_gather.delegate_addr)
    logger.info(f"balance_1: {balance_1}")

    assert init_aide.delegate.withdrew_delegate(amount=delegate_limit,
                                                staking_block_identifier=sd_gather.StakingBlockNum,
                                                private_key=sd_gather.delegate_pk,
                                                node_id=normal_aide_node_id)['code'] == 0
    wit_del_amt = init_aide.platon.get_balance(sd_gather.delegate_addr)
    logger.info(f"withdrew_delegate_wallet_balance wallet balance:{wit_del_amt}")
    wait_settlement(init_aide)
    assert init_aide.delegate.redeem_delegate(private_key=sd_gather.delegate_pk)['code'] == 0
    red_del_amt = init_aide.platon.get_balance(sd_gather.delegate_addr)
    logger.info("redeem_delegate_wallet_balance wallet balance:{}".format(red_del_amt))
    assert delegate_limit - (red_del_amt - wit_del_amt) < normal_aide.web3.toVon(0.001, "lat")

    assert init_aide.delegate.withdrew_delegate(amount=delegate_limit,
                                                staking_block_identifier=sd_gather.StakingBlockNum,
                                                private_key=sd_gather.delegate_pk,
                                                node_id=normal_aide_node_id)['code'] == 0
    wit_del_amt = init_aide.platon.get_balance(sd_gather.delegate_addr)
    logger.info(f"withdrew_delegate_wallet_balance wallet balance:{wit_del_amt}")
    wait_settlement(init_aide)
    assert init_aide.delegate.redeem_delegate(private_key=sd_gather.delegate_pk)['code'] == 0
    red_del_amt = init_aide.platon.get_balance(sd_gather.delegate_addr)
    logger.info("redeem_delegate_wallet_balance wallet balance:{}".format(red_del_amt))
    assert delegate_limit - (red_del_amt - wit_del_amt) < normal_aide.web3.toVon(0.001, "lat")


@pytest.mark.P3
def test_ROE_058(normal_aide, deploy_chain):
    """
    账户余额不足
    """
    delegate_amount = normal_aide.delegate._economic.delegate_limit
    sd_gather = create_staking_delegate_wallet_balance(normal_aide, delegate_amount=delegate_amount)
    with pytest.raises(ValueError) as exception_info:
        normal_aide.delegate.withdrew_delegate(staking_block_identifier=sd_gather.StakingBlockNum,
                                               private_key=sd_gather.delegate_pk,
                                               txn={"gasPrice": sd_gather.sta_del_amt})
    logger.info("str(exception_info.value)")
    assert '-32000' in str(exception_info.value)


@pytest.mark.P1
def test_ROE_060(normal_aide, deploy_chain):
    """
    质押 赎回质押 过了冻结期 再次质押和委托、赎回委托
    """
    delegate_limit = normal_aide.delegate._economic.delegate_limit
    staking_addr, staking_pk = generate_account(normal_aide, normal_aide.delegate._economic.staking_limit * 2)
    assert normal_aide.staking.create_staking(benefit_address=staking_addr, private_key=staking_pk)['code'] == 0
    StakingBlockNum = normal_aide.staking.staking_info.StakingBlockNum
    logger.info(f"one staking_block_num: {StakingBlockNum}")

    wait_settlement(normal_aide)
    assert normal_aide.staking.withdrew_staking(private_key=staking_pk)['code'] == 0

    wait_settlement(normal_aide, settlement=2)
    assert normal_aide.staking.create_staking(benefit_address=staking_addr, private_key=staking_pk)['code'] == 0
    StakingBlockNum = normal_aide.staking.staking_info.StakingBlockNum
    logger.info(f"two staking_block_num: {StakingBlockNum}")

    delegate_addr, delegate_pk = generate_account(normal_aide, delegate_limit * 2)
    assert normal_aide.delegate.delegate(balance_type=0, private_key=delegate_pk)['code'] == 0

    amount1 = normal_aide.platon.get_balance(delegate_addr)
    assert normal_aide.delegate.withdrew_delegate(private_key=delegate_pk,
                                                  staking_block_identifier=StakingBlockNum)['code'] == 0
    amount2 = normal_aide.platon.get_balance(delegate_addr)
    assert delegate_limit - (amount2 - amount1) < normal_aide.web3.toVon(1, "lat")
