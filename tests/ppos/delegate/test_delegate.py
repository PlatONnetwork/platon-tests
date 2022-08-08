import time

from loguru import logger

import allure
import pytest

from lib.account import REWARD_ADDRESS
from lib.funcs import wait_settlement, wait_consensus
from lib.utils import get_pledge_list
from tests.conftest import generate_account


@allure.title("Query delegate parameter validation")
@pytest.mark.P1
@pytest.mark.compatibility
def test_DI_001_009(normal_aide):
    """
    001: 委托 至 备选节点候选人
        - 质押成为备选节点候选人
    009：委托的资金等于低门槛的委托
        - 委托金额(_economic.delegate_limit) 至 备选节点候选人
    """
    address, prikey = generate_account(normal_aide, normal_aide.delegate._economic.staking_limit * 2)
    normal_aide.staking.create_staking(benefit_address=address, private_key=prikey)

    delegate_address, delegate_prikey = generate_account(normal_aide, normal_aide.delegate._economic.delegate_limit * 2)
    delegate_result = normal_aide.delegate.delegate(private_key=delegate_prikey)
    assert delegate_result['code'] == 0

    delegate_info = normal_aide.delegate.get_delegate_info(delegate_address)
    logger.info(delegate_info)
    assert delegate_info.Addr == delegate_address
    assert delegate_info.NodeId == normal_aide.node.node_id
    assert delegate_info.ReleasedHes == normal_aide.delegate._economic.delegate_limit


@allure.title("Delegate to different people")
@pytest.mark.P1
def test_DI_002_003_004(normal_aides):
    """
    002:委托 至 备选节点候选人
    003:委托 至 备选节点
    004:委托 至 验证节点 (验证节点轮流成为提议人进行出块)
    """
    aide1, aide2 = normal_aides[0], normal_aides[1]

    address, prikey = generate_account(aide1, aide1.delegate._economic.staking_limit * 3)
    aide1.staking.create_staking(benefit_address=address, private_key=prikey,
                                 amount=aide2.delegate._economic.staking_limit)

    address, prikey = generate_account(aide2, aide2.delegate._economic.staking_limit * 3)
    aide2.staking.create_staking(benefit_address=address, private_key=prikey,
                                 amount=aide2.delegate._economic.staking_limit * 2)

    wait_settlement(aide1)
    node_id_list = get_pledge_list(aide2.staking.get_verifier_list)
    logger.info("The billing cycle validates the list of people{}".format(node_id_list))
    assert aide1.node.node_id not in node_id_list
    assert aide2.node.node_id in node_id_list

    delegate_address, delegate_prikey = generate_account(aide1, aide1.delegate._economic.delegate_limit * 2)
    logger.info("The candidate delegate")
    delegate_result = aide1.delegate.delegate(private_key=delegate_prikey)
    logger.info(f'delegate_result={delegate_result}')
    assert delegate_result['code'] == 0

    delegate_address2, delegate_prikey2 = generate_account(aide2, aide2.delegate._economic.delegate_limit * 2)
    logger.info("The verifier delegates")
    delegate_result2 = aide2.delegate.delegate(private_key=delegate_prikey2)
    logger.info(f'delegate_result2={delegate_result2}')
    assert delegate_result2['code'] == 0

    wait_consensus(aide1)
    node_id_list = get_pledge_list(aide2.staking.get_validator_list)
    logger.info("Consensus validator list:{}".format(node_id_list))
    assert aide2.node.node_id in node_id_list
    delegate_address3, delegate_prikey3 = generate_account(aide2, aide2.delegate._economic.delegate_limit * 2)
    logger.info("Consensus verifier delegates")
    delegate_result3 = aide2.delegate.delegate(private_key=delegate_prikey3)
    logger.info(f'delegate_result3={delegate_result3}')
    assert delegate_result3['code'] == 0


