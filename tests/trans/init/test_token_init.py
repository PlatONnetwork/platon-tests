import time
from decimal import Decimal

import allure
import pytest
from loguru import logger
from platon._utils.inner_contract import InnerContractEvent
from platon_env.genesis import Genesis

from lib.utils import wait_settlement, lat, get_current_year_reward, wait_consensus
from setting.account import *
from setting.setting import GENESIS_FILE
from tests.ppos.conftest import new_account, create_sta_free_or_lock


@pytest.mark.P0
def test_chain_init_token(chain, normal_aide):
    """
    测试 私链启动后内置地址初始化金额
    @Desc:
        -启动私链，查看内置钱包地址金额
    """
    init_node_number = len(normal_aide.staking.get_validator_list())
    default_pledge_account = lat(init_node_number * 150000)
    community_account = default_pledge_account + 259096239000000000000000000 + 62215742000000000000000000
    main_account = str(10250000000000000000000000000 - community_account - 200000000000000000000000000)

    genesis = Genesis(GENESIS_FILE)
    genesis.data['economicModel']['innerAcc']['cdfBalance'] = community_account
    new_gen_file = GENESIS_FILE.replace(".json", "_new.json")
    genesis.save_as(new_gen_file)
    chain.install(genesis_file=new_gen_file)

    foundation_account = normal_aide.platon.get_balance(normal_aide.economic.innerAcc.platonFundAccount)
    assert foundation_account == 0

    foundation_louckup_account = normal_aide.platon.get_balance(normal_aide.restricting.ADDRESS)
    assert foundation_louckup_account == 259096239000000000000000000

    staking_contract_account = normal_aide.platon.get_balance(normal_aide.staking.ADDRESS)
    assert staking_contract_account == default_pledge_account

    incentive_pool_account = normal_aide.platon.get_balance(INCENTIVE_POOL_ACCOUNT)
    incentive_pool = int(genesis.data['alloc'][INCENTIVE_POOL_ACCOUNT]['balance']) + 62215742000000000000000000
    assert incentive_pool_account == incentive_pool

    remain = normal_aide.platon.get_balance(MAIN_ACCOUNT.address)
    assert int(main_account) == remain

    develop_account = normal_aide.platon.get_balance(CDF_ACCOUNT.address)
    assert develop_account == 0

    reality_total = foundation_account + foundation_louckup_account + staking_contract_account + incentive_pool_account + remain + develop_account
    assert reality_total == 10250000000000000000000000000


@allure.title("Two distribution-Transfer amount：{value}")
@pytest.mark.P0
@pytest.mark.parametrize('value', [0, 1000, 0.000000000000000001, 100000000])
def test_re_transfer(normal_aide, value):
    """
    测试 私链启动后转账功能
    @Desc:
        -启动私链，给普通账号转 0 LAT
        -启动私链，给普通账号转 1000 LAT
        -启动私链，给普通账号转 0.000000000000000001 LAT
        -启动私链，给普通账号转 100000000 LAT
    """
    account = new_account(normal_aide, lat(value))
    assert lat(value) == normal_aide.platon.get_balance(account.address)


@pytest.mark.P1
@pytest.mark.parametrize('value', [1000, 2000])
def test_transfer_insufficient_account(normal_aide, value):
    """
    测试 私链启动后转账功能-账号余额不足
    @Desc:
        -启动私链账号余额1000，给普通账号转 1000 LAT
        -启动私链账号余额1000，给普通账号转 2000 LAT
    """
    from_account = new_account(normal_aide, lat(1000))
    status = True
    try:
        to_account = new_account(normal_aide, 0)
        normal_aide.transfer.transfer(to_account.address, lat(value), private_key=from_account.privateKey)
        status = False
    except Exception as e:
        logger.info("Use case success, exception information：{} ".format(str(e)))
    assert status, "ErrMsg:Transfer result {}".format(status)


