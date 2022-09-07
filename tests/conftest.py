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
from lib.utils import PrintInfo as PF
from setting.setting import BASE_DIR, GENESIS_FILE


@pytest.fixture(scope='session')
def chain(request):
    """ 返回链对象，不恢复环境，请谨慎使用
    """
    chain_file = request.config.getoption("--chainFile")
    chain = Chain.from_file(join(BASE_DIR, chain_file))
    # 先清理supervisor，再进行安装
    for host in chain.hosts:
        host.supervisor.clean()
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
def normal_aide(normal_aides) -> Aide:
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


def create_sta_del_account(aide, sta_amt, del_amt):
    sta_addr, sta_pk = generate_account(aide, sta_amt)
    del_addr, del_pk = generate_account(aide, del_amt)
    return sta_addr, sta_pk, del_addr, del_pk


def create_sta_del(aide, restr_plan=None, mix=False):
    """
    创建质押和委托
    @param aide:
    @param restr_plan: 标识锁仓计划
    @param mix: 标识混合金额场景
    @Desc:
        - 传aide 即创建自由金额委托
        - 传aide + restr_plan  即创建锁仓金额委托
        - 传aide + restr_plan  先创建锁仓 在创建自由金额委托
    """
    # create_sta_del_account 调用一次会新建账户
    sta_addr, sta_pk, del_addr, del_pk = create_sta_del_account(aide, BaseData.init_sta_account_amt,
                                                                BaseData.init_del_account_amt)
    assert aide.staking.create_staking(amount=BaseData.staking_limit * 4, benefit_address=sta_addr,
                                       private_key=sta_pk)['code'] == 0
    StakingBlockNum = aide.staking.staking_info.StakingBlockNum
    if not restr_plan:
        logger.info(f'{f"{aide.node}: 自由金额委托":*^50s}')
        assert aide.delegate.delegate(amount=BaseData.delegate_amount, balance_type=0,
                                      private_key=del_pk)['code'] == 0
    else:
        logger.info(f'{f"{aide.node}: 锁仓金额委托":*^50s}')
        assert aide.restricting.restricting(release_address=del_addr, plans=restr_plan,
                                            private_key=del_pk)['code'] == 0
        restr_info = aide.restricting.get_restricting_info(del_addr)
        logger.info(f'setup -> restr_info: {restr_info}')
        assert aide.delegate.delegate(amount=BaseData.delegate_amount, balance_type=1,
                                      private_key=del_pk)['code'] == 0
    if mix:
        logger.info(f'{f"{aide.node}: 自由金额委托":*^50s}')
        assert aide.delegate.delegate(amount=BaseData.delegate_amount, balance_type=0,
                                      private_key=del_pk)['code'] == 0

    StaDel = namedtuple("StaDel", ['StakingBlockNum', 'sta_addr', 'sta_pk', 'del_addr', 'del_pk', 'node_id'])

    return StaDel._make([StakingBlockNum, sta_addr, sta_pk, del_addr, del_pk, aide.node.node_id])


@pytest.fixture(scope='module')
def update_undelegate_freeze_duration(chain: Chain):
    genesis = Genesis(GENESIS_FILE)
    genesis.data['economicModel']['staking']['unDelegateFreezeDuration'] = 2
    new_gen_file = GENESIS_FILE.replace(".json", "_new.json")
    genesis.save_as(new_gen_file)

    yield chain, new_gen_file


@pytest.fixture(scope='module')
def update_undelegate_freeze_duration_three(chain: Chain):
    genesis = Genesis(GENESIS_FILE)
    genesis.data['economicModel']['staking']['unStakeFreezeDuration'] = 3
    genesis.data['economicModel']['staking']['unDelegateFreezeDuration'] = 3
    new_gen_file = GENESIS_FILE.replace(".json", "_new.json")
    genesis.save_as(new_gen_file)

    yield chain, new_gen_file