@allure.title("init_aide can't be delegated")
@pytest.mark.P3
def test_DI_005(init_aide):
    """
    005: init_aide 不能被委托
    # TODO 这里直接抛出错误了,和期望不符合,预估gas
    """
    address, prikey = generate_account(init_aide, init_aide.delegate._economic.delegate_limit * 2)
    result = init_aide.delegate.delegate(private_key=prikey, txn={'gas': 4000000, 'gasPrice': 10000000000})
    logger.info(result)
    assert result['code'] == 301107


@allure.title("The amount entrusted by the client is less than the threshold")
@pytest.mark.P1
def test_DI_006(normal_aide):
    """
    006: 委托金额低于最低门槛
    """
    address, prikey = generate_account(normal_aide, normal_aide.delegate._economic.staking_limit * 2)
    normal_aide.staking.create_staking(benefit_address=address, private_key=prikey)

    delegate_address, delegate_prikey = generate_account(normal_aide, normal_aide.delegate._economic.delegate_limit * 2)
    delegate_result = normal_aide.delegate.delegate(amount=normal_aide.delegate._economic.delegate_limit - 1,
                                                    private_key=delegate_prikey)
    logger.info(delegate_result)
    # assert_code(result, 301105)


@allure.title("gas Insufficient entrustment")
@pytest.mark.P1
def test_DI_007(normal_aide):
    """
    007: gas 不足委托
    """
    address, prikey = generate_account(normal_aide, normal_aide.delegate._economic.staking_limit * 2)
    normal_aide.staking.create_staking(benefit_address=address, private_key=prikey)

    delegate_address, delegate_prikey = generate_account(normal_aide, normal_aide.delegate._economic.delegate_limit * 2)

    with pytest.raises(ValueError) as exception_info:
        normal_aide.delegate.delegate(txn={"gas": 1}, private_key=delegate_prikey)

    assert str(exception_info.value) == "{'code': -32000, 'message': 'intrinsic gas too low'}"


@pytest.mark.P1
def test_DI_008(normal_aide):
    """
    008: 账户余额不足发起委托, 余额不足分两种场景
        - {'code': 301111, 'message': 'The account balance is insufficient'}  够手续费但是不够委托最低门槛
        - {'code': -32000, 'message': 'insufficient funds for gas * price + value'} 不够手续费
    """
    address, prikey = generate_account(normal_aide, normal_aide.delegate._economic.staking_limit * 2)
    normal_aide.staking.create_staking(benefit_address=address, private_key=prikey)

    # 账户余额 够手续费，不满足最低门槛
    delegate_address, delegate_prikey = generate_account(normal_aide, normal_aide.delegate._economic.delegate_limit - 1)
    res = normal_aide.delegate.delegate(private_key=delegate_prikey)
    assert res["code"] == 301111

    delegate_address, delegate_prikey = generate_account(normal_aide, 10)
    with pytest.raises(ValueError) as exception_info:
        normal_aide.delegate.delegate(private_key=delegate_prikey)

    assert str(exception_info.value) == "{'code': -32000, 'message': 'insufficient funds for gas * price + value'}"


@allure.title("Delegate to a candidate who doesn't exist")
@pytest.mark.P3
def test_DI_010(normal_aide):
    """
    010: 对某个不存在的候选人做委托
        - {'code': 301102, 'message': 'The candidate does not exist'}
    """
    illegal_node_id = "7ee3276fd6b9c7864eb896310b5393324b6db785a2528c00cc28ca8c" \
                      "3f86fc229a86f138b1f1c8e3a942204c03faeb40e3b22ab11b8983c35dc025de42865990"
    delegate_address, delegate_prikey = generate_account(normal_aide, 10)
    result = normal_aide.delegate.delegate(node_id=illegal_node_id, private_key=delegate_prikey)
    logger.info(result)
    # assert_code(result, 301102)


