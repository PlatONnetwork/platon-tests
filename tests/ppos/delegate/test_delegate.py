import time

from loguru import logger

import allure
import pytest
from platon._utils.error_code import ERROR_CODE
from platon_utils import to_bech32_address

from setting.account import REWARD_ADDRESS
from lib.utils import wait_settlement, wait_consensus, new_account, lat
from lib.utils import get_pledge_list


@allure.title("Query delegate parameter validation")
@pytest.mark.P1
def test_DI_001_009(normal_aide, recover):
    """
    001: 委托 至 备选节点候选人
        - 质押成为备选节点候选人
    009：委托的资金等于低门槛的委托
        - 委托金额(_economic.delegate_limit) 至 备选节点候选人
    """
    sta_account = new_account(normal_aide, normal_aide.economic.staking_limit * 2)
    address, prikey = sta_account.address, sta_account.privateKey
    normal_aide.staking.create_staking(benefit_address=address, private_key=prikey)

    del_account = new_account(normal_aide, normal_aide.economic.delegate_limit * 2)
    delegate_address, delegate_prikey = del_account.address, del_account.privateKey
    delegate_result = normal_aide.delegate.delegate(private_key=delegate_prikey)
    assert delegate_result['code'] == 0

    delegate_info = normal_aide.delegate.get_delegate_info(delegate_address)
    logger.info(delegate_info)
    assert delegate_info.Addr == to_bech32_address(delegate_address, 'lat')
    assert delegate_info.NodeId == normal_aide.node_id
    assert delegate_info.ReleasedHes == normal_aide.economic.delegate_limit


@allure.title("Delegate to different people")
@pytest.mark.P1
def test_DI_002_003_004(normal_aides, recover):
    """
    002:委托 至 备选节点候选人
    003:委托 至 备选节点
    004:委托 至 验证节点 (验证节点轮流成为提议人进行出块)
    """
    aide1, aide2 = normal_aides[0], normal_aides[1]
    sta_account = new_account(aide1, aide1.economic.staking_limit * 3)
    address, prikey = sta_account.address, sta_account.privateKey
    aide1.staking.create_staking(benefit_address=address, private_key=prikey,
                                 amount=aide2.economic.staking_limit)

    sta_account = new_account(aide2, aide2.economic.staking_limit * 3)
    address, prikey = sta_account.address, sta_account.privateKey
    aide2.staking.create_staking(benefit_address=address, private_key=prikey,
                                 amount=aide2.economic.staking_limit * 2)

    wait_settlement(aide1)
    node_id_list = get_pledge_list(aide2.staking.get_verifier_list)
    logger.info("The billing cycle validates the list of people{}".format(node_id_list))
    assert aide1.node_id not in node_id_list
    assert aide2.node_id in node_id_list

    del_account = new_account(aide1, aide1.economic.delegate_limit * 2)
    delegate_address, delegate_prikey = del_account.address, del_account.privateKey
    logger.info("The candidate delegate")
    delegate_result = aide1.delegate.delegate(private_key=delegate_prikey)
    logger.info(f'delegate_result={delegate_result}')
    assert delegate_result['code'] == 0

    del2_account = new_account(aide2, aide2.economic.delegate_limit * 2)
    delegate_address2, delegate_prikey2 = del2_account.address, del2_account.privateKey
    logger.info("The verifier delegates")
    delegate_result2 = aide2.delegate.delegate(private_key=delegate_prikey2)
    logger.info(f'delegate_result2={delegate_result2}')
    assert delegate_result2['code'] == 0

    wait_consensus(aide1)
    node_id_list = get_pledge_list(aide2.staking.get_validator_list)
    logger.info("Consensus validator list:{}".format(node_id_list))
    assert aide2.node_id in node_id_list
    del3_account = new_account(aide2, aide2.economic.delegate_limit * 2)
    delegate_address3, delegate_prikey3 = del3_account.address, del3_account.privateKey
    logger.info("Consensus verifier delegates")
    delegate_result3 = aide2.delegate.delegate(private_key=delegate_prikey3)
    logger.info(f'delegate_result3={delegate_result3}')
    assert delegate_result3['code'] == 0