@pytest.fixture(scope='module')
def choose_undelegate_freeze_duration(request, chain):
    req_param = request.param
    duration = req_param.get("duration")
    slashBlocksReward = req_param.get("slashBlock")

    genesis = Genesis(GENESIS_FILE)
    new_gen_file = GENESIS_FILE.replace(".json", "_new.json")
    if slashBlocksReward:
        genesis.data['economicModel']['slashing']['slashBlocksReward'] = slashBlocksReward

    if duration > 2:
        genesis.data['economicModel']['staking']['unStakeFreezeDuration'] = duration
        genesis.data['economicModel']['staking']['unDelegateFreezeDuration'] = duration
    elif duration == 2:
        genesis.data['economicModel']['staking']['unDelegateFreezeDuration'] = 2
    else:
        genesis.data['economicModel']['staking']['unDelegateFreezeDuration'] = 1
    genesis.save_as(new_gen_file)
    yield chain, new_gen_file


@pytest.fixture()
def create_lock_free_amt(request, choose_undelegate_freeze_duration, normal_aides):
    """
    创建锁定期 只有自由金额
    @param choose_undelegate_freeze_duration: 修改创世文件赎回委托锁定周期参数
    @param normal_aides:
    @param request: param 根据使用fixture传入参数来判断一对多 or 多对多场景
    @Desc:
        - req_param ManyAcc: False
            - 只针对A节点赎回(A节点锁定期有钱)
        - req_param ManyAcc: True
            - A、B节点都赎回(A、B节点锁定期有钱)
    """
    req_param = request.param
    chain, new_gen_file = choose_undelegate_freeze_duration
    chain.install(genesis_file=new_gen_file)
    time.sleep(5)

    normal_aide0, normal_aide1 = normal_aides[0], normal_aides[1],
    normal_aide0_namedtuple = create_sta_del(normal_aide0)
    normal_aide1_namedtuple = create_sta_del(normal_aide1)

    wait_settlement(normal_aide0)
    logger.info(f'{f"{normal_aide0.node}: 赎回自由金额委托":*^50s}')
    assert normal_aide0.delegate.withdrew_delegate(BaseData.delegate_amount, normal_aide0_namedtuple.StakingBlockNum,
                                                   private_key=normal_aide0_namedtuple.del_pk)['code'] == 0

    if req_param.get("ManyAcc"):
        logger.info(f'{f"{normal_aide1.node}: 赎回自由金额委托":*^50s}')
        assert normal_aide0.delegate.withdrew_delegate(BaseData.delegate_amount,
                                                       normal_aide1_namedtuple.StakingBlockNum,
                                                       normal_aide1.node.node_id,
                                                       private_key=normal_aide1_namedtuple.del_pk)['code'] == 0

    yield normal_aide0, normal_aide1, normal_aide0_namedtuple, normal_aide1_namedtuple, req_param


@pytest.fixture()
def create_lock_restr_amt(request, choose_undelegate_freeze_duration, normal_aides):
    """
    创建锁定期 只有锁仓金额
    @param choose_undelegate_freeze_duration: 修改创世文件赎回委托锁定周期参数
    @param normal_aides:
    @param request: param 根据使用fixture传入参数来判断一对多 or 多对多场景
    @Desc:
        - req_param ManyAcc: False
            - 只赎回A节点锁仓金额
        - req_param ManyAcc: True
            - A、B节点都赎回锁仓金额
    """
    req_param = request.param
    chain, new_gen_file = choose_undelegate_freeze_duration
    chain.install(genesis_file=new_gen_file)
    time.sleep(5)

    normal_aide0, normal_aide1 = normal_aides[0], normal_aides[1],

    lockup_amount = BaseData.delegate_amount  # platon/10 * 100
    plan = [{'Epoch': 10, 'Amount': lockup_amount}]

    normal_aide0_namedtuple = create_sta_del(normal_aide0, plan)

    if req_param.get("ManyAcc"):
        normal_aide1_namedtuple = create_sta_del(normal_aide1, plan)
    else:
        normal_aide1_namedtuple = create_sta_del(normal_aide1, )

    wait_settlement(normal_aide0)
    logger.info(f'{f"{normal_aide0.node}: 赎回锁仓金额委托":*^50s}')
    assert normal_aide0.delegate.withdrew_delegate(private_key=normal_aide0_namedtuple.del_pk,
                                                   staking_block_identifier=normal_aide0_namedtuple.StakingBlockNum,
                                                   amount=BaseData.delegate_amount, )['code'] == 0
    if req_param.get("ManyAcc"):
        logger.info(f'{f"{normal_aide1.node}: 赎回锁仓金额委托":*^50s}')
        assert normal_aide0.delegate.withdrew_delegate(BaseData.delegate_amount,
                                                       normal_aide1_namedtuple.StakingBlockNum,
                                                       normal_aide1.node.node_id,
                                                       private_key=normal_aide1_namedtuple.del_pk)['code'] == 0

    yield normal_aide0, normal_aide1, normal_aide0_namedtuple, normal_aide1_namedtuple, req_param