@pytest.mark.P1
def test_transfer_insufficient_gas(normal_aide):
    """
    测试 私链启动后转账功能-账号gas不足
    @Desc:
        -启动私链账号余额1000，给普通账号转 500 LAT/ gas只给2100
    """
    from_account = new_account(normal_aide, lat(1000))
    status = True
    try:
        to_account = new_account(normal_aide, 0)
        normal_aide.transfer.transfer(to_account.address, lat(500), txn={"gas": 2100},
                                      private_key=from_account.privateKey)
        status = False
    except Exception as e:
        logger.info("Use case success, exception information：{} ".format(str(e)))
    assert status, "ErrMsg:Transfer result {}".format(status)


@pytest.mark.P1
def test_transfer_estimate_fee(normal_aide):
    """
    测试 私链启动后转账功能的gas值
    @Desc:
        -启动私链账号余额1000，调用gas预估接口查看gas值=21000
    """
    from_account = new_account(normal_aide, lat(1000))
    to_account = new_account(normal_aide, 0)

    transaction_data = {"to": to_account.address, "data": '', "from": from_account.address}
    estimate_gas = normal_aide.platon.estimate_gas(transaction_data)
    assert estimate_gas == 21000


@pytest.mark.P2
def test_transfer_to_own_account(normal_aide):
    """
    测试 私链启动后转账功能的,自己给自己转账
    @Desc:
        -启动私链账号余额1000，给from账号转 500 LAT,查看转账结果和余额
    """
    from_account = new_account(normal_aide, lat(1000))
    normal_aide.transfer.transfer(from_account.address, lat(500), private_key=from_account.privateKey)
    balance = normal_aide.platon.get_balance(from_account.address)
    assert balance == lat(1000) - normal_aide.platon.gas_price * 21000


@pytest.mark.P2
def test_transfer_to_incentive_pool_account(normal_aide):
    """
    测试 私链启动后转账功能，给platON激励池账户转账
    @Desc:
        -启动私链账号余额1000，给platON激励池账户转 500 LAT,查看转账结果和余额
    """
    from_account = new_account(normal_aide, lat(1000))
    incentive_pool_account = normal_aide.platon.get_balance(INCENTIVE_POOL_ACCOUNT)
    normal_aide.transfer.transfer(INCENTIVE_POOL_ACCOUNT, lat(500), private_key=from_account.privateKey)
    incentive_pool_account1 = normal_aide.platon.get_balance(INCENTIVE_POOL_ACCOUNT)
    assert incentive_pool_account1 == incentive_pool_account + lat(500) + normal_aide.platon.gas_price * 21000


@pytest.mark.P2
def test_transfer_to_internal_contract_account(normal_aide):
    """
     测试 私链启动后转账功能，给platON内置合约转账
     @Desc:
         -启动私链账号余额10000，给Staking地址转 500 LAT,查看转账结果和余额
         -启动私链账号余额10000，给Restriction plan地址转 500 LAT,查看转账结果和余额
         -启动私链账号余额10000，给entrusted dividend地址转 500 LAT,查看转账结果和余额
         -启动私链账号余额10000，给punishment地址转 500 LAT,查看转账结果和余额
     """
    from_account = new_account(normal_aide, lat(10000))
    staking_balance = normal_aide.platon.get_balance(normal_aide.staking.ADDRESS)
    restricting_balance = normal_aide.platon.get_balance(normal_aide.restricting.ADDRESS)
    delegate_balance = normal_aide.platon.get_balance(normal_aide.delegate.ADDRESS)
    slashing_balance = normal_aide.platon.get_balance(normal_aide.slashing.ADDRESS)

    normal_aide.transfer.transfer(normal_aide.staking.ADDRESS, lat(500), private_key=from_account.privateKey)
    normal_aide.transfer.transfer(normal_aide.restricting.ADDRESS, lat(500),
                                  private_key=from_account.privateKey)
    normal_aide.transfer.transfer(normal_aide.delegate.reward_ADDRESS, lat(500),
                                  private_key=from_account.privateKey)
    normal_aide.transfer.transfer(normal_aide.slashing.ADDRESS, lat(500), private_key=from_account.privateKey)

    staking_balance1 = normal_aide.platon.get_balance(normal_aide.staking.ADDRESS)
    restricting_balance1 = normal_aide.platon.get_balance(normal_aide.restricting.ADDRESS)
    delegate_balance1 = normal_aide.platon.get_balance(normal_aide.delegate.ADDRESS)
    slashing_balance1 = normal_aide.platon.get_balance(normal_aide.slashing.ADDRESS)

    assert staking_balance1 == staking_balance + lat(500)
    assert restricting_balance1 == restricting_balance + lat(500)
    assert delegate_balance1 == delegate_balance + lat(500)
    assert slashing_balance1 == slashing_balance + lat(500)