@allure.title("init_aide can't be delegated")
@pytest.mark.P3
def test_DI_005(init_aide):
    """
    005: init_aide 不能被委托
    """
    sta_account = new_account(init_aide, init_aide.economic.delegate_limit * 2)
    address, prikey = sta_account.address, sta_account.privateKey
    result = init_aide.delegate.delegate(private_key=prikey)
    logger.info(result)
    assert ERROR_CODE[301107] == result.message


@allure.title("The amount entrusted by the client is less than the threshold")
@pytest.mark.P1
def test_DI_006(normal_aide, recover):
    """
    006: 委托金额低于最低门槛
    """
    sta_account = new_account(normal_aide, normal_aide.economic.staking_limit * 2)
    address, prikey = sta_account.address, sta_account.privateKey
    normal_aide.staking.create_staking(benefit_address=address, private_key=prikey)

    del_account = new_account(normal_aide, normal_aide.economic.delegate_limit * 2)
    delegate_address, delegate_prikey = del_account.address, del_account.privateKey
    delegate_result = normal_aide.delegate.delegate(amount=normal_aide.economic.delegate_limit - 1,
                                                    private_key=delegate_prikey)
    logger.info(delegate_result)
    assert ERROR_CODE[301105] == delegate_result.message


@allure.title("gas Insufficient entrustment")
@pytest.mark.P1
def test_DI_007(normal_aide, recover):
    """
    007: gas 不足委托
    """
    sta_account = new_account(normal_aide, normal_aide.economic.staking_limit * 2)
    address, prikey = sta_account.address, sta_account.privateKey
    normal_aide.staking.create_staking(benefit_address=address, private_key=prikey)

    del_account = new_account(normal_aide, normal_aide.economic.delegate_limit * 2)
    delegate_address, delegate_prikey = del_account.address, del_account.privateKey

    with pytest.raises(ValueError) as exception_info:
        normal_aide.delegate.delegate(txn={"gas": 1}, private_key=delegate_prikey)

    assert str(exception_info.value) == "{'code': -32000, 'message': 'intrinsic gas too low'}"


@pytest.mark.P1
def test_DI_008(normal_aide, recover):
    """
    008: 账户余额不足发起委托, 余额不足分两种场景
        - {'code': 301111, 'message': 'The account balance is insufficient'}  够手续费但是不够委托最低门槛
        - {'code': -32000, 'message': 'insufficient funds for gas * price + value'} 不够手续费
    """
    sta_account = new_account(normal_aide, normal_aide.economic.staking_limit * 2)
    address, prikey = sta_account.address, sta_account.privateKey
    normal_aide.staking.create_staking(benefit_address=address, private_key=prikey)

    # 账户余额 够手续费，不满足最低门槛
    del_account = new_account(normal_aide, normal_aide.economic.delegate_limit - 1)
    delegate_address, delegate_prikey = del_account.address, del_account.privateKey
    res = normal_aide.delegate.delegate(private_key=delegate_prikey)
    assert res["code"] == 301111

    del_account1 = new_account(normal_aide, 10)
    delegate_address, delegate_prikey = del_account1.address, del_account1.privateKey
    with pytest.raises(ValueError) as exception_info:
        normal_aide.delegate.delegate(private_key=delegate_prikey)

    assert str(exception_info.value) == "{'code': -32000, 'message': 'insufficient funds for gas * price + value'}"


