import time
from collections import namedtuple

import pytest
from loguru import logger
from platon_env.chain import Chain
from platon_env.genesis import Genesis

from lib.utils import new_account, lat
from lib.basic_data import BaseData
from lib.utils import wait_settlement
from lib.utils import PrintInfo as PF
from setting.setting import GENESIS_FILE


def create_sta_del_account(aide, sta_amt, del_amt):
    sta_account = new_account(aide, sta_amt)
    sta_addr, sta_pk = sta_account.address, sta_account.privateKey
    del_account = new_account(aide, del_amt)
    del_addr, del_pk = del_account.address, del_account.privateKey
    return sta_addr, sta_pk, del_addr, del_pk


def create_sta_free_or_lock(aide, restr_plan=None, benefit_address=None):
    """
    创建自由/锁仓金额并质押节点
    """
    if not restr_plan:
        sta_account = new_account(aide, lat(200000))
        assert aide.staking.create_staking(benefit_address=benefit_address, private_key=sta_account.privateKey)['code'] == 0
        logger.info("质押节点信息：{}".format(aide.staking.get_candidate_info()))
    else:
        sta_account = new_account(aide, balance=lat(200000), restricting=restr_plan)
        logger.info("锁仓计划：{}".format(aide.restricting.get_restricting_info(sta_account.address)))
        assert aide.staking.create_staking(balance_type=1, benefit_address=benefit_address, private_key=sta_account.privateKey)['code'] == 0
        logger.info("质押节点信息：{}".format(aide.staking.get_candidate_info()))

    return sta_account


def create_sta_del(aide, restr_plan=None, mix=False, sta_amt=None, reward_per=0):
    """
    创建质押和委托
    @param aide:
    @param sta_amt: 节点中创建质押的金额
    @param restr_plan: 标识锁仓计划
    @param mix: 标识混合金额场景
    @param reward_per: 分红比例 默认为0, 目前只针对A节点
    @Desc:
        - 传aide 即创建自由金额委托
        - 传aide + restr_plan  即创建锁仓金额委托
        - 传aide + restr_plan + mix=True  先创建锁仓 在创建自由金额委托
    """
    # create_sta_del_account 调用一次会新建账户
    sta_addr, sta_pk, del_addr, del_pk = create_sta_del_account(aide, BaseData.init_sta_account_amt,
                                                                BaseData.init_del_account_amt)
    if not sta_amt:
        sta_amt = BaseData.staking_limit * 4
    assert aide.staking.create_staking(amount=sta_amt, benefit_address=sta_addr,
                                       reward_per=reward_per,
                                       private_key=sta_pk)['code'] == 0
    StakingBlockNum = aide.staking.staking_info.StakingBlockNum
    if not restr_plan:
        logger.info(f'{f"{aide}: 自由金额委托":*^50s}')
        assert aide.delegate.delegate(amount=BaseData.delegate_amount, balance_type=0,
                                      private_key=del_pk)['code'] == 0
    else:
        logger.info(f'{f"{aide}: 锁仓金额委托":*^50s}')
        assert aide.restricting.restricting(release_address=del_addr, plans=restr_plan,
                                            private_key=del_pk)['code'] == 0
        restr_info = aide.restricting.get_restricting_info(del_addr)
        logger.info(f'setup -> restr_info: {restr_info}')
        assert aide.delegate.delegate(amount=BaseData.delegate_amount, balance_type=1,
                                      private_key=del_pk)['code'] == 0
    if mix:
        logger.info(f'{f"{aide}: 自由金额委托":*^50s}')
        assert aide.delegate.delegate(amount=BaseData.delegate_amount, balance_type=0,
                                      private_key=del_pk)['code'] == 0

    StaDel = namedtuple("StaDel", ['StakingBlockNum', 'sta_addr', 'sta_pk', 'del_addr', 'del_pk', 'node_id'])

    return StaDel._make([StakingBlockNum, sta_addr, sta_pk, del_addr, del_pk, aide.node_id])


@pytest.fixture()
def update_undelegate_freeze_duration(initializer: Chain, recover):
    genesis = Genesis(GENESIS_FILE)
    genesis.data['economicModel']['staking']['unDelegateFreezeDuration'] = 2
    new_gen_file = GENESIS_FILE.replace(".json", "_new.json")
    genesis.save_as(new_gen_file)

    yield initializer, new_gen_file