@pytest.mark.P2
def test_transfer_pledge_same_transaction(normal_aide):
    """
     测试 私链启动后转账功能，一笔交易里同时质押和转账两个操作
     @Desc:
         -启动私链账号余额200000，构建一笔转账 500LAT和质押交易100000LAT，验证转账和质押结果
     """
    from_account = new_account(normal_aide, lat(200000))
    normal_aide.set_result_type('txn')
    data = normal_aide.staking.create_staking(private_key=from_account.privateKey)
    data['value'] = lat(500)
    staking_balance = normal_aide.platon.get_balance(normal_aide.staking.ADDRESS)
    normal_aide.set_result_type('receipt')
    normal_aide.send_transaction(data, private_key=from_account.privateKey)
    # print(InnerContractEvent().processReceipt(receipt))
    staking_balance1 = normal_aide.platon.get_balance(normal_aide.staking.ADDRESS)
    assert normal_aide.staking.get_candidate_info()
    assert staking_balance1 == staking_balance + normal_aide.economic.staking_limit + lat(500)


@pytest.mark.P2
def test_transfer_parallel_insufficient_account(normal_aide):
    """
     测试 私链启动后转账功能，发起多次转账（不等交易回执），余额不足
     @Desc:
         -启动私链账号余额1000，构建转账交易体-Nonce自定义 发起多次转账，验证转账结果
     """
    from_account = new_account(normal_aide, lat(1000))
    to_account = new_account(normal_aide, 0)
    nonce = normal_aide.platon.get_transaction_count(from_account.address)
    normal_aide.set_result_type('hash')
    try:
        normal_aide.transfer.transfer(to_account.address, lat(500), txn={"nonce": nonce},
                                      private_key=from_account.privateKey)
        normal_aide.transfer.transfer(to_account.address, lat(500), txn={"nonce": nonce + 1},
                                      private_key=from_account.privateKey)
    except Exception as e:
        logger.info("Use case success, exception information：{} ".format(str(e)))
    time.sleep(3)
    to_balance = normal_aide.platon.get_balance(to_account.address)
    assert to_balance == lat(500)


@pytest.mark.p1
@pytest.mark.parametrize('block', [20, 40])
def test_transfer_special_block(normal_aide, block):
    """
     测试 私链启动后转账功能，特殊区块按正常逻辑打包交易
     @Desc:
         -启动私链，持续发转账交易，查看20选举区块上是否有转账交易
         -启动私链，持续发转账交易，查看40结算区块上是否有转账交易

     """
    to_account = new_account(normal_aide, 0)
    count = 0
    normal_aide.set_result_type('receipt')
    for i in range(100):
        block_numner = normal_aide.transfer.transfer(to_account.address, lat(1))["blockNumber"]
        count += 1
        if block_numner % block == 0:
            break
    assert block_numner % block == 0
    balance = normal_aide.platon.get_balance(to_account.address)
    assert balance == lat(1) * count


@pytest.mark.P2
def test_transfer_to_incentive_pool_check_profit(normal_aide):
    """
     测试 私链启动后转账功能，向激励池转账，查看出块奖励和质押奖励
     @Desc:
         -启动私链，账户余额200000，向激励池转账10000
         -等待下个结算周期，查看出块奖励和质押奖励是否更新
     """
    from_account = new_account(normal_aide, lat(200000))
    benefit_account = new_account(normal_aide, 0)
    normal_aide.staking.create_staking(benefit_address=benefit_account.address, reward_per=1000,
                                       private_key=from_account.privateKey)

    wait_settlement(normal_aide)

    block_reward = normal_aide.staking.get_block_reward()
    staking_reward = normal_aide.staking.get_staking_reward()
    logger.info("block_reward: {} staking_reward: {}".format(block_reward, staking_reward))

    benefit_balance = normal_aide.platon.get_balance(benefit_account.address)
    logger.info("benifit_balance: {}".format(benefit_balance))