@pytest.fixture()
def create_lock_mix_amt_free_unlock_long(create_lock_restr_amt):
    """
    创建锁定期 混合金额 自由金额解锁周期更长
    # 先创建锁仓金额的委托
    # wait 160 ==> 锁仓金额 进入生效期
    # 赎回委托锁仓金额 进入 锁定期 2
    ======》fixture.create_lock_restr_amt
    # 发起自由金额委托
    # wait 160 ==> 锁仓金额锁定剩下 1， 自由金额生效
    # 赎回自由金额委托 自由金额 锁定期 2
    # setup ==>  锁仓金额 剩1个周期解锁 自由金额 剩2个周期解锁
    """
    normal_aide0, normal_aide1, normal_aide0_namedtuple, normal_aide1_namedtuple, req_param = create_lock_restr_amt

    logger.info(f'{f"{normal_aide0.node}: 自由金额委托":*^50s}')
    assert normal_aide0.delegate.delegate(amount=BaseData.delegate_amount, balance_type=0,
                                          private_key=normal_aide0_namedtuple.del_pk)['code'] == 0
    if req_param.get("MixAcc"):
        # 在多对多场景下,灵活创建多种账户金额数据 基于ManyAcc=True
        # MixAcc: False 表示节点A 拥有冻结期混合金额 自由金额解锁周期更长/节点B 拥有冻结期锁仓金额,不拥有自由金额
        # MixAcc: True  表示节点A/B 都拥有冻结期混合金额 自由金额解锁周期更长
        logger.info(f'{f"{normal_aide1.node}: 自由金额委托":*^50s}')
        assert normal_aide0.delegate.delegate(BaseData.delegate_amount, 0, normal_aide1.node.node_id,
                                              private_key=normal_aide1_namedtuple.del_pk)['code'] == 0

    wait_settlement(normal_aide0)
    logger.info(f'{f"{normal_aide0.node}: 赎回自由金额":*^50s}')
    assert normal_aide0.delegate.withdrew_delegate(private_key=normal_aide0_namedtuple.del_pk,
                                                   staking_block_identifier=normal_aide0_namedtuple.StakingBlockNum,
                                                   amount=BaseData.delegate_amount, )['code'] == 0
    if req_param.get("MixAcc"):
        logger.info(f'{f"{normal_aide1.node}: 赎回自由金额":*^50s}')
        assert normal_aide0.delegate.withdrew_delegate(BaseData.delegate_amount,
                                                       normal_aide1_namedtuple.StakingBlockNum,
                                                       normal_aide1.node.node_id,
                                                       private_key=normal_aide1_namedtuple.del_pk)['code'] == 0
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
    normal_aide0, normal_aide1, normal_aide0_namedtuple, normal_aide1_namedtuple, req_param = create_lock_free_amt

    lockup_amount = BaseData.delegate_amount  # platon/10 * 100
    plan = [{'Epoch': 10, 'Amount': lockup_amount}]
    logger.info(f'{f"{normal_aide0.node}: 锁仓金额委托":*^50s}')
    assert normal_aide0.restricting.restricting(release_address=normal_aide0_namedtuple.del_addr, plans=plan,
                                                private_key=normal_aide0_namedtuple.del_pk)['code'] == 0
    restr_info = normal_aide0.restricting.get_restricting_info(normal_aide0_namedtuple.del_addr)
    logger.info(f'{normal_aide0.node} 锁仓计划信息: {restr_info}')
    assert normal_aide0.delegate.delegate(amount=BaseData.delegate_amount, balance_type=1,
                                          private_key=normal_aide0_namedtuple.del_pk)['code'] == 0

    if req_param.get("MixAcc"):
        # 在多对多场景下,灵活创建多种账户金额数据 基于ManyAcc=True
        # MixAcc: False 表示节点A 拥有冻结期混合金额 锁仓金额解锁周期更长/节点B 拥有冻结期自由金额,不拥有锁仓金额
        # MixAcc: True  表示节点A/B 都拥有冻结期混合金额 锁仓金额解锁周期更长
        logger.info(f'{f"{normal_aide1.node}: 锁仓金额委托":*^50s}')
        assert normal_aide0.restricting.restricting(release_address=normal_aide1_namedtuple.del_addr, plans=plan,
                                                    private_key=normal_aide1_namedtuple.del_pk)['code'] == 0
        restr_info = normal_aide0.restricting.get_restricting_info(normal_aide1_namedtuple.del_addr)
        logger.info(f'{normal_aide0.node} 锁仓计划信息: {restr_info}')
        assert normal_aide0.delegate.delegate(BaseData.delegate_amount, 1, normal_aide1.node.node_id,
                                              private_key=normal_aide1_namedtuple.del_pk)['code'] == 0

    wait_settlement(normal_aide0)
    logger.info(f'{f"{normal_aide0.node}: 赎回锁仓金额":*^50s}')
    assert normal_aide0.delegate.withdrew_delegate(private_key=normal_aide0_namedtuple.del_pk,
                                                   staking_block_identifier=normal_aide0_namedtuple.StakingBlockNum,
                                                   amount=BaseData.delegate_amount, )['code'] == 0

    if req_param.get("MixAcc"):
        logger.info(f'{f"{normal_aide1.node}: 赎回锁仓金额":*^50s}')
        assert normal_aide0.delegate.withdrew_delegate(BaseData.delegate_amount,
                                                       normal_aide1_namedtuple.StakingBlockNum,
                                                       normal_aide1.node.node_id,
                                                       private_key=normal_aide1_namedtuple.del_pk)['code'] == 0

    yield normal_aide0, normal_aide1, normal_aide0_namedtuple, normal_aide1_namedtuple