@allure.title("Delegate to different people{status}")
@pytest.mark.P1
@pytest.mark.parametrize('status', [0, 1, 2, 3])
def test_DI_011_012_013_014(normal_aide, status):
    """
    0:A valid candidate whose commission is still in doubt
    1:The delegate is also a valid candidate at a lockup period
    2:A candidate whose mandate is voluntarily withdrawn but who is still in the freeze period
    3:A candidate whose mandate has been voluntarily withdrawn and whose freeze period has expired
    """
    address, prikey = generate_account(normal_aide, normal_aide.delegate._economic.staking_limit * 2)
    normal_aide.staking.create_staking(benefit_address=address, private_key=prikey)

    delegate_address, delegate_prikey = generate_account(normal_aide, normal_aide.delegate._economic.delegate_limit * 5)
    if status == 0:
        # A valid candidate whose commission is still in doubt
        delegate_result = normal_aide.delegate.delegate(private_key=delegate_prikey)
        logger.debug(f"0: {delegate_result}")
        assert delegate_result['code'] == 0

    if status == 1:
        # The delegate is also a valid candidate at a lockup period
        wait_settlement(normal_aide)
        delegate_result = normal_aide.delegate.delegate(private_key=delegate_prikey)
        logger.debug(f"1: {delegate_result}")
        assert delegate_result['code'] == 0

    if status == 2:
        # A candidate whose mandate is voluntarily withdrawn but who is still in the freeze period
        wait_settlement(normal_aide)
        withdrew_staking_result = normal_aide.staking.withdrew_staking(private_key=prikey)
        assert withdrew_staking_result['code'] == 0
        logger.info(f'withdrew_staking_result={withdrew_staking_result}')
        delegate_result = normal_aide.delegate.delegate(private_key=delegate_prikey)
        logger.info(f'delegate_result={delegate_result}')
        # assert_code(result, 301103)

    if status == 3:
        # A candidate whose mandate has been voluntarily withdrawn and whose freeze period has expired
        wait_settlement(normal_aide)
        withdrew_staking_result = normal_aide.staking.withdrew_staking(private_key=prikey)
        assert withdrew_staking_result['code'] == 0
        logger.info(f'withdrew_staking_result={withdrew_staking_result}')
        wait_settlement(normal_aide, 2)
        delegate_result = normal_aide.delegate.delegate(private_key=delegate_prikey)
        logger.info(f'delegate_result={delegate_result}')
        # assert_code(result, 301102)


@allure.title("Delegate to candidates whose penalties have lapsed (freeze period and after freeze period)")
@pytest.mark.P1
def test_DI_015_016(normal_aide, init_aide):
    """
    015: 委托被惩罚失效还在冻结期的候选人
    016: 委托被惩罚失效已经过了冻结期的候选人
    """
    staking_limit = normal_aide.delegate._economic.staking_limit
    delegate_limit = normal_aide.delegate._economic.delegate_limit
    address, prikey = generate_account(normal_aide, staking_limit * 2)
    delegate_address, delegate_prikey = generate_account(normal_aide, delegate_limit * 10)
    result = normal_aide.staking.create_staking(benefit_address=address, private_key=prikey)
    assert result['code'] == 0
    wait_settlement(normal_aide)

    candidate_info = init_aide.staking.get_candidate_info(node_id=normal_aide.node.node_id)
    logger.info('candidate_info: {}', candidate_info)
    normal_aide.node.stop()
    logger.info("Close one node")
    for i in range(4):
        wait_consensus(init_aide)  # 第三个共识轮开始惩罚
        candidate_info = init_aide.staking.get_candidate_info(node_id=normal_aide.node.node_id)
        logger.info(candidate_info)
        if candidate_info.Released < staking_limit:
            break
        logger.info("Node exceptions are not penalized")
    # todo: ws重连问题待解决
    normal_aide.node.start()
    logger.info("Restart the node")
    time.sleep(3)
    delegate_result = normal_aide.delegate.delegate(private_key=delegate_prikey)
    logger.info(delegate_result)
    # assert_code(delegate_result, 301103)
    logger.info("-016: Next settlement period")
    wait_settlement(normal_aide, 2)
    delegate_result = normal_aide.delegate.delegate(private_key=delegate_prikey)
    logger.info(f'delegate_result={delegate_result}')
    # assert_code(result, 301102)


