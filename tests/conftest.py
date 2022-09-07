import os.path
import time
from collections import namedtuple
from random import choice

import pytest
from loguru import logger
from platon_aide import Aide
from platon_aide.economic import Economic
from platon_env import Node
from platon_env.chain import Chain
from platon_env.genesis import Genesis

from lib.utils import new_account
from lib.basic_data import BaseData
from lib.funcs import assert_chain, wait_settlement
from setting.setting import GENESIS_FILE
from setting.account import MAIN_ACCOUNT


@pytest.fixture
def chain(initializer, request) -> Chain:
    """ 返回一个符合条件的chain对象，如果没有指定条件，会重新初始化chain后返回
    使用方法：
    1、和普通fixture一样直接使用
    2、从测试用例中传入条件到fixture（条件定义：lib.funcs.CONDITIONS）

    使用示例：
    @pytest.mark.parametrize('chain', ['test'], indirect=True)
    def test_example(chain):
        ...
    """
    condition = getattr(request, 'param', None)

    # 根据条件判断，是否可以直接使用环境
    if condition:
        result = assert_chain(initializer, condition)
        if result:
            return initializer

    # 重新初始化环境
    initializer.stop()
    initializer.init(force=True)
    initializer.start()

    return initializer


@pytest.fixture
def nodes(chain) -> [Node]:
    return chain.nodes


@pytest.fixture
def init_nodes(chain) -> [Node]:
    return chain.init_nodes


@pytest.fixture
def normal_nodes(chain) -> [Node]:
    return chain.normal_nodes


@pytest.fixture
def aides(nodes) -> [Aide]:
    aides = [node.aide for node in nodes]
    for aide in aides:
        aide.set_default_account(MAIN_ACCOUNT)

    return aides


@pytest.fixture
def init_aides(init_nodes) -> [Aide]:
    aides = [node.aide for node in init_nodes]
    for aide in aides:
        aide.set_default_account(MAIN_ACCOUNT)

    return aides


@pytest.fixture
def normal_aides(normal_nodes) -> [Aide]:
    aides = [node.aide for node in normal_nodes]
    for aide in aides:
        aide.set_default_account(MAIN_ACCOUNT)

    return aides


@pytest.fixture
def aide(aides) -> Aide:
    """ 返回一个随机节点的aide对象
    """
    return choice(aides)


@pytest.fixture
def init_aide(init_aides) -> Aide:
    """ 返回一个创世节点的aide对象
    """
    return choice(init_aides)


@pytest.fixture
def normal_aide(normal_aides) -> Aide:
    """ 返回一个普通节点的aide对象
    """
    return choice(normal_aides)


@pytest.fixture
def economic(aide) -> Economic:
    """ 返回一个普通节点的aide对象
    """
    return aide.economic


@pytest.fixture()
def solidity(aide, request):
    """ 根据传入的合约名称，编译合约，并返回一个solidity合约对象
    # todo: 待实现
    """
    name = request.param
    file = ''
    assert os.path.isfile(file), ''
    return aide.web3.platon.contract()


@pytest.fixture()
def wasm(aide, request):
    """ 根据传入的合约名称，编译合约，返回一个wasm合约对象
    # todo: 待实现
    """
    name = request.param
    file = ''
    assert os.path.isfile(file), ''
    return aide.web3.platon.contract(vm_type='wasm')


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
    sta_addr, sta_pk = new_account(aide, sta_amt)
    del_addr, del_pk = new_account(aide, del_amt)
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

    genesis = Genesis(GENESIS_FILE)
    new_gen_file = GENESIS_FILE.replace(".json", "_new.json")
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

    normal_aide0_namedtuple = create_sta_del(normal_aide0, plan, mix=True)
    if req_param.get("ManyAcc"):
        normal_aide1_namedtuple = create_sta_del(normal_aide1, plan, mix=True)
    else:
        normal_aide1_namedtuple = create_sta_del(normal_aide1, )

    wait_settlement(normal_aide0)

    assert normal_aide0.delegate.withdrew_delegate(private_key=normal_aide0_namedtuple.del_pk,
                                                   staking_block_identifier=normal_aide0_namedtuple.StakingBlockNum,
                                                   amount=BaseData.delegate_amount * 2, )['code'] == 0
    if req_param.get("ManyAcc"):
        assert normal_aide0.delegate.withdrew_delegate(private_key=normal_aide1_namedtuple.del_pk,
                                                       staking_block_identifier=normal_aide1_namedtuple.StakingBlockNum,
                                                       amount=BaseData.delegate_amount * 2, )['code'] == 0

    yield normal_aide0, normal_aide1, normal_aide0_namedtuple, normal_aide1_namedtuple


@pytest.fixture()
def test02(choose_undelegate_freeze_duration):
    chain, new_gen_file = choose_undelegate_freeze_duration
    print(chain, new_gen_file)
    pass