@pytest.fixture()
def create_lock_mix_amt_unlock_eq(request, choose_undelegate_freeze_duration, normal_aides):
    """
    创建锁定期 混合金额 锁仓金额和自由金额解锁周期相等
    # 赎回委托金额: BaseData.delegate_amount * 2
    """
    req_param = request.param
    chain, new_gen_file = choose_undelegate_freeze_duration
    chain.install(genesis_file=new_gen_file)
    time.sleep(5)

    normal_aide0, normal_aide1 = normal_aides[0], normal_aides[1],

    lockup_amount = BaseData.delegate_amount  # platon/10 * 100
    plan = [{'Epoch': 10, 'Amount': lockup_amount}]

    logger.info(f"{normal_aide0.node}: 创建质押和 混合金额")
    normal_aide0_namedtuple = create_sta_del(normal_aide0, plan, mix=True)
    if req_param.get("ManyAcc"):
        logger.info(f"{normal_aide1.node}: 创建质押和 混合金额")
        normal_aide1_namedtuple = create_sta_del(normal_aide1, plan, mix=True)
    else:
        logger.info(f"{normal_aide1.node}: 创建质押和 自由金额")
        normal_aide1_namedtuple = create_sta_del(normal_aide1, )

    wait_settlement(normal_aide0)
    logger.info(f"{normal_aide0.node}: 赎回锁仓+自由金额 进入冻结期")
    assert normal_aide0.delegate.withdrew_delegate(private_key=normal_aide0_namedtuple.del_pk,
                                                   staking_block_identifier=normal_aide0_namedtuple.StakingBlockNum,
                                                   amount=BaseData.delegate_amount * 2, )['code'] == 0
    if req_param.get("ManyAcc"):
        logger.info(f"{normal_aide1.node}: 赎回锁仓+自由金额 进入冻结期")
        assert normal_aide0.delegate.withdrew_delegate(private_key=normal_aide1_namedtuple.del_pk,
                                                       node_id=normal_aide1.node.node_id,
                                                       staking_block_identifier=normal_aide1_namedtuple.StakingBlockNum,
                                                       amount=BaseData.delegate_amount * 2, )['code'] == 0

    yield normal_aide0, normal_aide1, normal_aide0_namedtuple, normal_aide1_namedtuple