@allure.title("Delegate to a candidate who doesn't exist")
@pytest.mark.P3
def test_DI_010(normal_aide, recover):
    """
    010: 对某个不存在的候选人做委托
        - {'code': 301102, 'message': 'The candidate does not exist'}
    """
    illegal_node_id = "7ee3276fd6b9c7864eb896310b5393324b6db785a2528c00cc28ca8c" \
                      "3f86fc229a86f138b1f1c8e3a942204c03faeb40e3b22ab11b8983c35dc025de42865990"
    del_account = new_account(normal_aide, 10)
    delegate_address, delegate_prikey = del_account.address, del_account.privateKey
    result = normal_aide.delegate.delegate(node_id=illegal_node_id, private_key=delegate_prikey)
    logger.info(result)
    assert ERROR_CODE[301102] == result.message


@allure.title("Delegate to different people")
@pytest.mark.P1
def test_DI_011_012_013_014(normal_aide, recover):
    """
    0:A valid candidate whose commission is still in doubt
    1:The delegate is also a valid candidate at a lockup period
    2:A candidate whose mandate is voluntarily withdrawn but who is still in the freeze period
    3:A candidate whose mandate has been voluntarily withdrawn and whose freeze period has expired
    """
    sta_account = new_account(normal_aide, normal_aide.economic.staking_limit * 2)
    address, prikey = sta_account.address, sta_account.privateKey
    normal_aide.staking.create_staking(benefit_address=address, private_key=prikey)
    del_account = new_account(normal_aide, normal_aide.economic.delegate_limit * 5)
    delegate_address, delegate_prikey = del_account.address, del_account.privateKey

    # A valid candidate whose commission is still in doubt
    delegate_result = normal_aide.delegate.delegate(private_key=delegate_prikey)
    assert delegate_result['code'] == 0

    # The delegate is also a valid candidate at a lockup period
    wait_settlement(normal_aide)
    delegate_result = normal_aide.delegate.delegate(private_key=delegate_prikey)
    assert delegate_result['code'] == 0

    # A candidate whose mandate is voluntarily withdrawn but who is still in the freeze period
    wait_settlement(normal_aide)
    withdrew_staking_result = normal_aide.staking.withdrew_staking(private_key=prikey)
    assert withdrew_staking_result['code'] == 0
    delegate_result = normal_aide.delegate.delegate(private_key=delegate_prikey)
    logger.info(f'delegate_result={delegate_result}')
    assert ERROR_CODE[301103] == delegate_result.message

    # A candidate whose mandate has been voluntarily withdrawn and whose freeze period has expired
    wait_settlement(normal_aide, 2)
    delegate_result = normal_aide.delegate.delegate(private_key=delegate_prikey)
    logger.info(f'delegate_result={delegate_result}')
    assert ERROR_CODE[301102] == delegate_result.message


@allure.title("Delegate to candidates whose penalties have lapsed (freeze period and after freeze period)")
@pytest.mark.P1
def test_DI_015_016(normal_node, init_aide, recover):
    """
    015: 委托被惩罚失效还在冻结期的候选人
    016: 委托被惩罚失效已经过了冻结期的候选人
    """
    normal_aide = normal_node.aide
    staking_limit = normal_aide.economic.staking_limit
    delegate_limit = normal_aide.economic.delegate_limit
    sta_account = new_account(normal_aide, staking_limit * 2)
    address, prikey = sta_account.address, sta_account.privateKey
    del_account = new_account(normal_aide, delegate_limit * 10)
    delegate_address, delegate_prikey = del_account.address, del_account.privateKey
    result = normal_aide.staking.create_staking(benefit_address=address, private_key=prikey)
    assert result['code'] == 0
    wait_settlement(normal_aide)

    candidate_info = init_aide.staking.get_candidate_info(node_id=normal_aide.node_id)
    logger.info('candidate_info: {}', candidate_info)
    normal_node.stop()
    logger.info("Close one node")
    for i in range(4):
        wait_consensus(init_aide)  # 第三个共识轮开始惩罚
        candidate_info = init_aide.staking.get_candidate_info(candidate_info.NodeId)
        logger.info(candidate_info)
        if candidate_info.Released < staking_limit:
            break
        logger.info("Node exceptions are not penalized")
    normal_node.start()
    logger.info("Restart the node")
    delegate_result = normal_aide.delegate.delegate(private_key=delegate_prikey)
    logger.info(delegate_result)
    assert ERROR_CODE[301103] == delegate_result.message
    logger.info("-016: Next settlement period")
    wait_settlement(normal_aide, 2)
    delegate_result = normal_aide.delegate.delegate(private_key=delegate_prikey)
    logger.info(f'delegate_result={delegate_result}')
    assert ERROR_CODE[301102] == delegate_result.message


