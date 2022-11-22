import pytest
from loguru import logger
from platon_env.genesis import Genesis
from platon_env.utils import join_path

from setting.account import CDF_ACCOUNT
from setting.setting import GENESIS_FILE, BASE_DIR
from lib.utils import new_account


@pytest.mark.P3
@pytest.mark.parametrize('value, code', [('0', 3), ('3', 3), ('1', 0), ('2', 302034)])
def test_static_param_limit(init_aide, value, code):
    """
    1. 验证解委托冻结周期的静态参数限制
    """
    rec = init_aide.govern.param_proposal('staking', 'unDelegateFreezeDuration', value,
                                          private_key=CDF_ACCOUNT.key
                                          )
    assert rec.code == code, 'code error'


# @pytest.mark.P1
# @pytest.mark.parametrize('value', ['3'])
# def test_dynamic_param_limit(chain, init_aides, init_aide, normal_aide, economic, recover, value):
#     """
#     """
#     # 修改解质押冻结周期，并使其生效
#     rec = init_aide.govern.param_proposal('staking', 'unStakeFreezeDuration', value,
#                                           private_key=CDF_ACCOUNT.key
#                                           )
#     assert rec.code == 0
#     proposal = init_aide.govern.get_active_proposal(3)
#     assert proposal
#     for aide in init_aides:
#         rec = aide.govern.vote(proposal.ProposalID, 1,
#                                private_key=CDF_ACCOUNT.key
#                                )
#         assert rec.code == 0
#     # 检查修改生效前后，治理参数列表中的解委托冻结周期的的依赖介绍
#     params = init_aide.govern.govern_param_list()
#     print(params)
#     init_aide.wait_block(proposal.EndVotingBlock + 1)
#     params = init_aide.govern.govern_param_list()
#     print(params)
    # 修改解委托冻结周期，并使其生效
    # rec = init_aide.govern.param_proposal('staking', 'unDelegateFreezeDuration', value)
    # assert rec.code == 0
    # proposal = init_aide.govern.get_active_proposal(3)
    # assert proposal
    # for aide in init_aides:
    #     rec = aide.govern.vote(proposal.ProposalID, 1,
    #                            private_key=CDF_ACCOUNT.key
    #                            )
    #     assert rec.code == 0
    # init_aide.wait_block(proposal.EndVotingBlock + 1)
    # # 委托并解委托，检查解委托金额的冻结期
    # rec = normal_aide.staking.create_staking()
    # assert rec.code == 0
    # del_account = new_account(normal_aide, economic.delegate_limit * 5)
    # rec = normal_aide.delegate.delegate(economic.delegate_limit * 3, balance_type=0,
    #                                     private_key=del_account.key
    #                                     )
    # assert rec.code == 0
    # normal_aide.wait_period('epoch')
    # # period, _, _ = normal_aide.calculator.get_period_info()
    # rec = normal_aide.delegate.withdrew_delegate(economic.delegate_limit,
    #                                              private_key=del_account.key
    #                                              )
    # assert rec.code == 0
    # lock_info = normal_aide.delegate.get_delegate_lock_info(del_account.address)
    # logger.info(f'1th lock info: {lock_info}')
    # assert len(lock_info.Locks) == 1
    # assert lock_info.Locks[0].Epoch == period + 4 - 1
    # assert lock_info.Locks[0].Released == economic.delegate_limit


@pytest.mark.P1
@pytest.mark.parametrize('value', ['1', '5'])
def test_param_change(chain, init_aides, normal_aide, economic, recover, value):
    """
    @test:
    - 1. 验证参数修改，影响解委托冻结期
    - 2. 验证参数修改，不影响已有的解委托冻结期
    - 3. 验证参数修改打乱解冻顺序后，冻结金数据正确（先解委托的冻结期更长，后解委托的冻结期更短）
    @step:
    - 1. 质押节点并委托，两者进入生效期
    - 2. 解委托部分金额，委托金冻结期为当前参数值  # 注意要比提案生效期长
    - 3. 修改参数，链上改变，委托金冻结期不受影响
    - 4. 解委托剩余金额，委托金冻结期为修改后的参数值
    - 5. 两次冻结信息正确
    """

    # init: 修改创世文件参数
    genesis = Genesis(GENESIS_FILE)
    genesis.data['economicModel']['staking']['unStakeFreezeDuration'] = 5
    genesis.data['economicModel']['staking']['unDelegateFreezeDuration'] = 4
    genesis_tmp = join_path(BASE_DIR, 'env-files/tmp/genesis.json')
    genesis.save_as(genesis_tmp)
    chain.install(genesis_file=genesis_tmp)

    # step1: 质押节点并委托，两者进入生效期
    rec = normal_aide.staking.create_staking()
    assert rec.code == 0
    del_account = new_account(normal_aide, economic.delegate_limit * 5)
    rec = normal_aide.delegate.delegate(economic.delegate_limit * 3, balance_type=0,
                                        private_key=del_account.key
                                        )
    assert rec.code == 0
    normal_aide.wait_period('epoch')

    # step2: 解委托部分金额，委托金冻结期为当前参数值  # 注意要比提案生效期长
    period, _, _ = normal_aide.calculator.get_period_info()
    rec = normal_aide.delegate.withdrew_delegate(economic.delegate_limit,
                                                 private_key=del_account.key
                                                 )
    assert rec.code == 0
    lock_info = normal_aide.delegate.get_delegate_lock_info(del_account.address)
    logger.info(f'1th lock info: {lock_info}')
    assert len(lock_info.Locks) == 1
    assert lock_info.Locks[0].Epoch == period + 4 - 1
    assert lock_info.Locks[0].Released == economic.delegate_limit

    # step3: 修改参数，链上改变，委托金冻结期不受影响
    rec = normal_aide.govern.param_proposal('staking', 'unDelegateFreezeDuration', value)
    assert rec.code == 0
    proposal = normal_aide.govern.get_active_proposal(3)
    assert proposal
    for aide in init_aides:
        rec = aide.govern.vote(proposal.ProposalID, 1,
                               private_key=CDF_ACCOUNT.key
                               )
        assert rec.code == 0
    # todo: 增加提案生效前后,参数列表的检查
    normal_aide.wait_block(proposal.EndVotingBlock + 1)  # 参数提案：生效块高=结束投票块高+1
    real_value = normal_aide.govern.get_govern_param('staking', 'unDelegateFreezeDuration')
    assert real_value == value
    lock_info = normal_aide.delegate.get_delegate_lock_info(del_account.address)
    logger.info(f'1th lock info (after change): {lock_info}')
    assert len(lock_info.Locks) == 1
    assert lock_info.Locks[0].Epoch == period + 4 - 1
    assert lock_info.Locks[0].Released == economic.delegate_limit

    # step4: 解委托剩余金额，委托金冻结期为修改后的参数值
    # step5: 两次冻结信息正确
    rec = normal_aide.delegate.withdrew_delegate(economic.delegate_limit * 2,
                                                 private_key=del_account.key
                                                 )
    assert rec.code == 0
    period, _, _ = normal_aide.calculator.get_period_info()
    lock_info = normal_aide.delegate.get_delegate_lock_info(del_account.address)
    logger.info(f'2th lock info: {lock_info}')
    assert len(lock_info.Locks) == 2
    assert lock_info.Locks[1].Epoch == period + int(value) - 1
    assert lock_info.Locks[1].Released == economic.delegate_limit * 2
