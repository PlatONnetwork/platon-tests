import time
from decimal import Decimal

from loguru import logger

import allure
import pytest
from platon._utils.error_code import ERROR_CODE
from platon._utils.inner_contract import InnerContractEvent

from lib.account import *
from lib.funcs import wait_settlement, wait_consensus
from lib.utils import get_pledge_list, get_block_count_number
from setting.setting import GENESIS_FILE
from tests.conftest import generate_account, create_sta_free_or_lock
from platon_env.genesis import Genesis


@pytest.mark.P0
def test_chain_init_token(chain, normal_aide):
    """
    测试 私链启动后内置地址初始化金额
    @Desc:
        -启动私链，查看内置钱包地址金额
    """
    init_node_number = len(normal_aide.staking.get_validator_list())
    default_pledge_account = normal_aide.web3.toVon(init_node_number * 150000, 'lat')
    community_account = default_pledge_account + 259096239000000000000000000 + 62215742000000000000000000
    main_account = str(10250000000000000000000000000 - community_account - 200000000000000000000000000)

    genesis = Genesis(GENESIS_FILE)
    genesis.data['economicModel']['innerAcc']['cdfBalance'] = community_account
    new_gen_file = GENESIS_FILE.replace(".json", "_new.json")
    genesis.save_as(new_gen_file)
    chain.install(genesis_file=new_gen_file)

    foundation_account = normal_aide.platon.get_balance(normal_aide.economic.innerAcc.platonFundAccount)
    assert foundation_account == 0

    foundation_louckup_account = normal_aide.platon.get_balance(normal_aide.restricting.contract_address)
    assert foundation_louckup_account == 259096239000000000000000000

    staking_contract_account = normal_aide.platon.get_balance(normal_aide.staking.contract_address)
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
    amount = normal_aide.platon.web3.toVon(value, 'lat')
    address, _ = generate_account(normal_aide, amount)
    assert amount == normal_aide.platon.get_balance(address)


@pytest.mark.P1
@pytest.mark.parametrize('value', [1000, 2000])
def test_transfer_insufficient_account(normal_aide, value):
    """
    测试 私链启动后转账功能-账号余额不足
    @Desc:
        -启动私链账号余额1000，给普通账号转 1000 LAT
        -启动私链账号余额1000，给普通账号转 2000 LAT
    """
    from_address, from_ = generate_account(normal_aide, normal_aide.platon.web3.toVon(1000, 'lat'))
    status = True
    try:
        to_address, to_ = generate_account(normal_aide, 0)
        normal_aide.transfer.transfer(to_address, normal_aide.platon.web3.toVon(value, 'lat'), private_key=from_)
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
    from_address, from_ = generate_account(normal_aide, normal_aide.platon.web3.toVon(1000, 'lat'))
    status = True
    try:
        to_address, to_ = generate_account(normal_aide, 0)
        normal_aide.transfer.transfer(to_address, normal_aide.platon.web3.toVon(500, 'lat'), txn={"gas": 2100},
                                      private_key=from_)
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
    from_address, from_ = generate_account(normal_aide, normal_aide.platon.web3.toVon(1000, 'lat'))
    to_address, to_ = generate_account(normal_aide, 0)

    transaction_data = {"to": to_address, "data": '', "from": from_address}
    estimate_gas = normal_aide.platon.estimate_gas(transaction_data)
    assert estimate_gas == 21000


@pytest.mark.P2
def test_transfer_to_own_account(normal_aide):
    """
    测试 私链启动后转账功能的,自己给自己转账
    @Desc:
        -启动私链账号余额1000，给from账号转 500 LAT,查看转账结果和余额
    """
    from_address, from_ = generate_account(normal_aide, normal_aide.platon.web3.toVon(1000, 'lat'))
    status = True
    try:
        normal_aide.transfer.transfer(from_address, normal_aide.platon.web3.toVon(500, 'lat'), private_key=from_)
        balance = normal_aide.platon.get_balance(from_address)
        assert status
        assert balance == normal_aide.platon.web3.toVon(1000, 'lat') - normal_aide.platon.gas_price * 21000
    except Exception as e:
        logger.info("Use case success, exception information：{} ".format(str(e)))