@allure.title("Use the pledge account as the entrustment")
@pytest.mark.P1
def test_DI_017(normal_aide):
    """
    017: 使用质押账户做委托
    """
    address, prikey = generate_account(normal_aide, normal_aide.delegate._economic.staking_limit * 2)
    result = normal_aide.staking.create_staking(benefit_address=address, private_key=prikey)
    assert result['code'] == 0
    delegate_result = normal_aide.delegate.delegate(private_key=prikey)
    logger.info(f'delegate_result={delegate_result}')
    # assert_code(result, 301106)


@allure.title("Delegate to candidates whose revenue address is the incentive pool")
@pytest.mark.P1
def test_DI_018(normal_aide):
    """
    018: 对收益地址是激励池的候选人做委托
    """
    address, prikey = generate_account(normal_aide, normal_aide.delegate._economic.staking_limit * 2)
    result = normal_aide.staking.create_staking(benefit_address=REWARD_ADDRESS, private_key=prikey)
    assert result['code'] == 0
    delegate_address, delegate_prikey = generate_account(normal_aide, normal_aide.delegate._economic.delegate_limit * 2)
    delegate_result = normal_aide.delegate.delegate(private_key=delegate_prikey)
    logger.info(f'delegate_result={delegate_result}')
    # {'code': 301107, 'message': 'The candidate is not allowed to delegate'}


@allure.title("After verifying the node delegation, cancel the pledge, and pledge and delegate again")
@pytest.mark.P1
def test_DI_019(normal_aide):
    """
    019: 验证节点委托后取消质押,并再次质押和委托
    """
    address, prikey = generate_account(normal_aide, normal_aide.delegate._economic.staking_limit * 2)
    normal_aide.staking.create_staking(benefit_address=address, private_key=prikey)

    delegate_address, delegate_prikey = generate_account(normal_aide, normal_aide.delegate._economic.delegate_limit * 3)
    delegate_result = normal_aide.delegate.delegate(private_key=delegate_prikey)
    assert delegate_result['code'] == 0
    result = normal_aide.staking.withdrew_staking(private_key=prikey)
    assert result['code'] == 0

    # Repeat staking
    result = normal_aide.staking.create_staking(benefit_address=address, private_key=prikey)
    assert result['code'] == 0
    result = normal_aide.delegate.delegate(private_key=delegate_prikey)
    assert result['code'] == 0

    # Recheck wallet associations
    msg = normal_aide.delegate.get_delegate_list(address=delegate_address)
    logger.info(msg)

    assert len(msg) == 2
    for delegate_info in msg:
        assert delegate_info.Addr == delegate_address
        assert delegate_info.NodeId == normal_aide.node.node_id


@allure.title("Delegate to the non-verifier")
@pytest.mark.P3
def test_DI_020(normal_aides):
    """
    020: 委托给非验证人
    """
    normal_aide1, normal_aide2 = normal_aides[0], normal_aides[1]
    delegate_address, delegate_prikey = generate_account(normal_aide1, normal_aide1.delegate._economic.delegate_limit * 3)
    result = normal_aide1.delegate.delegate(node_id=normal_aide2.node.node_id, private_key=delegate_prikey)
    logger.info(result)
    # {'code': 301102, 'message': 'The candidate does not exist'}


@allure.title("The entrusted verifier is penalized to verify the entrusted principal")
@pytest.mark.P3
def test_DI_021(normal_aide, init_aide):
    """
    :param normal_aide_obj:
    :param init_aide_obj:
    :return:
    """
    value = normal_aide.delegate._economic.staking_limit
    address, prikey = generate_account(normal_aide, value * 3)
    normal_aide.staking.create_staking(amount=value, benefit_address=address, private_key=prikey)

    delegate_address, delegate_prikey = generate_account(normal_aide, normal_aide.delegate._economic.delegate_limit * 3)
    delegate_result = normal_aide.delegate.delegate(private_key=delegate_prikey)
    assert delegate_result['status'] == 1
    logger.info(delegate_result)

    msg = normal_aide.staking.staking_info
    staking_blocknum = msg.StakingBlockNum
    logger.info("Close one node")
    normal_aide.node.stop()
    node = init_aide.node
    logger.info("The next two periods")
    wait_settlement(init_aide, 2)
    logger.info("Restart the node")
    # todo: 重启ws重连问题待解决
    normal_aide.node.start()
    msg = init_aide.delegate.get_delegate_info()
    logger.info(msg)
    assert msg.Released == normal_aide.delegate._economic.delegate_limit


