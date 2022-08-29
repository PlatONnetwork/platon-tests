import os.path
import time
from collections import namedtuple
from os.path import join
from random import choice

import pytest
from loguru import logger
from platon_aide import Aide
from platon_env.chain import Chain
from platon_env.genesis import Genesis

from lib.basic_data import BaseData
from lib.funcs import assert_chain, get_aides, wait_settlement
from setting.setting import BASE_DIR, GENESIS_FILE


@pytest.fixture(scope='session')
def chain(request):
    """ 返回链对象，不恢复环境，请谨慎使用
    """
    chain_file = request.config.getoption("--chainFile")
    chain = Chain.from_file(join(BASE_DIR, chain_file))
    chain.install()
    # todo：优化等待链出块的方式
    time.sleep(3)

    yield chain
    # chain.uninstall()


@pytest.fixture
def deploy_chain(chain):
    chain.install()
    logger.info(f"deploy_chain")
    time.sleep(5)


@pytest.fixture
def condition_chain(chain, request):
    """
    支持在使用该fixture时，传入一个参数，返回一个符合条件的chain对象。
    当前链无法满足条件时，会进行重新部署。
    注意：
    1、通过lib.funcs.CONDITIONS，获取当前支持的判断条件
    2、多个条件，请使用多个fixture来完成
    """
    condition = request.param
    result = assert_chain(chain, condition)
    if not result:
        chain.install()
    return chain


@pytest.fixture()
def reset_chain(chain: Chain):
    """ 返回chain对象，并且在用例运行完成后恢复环境
    """
    chain.install()
    time.sleep(5)  # 等待链出块


@pytest.fixture(scope='session')
def aides(chain: Chain):
    """ 返回链上所有节点的aide对象列表
    """
    aides = get_aides(chain, 'all')
    BaseData(aides).set_var_info()
    return aides


@pytest.fixture
def aide(aides) -> Aide:
    """ 返回一个随机节点的aide对象
    """
    return choice(aides)


@pytest.fixture(scope='session')
def init_aides(chain: Chain):
    """ 返回链上创世节点的aide对象列表
    """
    init_aides = get_aides(chain, 'init')
    BaseData(init_aides).set_var_info()
    return init_aides


@pytest.fixture
def init_aide(init_aides):
    """ 返回一个创世节点的aide对象
    """
    init_aides = choice(init_aides)
    return init_aides


@pytest.fixture(scope='session')
def normal_aides(chain: Chain):
    """ 返回链上普通节点的aide对象列表
    """
    normal_aides = get_aides(chain, 'normal')
    BaseData(normal_aides).set_var_info()
    return normal_aides


@pytest.fixture
def normal_aide(normal_aides):
    """ 返回一个普通节点的aide对象
    """
    normal_aide = choice(normal_aides)
    return normal_aide


@pytest.fixture
def validator_aides():
    ...


@pytest.fixture
def validator_aide(validator_aides):
    ...


@pytest.fixture
def verifier_aides():
    ...


@pytest.fixture
def verifier_aide(validator_aides):
    ...


@pytest.fixture()
def solidity(node, request):
    """ 根据传入的合约参数，返回一个solidity合约对象
    注意：
    1、
    """
    name = request.param
    file = ''
    assert os.path.isfile(file), ''
    return node.web3.platon.contract()


@pytest.fixture()
def wasm(node, request):
    """ 根据传入的合约参数，返回一个solidity合约对象
    """
    name = request.param
    file = ''
    assert os.path.isfile(file), ''
    return node.web3.platon.contract(vm_type='wasm')


def generate_account(aide, balance=0):
    account = aide.platon.account.create(hrp=aide.hrp)
    address = account.address
    prikey = account.privateKey.hex()[2:]
    if balance != 0:
        aide.transfer.transfer(address, balance)
    return address, prikey


# def get_datahash(aide, txn, privatekey=Master_prikey):
#     if not txn.get('nonce'):
#         account = aide.web3.platon.account.from_key(privatekey, hrp=aide.web3.hrp)
#         nonce = aide.web3.platon.get_transaction_count(account.address)
#         txn['nonce'] = nonce
#
#     signed_txn = aide.web3.platon.account.sign_transaction(txn, privatekey, hrp=aide.web3.hrp)
#     data_hash = HexBytes(signed_txn.rawTransaction).hex()
#     return data_hash

# def set_var_info(aides):
#     """获取/设置 常用变量数据"""
#     for aide in aides:
#         staking_limit = aide.delegate._economic.staking_limit
#         delegate_limit = aide.delegate._economic.delegate_limit
#
#         delegate_amount = delegate_limit * 100
#
#         init_sta_account_amt = staking_limit * 10
#         init_del_account_amt = staking_limit * 10
#
#         setattr(aide, "staking_limit", staking_limit)
#         setattr(aide, "delegate_limit", delegate_limit)
#         setattr(aide, "delegate_amount", delegate_amount)
#         setattr(aide, "init_sta_account_amt", init_sta_account_amt)
#         setattr(aide, "init_del_account_amt", init_del_account_amt)


