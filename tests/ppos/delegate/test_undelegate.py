import pytest
from platon._utils.error_code import ERROR_CODE

from lib.funcs import wait_settlement
from tests.conftest import generate_account
from loguru import logger


@pytest.mark.P0
@pytest.mark.compatibility
def test_ROE_001_007_015(normal_aide):
    """
    和用例test_DI_031一致，需要合并吗？
    """
    value = normal_aide.delegate._economic.staking_limit
    address, pk = generate_account(normal_aide, value * 3)
    normal_aide.staking.create_staking(amount=value, benefit_address=address, private_key=pk)

    delegate_address, delegate_pk = generate_account(normal_aide, normal_aide.delegate._economic.delegate_limit * 3)
    assert normal_aide.delegate.delegate(private_key=delegate_pk)['code'] == 0

    assert normal_aide.delegate.withdrew_delegate(private_key=delegate_pk)['code'] == 0


@pytest.mark.P1
def test_ROE_002(normal_aide):
    """

    """
    value = normal_aide.delegate._economic.staking_limit
    address, pk = generate_account(normal_aide, value * 3)
    normal_aide.staking.create_staking(amount=value, benefit_address=address, private_key=pk)

    delegate_address, delegate_pk = generate_account(normal_aide, normal_aide.delegate._economic.delegate_limit * 3)
    assert normal_aide.delegate.delegate(private_key=delegate_pk)['code'] == 0

    with pytest.raises(ValueError) as exception_info:
        normal_aide.delegate.withdrew_delegate(txn={"gas": 1}, private_key=delegate_pk)

    assert str(exception_info.value) == "{'code': -32000, 'message': 'intrinsic gas too low'}"


@pytest.mark.P3
def test_ROE_003(normal_aide):
    """

    """
    value = normal_aide.delegate._economic.staking_limit
    address, pk = generate_account(normal_aide, value * 3)
    normal_aide.staking.create_staking(amount=value, benefit_address=address, private_key=pk)

    delegate_address, delegate_pk = generate_account(normal_aide, normal_aide.delegate._economic.delegate_limit * 3)
    assert normal_aide.delegate.delegate(private_key=delegate_pk)['code'] == 0

    illegal_nodeID = "7ee3276fd6b9c7864eb896310b5393324b6db785a2528c00cc28ca8c" \
                     "3f86fc229a86f138b1f1c8e3a942204c03faeb40e3b22ab11b8983c35dc025de42865990"
    result = normal_aide.delegate.withdrew_delegate(node_id=illegal_nodeID, private_key=delegate_pk)
    logger.info(result)
    assert ERROR_CODE[301109] == result['message']


@pytest.mark.P1
def test_ROE_004(normal_aide):
    """

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


@pytest.mark.P1
def test_ROE_005_018(normal_aide):
    """

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
    logger.info(f"Receive the amount entrusted by the lockup period: {res}")
    amount_after = normal_aide.platon.get_balance(delegate_address)
    logger.info("The wallet balance:{}".format(amount_after))
    delegate_limit = normal_aide.delegate._economic.delegate_limit
    assert delegate_limit - (amount_after - amount) < normal_aide.web3.toVon(1, 'lat')


@pytest.mark.P1
def test_ROE_006_008(normal_aide):
    """

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
    delegate_limit = normal_aide.delegate._economic.delegate_limit
    assert delegate_limit * 2 - (amount_after - amount) < normal_aide.web3.toVon(1, 'lat')


@pytest.mark.P1
def test_ROE_010(normal_aide):
    """

    """
    # client_new_node.economic.env.deploy_all()
    delegate_address, delegate_pk = generate_account(normal_aide, normal_aide.delegate._economic.staking_limit)
    lockup_amount = normal_aide.web3.toVon(1000, 'lat')
    plan = [{'Epoch': 1, 'Amount': lockup_amount}]
    # Create a lock plan
    result = normal_aide.transfer.restricting(release_address=delegate_address, plans=plan)
    logger.info(result)

    msg = normal_aide.transfer.get_restricting_info(delegate_address)
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