@allure.title("Free amount in different periods when additional entrustment is made")
@pytest.mark.P2
@pytest.mark.parametrize('status', [0, 1, 2])
def test_DI_022_023_024(normal_aide, defer_reset_chain, status):
    """
    022:There is only the free amount of hesitation period when additional entrusting
    023:Only the free amount of the lockup period exists when the delegate is added
    024:The amount of both hesitation period and lockup period exists when additional entrustment is made
    :param normal_aide_obj:
    :param status:
    :return:
    """
    # todo: 价格deploy_all的方法,或者等等看ws重连问题解决后可不可以
    value = normal_aide.delegate._economic.staking_limit
    address, prikey = generate_account(normal_aide, value * 3)
    normal_aide.staking.create_staking(amount=value, benefit_address=address, private_key=prikey)

    delegate_address, delegate_prikey = generate_account(normal_aide, normal_aide.delegate._economic.delegate_limit * 3)
    delegate_result = normal_aide.delegate.delegate(private_key=delegate_prikey)
    assert delegate_result['status'] == 1
    logger.info(delegate_result)

    msg = normal_aide.staking.staking_info
    staking_blocknum = msg.StakingBlockNum

    if status == 0:
        result = normal_aide.delegate.delegate(private_key=delegate_prikey)
        logger.info(result)
        msg = normal_aide.delegate.get_delegate_info(address=delegate_address)
        logger.info(msg)
        assert msg.ReleasedHes == normal_aide.delegate._economic.delegate_limit * 2

    if status == 1:
        wait_settlement(normal_aide)
        result = normal_aide.delegate.delegate(private_key=delegate_prikey)
        logger.info(result)
        msg = msg = normal_aide.delegate.get_delegate_info(address=delegate_address)
        logger.info(msg)
        assert msg.ReleasedHes == normal_aide.delegate._economic.delegate_limit
        assert msg.Released == normal_aide.delegate._economic.delegate_limit

    if status == 2:
        wait_settlement(normal_aide)
        result = normal_aide.delegate.delegate(private_key=delegate_prikey)
        logger.info(result)
        result = normal_aide.delegate.delegate(private_key=delegate_prikey)
        logger.info(result)
        msg = msg = normal_aide.delegate.get_delegate_info(address=delegate_address)
        logger.info(msg)
        assert msg.ReleasedHes == normal_aide.delegate._economic.delegate_limit * 2
        assert msg.Released == normal_aide.delegate._economic.delegate_limit


@allure.title("uncommitted")
@pytest.mark.P2
def test_DI_025(normal_aide):
    """
    :param normal_aide_obj:
    :return:
    """
    delegate_address, delegate_prikey = generate_account(normal_aide, normal_aide.delegate._economic.delegate_limit * 3)
    result = normal_aide.delegate.get_delegate_info(address=delegate_address)
    logger.info(result)
    # assert_code(result, 301203)


@allure.title("The entrusted candidate is valid")
@pytest.mark.P2
def test_DI_026(normal_aide):
    """
    :param normal_aide_obj:
    :return:
    """
    address, prikey = generate_account(normal_aide, normal_aide.delegate._economic.staking_limit * 2)
    normal_aide.staking.create_staking(benefit_address=address, private_key=prikey)

    delegate_address, delegate_prikey = generate_account(normal_aide, normal_aide.delegate._economic.delegate_limit * 3)
    delegate_result = normal_aide.delegate.delegate(private_key=delegate_prikey)
    assert delegate_result['status'] == 1
    logger.info(delegate_result)

    delegate_list = normal_aide.delegate.get_delegate_list(address=delegate_address)
    logger.info(delegate_list)
    # assert result["Code"] == 0
    # assert client_new_node.node.web3.toChecksumAddress(result["Ret"][0]["Addr"]) == address_delegate
    # assert result["Ret"][0]["NodeId"] == client_new_node.node.node_id
    assert delegate_list.Addr == delegate_address
    assert delegate_list.NodeID == normal_aide.node.node_id