@allure.title("Use the pledge account as the entrustment")
@pytest.mark.P1
def test_DI_017(normal_aide, recover):
    """
    017: 使用质押账户做委托
    """
    sta_account = new_account(normal_aide, normal_aide.economic.staking_limit * 2)
    address, prikey = sta_account.address, sta_account.privateKey
    result = normal_aide.staking.create_staking(benefit_address=address, private_key=prikey)
    assert result['code'] == 0
    delegate_result = normal_aide.delegate.delegate(private_key=prikey)
    logger.info(f'delegate_result={delegate_result}')
    assert ERROR_CODE[301106] == delegate_result.message


@allure.title("Delegate to candidates whose revenue address is the incentive pool")
@pytest.mark.P1
def test_DI_018(normal_aide, recover):
    """
    018: 对收益地址是激励池的候选人做委托
    """
    sta_account = new_account(normal_aide, normal_aide.economic.staking_limit * 2)
    address, prikey = sta_account.address, sta_account.privateKey
    result = normal_aide.staking.create_staking(benefit_address=REWARD_ADDRESS, private_key=prikey)
    assert result['code'] == 0
    del_account = new_account(normal_aide, normal_aide.economic.delegate_limit * 2)
    delegate_address, delegate_prikey = del_account.address, del_account.privateKey
    delegate_result = normal_aide.delegate.delegate(private_key=delegate_prikey)
    logger.info(f'delegate_result={delegate_result}')
    assert ERROR_CODE[301107] == delegate_result.message


@allure.title("After verifying the node delegation, cancel the pledge, and pledge and delegate again")
@pytest.mark.P1
def test_DI_019(normal_aide, recover):
    """
    019: 验证节点委托后取消质押,并再次质押和委托
        - 再次质押计算 节点被委托的未生效总数 == normal_aide.economic.staking_limit
    """
    sta_account = new_account(normal_aide, normal_aide.economic.staking_limit * 2)
    address, prikey = sta_account.address, sta_account.privateKey

    normal_aide.staking.create_staking(benefit_address=address, private_key=prikey)

    del_account = new_account(normal_aide, normal_aide.economic.delegate_limit * 3)
    delegate_address, delegate_prikey = del_account.address, del_account.privateKey
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
        assert delegate_info.Addr == to_bech32_address(delegate_address, 'lat')
        assert delegate_info.NodeId == normal_aide.node_id

    staking_info = normal_aide.staking.staking_info  # 节点被委托的未生效总数量
    assert staking_info.DelegateTotalHes == normal_aide.economic.delegate_limit


@allure.title("Delegate to the non-verifier")
@pytest.mark.P3
def test_DI_020(normal_aides):
    """
    020: 委托给非验证人
    """
    normal_aide1, normal_aide2 = normal_aides[0], normal_aides[1]
    del_account = new_account(normal_aide1,
                                                    normal_aide1.economic.delegate_limit * 3)
    delegate_address, delegate_prikey = del_account.address, del_account.privateKey
    result = normal_aide1.delegate.delegate(node_id=normal_aide2.node_id, private_key=delegate_prikey)
    logger.info(result)
    assert ERROR_CODE[301102] == result.message