def create_sta_del_account(aide, sta_amt, del_amt):
    sta_addr, sta_pk = generate_account(aide, sta_amt)
    del_addr, del_pk = generate_account(aide, del_amt)
    return sta_addr, sta_pk, del_addr, del_pk


def create_sta_del(aide, restr_plan=None, mix=False):
    sta_addr, sta_pk, del_addr, del_pk = create_sta_del_account(aide, BaseData.init_sta_account_amt,
                                                                BaseData.init_del_account_amt)
    assert aide.staking.create_staking(amount=BaseData.staking_limit, benefit_address=sta_addr,
                                       private_key=sta_pk)['code'] == 0
    StakingBlockNum = aide.staking.staking_info.StakingBlockNum
    if not restr_plan:
        assert aide.delegate.delegate(amount=BaseData.delegate_amount, balance_type=0,
                                      private_key=del_pk)['code'] == 0
    else:
        assert aide.restricting.restricting(release_address=del_addr, plans=restr_plan,
                                            private_key=del_pk)['code'] == 0
        restr_info = aide.restricting.get_restricting_info(del_addr)
        logger.info(f'setup -> restr_info: {restr_info}')
        assert aide.delegate.delegate(amount=BaseData.delegate_amount, balance_type=1,
                                      private_key=del_pk)['code'] == 0
    if mix:
        assert aide.delegate.delegate(amount=BaseData.delegate_amount, balance_type=0,
                                      private_key=del_pk)['code'] == 0

    StaDel = namedtuple("StaDel", ['StakingBlockNum', 'sta_addr', 'sta_pk', 'del_addr', 'del_pk'])

    return StaDel._make([StakingBlockNum, sta_addr, sta_pk, del_addr, del_pk])


@pytest.fixture(scope='module')
def update_undelegate_freeze_duration(chain: Chain):
    genesis = Genesis(GENESIS_FILE)
    genesis.data['economicModel']['staking']['unDelegateFreezeDuration'] = 2
    new_gen_file = GENESIS_FILE.replace(".json", "_new.json")
    genesis.save_as(new_gen_file)

    yield chain, new_gen_file


@pytest.fixture()
def create_lock_free_amt(update_undelegate_freeze_duration, normal_aides):
    chain, new_gen_file = update_undelegate_freeze_duration
    chain.install(genesis_file=new_gen_file)
    time.sleep(5)

    normal_aide0, normal_aide1 = normal_aides[0], normal_aides[1],
    normal_aide0_namedtuple = create_sta_del(normal_aide0)
    normal_aide1_namedtuple = create_sta_del(normal_aide1)

    wait_settlement(normal_aide0)

    assert normal_aide0.delegate.withdrew_delegate(private_key=normal_aide0_namedtuple.del_pk,
                                                   staking_block_identifier=normal_aide0_namedtuple.StakingBlockNum,
                                                   amount=BaseData.delegate_amount, )['code'] == 0

    yield normal_aide0, normal_aide1, normal_aide0_namedtuple, normal_aide1_namedtuple


@pytest.fixture()
def create_lock_restr_amt(update_undelegate_freeze_duration, normal_aides):
    chain, new_gen_file = update_undelegate_freeze_duration
    chain.install(genesis_file=new_gen_file)
    time.sleep(5)

    normal_aide0, normal_aide1 = normal_aides[0], normal_aides[1],

    lockup_amount = BaseData.delegate_amount  # platon/10 * 100
    plan = [{'Epoch': 10, 'Amount': lockup_amount}]

    normal_aide0_namedtuple = create_sta_del(normal_aide0, plan)
    normal_aide1_namedtuple = create_sta_del(normal_aide1, )

    wait_settlement(normal_aide0)

    assert normal_aide0.delegate.withdrew_delegate(private_key=normal_aide0_namedtuple.del_pk,
                                                   staking_block_identifier=normal_aide0_namedtuple.StakingBlockNum,
                                                   amount=BaseData.delegate_amount, )['code'] == 0
    yield normal_aide0, normal_aide1, normal_aide0_namedtuple, normal_aide1_namedtuple