@pytest.mark.P1
@pytest.mark.parametrize('use_type', ['free', 'lock'])
def test_pledge_benefit_address_by_incentive_pool(normal_aide, use_type):
    """
     测试 私链启动后自由/锁仓质押节点，收益账户填写激励池，查看出块奖励和质押奖励
     @Desc:
         -启动私链，账户余额200000，收益账户设置激励池地址
         -等待出块奖励和质押奖励，查看激励池金额变化
     """
    if use_type == 'free':
        create_sta_free_or_lock(normal_aide, benefit_address=INCENTIVE_POOL_ACCOUNT)

    if use_type == 'lock':
        plan = [{'Epoch': 5, 'Amount': normal_aide.economic.staking_limit}]
        create_sta_free_or_lock(normal_aide, plan, benefit_address=INCENTIVE_POOL_ACCOUNT)

    wait_settlement(normal_aide)

    block_reward = normal_aide.staking.get_block_reward()
    staking_reward = normal_aide.staking.get_staking_reward()
    logger.info("block_reward: {} staking_reward: {}".format(block_reward, staking_reward))

    benefit_balance = normal_aide.platon.get_balance(INCENTIVE_POOL_ACCOUNT)
    logger.info("benifit_balance: {}".format(benefit_balance))

    wait_settlement(normal_aide)

    benefit_balance1 = normal_aide.platon.get_balance(INCENTIVE_POOL_ACCOUNT)
    logger.info("benifit_balance1: {}".format(benefit_balance1))

    assert benefit_balance1 == benefit_balance


@pytest.mark.P1
def test_init_node_block_staking_reward(init_aide):
    """
     测试 私链启动后初始节点出块奖励和质押奖励
    @Desc:
     -犹豫期，查看质押节点收益地址是否有出块奖励和质押奖励
     -生效期，查看质押节点收益地址是否有出块奖励和质押奖励
     -生效期撤销质押，等待跨结算周期结束，查看质押节点的出块奖励和质押奖励
    """
    wait_consensus(init_aide)
    logger.info("查看犹豫期收益地址金额")
    ben_balance = init_aide.platon.get_balance(init_aide.staking.staking_info.BenefitAddress)
    assert ben_balance == init_aide.platon.get_balance(INCENTIVE_POOL_ACCOUNT)

    wait_settlement(init_aide)
    logger.info("查看生效期期收益地址金额")
    ben_balance = init_aide.platon.get_balance(init_aide.staking.staking_info.BenefitAddress)
    assert ben_balance == init_aide.platon.get_balance(INCENTIVE_POOL_ACCOUNT)

    wait_settlement(init_aide)
    logger.info("查看跨结算周期收益地址金额")
    ben_balance = init_aide.platon.get_balance(init_aide.staking.staking_info.BenefitAddress)
    assert ben_balance == init_aide.platon.get_balance(INCENTIVE_POOL_ACCOUNT)


@pytest.mark.P2
def test_init_node_re_pledge(init_aide):
    """
     测试 私链启动后初始验证人退出后重新质押
     @Desc:
         -启动私链，初始验证人退出
         -等待节点退出后重新质押
     """
    assert init_aide.staking.withdrew_staking(private_key=CDF_ACCOUNT.privateKey)['code'] == 0

    wait_settlement(init_aide, 3)
    logger.info("节点完全退出")
    assert init_aide.staking.get_candidate_info() is None

    sta_account = new_account(init_aide, lat(300000))
    ben_account = new_account(init_aide)
    logger.info("节点重新质押")
    assert init_aide.staking.create_staking(benefit_address=ben_account.address, private_key=sta_account.privateKey)[
               'code'] == 0
    start_bn = init_aide.platon.block_number

    wait_settlement(init_aide)
    assert init_aide.staking.withdrew_staking(private_key=sta_account.privateKey)['code'] == 0
    block_reward, staking_reward = get_current_year_reward(init_aide)

    wait_consensus(init_aide, 5)

    blocknumber = init_aide.calculator.get_block_count(init_aide.staking.staking_info.NodeId, start_bn=start_bn)
    block_reward_total = int(Decimal(str(blocknumber)) * Decimal(str(block_reward)))
    logger.info("节点总出块奖励：{}".format(block_reward_total))

    ben_balance = init_aide.platon.get_balance(ben_account.address)
    logger.info("质押节点收益地址余额：{}".format(ben_balance))

    assert ben_balance == block_reward_total + staking_reward