@allure.title("Punish the verifier and verify the entrusted amount")
@pytest.mark.P3
def test_DI_021(normal_nodes):
    """
    021: 委托的验证人被惩罚，校验委托本金
    """
    normal_aide = normal_nodes[0].aide
    normal_aide1 = normal_nodes[1].aide
    staking_limit = normal_aide.economic.staking_limit
    sta_account = new_account(normal_aide, staking_limit * 3)
    address, prikey = sta_account.address, sta_account.privateKey
    normal_aide.staking.create_staking(amount=staking_limit, benefit_address=address, private_key=prikey)

    del_account = new_account(normal_aide, normal_aide.economic.delegate_limit * 3)
    delegate_address, delegate_prikey = del_account.address, del_account.privateKey
    delegate_result = normal_aide.delegate.delegate(private_key=delegate_prikey)
    assert delegate_result['code'] == 0
    logger.info(delegate_result)

    msg = normal_aide.staking.staking_info
    logger.info("Close one node")
    normal_nodes[0].stop()

    logger.info("The next two periods")
    wait_settlement(normal_aide1, 2)
    logger.info("Restart the node")
    # todo: 重启ws重连问题待解决
    normal_nodes[0].start()
    time.sleep(10)
    msg = normal_aide.delegate.get_delegate_info(address=delegate_address, staking_block_identifier=msg.StakingBlockNum)
    logger.info(msg)
    assert msg.Released == normal_aide.economic.delegate_limit


@allure.title("Free amount in different periods when additional entrustment is made")
@pytest.mark.P2
@pytest.mark.parametrize('status', [0, 1, 2])
def test_DI_022_023_024(normal_aide, recover, status):
    """
    022:There is only the free amount of hesitation period when additional entrusting
    023:Only the free amount of the lockup period exists when the delegate is added
    024:The amount of both hesitation period and lockup period exists when additional entrustment is made
    """
    # todo: 价格deploy_all的方法,或者等等看ws重连问题解决后可不可以
    sta_account = new_account(normal_aide, normal_aide.economic.staking_limit * 3)
    address, prikey = sta_account.address, sta_account.privateKey
    normal_aide.staking.create_staking(benefit_address=address, private_key=prikey)

    del_account = new_account(normal_aide, normal_aide.economic.delegate_limit * 5)
    delegate_address, delegate_prikey = del_account.address, del_account.privateKey
    delegate_result = normal_aide.delegate.delegate(private_key=delegate_prikey)
    assert delegate_result['code'] == 0

    staking_info = normal_aide.staking.staking_info

    if status == 0:
        result = normal_aide.delegate.delegate(private_key=delegate_prikey)
        logger.info(result)
        res = normal_aide.delegate.get_delegate_info(address=delegate_address,
                                                     staking_block_identifier=staking_info.StakingBlockNum)
        logger.info(res)
        assert res.ReleasedHes == normal_aide.economic.delegate_limit * 2

    if status == 1:
        wait_settlement(normal_aide)
        result = normal_aide.delegate.delegate(private_key=delegate_prikey)
        logger.info(result)
        res = normal_aide.delegate.get_delegate_info(address=delegate_address,
                                                     staking_block_identifier=staking_info.StakingBlockNum)
        logger.info(res)
        assert res.ReleasedHes == normal_aide.economic.delegate_limit
        assert res.Released == normal_aide.economic.delegate_limit

    if status == 2:
        wait_settlement(normal_aide)
        _ = normal_aide.delegate.delegate(private_key=delegate_prikey)
        _ = normal_aide.delegate.delegate(private_key=delegate_prikey)

        res = normal_aide.delegate.get_delegate_info(address=delegate_address,
                                                     staking_block_identifier=staking_info.StakingBlockNum)
        logger.info(res)
        assert res.ReleasedHes == normal_aide.economic.delegate_limit * 2
        assert res.Released == normal_aide.economic.delegate_limit


@allure.title("uncommitted")
@pytest.mark.P2
def test_DI_025(normal_aide, recover):
    """
    025: 没有被委托过的信息
    """
    del_account = new_account(normal_aide, normal_aide.economic.delegate_limit * 3)
    delegate_address, delegate_prikey = del_account.address, del_account.privateKey
    assert not normal_aide.delegate.get_delegate_list(address=delegate_address)
    # assert_code(result, 301203)