@pytest.mark.P2
def test_transfer_to_incentive_pool_account(normal_aide):
    """
    测试 私链启动后转账功能，给platON激励池账户转账
    @Desc:
        -启动私链账号余额1000，给platON激励池账户转 500 LAT,查看转账结果和余额
    """
    from_address, from_ = generate_account(normal_aide, normal_aide.platon.web3.toVon(1000, 'lat'))
    incentive_pool_account = normal_aide.platon.get_balance(INCENTIVE_POOL_ACCOUNT)
    normal_aide.transfer.transfer(INCENTIVE_POOL_ACCOUNT, normal_aide.platon.web3.toVon(500, 'lat'), private_key=from_)
    incentive_pool_account1 = normal_aide.platon.get_balance(INCENTIVE_POOL_ACCOUNT)
    assert incentive_pool_account1 == incentive_pool_account + normal_aide.platon.web3.toVon(500, 'lat') + normal_aide.platon.gas_price * 21000


@pytest.mark.P2
def test_transfer_to_internal_contract_account(normal_aide):
    """
     测试 私链启动后转账功能，给platON内置合约转账
     @Desc:
         -启动私链账号余额1000，给Staking地址转 500 LAT,查看转账结果和余额
         -启动私链账号余额1000，给Restriction plan地址转 500 LAT,查看转账结果和余额
         -启动私链账号余额1000，给entrusted dividend地址转 500 LAT,查看转账结果和余额
         -启动私链账号余额1000，给punishment地址转 500 LAT,查看转账结果和余额
     """
    from_address, from_ = generate_account(normal_aide, normal_aide.platon.web3.toVon(10000, 'lat'))
    staking_balance = normal_aide.platon.get_balance(normal_aide.staking.contract_address)
    restricting_balance = normal_aide.platon.get_balance(normal_aide.restricting.contract_address)
    delegate_balance = normal_aide.platon.get_balance(normal_aide.delegate.contract_address)
    slashing_balance = normal_aide.platon.get_balance(normal_aide.slashing.contract_address)

    normal_aide.transfer.transfer(normal_aide.staking.contract_address, normal_aide.platon.web3.toVon(500, 'lat'), private_key=from_)
    normal_aide.transfer.transfer(normal_aide.restricting.contract_address, normal_aide.platon.web3.toVon(500, 'lat'), private_key=from_)
    normal_aide.transfer.transfer(normal_aide.delegate.reward_contract_address, normal_aide.platon.web3.toVon(500, 'lat'), private_key=from_)
    normal_aide.transfer.transfer(normal_aide.slashing.contract_address, normal_aide.platon.web3.toVon(500, 'lat'), private_key=from_)

    staking_balance1 = normal_aide.platon.get_balance(normal_aide.staking.contract_address)
    restricting_balance1 = normal_aide.platon.get_balance(normal_aide.restricting.contract_address)
    delegate_balance1 = normal_aide.platon.get_balance(normal_aide.delegate.contract_address)
    slashing_balance1 = normal_aide.platon.get_balance(normal_aide.slashing.contract_address)

    assert staking_balance1 == staking_balance + normal_aide.platon.web3.toVon(500, 'lat')
    assert restricting_balance1 == restricting_balance + normal_aide.platon.web3.toVon(500, 'lat')
    assert delegate_balance1 == delegate_balance + normal_aide.platon.web3.toVon(500, 'lat')
    assert slashing_balance1 == slashing_balance + normal_aide.platon.web3.toVon(500, 'lat')


@pytest.mark.P2
def test_transfer_pledge_same_transaction(normal_aide):
    """
     测试 私链启动后转账功能，一笔交易里同时质押和转账两个操作
     @Desc:
         -启动私链账号余额200000，构建一笔转账 500LAT和质押交易100000LAT，验证转账和质押结果
     """
    normal_aide.set_result_type('txn')
    from_address, from_ = generate_account(normal_aide, normal_aide.platon.web3.toVon(200000, 'lat'))
    data = normal_aide.staking.create_staking(private_key=from_)
    data['value'] = normal_aide.platon.web3.toVon(500, 'lat')
    staking_balance = normal_aide.platon.get_balance(normal_aide.staking.contract_address)
    normal_aide.set_result_type('receipt')
    receipt = normal_aide.staking.send_transaction(data, private_key=from_)
    # print(InnerContractEvent().processReceipt(receipt))
    staking_balance1 = normal_aide.platon.get_balance(normal_aide.staking.contract_address)
    assert normal_aide.staking.get_candidate_info()
    assert staking_balance1 == staking_balance + normal_aide.economic.staking_limit + normal_aide.platon.web3.toVon(500, 'lat')