@pytest.mark.P1
def test_zero_execution_block_check_incentive_pool(normal_nodes):
    """
     测试 私链启动后自由/锁仓质押节点，构建节点零出块，查看激励池金额
     @Desc:
         -启动私链，账户余额200000，质押节点10000
         -停止节点，等待节点零出块，查看激励池金额
     """
    node = normal_nodes[0]
    node1 = normal_nodes[1]

    from_account = new_account(node.aide, lat(300000))

    # create_sta_free_or_lock(node.aide, )
    assert node.aide.staking.create_staking(amount=lat(200000), private_key=from_account.privateKey)['code'] == 0
    staking_info = node.aide.staking.get_candidate_info()

    wait_settlement(node.aide)

    block_reward, staking_reward = get_current_year_reward(node.aide)

    logger.info("停止节点")
    node.stop()

    incentive_pool_balance = node1.aide.platon.get_balance(INCENTIVE_POOL_ACCOUNT)
    logger.info("激励池金额：{}".format(incentive_pool_balance))
    wait_settlement(node1.aide)

    blocknumber = node1.aide.calculator.get_block_count(node.node_id)
    block_reward_total = int(Decimal(str(blocknumber)) * Decimal(str(block_reward)))
    logger.info("节点出块奖励：{}".format(block_reward_total))

    penalty_amount = int(Decimal(str(block_reward)) * Decimal(str(node1.aide.economic.slashing.slashBlocksReward)))
    if penalty_amount >= staking_info['Shares']:
        penalty_amount = staking_info['Shares']
    logger.info("零出块处罚金额：{}".format(penalty_amount))
    incentive_pool_balance1 = node1.aide.platon.get_balance(INCENTIVE_POOL_ACCOUNT)
    logger.info("激励池金额：{}".format(incentive_pool_balance1))

    assert incentive_pool_balance1 == incentive_pool_balance + penalty_amount


@pytest.mark.P1
def test_normal_node_block_staking_reward(normal_aide):
    """
     测试 私链启动后质押节点出块奖励和质押奖励
    @Desc:
     -启动私链，账户余额200000，质押节点100000
     -犹豫期，查看质押节点收益地址是否有出块奖励和质押奖励
     -生效期，查看质押节点收益地址是否有出块奖励和质押奖励
     -生效期撤销质押，等待跨结算周期结束，查看质押节点的出块奖励和质押奖励
    """
    ben_account = new_account(normal_aide)

    sta_account = create_sta_free_or_lock(normal_aide, benefit_address=ben_account.address)

    ben_balance = normal_aide.platon.get_balance(ben_account.address)
    logger.info("质押节点犹豫期收益地址余额：{}".format(ben_balance))
    assert ben_balance == 0

    wait_settlement(normal_aide)

    block_reward, staking_reward = get_current_year_reward(normal_aide)

    assert normal_aide.staking.withdrew_staking(private_key=sta_account.privateKey)['code'] == 0

    wait_consensus(normal_aide, 3)

    ben_balance1 = normal_aide.platon.get_balance(ben_account.address)
    logger.info("质押节点生效期收益地址余额：{}".format(ben_balance1))
    assert ben_balance1 > ben_balance

    logger.info("等待当前结算周期结束，统计出块奖励和质押奖励")
    wait_consensus(normal_aide, 2)

    blocknumber = normal_aide.calculator.get_block_count(normal_aide.staking.staking_info.NodeId)
    block_reward_total = int(Decimal(str(blocknumber)) * Decimal(str(block_reward)))
    logger.info("节点总出块奖励：{}".format(block_reward_total))

    ben_balance2 = normal_aide.platon.get_balance(ben_account.address)
    logger.info("质押节点收益地址余额：{}".format(ben_balance2))

    assert ben_balance2 == block_reward_total + staking_reward