@allure.title("The entrusted candidate does not exist")
@pytest.mark.P2
def test_DI_027(normal_aide):
    """
    The entrusted candidate does not exist
    :param normal_aide_obj:
    :return:
    """
    address, prikey = generate_account(normal_aide, normal_aide.delegate._economic.staking_limit * 2)
    delegate_address, delegate_prikey = generate_account(normal_aide, normal_aide.delegate._economic.delegate_limit * 3)
    illegal_node_id = "7ee3276fd6b9c7864eb896310b5393324b6db785a2528c00cc28ca8c" \
                      "3f86fc229a86f138b1f1c8e3a942204c03faeb40e3b22ab11b8983c35dc025de42865990"

    result = normal_aide.delegate.delegate(node_id=illegal_node_id, private_key=delegate_prikey)
    logger.info(result)
    delegate_list = normal_aide.delegate.get_delegate_list(address=delegate_address)
    logger.info(delegate_list)
    # assert_code(result, 301203)


@allure.title("The entrusted candidate is invalid")
@pytest.mark.P2
def test_DI_028(normal_aide):
    """
    The entrusted candidate is invalid
    """
    address, prikey = generate_account(normal_aide, normal_aide.delegate._economic.staking_limit * 2)
    normal_aide.staking.create_staking(benefit_address=address, private_key=prikey)

    delegate_address, delegate_prikey = generate_account(normal_aide, normal_aide.delegate._economic.delegate_limit * 3)
    delegate_result = normal_aide.delegate.delegate(private_key=delegate_prikey)
    assert delegate_result['status'] == 1
    logger.info(delegate_result)

    # Exit the pledge
    withdrew_staking_result = normal_aide.staking.withdrew_staking(private_key=prikey)
    delegate_list = normal_aide.delegate.get_delegate_list(address=delegate_address)
    logger.info(delegate_list)
    # assert result["Code"] == 0
    # assert client_new_node.node.web3.toChecksumAddress(result["Ret"][0]["Addr"]) == address_delegate
    # assert result["Ret"][0]["NodeId"] == client_new_node.node.node_id
    assert delegate_list.Addr == delegate_address
    assert delegate_list.NodeID == normal_aide.node.node_id


@allure.title("Delegate information in the hesitation period, lock period")
@pytest.mark.P2
def test_DI_029_030(normal_aide):
    """
    029:Hesitation period inquiry entrustment details
    030:Lock periodic query information
    """
    address, prikey = generate_account(normal_aide, normal_aide.delegate._economic.staking_limit * 2)
    normal_aide.staking.create_staking(benefit_address=address, private_key=prikey)

    delegate_address, delegate_prikey = generate_account(normal_aide, normal_aide.delegate._economic.delegate_limit * 3)
    delegate_result = normal_aide.delegate.delegate(private_key=delegate_prikey)
    assert delegate_result['status'] == 1
    logger.info(delegate_result)

    # Hesitation period inquiry entrustment details
    delegate_list = normal_aide.delegate.get_delegate_list(address=delegate_address)
    logger.info(delegate_list)
    logger.info("The next cycle")
    wait_settlement(normal_aide)
    delegate_list = normal_aide.delegate.get_delegate_list(address=delegate_address)
    logger.info(delegate_list)
    # assert result["Code"] == 0
    # assert client_new_node.node.web3.toChecksumAddress(result["Ret"][0]["Addr"]) == address_delegate
    # assert result["Ret"][0]["NodeId"] == client_new_node.node.node_id
    assert delegate_list.Addr == delegate_address
    assert delegate_list.NodeID == normal_aide.node.node_id