@allure.title("The entrusted candidate is valid")
@pytest.mark.P2
def test_DI_026(normal_aide, recover):
    """
    026: 被委托的候选人有效
    """
    sta_account = new_account(normal_aide, normal_aide.economic.staking_limit * 2)
    address, prikey = sta_account.address, sta_account.privateKey
    normal_aide.staking.create_staking(benefit_address=address, private_key=prikey)

    del_account = new_account(normal_aide, normal_aide.economic.delegate_limit * 3)
    delegate_address, delegate_prikey = del_account.address, del_account.privateKey
    delegate_result = normal_aide.delegate.delegate(private_key=delegate_prikey)
    logger.info(delegate_result)
    assert delegate_result['code'] == 0

    delegate_list = normal_aide.delegate.get_delegate_list(address=delegate_address)
    logger.info(delegate_list)
    assert len(delegate_list) == 1
    for item in delegate_list:
        assert item.Addr == to_bech32_address(delegate_address, 'lat')
        assert item.NodeId == normal_aide.node_id


@allure.title("The entrusted candidate does not exist")
@pytest.mark.P2
def test_DI_027(normal_aide, recover):
    """
    The entrusted candidate does not exist
    """
    del_account = new_account(normal_aide, normal_aide.economic.delegate_limit * 3)
    delegate_address, delegate_prikey = del_account.address, del_account.privateKey

    illegal_node_id = "7ee3276fd6b9c7864eb896310b5393324b6db785a2528c00cc28ca8c" \
                      "3f86fc229a86f138b1f1c8e3a942204c03faeb40e3b22ab11b8983c35dc025de42865990"

    result = normal_aide.delegate.delegate(node_id=illegal_node_id, private_key=delegate_prikey)
    logger.info(result)
    assert ERROR_CODE[301102] == result.message
    assert not normal_aide.delegate.get_delegate_list(address=delegate_address)


@allure.title("The entrusted candidate is invalid")
@pytest.mark.P2
def test_DI_028(normal_aide, recover):
    """
    The entrusted candidate is invalid
    """
    sta_account = new_account(normal_aide, normal_aide.economic.staking_limit * 2)
    address, prikey = sta_account.address, sta_account.privateKey
    normal_aide.staking.create_staking(benefit_address=address, private_key=prikey)

    del_account = new_account(normal_aide, normal_aide.economic.delegate_limit * 3)
    delegate_address, delegate_prikey = del_account.address, del_account.privateKey
    delegate_result = normal_aide.delegate.delegate(private_key=delegate_prikey)
    logger.info(delegate_result)
    assert delegate_result['code'] == 0

    # Exit the pledge
    withdrew_staking_result = normal_aide.staking.withdrew_staking(private_key=prikey)
    assert withdrew_staking_result['code'] == 0
    delegate_list = normal_aide.delegate.get_delegate_list(address=delegate_address)
    logger.info(delegate_list)
    assert len(delegate_list) == 1


@allure.title("Delegate information in the hesitation period, lock period")
@pytest.mark.P2
def test_DI_029_030(normal_aide, recover):
    """
    029:Hesitation period inquiry entrustment details
    030:Lock periodic query information
    """
    sta_account = new_account(normal_aide, normal_aide.economic.staking_limit * 2)
    address, prikey = sta_account.address, sta_account.privateKey
    normal_aide.staking.create_staking(benefit_address=address, private_key=prikey)

    del_account = new_account(normal_aide, normal_aide.economic.delegate_limit * 3)
    delegate_address, delegate_prikey = del_account.address, del_account.privateKey
    delegate_result = normal_aide.delegate.delegate(private_key=delegate_prikey)
    logger.info(delegate_result)
    assert delegate_result['code'] == 0

    # Hesitation period inquiry entrustment details
    delegate_list = normal_aide.delegate.get_delegate_list(address=delegate_address)
    logger.info(delegate_list)
    logger.info("The next cycle")
    wait_settlement(normal_aide)
    delegate_list = normal_aide.delegate.get_delegate_list(address=delegate_address)
    logger.info(delegate_list)

    assert delegate_list[0].Addr == to_bech32_address(delegate_address, 'lat')
    assert delegate_list[0].NodeId == normal_aide.node_id