@pytest.mark.P2
def test_normal_node_edit_benifit_address(normal_aide):
    """
     测试 私链启动后修改收益地址查看出块奖励和质押奖励（节点出块中）
    @Desc:
     -启动私链，账户余额200000，质押节点100000
     -当前共识轮节点出块中，修改节点收益地址
     -查看节点的出块奖励和质押奖励金额
    """
    ben_account = new_account(normal_aide)
    ben_account1 = new_account(normal_aide)

    sta_account = create_sta_free_or_lock(normal_aide, benefit_address=ben_account.address)

    wait_settlement(normal_aide)

    block_reward, staking_reward = get_current_year_reward(normal_aide)

    wait_consensus(normal_aide)

    for i in range(40):
        current_block = normal_aide.platon.block_number
        node_id = normal_aide.ec_recover(normal_aide.platon.get_block(current_block))
        if node_id == normal_aide.staking.staking_info.NodeId:
            break
        time.sleep(1)
    normal_aide.staking.set_result_type('txn')
    txn1 = normal_aide.staking.edit_candidate(benifit_address=ben_account1.address, private_key=sta_account.privateKey)
    receipt = normal_aide.transfer.send_transaction(txn1, private_key=sta_account.privateKey, result_type='receipt')
    assert InnerContractEvent().processReceipt(receipt)['code'] == 0

    txn2 = normal_aide.staking.withdrew_staking(private_key=sta_account.privateKey)
    receipt = normal_aide.transfer.send_transaction(txn2, private_key=sta_account.privateKey, result_type='receipt')
    assert InnerContractEvent().processReceipt(receipt)['code'] == 0

    wait_consensus(normal_aide, 4)

    blocknumber = normal_aide.calculator.get_block_count(normal_aide.staking.staking_info.NodeId)
    block_reward_total = int(Decimal(str(blocknumber)) * Decimal(str(block_reward)))
    logger.info("节点总出块奖励：{}".format(block_reward_total))
    ben_balance = normal_aide.platon.get_balance(ben_account.address)
    ben_balance1 = normal_aide.platon.get_balance(ben_account1.address)

    assert ben_balance + ben_balance1 == block_reward_total + staking_reward + int(
        Decimal(str(txn1['gas'])) * Decimal(str(txn1['gasPrice']))) + int(
        Decimal(str(txn2['gas'])) * Decimal(str(txn2['gasPrice'])))


@pytest.mark.P1
def test_init_block_staking_reward(init_aide):
    """
     测试 私链启动后，验证第一个结算周期区块奖励和质押奖励
    @Desc:
     -启动私链，计算第一个结算周期的出块奖励和质押奖励和查看接口返回的出块奖励和质押奖励是否一致
    """
    logger.info("链当前块高：{}".format(init_aide.platon.block_number))

    incentive_pool_amount = init_aide.platon.get_balance(INCENTIVE_POOL_ACCOUNT, 0)

    annualcycle = init_aide.economic.increasing_epoch

    block_proportion = str(init_aide.economic.reward.newBlockRate / 100)

    verifier_num = init_aide.calculator.get_verifier_count()
    print(init_aide.economic.epoch_consensus)
    amount_per_settlement = int(Decimal(str(incentive_pool_amount)) / Decimal(str(annualcycle)))
    total_block_rewards = int(Decimal(str(amount_per_settlement)) * Decimal(str(block_proportion)))
    per_block_reward = int(Decimal(str(total_block_rewards)) / Decimal(str(init_aide.economic.epoch_blocks)))
    staking_reward_total = amount_per_settlement - total_block_rewards
    per_staking_reward = int(Decimal(str(staking_reward_total)) / Decimal(str(verifier_num)))

    block_reward, staking_reward = get_current_year_reward(init_aide)

    assert per_block_reward == block_reward
    assert staking_reward == per_staking_reward