@allure.title("The delegate message no longer exists")
@pytest.mark.P2
def test_DI_031(normal_aide):
    """
    The delegate message no longer exists
    """
    value = normal_aide.delegate._economic.staking_limit
    address, prikey = generate_account(normal_aide, value * 3)
    normal_aide.staking.create_staking(amount=value, benefit_address=address, private_key=prikey)

    delegate_address, delegate_prikey = generate_account(normal_aide, normal_aide.delegate._economic.delegate_limit * 3)
    delegate_result = normal_aide.delegate.delegate(private_key=delegate_prikey)
    assert delegate_result['status'] == 1
    logger.info(delegate_result)

    msg = normal_aide.staking.staking_info
    staking_blocknum = msg.StakingBlockNum

    result = normal_aide.delegate.withdrew_delegate(private_key=delegate_prikey)
    # assert_code(result, 0)
    logger.info(result)
    result = normal_aide.delegate.get_delegate_info()
    logger.info(result)
    # assert_code(result, 301205)


@allure.title("The commission information is still in the hesitation period & The delegate information is still locked")
@pytest.mark.P2
def test_DI_032_033(normal_aide):
    """
    032:The commission information is still in the hesitation period
    033The delegate information is still locked
    """
    value = normal_aide.delegate._economic.staking_limit
    address, prikey = generate_account(normal_aide, value * 3)
    normal_aide.staking.create_staking(amount=value, benefit_address=address, private_key=prikey)

    delegate_address, delegate_prikey = generate_account(normal_aide, normal_aide.delegate._economic.delegate_limit * 3)
    delegate_result = normal_aide.delegate.delegate(private_key=delegate_prikey)
    assert delegate_result['status'] == 1
    logger.info(delegate_result)

    msg = normal_aide.staking.staking_info
    staking_blocknum = msg.StakingBlockNum

    # Hesitation period inquiry entrustment details
    result = normal_aide.delegate.get_delegate_info(address=delegate_address)
    logger.info(result)
    # assert client_new_node.node.web3.toChecksumAddress(result["Ret"]["Addr"]) == address_delegate
    # assert result["Ret"]["NodeId"] == client_new_node.node.node_id
    assert result.Addr == delegate_address
    assert result.NodeID == normal_aide.node.node_id
    logger.info("The next cycle")
    wait_consensus(normal_aide)
    result = normal_aide.delegate.get_delegate_info(address=delegate_address)
    logger.info(result)
    # assert client_new_node.node.web3.toChecksumAddress(result["Ret"]["Addr"]) == address_delegate
    # assert result["Ret"]["NodeId"] == client_new_node.node.node_id
    assert result.Addr == delegate_address
    assert result.NodeId == normal_aide.node.node_id


@allure.title("The entrusted candidate has withdrawn of his own accord")
@pytest.mark.P2
def test_DI_034(normal_aide):
    """
    The entrusted candidate has withdrawn of his own accord
    """
    value = normal_aide.delegate._economic.staking_limit
    address, prikey = generate_account(normal_aide, value * 3)
    normal_aide.staking.create_staking(amount=value, benefit_address=address, private_key=prikey)

    delegate_address, delegate_prikey = generate_account(normal_aide, normal_aide.delegate._economic.delegate_limit * 3)
    delegate_result = normal_aide.delegate.delegate(private_key=delegate_prikey)
    assert delegate_result['status'] == 1
    logger.info(delegate_result)

    msg = normal_aide.staking.staking_info
    staking_blocknum = msg.StakingBlockNum

    # Exit the pledge
    withdrew_staking_result = normal_aide.staking.withdrew_staking(private_key=prikey)

    result = normal_aide.delegate.get_delegate_info(address=delegate_address, staking_block_identifier=staking_blocknum)
    logger.info(result)
    # assert client_new_node.node.web3.toChecksumAddress(result["Ret"]["Addr"]) == address_delegate
    # assert result["Ret"]["NodeId"] == client_new_node.node.node_id
    assert result.Addr == delegate_address
    assert result.NodeId == normal_aide.node.node_id