@pytest.fixture()
def lock_mix_amt_unlock_eq_delegate(request, create_lock_mix_amt_unlock_eq):
    """
    使用锁定期混合金额进行委托
    @param request: wait_settlement字段来控制 True 锁定期金额委托生效期 False 锁定期金额委托犹豫期
    @param create_lock_mix_amt_unlock_eq:
    @return:
    """
    normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt = create_lock_mix_amt_unlock_eq
    req_param = request.param

    logger.info(f"使用锁定期 锁仓+自由金额委托 delegate_limit * 110 = 1100")
    assert normal_aide0.delegate.delegate(BaseData.delegate_amount + (BaseData.delegate_limit * 10), 3,
                                          private_key=normal_aide0_nt.del_pk)['code'] == 0
    logger.info(f"使用锁定期 自由金额委托 delegate_limit * 70 = 700")
    assert normal_aide0.delegate.delegate(BaseData.delegate_limit * 70, 3,
                                          private_key=normal_aide0_nt.del_pk)['code'] == 0

    assert len(PF.p_get_delegate_lock_info(normal_aide0, normal_aide0_nt)['Locks']) == 1

    lock_residue_amt = BaseData.delegate_amount * 2 - (BaseData.delegate_amount + BaseData.delegate_limit * 80)
    logger.info(f"锁定期剩余自由金额: {lock_residue_amt} (2000 - 1100 - 700 = 200) ")

    if req_param.get("wait_settlement"):
        # 使锁定期委托金额 —> 进入 生效期
        wait_settlement(normal_aide0)

    yield normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt, lock_residue_amt


@pytest.fixture()
def acc_mix_amt_delegate(request, create_lock_mix_amt_unlock_eq):
    """
    使用账户混合金额进行委托
    @param request: wait_settlement字段来控制 True 账户金额委托生效期 False 账户金额委托犹豫期
    @param create_lock_mix_amt_unlock_eq:
    @return:
    """
    normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt = create_lock_mix_amt_unlock_eq
    req_param = request.param

    logger.info(f"使用账户自由金额委托: {BaseData.delegate_amount}")
    assert normal_aide0.delegate.delegate(BaseData.delegate_amount, 0,
                                          private_key=normal_aide0_nt.del_pk)['code'] == 0

    logger.info(f"使用账户锁仓金额委托: {BaseData.delegate_amount}")
    lockup_amount = BaseData.delegate_amount  # platon/10 * 100
    plan = [{'Epoch': 10, 'Amount': lockup_amount}]
    logger.info(f'{f"{normal_aide0.node}: 锁仓金额委托":*^50s}')
    assert normal_aide0.restricting.restricting(release_address=normal_aide0_nt.del_addr, plans=plan,
                                                private_key=normal_aide0_nt.del_pk)['code'] == 0
    assert normal_aide0.delegate.delegate(amount=BaseData.delegate_amount, balance_type=1,
                                          private_key=normal_aide0_nt.del_pk)['code'] == 0

    if req_param.get("wait_settlement"):
        # 使账户委托金额 —> 进入 生效期
        wait_settlement(normal_aide0)