@allure.title("The delegate message no longer exists")
@pytest.mark.P2
def test_DI_031(normal_aide, recover):
    """
    The delegate message no longer exists
    """
    sta_account = new_account(normal_aide, normal_aide.economic.staking_limit * 3)
    address, prikey = sta_account.address, sta_account.privateKey
    normal_aide.staking.create_staking(private_key=prikey, benefit_address=address,
                                       amount=normal_aide.economic.staking_limit, )

    del_account = new_account(normal_aide, normal_aide.economic.delegate_limit * 3)
    delegate_address, delegate_prikey = del_account.address, del_account.privateKey
    assert normal_aide.delegate.delegate(private_key=delegate_prikey)['code'] == 0

    msg = normal_aide.staking.staking_info

    assert normal_aide.delegate.withdrew_delegate(private_key=delegate_prikey)['code'] == 0

    result = normal_aide.delegate.get_delegate_info(address=delegate_address,
                                                    staking_block_identifier=msg.StakingBlockNum)
    assert result is None  # 查委托信息，验证没有委托信息则返回None（之前旧框架返回异常code码）


@allure.title("The commission information is still in the hesitation period & The delegate information is still locked")
@pytest.mark.P2
def test_DI_032_033(normal_aide, recover):
    """
    032:The commission information is still in the hesitation period
    033The delegate information is still locked
    """
    value = normal_aide.economic.staking_limit
    sta_account = new_account(normal_aide, value * 3)
    address, prikey = sta_account.address, sta_account.privateKey
    normal_aide.staking.create_staking(amount=value, benefit_address=address, private_key=prikey)

    del_account = new_account(normal_aide, normal_aide.economic.delegate_limit * 3)
    delegate_address, delegate_prikey = del_account.address, del_account.privateKey
    delegate_result = normal_aide.delegate.delegate(private_key=delegate_prikey)
    logger.info(delegate_result)
    assert delegate_result['code'] == 0
    msg = normal_aide.staking.staking_info

    # Hesitation period inquiry entrustment details
    result = normal_aide.delegate.get_delegate_info(address=delegate_address,
                                                    staking_block_identifier=msg.StakingBlockNum)
    logger.info(result)
    assert result.Addr == to_bech32_address(delegate_address, 'lat')
    assert result.NodeId == normal_aide.node_id

    logger.info("The next cycle")
    wait_consensus(normal_aide)
    result = normal_aide.delegate.get_delegate_info(address=delegate_address,
                                                    staking_block_identifier=msg.StakingBlockNum)
    logger.info(result)
    assert result.Addr == to_bech32_address(delegate_address, 'lat')
    assert result.NodeId == normal_aide.node_id


@allure.title("The entrusted candidate has withdrawn of his own accord")
@pytest.mark.P2
def test_DI_034(normal_aide, recover):
    """
    The entrusted candidate has withdrawn of his own accord
    """
    value = normal_aide.economic.staking_limit
    sta_account = new_account(normal_aide, value * 3)
    address, prikey = sta_account.address, sta_account.privateKey
    normal_aide.staking.create_staking(amount=value, benefit_address=address, private_key=prikey)

    del_account = new_account(normal_aide, normal_aide.economic.delegate_limit * 3)
    delegate_address, delegate_prikey = del_account.address, del_account.privateKey
    delegate_result = normal_aide.delegate.delegate(private_key=delegate_prikey)
    logger.info(delegate_result)
    assert delegate_result['code'] == 0

    msg = normal_aide.staking.staking_info

    # Exit the pledge
    _ = normal_aide.staking.withdrew_staking(private_key=prikey)

    result = normal_aide.delegate.get_delegate_info(address=delegate_address,
                                                    staking_block_identifier=msg.StakingBlockNum)
    logger.info(result)
    assert result.Addr == to_bech32_address(delegate_address, 'lat')
    assert result.NodeId == normal_aide.node_id