@allure.title("Entrusted candidate (penalized in lockup period, penalized out completely)")
@pytest.mark.P2
def test_DI_035_036(normal_aide, init_aide):
    """
    The entrusted candidate is still penalized in the lockup period
    The entrusted candidate was penalized to withdraw completely

    """
    value = normal_aide.delegate._economic.staking_limit
    address, prikey = generate_account(normal_aide, value * 3)
    normal_aide.staking.create_staking(amount=value, benefit_address=address, private_key=prikey)

    delegate_address, delegate_prikey = generate_account(normal_aide, normal_aide.delegate._economic.delegate_limit * 3)
    delegate_result = normal_aide.delegate.delegate(private_key=delegate_prikey)
    assert delegate_result['status'] == 1
    logger.info(delegate_result)

    msg = normal_aide.staking.staking_info
    staking_blocknum = msg.StakingBlockNum

    # The validation node becomes the out-block validation node
    wait_consensus(init_aide, 4)
    validator_list = get_pledge_list(init_aide.staking.get_validator_list)
    assert normal_aide.node.node_id in validator_list
    candidate_info = init_aide.staking.get_candidate_info(node_id=normal_aide.node.node_id)
    logger.info(candidate_info)

    logger.info("Close one node")
    normal_aide.node.stop()
    for i in range(4):
        wait_consensus(init_aide)
        candidate_info = init_aide.staking.get_candidate_info(node_id=normal_aide.node.node_id)
        logger.info(candidate_info)
        if candidate_info.Released < value:
            break

    result = init_aide.delegate.get_delegate_info(address=delegate_address, staking_block_identifier=staking_blocknum)
    logger.info(result)
    # assert other_node.web3.toChecksumAddress(result["Ret"]["Addr"]) == address_delegate
    # assert result["Ret"]["NodeId"] == node.node_id
    assert result.Addr == delegate_address
    assert result.NodeId == normal_aide.node.node_id
    logger.info("Restart the node")
    normal_aide.node.start()
    logger.info("Next settlement period")
    wait_settlement(init_aide, 2)

    result = init_aide.delegate.get_delegate_info(address=delegate_address, staking_block_identifier=staking_blocknum)
    logger.info(result)
    # assert other_node.web3.toChecksumAddress(result["Ret"]["Addr"]) == address_delegate
    # assert result["Ret"]["NodeId"] == node.node_id
    assert result.Addr == delegate_address
    assert result.NodeId == normal_aide.node.node_id


@allure.title("Query for delegate information in undo")
@pytest.mark.P2
def test_DI_038(normal_aide):
    """
    Query for delegate information in undo
    :param normal_aide_obj:
    :return:
    """
    value = normal_aide.delegate._economic.staking_limit
    address, prikey = generate_account(normal_aide, value * 3)
    normal_aide.staking.create_staking(amount=value, benefit_address=address, private_key=prikey)

    delegate_address, delegate_prikey = generate_account(normal_aide, normal_aide.delegate._economic.delegate_limit * 3)
    delegate_result = normal_aide.delegate.delegate(private_key=delegate_prikey)
    assert delegate_result['status'] == 1
    logger.info(delegate_result)

    msg = normal_aide.staking.staking_info
    staking_blocknum = msg.StakingBlockNum

    logger.info("The next cycle")
    wait_consensus(normal_aide)

    # Exit the pledge
    withdrew_staking_result = normal_aide.staking.withdrew_staking(private_key=prikey)
    logger(f'withdrew_staking_result={withdrew_staking_result}')

    result = normal_aide.delegate.get_delegate_info(address=delegate_address, staking_block_identifier=staking_blocknum)
    logger.info(result)
    # assert client_new_node.node.web3.toChecksumAddress(result["Ret"]["Addr"]) == address_delegate
    # assert result["Ret"]["NodeId"] == client_new_node.node.node_id
    assert result.Addr == delegate_address
    assert result.NodeId == normal_aide.node.node_id