@pytest.mark.P2
def test_transfer_parallel_insufficient_account(normal_aide):
    """
     测试 私链启动后转账功能，发起多次转账（不等交易回执），余额不足
     @Desc:
         -启动私链账号余额10000，构建转账交易体-Nonce自定义 发起多次转账，验证转账结果
     """
    from_address, from_ = generate_account(normal_aide, normal_aide.platon.web3.toVon(1000, 'lat'))
    to_address, to_ = generate_account(normal_aide, 0)
    nonce = normal_aide.platon.get_transaction_count(from_address)
    normal_aide.set_result_type('hash')
    try:
        normal_aide.transfer.transfer(to_address, normal_aide.web3.toVon(500, 'lat'), txn={"nonce": nonce}, private_key=from_)
        normal_aide.transfer.transfer(to_address, normal_aide.web3.toVon(500, 'lat'), txn={"nonce": nonce+1}, private_key=from_)
    except Exception as e:
        logger.info("Use case success, exception information：{} ".format(str(e)))
    time.sleep(3)
    to_balance = normal_aide.platon.get_balance(to_address)
    assert to_balance == normal_aide.web3.toVon(500, 'lat')


@pytest.mark.p1
@pytest.mark.parametrize('block', [20, 40])
def test_transfer_special_block(normal_aide, block):
    """
     测试 私链启动后转账功能，特殊区块按正常逻辑打包交易
     @Desc:
         -启动私链，持续发转账交易，查看20选举区块上是否有转账交易
         -启动私链，持续发转账交易，查看40结算区块上是否有转账交易

     """
    to_address, to_ = generate_account(normal_aide, 0)
    count = 0
    normal_aide.set_result_type('receipt')
    for i in range(100):
        block_numner = normal_aide.transfer.transfer(to_address, normal_aide.web3.toVon(1, 'lat'))["blockNumber"]
        count += 1
        if block_numner % block == 0:
            break
    print(block_numner)
    assert block_numner % block == 0
    balance = normal_aide.platon.get_balance(to_address)
    assert balance == normal_aide.web3.toVon(1, 'lat') * count


@pytest.mark.P2
def test_transfer_to_incentive_pool_check_profit(normal_aide):
    """
     测试 私链启动后转账功能，向激励池转账，查看出块奖励和质押奖励
     @Desc:
         -启动私链，账户余额200000，向激励池转账10000
         -等待下个结算周期，查看出块奖励和质押奖励是否更新
     """
    from_address, from_ = generate_account(normal_aide, normal_aide.web3.toVon(200000, 'lat'))
    benefit_address, benefit_ = generate_account(normal_aide, 0)
    normal_aide.staking.create_staking(benefit_address=benefit_address, reward_per=1000, private_key=from_)

    wait_settlement(normal_aide)

    block_reward = normal_aide.staking.get_block_reward()
    staking_reward = normal_aide.staking.get_staking_reward()
    logger.info("block_reward: {} staking_reward: {}".format(block_reward, staking_reward))

    benefit_balance = normal_aide.platon.get_balance(benefit_address)
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
def test_zero_execution_block_check_incentive_pool(normal_aides):
    """
     测试 私链启动后自由/锁仓质押节点，构建节点零出块，查看激励池金额
     @Desc:
         -启动私链，账户余额200000，质押节点10000
         -停止节点，等待节点零出块，查看激励池金额
     """
    create_sta_free_or_lock(normal_aides[0])

    wait_settlement(normal_aides[0])

    block_reward = normal_aides[0].staking.get_block_reward()
    staking_reward_total = normal_aides[0].staking.get_staking_reward()
    logger.info("block_reward: {} staking_reward: {}".format(block_reward, staking_reward_total))
    # verifier_num = normal_aides[0].calculator.get_verifier_count()
    # staking_reward = int(Decimal(str(staking_reward_total)) / Decimal(str(verifier_num)))
    logger.info("停止节点")
    normal_aides[0].node.stop()

    incentive_pool_balance = normal_aides[1].platon.get_balance(INCENTIVE_POOL_ACCOUNT)
    logger.info("激励池金额：{}".format(incentive_pool_balance))
    wait_settlement(normal_aides[1])

    blocknumber = get_block_count_number(normal_aides[0].node.node_id)
    block_reward_total = blocknumber * Decimal(str(block_reward))
    logger.info("节点出块奖励：{}".format(block_reward_total))

    penalty_amount = int(Decimal(str(block_reward)) * Decimal(str(normal_aides[1].economic.slashing.slashBlocksReward)))
    logger.info("零出块处罚金额：{}".format(penalty_amount))
    incentive_pool_balance1 = normal_aides[1].platon.get_balance(INCENTIVE_POOL_ACCOUNT)
    logger.info("激励池金额：{}".format(incentive_pool_balance1))

    assert incentive_pool_balance1 == incentive_pool_balance + penalty_amount - block_reward_total