@pytest.fixture()
def create_lock_mix_amt_free_unlock_long(update_undelegate_freeze_duration, normal_aides):
    """
    创建锁定期 混合金额 自由金额解锁周期更长
    # 先创建锁仓金额的委托
    # wait 160 ==> 锁仓金额 进入生效期
    # 赎回委托锁仓金额 进入 锁定期 2
    # 发起自由金额委托
    # wait 160 ==> 锁仓金额锁定剩下 1， 自由金额生效
    # 赎回自由金额委托 自由金额 锁定期 2
    # setup ==>  锁仓金额 剩1个周期解锁 自由金额 剩2个周期解锁
    """
    chain, new_gen_file = update_undelegate_freeze_duration
    chain.install(genesis_file=new_gen_file)
    time.sleep(5)

    normal_aide0, normal_aide1 = normal_aides[0], normal_aides[1],

    lockup_amount = BaseData.delegate_amount  # platon/10 * 100
    plan = [{'Epoch': 10, 'Amount': lockup_amount}]

    normal_aide0_namedtuple = create_sta_del(normal_aide0, plan)
    normal_aide1_namedtuple = create_sta_del(normal_aide1, )

    wait_settlement(normal_aide0)
    logger.info(f'{"赎回锁仓金额":*^50s}')
    assert normal_aide0.delegate.withdrew_delegate(private_key=normal_aide0_namedtuple.del_pk,
                                                   staking_block_identifier=normal_aide0_namedtuple.StakingBlockNum,
                                                   amount=BaseData.delegate_amount, )['code'] == 0
    logger.info(f'{"自由金额委托":*^50s}')
    assert normal_aide0.delegate.delegate(amount=BaseData.delegate_amount, balance_type=0,
                                          private_key=normal_aide0_namedtuple.del_pk)['code'] == 0
    wait_settlement(normal_aide0)
    logger.info(f'{"赎回自由金额":*^50s}')
    assert normal_aide0.delegate.withdrew_delegate(private_key=normal_aide0_namedtuple.del_pk,
                                                   staking_block_identifier=normal_aide0_namedtuple.StakingBlockNum,
                                                   amount=BaseData.delegate_amount, )['code'] == 0

    yield normal_aide0, normal_aide1, normal_aide0_namedtuple, normal_aide1_namedtuple


@pytest.fixture()
def create_lock_mix_amt_restr_unlock_long(create_lock_free_amt):
    """
    创建锁定期 混合金额 锁仓金额解锁周期更长
    # 先创建自由金额的委托
    # wait 160 ==> 自由金额 进入生效期
    # 赎回委托自由金额 进入 锁定期 2
    ======》fixture.create_lock_free_amt
    # 发起锁仓金额委托
    # wait 160 ==> 自由金额锁定剩下 1， 锁仓金额生效
    # 赎回锁仓金额委托 锁仓金额 锁定期 2
    # setup ==>  自由金额 剩1个周期解锁 锁仓金额 剩2个周期解锁
    """
    normal_aide0, normal_aide1, normal_aide0_namedtuple, normal_aide1_namedtuple = create_lock_free_amt

    lockup_amount = BaseData.delegate_amount  # platon/10 * 100
    plan = [{'Epoch': 10, 'Amount': lockup_amount}]
    logger.info(f'{"锁仓金额委托":*^50s}')
    assert normal_aide0.restricting.restricting(release_address=normal_aide0_namedtuple.del_addr, plans=plan,
                                                private_key=normal_aide0_namedtuple.del_pk)['code'] == 0
    restr_info = normal_aide0.restricting.get_restricting_info(normal_aide0_namedtuple.del_addr)
    logger.info(f'setup -> restr_info: {restr_info}')
    assert normal_aide0.delegate.delegate(amount=BaseData.delegate_amount, balance_type=1,
                                          private_key=normal_aide0_namedtuple.del_pk)['code'] == 0

    wait_settlement(normal_aide0)
    logger.info(f'{"赎回锁仓金额":*^50s}')
    assert normal_aide0.delegate.withdrew_delegate(private_key=normal_aide0_namedtuple.del_pk,
                                                   staking_block_identifier=normal_aide0_namedtuple.StakingBlockNum,
                                                   amount=BaseData.delegate_amount, )['code'] == 0

    yield normal_aide0, normal_aide1, normal_aide0_namedtuple, normal_aide1_namedtuple


@pytest.fixture()
def create_lock_mix_amt_free_(update_undelegate_freeze_duration, normal_aides):
    chain, new_gen_file = update_undelegate_freeze_duration
    chain.install(genesis_file=new_gen_file)
    time.sleep(5)

    normal_aide0, normal_aide1 = normal_aides[0], normal_aides[1],

    lockup_amount = BaseData.delegate_amount  # platon/10 * 100
    plan = [{'Epoch': 10, 'Amount': lockup_amount}]

    normal_aide0_namedtuple = create_sta_del(normal_aide0, plan, mix=True)
    normal_aide1_namedtuple = create_sta_del(normal_aide1, )

    wait_settlement(normal_aide0)

    assert normal_aide0.delegate.withdrew_delegate(private_key=normal_aide0_namedtuple.del_pk,
                                                   staking_block_identifier=normal_aide0_namedtuple.StakingBlockNum,
                                                   amount=BaseData.delegate_amount, )['code'] == 0
    yield normal_aide0, normal_aide1, normal_aide0_namedtuple, normal_aide1_namedtuple