@allure.title("Entrusted candidate (penalized in lockup period, penalized out completely)")
@pytest.mark.P2
def test_DI_035_036(normal_node, init_aide, recover):
    """
    The entrusted candidate is still penalized in the lockup period
    The entrusted candidate was penalized to withdraw completely
    """
    normal_aide = normal_node.aide
    sta_account = new_account(normal_aide, lat(300000))
    address, prikey = sta_account.address, sta_account.privateKey
    normal_aide.staking.create_staking(amount=normal_aide.economic.staking_limit, benefit_address=address, private_key=prikey)

    del_account = new_account(normal_aide, normal_aide.economic.delegate_limit * 3)
    delegate_address, delegate_prikey = del_account.address, del_account.privateKey
    assert normal_aide.delegate.delegate(private_key=delegate_prikey)['code'] == 0
    msg = normal_aide.staking.staking_info

    # The validation node becomes the out-block validation node
    wait_consensus(init_aide, 5)
    validator_list = get_pledge_list(init_aide.staking.get_validator_list)
    assert normal_aide.node_id in validator_list
    candidate_info = init_aide.staking.get_candidate_info(node_id=normal_aide.node_id)
    logger.info(candidate_info)

    logger.info("Close one node")
    normal_node.stop()
    for i in range(4):
        wait_consensus(init_aide)
        candidate_info = init_aide.staking.get_candidate_info(node_id=candidate_info.NodeId)
        logger.info(candidate_info)
        if candidate_info.Released < init_aide.economic.staking_limit:
            break

    result = init_aide.delegate.get_delegate_info(address=delegate_address, node_id=normal_aide.node_id,
                                                  staking_block_identifier=msg.StakingBlockNum)
    logger.info(result)
    assert result.Addr == to_bech32_address(delegate_address, 'lat')
    assert result.NodeId == normal_aide.node_id
    logger.info("Restart the node")
    normal_node.start()
    logger.info("Next settlement period")
    wait_settlement(init_aide, 2)

    result = normal_aide.delegate.get_delegate_info(address=delegate_address,
                                                    staking_block_identifier=msg.StakingBlockNum)
    logger.info(result)
    assert result.Addr == to_bech32_address(delegate_address, 'lat')
    assert result.NodeId == normal_aide.node_id


@allure.title("Query for delegate information in undo")
@pytest.mark.P2
def test_DI_038(normal_aide, recover):
    """
    Query for delegate information in undo
    """
    value = normal_aide.economic.staking_limit
    sta_account = new_account(normal_aide, value * 3)
    address, prikey = sta_account.address, sta_account.privateKey
    normal_aide.staking.create_staking(amount=value, benefit_address=address, private_key=prikey)

    del_account = new_account(normal_aide, normal_aide.economic.delegate_limit * 3)
    delegate_address, delegate_prikey = del_account.address, del_account.privateKey
    delegate_result = normal_aide.delegate.delegate(private_key=delegate_prikey)
    logger.info(delegate_result)
    assert delegate_result['code'] == 0

    msg = normal_aide.staking.staking_info

    logger.info("The next cycle")
    wait_consensus(normal_aide)

    # Exit the pledge
    withdrew_staking_result = normal_aide.staking.withdrew_staking(private_key=prikey)
    logger.info(f'withdrew_staking_result={withdrew_staking_result}')

    result = normal_aide.delegate.get_delegate_info(address=delegate_address,
                                                    staking_block_identifier=msg.StakingBlockNum)
    logger.info(result)
    assert result.Addr == to_bech32_address(delegate_address, 'lat')
    assert result.NodeId == normal_aide.node_id