@pytest.fixture()
def update_undelegate_freeze_duration_three(initializer: Chain, recover):
    genesis = Genesis(GENESIS_FILE)
    genesis.data['economicModel']['staking']['unStakeFreezeDuration'] = 3
    genesis.data['economicModel']['staking']['unDelegateFreezeDuration'] = 3
    new_gen_file = GENESIS_FILE.replace(".json", "_new.json")
    genesis.save_as(new_gen_file)

    yield initializer, new_gen_file


@pytest.fixture()
def choose_undelegate_freeze_duration(request, initializer):
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
    elif duration == 0:
        genesis.data['economicModel']['staking']['unDelegateFreezeDuration'] = 0
    else:
        genesis.data['economicModel']['staking']['unDelegateFreezeDuration'] = 1
    genesis.save_as(new_gen_file)
    yield initializer, new_gen_file


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
    # chain.uninstall()
    for host in chain.hosts:
        host.supervisor.clean()
    chain.install(genesis_file=new_gen_file)
    time.sleep(5)

    normal_aide0, normal_aide1 = normal_aides[0], normal_aides[1],
    normal_aide0_namedtuple = create_sta_del(normal_aide0)
    normal_aide1_namedtuple = create_sta_del(normal_aide1)

    wait_settlement(normal_aide0)
    logger.info(f'{f"{normal_aide0}: 赎回自由金额委托":*^50s}')
    assert normal_aide0.delegate.withdrew_delegate(BaseData.delegate_amount, normal_aide0_namedtuple.StakingBlockNum,
                                                   private_key=normal_aide0_namedtuple.del_pk)['code'] == 0

    if req_param.get("ManyAcc"):
        logger.info(f'{f"{normal_aide1}: 赎回自由金额委托":*^50s}')
        assert normal_aide0.delegate.withdrew_delegate(BaseData.delegate_amount,
                                                       normal_aide1_namedtuple.StakingBlockNum,
                                                       normal_aide1.node_id,
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
    # chain.uninstall()
    for host in chain.hosts:
        host.supervisor.clean()
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
    logger.info(f'{f"{normal_aide0}: 赎回锁仓金额委托":*^50s}')
    assert normal_aide0.delegate.withdrew_delegate(private_key=normal_aide0_namedtuple.del_pk,
                                                   staking_block_identifier=normal_aide0_namedtuple.StakingBlockNum,
                                                   amount=BaseData.delegate_amount, )['code'] == 0
    if req_param.get("ManyAcc"):
        logger.info(f'{f"{normal_aide1}: 赎回锁仓金额委托":*^50s}')
        assert normal_aide0.delegate.withdrew_delegate(BaseData.delegate_amount,
                                                       normal_aide1_namedtuple.StakingBlockNum,
                                                       normal_aide1.node_id,
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

    logger.info(f'{f"{normal_aide0}: 自由金额委托":*^50s}')
    assert normal_aide0.delegate.delegate(amount=BaseData.delegate_amount, balance_type=0,
                                          private_key=normal_aide0_namedtuple.del_pk)['code'] == 0
    if req_param.get("MixAcc"):
        # 在多对多场景下,灵活创建多种账户金额数据 基于ManyAcc=True
        # MixAcc: False 表示节点A 拥有冻结期混合金额 自由金额解锁周期更长/节点B 拥有冻结期锁仓金额,不拥有自由金额
        # MixAcc: True  表示节点A/B 都拥有冻结期混合金额 自由金额解锁周期更长
        logger.info(f'{f"{normal_aide1}: 自由金额委托":*^50s}')
        assert normal_aide0.delegate.delegate(BaseData.delegate_amount, 0, normal_aide1.node_id,
                                              private_key=normal_aide1_namedtuple.del_pk)['code'] == 0

    wait_settlement(normal_aide0)
    logger.info(f'{f"{normal_aide0}: 赎回自由金额":*^50s}')
    assert normal_aide0.delegate.withdrew_delegate(private_key=normal_aide0_namedtuple.del_pk,
                                                   staking_block_identifier=normal_aide0_namedtuple.StakingBlockNum,
                                                   amount=BaseData.delegate_amount, )['code'] == 0
    if req_param.get("MixAcc"):
        logger.info(f'{f"{normal_aide0}: 赎回自由金额":*^50s}')
        assert normal_aide0.delegate.withdrew_delegate(BaseData.delegate_amount,
                                                       normal_aide1_namedtuple.StakingBlockNum,
                                                       normal_aide1.node_id,
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
    logger.info(f'{f"{normal_aide0}: 锁仓金额委托":*^50s}')
    assert normal_aide0.restricting.restricting(release_address=normal_aide0_namedtuple.del_addr, plans=plan,
                                                private_key=normal_aide0_namedtuple.del_pk)['code'] == 0
    restr_info = normal_aide0.restricting.get_restricting_info(normal_aide0_namedtuple.del_addr)
    logger.info(f'{normal_aide0} 锁仓计划信息: {restr_info}')
    assert normal_aide0.delegate.delegate(amount=BaseData.delegate_amount, balance_type=1,
                                          private_key=normal_aide0_namedtuple.del_pk)['code'] == 0

    if req_param.get("MixAcc"):
        # 在多对多场景下,灵活创建多种账户金额数据 基于ManyAcc=True
        # MixAcc: False 表示节点A 拥有冻结期混合金额 锁仓金额解锁周期更长/节点B 拥有冻结期自由金额,不拥有锁仓金额
        # MixAcc: True  表示节点A/B 都拥有冻结期混合金额 锁仓金额解锁周期更长
        logger.info(f'{f"{normal_aide0}: 锁仓金额委托":*^50s}')
        assert normal_aide0.restricting.restricting(release_address=normal_aide1_namedtuple.del_addr, plans=plan,
                                                    private_key=normal_aide1_namedtuple.del_pk)['code'] == 0
        restr_info = normal_aide0.restricting.get_restricting_info(normal_aide1_namedtuple.del_addr)
        logger.info(f'{normal_aide0} 锁仓计划信息: {restr_info}')
        assert normal_aide0.delegate.delegate(BaseData.delegate_amount, 1, normal_aide1.node_id,
                                              private_key=normal_aide1_namedtuple.del_pk)['code'] == 0

    wait_settlement(normal_aide0)
    logger.info(f'{f"{normal_aide0}: 赎回锁仓金额":*^50s}')
    assert normal_aide0.delegate.withdrew_delegate(private_key=normal_aide0_namedtuple.del_pk,
                                                   staking_block_identifier=normal_aide0_namedtuple.StakingBlockNum,
                                                   amount=BaseData.delegate_amount, )['code'] == 0

    if req_param.get("MixAcc"):
        logger.info(f'{f"{normal_aide1}: 赎回锁仓金额":*^50s}')
        assert normal_aide0.delegate.withdrew_delegate(BaseData.delegate_amount,
                                                       normal_aide1_namedtuple.StakingBlockNum,
                                                       normal_aide1.node_id,
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
    for host in chain.hosts:
        host.supervisor.clean()
    chain.install(genesis_file=new_gen_file)
    time.sleep(5)

    normal_aide0, normal_aide1 = normal_aides[0], normal_aides[1],

    lockup_amount = BaseData.delegate_amount  # platon/10 * 100
    plan = [{'Epoch': 10, 'Amount': lockup_amount}]

    logger.info(f"{normal_aide0}: 创建质押和 混合金额")
    if req_param.get("StaAmt"):  # 为了解决质押最低金额
        normal_aide0_namedtuple = create_sta_del(normal_aide0, plan, mix=True, sta_amt=BaseData.staking_limit,
                                                 reward_per=req_param.get("rewardPer"))
    else:  # 默认为质押 BaseData.staking_limit * 4
        normal_aide0_namedtuple = create_sta_del(normal_aide0, plan, mix=True)

    if req_param.get("ManyAcc"):  # 为了解决多个账户创建一样的数据信息
        logger.info(f"{normal_aide0}: 创建质押和 混合金额")
        if req_param.get("StaAmt"):
            normal_aide1_namedtuple = create_sta_del(normal_aide1, plan, mix=True, sta_amt=BaseData.staking_limit)
        else:
            normal_aide1_namedtuple = create_sta_del(normal_aide1, plan, mix=True)
    else:
        logger.info(f"{normal_aide0}: 创建质押和 自由金额")
        normal_aide1_namedtuple = create_sta_del(normal_aide1, )

    wait_settlement(normal_aide0)
    logger.info(f"{normal_aide0}: 赎回锁仓+自由金额 进入冻结期")
    assert normal_aide0.delegate.withdrew_delegate(private_key=normal_aide0_namedtuple.del_pk,
                                                   staking_block_identifier=normal_aide0_namedtuple.StakingBlockNum,
                                                   amount=BaseData.delegate_amount * 2, )['code'] == 0
    if req_param.get("ManyAcc"):
        logger.info(f"{normal_aide0}: 赎回锁仓+自由金额 进入冻结期")
        assert normal_aide0.delegate.withdrew_delegate(private_key=normal_aide1_namedtuple.del_pk,
                                                       node_id=normal_aide1.node_id,
                                                       staking_block_identifier=normal_aide1_namedtuple.StakingBlockNum,
                                                       amount=BaseData.delegate_amount * 2, )['code'] == 0

    yield normal_aide0, normal_aide1, normal_aide0_namedtuple, normal_aide1_namedtuple


@pytest.fixture()
def many_cycle_restr_redeem_delegate(request, choose_undelegate_freeze_duration, normal_aides):
    """
    创建锁定期 混合金额 锁仓金额和自由金额 多周期的锁仓计划
    """
    req_param = request.param
    chain, new_gen_file = choose_undelegate_freeze_duration
    for host in chain.hosts:
        host.supervisor.clean()
    chain.install(genesis_file=new_gen_file)
    time.sleep(5)

    normal_aide0, normal_aide1 = normal_aides[0], normal_aides[1],

    lockup_amount = BaseData.delegate_amount  # platon/10 * 100
    lock_amt = BaseData.delegate_limit * 10
    assert lock_amt * 10 == lockup_amount
    plan = [{'Epoch': i, 'Amount': lock_amt} for i in range(1, 11)]

    logger.info(f"{normal_aide0}: 创建质押和 混合金额")
    normal_aide0_namedtuple = create_sta_del(normal_aide0, plan, mix=True)
    if req_param.get("ManyAcc"):
        logger.info(f"{normal_aide0}: 创建质押和 混合金额")
        normal_aide1_namedtuple = create_sta_del(normal_aide1, plan, mix=True)
    else:
        logger.info(f"{normal_aide0}: 创建质押和 自由金额")
        normal_aide1_namedtuple = create_sta_del(normal_aide1, )

    wait_settlement(normal_aide0)
    PF.p_get_delegate_info(normal_aide0, normal_aide0_namedtuple.del_addr, normal_aide0_namedtuple)

    logger.info(f"{normal_aide0}: 赎回锁仓+自由金额 进入冻结期")
    assert normal_aide0.delegate.withdrew_delegate(private_key=normal_aide0_namedtuple.del_pk,
                                                   staking_block_identifier=normal_aide0_namedtuple.StakingBlockNum,
                                                   amount=BaseData.delegate_amount * 2, )['code'] == 0
    if req_param.get("ManyAcc"):
        logger.info(f"{normal_aide0}: 赎回锁仓+自由金额 进入冻结期")
        assert normal_aide0.delegate.withdrew_delegate(private_key=normal_aide1_namedtuple.del_pk,
                                                       node_id=normal_aide1.node_id,
                                                       staking_block_identifier=normal_aide1_namedtuple.StakingBlockNum,
                                                       amount=BaseData.delegate_amount * 2, )['code'] == 0

    yield normal_aide0, normal_aide1, normal_aide0_namedtuple, normal_aide1_namedtuple


@pytest.fixture()
def many_cycle_restr_loop_redeem_delegate(choose_undelegate_freeze_duration, normal_aides):
    """
    创建锁定期 混合金额 锁仓金额和自由金额 多周期的锁仓计划并使用锁仓金额嵌套委托多节点
    """
    chain, new_gen_file = choose_undelegate_freeze_duration
    for host in chain.hosts:
        host.supervisor.clean()
    chain.install(genesis_file=new_gen_file)
    time.sleep(5)

    normal_aide0, normal_aide1 = normal_aides[0], normal_aides[1],

    lockup_amount = BaseData.delegate_amount  # platon/10 * 100
    lock_amt = BaseData.delegate_limit * 10
    assert lock_amt * 10 == lockup_amount
    plan = [{'Epoch': i, 'Amount': lock_amt} for i in range(1, 11)]

    logger.info(f"{normal_aide0}: 创建质押和 混合金额")
    normal_aide0_namedtuple = create_sta_del(normal_aide0, plan, mix=True)
    logger.info(f"为其他节点创建质押和委托")
    other_nt_list = [create_sta_del(normal_aides[i], ) for i in range(1, 4)]

    wait_settlement(normal_aide0)
    PF.p_get_delegate_info(normal_aide0, normal_aide0_namedtuple.del_addr, normal_aide0_namedtuple)

    logger.info(f"{normal_aide0}: 赎回锁仓+自由金额 进入冻结期")
    assert normal_aide0.delegate.withdrew_delegate(private_key=normal_aide0_namedtuple.del_pk,
                                                   staking_block_identifier=normal_aide0_namedtuple.StakingBlockNum,
                                                   amount=BaseData.delegate_amount * 2, )['code'] == 0
    yield normal_aide0, normal_aide1, normal_aide0_namedtuple, other_nt_list


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
    logger.info(f'{f"{normal_aide0}: 锁仓金额委托":*^50s}')
    assert normal_aide0.restricting.restricting(release_address=normal_aide0_nt.del_addr, plans=plan,
                                                private_key=normal_aide0_nt.del_pk)['code'] == 0
    assert normal_aide0.delegate.delegate(amount=BaseData.delegate_amount, balance_type=1,
                                          private_key=normal_aide0_nt.del_pk)['code'] == 0

    if req_param.get("wait_settlement"):
        # 使账户委托金额 —> 进入 生效期
        wait_settlement(normal_aide0)

    yield normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt


@pytest.fixture()
def acc_mix_amt_delegate_02(request, create_lock_mix_amt_free_unlock_long):
    """
    使用账户混合金额进行委托
    @param request: wait_settlement字段来控制 True 账户金额委托生效期 False 账户金额委托犹豫期
    @param create_lock_mix_amt_free_unlock_long:
    @return:
    """
    normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt = create_lock_mix_amt_free_unlock_long
    req_param = request.param

    logger.info(f"使用账户自由金额委托: {BaseData.delegate_amount}")
    assert normal_aide0.delegate.delegate(BaseData.delegate_amount, 0,
                                          private_key=normal_aide0_nt.del_pk)['code'] == 0

    logger.info(f"使用账户锁仓金额委托: {BaseData.delegate_amount}")
    lockup_amount = BaseData.delegate_amount  # platon/10 * 100
    plan = [{'Epoch': 10, 'Amount': lockup_amount}]
    logger.info(f'{f"{normal_aide0}: 锁仓金额委托":*^50s}')
    assert normal_aide0.restricting.restricting(release_address=normal_aide0_nt.del_addr, plans=plan,
                                                private_key=normal_aide0_nt.del_pk)['code'] == 0
    assert normal_aide0.delegate.delegate(amount=BaseData.delegate_amount, balance_type=1,
                                          private_key=normal_aide0_nt.del_pk)['code'] == 0

    if req_param.get("wait_settlement"):
        # 使账户委托金额 —> 进入 生效期
        wait_settlement(normal_aide0)

    yield normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt


@pytest.fixture()
def acc_mix_diff_cycle_delegate(request, create_lock_mix_amt_unlock_eq):
    """
    构造账户两种金额 发起委托 在不同周期
    @param request:
        - restr_wait(True): 1.锁仓委托 进入生效期    2.自由金额委托 犹豫期
        - free_wait(True):  1.自由金额委托 进入生效期 2.锁仓委托 犹豫期
        * 若想两种金额类型都在生效期 使用fixture: acc_mix_amt_delegate wait_settlement=True
    @param create_lock_mix_amt_unlock_eq:
    @return:
    """
    normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt = create_lock_mix_amt_unlock_eq
    req_param = request.param

    lockup_amount = BaseData.delegate_amount  # platon/10 * 100
    plan = [{'Epoch': 10, 'Amount': lockup_amount}]

    if req_param.get("restr_wait"):
        logger.info(f'{f"{normal_aide0}: 账户锁仓金额委托":*^50s}')
        assert normal_aide0.restricting.restricting(release_address=normal_aide0_nt.del_addr, plans=plan,
                                                    private_key=normal_aide0_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(amount=BaseData.delegate_amount, balance_type=1,
                                              private_key=normal_aide0_nt.del_pk)['code'] == 0
        wait_settlement(normal_aide0)

    logger.info(f"账户自由金额委托: {BaseData.delegate_amount}")
    assert normal_aide0.delegate.delegate(BaseData.delegate_amount, 0,
                                          private_key=normal_aide0_nt.del_pk)['code'] == 0
    if req_param.get("free_wait"):
        wait_settlement(normal_aide0)
        logger.info(f'{f"{normal_aide0}: 账户锁仓金额委托":*^50s}')
        assert normal_aide0.restricting.restricting(release_address=normal_aide0_nt.del_addr, plans=plan,
                                                    private_key=normal_aide0_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(amount=BaseData.delegate_amount, balance_type=1,
                                              private_key=normal_aide0_nt.del_pk)['code'] == 0
    pass


@pytest.fixture()
def lock_mix_diff_cycle_delegate(create_lock_mix_amt_unlock_eq):
    """
    构造锁定期 锁仓金额委托在生效期 自由金额委托在犹豫期
    @param create_lock_mix_amt_unlock_eq:
    @Desc:
        - 解锁周期相同时会优先使用锁仓金额委托, 1.锁仓金额生效期 2.自由金额犹豫期
        * 若想两种金额类型都在生效期 使用fixture: lock_mix_amt_unlock_eq_delegate wait_settlement=True
    """
    normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt = create_lock_mix_amt_unlock_eq

    logger.info(f'使用锁定期 锁仓金额委托 1000')
    assert normal_aide0.delegate.delegate(BaseData.delegate_amount, 3,
                                          private_key=normal_aide0_nt.del_pk)['code'] == 0
    wait_settlement(normal_aide0)

    logger.info(f"使用锁定期 自由金额委托 1000")
    assert normal_aide0.delegate.delegate(BaseData.delegate_amount, 3,
                                          private_key=normal_aide0_nt.del_pk)['code'] == 0


@pytest.fixture()
def lock_mix_diff_cycle_delegate_free_valid(create_lock_mix_amt_free_unlock_long):
    """
    构造锁定期 锁仓金额委托在犹豫期 自由金额委托在生效期
    @param create_lock_mix_amt_free_unlock_long:
    @Desc:
        - 自由金额解锁周期更长优先使用自由金额, 1.自由金额生效期 2.锁仓金额犹豫期
        * 若想两种金额类型都在生效期 使用fixture: lock_mix_amt_unlock_eq_delegate wait_settlement=True
    """
    normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt = create_lock_mix_amt_free_unlock_long

    logger.info(f'使用锁定期 自由金额委托 1000')
    assert normal_aide0.delegate.delegate(BaseData.delegate_amount, 3,
                                          private_key=normal_aide0_nt.del_pk)['code'] == 0
    wait_settlement(normal_aide0)

    logger.info(f"使用锁定期 锁仓金额委托 1000")
    assert normal_aide0.delegate.delegate(BaseData.delegate_amount, 3,
                                          private_key=normal_aide0_nt.del_pk)['code'] == 0


@pytest.fixture()
def acc_lock_mix_diff_cycle_del(request, create_lock_mix_amt_unlock_eq):
    """
    适用场景:(除 # 锁定期自由金额在生效期的场景 需要使用 acc_lock_mix_diff_cycle_del_free_valid)
    - 自由金额 犹豫期  /  锁仓金额 生效期 (账户)
        - 自由金额 犹豫期 / 锁仓金额 生效期  {"Acc":[restr_wait],"Lock"[restr_wait]}
        # 自由金额 生效期 / 锁仓金额 犹豫期  {"Acc":[restr_wait],"Lock"[free_wait]}
    - 自由金额 生效期  /  锁仓金额 犹豫期 (账户)
        - 自由金额 犹豫期 / 锁仓金额 生效期  {"Acc":[free_wait],"Lock"[restr_wait]}
        # 自由金额 生效期 / 锁仓金额 犹豫期  {"Acc":[free_wait],"Lock"[free_wait]}

    @request.param:
        示例： init_data = {"Acc": {"restr_wait": True}, "Lock": {"restr_wait": True}}
              init_data = {"Lock": {"free_wait": True}, "Acc": {"free_wait": True}}
              setup_data_02 = [{"Acc": {"restr_wait": True}, "Lock": {"free_wait": True}}]
    """
    normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt = create_lock_mix_amt_unlock_eq
    req_param = request.param
    Acc_data = req_param["Acc"]
    Lock_data = req_param["Lock"]

    lockup_amount = BaseData.delegate_amount  # platon/10 * 100
    plan = [{'Epoch': 10, 'Amount': lockup_amount}]

    if Acc_data.get("restr_wait"):
        # 账户锁仓金额委托
        acc_restr_delegate(normal_aide0, normal_aide0_nt, plan)
    # 目前可用 if not Acc_data.get("restr_wait") 代替,没有找到锁仓等待,就去使用自由金额委托等待
    if Acc_data.get("free_wait"):
        # 账户自由金额委托
        acc_free_delegate(normal_aide0, normal_aide0_nt)

    if Lock_data.get("restr_wait"):
        # 锁定期锁仓金额委托
        lock_restr_delegate(normal_aide0, normal_aide0_nt)

    if Lock_data.get("free_wait"):
        # 锁定期自由金额委托 / !!! 有个潜在业务逻辑 即解锁周期一致时会先使用锁仓金额委托
        lock_free_delegate(normal_aide0, normal_aide0_nt)

    wait_settlement(normal_aide0)
    # 等待一个周期后,反向操作一波,如上个周期用锁仓委托即这周期用自由委托
    if Acc_data.get("restr_wait"):
        # 账户自由金额委托
        acc_free_delegate(normal_aide0, normal_aide0_nt)
    if Acc_data.get("free_wait"):
        # 账户锁仓金额委托
        acc_restr_delegate(normal_aide0, normal_aide0_nt, plan)
    if Lock_data.get("restr_wait"):
        # 锁定期自由金额委托
        lock_free_delegate(normal_aide0, normal_aide0_nt)
    if Lock_data.get("free_wait"):
        # 锁定期锁仓金额委托
        lock_restr_delegate(normal_aide0, normal_aide0_nt)
    pass


@pytest.fixture()
def acc_lock_mix_diff_cycle_del_free_valid(request, create_lock_mix_amt_free_unlock_long):
    """
    适用场景:
    - 锁定期自由金额 生效期 / 锁仓金额 犹豫期
        - {"Acc":[restr_wait],"Lock"[free_wait]}
        - {"Acc":[free_wait],"Lock"[free_wait]}
    @request.param:
        示例： init_data = {"Acc": {"restr_wait": True}, "Lock": {"free_wait": True}}
    """
    normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt = create_lock_mix_amt_free_unlock_long
    req_param = request.param
    Acc_data = req_param["Acc"]
    Lock_data = req_param["Lock"]

    lockup_amount = BaseData.delegate_amount  # platon/10 * 100
    plan = [{'Epoch': 10, 'Amount': lockup_amount}]

    if Acc_data.get("restr_wait"):
        # 账户锁仓金额委托
        acc_restr_delegate(normal_aide0, normal_aide0_nt, plan)
    # 目前可用 if not Acc_data.get("restr_wait") 代替,没有找到锁仓等待,就去使用自由金额委托等待
    if Acc_data.get("free_wait"):
        # 账户自由金额委托
        acc_free_delegate(normal_aide0, normal_aide0_nt)

    if Lock_data.get("restr_wait"):
        # 锁定期锁仓金额委托
        lock_restr_delegate(normal_aide0, normal_aide0_nt)

    if Lock_data.get("free_wait"):
        # 锁定期自由金额委托 / !!! 有个潜在业务逻辑 即解锁周期一致时会先使用锁仓金额委托
        lock_free_delegate(normal_aide0, normal_aide0_nt)

    wait_settlement(normal_aide0)
    # 等待一个周期后,反向操作一波,如上个周期用锁仓委托即这周期用自由委托
    if Acc_data.get("restr_wait"):
        # 账户自由金额委托
        acc_free_delegate(normal_aide0, normal_aide0_nt)
    if Acc_data.get("free_wait"):
        # 账户锁仓金额委托
        acc_restr_delegate(normal_aide0, normal_aide0_nt, plan)
    if Lock_data.get("restr_wait"):
        # 锁定期自由金额委托
        lock_free_delegate(normal_aide0, normal_aide0_nt)
    if Lock_data.get("free_wait"):
        # 锁定期锁仓金额委托
        lock_restr_delegate(normal_aide0, normal_aide0_nt)
    pass


def acc_restr_delegate(normal_aide0, normal_aide0_nt, plan):
    logger.info(f'{f"{normal_aide0}: 账户锁仓金额委托":*^50s}')
    assert normal_aide0.restricting.restricting(release_address=normal_aide0_nt.del_addr, plans=plan,
                                                private_key=normal_aide0_nt.del_pk)['code'] == 0
    assert normal_aide0.delegate.delegate(amount=BaseData.delegate_amount, balance_type=1,
                                          private_key=normal_aide0_nt.del_pk)['code'] == 0


def acc_free_delegate(normal_aide0, normal_aide0_nt):
    logger.info(f"账户自由金额委托: {BaseData.delegate_amount}")
    assert normal_aide0.delegate.delegate(BaseData.delegate_amount, 0,
                                          private_key=normal_aide0_nt.del_pk)['code'] == 0


def lock_restr_delegate(normal_aide0, normal_aide0_nt):
    """!!! 强调,这里委托金额 锁定期 锁仓1000 (之前是锁仓1000 + 自由金额100)"""
    logger.info(f"使用锁定期 锁仓金额委托 delegate_limit * 100")
    assert normal_aide0.delegate.delegate(BaseData.delegate_amount, 3,
                                          private_key=normal_aide0_nt.del_pk)['code'] == 0


def lock_free_delegate(normal_aide0, normal_aide0_nt):
    """!!! 强调,这里委托金额 锁定期 自由金额1000 (之前是委托了800 还剩200在锁定计划中)"""
    logger.info(f"使用锁定期 自由金额委托 delegate_limit * 100")
    assert normal_aide0.delegate.delegate(BaseData.delegate_amount, 3,
                                          private_key=normal_aide0_nt.del_pk)['code'] == 0


@pytest.fixture()
def loop_delegate(choose_undelegate_freeze_duration, normal_aides):
    """
    创建锁定期/账户 混合金额 多周期的锁仓计划并使用锁仓金额嵌套委托多节点
    """
    chain, new_gen_file = choose_undelegate_freeze_duration
    for host in chain.hosts:
        host.supervisor.clean()
    chain.install(genesis_file=new_gen_file)
    time.sleep(5)

    normal_aide0, normal_aide1 = normal_aides[0], normal_aides[1],

    lockup_amount = BaseData.delegate_amount  # platon/10 * 100
    lock_amt = BaseData.delegate_limit * 10
    assert lock_amt * 10 == lockup_amount
    plan = [{'Epoch': i, 'Amount': lock_amt} for i in range(1, 11)]

    logger.info(f"{normal_aide0}: 创建质押和 混合金额")
    normal_aide0_namedtuple = create_sta_del(normal_aide0, plan, mix=True)
    logger.info(f"为其他节点创建质押和委托")
    other_nt_list = [create_sta_del(normal_aides[i], ) for i in range(1, 4)]
    init_restr_info = PF.p_get_restricting_info(normal_aide0, normal_aide0_namedtuple)

    wait_settlement(normal_aide0)

    logger.info(f"{normal_aide0}: 赎回锁仓+自由金额 进入冻结期")
    assert normal_aide0.delegate.withdrew_delegate(private_key=normal_aide0_namedtuple.del_pk,
                                                   staking_block_identifier=normal_aide0_namedtuple.StakingBlockNum,
                                                   amount=BaseData.delegate_amount * 2, )['code'] == 0
    yield normal_aide0, normal_aide0_namedtuple, other_nt_list, plan, init_restr_info
