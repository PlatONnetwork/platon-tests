"""
@Author  :  Jw
@Contact :  libai7236@gmail.com
@Time    :  2022/8/23 11:38
@Version :  platon-1.3.0
@Desc    :  委托锁定
"""
import inspect
import time
from decimal import Decimal

import pytest
from loguru import logger
from platon._utils.error_code import ERROR_CODE

from lib.assertion import Assertion
from lib.basic_data import BaseData as BD
from lib.utils import wait_settlement, wait_consensus
from lib.utils import get_pledge_list, new_account, PrintInfo as PF
from tests.ppos.conftest import create_sta_del_account, create_sta_del


# logger.add("logs/case_{time}.log", rotation="500MB")


def redeem_del_wait_unlock_diff_balance_restr(aide, aide_nt, wait_num=2, diff_restr=False):
    """
    等待解锁期并领取 / 等待2个结算周期
    @param aide: 发起查询的aide对象
    @param aide_nt: aide_nt.del_addr委托账户地址 aide_nt.del_pk委托账户私钥
    @param wait_num: 等待周期
    @param diff_restr: 领取锁仓金额 前后锁仓计划对比
    @return: 解锁期账户余额前后数据
    """
    acc_amt_before = aide.platon.get_balance(aide_nt.del_addr)
    logger.info(f"redeem_delegate_before_balance: {acc_amt_before}")

    if diff_restr:
        restr_info_before = PF.p_get_restricting_info(aide, aide_nt)
        logger.info(f"redeem_delegate_restr_info_before: {restr_info_before}")

    if wait_num == 1:
        wait_settlement(aide)
    elif wait_num == 0:
        pass
    else:
        wait_settlement(aide, wait_num - 1)
    assert aide.delegate.redeem_delegate(private_key=aide_nt.del_pk)['code'] == 0
    red_acc_amt = aide.platon.get_balance(aide_nt.del_addr)
    logger.info(f"redeem_delegate_balance: {red_acc_amt}")

    if diff_restr:
        restr_info_later = PF.p_get_restricting_info(aide, aide_nt)
        logger.info(f"redeem_delegate_restr_info_later: {restr_info_later}")
        return acc_amt_before, red_acc_amt, restr_info_before, restr_info_later
    return acc_amt_before, red_acc_amt


def withdrew_del_diff_balance_restr(aide, aide_nt, withdrew_del_amt, diff_restr=False):
    """
    赎回委托 前后账户余额信息 和 锁仓计划信息
    @param aide:
    @param aide_nt: 查询账户地址
    @param withdrew_del_amt: 赎回委托金额
    @param diff_restr: False 只对比账户余额 , True 对比锁仓
    @return:
    """
    restr_info_before, restr_info_later = None, None

    amt_before = aide.platon.get_balance(aide_nt.del_addr)
    logger.info(f"withdrew_delegate_before_balance: {amt_before}")
    if diff_restr:
        restr_info_before = PF.p_get_restricting_info(aide, aide_nt)
        logger.info(f"withdrew_delegate_restr_info_before: {restr_info_before}")

    assert aide.delegate.withdrew_delegate(withdrew_del_amt, private_key=aide_nt.del_pk)['code'] == 0

    if diff_restr:
        restr_info_later = PF.p_get_restricting_info(aide, aide_nt)
        logger.info(f"withdrew_delegate_restr_info_later: {restr_info_later}")

    amt_later = aide.platon.get_balance(aide_nt.del_addr)
    logger.info(f"withdrew_delegate_later_balance: {amt_later}")
    return amt_before, amt_later, restr_info_before, restr_info_later


def wait_consensus_assert_stop_node_status(run_aide, stop_aide, del_pk, wait_num=4):
    punishment_consensus_num = 0
    for i in range(wait_num):
        wait_consensus(run_aide)
        candidate_info = PF.p_get_candidate_info(run_aide, query_aide=stop_aide)
        if candidate_info.Status == 0:
            logger.info(f"已等待{i + 1}共识轮: -> 节点状态正常进行委托")
            assert run_aide.delegate.delegate(BD.delegate_limit, 3, stop_aide.node.node_id,
                                              private_key=del_pk.del_pk)['code'] == 0
        elif candidate_info.Status == 3 or 7:
            logger.info(f"已等待{i + 1}共识轮: -> 节点状态异常(节点零出块需要锁定但无需解除质押) 进行委托")
            res = run_aide.delegate.delegate(BD.delegate_limit, 3, stop_aide.node.node_id,
                                             private_key=del_pk.del_pk)
            assert res['message'] == ERROR_CODE[301103]
            punishment_consensus_num = i + 1
            break
        else:
            continue
    return punishment_consensus_num


def test_ghost_bug_001(normal_aide):
    """赎回质押后再次进行质押"""
    sta_addr, sta_pk = new_account(normal_aide, BD.staking_limit * 5)
    assert normal_aide.staking.create_staking(amount=BD.staking_limit * 2, benefit_address=sta_addr,
                                              private_key=sta_pk)['code'] == 0
    wait_settlement(normal_aide)
    logger.info(f"1: {get_pledge_list(normal_aide.staking.get_validator_list)}")
    logger.info(f"2: {get_pledge_list(normal_aide.staking.get_verifier_list)}")
    logger.info(f"3: {get_pledge_list(normal_aide.staking.get_candidate_list)}")

    assert normal_aide.staking.withdrew_staking(private_key=sta_pk)['code'] == 0

    assert PF.p_get_candidate_info(normal_aide, normal_aide).Status == 33

    wait_settlement(normal_aide, 2)

    assert PF.p_get_candidate_info(normal_aide, normal_aide) is None
    logger.info(f"1: {get_pledge_list(normal_aide.staking.get_validator_list)}")
    logger.info(f"2: {get_pledge_list(normal_aide.staking.get_verifier_list)}")
    logger.info(f"3: {get_pledge_list(normal_aide.staking.get_candidate_list)}")
    # 幽灵bug 测试过程中有次质押数据返回失败,但是 get_candidate_list 有节点信息
    res = normal_aide.staking.create_staking(amount=BD.staking_limit * 2, benefit_address=sta_addr,
                                             private_key=sta_pk)
    logger.info(f"再次质押返回数据: {res}")

    logger.info(f"1: {get_pledge_list(normal_aide.staking.get_validator_list)}")
    logger.info(f"2: {get_pledge_list(normal_aide.staking.get_verifier_list)}")
    logger.info(f"3: {get_pledge_list(normal_aide.staking.get_candidate_list)}")
    pass


@pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
@pytest.mark.parametrize('create_lock_free_amt', [{"ManyAcc": True}], indirect=True)
def test_withdrew_staking(create_lock_free_amt):
    """测试主动撤销质押 并 零出块"""
    normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt, _ = create_lock_free_amt
    assert normal_aide0.staking.withdrew_staking(node_id=normal_aide0_nt.node_id,
                                                 private_key=normal_aide0_nt.sta_pk)['code'] == 0
    candidate_info = PF.p_get_candidate_info(normal_aide1, query_aide=normal_aide0)
    assert candidate_info.Status == 33
    normal_aide0.node.stop()

    punishment_consensus_num = wait_consensus_assert_stop_node_status(normal_aide1, normal_aide0, normal_aide0_nt)
    logger.info(f"stop_node 在第{punishment_consensus_num}个共识轮被惩罚")
    if punishment_consensus_num == 4:  # 第4个共识轮被惩罚,表示上一个结算周期已过,需在等待一个结算周期
        wait_settlement(normal_aide1)
    else:
        wait_settlement(normal_aide1, 1)
    normal_aide0.node.start()
    candidate_info = PF.p_get_candidate_info(normal_aide1, query_aide=normal_aide0)
    assert candidate_info.Status == 35


class TestDelegateLockOneAccToManyNode:
    """ 测试单账户-多节点场景 """

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
    @pytest.mark.parametrize('create_lock_free_amt', [{"ManyAcc": False}], indirect=True)
    def test_lock_free_amt(self, create_lock_free_amt):
        """
        测试 锁定期 自由金额 委托多节点
        @param create_lock_free_amt:
        @Desc:
            -委托 A、B 节点 / limit - 1 -> fail
            -委托 A、B 节点 / limit
            -委托 A、B 节点 / limit * 5
            -委托 A、B 节点 / limit * 110 -> fail
            -委托 A(剩余金额/2) -> pass / B(剩余金额/2)+von_limit -> fail
            -查询锁定期 自由余额 == del_amt3(剩余金额/2)
            -各节点委托信息
            -委托账户领取解锁期金额
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt, _ = create_lock_free_amt
        PF.p_get_delegate_lock_info(normal_aide0, normal_aide0_nt)

        logger.info("-委托 A、B 节点 / limit - 1 -> fail")
        del_amt0 = BD.delegate_limit - 1
        assert normal_aide0.delegate.delegate(del_amt0, 3,
                                              private_key=normal_aide0_nt.del_pk)['message'] == ERROR_CODE[301105]
        assert normal_aide0.delegate.delegate(del_amt0, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide0_nt.del_pk)['message'] == ERROR_CODE[301105]

        logger.info("case-委托 A、B 节点 / limit")
        assert normal_aide0.delegate.delegate(private_key=normal_aide0_nt.del_pk, balance_type=3)['code'] == 0
        assert normal_aide0.delegate.delegate(private_key=normal_aide0_nt.del_pk, balance_type=3,
                                              node_id=normal_aide1.node.node_id)['code'] == 0

        logger.info("-委托 A、B 节点 / limit * 5")
        del_amt1 = BD.delegate_limit * 5
        assert normal_aide0.delegate.delegate(del_amt1, 3, private_key=normal_aide0_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(del_amt1, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide0_nt.del_pk, )['code'] == 0

        logger.info("-委托 A、B 节点 / limit * 110 -> fail")
        del_amt2 = BD.delegate_limit * 110
        res = normal_aide0.delegate.delegate(del_amt2, 3, private_key=normal_aide0_nt.del_pk)
        assert ERROR_CODE[301207] == res['message']
        res = normal_aide0.delegate.delegate(del_amt2, 3, normal_aide1.node.node_id, private_key=normal_aide0_nt.del_pk)
        assert ERROR_CODE[301207] == res['message']

        logger.info("-委托 A(剩余金额/2) -> pass / B(剩余金额/2)+von_limit -> fail")
        residue_amt = BD.delegate_amount - (del_amt1 * 2) - (BD.delegate_limit * 2)
        del_amt3 = int(Decimal(residue_amt) / Decimal(2))
        assert normal_aide0.delegate.delegate(del_amt3, 3, private_key=normal_aide0_nt.del_pk)['code'] == 0
        res = normal_aide0.delegate.delegate(del_amt3 + BD.von_limit, 3, normal_aide1.node.node_id,
                                             private_key=normal_aide0_nt.del_pk)
        assert ERROR_CODE[301207] == res['message']

        logger.info("-查询锁定期 自由余额 == del_amt3(剩余金额/2)")
        lock_info = PF.p_get_delegate_lock_info(normal_aide0, normal_aide0_nt)
        assert lock_info['Locks'][0]['Released'] == del_amt3

        logger.info("-各节点委托信息")
        del_info_0 = normal_aide0.delegate.get_delegate_info(normal_aide0_nt.del_addr,
                                                             staking_block_identifier=normal_aide0_nt.StakingBlockNum)
        assert del_info_0.LockReleasedHes == del_amt3 + del_amt1 + BD.delegate_limit
        del_info_1 = normal_aide0.delegate.get_delegate_info(normal_aide0_nt.del_addr, normal_aide1.node.node_id,
                                                             staking_block_identifier=normal_aide1_nt.StakingBlockNum)
        assert del_info_1.LockReleasedHes == del_amt1 + BD.delegate_limit

        logger.info("-委托账户领取解锁期金额")
        acc_amt_bef, red_acc_amt = redeem_del_wait_unlock_diff_balance_restr(normal_aide0, normal_aide0_nt)
        assert abs(red_acc_amt - acc_amt_bef - del_amt3) < BD.von_limit
        logger.info("-验证锁定期数据")
        Assertion.del_lock_info_zero_money(normal_aide0, normal_aide0_nt)

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
    @pytest.mark.parametrize('create_lock_restr_amt', [{"ManyAcc": False}], indirect=True)
    def test_lock_restr_amt(self, create_lock_restr_amt):
        """
        测试 锁定期 锁仓金额 委托多节点
        @param create_lock_restr_amt:
        @Desc:
            -委托 A、B 节点 / limit
            -委托 A、B 节点 / limit * 5
            -委托 A、B 节点 / limit * 110 -> fail
            -委托 A(剩余金额/2) -> pass / B(剩余金额/2)+von_limit -> fail
            -查询锁定期 锁仓金额 RestrictingPlan == del_amt3(剩余金额/2)
            -各节点委托信息 犹豫期 LockRestrictingPlanHes
            -委托账户领取解锁期金额 - 锁仓计划周期为10 暂未释放/余额不变
            -查锁仓计划信息 验证质押金额等字段
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt, _ = create_lock_restr_amt
        PF.p_get_delegate_lock_info(normal_aide0, normal_aide0_nt)

        logger.info("-委托 A、B 节点 / limit")
        assert normal_aide0.delegate.delegate(private_key=normal_aide0_nt.del_pk, balance_type=3)['code'] == 0
        assert normal_aide0.delegate.delegate(private_key=normal_aide0_nt.del_pk, balance_type=3,
                                              node_id=normal_aide1.node.node_id)['code'] == 0

        logger.info("-委托 A、B 节点 / limit * 5")
        del_amt1 = BD.delegate_limit * 5
        assert normal_aide0.delegate.delegate(del_amt1, 3, private_key=normal_aide0_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(del_amt1, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide0_nt.del_pk, )['code'] == 0

        logger.info("-委托 A、B 节点 / limit * 110 -> fail")
        del_amt2 = BD.delegate_limit * 110
        res = normal_aide0.delegate.delegate(del_amt2, 3, private_key=normal_aide0_nt.del_pk)
        assert ERROR_CODE[301207] == res['message']
        res = normal_aide0.delegate.delegate(del_amt2, 3, normal_aide1.node.node_id, private_key=normal_aide0_nt.del_pk)
        assert ERROR_CODE[301207] == res['message']

        logger.info("-委托 A(剩余金额/2) -> pass / B(剩余金额/2)+von_limit -> fail")
        residue_amt = BD.delegate_amount - (del_amt1 * 2) - (BD.delegate_limit * 2)
        del_amt3 = int(Decimal(residue_amt) / Decimal(2))
        assert normal_aide0.delegate.delegate(del_amt3, 3, private_key=normal_aide0_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(del_amt3 + BD.von_limit, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide0_nt.del_pk)['message'] == ERROR_CODE[301207]

        logger.info("-查询锁定期 锁仓金额 RestrictingPlan == del_amt3(剩余金额/2)")
        lock_info = PF.p_get_delegate_lock_info(normal_aide0, normal_aide0_nt)
        assert lock_info['Locks'][0]['RestrictingPlan'] == del_amt3

        logger.info("-各节点委托信息 犹豫期 LockRestrictingPlanHes")
        del_info_0 = normal_aide0.delegate.get_delegate_info(normal_aide0_nt.del_addr,
                                                             staking_block_identifier=normal_aide0_nt.StakingBlockNum)
        assert del_info_0.LockRestrictingPlanHes == del_amt3 + del_amt1 + BD.delegate_limit
        del_info_1 = normal_aide0.delegate.get_delegate_info(normal_aide0_nt.del_addr, normal_aide1.node.node_id,
                                                             staking_block_identifier=normal_aide1_nt.StakingBlockNum)
        assert del_info_1.LockRestrictingPlanHes == del_amt1 + BD.delegate_limit

        logger.info("-委托账户领取解锁期金额 - 锁仓计划周期为10 暂未释放/余额不变")
        acc_amt_bef, red_acc_amt = redeem_del_wait_unlock_diff_balance_restr(normal_aide0, normal_aide0_nt)
        assert abs(acc_amt_bef - red_acc_amt) < BD.von_limit

        logger.info("-查锁仓计划信息 验证质押金额等字段")
        restr_info = PF.p_get_restricting_info(normal_aide0, normal_aide0_nt)
        assert restr_info["Pledge"] == del_amt3 + (del_amt1 * 2) + (BD.delegate_limit * 2)
        assert restr_info["debt"] == 0

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
    @pytest.mark.parametrize('create_lock_restr_amt', [{"ManyAcc": False, "MixAcc": False}], indirect=True)
    def test_lock_mix_amt_free_unlock_long(self, create_lock_mix_amt_free_unlock_long):
        """
        锁定期混合金额 自由金额解锁周期更长
        @param create_lock_mix_amt_free_unlock_long:
        @Desc:
            -委托 A、B 节点 / limit * 210 / 超过锁定期总金额 -> fail
            -委托 A、B 节点 / limit / 使用自由金额委托
            -委托 A、B 节点 / 自由金额委托部分和超出(即扣锁仓), 委托锁仓金额部分和超出
            -各节点委托信息
            -锁仓计划解锁未释放 / 领取解锁的锁仓金额
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt = create_lock_mix_amt_free_unlock_long
        PF.p_get_delegate_lock_info(normal_aide0, normal_aide0_nt)

        logger.info("-委托 A、B 节点 / limit * 210 / 超过锁定期总金额 -> fail")
        assert normal_aide0.delegate.delegate(BD.delegate_limit * 210, 3,
                                              private_key=normal_aide0_nt.del_pk)['message'] == ERROR_CODE[301207]
        assert normal_aide0.delegate.delegate(BD.delegate_limit * 210, 3, node_id=normal_aide1.node.node_id,
                                              private_key=normal_aide0_nt.del_pk)['message'] == ERROR_CODE[301207]

        logger.info("-委托 A、B 节点 / limit / 使用自由金额委托")
        assert normal_aide0.delegate.delegate(private_key=normal_aide0_nt.del_pk, balance_type=3)['code'] == 0
        assert normal_aide0.delegate.delegate(private_key=normal_aide0_nt.del_pk, balance_type=3,
                                              node_id=normal_aide1.node.node_id)['code'] == 0
        logger.info("查锁定期信息并验证 - lock_released - 980")
        lock_released = BD.delegate_amount - (BD.delegate_limit * 2)
        expect_data = {(3, 0, BD.delegate_amount), (4, lock_released, 0)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data)

        logger.info("-委托 A、B 节点 / 自由金额委托部分和超出(即扣锁仓), 委托锁仓金额部分和超出")
        logger.info("-剩余自由金额980 - 100 - 900 / 锁仓剩余980 - 500 - 500(fail)")
        del_amt1 = BD.delegate_limit * 10
        assert normal_aide0.delegate.delegate(del_amt1, 3, private_key=normal_aide0_nt.del_pk)['code'] == 0
        expect_data = {(3, 0, BD.delegate_amount), (4, lock_released - del_amt1, 0)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data)

        del_amt2 = BD.delegate_limit * 90
        assert normal_aide0.delegate.delegate(del_amt2, 3, private_key=normal_aide0_nt.del_pk)['code'] == 0
        lock_restricting_plan = BD.delegate_amount - abs(lock_released - del_amt1 - del_amt2)
        expect_data = {(3, 0, lock_restricting_plan), }
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data)

        del_amt3 = BD.delegate_limit * 50
        assert normal_aide0.delegate.delegate(del_amt3, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide0_nt.del_pk)['code'] == 0
        expect_data = {(3, 0, lock_restricting_plan - del_amt3), }
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data)

        assert normal_aide0.delegate.delegate(del_amt3, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide0_nt.del_pk)['message'] == ERROR_CODE[301207]
        logger.info("-验证各节点委托信息")
        del_info_0 = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        # 锁定期自由金额 = lock_released 全部自由金额 + delegate_limit
        assert del_info_0.LockReleasedHes == lock_released + BD.delegate_limit
        assert del_info_0.LockRestrictingPlanHes == abs(lock_released - BD.delegate_amount)

        del_info_1 = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide1_nt)
        assert del_info_1.LockReleasedHes == BD.delegate_limit
        assert del_info_1.LockRestrictingPlanHes == del_amt3

        wait_settlement(normal_aide0)
        logger.info(f'{"-锁定期中锁仓解锁/锁仓计划未释放":*^50s}')
        RestrictingPlan = BD.delegate_amount * 2 - (del_amt3 + del_amt2 + del_amt1 + BD.delegate_limit * 2)
        expect_data = {"Released": 0, "RestrictingPlan": RestrictingPlan}
        Assertion.del_lock_release_money(normal_aide0, normal_aide0_nt, expect_data)

        logger.info(f'{"-领取解锁的锁仓金额":*^50s}')
        assert normal_aide0.delegate.redeem_delegate(private_key=normal_aide0_nt.del_pk)['code'] == 0
        restr_info = PF.p_get_restricting_info(normal_aide0, normal_aide0_nt)
        assert restr_info['Pledge'] == BD.delegate_amount - RestrictingPlan
        assert restr_info['balance'] == BD.delegate_amount and restr_info['debt'] == 0

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
    @pytest.mark.parametrize('create_lock_free_amt', [{"ManyAcc": False}], indirect=True)
    def test_lock_mix_amt_restr_unlock_long(self, create_lock_mix_amt_restr_unlock_long):
        """
        锁定期混合金额 锁仓金额解锁周期更长
        @param create_lock_mix_amt_restr_unlock_long:
        @Desc:
            -委托 A、B 节点 / limit * 210 / 超过锁定期总金额 -> fail
            -委托 A、B 节点 / limit / 使用锁仓金额委托
            -委托 A、B 节点 / 锁仓金额委托部分和超出(即扣自由金额), 委托自由金额部分和超出
            -验证各节点委托信息
            -等待锁定期中自由金额解锁并领取
            -锁仓计划信息不变,锁定期锁仓金额已全部再次委托
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt = create_lock_mix_amt_restr_unlock_long
        PF.p_get_delegate_lock_info(normal_aide0, normal_aide0_nt)

        logger.info("-委托 A、B 节点 / limit * 210 / 超过锁定期总金额 -> fail")
        assert normal_aide0.delegate.delegate(BD.delegate_limit * 210, 3,
                                              private_key=normal_aide0_nt.del_pk)['message'] == ERROR_CODE[301207]
        assert normal_aide0.delegate.delegate(BD.delegate_limit * 210, 3, node_id=normal_aide1.node.node_id,
                                              private_key=normal_aide0_nt.del_pk)['message'] == ERROR_CODE[301207]

        logger.info("-委托 A、B 节点 / limit / 使用锁仓金额委托")
        assert normal_aide0.delegate.delegate(balance_type=3, private_key=normal_aide0_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(balance_type=3, node_id=normal_aide1.node.node_id,
                                              private_key=normal_aide0_nt.del_pk, )['code'] == 0
        logger.info("查锁定期信息并验证")
        lock_restricting_plan = BD.delegate_amount - (BD.delegate_limit * 2)
        expect_data = {(3, BD.delegate_amount, 0), (4, 0, lock_restricting_plan)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data)

        logger.info("-委托 A、B 节点 / 锁仓金额委托部分和超出(即扣自由金额), 委托自由金额部分和超出")
        logger.info("-剩余锁仓金额980 - 100 - 900 / 剩余自由金额980 - 500 - 500(fail)")
        del_amt1 = BD.delegate_limit * 10
        assert normal_aide0.delegate.delegate(del_amt1, 3, private_key=normal_aide0_nt.del_pk)['code'] == 0
        expect_data = {(3, BD.delegate_amount, 0), (4, 0, lock_restricting_plan - del_amt1), }
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data)

        del_amt2 = BD.delegate_limit * 90
        assert normal_aide0.delegate.delegate(del_amt2, 3, private_key=normal_aide0_nt.del_pk)['code'] == 0
        lock_released = BD.delegate_amount - abs(lock_restricting_plan - del_amt1 - del_amt2)
        expect_data = {(3, lock_released, 0), }
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data)

        del_amt3 = BD.delegate_limit * 50
        assert normal_aide0.delegate.delegate(del_amt3, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide0_nt.del_pk)['code'] == 0
        expect_data = {(3, lock_released - del_amt3, 0), }
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data)

        assert normal_aide0.delegate.delegate(del_amt3, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide0_nt.del_pk)['message'] == ERROR_CODE[301207]
        logger.info("-验证各节点委托信息")
        del_info_0 = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        assert del_info_0.LockReleasedHes == abs(lock_restricting_plan - BD.delegate_amount)
        assert del_info_0.LockRestrictingPlanHes == lock_restricting_plan + BD.delegate_limit

        del_info_1 = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide1_nt)
        assert del_info_1.LockReleasedHes == del_amt3
        assert del_info_1.LockRestrictingPlanHes == BD.delegate_limit

        logger.info(f'{"-等待锁定期中自由金额解锁并领取":*^50s}')
        Released = BD.delegate_amount * 2 - (del_amt3 + del_amt2 + del_amt1 + BD.delegate_limit * 2)
        acc_amt_bef, red_acc_amt = redeem_del_wait_unlock_diff_balance_restr(normal_aide0, normal_aide0_nt, wait_num=1)
        assert abs(red_acc_amt - acc_amt_bef - Released) < BD.von_limit

        logger.info(f'{"-锁仓计划信息不变,锁定期锁仓金额已全部再次委托":*^50s}')
        restr_info = PF.p_get_restricting_info(normal_aide0, normal_aide0_nt)
        assert restr_info['Pledge'] == BD.delegate_amount
        assert restr_info['balance'] == BD.delegate_amount and restr_info['debt'] == 0

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
    @pytest.mark.parametrize('create_lock_mix_amt_unlock_eq', [{"ManyAcc": False}], indirect=True)
    def test_lock_mix_amt_unlock_eq(self, create_lock_mix_amt_unlock_eq):
        """
        锁定期混合金额 锁仓金额与自由金额解锁周期相等
        @param create_lock_mix_amt_unlock_eq:
        @Desc:
            -委托 A、B 节点 / limit * 210 / 超过锁定期总金额 -> fail
            -委托 A、B 节点 / limit / 使用锁仓金额委托
            -委托 A、B 节点 / 锁仓金额委托部分和超出(即扣自由金额), 委托自由金额部分和超出
            -验证各节点委托信息
            -等待锁定期中自由金额解锁并领取
            -锁仓计划信息不变,锁定期锁仓金额已全部再次委托
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt = create_lock_mix_amt_unlock_eq
        PF.p_get_delegate_lock_info(normal_aide0, normal_aide0_nt)

        logger.info("-委托 A、B 节点 / limit * 210 / 超过锁定期总金额 -> fail")
        assert normal_aide0.delegate.delegate(BD.delegate_limit * 210, 3,
                                              private_key=normal_aide0_nt.del_pk)['message'] == ERROR_CODE[301207]
        assert normal_aide0.delegate.delegate(BD.delegate_limit * 210, 3, node_id=normal_aide1.node.node_id,
                                              private_key=normal_aide0_nt.del_pk)['message'] == ERROR_CODE[301207]

        logger.info("-委托 A、B 节点 / limit / 使用锁仓金额委托")
        assert normal_aide0.delegate.delegate(balance_type=3, private_key=normal_aide0_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(balance_type=3, node_id=normal_aide1.node.node_id,
                                              private_key=normal_aide0_nt.del_pk, )['code'] == 0

        logger.info("查锁定期信息并验证")
        lock_restricting_plan = BD.delegate_amount - (BD.delegate_limit * 2)
        expect_data = {(3, BD.delegate_amount, lock_restricting_plan), }
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data)

        logger.info("-委托 A、B 节点 / 锁仓金额委托部分和超出(即扣自由金额), 委托自由金额部分和超出")
        logger.info("-剩余锁仓金额980 - 100 - 900 / 剩余自由金额980 - 500 - 500(fail)")
        del_amt1 = BD.delegate_limit * 10
        assert normal_aide0.delegate.delegate(del_amt1, 3, private_key=normal_aide0_nt.del_pk)['code'] == 0
        expect_data = {(3, BD.delegate_amount, lock_restricting_plan - del_amt1), }
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data)

        del_amt2 = BD.delegate_limit * 90
        assert normal_aide0.delegate.delegate(del_amt2, 3, private_key=normal_aide0_nt.del_pk)['code'] == 0
        lock_released = BD.delegate_amount - abs(lock_restricting_plan - del_amt1 - del_amt2)
        expect_data = {(3, lock_released, 0), }
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data)

        del_amt3 = BD.delegate_limit * 50
        assert normal_aide0.delegate.delegate(del_amt3, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide0_nt.del_pk)['code'] == 0
        expect_data = {(3, lock_released - del_amt3, 0), }
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data)

        assert normal_aide0.delegate.delegate(del_amt3, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide0_nt.del_pk)['message'] == ERROR_CODE[301207]
        logger.info("-验证各节点委托信息")
        del_info_0 = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        assert del_info_0.LockReleasedHes == abs(lock_restricting_plan - BD.delegate_amount)
        assert del_info_0.LockRestrictingPlanHes == lock_restricting_plan + BD.delegate_limit

        del_info_1 = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide1_nt)
        assert del_info_1.LockReleasedHes == del_amt3
        assert del_info_1.LockRestrictingPlanHes == BD.delegate_limit

        logger.info(f'{"-等待锁定期中自由金额解锁并领取":*^50s}')
        Released = BD.delegate_amount * 2 - (del_amt3 + del_amt2 + del_amt1 + BD.delegate_limit * 2)
        acc_amt_bef, red_acc_amt = redeem_del_wait_unlock_diff_balance_restr(normal_aide0, normal_aide0_nt)
        assert abs(red_acc_amt - acc_amt_bef - Released) < BD.von_limit

        logger.info(f'{"-锁仓计划信息不变,锁定期锁仓金额已全部再次委托":*^50s}')
        restr_info = PF.p_get_restricting_info(normal_aide0, normal_aide0_nt)
        assert restr_info['Pledge'] == BD.delegate_amount
        assert restr_info['balance'] == BD.delegate_amount and restr_info['debt'] == 0

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
    @pytest.mark.parametrize('create_lock_mix_amt_unlock_eq', [{"ManyAcc": True, "StaAmt": "limit", "rewardPer": 0}],
                             indirect=True)
    def test_lock_del_candidate_list(self, create_lock_mix_amt_unlock_eq):
        """
        @Desc:
            - 测试对 candidate_list 中的节点进行委托
            - 测试释放金额小于最低委托金额时 不会自动提取
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt = create_lock_mix_amt_unlock_eq
        print(normal_aide0_nt.node_id)
        print(normal_aide1_nt.node_id)
        validator_list = get_pledge_list(normal_aide0.staking.get_validator_list)
        logger.info(f"1: {validator_list}")
        verifier_list = get_pledge_list(normal_aide0.staking.get_verifier_list)
        logger.info(f"2: {verifier_list}")
        candidate_list = get_pledge_list(normal_aide0.staking.get_candidate_list)
        logger.info(f"3: {candidate_list}")
        assert normal_aide0_nt.node_id in verifier_list and normal_aide0_nt.node_id in candidate_list
        assert normal_aide1_nt.node_id not in verifier_list and normal_aide1_nt.node_id in candidate_list

        logger.info(f"使用锁定金 对节点B进行委托")
        assert normal_aide0.delegate.delegate(BD.von_k * 2 - BD.von_limit, 3, normal_aide1_nt.node_id,
                                              private_key=normal_aide0_nt.del_pk)['code'] == 0

        expect_data = {(3, BD.von_limit, 0)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data)

        wait_settlement(normal_aide0, 1)
        logger.info("验证释放金额 小于最低委托金额时 不会自动释放")
        expect_data = {"Released": BD.von_limit, "RestrictingPlan": 0}
        Assertion.del_lock_release_money(normal_aide0, normal_aide0_nt, expect_data)

        logger.info(f"对节点B赎回委托")
        wit_del_res = PF.p_withdrew_delegate(normal_aide0, BD.von_k, normal_aide1_nt, normal_aide0_nt.del_pk)
        wit_del_data = {
            "lockReleased": BD.von_k - BD.von_limit, "lockRestrictingPlan": BD.von_limit,
            "released": 0, "restrictingPlan": 0
        }
        Assertion.assert_withdrew_delegate_response_contain(wit_del_res, expect_data=wit_del_data)

        expect_data = {(5, BD.von_k - BD.von_limit, BD.von_limit)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data)

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
    @pytest.mark.parametrize('create_lock_mix_amt_unlock_eq', [{"ManyAcc": False, "rewardPer": 10}], indirect=True)
    @pytest.mark.parametrize('lock_mix_amt_unlock_eq_delegate', [{"wait_settlement": True}], indirect=True)
    def test_interface_1104_5100_1005_reward_field(self, lock_mix_amt_unlock_eq_delegate):
        """
        测试 接口1104 resp: CumulativeIncome、5100 resp: reward、1005 resp: delegateIncome、1105 resp: DelegateRewardTotal
        - 1104: 委托信息中的收益字段需要主动触发计算
        - 1005: 全部赎回委托则触发委托收益 回 账户
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt, lock_residue_amt = lock_mix_amt_unlock_eq_delegate
        PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        wait_settlement(normal_aide0, 1)
        del_info1 = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        assert del_info1.CumulativeIncome == 0

        staking_info = normal_aide0.staking.staking_info

        logger.info(f"赎回触发 delegate_info 中 委托奖励计算")
        wit_del_data1 = PF.p_withdrew_delegate(normal_aide0, BD.delegate_limit, normal_aide0_nt, normal_aide0_nt.del_pk)
        assert wit_del_data1.delegateIncome == 0

        del_info2 = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        delegate_reward_info = normal_aide0.delegate.get_delegate_reward(normal_aide0_nt.del_addr,
                                                                         [normal_aide0_nt.node_id])
        logger.info(f"get_delegate_reward: {delegate_reward_info}")

        assert del_info2.CumulativeIncome == delegate_reward_info[0].reward == staking_info.DelegateRewardTotal

        wit_del_dat2 = PF.p_withdrew_delegate(normal_aide0, BD.delegate_limit, normal_aide0_nt, normal_aide0_nt.del_pk)
        assert wit_del_dat2.delegateIncome == 0

        amt_before = normal_aide0.platon.get_balance(normal_aide0_nt.del_addr)
        logger.info(f"全部赎回才会触发 delegateIncome 计算")
        wit_del = BD.delegate_limit * 178
        wit_del_dat3 = PF.p_withdrew_delegate(normal_aide0, wit_del, normal_aide0_nt, normal_aide0_nt.del_pk)
        assert del_info2.CumulativeIncome == wit_del_dat3.delegateIncome
        amt_later = normal_aide0.platon.get_balance(normal_aide0_nt.del_addr)
        assert wit_del_dat3.delegateIncome - (amt_later - amt_before) < BD.von_min

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 0, }], indirect=True)
    def test_undelegate_freeze_duration_zero(self, choose_undelegate_freeze_duration):
        """解委托周期为零 部署链失败"""
        chain, new_gen_file = choose_undelegate_freeze_duration
        with pytest.raises(Exception) as exception_info:
            chain.install(genesis_file=new_gen_file)
        assert "executor install failed" in str(exception_info.value)


class TestDelegateLockManyAccToManyNode:
    """ 测试多账户-多节点场景 """

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
    @pytest.mark.parametrize('create_lock_free_amt', [{"ManyAcc": True}], indirect=True)
    def test_lock_free_amt(self, create_lock_free_amt):
        """
        测试 锁定期 自由金额 多账户委托多节点
        @param create_lock_free_amt:
        @Desc:
            -账户A1,B1 分别委托 A、B 节点 / limit * 110 -> fail
            -账户A1,B1 分别委托 A、B 节点 / limit
            -账户A1,B1 分别委托 A、B 节点 / limit * 5
            -账户A1 (剩余金额/2)分别委托 A、B 节点, B1 分别委托 A(剩余金额/2)、B节点(剩余金额/2)+von_limit -> fail
            -查询A1 无锁定金额 / B1 锁定期 自由余额 == del_amt3(剩余金额/2)
            -各节点委托信息
            -委托账户领取解锁期金额
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt, _ = create_lock_free_amt
        PF.p_get_delegate_lock_info(normal_aide0, normal_aide0_nt)
        PF.p_get_delegate_lock_info(normal_aide1, normal_aide1_nt)

        logger.info("-账户A1,B1 分别委托 A、B 节点 / limit * 110 -> fail")
        # (之前用例有一对多,这里本质就是2个一对多,避免用例重复只写一对一)
        del_amt1 = BD.delegate_limit * 110
        res = normal_aide0.delegate.delegate(del_amt1, 3, private_key=normal_aide0_nt.del_pk)
        assert ERROR_CODE[301207] == res['message']
        res = normal_aide0.delegate.delegate(del_amt1, 3, normal_aide1.node.node_id, private_key=normal_aide1_nt.del_pk)
        assert ERROR_CODE[301207] == res['message']

        logger.info("-账户A1,B1 分别委托 A、B 节点 / limit")
        assert normal_aide0.delegate.delegate(BD.delegate_limit, 3, private_key=normal_aide0_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(BD.delegate_limit, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide0_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(BD.delegate_limit, 3, private_key=normal_aide1_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(BD.delegate_limit, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide1_nt.del_pk)['code'] == 0

        logger.info("-账户A1,B1 分别委托 A、B 节点 / limit * 5")
        del_amt2 = BD.delegate_limit * 5
        assert normal_aide0.delegate.delegate(del_amt2, 3, private_key=normal_aide0_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(del_amt2, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide0_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(del_amt2, 3, private_key=normal_aide1_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(del_amt2, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide1_nt.del_pk)['code'] == 0

        logger.info("-账户A1 (剩余金额/2)分别委托 A、B 节点")
        residue_amt = BD.delegate_amount - (del_amt2 * 2) - (BD.delegate_limit * 2)
        del_amt3 = int(Decimal(residue_amt) / Decimal(2))
        assert normal_aide0.delegate.delegate(del_amt3, 3, private_key=normal_aide0_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(del_amt3, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide0_nt.del_pk)['code'] == 0

        logger.info("-账户B1 分别委托 A(剩余金额/2)、B节点(剩余金额/2)+von_limit -> fail")
        assert normal_aide0.delegate.delegate(del_amt3, 3, private_key=normal_aide1_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(del_amt3 + BD.von_limit, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide1_nt.del_pk)['message'] == ERROR_CODE[301207]

        logger.info("-查询A1 无锁定金额")
        Assertion.del_lock_info_zero_money(normal_aide0, normal_aide0_nt)
        logger.info(f"-B1 锁定期 自由余额 == (剩余金额/2) {del_amt3}")
        expect_data = {(3, del_amt3, 0), }
        Assertion.del_locks_money(normal_aide1, normal_aide1_nt, expect_data)

        logger.info("-A节点(A1,B1账户) 委托信息 合计(limit + del_amt2 + del_amt3) * 2")
        A_A1_del = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        assert A_A1_del.LockReleasedHes == BD.delegate_limit + del_amt2 + del_amt3
        A_B1_del = PF.p_get_delegate_info(normal_aide0, normal_aide1_nt.del_addr, normal_aide0_nt)
        assert A_B1_del.LockReleasedHes == BD.delegate_limit + del_amt2 + del_amt3

        logger.info("-B节点(A1,B1账户) 委托信息 A1(limit + del_amt2 + del_amt3) / B1(limit + del_amt2)")
        B_A1_del = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide1_nt)
        assert B_A1_del.LockReleasedHes == BD.delegate_limit + del_amt2 + del_amt3
        B_B1_del = PF.p_get_delegate_info(normal_aide0, normal_aide1_nt.del_addr, normal_aide1_nt)
        assert B_B1_del.LockReleasedHes == BD.delegate_limit + del_amt2

        logger.info("-B1账户领取解锁期金额")
        acc_amt_bef, red_acc_amt = redeem_del_wait_unlock_diff_balance_restr(normal_aide1, normal_aide1_nt)
        assert abs(red_acc_amt - acc_amt_bef - del_amt3) < BD.von_limit
        logger.info("-验证B1账户锁定期无数据")
        Assertion.del_lock_info_zero_money(normal_aide1, normal_aide1_nt)

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
    @pytest.mark.parametrize('create_lock_restr_amt', [{"ManyAcc": True}], indirect=True)
    def test_lock_restr_amt(self, create_lock_restr_amt):
        """
        测试 锁定期 锁仓金额 多账户委托多节点
        @param create_lock_restr_amt:
        @Desc:
            -账户A1,B1 分别委托 A、B 节点 / limit * 110 -> fail
            -账户A1,B1 分别委托 A、B 节点 / limit
            -账户A1,B1 分别委托 A、B 节点 / limit * 5
            -账户A1 (剩余金额/2)分别委托 A、B 节点, B1 分别委托 A(剩余金额/2)、B节点(剩余金额/2)+von_limit -> fail
            -查询A1 无锁定金额 / B1 锁定期 自由余额 == del_amt3(剩余金额/2)
            -各节点委托信息
            -委托账户领取解锁期金额
            -验证锁仓计划信息
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt, _ = create_lock_restr_amt
        PF.p_get_delegate_lock_info(normal_aide0, normal_aide0_nt)
        PF.p_get_delegate_lock_info(normal_aide1, normal_aide1_nt)

        logger.info("-账户A1,B1 分别委托 A、B 节点 / limit * 110 -> fail")
        del_amt1 = BD.delegate_limit * 110
        res = normal_aide0.delegate.delegate(del_amt1, 3, private_key=normal_aide0_nt.del_pk)
        assert ERROR_CODE[301207] == res['message']
        res = normal_aide0.delegate.delegate(del_amt1, 3, normal_aide1.node.node_id, private_key=normal_aide1_nt.del_pk)
        assert ERROR_CODE[301207] == res['message']

        logger.info("-账户A1,B1 分别委托 A、B 节点 / limit")
        assert normal_aide0.delegate.delegate(BD.delegate_limit, 3, private_key=normal_aide0_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(BD.delegate_limit, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide0_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(BD.delegate_limit, 3, private_key=normal_aide1_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(BD.delegate_limit, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide1_nt.del_pk)['code'] == 0

        logger.info("-账户A1,B1 分别委托 A、B 节点 / limit * 5")
        del_amt2 = BD.delegate_limit * 5
        assert normal_aide0.delegate.delegate(del_amt2, 3, private_key=normal_aide0_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(del_amt2, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide0_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(del_amt2, 3, private_key=normal_aide1_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(del_amt2, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide1_nt.del_pk)['code'] == 0

        logger.info("-账户A1 (剩余金额/2)分别委托 A、B 节点")
        residue_amt = BD.delegate_amount - (del_amt2 * 2) - (BD.delegate_limit * 2)
        del_amt3 = int(Decimal(residue_amt) / Decimal(2))
        assert normal_aide0.delegate.delegate(del_amt3, 3, private_key=normal_aide0_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(del_amt3, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide0_nt.del_pk)['code'] == 0

        logger.info("-账户B1 分别委托 A(剩余金额/2)、B节点(剩余金额/2)+von_limit -> fail")
        assert normal_aide0.delegate.delegate(del_amt3, 3, private_key=normal_aide1_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(del_amt3 + BD.von_limit, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide1_nt.del_pk)['message'] == ERROR_CODE[301207]

        logger.info("-查询A1 无锁定金额")
        Assertion.del_lock_info_zero_money(normal_aide0, normal_aide0_nt)
        logger.info(f"-B1 锁定期 锁仓余额 == (剩余金额/2) {del_amt3}")
        expect_data = {(3, 0, del_amt3), }
        Assertion.del_locks_money(normal_aide1, normal_aide1_nt, expect_data)

        logger.info("-A节点(A1,B1账户) 委托信息 合计(limit + del_amt2 + del_amt3) * 2")
        A_A1_del = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        assert A_A1_del.LockRestrictingPlanHes == BD.delegate_limit + del_amt2 + del_amt3
        A_B1_del = PF.p_get_delegate_info(normal_aide0, normal_aide1_nt.del_addr, normal_aide0_nt)
        assert A_B1_del.LockRestrictingPlanHes == BD.delegate_limit + del_amt2 + del_amt3

        logger.info("-B节点(A1,B1账户) 委托信息 A1(limit + del_amt2 + del_amt3) / B1(limit + del_amt2)")
        B_A1_del = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide1_nt)
        assert B_A1_del.LockRestrictingPlanHes == BD.delegate_limit + del_amt2 + del_amt3
        B_B1_del = PF.p_get_delegate_info(normal_aide0, normal_aide1_nt.del_addr, normal_aide1_nt)
        assert B_B1_del.LockRestrictingPlanHes == BD.delegate_limit + del_amt2

        logger.info("-B1账户领取解锁期金额 / 锁仓计划未释放 账户余额不变只扣手续费")
        acc_amt_bef, red_acc_amt = redeem_del_wait_unlock_diff_balance_restr(normal_aide1, normal_aide1_nt)
        assert abs(red_acc_amt - acc_amt_bef) < BD.von_limit
        logger.info("-领取之后 验证B1账户锁定期无数据")
        Assertion.del_lock_info_zero_money(normal_aide1, normal_aide1_nt)

        logger.info("-验证A1账户的锁仓计划")
        restr_info = PF.p_get_restricting_info(normal_aide0, normal_aide0_nt)
        assert restr_info["Pledge"] == restr_info['balance'] == BD.delegate_amount
        assert restr_info["debt"] == 0

        logger.info("-验证B1账户的锁仓计划")
        restr_info = PF.p_get_restricting_info(normal_aide1, normal_aide1_nt)
        assert restr_info['balance'] == BD.delegate_amount
        assert restr_info["Pledge"] == BD.delegate_amount - del_amt3
        assert restr_info["debt"] == 0

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
    @pytest.mark.parametrize('create_lock_restr_amt', [{"ManyAcc": True, "MixAcc": True}], indirect=True)
    def test_lock_mix_amt_free_unlock_long(self, create_lock_mix_amt_free_unlock_long):
        """
        锁定期混合金额 自由金额解锁周期更长 多账户委托多节点
        @param create_lock_mix_amt_free_unlock_long:
        @Setup:
            - "ManyAcc": True -> A1、B1账户 都先创建锁仓计划并赎回
            - "MixAcc": True -> A1、B1账户 都再次创建自由金额委托并赎回
            - Result: A1、B1账户 都拥有 锁定期混合金额 自由金额解锁周期更长
        @Desc:
            -账户A1,B1 分别委托 A、B 节点 / limit * 210 -> fail
            -账户A1,B1 分别委托 A、B 节点 / limit / 会使用自由金额委托
            -查锁定期信息并验证 - lock_released = 980
            -A1账户剩余自由金额980、锁仓金额1000 - 委托 A节点500(自由金额980-500) B节点500(自由金额480+20锁仓金额)
            -B1账户剩余自由金额980、锁仓金额1000 - 委托 A节点500(自由金额980-500) B节点500(自由金额480+20锁仓金额)
            -A1账户剩余锁仓金额980 - 委托 A节点500(锁仓金额980-500) B节点480(锁仓金额480)
            -B1账户剩余锁仓金额980 - 委托 A节点500(锁仓金额980-500) B节点500(锁仓金额480 -> fail)
            -验证A节点 A1、B1账户委托信息
            -验证B节点 A1、B1账户委托信息
            -B1账户 锁定期中锁仓金额解锁/锁仓计划未释放
            -B1账户 领取解锁的锁仓金额
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt = create_lock_mix_amt_free_unlock_long
        assert len(PF.p_get_delegate_lock_info(normal_aide0, normal_aide0_nt)['Locks']) == 2
        assert len(PF.p_get_delegate_lock_info(normal_aide0, normal_aide1_nt)['Locks']) == 2

        logger.info("-账户A1,B1 分别委托 A、B 节点 / limit * 210 -> fail")
        del_amt1 = BD.delegate_limit * 210
        assert normal_aide0.delegate.delegate(del_amt1, 3,
                                              private_key=normal_aide0_nt.del_pk)['message'] == ERROR_CODE[301207]
        assert normal_aide0.delegate.delegate(del_amt1, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide0_nt.del_pk)['message'] == ERROR_CODE[301207]

        logger.info("-账户A1,B1 分别委托 A、B 节点 / limit / 会使用自由金额委托")
        assert normal_aide0.delegate.delegate(BD.delegate_limit, 3, private_key=normal_aide0_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(BD.delegate_limit, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide0_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(BD.delegate_limit, 3, private_key=normal_aide1_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(BD.delegate_limit, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide1_nt.del_pk)['code'] == 0

        logger.info("查锁定期信息并验证 - lock_released = 980")
        lock_released = BD.delegate_amount - (BD.delegate_limit * 2)
        expect_data = {(3, 0, BD.delegate_amount), (4, lock_released, 0)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data)
        Assertion.del_locks_money(normal_aide0, normal_aide1_nt, expect_data)

        logger.info("-A1账户剩余自由金额980、锁仓金额1000 - 委托 A节点500(自由金额980-500) B节点500(自由金额480+20锁仓金额)")
        del_amt2 = int(Decimal(BD.delegate_amount) / Decimal(2))
        assert normal_aide0.delegate.delegate(del_amt2, 3, private_key=normal_aide0_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(del_amt2, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide0_nt.del_pk)['code'] == 0
        expect_data = {(3, 0, BD.delegate_amount - abs(del_amt2 * 2 - lock_released)), }
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data)

        logger.info("-B1账户剩余自由金额980、锁仓金额1000 - 委托 A节点500(自由金额980-500) B节点500(自由金额480+20锁仓金额)")
        assert normal_aide0.delegate.delegate(del_amt2, 3, private_key=normal_aide1_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(del_amt2, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide1_nt.del_pk)['code'] == 0
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data)

        logger.info("-A1账户剩余锁仓金额980 - 委托 A节点500(锁仓金额980-500) B节点480(锁仓金额480)")
        assert normal_aide0.delegate.delegate(del_amt2, 3, private_key=normal_aide0_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(del_amt2 - BD.delegate_limit * 2, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide0_nt.del_pk)['code'] == 0
        Assertion.del_lock_info_zero_money(normal_aide0, normal_aide0_nt)

        logger.info("-B1账户剩余锁仓金额980 - 委托 A节点500(锁仓金额980-500) B节点500(锁仓金额480 -> fail)")
        assert normal_aide0.delegate.delegate(del_amt2, 3, private_key=normal_aide1_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(del_amt2, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide1_nt.del_pk)['message'] == ERROR_CODE[301207]
        expect_data = {(3, 0, del_amt2 - BD.delegate_limit * 2), }
        Assertion.del_locks_money(normal_aide0, normal_aide1_nt, expect_data)

        logger.info("-验证A节点 A1、B1账户委托信息")
        A_A1_del = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        assert A_A1_del.LockReleasedHes == del_amt2 + BD.delegate_limit
        assert A_A1_del.LockRestrictingPlanHes == del_amt2

        A_B1_del = PF.p_get_delegate_info(normal_aide0, normal_aide1_nt.del_addr, normal_aide0_nt)
        assert A_B1_del.LockReleasedHes == del_amt2 + BD.delegate_limit
        assert A_B1_del.LockRestrictingPlanHes == del_amt2

        logger.info("-验证B节点 A1、B1账户委托信息")
        B_A1_del = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide1_nt)
        assert B_A1_del.LockReleasedHes == (BD.delegate_amount - del_amt2 - BD.delegate_limit * 2) + BD.delegate_limit
        assert B_A1_del.LockRestrictingPlanHes == del_amt2

        B_B1_del = PF.p_get_delegate_info(normal_aide0, normal_aide1_nt.del_addr, normal_aide1_nt)
        assert B_B1_del.LockReleasedHes == (BD.delegate_amount - del_amt2 - BD.delegate_limit * 2) + BD.delegate_limit
        assert B_B1_del.LockRestrictingPlanHes == BD.delegate_limit * 2

        wait_settlement(normal_aide0)
        logger.info(f'{"-B1账户 锁定期中锁仓金额解锁/锁仓计划未释放":*^50s}')
        RestrictingPlan = BD.delegate_amount * 2 - (del_amt2 * 3 + BD.delegate_limit * 2)
        expect_data = {"Released": 0, "RestrictingPlan": RestrictingPlan}
        Assertion.del_lock_release_money(normal_aide0, normal_aide1_nt, expect_data)

        logger.info(f'{"-B1账户 领取解锁的锁仓金额":*^50s}')
        assert normal_aide0.delegate.redeem_delegate(private_key=normal_aide1_nt.del_pk)['code'] == 0
        restr_info = PF.p_get_restricting_info(normal_aide0, normal_aide1_nt)
        assert restr_info['Pledge'] == BD.delegate_amount - RestrictingPlan
        assert restr_info['balance'] == BD.delegate_amount and restr_info['debt'] == 0

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
    @pytest.mark.parametrize('create_lock_free_amt', [{"ManyAcc": True, "MixAcc": True}], indirect=True)
    def test_lock_mix_amt_restr_unlock_long(self, create_lock_mix_amt_restr_unlock_long):
        """
        锁定期混合金额 锁仓金额解锁周期更长 多账户委托多节点
        @param create_lock_mix_amt_restr_unlock_long:
        @Setup:
            - "ManyAcc": True -> A1、B1账户 都先创建自由金额委托并赎回
            - "MixAcc": True -> A1、B1账户 都再次创建锁仓金额委托并赎回
            - Result: A1、B1账户 都拥有 锁定期混合金额 锁仓金额解锁周期更长
        @Desc:
            -账户A1,B1 分别委托 A、B 节点 / limit * 210 -> fail
            -账户A1,B1 分别委托 A、B 节点 / limit / 会使用锁仓金额委托
            -查锁定期信息并验证 - lock_released = 980
            -A1账户剩余锁仓金额980、自由金额1000 - 委托 A节点500(锁仓金额980-500) B节点500(锁仓金额480+20自由金额)
            -B1账户剩余锁仓金额980、自由金额1000 - 委托 A节点500(锁仓金额980-500) B节点500(锁仓金额480+20自由金额)
            -A1账户剩余自由金额980 - 委托 A节点500(自由金额980-500) B节点480(自由金额480)
            -B1账户剩余自由金额980 - 委托 A节点500(自由金额980-500) B节点500(自由金额480 -> fail)
            -验证A节点 A1、B1账户委托信息
            -验证B节点 A1、B1账户委托信息
            -B1账户 锁定期中自由金额解锁并领取
            -B1账户 原锁仓计划信息不变,锁定期锁仓金额已全部再次委托
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt = create_lock_mix_amt_restr_unlock_long
        assert len(PF.p_get_delegate_lock_info(normal_aide0, normal_aide0_nt)['Locks']) == 2
        assert len(PF.p_get_delegate_lock_info(normal_aide0, normal_aide1_nt)['Locks']) == 2

        logger.info("-账户A1,B1 分别委托 A、B 节点 / limit * 210 -> fail")
        del_amt1 = BD.delegate_limit * 210
        assert normal_aide0.delegate.delegate(del_amt1, 3,
                                              private_key=normal_aide0_nt.del_pk)['message'] == ERROR_CODE[301207]
        assert normal_aide0.delegate.delegate(del_amt1, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide0_nt.del_pk)['message'] == ERROR_CODE[301207]

        logger.info("-账户A1,B1 分别委托 A、B 节点 / limit / 会使用锁仓金额委托")
        assert normal_aide0.delegate.delegate(BD.delegate_limit, 3, private_key=normal_aide0_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(BD.delegate_limit, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide0_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(BD.delegate_limit, 3, private_key=normal_aide1_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(BD.delegate_limit, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide1_nt.del_pk)['code'] == 0

        logger.info("查锁定期信息并验证 - lock_released = 980")
        lock_restricting_plan = BD.delegate_amount - (BD.delegate_limit * 2)
        expect_data = {(3, BD.delegate_amount, 0), (4, 0, lock_restricting_plan)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data)
        Assertion.del_locks_money(normal_aide0, normal_aide1_nt, expect_data)

        logger.info("-A1账户剩余锁仓金额980、自由金额1000 - 委托 A节点500(锁仓金额980-500) B节点500(锁仓金额480+20自由金额)")
        del_amt2 = int(Decimal(BD.delegate_amount) / Decimal(2))
        assert normal_aide0.delegate.delegate(del_amt2, 3, private_key=normal_aide0_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(del_amt2, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide0_nt.del_pk)['code'] == 0
        expect_data = {(3, BD.delegate_amount - abs(del_amt2 * 2 - lock_restricting_plan), 0), }
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data)

        logger.info("-B1账户剩余锁仓金额980、自由金额1000 - 委托 A节点500(锁仓金额980-500) B节点500(锁仓金额480+20自由金额)")
        assert normal_aide0.delegate.delegate(del_amt2, 3, private_key=normal_aide1_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(del_amt2, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide1_nt.del_pk)['code'] == 0
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data)

        logger.info("-A1账户剩余自由金额980 - 委托 A节点500(自由金额980-500) B节点480(自由金额480)")
        assert normal_aide0.delegate.delegate(del_amt2, 3, private_key=normal_aide0_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(del_amt2 - BD.delegate_limit * 2, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide0_nt.del_pk)['code'] == 0
        Assertion.del_lock_info_zero_money(normal_aide0, normal_aide0_nt)

        logger.info("-B1账户剩余自由金额980 - 委托 A节点500(自由金额980-500) B节点500(自由金额480 -> fail)")
        assert normal_aide0.delegate.delegate(del_amt2, 3, private_key=normal_aide1_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(del_amt2, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide1_nt.del_pk)['message'] == ERROR_CODE[301207]
        expect_data = {(3, del_amt2 - BD.delegate_limit * 2, 0), }
        Assertion.del_locks_money(normal_aide0, normal_aide1_nt, expect_data)

        logger.info("-验证A节点 A1、B1账户委托信息")
        A_A1_del = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        assert A_A1_del.LockReleasedHes == del_amt2
        assert A_A1_del.LockRestrictingPlanHes == del_amt2 + BD.delegate_limit

        A_B1_del = PF.p_get_delegate_info(normal_aide0, normal_aide1_nt.del_addr, normal_aide0_nt)
        assert A_B1_del.LockReleasedHes == del_amt2
        assert A_B1_del.LockRestrictingPlanHes == del_amt2 + BD.delegate_limit

        logger.info("-验证B节点 A1、B1账户委托信息")
        B_A1_del = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide1_nt)
        assert B_A1_del.LockReleasedHes == del_amt2
        assert B_A1_del.LockRestrictingPlanHes == lock_restricting_plan - del_amt2 + BD.delegate_limit

        B_B1_del = PF.p_get_delegate_info(normal_aide0, normal_aide1_nt.del_addr, normal_aide1_nt)
        assert B_B1_del.LockReleasedHes == BD.delegate_limit * 2
        assert B_B1_del.LockRestrictingPlanHes == lock_restricting_plan - del_amt2 + BD.delegate_limit

        logger.info(f'{"-B1账户 锁定期中自由金额解锁并领取":*^50s}')
        Released = BD.delegate_amount * 2 - (del_amt2 * 3 + BD.delegate_limit * 2)
        acc_amt_bef, red_acc_amt = redeem_del_wait_unlock_diff_balance_restr(normal_aide0, normal_aide1_nt, wait_num=1)
        assert abs(red_acc_amt - acc_amt_bef - Released) < BD.von_limit

        logger.info(f'{"-B1账户 原锁仓计划信息不变,锁定期锁仓金额已全部再次委托":*^50s}')
        restr_info = PF.p_get_restricting_info(normal_aide0, normal_aide1_nt)
        assert restr_info['Pledge'] == BD.delegate_amount
        assert restr_info['balance'] == BD.delegate_amount and restr_info['debt'] == 0


class TestDelegateLockNodeException:
    """测试节点异常 使用锁定期金额进行委托和赎回委托"""

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 10, }], indirect=True)
    @pytest.mark.parametrize('create_lock_restr_amt', [{"ManyAcc": True, "MixAcc": True}], indirect=True)
    def test_node_gt_staking_limit(self, create_lock_mix_amt_free_unlock_long):
        """
        测试节点状态异常(惩罚后大于质押金额) 使用锁定期金额 自由金额锁定周期更长进行委托
        @Setup:
            - choose_undelegate_freeze_duration: 更新锁定周期数
            - create_lock_restr_amt ManyAcc: 多账户都创建锁仓计划委托并赎回
            - create_lock_mix_amt_free_unlock_long MixAcc: 多账户都创建自由金额委托并赎回
        @Desc:
            - 验证多账户初始锁定金额中包含(锁仓金额 和 自由金额)
            - 关闭节点未被惩罚前委托
            - 关闭节点被惩罚后委托
            - 节点惩罚后的质押金额 > staking_limit 等待一个周期后 节点状态恢复可用,可被正常委托
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt = create_lock_mix_amt_free_unlock_long
        assert len(PF.p_get_delegate_lock_info(normal_aide0, normal_aide0_nt)['Locks']) == 2
        assert len(PF.p_get_delegate_lock_info(normal_aide0, normal_aide1_nt)['Locks']) == 2

        validator_list = get_pledge_list(normal_aide1.staking.get_validator_list)
        assert normal_aide1.node.node_id in validator_list

        logger.info(f"stop_node_id: {normal_aide1.node.node_id}")
        normal_aide1.node.stop()

        total_staking_reward, per_block_reward = normal_aide0.calculator.get_reward_info()
        logger.info(f"total_staking_reward: {total_staking_reward}")
        logger.info(f"per_block_reward: {per_block_reward}, total:{per_block_reward * 5}")

        punishment_consensus_num = wait_consensus_assert_stop_node_status(normal_aide0, normal_aide1, normal_aide1_nt)
        logger.info(f"stop_node 在第{punishment_consensus_num}个共识轮被惩罚")
        if punishment_consensus_num == 4:  # 第4个共识轮被惩罚,表示上一个结算周期已过,需在等待一个结算周期
            wait_settlement(normal_aide0)
        else:
            wait_settlement(normal_aide0, 1)
        logger.info(f"被惩罚 节点质押金额 > staking_limit, 节点状态恢复正常")
        candidate_info = PF.p_get_candidate_info(normal_aide0, query_aide=normal_aide1)
        assert candidate_info.Status == 0
        assert normal_aide0.delegate.delegate(BD.delegate_limit, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide1_nt.del_pk)['code'] == 0

        logger.info(f"start_node_id: {normal_aide1.node.node_id}")
        normal_aide1.node.start()
        logger.info(f"{normal_aide1.node}: 委托BD.delegate_amount, 会使用锁定期自由金额+锁仓金额")
        assert normal_aide0.delegate.delegate(BD.delegate_amount, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide1_nt.del_pk)['code'] == 0
        lock_info = PF.p_get_delegate_lock_info(normal_aide0, normal_aide1_nt)
        logger.info(f"{normal_aide1.node}: 锁定期只剩下锁仓金额")
        assert len(lock_info["Locks"]) == 1
        logger.info(f"其他账户对{normal_aide1.node}进行委托")
        assert normal_aide0.delegate.delegate(BD.delegate_amount, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide0_nt.del_pk)['code'] == 0

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 10, "slashBlock": 10}], indirect=True)
    @pytest.mark.parametrize('create_lock_restr_amt', [{"ManyAcc": True, "MixAcc": True}], indirect=True)
    def test_node_lt_staking_limit(self, create_lock_mix_amt_free_unlock_long):
        """测试节点状态异常(惩罚后小于质押金额) 使用锁定期金额委托"""
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt = create_lock_mix_amt_free_unlock_long

        assert PF.p_get_candidate_info(normal_aide0, query_aide=normal_aide1).Status == 0

        validator_list = get_pledge_list(normal_aide1.staking.get_validator_list)
        assert normal_aide1.node.node_id in validator_list

        logger.info(f"stop_node_id: {normal_aide1.node.node_id}")
        normal_aide1.node.stop()

        total_staking_reward, per_block_reward = normal_aide0.calculator.get_reward_info()
        logger.info(f"total_staking_reward: {total_staking_reward}")
        logger.info(f"per_block_reward: {per_block_reward}, total:{per_block_reward * 10}")

        punishment_consensus_num = wait_consensus_assert_stop_node_status(normal_aide0, normal_aide1, normal_aide1_nt)
        logger.info(f"stop_node 在第{punishment_consensus_num}个共识轮被惩罚")
        if punishment_consensus_num == 4:  # 第4个共识轮被惩罚,表示上一个结算周期已过,需在等待一个结算周期
            wait_settlement(normal_aide0)
        else:
            wait_settlement(normal_aide0, 1)
        logger.info(f"start_node_id: {normal_aide1.node.node_id}")
        normal_aide1.node.start()
        logger.info(f"被惩罚 节点质押金额 < staking_limit, 节点状态异常")
        candidate_info = PF.p_get_candidate_info(normal_aide0, query_aide=normal_aide1)
        assert candidate_info.Status == 7
        assert normal_aide0.delegate.delegate(BD.delegate_limit, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide1_nt.del_pk)['message'] == ERROR_CODE[301103]

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
    @pytest.mark.parametrize('create_lock_free_amt', [{"ManyAcc": True}], indirect=True)
    def test_node_withdrew_staking(self, create_lock_free_amt):
        """
        测试节点状态异常(主动赎回质押金额)
        - 使用锁定期金额 自由金额进行委托
        - 锁定期无锁定金额 有释放金额 进行委托  ->  fail
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt, _ = create_lock_free_amt

        logger.info(f"-赎回质押 和 锁定期周期数一致,再次发起委托")
        assert normal_aide1.delegate.delegate(amount=BD.delegate_amount, balance_type=0,
                                              private_key=normal_aide1_nt.del_pk)['code'] == 0

        assert normal_aide0.staking.withdrew_staking(node_id=normal_aide1.node.node_id,
                                                     private_key=normal_aide1_nt.sta_pk)['code'] == 0
        assert PF.p_get_candidate_info(normal_aide0, normal_aide1).Status == 33
        assert normal_aide0.delegate.delegate(BD.delegate_limit, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide1_nt.del_pk)['message'] == ERROR_CODE[301103]

        wait_settlement(normal_aide0, 1)
        wit_del_res = PF.p_withdrew_delegate(normal_aide0, BD.delegate_amount, normal_aide1_nt, normal_aide1_nt.del_pk)
        expect_data = {"lockReleased": BD.delegate_amount, "lockRestrictingPlan": 0,
                       "released": 0, "restrictingPlan": 0}
        Assertion.assert_withdrew_delegate_response_contain(wit_del_res, expect_data)

        logger.info(f"-验证 lock_info 只存在一笔锁定金额,之前的锁定期金额已释放")
        assert len(PF.p_get_delegate_lock_info(normal_aide0, normal_aide1_nt)['Locks']) == 1
        assert PF.p_get_candidate_info(normal_aide0, normal_aide1).Status == 33

        wait_settlement(normal_aide0)
        logger.info(f"-{normal_aide1.node}: 已无质押信息")
        assert PF.p_get_candidate_info(normal_aide0, normal_aide1) is None

        assert normal_aide1.staking.create_staking(amount=BD.staking_limit, balance_type=0,
                                                   node_id=normal_aide1.node.node_id,
                                                   benefit_address=normal_aide1_nt.sta_addr,
                                                   private_key=normal_aide1_nt.sta_pk)['code'] == 0

        assert normal_aide1.delegate.delegate(BD.delegate_amount, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide1_nt.del_pk)['code'] == 0
        logger.info(f"-锁定期无金额委托")
        assert normal_aide0.delegate.delegate(BD.delegate_limit, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide1_nt.del_pk)['message'] == ERROR_CODE[301207]


class TestWithdrewDelegate:
    """测试赎回委托 - 此类只做用例理解标识,无实际用例"""
    pass


class TestWithdrewDelegateBaseCase(TestWithdrewDelegate):
    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
    @pytest.mark.parametrize('create_lock_mix_amt_unlock_eq', [{"ManyAcc": True}], indirect=True)
    @pytest.mark.parametrize('lock_mix_amt_unlock_eq_delegate', [{"wait_settlement": False}], indirect=True)
    def test_lock_withdrew_delegate(self, lock_mix_amt_unlock_eq_delegate):
        """
        测试 锁定期金额委托
        @param lock_mix_amt_unlock_eq_delegate:
        @Setup:
            -锁定期混合金额犹豫期进行委托
        @Desc:
            -赎回委托 limit * 10
            -赎回委托 delegate_amount = limit * 100
            -赎回委托 limit * 80 -> fail
            -跨结算周期赎回委托 limit * 70
            -等待锁定期金额解锁并领取(分别验证领取自由金额/锁仓金额)
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt, lock_residue_amt = lock_mix_amt_unlock_eq_delegate
        logger.info(f"-赎回委托 limit * 10")
        wit_del_res = PF.p_withdrew_delegate(normal_aide0, BD.delegate_limit * 10,
                                             normal_aide0_nt, normal_aide0_nt.del_pk)
        wit_del_data = {"lockReleased": BD.delegate_limit * 10, "lockRestrictingPlan": 0,
                        "released": 0, "restrictingPlan": 0}
        Assertion.assert_withdrew_delegate_response_contain(wit_del_res, wit_del_data)

        expect_data1 = {(3, lock_residue_amt + BD.delegate_limit * 10, 0)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data1)

        logger.info(f"-赎回委托 delegate_amount = limit * 100")
        wit_del_res = PF.p_withdrew_delegate(normal_aide0, BD.delegate_amount,
                                             normal_aide0_nt, normal_aide0_nt.del_pk)
        wit_del_data = {"lockReleased": BD.delegate_limit * 70, "lockRestrictingPlan": BD.delegate_limit * 30,
                        "released": 0, "restrictingPlan": 0}
        Assertion.assert_withdrew_delegate_response_contain(wit_del_res, wit_del_data)

        expect_data2 = {(3, BD.delegate_amount, lock_residue_amt + BD.delegate_limit * 10)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data2)

        logger.info(f"-赎回委托 limit * 80 -> fail")
        res = normal_aide0.delegate.withdrew_delegate(BD.delegate_limit * 80, private_key=normal_aide0_nt.del_pk)
        assert res['message'] == ERROR_CODE[301113]

        wait_settlement(normal_aide0)

        logger.info(f"-跨结算周期赎回委托 limit * 70")
        wit_del_res = PF.p_withdrew_delegate(normal_aide0, BD.delegate_limit * 70,
                                             normal_aide0_nt, normal_aide0_nt.del_pk)
        wit_del_data = {"lockReleased": 0, "lockRestrictingPlan": BD.delegate_limit * 70,
                        "released": 0, "restrictingPlan": 0}
        Assertion.assert_withdrew_delegate_response_contain(wit_del_res, wit_del_data)

        expect_data2.add((4, 0, BD.delegate_limit * 70))
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data2)

        logger.info(f"-等待锁定期自由金额解锁并领取")
        acc_amt_before, red_acc_amt, restr_info_before, restr_info_later = \
            redeem_del_wait_unlock_diff_balance_restr(normal_aide0, normal_aide0_nt, wait_num=1, diff_restr=True)
        assert abs(red_acc_amt - acc_amt_before - BD.delegate_amount) < BD.von_limit
        logger.info(f"-锁定期锁仓金额解锁领取后 验证锁仓计划")
        expect_data = {'Pledge': {"old_value": BD.delegate_amount,
                                  "new_value": BD.delegate_amount - (lock_residue_amt + BD.delegate_limit * 10)}}
        Assertion.assert_restr_amt(restr_info_before, restr_info_later, expect_data)

        acc_amt_before, red_acc_amt, restr_info_before, restr_info_later = \
            redeem_del_wait_unlock_diff_balance_restr(normal_aide0, normal_aide0_nt, wait_num=1, diff_restr=True)
        logger.info(f"-等待解锁期领取,无自由金额,账户余额未增加")
        assert abs(red_acc_amt - acc_amt_before) < BD.von_limit
        logger.info(f"-锁定期锁仓金额解锁领取后 验证锁仓计划")
        old_value = BD.delegate_amount - (lock_residue_amt + BD.delegate_limit * 10)
        expect_data = {'Pledge': {"old_value": old_value,
                                  "new_value": old_value - BD.delegate_limit * 70}}
        Assertion.assert_restr_amt(restr_info_before, restr_info_later, expect_data)
        logger.info(f"-lock_info 锁定期无锁定数据、无已释放金额")
        Assertion.del_lock_info_zero_money(normal_aide0, normal_aide0_nt)

        assert PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt) is None

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
    @pytest.mark.parametrize('create_lock_mix_amt_unlock_eq', [{"ManyAcc": True}], indirect=True)
    @pytest.mark.parametrize('lock_mix_amt_unlock_eq_delegate', [{"wait_settlement": True}], indirect=True)
    def test_withdrew_delegate_min(self, lock_mix_amt_unlock_eq_delegate):
        """
        测试赎回委托 低于最小委托限制后 会全部赎回
        - 锁定期生效期 锁仓金额1000 自由金额800
            * 先赎回801  -> 锁仓金额余 999
            * 在赎回990  -> 将锁仓金额999全部赎回
        - 锁定期犹豫期 锁仓金额1000 自由金额15
            * 先赎回10   -> 自由金额5 锁仓金额1000
            * 在赎回1000 -> 全部赎回
        - 锁定期犹豫期 锁仓金额1000 自由金额10 账户自由金额10
            * 先赎回25   -> 账户自由金额10 + 锁定期自由金额10 + 锁仓金额5  锁定期 锁仓余995
            * 赎回990    -> 锁仓995 全部赎回
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt, lock_residue_amt = lock_mix_amt_unlock_eq_delegate
        logger.info(f"-生效期 赎回委托 801 生效期自由金额800 + 生效期锁仓金额1")
        response = normal_aide0.delegate.withdrew_delegate(BD.delegate_limit * 80 + BD.von_limit,
                                                           private_key=normal_aide0_nt.del_pk)
        logger.info(f"-1.赎回委托信息: {response}")
        assert response['code'] == 0
        lock_data = response.data
        assert lock_data.lockReleased == BD.delegate_limit * 80
        assert lock_data.lockRestrictingPlan == BD.von_limit
        assert lock_data.released == 0 and lock_data.restrictingPlan == 0

        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        delegate_info_expect_data = {"Released": 0, "RestrictingPlan": BD.von_limit * 999,
                                     "ReleasedHes": 0, "RestrictingPlanHes": 0,
                                     "LockReleasedHes": 0, "LockRestrictingPlanHes": 0}
        Assertion.assert_delegate_info_contain(delegate_info, delegate_info_expect_data)
        lock_expect_data = {(3, lock_residue_amt, 0), (4, BD.delegate_limit * 80, BD.von_limit)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, lock_expect_data)

        logger.info(f"-生效期 赎回委托990 生效期锁仓金额999  低于10会全部赎回")
        response = normal_aide0.delegate.withdrew_delegate(BD.von_limit * 990, private_key=normal_aide0_nt.del_pk)
        logger.info(f"-2.赎回委托信息: {response}")
        assert response['code'] == 0
        lock_data = response.data
        assert lock_data.lockRestrictingPlan == BD.von_limit * 999
        assert lock_data.released == 0 and lock_data.restrictingPlan == 0 and lock_data.lockReleased == 0

        assert PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt) is None
        lock_expect_data = {(3, lock_residue_amt, 0), (4, BD.delegate_limit * 80, BD.delegate_amount)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, lock_expect_data)

        logger.info(f"-锁定金委托 1015=锁仓金额1k + 自由金额15")
        assert normal_aide0.delegate.delegate(BD.von_k + BD.von_limit * 15, 3,
                                              private_key=normal_aide0_nt.del_pk)['code'] == 0
        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        delegate_info_expect_data = {"Released": 0, "RestrictingPlan": 0,
                                     "ReleasedHes": 0, "RestrictingPlanHes": 0,
                                     "LockReleasedHes": BD.von_limit * 15, "LockRestrictingPlanHes": BD.von_k}
        Assertion.assert_delegate_info_contain(delegate_info, delegate_info_expect_data)
        lock_expect_data = {(3, lock_residue_amt, 0), (4, BD.delegate_limit * 80 - BD.von_limit * 15, 0)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, lock_expect_data)

        logger.info(f"犹豫期赎回10  自由金额还剩下5")
        response = normal_aide0.delegate.withdrew_delegate(BD.delegate_limit, private_key=normal_aide0_nt.del_pk)
        logger.info(f"-3.赎回委托信息: {response}")
        assert response['code'] == 0
        lock_data = response.data
        assert lock_data.lockReleased == BD.delegate_limit
        assert lock_data.lockRestrictingPlan == 0
        assert lock_data.released == 0
        assert lock_data.restrictingPlan == 0

        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        delegate_info_expect_data = {"Released": 0, "RestrictingPlan": 0,
                                     "ReleasedHes": 0, "RestrictingPlanHes": 0,
                                     "LockReleasedHes": BD.von_limit * 5, "LockRestrictingPlanHes": BD.von_k}
        Assertion.assert_delegate_info_contain(delegate_info, delegate_info_expect_data)
        lock_expect_data = {(3, lock_residue_amt, 0), (4, BD.delegate_limit * 80 - BD.von_limit * 5, 0)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, lock_expect_data)

        logger.info(f"犹豫期赎回1000 会赎回 自由金额5 + 锁仓金额1000")
        response = normal_aide0.delegate.withdrew_delegate(BD.delegate_amount, private_key=normal_aide0_nt.del_pk)
        logger.info(f"-4.赎回委托信息: {response}")
        assert response['code'] == 0
        lock_data = response.data
        assert lock_data.lockReleased == BD.von_limit * 5
        assert lock_data.lockRestrictingPlan == BD.delegate_amount
        assert lock_data.released == 0
        assert lock_data.restrictingPlan == 0

        assert PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt) is None
        lock_expect_data = {(3, lock_residue_amt, 0), (4, BD.delegate_limit * 80, BD.von_k)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, lock_expect_data)

        logger.info("账户金额 和锁仓金额混合委托 ")
        assert normal_aide0.delegate.delegate(BD.von_k + BD.von_limit * 10, 3,
                                              private_key=normal_aide0_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(BD.von_limit * 10, 0, private_key=normal_aide0_nt.del_pk)['code'] == 0
        logger.info("赎回25 账户自由金额10 + 锁定期自由金额10 + 锁仓金额5")
        response = normal_aide0.delegate.withdrew_delegate(BD.von_limit * 25, private_key=normal_aide0_nt.del_pk)

        logger.info(f"-5.赎回委托信息: {response}")
        assert response['code'] == 0
        lock_data = response.data
        assert lock_data.lockReleased == BD.delegate_limit
        assert lock_data.lockRestrictingPlan == BD.von_limit * 5
        assert lock_data.released == BD.delegate_limit
        assert lock_data.restrictingPlan == 0

        lock_expect_data = {(3, lock_residue_amt, 0), (4, BD.delegate_limit * 80, BD.von_limit * 5)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, lock_expect_data)
        logger.info("赎回990 -> 锁仓金额990 + 剩下5 小于最低金额 = 995")
        response = normal_aide0.delegate.withdrew_delegate(BD.von_limit * 990, private_key=normal_aide0_nt.del_pk)
        logger.info(f"-6.赎回委托信息: {response}")
        assert response['code'] == 0
        lock_data = response.data
        assert lock_data.lockReleased == 0
        assert lock_data.lockRestrictingPlan == BD.von_limit * 995
        assert lock_data.released == 0
        assert lock_data.restrictingPlan == 0

        lock_expect_data = {(3, lock_residue_amt, 0), (4, BD.delegate_limit * 80, BD.von_k)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, lock_expect_data)

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
    @pytest.mark.parametrize('create_lock_mix_amt_unlock_eq', [{"ManyAcc": False}], indirect=True)
    @pytest.mark.parametrize('acc_mix_amt_delegate', [{"wait_settlement": True}], indirect=True)
    @pytest.mark.parametrize('lock_mix_amt_unlock_eq_delegate', [{"wait_settlement": False}], indirect=True)
    def test_withdrew_delegate_response(self, acc_mix_amt_delegate, lock_mix_amt_unlock_eq_delegate):
        """
        测试赎回委托的响应数据
        @setup:
            - 创建锁定金混合金额
            - 账户混合金额去委托(自由金额1000 + 锁仓1000)  并 进入生效期
            - 锁定金额委托(自由金额800 + 锁仓1000)
        @Desc:
            - 账户金额去委托(自由金额1000 + 锁仓1000)
            - 赎回5500  -> 验证赎回委托返回数据
        """
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt, lock_residue_amt = lock_mix_amt_unlock_eq_delegate

        logger.info(f"使用账户自由金额委托: {BD.delegate_amount}")
        assert normal_aide0.delegate.delegate(BD.delegate_amount, 0,
                                              private_key=normal_aide0_nt.del_pk)['code'] == 0

        logger.info(f"使用账户锁仓金额委托: {BD.delegate_amount}")
        lockup_amount = BD.delegate_amount  # platon/10 * 100
        plan = [{'Epoch': 10, 'Amount': lockup_amount}]
        logger.info(f'{f"{normal_aide0.node}: 锁仓金额委托":*^50s}')
        assert normal_aide0.restricting.restricting(release_address=normal_aide0_nt.del_addr, plans=plan,
                                                    private_key=normal_aide0_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(amount=BD.delegate_amount, balance_type=1,
                                              private_key=normal_aide0_nt.del_pk)['code'] == 0

        del_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        expect_del_info = {
            'Released': BD.von_k, 'ReleasedHes': BD.von_k,
            'RestrictingPlan': BD.von_k, 'RestrictingPlanHes': BD.von_k,
            'LockReleasedHes': BD.von_k - lock_residue_amt, 'LockRestrictingPlanHes': BD.von_k
        }
        Assertion.assert_delegate_info_contain(del_info, expect_del_info)
        wit_del_amt = BD.von_k * 5 + BD.delegate_limit * 50
        wit_del_res = PF.p_withdrew_delegate(normal_aide0, wit_del_amt, normal_aide0_nt, normal_aide0_nt.del_pk)
        released = BD.von_k - lock_residue_amt
        restrictingPlan = (BD.von_k + BD.delegate_limit * 50) - released
        wit_del_data = {"lockReleased": BD.von_k + released, "lockRestrictingPlan": BD.von_k + restrictingPlan,
                        "released": BD.von_k, "restrictingPlan": BD.von_k}
        Assertion.assert_withdrew_delegate_response_contain(wit_del_res, wit_del_data)


class TestAccLockMixAmtHesitation(TestWithdrewDelegate):
    """测试赎回委托 / 账户委托(MixAmt同时)犹豫期、锁定期委托犹豫期 (01~04)"""

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
    @pytest.mark.parametrize('create_lock_mix_amt_unlock_eq', [{"ManyAcc": True}], indirect=True)
    @pytest.mark.parametrize('acc_mix_amt_delegate', [{"wait_settlement": False}], indirect=True)
    @pytest.mark.parametrize('lock_mix_amt_unlock_eq_delegate', [{"wait_settlement": False}], indirect=True)
    def test_acc_lock_mix_withdrew_delegate_01(self, lock_mix_amt_unlock_eq_delegate, acc_mix_amt_delegate):
        """
        测试 赎回委托金额 总和 < 账户已委托总和
        @param lock_mix_amt_unlock_eq_delegate: 锁定期 已委托混合金额总和 BD.delegate_amount * 2 - lock_residue_amt
        @param acc_mix_amt_delegate: 账户已委托金额 总和 BD.delegate_amount * 2
        @Desc:
            -赎回账户自由金额 BD.delegate_limit * 50 赎回500
            -赎回账户自由金额 BD.delegate_limit * 50 锁仓金额BD.delegate_limit * 50 赎回1000
        @Result:
            -合计赎回1000 + 500 < 账户委托总和 BD.delegate_amount * 2
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt, lock_residue_amt = lock_mix_amt_unlock_eq_delegate

        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        expect_data = {"ReleasedHes": BD.von_k, "RestrictingPlanHes": BD.von_k,
                       "LockReleasedHes": BD.von_k - lock_residue_amt, "LockRestrictingPlanHes": BD.von_k}
        Assertion.assert_delegate_info_contain(delegate_info, expect_data)

        logger.info(f"-赎回账户自由金额 BD.delegate_limit * 50")
        withdrew_del_amt1 = BD.delegate_limit * 50
        amt_before, amt_later, _, _ = withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt,
                                                                      withdrew_del_amt1)
        assert withdrew_del_amt1 - abs(amt_later - amt_before) < BD.von_limit
        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        expect_data = {"ReleasedHes": BD.von_k - withdrew_del_amt1, "RestrictingPlanHes": BD.von_k,
                       "LockReleasedHes": BD.von_k - lock_residue_amt, "LockRestrictingPlanHes": BD.von_k}
        Assertion.assert_delegate_info_contain(delegate_info, expect_data)

        logger.info(f"-赎回账户自由金额 BD.delegate_limit * 50 锁仓金额BD.delegate_limit * 50")
        withdrew_del_amt2 = BD.delegate_limit * 100
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt2, diff_restr=True)
        assert withdrew_del_amt1 - abs(amt_later - amt_before) < BD.von_limit

        expect_data = {'Pledge': {"old_value": BD.delegate_amount * 2,
                                  "new_value": BD.delegate_amount * 2 - withdrew_del_amt1}}
        Assertion.assert_restr_amt(restr_before, restr_later, expect_data)

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
    @pytest.mark.parametrize('create_lock_mix_amt_unlock_eq', [{"ManyAcc": True}], indirect=True)
    @pytest.mark.parametrize('acc_mix_amt_delegate', [{"wait_settlement": False}], indirect=True)
    @pytest.mark.parametrize('lock_mix_amt_unlock_eq_delegate', [{"wait_settlement": False}], indirect=True)
    def test_acc_lock_mix_withdrew_delegate_02(self, lock_mix_amt_unlock_eq_delegate, acc_mix_amt_delegate):
        """
        测试 账户已委托总和 < 赎回委托金额总和 < 锁定期已委托混合金额总和 + 账户金额总和
        @param lock_mix_amt_unlock_eq_delegate: 锁定期 已委托混合金额总和 BD.delegate_amount * 2 - lock_residue_amt
        @param acc_mix_amt_delegate: 账户已委托金额 总和 BD.delegate_amount * 2
        @Desc:
            -赎回委托金额 BD.delegate_limit * 210 赎回2100
        @Result:
            -账户已委托总和2000 < 赎回委托金额2100 < 账户委托总和 2000 + 锁定期 已委托混合金额总和 2000 - 200
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt, lock_residue_amt = lock_mix_amt_unlock_eq_delegate

        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        expect_data = {"ReleasedHes": BD.von_k, "RestrictingPlanHes": BD.von_k,
                       "LockReleasedHes": BD.von_k - lock_residue_amt, "LockRestrictingPlanHes": BD.von_k}
        Assertion.assert_delegate_info_contain(delegate_info, expect_data)

        logger.info(f"-赎回委托金额 BD.delegate_limit * 210")
        withdrew_del_amt1 = BD.delegate_limit * 210
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt1, diff_restr=True)

        logger.info(f"-账户余额 BD.delegate_limit * 100 赎回1000")
        assert BD.delegate_amount - abs(amt_later - amt_before) < BD.von_limit

        logger.info(f"-账户锁仓 BD.delegate_limit * 100 质押扣减1000")
        expect_data = {'Pledge': {"old_value": BD.delegate_amount * 2,
                                  "new_value": BD.delegate_amount * 2 - BD.delegate_amount}}
        Assertion.assert_restr_amt(restr_before, restr_later, expect_data)

        logger.info(f"-锁定期 BD.delegate_limit * 10 自由金额赎回100")
        expect_data1 = {(3, lock_residue_amt + BD.delegate_limit * 10, 0)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data1)

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
    @pytest.mark.parametrize('create_lock_mix_amt_unlock_eq', [{"ManyAcc": True}], indirect=True)
    @pytest.mark.parametrize('acc_mix_amt_delegate', [{"wait_settlement": False}], indirect=True)
    @pytest.mark.parametrize('lock_mix_amt_unlock_eq_delegate', [{"wait_settlement": False}], indirect=True)
    def test_acc_lock_mix_withdrew_delegate_03(self, lock_mix_amt_unlock_eq_delegate, acc_mix_amt_delegate):
        """
        测试 账户已委托总和 < 赎回委托金额总和 < 锁定期已委托混合金额总和 + 账户金额总和
        @param lock_mix_amt_unlock_eq_delegate: 锁定期 已委托混合金额总和 BD.delegate_amount * 2 - lock_residue_amt
        @param acc_mix_amt_delegate: 账户已委托金额 总和 BD.delegate_amount * 2
        @Desc:
            -赎回账户自由金额 BD.delegate_limit * 350 赎回3500
        @Result:
            -账户委托 2000 + 锁定期自由金额委托1000 < 赎回委托金额3500 < 账户委托 2000 + 锁定期委托总和 1800
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt, lock_residue_amt = lock_mix_amt_unlock_eq_delegate

        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        expect_data = {"ReleasedHes": BD.von_k, "RestrictingPlanHes": BD.von_k,
                       "LockReleasedHes": BD.von_k - lock_residue_amt, "LockRestrictingPlanHes": BD.von_k}
        Assertion.assert_delegate_info_contain(delegate_info, expect_data)

        logger.info(f"-赎回账户自由金额 BD.delegate_limit * 350")
        withdrew_del_amt1 = BD.delegate_limit * 350
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt1, diff_restr=True)

        logger.info(f"-账户余额 BD.delegate_limit * 100 赎回1000")
        assert BD.delegate_amount - abs(amt_later - amt_before) < BD.von_limit

        logger.info(f"-账户锁仓 赎回1000")
        expect_data = {'Pledge': {"old_value": BD.delegate_amount * 2,
                                  "new_value": BD.delegate_amount * 2 - BD.delegate_amount}}
        Assertion.assert_restr_amt(restr_before, restr_later, expect_data)

        logger.info(f"-锁定期 BD.delegate_limit * 100 自由金额赎回800 + 锁定期锁仓 赎回700")
        expect_data1 = {(3, BD.delegate_amount, BD.delegate_limit * 70)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data1)

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
    @pytest.mark.parametrize('create_lock_mix_amt_unlock_eq', [{"ManyAcc": True}], indirect=True)
    @pytest.mark.parametrize('acc_mix_amt_delegate', [{"wait_settlement": False}], indirect=True)
    @pytest.mark.parametrize('lock_mix_amt_unlock_eq_delegate', [{"wait_settlement": False}], indirect=True)
    def test_acc_lock_mix_withdrew_delegate_04(self, lock_mix_amt_unlock_eq_delegate, acc_mix_amt_delegate):
        """
        测试 赎回委托金额总和 >= 锁定期已委托混合金额总和 + 账户金额总和
        @param lock_mix_amt_unlock_eq_delegate: 锁定期 已委托混合金额总和 BD.delegate_amount * 2 - lock_residue_amt
        @param acc_mix_amt_delegate: 账户已委托金额 总和 BD.delegate_amount * 2
        @Desc:
            -赎回账户自由金额 BD.delegate_limit * 400 赎回 4000 -> fail
            -赎回账户自由金额 BD.delegate_limit * 380 赎回 3800
        @Result:
            -赎回委托金额总和(3800, 4000) >= 3800
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt, lock_residue_amt = lock_mix_amt_unlock_eq_delegate

        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        expect_data = {"ReleasedHes": BD.von_k, "RestrictingPlanHes": BD.von_k,
                       "LockReleasedHes": BD.von_k - lock_residue_amt, "LockRestrictingPlanHes": BD.von_k}
        Assertion.assert_delegate_info_contain(delegate_info, expect_data)

        logger.info(f"-赎回账户自由金额 BD.delegate_limit * 400 -> fail")
        withdrew_del_amt1 = BD.delegate_limit * 400
        res = normal_aide0.delegate.withdrew_delegate(withdrew_del_amt1, private_key=normal_aide0_nt.del_pk)
        assert res['message'] == ERROR_CODE[301113]

        logger.info(f"-赎回账户自由金额 BD.delegate_limit * 380")
        withdrew_del_amt2 = BD.delegate_limit * 380
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt2, diff_restr=True)

        logger.info(f"-账户余额 BD.delegate_limit * 100 赎回1000")
        assert BD.delegate_amount - abs(amt_later - amt_before) < BD.von_limit

        logger.info(f"-账户锁仓 赎回1000")
        expect_data = {'Pledge': {"old_value": BD.delegate_amount * 2,
                                  "new_value": BD.delegate_amount * 2 - BD.delegate_amount}}
        Assertion.assert_restr_amt(restr_before, restr_later, expect_data)

        logger.info(f"-锁定期 BD.delegate_limit * 100 自由金额赎回800 + 锁定期锁仓 赎回1000")
        expect_data1 = {(3, BD.delegate_amount, BD.delegate_amount)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data1)


class TestAccMixHesitationLockMixValid(TestWithdrewDelegate):
    """测试赎回委托 / 账户委托(MixAmt同时)犹豫期、锁定期委托生效期 (05~08)"""

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
    @pytest.mark.parametrize('create_lock_mix_amt_unlock_eq', [{"ManyAcc": True}], indirect=True)
    @pytest.mark.parametrize('acc_mix_amt_delegate', [{"wait_settlement": False}], indirect=True)
    @pytest.mark.parametrize('lock_mix_amt_unlock_eq_delegate', [{"wait_settlement": True}], indirect=True)
    def test_acc_lock_mix_withdrew_delegate_05(self, lock_mix_amt_unlock_eq_delegate, acc_mix_amt_delegate):
        """
        测试 赎回委托金额 总和 < 账户已委托总和
        @param lock_mix_amt_unlock_eq_delegate: 锁定期 已委托混合金额总和 BD.delegate_amount * 2 - lock_residue_amt
        @param acc_mix_amt_delegate: 账户已委托金额 总和 BD.delegate_amount * 2
        @Setup:
            -注意继承 fixture 前后顺序会影响前置
        @Desc:
            -赎回账户自由金额 BD.delegate_limit * 50 赎回500
            -赎回账户自由金额 BD.delegate_limit * 50 锁仓金额BD.delegate_limit * 50 赎回1000
        @Result:
            -合计赎回1000 + 500 < 账户委托总和 BD.delegate_amount * 2
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt, lock_residue_amt = lock_mix_amt_unlock_eq_delegate

        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        expect_data = {"Released": BD.von_k - lock_residue_amt, "RestrictingPlan": BD.von_k,  # 生效期金额
                       "ReleasedHes": BD.von_k, "RestrictingPlanHes": BD.von_k,  # 账户犹豫期金额
                       "LockReleasedHes": 0, "LockRestrictingPlanHes": 0}  # 锁定犹豫期金额
        Assertion.assert_delegate_info_contain(delegate_info, expect_data)

        logger.info(f"-赎回账户自由金额 BD.delegate_limit * 50")
        withdrew_del_amt1 = BD.delegate_limit * 50
        amt_before, amt_later, _, _ = withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt,
                                                                      withdrew_del_amt1)
        assert withdrew_del_amt1 - abs(amt_later - amt_before) < BD.von_limit
        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        expect_data = {"Released": BD.von_k - lock_residue_amt, "RestrictingPlan": BD.von_k,
                       "ReleasedHes": BD.von_k - withdrew_del_amt1, "RestrictingPlanHes": BD.von_k,
                       "LockReleasedHes": 0, "LockRestrictingPlanHes": 0}
        Assertion.assert_delegate_info_contain(delegate_info, expect_data)

        logger.info(f"-赎回账户自由金额 BD.delegate_limit * 50 锁仓金额BD.delegate_limit * 50")
        withdrew_del_amt2 = BD.delegate_limit * 100
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt2, diff_restr=True)
        assert withdrew_del_amt1 - abs(amt_later - amt_before) < BD.von_limit

        expect_data = {'Pledge': {"old_value": BD.delegate_amount * 2,
                                  "new_value": BD.delegate_amount * 2 - withdrew_del_amt1}}
        Assertion.assert_restr_amt(restr_before, restr_later, expect_data)

        delegate_info_f = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        expect_data_f = {"Released": BD.von_k - lock_residue_amt, "RestrictingPlan": BD.von_k,
                         "ReleasedHes": 0, "RestrictingPlanHes": BD.von_k - withdrew_del_amt1,
                         "LockReleasedHes": 0, "LockRestrictingPlanHes": 0}
        Assertion.assert_delegate_info_contain(delegate_info_f, expect_data_f)

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
    @pytest.mark.parametrize('create_lock_mix_amt_unlock_eq', [{"ManyAcc": True}], indirect=True)
    @pytest.mark.parametrize('acc_mix_amt_delegate', [{"wait_settlement": False}], indirect=True)
    @pytest.mark.parametrize('lock_mix_amt_unlock_eq_delegate', [{"wait_settlement": True}], indirect=True)
    def test_acc_lock_mix_withdrew_delegate_06(self, lock_mix_amt_unlock_eq_delegate, acc_mix_amt_delegate):
        """
        测试 账户已委托总和 < 赎回委托金额总和 < 锁定期已委托混合金额总和 + 账户金额总和
        @param lock_mix_amt_unlock_eq_delegate: 锁定期 已委托混合金额总和 BD.delegate_amount * 2 - lock_residue_amt
        @param acc_mix_amt_delegate: 账户已委托金额 总和 BD.delegate_amount * 2
        @Desc:
            -赎回委托金额 BD.delegate_limit * 210 赎回2100
        @Result:
            -账户已委托总和2000 < 赎回委托金额2100 < 账户委托总和 2000 + 锁定期 已委托混合金额总和 2000 - 200
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt, lock_residue_amt = lock_mix_amt_unlock_eq_delegate

        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        expect_data = {"Released": BD.von_k - lock_residue_amt, "RestrictingPlan": BD.von_k,
                       "ReleasedHes": BD.von_k, "RestrictingPlanHes": BD.von_k,
                       "LockReleasedHes": 0, "LockRestrictingPlanHes": 0}
        Assertion.assert_delegate_info_contain(delegate_info, expect_data)

        logger.info(f"-赎回委托金额 BD.delegate_limit * 210")
        withdrew_del_amt1 = BD.delegate_limit * 210
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt1, diff_restr=True)

        logger.info(f"-账户余额 BD.delegate_limit * 100 赎回1000")
        assert BD.delegate_amount - abs(amt_later - amt_before) < BD.von_limit

        logger.info(f"-账户锁仓 BD.delegate_limit * 100 质押扣减1000")
        expect_data = {'Pledge': {"old_value": BD.delegate_amount * 2,
                                  "new_value": BD.delegate_amount * 2 - BD.delegate_amount}}
        Assertion.assert_restr_amt(restr_before, restr_later, expect_data)

        logger.info(f"-锁定期 BD.delegate_limit * 10 自由金额赎回100")
        expect_data1 = {(3, lock_residue_amt, 0), (4, BD.delegate_limit * 10, 0)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data1)

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
    @pytest.mark.parametrize('create_lock_mix_amt_unlock_eq', [{"ManyAcc": True}], indirect=True)
    @pytest.mark.parametrize('acc_mix_amt_delegate', [{"wait_settlement": False}], indirect=True)
    @pytest.mark.parametrize('lock_mix_amt_unlock_eq_delegate', [{"wait_settlement": True}], indirect=True)
    def test_acc_lock_mix_withdrew_delegate_07(self, lock_mix_amt_unlock_eq_delegate, acc_mix_amt_delegate):
        """
        测试 账户已委托总和 < 赎回委托金额总和 < 锁定期已委托混合金额总和 + 账户金额总和
        @param lock_mix_amt_unlock_eq_delegate: 锁定期 已委托混合金额总和 BD.delegate_amount * 2 - lock_residue_amt
        @param acc_mix_amt_delegate: 账户已委托金额 总和 BD.delegate_amount * 2
        @Desc:
            -赎回账户自由金额 BD.delegate_limit * 350 赎回3500
        @Result:
            -账户委托 2000 + 锁定期自由金额委托1000 < 赎回委托金额3500 < 账户委托 2000 + 锁定期委托总和 1800
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt, lock_residue_amt = lock_mix_amt_unlock_eq_delegate

        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        expect_data = {"Released": BD.von_k - lock_residue_amt, "RestrictingPlan": BD.von_k,
                       "ReleasedHes": BD.von_k, "RestrictingPlanHes": BD.von_k,
                       "LockReleasedHes": 0, "LockRestrictingPlanHes": 0}
        Assertion.assert_delegate_info_contain(delegate_info, expect_data)

        logger.info(f"-赎回账户自由金额 BD.delegate_limit * 350")
        withdrew_del_amt1 = BD.delegate_limit * 350
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt1, diff_restr=True)

        logger.info(f"-账户余额 BD.delegate_limit * 100 赎回1000")
        assert BD.delegate_amount - abs(amt_later - amt_before) < BD.von_limit

        logger.info(f"-账户锁仓 赎回1000")
        expect_data = {'Pledge': {"old_value": BD.delegate_amount * 2,
                                  "new_value": BD.delegate_amount * 2 - BD.delegate_amount}}
        Assertion.assert_restr_amt(restr_before, restr_later, expect_data)

        logger.info(f"-锁定期 BD.delegate_limit * 100 自由金额赎回800 + 锁定期锁仓 赎回700")
        expect_data1 = {(3, lock_residue_amt, 0), (4, BD.delegate_amount - lock_residue_amt, BD.delegate_limit * 70)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data1)

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
    @pytest.mark.parametrize('create_lock_mix_amt_unlock_eq', [{"ManyAcc": True}], indirect=True)
    @pytest.mark.parametrize('acc_mix_amt_delegate', [{"wait_settlement": False}], indirect=True)
    @pytest.mark.parametrize('lock_mix_amt_unlock_eq_delegate', [{"wait_settlement": True}], indirect=True)
    def test_acc_lock_mix_withdrew_delegate_08(self, lock_mix_amt_unlock_eq_delegate, acc_mix_amt_delegate):
        """
        测试 赎回委托金额总和 >= 锁定期已委托混合金额总和 + 账户金额总和
        @param lock_mix_amt_unlock_eq_delegate: 锁定期 已委托混合金额总和 BD.delegate_amount * 2 - lock_residue_amt
        @param acc_mix_amt_delegate: 账户已委托金额 总和 BD.delegate_amount * 2
        @Desc:
            -赎回账户自由金额 BD.delegate_limit * 400 赎回 4000 -> fail
            -赎回账户自由金额 BD.delegate_limit * 380 赎回 3800
        @Result:
            -赎回委托金额总和(3800, 4000) >= 3800
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt, lock_residue_amt = lock_mix_amt_unlock_eq_delegate

        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        expect_data = {"Released": BD.von_k - lock_residue_amt, "RestrictingPlan": BD.von_k,
                       "ReleasedHes": BD.von_k, "RestrictingPlanHes": BD.von_k,
                       "LockReleasedHes": 0, "LockRestrictingPlanHes": 0}
        Assertion.assert_delegate_info_contain(delegate_info, expect_data)

        logger.info(f"-赎回账户自由金额 BD.delegate_limit * 400 -> fail")
        withdrew_del_amt1 = BD.delegate_limit * 400
        res = normal_aide0.delegate.withdrew_delegate(withdrew_del_amt1, private_key=normal_aide0_nt.del_pk)
        assert res['message'] == ERROR_CODE[301113]

        logger.info(f"-赎回账户自由金额 BD.delegate_limit * 380")
        withdrew_del_amt2 = BD.delegate_limit * 380
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt2, diff_restr=True)

        logger.info(f"-账户余额 BD.delegate_limit * 100 赎回1000")
        assert BD.delegate_amount - abs(amt_later - amt_before) < BD.von_limit

        logger.info(f"-账户锁仓 赎回1000")
        expect_data = {'Pledge': {"old_value": BD.delegate_amount * 2,
                                  "new_value": BD.delegate_amount * 2 - BD.delegate_amount}}
        Assertion.assert_restr_amt(restr_before, restr_later, expect_data)

        logger.info(f"-锁定期 BD.delegate_limit * 100 自由金额赎回800 + 锁定期锁仓 赎回1000")
        expect_data1 = {(3, lock_residue_amt, 0), (4, BD.delegate_amount - lock_residue_amt, BD.delegate_amount)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data1)


class TestAccMixValidLockMixHesitation(TestWithdrewDelegate):
    """测试赎回委托 / 账户委托(MixAmt同时)生效期、锁定期委托犹豫期 (09~12)"""

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
    @pytest.mark.parametrize('create_lock_mix_amt_unlock_eq', [{"ManyAcc": True}], indirect=True)
    @pytest.mark.parametrize('acc_mix_amt_delegate', [{"wait_settlement": True}], indirect=True)
    @pytest.mark.parametrize('lock_mix_amt_unlock_eq_delegate', [{"wait_settlement": False}], indirect=True)
    def test_acc_lock_mix_withdrew_delegate_09(self, acc_mix_amt_delegate, lock_mix_amt_unlock_eq_delegate):
        """
        测试 赎回委托金额 总和 < 锁定期已委托总和
        @param lock_mix_amt_unlock_eq_delegate: 锁定期 已委托混合金额总和 BD.delegate_amount * 2 - lock_residue_amt
        @param acc_mix_amt_delegate: 账户已委托金额 总和 BD.delegate_amount * 2
        @Setup:
            -注意继承 fixture 前后顺序会影响前置
        @Desc:
            -赎回锁定期自由金额 BD.delegate_limit * 50 赎回500
            -赎回锁定期自由金额 BD.delegate_limit * 50 锁仓金额BD.delegate_limit * 50 赎回1000
        @Result:
            -合计赎回1000 + 500 < 锁定期委托总和 1800
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt, lock_residue_amt = lock_mix_amt_unlock_eq_delegate

        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        expect_data = {"Released": BD.von_k, "RestrictingPlan": BD.von_k,  # 生效期金额
                       "ReleasedHes": 0, "RestrictingPlanHes": 0,  # 账户犹豫期金额
                       "LockReleasedHes": BD.von_k - lock_residue_amt, "LockRestrictingPlanHes": BD.von_k}  # 锁定犹豫期金额
        Assertion.assert_delegate_info_contain(delegate_info, expect_data)

        logger.info(f"-赎回锁定期自由金额 BD.delegate_limit * 50 赎回500")
        withdrew_del_amt1 = BD.delegate_limit * 50
        amt_before, amt_later, _, _ = withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt,
                                                                      withdrew_del_amt1)
        # 账户余额基本无变化,需要支付一次赎回委托的手续费
        assert abs(amt_later - amt_before) < BD.von_min
        expect_data1 = {(3, lock_residue_amt, 0), (4, withdrew_del_amt1, 0)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data1)

        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        expect_data = {"Released": BD.von_k, "RestrictingPlan": BD.von_k,
                       "ReleasedHes": 0, "RestrictingPlanHes": 0,
                       "LockReleasedHes": BD.von_k - lock_residue_amt - withdrew_del_amt1,
                       "LockRestrictingPlanHes": BD.von_k}
        Assertion.assert_delegate_info_contain(delegate_info, expect_data)

        logger.info(f"-赎回锁定期自由金额 BD.delegate_limit * 30 锁仓金额BD.delegate_limit * 70 赎回1000")
        withdrew_del_amt2 = BD.delegate_limit * 100
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt2, diff_restr=True)
        assert abs(amt_later - amt_before) < BD.von_min
        out_amt = BD.delegate_amount - lock_residue_amt
        released_amt = out_amt - withdrew_del_amt1
        restr_plan_amt = BD.delegate_amount - released_amt
        expect_data1 = {(3, lock_residue_amt, 0), (4, withdrew_del_amt1 + released_amt, restr_plan_amt)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data1)

        # 赎回锁定期锁仓金额不会改变锁仓计划,待解锁领取后会更改锁仓计划 数据对比没有变化: {}
        Assertion.assert_restr_amt(restr_before, restr_later, {})

        delegate_info_f = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        expect_data_f = {"Released": BD.von_k, "RestrictingPlan": BD.von_k,
                         "ReleasedHes": 0, "RestrictingPlanHes": 0,
                         "LockReleasedHes": 0,
                         "LockRestrictingPlanHes": BD.von_k - restr_plan_amt}
        Assertion.assert_delegate_info_contain(delegate_info_f, expect_data_f)

        acc_amt_before, red_acc_amt, restr_info_before, restr_info_later = \
            redeem_del_wait_unlock_diff_balance_restr(normal_aide0, normal_aide0_nt, diff_restr=True)
        assert abs(red_acc_amt - acc_amt_before - BD.delegate_amount) < BD.von_min

        logger.info(f"解锁并领取之后,验证锁仓计划")
        expect_data = {'Pledge': {"old_value": BD.delegate_amount * 2,
                                  "new_value": BD.delegate_amount * 2 - restr_plan_amt}}
        Assertion.assert_restr_amt(restr_info_before, restr_info_later, expect_data)

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
    @pytest.mark.parametrize('create_lock_mix_amt_unlock_eq', [{"ManyAcc": True}], indirect=True)
    @pytest.mark.parametrize('acc_mix_amt_delegate', [{"wait_settlement": True}], indirect=True)
    @pytest.mark.parametrize('lock_mix_amt_unlock_eq_delegate', [{"wait_settlement": False}], indirect=True)
    def test_acc_lock_mix_withdrew_delegate_10(self, acc_mix_amt_delegate, lock_mix_amt_unlock_eq_delegate):
        """
        测试 锁定期已委托总和 < 赎回委托金额总和 < 锁定期已委托混合金额总和 + 账户金额总和
        @param lock_mix_amt_unlock_eq_delegate: 锁定期 已委托混合金额总和 BD.delegate_amount * 2 - lock_residue_amt
        @param acc_mix_amt_delegate: 账户已委托金额 总和 BD.delegate_amount * 2
        @Desc:
            -赎回委托金额 BD.delegate_limit * 210 赎回2100
        @Result:
            -锁定期已委托总和1800 < 赎回委托金额2100 < 账户委托总和 2000 + 锁定期 已委托混合金额总和 1800
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt, lock_residue_amt = lock_mix_amt_unlock_eq_delegate

        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        expect_data = {"Released": BD.von_k, "RestrictingPlan": BD.von_k,
                       "ReleasedHes": 0, "RestrictingPlanHes": 0,
                       "LockReleasedHes": BD.von_k - lock_residue_amt, "LockRestrictingPlanHes": BD.von_k}
        Assertion.assert_delegate_info_contain(delegate_info, expect_data)

        logger.info(f"-赎回委托金额 BD.delegate_limit * 210")
        withdrew_del_amt1 = BD.delegate_limit * 210
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt1, diff_restr=True)

        # 账户余额基本无变化,需要支付一次赎回委托的手续费
        assert abs(amt_later - amt_before) < BD.von_min
        logger.info(f"-锁定期自由金额 赎回800 锁定期锁仓 赎回1000 / 账户自由金额赎回 300 ")
        lock_released = BD.delegate_amount - lock_residue_amt
        acc_released = withdrew_del_amt1 - (lock_released + BD.delegate_amount)
        expect_data1 = {(3, lock_residue_amt, 0), (4, lock_released + acc_released, BD.delegate_amount)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data1)

        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        expect_data = {"Released": BD.von_k - acc_released, "RestrictingPlan": BD.von_k,
                       "ReleasedHes": 0, "RestrictingPlanHes": 0,
                       "LockReleasedHes": 0, "LockRestrictingPlanHes": 0}
        Assertion.assert_delegate_info_contain(delegate_info, expect_data)
        Assertion.assert_restr_amt(restr_before, restr_later, {})

        acc_amt_before, red_acc_amt, restr_info_before, restr_info_later = \
            redeem_del_wait_unlock_diff_balance_restr(normal_aide0, normal_aide0_nt, diff_restr=True)
        release = lock_residue_amt + lock_released + acc_released
        assert abs(red_acc_amt - acc_amt_before - release) < BD.von_min

        logger.info(f"解锁并领取之后,验证锁仓计划")
        expect_data = {'Pledge': {"old_value": BD.delegate_amount * 2,
                                  "new_value": BD.delegate_amount * 2 - BD.delegate_amount}}
        Assertion.assert_restr_amt(restr_info_before, restr_info_later, expect_data)

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
    @pytest.mark.parametrize('create_lock_mix_amt_unlock_eq', [{"ManyAcc": True}], indirect=True)
    @pytest.mark.parametrize('acc_mix_amt_delegate', [{"wait_settlement": True}], indirect=True)
    @pytest.mark.parametrize('lock_mix_amt_unlock_eq_delegate', [{"wait_settlement": False}], indirect=True)
    def test_acc_lock_mix_withdrew_delegate_11(self, acc_mix_amt_delegate, lock_mix_amt_unlock_eq_delegate):
        """
        测试 锁定期已委托总和 < 赎回委托金额总和 < 锁定期已委托混合金额总和 + 账户金额总和
        @param lock_mix_amt_unlock_eq_delegate: 锁定期 已委托混合金额总和 BD.delegate_amount * 2 - lock_residue_amt
        @param acc_mix_amt_delegate: 账户已委托金额 总和 BD.delegate_amount * 2
        @Desc:
            -赎回委托金额 BD.delegate_limit * 350 赎回3500
        @Result:
            -锁定期委托 1800 + 账户自由金额1000 + 账户锁仓金额700 < 赎回委托金额3500 < 账户委托 2000 + 锁定期委托总和 1800
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt, lock_residue_amt = lock_mix_amt_unlock_eq_delegate

        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        expect_data = {"Released": BD.von_k, "RestrictingPlan": BD.von_k,
                       "ReleasedHes": 0, "RestrictingPlanHes": 0,
                       "LockReleasedHes": BD.von_k - lock_residue_amt, "LockRestrictingPlanHes": BD.von_k}
        Assertion.assert_delegate_info_contain(delegate_info, expect_data)

        logger.info(f"-赎回金额 BD.delegate_limit * 350")
        withdrew_del_amt1 = BD.delegate_limit * 350
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt1, diff_restr=True)

        assert abs(amt_later - amt_before) < BD.von_min
        logger.info(f"-锁定期自由金额 赎回800 锁定期锁仓 赎回1000 / 账户自由金额 赎回1000 账户锁仓 赎回700")
        lock_released = BD.delegate_amount - lock_residue_amt
        lock_plan = BD.delegate_amount
        acc_released = BD.delegate_amount
        acc_plan = withdrew_del_amt1 - (lock_released + lock_plan + acc_released)
        expect_data1 = {(3, lock_residue_amt, 0), (4, lock_released + acc_released, lock_plan + acc_plan)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data1)

        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        expect_data = {"Released": 0, "RestrictingPlan": BD.von_k - acc_plan,
                       "ReleasedHes": 0, "RestrictingPlanHes": 0,
                       "LockReleasedHes": 0, "LockRestrictingPlanHes": 0}
        Assertion.assert_delegate_info_contain(delegate_info, expect_data)
        Assertion.assert_restr_amt(restr_before, restr_later, {})

        acc_amt_before, red_acc_amt, restr_info_before, restr_info_later = \
            redeem_del_wait_unlock_diff_balance_restr(normal_aide0, normal_aide0_nt, diff_restr=True)
        release = lock_residue_amt + lock_released + acc_released
        assert abs(red_acc_amt - acc_amt_before - release) < BD.von_min

        logger.info(f"解锁并领取之后,验证锁仓计划")
        expect_data = {'Pledge': {"old_value": BD.delegate_amount * 2,
                                  "new_value": BD.delegate_amount * 2 - lock_plan - acc_plan}}
        Assertion.assert_restr_amt(restr_info_before, restr_info_later, expect_data)

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
    @pytest.mark.parametrize('create_lock_mix_amt_unlock_eq', [{"ManyAcc": True}], indirect=True)
    @pytest.mark.parametrize('acc_mix_amt_delegate', [{"wait_settlement": True}], indirect=True)
    @pytest.mark.parametrize('lock_mix_amt_unlock_eq_delegate', [{"wait_settlement": False}], indirect=True)
    def test_acc_lock_mix_withdrew_delegate_12(self, acc_mix_amt_delegate, lock_mix_amt_unlock_eq_delegate):
        """
        测试 赎回委托金额总和 >= 锁定期已委托混合金额总和 + 账户金额总和
        @param lock_mix_amt_unlock_eq_delegate: 锁定期 已委托混合金额总和 BD.delegate_amount * 2 - lock_residue_amt
        @param acc_mix_amt_delegate: 账户已委托金额 总和 BD.delegate_amount * 2
        @Desc:
            -赎回账户自由金额 BD.delegate_limit * 400 赎回 4000 -> fail
            -赎回账户自由金额 BD.delegate_limit * 380 赎回 3800
        @Result:
            -赎回委托金额总和(3800, 4000) >= 3800
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt, lock_residue_amt = lock_mix_amt_unlock_eq_delegate

        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        expect_data = {"Released": BD.von_k, "RestrictingPlan": BD.von_k,
                       "ReleasedHes": 0, "RestrictingPlanHes": 0,
                       "LockReleasedHes": BD.von_k - lock_residue_amt, "LockRestrictingPlanHes": BD.von_k}
        Assertion.assert_delegate_info_contain(delegate_info, expect_data)

        logger.info(f"-赎回金额 BD.delegate_limit * 400 -> fail")
        withdrew_del_amt1 = BD.delegate_limit * 400
        res = normal_aide0.delegate.withdrew_delegate(withdrew_del_amt1, private_key=normal_aide0_nt.del_pk)
        assert res['message'] == ERROR_CODE[301113]

        logger.info(f"-赎回金额 BD.delegate_limit * 380")
        withdrew_del_amt2 = BD.delegate_limit * 380
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt2, diff_restr=True)

        assert abs(amt_later - amt_before) < BD.von_min
        logger.info(f"-锁定期自由金额 赎回800 锁定期锁仓 赎回1000 / 账户自由金额 赎回1000 账户锁仓 赎回1000")
        lock_released = BD.delegate_amount - lock_residue_amt
        lock_plan = BD.delegate_amount
        acc_released = BD.delegate_amount
        acc_plan = withdrew_del_amt2 - (lock_released + lock_plan + acc_released)
        expect_data1 = {(3, lock_residue_amt, 0), (4, lock_released + acc_released, lock_plan + acc_plan)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data1)

        assert PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt) is None
        Assertion.assert_restr_amt(restr_before, restr_later, {})

        acc_amt_before, red_acc_amt, restr_info_before, restr_info_later = \
            redeem_del_wait_unlock_diff_balance_restr(normal_aide0, normal_aide0_nt, diff_restr=True)
        release = lock_residue_amt + lock_released + acc_released
        assert abs(red_acc_amt - acc_amt_before - release) < BD.von_min

        logger.info(f"解锁并领取之后,验证锁仓计划")
        expect_data = {'Pledge': {"old_value": BD.delegate_amount * 2,
                                  "new_value": BD.delegate_amount * 2 - lock_plan - acc_plan}}
        Assertion.assert_restr_amt(restr_info_before, restr_info_later, expect_data)


class TestAccLockMixAmtValid(TestWithdrewDelegate):
    """测试赎回委托 / 账户委托(MixAmt同时)生效期、锁定期委托生效期 (13~16)"""

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
    @pytest.mark.parametrize('create_lock_mix_amt_unlock_eq', [{"ManyAcc": True}], indirect=True)
    @pytest.mark.parametrize('acc_mix_amt_delegate', [{"wait_settlement": False}], indirect=True)
    @pytest.mark.parametrize('lock_mix_amt_unlock_eq_delegate', [{"wait_settlement": False}], indirect=True)
    def test_acc_lock_mix_withdrew_delegate_13(self, lock_mix_amt_unlock_eq_delegate, acc_mix_amt_delegate):
        """
        测试 赎回委托金额 总和 < 账户已委托总和
        @param lock_mix_amt_unlock_eq_delegate: 锁定期 已委托混合金额总和 BD.delegate_amount * 2 - lock_residue_amt
        @param acc_mix_amt_delegate: 账户已委托金额 总和 BD.delegate_amount * 2
        @Desc:
            -赎回账户自由金额 BD.delegate_limit * 50 赎回500
            -赎回账户自由金额 BD.delegate_limit * 50 锁仓金额BD.delegate_limit * 50 赎回1000
        @Result:
            -合计赎回1000 + 500 < 账户委托总和 BD.delegate_amount * 2
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt, lock_residue_amt = lock_mix_amt_unlock_eq_delegate
        wait_settlement(normal_aide0)
        logger.info(f"lock_acc_mix_delegate -> 都进入生效期")
        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        expect_data = {"Released": BD.von_k + (BD.von_k - lock_residue_amt), "RestrictingPlan": BD.von_k + BD.von_k,
                       "ReleasedHes": 0, "RestrictingPlanHes": 0,
                       "LockReleasedHes": 0, "LockRestrictingPlanHes": 0}
        Assertion.assert_delegate_info_contain(delegate_info, expect_data)

        logger.info(f"-赎回账户自由金额 BD.delegate_limit * 50")
        withdrew_del_amt1 = BD.delegate_limit * 50
        amt_before, amt_later, _, _ = withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt,
                                                                      withdrew_del_amt1)
        assert abs(amt_later - amt_before) < BD.von_min
        expect_data1 = {(3, lock_residue_amt, 0), (4, withdrew_del_amt1, 0)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data1)

        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        expect_data2 = {"Released": BD.von_k * 2 - lock_residue_amt - withdrew_del_amt1,
                        "RestrictingPlan": BD.von_k * 2,
                        "ReleasedHes": 0, "RestrictingPlanHes": 0,
                        "LockReleasedHes": 0, "LockRestrictingPlanHes": 0}
        Assertion.assert_delegate_info_contain(delegate_info, expect_data2)

        logger.info(f"-赎回账户自由金额 BD.delegate_limit * 100 赎回金额1000")
        withdrew_del_amt2 = BD.delegate_limit * 100
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt2, diff_restr=True)
        assert abs(amt_later - amt_before) < BD.von_min
        logger.info(f"-生效期金额合并后,赎回委托不区分账户,按先自由金额、后锁仓的规则赎回")
        expect_data3 = {(3, lock_residue_amt, 0), (4, withdrew_del_amt1 + withdrew_del_amt2, 0)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data3)
        logger.info(f"-锁仓计划无变化")
        Assertion.assert_restr_amt(restr_before, restr_later, {})

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
    @pytest.mark.parametrize('create_lock_mix_amt_unlock_eq', [{"ManyAcc": True}], indirect=True)
    @pytest.mark.parametrize('acc_mix_amt_delegate', [{"wait_settlement": False}], indirect=True)
    @pytest.mark.parametrize('lock_mix_amt_unlock_eq_delegate', [{"wait_settlement": False}], indirect=True)
    def test_acc_lock_mix_withdrew_delegate_14(self, lock_mix_amt_unlock_eq_delegate, acc_mix_amt_delegate):
        """
        测试 账户已委托总和 < 赎回委托金额总和 < 锁定期已委托混合金额总和 + 账户金额总和
        @param lock_mix_amt_unlock_eq_delegate: 锁定期 已委托混合金额总和 BD.delegate_amount * 2 - lock_residue_amt
        @param acc_mix_amt_delegate: 账户已委托金额 总和 BD.delegate_amount * 2
        @Desc:
            -赎回委托金额 BD.delegate_limit * 210 赎回2100
        @Result:
            -账户已委托总和2000 < 赎回委托金额2100 < 账户委托总和 2000 + 锁定期 已委托混合金额总和 2000 - 200
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt, lock_residue_amt = lock_mix_amt_unlock_eq_delegate
        wait_settlement(normal_aide0)
        logger.info(f"lock_acc_mix_delegate -> 都进入生效期")
        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        expect_data = {"Released": BD.von_k + (BD.von_k - lock_residue_amt), "RestrictingPlan": BD.von_k + BD.von_k,
                       "ReleasedHes": 0, "RestrictingPlanHes": 0,
                       "LockReleasedHes": 0, "LockRestrictingPlanHes": 0}
        Assertion.assert_delegate_info_contain(delegate_info, expect_data)

        logger.info(f"-赎回委托金额 BD.delegate_limit * 210")
        withdrew_del_amt1 = BD.delegate_limit * 210
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt1, diff_restr=True)
        assert abs(amt_later - amt_before) < BD.von_min
        logger.info(f"-生效期金额合并后,赎回委托不区分账户,自由金额1800、锁仓金额300")
        released = BD.von_k + (BD.von_k - lock_residue_amt)
        released_plan = withdrew_del_amt1 - released
        expect_data2 = {(3, lock_residue_amt, 0), (4, released, released_plan)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data2)

        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        expect_data3 = {"Released": 0,
                        "RestrictingPlan": BD.von_k * 2 - released_plan,
                        "ReleasedHes": 0, "RestrictingPlanHes": 0,
                        "LockReleasedHes": 0, "LockRestrictingPlanHes": 0}
        Assertion.assert_delegate_info_contain(delegate_info, expect_data3)
        Assertion.assert_restr_amt(restr_before, restr_later, {})

        acc_amt_before, red_acc_amt, restr_info_before, restr_info_later = \
            redeem_del_wait_unlock_diff_balance_restr(normal_aide0, normal_aide0_nt, diff_restr=True)
        release = lock_residue_amt + released
        assert abs(red_acc_amt - acc_amt_before - release) < BD.von_min
        logger.info(f"解锁并领取之后,验证锁仓计划")
        expect_data = {'Pledge': {"old_value": BD.delegate_amount * 2,
                                  "new_value": BD.delegate_amount * 2 - released_plan}}
        Assertion.assert_restr_amt(restr_info_before, restr_info_later, expect_data)

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
    @pytest.mark.parametrize('create_lock_mix_amt_unlock_eq', [{"ManyAcc": True}], indirect=True)
    @pytest.mark.parametrize('acc_mix_amt_delegate', [{"wait_settlement": False}], indirect=True)
    @pytest.mark.parametrize('lock_mix_amt_unlock_eq_delegate', [{"wait_settlement": False}], indirect=True)
    def test_acc_lock_mix_withdrew_delegate_15(self, lock_mix_amt_unlock_eq_delegate, acc_mix_amt_delegate):
        """
        测试 账户已委托总和 < 赎回委托金额总和 < 锁定期已委托混合金额总和 + 账户金额总和
        @param lock_mix_amt_unlock_eq_delegate: 锁定期 已委托混合金额总和 BD.delegate_amount * 2 - lock_residue_amt
        @param acc_mix_amt_delegate: 账户已委托金额 总和 BD.delegate_amount * 2
        @Desc:
            -赎回账户自由金额 BD.delegate_limit * 350 赎回3500
        @Result:
            -账户委托 2000 + 锁定期自由金额委托1000 < 赎回委托金额3500 < 账户委托 2000 + 锁定期委托总和 1800
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt, lock_residue_amt = lock_mix_amt_unlock_eq_delegate
        wait_settlement(normal_aide0)
        logger.info(f"lock_acc_mix_delegate -> 都进入生效期")
        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        expect_data = {"Released": BD.von_k + (BD.von_k - lock_residue_amt), "RestrictingPlan": BD.von_k + BD.von_k,
                       "ReleasedHes": 0, "RestrictingPlanHes": 0,
                       "LockReleasedHes": 0, "LockRestrictingPlanHes": 0}
        Assertion.assert_delegate_info_contain(delegate_info, expect_data)

        logger.info(f"-赎回金额 BD.delegate_limit * 350")
        withdrew_del_amt1 = BD.delegate_limit * 350
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt1, diff_restr=True)

        assert abs(amt_later - amt_before) < BD.von_min
        logger.info(f"-生效期金额合并后,赎回委托不区分账户, 自由金额1800 锁仓金额1700")
        released = BD.von_k + (BD.von_k - lock_residue_amt)
        released_plan = withdrew_del_amt1 - released
        expect_data2 = {(3, lock_residue_amt, 0), (4, released, released_plan)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data2)

        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        expect_data3 = {"Released": 0,
                        "RestrictingPlan": BD.von_k * 2 - released_plan,
                        "ReleasedHes": 0, "RestrictingPlanHes": 0,
                        "LockReleasedHes": 0, "LockRestrictingPlanHes": 0}
        Assertion.assert_delegate_info_contain(delegate_info, expect_data3)
        Assertion.assert_restr_amt(restr_before, restr_later, {})

        acc_amt_before, red_acc_amt, restr_info_before, restr_info_later = \
            redeem_del_wait_unlock_diff_balance_restr(normal_aide0, normal_aide0_nt, diff_restr=True)
        release = lock_residue_amt + released
        assert abs(red_acc_amt - acc_amt_before - release) < BD.von_min
        logger.info(f"解锁并领取之后,验证锁仓计划")
        expect_data = {'Pledge': {"old_value": BD.delegate_amount * 2,
                                  "new_value": BD.delegate_amount * 2 - released_plan}}
        Assertion.assert_restr_amt(restr_info_before, restr_info_later, expect_data)

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
    @pytest.mark.parametrize('create_lock_mix_amt_unlock_eq', [{"ManyAcc": True}], indirect=True)
    @pytest.mark.parametrize('acc_mix_amt_delegate', [{"wait_settlement": False}], indirect=True)
    @pytest.mark.parametrize('lock_mix_amt_unlock_eq_delegate', [{"wait_settlement": False}], indirect=True)
    def test_acc_lock_mix_withdrew_delegate_16(self, lock_mix_amt_unlock_eq_delegate, acc_mix_amt_delegate):
        """
        测试 赎回委托金额总和 >= 锁定期已委托混合金额总和 + 账户金额总和
        @param lock_mix_amt_unlock_eq_delegate: 锁定期 已委托混合金额总和 BD.delegate_amount * 2 - lock_residue_amt
        @param acc_mix_amt_delegate: 账户已委托金额 总和 BD.delegate_amount * 2
        @Desc:
            -赎回账户自由金额 BD.delegate_limit * 400 赎回 4000 -> fail
            -赎回账户自由金额 BD.delegate_limit * 380 赎回 3800
        @Result:
            -赎回委托金额总和(3800, 4000) >= 3800
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt, lock_residue_amt = lock_mix_amt_unlock_eq_delegate
        wait_settlement(normal_aide0)
        logger.info(f"lock_acc_mix_delegate -> 都进入生效期")
        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        expect_data = {"Released": BD.von_k + (BD.von_k - lock_residue_amt), "RestrictingPlan": BD.von_k + BD.von_k,
                       "ReleasedHes": 0, "RestrictingPlanHes": 0,
                       "LockReleasedHes": 0, "LockRestrictingPlanHes": 0}
        Assertion.assert_delegate_info_contain(delegate_info, expect_data)

        logger.info(f"-赎回账户自由金额 BD.delegate_limit * 400 -> fail")
        withdrew_del_amt1 = BD.delegate_limit * 400
        res = normal_aide0.delegate.withdrew_delegate(withdrew_del_amt1, private_key=normal_aide0_nt.del_pk)
        assert res['message'] == ERROR_CODE[301113]

        logger.info(f"-赎回账户自由金额 BD.delegate_limit * 380")
        withdrew_del_amt2 = BD.delegate_limit * 380
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt2, diff_restr=True)

        assert abs(amt_later - amt_before) < BD.von_min
        logger.info(f"-生效期金额合并后,赎回委托不区分账户, 自由金额1800 锁仓金额1700")
        released = BD.von_k + (BD.von_k - lock_residue_amt)
        released_plan = withdrew_del_amt2 - released
        expect_data2 = {(3, lock_residue_amt, 0), (4, released, released_plan)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data2)

        assert PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt) is None
        Assertion.assert_restr_amt(restr_before, restr_later, {})

        acc_amt_before, red_acc_amt, restr_info_before, restr_info_later = \
            redeem_del_wait_unlock_diff_balance_restr(normal_aide0, normal_aide0_nt, diff_restr=True)
        release = lock_residue_amt + released
        assert abs(red_acc_amt - acc_amt_before - release) < BD.von_min
        logger.info(f"解锁并领取之后,验证锁仓计划")
        expect_data = {'Pledge': {"old_value": BD.delegate_amount * 2,
                                  "new_value": 0}}
        Assertion.assert_restr_amt(restr_info_before, restr_info_later, expect_data)


class TestAccMixDiffCycle(TestWithdrewDelegate):
    """
    账户Mix金额(不同周期)
    - 自由金额 犹豫期  /  锁仓金额 生效期  -> TestAccFreeHesitationRestrValid
        * 锁定期Mix金额
            - 同时犹豫期
            - 自由金额 犹豫期 / 锁仓金额 生效期  -> setup_data_01
            - 自由金额 生效期 / 锁仓金额 犹豫期  -> setup_data_02
            - 同时生效期
    - 自由金额 生效期  /  锁仓金额 犹豫期
        * 锁定期Mix金额
            - 同时犹豫期
            - 自由金额 犹豫期 / 锁仓金额 生效期  -> setup_data_03
            - 自由金额 生效期 / 锁仓金额 犹豫期  -> setup_data_04
            - 同时生效期
    # 单fixture 已经无法满足需求, 组合fixture 要拼凑编写不同场景 解读成本高
    # 尝试解决方案:
        - 1.按场景 一步一步编写出前置,代码重复度高,基本无可复用性
        - 2.自定义数据结构组合,解析数据结构,按传入数据完成前置 (时间成本高)
        - 3.根据现有fixture 组合成基础前置,不满足需求在用例中继续委托,得到不纯粹的前置
            例: - 需要场景: 账户 自由金额 犹豫期  /  锁仓金额 生效期   锁定期 自由金额 犹豫期 / 锁仓金额 生效期
                - 基础前置: 账户自由金额 锁仓金额 / 都在生效期, 锁定期 自由金额 锁仓金额 / 都在生效期
                - 补充前置: 账户在发起自由金额委托  / 冻结期自由金额在次委托
    """
    setup_data_01 = [{"Acc": {"restr_wait": True}, "Lock": {"restr_wait": True}}]
    # 表示想先使用锁定期中自由金额,即锁定期解锁周期不能相等,需要自由金额解锁周期更长
    setup_data_02 = [{"Acc": {"restr_wait": True}, "Lock": {"free_wait": True}}]
    setup_data_03 = [{"Acc": {"free_wait": True}, "Lock": {"restr_wait": True}}]
    setup_data_04 = [{"Acc": {"free_wait": True}, "Lock": {"free_wait": True}}]
    pass


class TestAccFreeHesitationRestrValid(TestAccMixDiffCycle):
    """ 测试赎回委托 账户混合金额 自由金额 犹豫期  /  锁仓金额 生效期 """

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
    @pytest.mark.parametrize('create_lock_mix_amt_unlock_eq', [{"ManyAcc": True}], indirect=True)
    @pytest.mark.parametrize('acc_mix_diff_cycle_delegate', [{"restr_wait": True}], indirect=True)
    @pytest.mark.parametrize('lock_mix_amt_unlock_eq_delegate', [{"wait_settlement": False}], indirect=True)
    def test_lock_mix_hesitation(self, acc_mix_diff_cycle_delegate, lock_mix_amt_unlock_eq_delegate):
        """
        锁定期Mix金额 - 同时犹豫期
        @param acc_mix_diff_cycle_delegate: 自由金额 犹豫期  /  锁仓金额 生效期
        @param lock_mix_amt_unlock_eq_delegate: 锁定期Mix金额 - 同时犹豫期
        @Desc:
            - 赎回500     -> acc_free 回账户余额500
            - 再赎回1000  -> acc_free 回账户余额500 冻结自由金额500
            - 再赎回1000  -> 冻结自由金额300 冻结锁仓金额700
            - 再赎回1000  -> 冻结锁仓金额300 冻结锁仓金额700
            - 再赎回500   -> fail
            - 再赎回300   -> 冻结锁仓金额300
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt, lock_residue_amt = lock_mix_amt_unlock_eq_delegate
        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        expect_data = {"Released": 0, "RestrictingPlan": BD.von_k,
                       "ReleasedHes": BD.von_k, "RestrictingPlanHes": 0,
                       "LockReleasedHes": BD.von_k - lock_residue_amt, "LockRestrictingPlanHes": BD.von_k}
        Assertion.assert_delegate_info_contain(delegate_info, expect_data)

        logger.info(f"- 赎回500     -> acc_free 回账户余额500")
        withdrew_del_amt1 = BD.delegate_limit * 50
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt1, diff_restr=True)
        assert withdrew_del_amt1 - abs(amt_later - amt_before) < BD.von_min

        logger.info(f"- 再赎回1000  -> acc_free 回账户余额500 冻结自由金额500")
        withdrew_del_amt2 = BD.delegate_limit * 100
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt2, diff_restr=True)
        assert withdrew_del_amt1 - abs(amt_later - amt_before) < BD.von_min
        expect_data2 = {(3, lock_residue_amt, 0), (4, withdrew_del_amt1, 0)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data2)

        logger.info(f"- 再赎回1000  -> 冻结自由金额300 冻结锁仓金额700")
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt2, diff_restr=True)
        assert abs(amt_later - amt_before) < BD.von_min
        released = (BD.von_k - lock_residue_amt) - withdrew_del_amt1
        released_plan = BD.von_k - released
        expect_data2 = {(3, lock_residue_amt, 0), (4, withdrew_del_amt1 + released, released_plan)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data2)

        logger.info(f"- 再赎回1000  -> 冻结锁仓金额300 冻结锁仓金额700")
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt2, diff_restr=True)
        assert abs(amt_later - amt_before) < BD.von_min
        expect_data2 = {(3, lock_residue_amt, 0), (4, withdrew_del_amt1 + released, released_plan + BD.von_k)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data2)

        logger.info(f"- 再赎回500   -> fail")
        res = normal_aide0.delegate.withdrew_delegate(withdrew_del_amt1, private_key=normal_aide0_nt.del_pk)
        assert res['message'] == ERROR_CODE[301113]

        logger.info(f"- 再赎回300   -> 冻结锁仓金额300")
        withdrew_del_amt3 = BD.delegate_limit * 30
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt3, diff_restr=True)
        assert abs(amt_later - amt_before) < BD.von_min
        released_plan_2 = released_plan + BD.von_k + withdrew_del_amt3
        expect_data2 = {(3, lock_residue_amt, 0), (4, withdrew_del_amt1 + released, released_plan_2)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data2)

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 3, }], indirect=True)
    @pytest.mark.parametrize('create_lock_mix_amt_unlock_eq', [{"ManyAcc": True}], indirect=True)
    @pytest.mark.parametrize('acc_mix_diff_cycle_delegate', [{"restr_wait": True}], indirect=True)
    @pytest.mark.parametrize('lock_mix_amt_unlock_eq_delegate', [{"wait_settlement": True}], indirect=True)
    def test_lock_mix_valid(self, lock_mix_amt_unlock_eq_delegate, acc_mix_diff_cycle_delegate):
        """
        锁定期Mix金额 - 同时生效期
        @param acc_mix_diff_cycle_delegate: 自由金额 犹豫期  /  锁仓金额 生效期
        @param lock_mix_amt_unlock_eq_delegate: 锁定期Mix金额 - 同时生效期
        @Desc:
            - 生效期赎回规则 先自由 再锁仓
            - 再赎回1000  -> 赎回自由金额1000并冻结
            - 再赎回1000  -> 赎回自由金额800+锁仓200并冻结
            - 再赎回1800  -> 赎回锁仓金额1800并冻结
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt, lock_residue_amt = lock_mix_amt_unlock_eq_delegate
        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        expect_data = {"Released": BD.von_k - lock_residue_amt, "RestrictingPlan": BD.von_k * 2,
                       "ReleasedHes": BD.von_k, "RestrictingPlanHes": 0,
                       "LockReleasedHes": 0, "LockRestrictingPlanHes": 0}
        Assertion.assert_delegate_info_contain(delegate_info, expect_data)

        logger.info(f"- 再赎回1000  -> 账户犹豫期自由金额1000")
        withdrew_del_amt1 = BD.delegate_limit * 100
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt1, diff_restr=True)
        assert withdrew_del_amt1 - abs(amt_later - amt_before) < BD.von_min
        expect_data2 = {(4, lock_residue_amt, 0)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data2)

        logger.info(f"- 再赎回1000  -> 赎回自由金额800+锁仓200并冻结")
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt1, diff_restr=True)
        assert abs(amt_later - amt_before) < BD.von_min
        released = BD.von_k - lock_residue_amt
        released_plan = BD.von_k - released
        expect_data2 = {(4, lock_residue_amt, 0), (6, released, released_plan)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data2)

        logger.info(f"- 再赎回1800  -> 赎回锁仓金额1800并冻结")
        withdrew_del_amt2 = BD.delegate_limit * 180
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt2, diff_restr=True)
        assert abs(amt_later - amt_before) < BD.von_min
        expect_data2 = {(4, lock_residue_amt, 0), (6, released, released_plan + withdrew_del_amt2)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data2)

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
    @pytest.mark.parametrize('create_lock_mix_amt_unlock_eq', [{"ManyAcc": True}], indirect=True)
    @pytest.mark.parametrize('acc_lock_mix_diff_cycle_del', TestAccMixDiffCycle.setup_data_01, indirect=True)
    def test_lock_free_hesitation_restr_valid(self, acc_lock_mix_diff_cycle_del, create_lock_mix_amt_unlock_eq):
        """
        锁定期混合金额 自由金额 犹豫期 / 锁仓金额 生效期
        @param acc_lock_mix_diff_cycle_del: 账户混合金额 自由金额 犹豫期  /  锁仓金额 生效期
        @param create_lock_mix_amt_unlock_eq: 创建锁定期混合金额解锁周期相等
        @Desc:
            - 此时所有已委托总额 = 4000
            - 赎回1500  -> 赎回账户自由金额1000 + 锁定期自由金额500并冻结
            - 再赎回2000  -> 锁定期自由金额500并冻结 + 账户锁仓金额1000并冻结 + 锁定期锁仓金额500并冻结
            - 再赎回500   -> 锁定期锁仓金额500并冻结
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt = create_lock_mix_amt_unlock_eq
        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        expect_data = {"Released": 0, "RestrictingPlan": BD.von_k * 2,
                       "ReleasedHes": BD.von_k, "RestrictingPlanHes": 0,
                       "LockReleasedHes": BD.von_k, "LockRestrictingPlanHes": 0}
        Assertion.assert_delegate_info_contain(delegate_info, expect_data)

        logger.info(f"- 赎回1500  -> 赎回账户自由金额1000 + 锁定期自由金额500并冻结")
        withdrew_del_amt1 = BD.delegate_limit * 150
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt1, diff_restr=True)
        assert BD.delegate_amount - abs(amt_later - amt_before) < BD.von_min

        expect_data2 = {(4, BD.delegate_limit * 50, 0)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data2)

        logger.info(f"- 再赎回2000  -> 锁定期自由金额500并冻结 + 账户锁仓金额1000并冻结 + 锁定期锁仓金额500并冻结")
        withdrew_del_amt2 = BD.delegate_limit * 200
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt2, diff_restr=True)
        assert abs(amt_later - amt_before) < BD.von_min

        expect_data3 = {(4, BD.delegate_limit * 50 * 2, withdrew_del_amt1)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data3)

        logger.info(f"- 再赎回500   -> 锁定期锁仓金额500并冻结")
        withdrew_del_amt3 = BD.delegate_limit * 50
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt3, diff_restr=True)
        assert abs(amt_later - amt_before) < BD.von_min

        expect_data4 = {(4, BD.delegate_limit * 50 * 2, withdrew_del_amt1 + withdrew_del_amt3)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data4)
        pass

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 5, }], indirect=True)
    @pytest.mark.parametrize('create_lock_restr_amt', [{"ManyAcc": True, "MixAcc": True}], indirect=True)
    @pytest.mark.parametrize('acc_lock_mix_diff_cycle_del_free_valid', TestAccMixDiffCycle.setup_data_02, indirect=True)
    def test_lock_free_valid_restr_hesitation(self, create_lock_mix_amt_free_unlock_long,
                                              acc_lock_mix_diff_cycle_del_free_valid):
        """
        锁定期混合金额 自由金额 生效期 / 锁仓金额 犹豫期
        @param acc_lock_mix_diff_cycle_del_free_valid: 账户混合金额 自由金额 犹豫期  /  锁仓金额 生效期
        @param create_lock_mix_amt_free_unlock_long: 创建锁定期混合金额自由金额解锁周期更长
        @Desc:
            - 此时所有已委托总额 = 4000
            - 赎回1500    -> 赎回账户自由金额1000 + 锁定期锁仓金额500并冻结
            - 再赎回2000  -> 锁定期锁仓金额500并冻结 + 生效期自由金额1000并冻结 + 生效期锁仓金额500并冻结
            - 再赎回500   -> 生效期锁仓金额500并冻结
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt = create_lock_mix_amt_free_unlock_long
        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        expect_data = {"Released": BD.von_k, "RestrictingPlan": BD.von_k,
                       "ReleasedHes": BD.von_k, "RestrictingPlanHes": 0,
                       "LockReleasedHes": 0, "LockRestrictingPlanHes": BD.von_k}
        Assertion.assert_delegate_info_contain(delegate_info, expect_data)
        Assertion.del_lock_info_zero_money(normal_aide0, normal_aide0_nt)

        logger.info(f"- 赎回1500  -> 赎回账户自由金额1000 + 锁定期锁仓金额500并冻结")
        withdrew_del_amt1 = BD.delegate_limit * 150
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt1, diff_restr=True)
        assert BD.delegate_amount - abs(amt_later - amt_before) < BD.von_min
        expect_data1 = {(8, 0, BD.delegate_limit * 50)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data1)

        logger.info(f"- 再赎回2000  -> 锁定期锁仓金额500并冻结 + 生效期自由金额1000并冻结 + 生效期锁仓金额500并冻结")
        withdrew_del_amt2 = BD.delegate_limit * 200
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt2, diff_restr=True)
        assert abs(amt_later - amt_before) < BD.von_min

        expect_data2 = {(8, BD.von_k, BD.delegate_limit * 50 + BD.von_k)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data2)

        logger.info(f"- 再赎回500   -> 锁定期锁仓金额500并冻结")
        withdrew_del_amt3 = BD.delegate_limit * 50
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt3, diff_restr=True)
        assert abs(amt_later - amt_before) < BD.von_min

        expect_data3 = {(8, BD.von_k, BD.delegate_limit * 50 + BD.von_k + withdrew_del_amt3)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data3)
        pass


class TestAccFreeValidRestrHesitation(TestAccMixDiffCycle):
    """ 测试赎回委托 账户混合金额  自由金额 生效期  /  锁仓金额 犹豫期 """

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
    @pytest.mark.parametrize('create_lock_mix_amt_unlock_eq', [{"ManyAcc": True}], indirect=True)
    @pytest.mark.parametrize('lock_mix_amt_unlock_eq_delegate', [{"wait_settlement": False}], indirect=True)
    @pytest.mark.parametrize('acc_mix_diff_cycle_delegate', [{"free_wait": True}], indirect=True)
    def test_lock_mix_hesitation(self, acc_mix_diff_cycle_delegate, lock_mix_amt_unlock_eq_delegate):
        """
        锁定期Mix金额 - 同时犹豫期
        @param acc_mix_diff_cycle_delegate: 自由金额 生效期  /  锁仓金额 犹豫期
        @param lock_mix_amt_unlock_eq_delegate: 锁定期Mix金额 - 同时犹豫期
        @Desc:
            - 赎回1000   ->  账户锁仓金额1000
            - 赎回1000   ->  锁定期自由金额800 + 锁定期锁仓金额200  进入锁定期
            - 赎回1800   ->  锁定期锁仓金额800 + 生效期自由金额1000 进入锁定期
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt, lock_residue_amt = lock_mix_amt_unlock_eq_delegate
        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        expect_data = {"Released": BD.von_k, "RestrictingPlan": 0,
                       "ReleasedHes": 0, "RestrictingPlanHes": BD.von_k,
                       "LockReleasedHes": BD.von_k - lock_residue_amt, "LockRestrictingPlanHes": BD.von_k}
        Assertion.assert_delegate_info_contain(delegate_info, expect_data)
        expect_data1 = {(3, lock_residue_amt, 0)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data1)

        logger.info(f"- 赎回1000   ->  账户锁仓金额1000")
        withdrew_del_amt1 = BD.delegate_limit * 100
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt1, diff_restr=True)
        assert abs(amt_later - amt_before) < BD.von_min
        expect_data2 = {(3, lock_residue_amt, 0)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data2)
        expect_data3 = {'Pledge': {"old_value": BD.von_k * 2, "new_value": BD.von_k}}
        Assertion.assert_restr_amt(restr_before, restr_later, expect_data3)

        logger.info(f"- 赎回1000   ->  锁定期自由金额800 + 锁定期锁仓金额200  进入锁定期")
        withdrew_del_amt2 = BD.delegate_limit * 100
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt2, diff_restr=True)
        assert abs(amt_later - amt_before) < BD.von_min
        expect_data4 = {(3, lock_residue_amt, 0), (4, BD.von_k - lock_residue_amt, lock_residue_amt)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data4)
        Assertion.assert_restr_amt(restr_before, restr_later, {})

        logger.info(f"- 赎回1800   ->  锁定期锁仓金额800 + 生效期自由金额1000 进入锁定期")
        withdrew_del_amt2 = BD.delegate_limit * 180
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt2, diff_restr=True)
        assert abs(amt_later - amt_before) < BD.von_min
        expect_data4 = {(3, lock_residue_amt, 0), (4, BD.von_k - lock_residue_amt + BD.von_k, BD.von_k)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data4)
        Assertion.assert_restr_amt(restr_before, restr_later, {})

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 3, }], indirect=True)
    @pytest.mark.parametrize('create_lock_mix_amt_unlock_eq', [{"ManyAcc": True}], indirect=True)
    @pytest.mark.parametrize('acc_mix_diff_cycle_delegate', [{"free_wait": True}], indirect=True)
    @pytest.mark.parametrize('lock_mix_amt_unlock_eq_delegate', [{"wait_settlement": True}], indirect=True)
    def test_lock_mix_valid(self, lock_mix_amt_unlock_eq_delegate, acc_mix_diff_cycle_delegate):
        """
        锁定期Mix金额 - 同时生效期
        @param acc_mix_diff_cycle_delegate: 自由金额 生效期  /  锁仓金额 犹豫期
        @param lock_mix_amt_unlock_eq_delegate: 锁定期Mix金额 - 同时生效期
        @Desc:
            - 生效期赎回规则 先自由 再锁仓
            - 赎回1000   ->  账户锁仓金额1000
            - 赎回1000   ->  锁定期自由金额800 + 锁定期锁仓金额200  进入锁定期
            - 赎回1800   ->  锁定期锁仓金额800 + 生效期自由金额1000 进入锁定期
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt, lock_residue_amt = lock_mix_amt_unlock_eq_delegate
        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        expect_data = {"Released": BD.von_k * 2 - lock_residue_amt, "RestrictingPlan": BD.von_k,
                       "ReleasedHes": 0, "RestrictingPlanHes": BD.von_k,
                       "LockReleasedHes": 0, "LockRestrictingPlanHes": 0}
        Assertion.assert_delegate_info_contain(delegate_info, expect_data)

        logger.info(f"- 赎回1000   ->  账户锁仓金额1000")
        withdrew_del_amt1 = BD.delegate_limit * 100
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt1, diff_restr=True)
        assert abs(amt_later - amt_before) < BD.von_min
        expect_data2 = {(4, lock_residue_amt, 0)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data2)
        expect_data3 = {'Pledge': {"old_value": BD.von_k * 2, "new_value": BD.von_k}}
        Assertion.assert_restr_amt(restr_before, restr_later, expect_data3)

        logger.info(f"- 赎回1000   ->  生效期自由金额1000  进入锁定期")
        withdrew_del_amt2 = BD.delegate_limit * 100
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt2, diff_restr=True)
        assert abs(amt_later - amt_before) < BD.von_min
        expect_data4 = {(4, lock_residue_amt, 0), (6, BD.von_k, 0)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data4)

        logger.info(f"- 赎回1800   ->  生效期自由金额800 + 生效期锁仓金额1000 进入锁定期")
        withdrew_del_amt2 = BD.delegate_limit * 180
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt2, diff_restr=True)
        assert abs(amt_later - amt_before) < BD.von_min
        expect_data4 = {(4, lock_residue_amt, 0), (6, BD.von_k * 2 - lock_residue_amt, BD.von_k)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data4)
        Assertion.assert_restr_amt(restr_before, restr_later, {})

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
    @pytest.mark.parametrize('create_lock_mix_amt_unlock_eq', [{"ManyAcc": True}], indirect=True)
    @pytest.mark.parametrize('acc_lock_mix_diff_cycle_del', TestAccMixDiffCycle.setup_data_03, indirect=True)
    def test_lock_free_hesitation_restr_valid(self, acc_lock_mix_diff_cycle_del, create_lock_mix_amt_unlock_eq):
        """
        锁定期混合金额 自由金额 犹豫期 / 锁仓金额 生效期
        @param acc_lock_mix_diff_cycle_del: 账户混合金额 自由金额 生效期  /  锁仓金额 犹豫期
        @param create_lock_mix_amt_unlock_eq: 创建锁定期混合金额解锁周期相等
        @Desc:
            - 此时所有已委托总额 = 4000
            - 赎回1500    -> 赎回账户锁仓金额1000 + 锁定期自由金额500并冻结
            - 再赎回2000  -> 锁定期自由金额500并冻结 + 生效期自由金额1000并冻结 + 生效期锁仓金额500并冻结
            - 再赎回500   -> 生效期锁仓金额500并冻结
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt = create_lock_mix_amt_unlock_eq
        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        expect_data = {"Released": BD.von_k, "RestrictingPlan": BD.von_k,
                       "ReleasedHes": 0, "RestrictingPlanHes": BD.von_k,
                       "LockReleasedHes": BD.von_k, "LockRestrictingPlanHes": 0}
        Assertion.assert_delegate_info_contain(delegate_info, expect_data)

        logger.info(f"- 赎回1500    -> 赎回账户锁仓金额1000 + 锁定期自由金额500并冻结")
        withdrew_del_amt1 = BD.delegate_limit * 150
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt1, diff_restr=True)
        assert abs(amt_later - amt_before) < BD.von_min
        expect_data2 = {(4, BD.delegate_limit * 50, 0)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data2)
        expect_data3 = {'Pledge': {"old_value": BD.von_k * 2, "new_value": BD.von_k}}
        Assertion.assert_restr_amt(restr_before, restr_later, expect_data3)

        logger.info(f"- 再赎回2000  -> 锁定期自由金额500并冻结 + 生效期自由金额1000并冻结 + 生效期锁仓金额500并冻结")
        withdrew_del_amt2 = BD.delegate_limit * 200
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt2, diff_restr=True)
        assert abs(amt_later - amt_before) < BD.von_min
        expect_data4 = {(4, BD.von_k * 2, BD.delegate_limit * 50)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data4)
        Assertion.assert_restr_amt(restr_before, restr_later, {})

        logger.info(f"- 再赎回500   -> 锁定期锁仓金额500并冻结")
        withdrew_del_amt3 = BD.delegate_limit * 50
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt3, diff_restr=True)
        assert abs(amt_later - amt_before) < BD.von_min
        expect_data5 = {(4, BD.von_k * 2, BD.von_k)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data5)
        Assertion.assert_restr_amt(restr_before, restr_later, {})

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 5, }], indirect=True)
    @pytest.mark.parametrize('create_lock_restr_amt', [{"ManyAcc": True, "MixAcc": True}], indirect=True)
    @pytest.mark.parametrize('acc_lock_mix_diff_cycle_del_free_valid', TestAccMixDiffCycle.setup_data_04, indirect=True)
    def test_lock_free_valid_restr_hesitation(self, create_lock_mix_amt_free_unlock_long,
                                              acc_lock_mix_diff_cycle_del_free_valid):
        """
        锁定期混合金额 自由金额 生效期 / 锁仓金额 犹豫期
        @param acc_lock_mix_diff_cycle_del_free_valid: 账户混合金额 自由金额 生效期  /  锁仓金额 犹豫期
        @param create_lock_mix_amt_free_unlock_long: 创建锁定期混合金额自由金额解锁周期更长
        @Desc:
            - 此时所有已委托总额 = 4000
            - 赎回1500    -> 账户锁仓金额1000 + 锁定期锁仓金额500并冻结
            - 再赎回2000  -> 锁定期锁仓金额500并冻结 + 生效期自由金额1500并冻结
            - 再赎回500   -> 生效期自由金额500并冻结
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt = create_lock_mix_amt_free_unlock_long
        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        expect_data = {"Released": BD.von_k * 2, "RestrictingPlan": 0,
                       "ReleasedHes": 0, "RestrictingPlanHes": BD.von_k,
                       "LockReleasedHes": 0, "LockRestrictingPlanHes": BD.von_k}
        Assertion.assert_delegate_info_contain(delegate_info, expect_data)
        Assertion.del_lock_info_zero_money(normal_aide0, normal_aide0_nt)

        logger.info(f"- 赎回1500    -> 账户锁仓金额1000 + 锁定期锁仓金额500并冻结")
        withdrew_del_amt1 = BD.delegate_limit * 150
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt1, diff_restr=True)
        assert abs(amt_later - amt_before) < BD.von_min
        expect_data1 = {(8, 0, BD.delegate_limit * 50)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data1)
        expect_data2 = {'Pledge': {"old_value": BD.von_k * 2, "new_value": BD.von_k}}
        Assertion.assert_restr_amt(restr_before, restr_later, expect_data2)

        logger.info(f"- 再赎回2000  -> 锁定期锁仓金额500并冻结 + 生效期自由金额1500并冻结")
        withdrew_del_amt2 = BD.delegate_limit * 200
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt2, diff_restr=True)
        assert abs(amt_later - amt_before) < BD.von_min
        expect_data3 = {(8, BD.delegate_limit * 50 + BD.von_k, BD.von_k)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data3)

        logger.info(f"- 再赎回500   -> 生效期自由金额500并冻结")
        withdrew_del_amt3 = BD.delegate_limit * 50
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt3, diff_restr=True)
        assert abs(amt_later - amt_before) < BD.von_min
        expect_data4 = {(8, BD.von_k * 2, BD.von_k)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data4)


class TestLockMixDiffCycle(TestWithdrewDelegate):
    """
    锁定期Mix金额(不同周期)
    - 自由金额 犹豫期  /  锁仓金额 生效期
        * 账户Mix金额
            - 同时犹豫期
            - 同时生效期
    - 自由金额 生效期  /  锁仓金额 犹豫期
        * 账户Mix金额
            - 同时犹豫期
            - 同时生效期
    """
    pass


class TestLockFreeHesitationRestrValid(TestLockMixDiffCycle):
    """ 测试赎回委托 锁定期混合金额 自由金额 犹豫期  /  锁仓金额 生效期 """

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
    @pytest.mark.parametrize('create_lock_mix_amt_unlock_eq', [{"ManyAcc": True}], indirect=True)
    @pytest.mark.parametrize('acc_mix_amt_delegate', [{"wait_settlement": False}], indirect=True)
    def test_acc_mix_hesitation(self, lock_mix_diff_cycle_delegate, acc_mix_amt_delegate):
        """
        @param lock_mix_diff_cycle_delegate: 锁定期 自由金额 犹豫期  /  锁仓金额 生效期
        @param acc_mix_amt_delegate: 账户Mix金额 - 同时犹豫期
        @Desc:
            - 此时所有已委托总额 = 4000
            - 赎回1500    -> 账户自由金额1000 + 账户锁仓金额500 锁仓计划质押金额-500
            - 再赎回2000  -> 账户锁仓金额500 锁仓计划质押金额-500 + 锁定期自由金额1000 重新冻结 + 生效期锁仓金额500并冻结
            - 再赎回500   -> 生效期锁仓金额500并冻结
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt = acc_mix_amt_delegate
        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        expect_data = {"Released": 0, "RestrictingPlan": BD.von_k,
                       "ReleasedHes": BD.von_k, "RestrictingPlanHes": BD.von_k,
                       "LockReleasedHes": BD.von_k, "LockRestrictingPlanHes": 0}
        Assertion.assert_delegate_info_contain(delegate_info, expect_data)

        logger.info(f"- 赎回1500    -> 账户自由金额1000 + 账户锁仓金额500 锁仓计划质押金额-500")
        withdrew_del_amt1 = BD.delegate_limit * 150
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt1, diff_restr=True)
        assert BD.von_k - abs(amt_later - amt_before) < BD.von_min
        Assertion.del_lock_info_zero_money(normal_aide0, normal_aide0_nt)
        expect_data2 = {'Pledge': {"old_value": BD.von_k * 2, "new_value": BD.von_k * 2 - BD.delegate_limit * 50}}
        Assertion.assert_restr_amt(restr_before, restr_later, expect_data2)

        logger.info(f"- 再赎回2000  -> 账户锁仓金额500 锁仓计划质押金额-500 + 锁定期自由金额1000 重新冻结 + 生效期锁仓金额500并冻结")
        withdrew_del_amt2 = BD.delegate_limit * 200
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt2, diff_restr=True)
        assert abs(amt_later - amt_before) < BD.von_min
        expect_data3 = {(4, BD.von_k, BD.delegate_limit * 50)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data3)
        expect_data4 = {'Pledge': {"old_value": BD.von_k * 2 - BD.delegate_limit * 50, "new_value": BD.von_k}}
        Assertion.assert_restr_amt(restr_before, restr_later, expect_data4)

        logger.info(f"- 再赎回500   -> 生效期锁仓金额500并冻结")
        withdrew_del_amt2 = BD.delegate_limit * 50
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt2, diff_restr=True)
        assert abs(amt_later - amt_before) < BD.von_min
        expect_data5 = {(4, BD.von_k, BD.von_k)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data5)
        Assertion.assert_restr_amt(restr_before, restr_later, {})

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 3, }], indirect=True)
    @pytest.mark.parametrize('create_lock_mix_amt_unlock_eq', [{"ManyAcc": True}], indirect=True)
    @pytest.mark.parametrize('acc_mix_amt_delegate', [{"wait_settlement": True}], indirect=True)
    def test_acc_mix_valid(self, acc_mix_amt_delegate, lock_mix_diff_cycle_delegate):
        """
        @param lock_mix_diff_cycle_delegate: 锁定期 自由金额 犹豫期  /  锁仓金额 生效期
        @param acc_mix_amt_delegate: 账户Mix金额 - 同时生效期
        @Desc:
            - 此时所有已委托总额 = 4000
            - 赎回1500    -> 锁定期自由金额1000 + 生效期自由金额500 并冻结
            - 再赎回2000  -> 生效期自由金额500 + 生效期锁仓金额1500并冻结
            - 再赎回500   -> 生效期锁仓金额500并冻结
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt = acc_mix_amt_delegate
        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        expect_data = {"Released": BD.von_k, "RestrictingPlan": BD.von_k * 2,
                       "ReleasedHes": 0, "RestrictingPlanHes": 0,
                       "LockReleasedHes": BD.von_k, "LockRestrictingPlanHes": 0}
        Assertion.assert_delegate_info_contain(delegate_info, expect_data)
        Assertion.del_lock_info_zero_money(normal_aide0, normal_aide0_nt)

        logger.info(f"- 赎回1500    -> 锁定期锁仓自由金额1000 + 生效期自由金额500 并冻结")
        withdrew_del_amt1 = BD.delegate_limit * 150
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt1, diff_restr=True)
        assert abs(amt_later - amt_before) < BD.von_min
        Assertion.assert_restr_amt(restr_before, restr_later, {})
        expect_data2 = {(6, BD.von_k + BD.delegate_limit * 50, 0)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data2)

        logger.info(f"- 再赎回2000  -> 生效期自由金额500 + 生效期锁仓金额1500并冻结")
        withdrew_del_amt2 = BD.delegate_limit * 200
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt2, diff_restr=True)
        assert abs(amt_later - amt_before) < BD.von_min
        Assertion.assert_restr_amt(restr_before, restr_later, {})
        expect_data3 = {(6, BD.von_k * 2, BD.von_k + BD.delegate_limit * 50)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data3)

        logger.info(f"- 再赎回500   -> 生效期锁仓金额500并冻结")
        withdrew_del_amt3 = BD.delegate_limit * 50
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt3, diff_restr=True)
        assert abs(amt_later - amt_before) < BD.von_min
        Assertion.assert_restr_amt(restr_before, restr_later, {})
        expect_data4 = {(6, BD.von_k * 2, BD.von_k * 2)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data4)


class TestLockFreeValidRestrHesitation(TestLockMixDiffCycle):
    """ 测试赎回委托 锁定期混合金额 自由金额 生效期  /  锁仓金额 犹豫期 """

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 5, }], indirect=True)
    @pytest.mark.parametrize('create_lock_restr_amt', [{"ManyAcc": True}], indirect=True)
    @pytest.mark.parametrize('acc_mix_amt_delegate_02', [{"wait_settlement": False}], indirect=True)
    def test_acc_mix_hesitation(self, lock_mix_diff_cycle_delegate_free_valid, acc_mix_amt_delegate_02):
        """
        @param lock_mix_diff_cycle_delegate_free_valid: 自由金额 生效期  /  锁仓金额 犹豫期
        @param acc_mix_amt_delegate_02: 继承 create_lock_mix_amt_free_unlock_long / 账户Mix金额 - 同时犹豫期
        @Desc:
            - 此时所有已委托总额 = 4000
            - 赎回1500    -> 账户自由金额1000 + 账户锁仓金额500 锁仓计划质押金额-500
            - 再赎回2000  -> 账户锁仓金额500 锁仓计划质押金额-500 + 锁定期锁仓金额1000 重新冻结 + 生效期自由金额500并冻结
            - 再赎回500   -> 生效期自由金额500并冻结
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt = acc_mix_amt_delegate_02
        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        expect_data = {"Released": BD.von_k, "RestrictingPlan": 0,
                       "ReleasedHes": BD.von_k, "RestrictingPlanHes": BD.von_k,
                       "LockReleasedHes": 0, "LockRestrictingPlanHes": BD.von_k}
        Assertion.assert_delegate_info_contain(delegate_info, expect_data)

        logger.info(f"- 赎回1500    -> 账户自由金额1000 + 账户锁仓金额500 锁仓计划质押金额-500")
        withdrew_del_amt1 = BD.delegate_limit * 150
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt1, diff_restr=True)
        assert BD.von_k - abs(amt_later - amt_before) < BD.von_min
        Assertion.del_lock_info_zero_money(normal_aide0, normal_aide0_nt)
        expect_data2 = {'Pledge': {"old_value": BD.von_k * 2, "new_value": BD.von_k * 2 - BD.delegate_limit * 50}}
        Assertion.assert_restr_amt(restr_before, restr_later, expect_data2)

        logger.info(f"- 再赎回2000  -> 账户锁仓金额500 锁仓计划质押金额-500 + 锁定期锁仓金额1000 重新冻结 + 生效期自由金额500并冻结")
        withdrew_del_amt2 = BD.delegate_limit * 200
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt2, diff_restr=True)
        assert abs(amt_later - amt_before) < BD.von_min
        expect_data3 = {(8, BD.delegate_limit * 50, BD.von_k)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data3)
        expect_data4 = {'Pledge': {"old_value": BD.von_k * 2 - BD.delegate_limit * 50, "new_value": BD.von_k}}
        Assertion.assert_restr_amt(restr_before, restr_later, expect_data4)

        logger.info(f"- 再赎回500   -> 生效期自由金额500并冻结")
        withdrew_del_amt2 = BD.delegate_limit * 50
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt2, diff_restr=True)
        assert abs(amt_later - amt_before) < BD.von_min
        expect_data5 = {(8, BD.von_k, BD.von_k)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data5)
        Assertion.assert_restr_amt(restr_before, restr_later, {})

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 5, }], indirect=True)
    @pytest.mark.parametrize('create_lock_restr_amt', [{"ManyAcc": True}], indirect=True)
    @pytest.mark.parametrize('acc_mix_amt_delegate_02', [{"wait_settlement": True}], indirect=True)
    def test_acc_mix_valid(self, acc_mix_amt_delegate_02, lock_mix_diff_cycle_delegate_free_valid):
        """
        @param lock_mix_diff_cycle_delegate_free_valid: 自由金额 生效期  /  锁仓金额 犹豫期
        @param acc_mix_amt_delegate_02: 继承 create_lock_mix_amt_free_unlock_long / 账户Mix金额 - 同时生效期
        @Desc:
            - 此时所有已委托总额 = 4000
            - 赎回1500    -> 锁定期 锁仓金额1000 生效期自由金额500并冻结
            - 再赎回2000  -> 生效期自由金额1500并冻结 + 生效期锁仓金额500并冻结
            - 再赎回500   -> 生效期锁仓金额500并冻结
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt = acc_mix_amt_delegate_02
        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        expect_data = {"Released": BD.von_k * 2, "RestrictingPlan": BD.von_k,
                       "ReleasedHes": 0, "RestrictingPlanHes": 0,
                       "LockReleasedHes": 0, "LockRestrictingPlanHes": BD.von_k}
        Assertion.assert_delegate_info_contain(delegate_info, expect_data)
        Assertion.del_lock_info_zero_money(normal_aide0, normal_aide0_nt)

        logger.info(f"- 赎回1500    -> 锁定期 锁仓金额1000 生效期自由金额500并冻结")
        withdrew_del_amt1 = BD.delegate_limit * 150
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt1, diff_restr=True)
        assert abs(amt_later - amt_before) < BD.von_min
        Assertion.assert_restr_amt(restr_before, restr_later, {})
        expect_data2 = {(9, BD.delegate_limit * 50, BD.von_k)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data2)

        logger.info(f"- 再赎回2000  -> 生效期自由金额1500并冻结 + 生效期锁仓金额500并冻结")
        withdrew_del_amt2 = BD.delegate_limit * 200
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt2, diff_restr=True)
        assert abs(amt_later - amt_before) < BD.von_min
        Assertion.assert_restr_amt(restr_before, restr_later, {})
        expect_data3 = {(9, BD.von_k * 2, BD.von_k + BD.delegate_limit * 50)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data3)

        logger.info(f"- 再赎回500   -> 生效期锁仓金额500并冻结")
        withdrew_del_amt2 = BD.delegate_limit * 50
        amt_before, amt_later, restr_before, restr_later = \
            withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, withdrew_del_amt2, diff_restr=True)
        assert abs(amt_later - amt_before) < BD.von_min
        Assertion.assert_restr_amt(restr_before, restr_later, {})
        expect_data4 = {(9, BD.von_k * 2, BD.von_k + BD.von_k)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data4)


class TestRedeemDelegate:
    """测试提取解锁委托"""

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
    @pytest.mark.parametrize('create_lock_restr_amt', [{"ManyAcc": True, "MixAcc": True}], indirect=True)
    def test_basics_redeem_delegate(self, create_lock_mix_amt_free_unlock_long):
        """
        正向用例
        - 提取到期 锁定金额
        - 解锁周期不同，分别多次提取
        - 提取多个节点释放的锁定金额
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt = create_lock_mix_amt_free_unlock_long
        expect_data = {(3, 0, BD.von_k), (4, BD.von_k, 0)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data)
        Assertion.del_locks_money(normal_aide1, normal_aide1_nt, expect_data)

        logger.info(f"使用账户B1自由金额 分别委托A/B节点 limit")
        assert normal_aide0.delegate.delegate(amount=BD.delegate_limit, balance_type=0,
                                              private_key=normal_aide1_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(amount=BD.delegate_limit, balance_type=0, node_id=normal_aide1_nt.node_id,
                                              private_key=normal_aide1_nt.del_pk)['code'] == 0

        acc_amt_before, red_acc_amt, restr_before, restr_later = \
            redeem_del_wait_unlock_diff_balance_restr(normal_aide0, normal_aide0_nt, wait_num=1, diff_restr=True)
        logger.info(f"账户A1 已领取 释放的锁仓金额")
        assert abs(red_acc_amt - acc_amt_before) < BD.von_min
        expect_data2 = {'Pledge': {"old_value": BD.von_k, "new_value": 0}}
        Assertion.assert_restr_amt(restr_before, restr_later, expect_data2)
        logger.info(f"账户B1 锁定期信息")
        Assertion.del_locks_money(normal_aide1, normal_aide1_nt, {(4, BD.von_k, 0)})
        Assertion.del_lock_release_money(normal_aide1, normal_aide1_nt, {"Released": 0, "RestrictingPlan": BD.von_k})

        acc_amt_before, red_acc_amt, restr_before, restr_later = \
            redeem_del_wait_unlock_diff_balance_restr(normal_aide0, normal_aide0_nt, wait_num=1, diff_restr=True)
        logger.info(f"账户A1 已领取 锁定期释放的自由金额")
        assert abs(red_acc_amt - acc_amt_before - BD.delegate_amount) < BD.von_min
        Assertion.assert_restr_amt(restr_before, restr_later, {})
        logger.info(f"账户B1 锁定期信息")
        Assertion.del_locks_money(normal_aide1, normal_aide1_nt, {})
        expect_data3 = {"Released": BD.von_k, "RestrictingPlan": BD.von_k}
        Assertion.del_lock_release_money(normal_aide1, normal_aide1_nt, expect_data3)

        logger.info(f"账户A1 取消委托 并进入冻结期")
        wit_del_res = PF.p_withdrew_delegate(normal_aide0, BD.delegate_limit,
                                             normal_aide0_nt, normal_aide1_nt.del_pk)
        wit_del_data = {"lockReleased": BD.delegate_limit, "lockRestrictingPlan": 0,
                        "released": 0, "restrictingPlan": 0}
        Assertion.assert_withdrew_delegate_response_contain(wit_del_res, wit_del_data)

        wit_del_res = PF.p_withdrew_delegate(normal_aide0, BD.delegate_limit,
                                             normal_aide1_nt, normal_aide1_nt.del_pk)
        wit_del_data = {"lockReleased": BD.delegate_limit, "lockRestrictingPlan": 0,
                        "released": 0, "restrictingPlan": 0}
        Assertion.assert_withdrew_delegate_response_contain(wit_del_res, wit_del_data)

        logger.info(f"领取账户B1 已释放金额")
        acc_amt_before, red_acc_amt, restr_before, restr_later = \
            redeem_del_wait_unlock_diff_balance_restr(normal_aide1, normal_aide1_nt, wait_num=2, diff_restr=True)
        assert abs(red_acc_amt - acc_amt_before - (BD.von_k + BD.delegate_limit * 2)) < BD.von_min
        expect_data4 = {'Pledge': {"old_value": BD.von_k, "new_value": 0}}
        Assertion.assert_restr_amt(restr_before, restr_later, expect_data4)

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
    @pytest.mark.parametrize('create_lock_free_amt', [{"ManyAcc": True, "MixAcc": True}], indirect=True)
    def test_node_exception_redeem_delegate(self, create_lock_mix_amt_restr_unlock_long, normal_aides):
        """
        节点异常提取已解锁金额
        - 节点物理状态异常
        - 节点链上状态异常 零出块后大于质押金额
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt = create_lock_mix_amt_restr_unlock_long
        normal_aide2 = normal_aides[-1]
        expect_data = {(3, BD.von_k, 0), (4, 0, BD.von_k)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data)
        Assertion.del_locks_money(normal_aide1, normal_aide1_nt, expect_data)

        normal_aide1.node.stop()

        wait_settlement(normal_aide2)

        acc_amt_before = normal_aide0.platon.get_balance(normal_aide1_nt.del_addr)
        logger.info(f"物理状态异常领取已释放锁定金 自由金额")
        assert normal_aide0.delegate.redeem_delegate(private_key=normal_aide1_nt.del_pk)['code'] == 0
        red_acc_amt = normal_aide0.platon.get_balance(normal_aide1_nt.del_addr)
        assert abs(red_acc_amt - acc_amt_before - BD.von_k) < BD.von_min

        normal_aide1.node.start()
        normal_aide0.node.stop()

        acc_amt_before, red_acc_amt, restr_before, restr_later = \
            redeem_del_wait_unlock_diff_balance_restr(normal_aide2, normal_aide0_nt, wait_num=1, diff_restr=True)

        candidate_info = PF.p_get_candidate_info(normal_aide1, query_aide=normal_aide0)
        assert candidate_info.Status == 3
        logger.info(f"链上状态异常领取已释放锁定金 自由金额 + 锁仓金额")
        assert abs(red_acc_amt - acc_amt_before - BD.von_k) < BD.von_min

        expect_data2 = {'Pledge': {"old_value": BD.von_k, "new_value": 0}}
        Assertion.assert_restr_amt(restr_before, restr_later, expect_data2)

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
    @pytest.mark.parametrize('create_lock_mix_amt_unlock_eq', [{"ManyAcc": True}], indirect=True)
    def test_fail_redeem_delegate(self, create_lock_mix_amt_unlock_eq):
        """
        反向用例
        - 提取未到期 锁定金额  -> pass 扣手续费
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt = create_lock_mix_amt_unlock_eq
        expect_data = {(3, BD.von_k, BD.von_k)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data)
        Assertion.del_locks_money(normal_aide1, normal_aide1_nt, expect_data)

        assert normal_aide0.delegate.redeem_delegate(private_key=normal_aide0_nt.del_pk)['code'] == 0
        acc_amt_before, red_acc_amt, restr_before, restr_later = \
            redeem_del_wait_unlock_diff_balance_restr(normal_aide0, normal_aide0_nt, wait_num=0, diff_restr=True)
        assert abs(red_acc_amt - acc_amt_before) < BD.von_min
        Assertion.assert_restr_amt(restr_before, restr_later, {})

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
    @pytest.mark.parametrize('many_cycle_restr_redeem_delegate', [{"ManyAcc": True}], indirect=True)
    def test_many_cycle_restr_redeem_delegate(self, many_cycle_restr_redeem_delegate):
        """
        锁定期混合金额 锁仓金额 在多个周期释放,领取已释放的金额
        @param many_cycle_restr_redeem_delegate:
        @Desc:
            - 锁定期金额未解锁 和 锁定期金额已解锁但未领取, 锁仓计划的变化如下
              * {'balance': 1k, 'debt': ++100(amt), 'plans': --1(len), 'Pledge': 1k}
            - 锁定期金额已解锁并领取
              * 释放金额1k 回锁仓, Pledge = 0
              * 锁仓有欠释放, {'balance': 1k - debt, 'debt': 0, 'plans': --1(len), 'Pledge': 0}
              * debt 的钱回账户
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt = many_cycle_restr_redeem_delegate

        logger.info(f"锁定期金额未解锁")
        acc_amt_before, red_acc_amt, restr_before, restr_later = \
            redeem_del_wait_unlock_diff_balance_restr(normal_aide0, normal_aide0_nt, wait_num=1, diff_restr=True)
        assert abs(red_acc_amt - acc_amt_before) < BD.von_min
        expect_data = {'debt': {"old_value": BD.delegate_limit * 10, "new_value": BD.delegate_limit * 20},
                       'plans': {"old_value_len": 9, "new_value_len": 8}}
        Assertion.assert_restr_amt(restr_before, restr_later, expect_data)

        logger.info(f"锁定期金额解锁并领取")
        acc_amt_before, red_acc_amt, restr_before, restr_later = \
            redeem_del_wait_unlock_diff_balance_restr(normal_aide0, normal_aide0_nt, wait_num=1, diff_restr=True)
        assert abs(red_acc_amt - acc_amt_before - (BD.von_k + BD.delegate_limit * 30)) < BD.von_min
        balance = BD.von_k - BD.delegate_limit * 30
        expect_data2 = {'balance': {"old_value": BD.von_k, "new_value": balance},
                        'debt': {"old_value": BD.delegate_limit * 20, "new_value": 0},
                        'plans': {"old_value_len": 8, "new_value_len": 7},
                        'Pledge': {"old_value": BD.von_k, "new_value": 0}}
        Assertion.assert_restr_amt(restr_before, restr_later, expect_data2)

        logger.info(f"锁仓计划继续释放")
        wait_settlement(normal_aide0)
        acc_amt = normal_aide0.platon.get_balance(normal_aide0_nt.del_addr)
        restr_info = PF.p_get_restricting_info(normal_aide0, normal_aide0_nt)
        assert acc_amt - red_acc_amt == BD.delegate_limit * 10

        expect_data3 = {'balance': {"old_value": balance, "new_value": balance - BD.delegate_limit * 10},
                        'plans': {"old_value_len": 7, "new_value_len": 6}}
        Assertion.assert_restr_amt(restr_later, restr_info, expect_data3)
        pass

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
    def test_many_cycle_restr_loop_redeem_delegate(self, many_cycle_restr_loop_redeem_delegate, normal_aides):
        """
        锁定期混合金额 锁仓金额 在多个周期释放并嵌套委托(多节点), 领取已释放的金额
        @param many_cycle_restr_loop_redeem_delegate:
        @Desc:
            - 锁定期金额未解锁 和 锁定期金额已解锁但未领取, 锁仓计划的变化如下
              * {'balance': 1k, 'debt': ++100(amt), 'plans': --1(len), 'Pledge': 1k}
            - 锁定期金额已解锁并领取
              * 释放金额1k 回锁仓, Pledge = 0
              * 锁仓有欠释放, {'balance': 1k - debt, 'debt': 0, 'plans': --1(len), 'Pledge': 0}
              * debt 的钱回账户
        """
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, other_nt_list = many_cycle_restr_loop_redeem_delegate

        logger.info(f"锁定期金额未解锁")
        acc_amt_before, red_acc_amt, restr_before, restr_later = \
            redeem_del_wait_unlock_diff_balance_restr(normal_aide0, normal_aide0_nt, wait_num=1, diff_restr=True)
        assert abs(red_acc_amt - acc_amt_before) < BD.von_min
        expect_data = {'debt': {"old_value": BD.delegate_limit * 10, "new_value": BD.delegate_limit * 20},
                       'plans': {"old_value_len": 9, "new_value_len": 8}}
        Assertion.assert_restr_amt(restr_before, restr_later, expect_data)

        logger.info(f"锁定期锁仓金额对 A、B、C、D 节点进行委托")
        del_amt = BD.delegate_limit * 25
        for i in range(0, 4):
            assert normal_aide0.delegate.delegate(amount=del_amt, balance_type=3, node_id=normal_aides[i].node.node_id,
                                                  private_key=normal_aide0_nt.del_pk)['code'] == 0

        logger.info(f"锁定期自由金额已释放并领取")
        acc_amt_before, red_acc_amt, restr_before, restr_later = \
            redeem_del_wait_unlock_diff_balance_restr(normal_aide0, normal_aide0_nt, wait_num=1, diff_restr=True)
        assert abs(red_acc_amt - acc_amt_before - BD.von_k) < BD.von_min
        expect_data2 = {'debt': {"old_value": BD.delegate_limit * 20, "new_value": BD.delegate_limit * 30},
                        'plans': {"old_value_len": 8, "new_value_len": 7}}
        Assertion.assert_restr_amt(restr_before, restr_later, expect_data2)

        logger.info(f"赎回 节点A 的锁仓金额委托, 并进入锁定期")
        wit_del_res = PF.p_withdrew_delegate(normal_aide0, del_amt,
                                             normal_aide0_nt, normal_aide0_nt.del_pk)
        wit_del_data = {"lockReleased": 0, "lockRestrictingPlan": del_amt,
                        "released": 0, "restrictingPlan": 0}
        Assertion.assert_withdrew_delegate_response_contain(wit_del_res, wit_del_data)

        logger.info(f"等待节点A的锁仓金额 解锁并领取")
        acc_amt_before, red_acc_amt, restr_before, restr_later = \
            redeem_del_wait_unlock_diff_balance_restr(normal_aide0, normal_aide0_nt, wait_num=2, diff_restr=True)

        expect_data3 = {'balance': {"old_value": BD.von_k, "new_value": BD.von_k - del_amt},
                        'debt': {"old_value": BD.delegate_limit * 30, "new_value": BD.delegate_limit * 50 - del_amt},
                        'plans': {"old_value_len": 7, "new_value_len": 5},
                        'Pledge': {"old_value": BD.von_k, "new_value": BD.von_k - del_amt}}
        Assertion.assert_restr_amt(restr_before, restr_later, expect_data3)

        logger.info(f"赎回 节点B、C、D 的锁仓金额委托, 并进入锁定期")
        for i in range(1, 4):
            wit_del_res = PF.p_withdrew_delegate(normal_aide0, del_amt,
                                                 other_nt_list[i - 1], normal_aide0_nt.del_pk)
            wit_del_data = {"lockReleased": 0, "lockRestrictingPlan": del_amt,
                            "released": 0, "restrictingPlan": 0}
            Assertion.assert_withdrew_delegate_response_contain(wit_del_res, wit_del_data)

        logger.info(f"等待节点B、C、D的锁仓金额 解锁并领取")
        acc_amt_before, red_acc_amt, restr_before, restr_later = \
            redeem_del_wait_unlock_diff_balance_restr(normal_aide0, normal_aide0_nt, wait_num=2, diff_restr=True)
        balance = BD.von_k - del_amt * 2 - BD.delegate_limit * 20
        expect_data4 = {'balance': {"old_value": BD.von_k - del_amt, "new_value": balance},
                        'debt': {"old_value": del_amt, "new_value": 0},
                        'plans': {"old_value_len": 5, "new_value_len": 3},
                        'Pledge': {"old_value": BD.von_k - del_amt, "new_value": 0}}
        Assertion.assert_restr_amt(restr_before, restr_later, expect_data4)

        logger.info(f"锁仓计划继续释放")
        wait_settlement(normal_aide0)
        acc_amt = normal_aide0.platon.get_balance(normal_aide0_nt.del_addr)
        restr_info = PF.p_get_restricting_info(normal_aide0, normal_aide0_nt)
        assert acc_amt - red_acc_amt == BD.delegate_limit * 10

        expect_data5 = {'balance': {"old_value": balance, "new_value": balance - BD.delegate_limit * 10},
                        'plans': {"old_value_len": 3, "new_value_len": 2}}
        Assertion.assert_restr_amt(restr_later, restr_info, expect_data5)


class TestLoopDelegate:
    """测试循环委托"""

    @staticmethod
    def _cycle_2_block_161_320(del_amt, loop_delegate):
        """
        @Desc:
            - 锁仓计划合并会先填平欠释放金额
            - 锁定期金额委托犹豫期 赎回
            - 锁定期金额一对多委托
            - 账户自由金额+锁仓金额 一对多委托,并存在未委托完的锁仓金额
        """
        normal_aide0, normal_aide0_nt, all_aide_nt_list, plan, init_restr_info = loop_delegate
        assert normal_aide0.platon.block_number > 160

        logger.info(f"查询锁定期数据信息")
        lock_info_expect_data = {(3, BD.von_k, BD.von_k)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, lock_info_expect_data)

        logger.info(f"查询锁仓计划信息")
        restr_info = PF.p_get_restricting_info(normal_aide0, normal_aide0_nt)
        restr_info_expect_data = {'plans': {"old_value_len": 10, "new_value_len": 9},
                                  'debt': {"old_value": 0, "new_value": BD.delegate_limit * 10}, }
        Assertion.assert_restr_amt(init_restr_info, restr_info, restr_info_expect_data)

        logger.info(f"锁仓计划合并 验证账户余额")
        acc_amt_before = normal_aide0.platon.get_balance(normal_aide0_nt.del_addr)
        assert normal_aide0.restricting.restricting(release_address=normal_aide0_nt.del_addr, plans=plan,
                                                    private_key=normal_aide0_nt.del_pk)['code'] == 0
        acc_amt_last = normal_aide0.platon.get_balance(normal_aide0_nt.del_addr)
        assert acc_amt_last - acc_amt_before - del_amt[100] < BD.von_min

        logger.info(f"查节点委托信息")
        assert PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt) is None

        logger.info(f"查询提取锁定金前后 锁仓计划 和 账户余额")
        acc_amt_before, red_acc_amt, _, restr_later = \
            redeem_del_wait_unlock_diff_balance_restr(normal_aide0, normal_aide0_nt, wait_num=0, diff_restr=True)
        assert abs(red_acc_amt - acc_amt_before) < BD.von_min
        restr_expect_data = {'balance': {"old_value": BD.von_k, "new_value": BD.von_k * 2 - BD.delegate_limit * 10},
                             'debt': {"old_value": BD.delegate_limit * 10, "new_value": 0},
                             'plans': {'old_value_len': 9, 'new_value_len': 10}}
        Assertion.assert_restr_amt(restr_info, restr_later, restr_expect_data)

        logger.info(f"锁定期金额委托1000 即用锁仓金额在委托")
        assert normal_aide0.delegate.delegate(BD.von_k, 3, private_key=normal_aide0_nt.del_pk)['code'] == 0
        logger.info(f"赎回500 并验证 lock_info")
        assert normal_aide0.delegate.withdrew_delegate(amount=del_amt[500],
                                                       staking_block_identifier=normal_aide0_nt.StakingBlockNum,
                                                       node_id=normal_aide0_nt.node_id,
                                                       private_key=normal_aide0_nt.del_pk, )['code'] == 0
        lock_info_expect_data = {(3, BD.von_k, del_amt[500])}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, lock_info_expect_data)

        logger.info(f"锁定期锁仓金额剩下500 自由金额1000 一对多分别委托 ABCD * 300 = 1200 自由金额还剩下300")
        for i in range(4):
            aide_nt, node_id = all_aide_nt_list[i], all_aide_nt_list[i].node_id
            assert normal_aide0.delegate.delegate(del_amt[300], 3, node_id=node_id,
                                                  private_key=normal_aide0_nt.del_pk)['code'] == 0

            delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, aide_nt)
            if i == 0:
                logger.info("A节点 锁定金 委托数据")
                delegate_info_expect_data = {"Released": 0, "RestrictingPlan": 0,
                                             "ReleasedHes": 0, "RestrictingPlanHes": 0, "LockReleasedHes": 0,
                                             "LockRestrictingPlanHes": del_amt[500] + del_amt[300]}
            elif i == 1:
                logger.info("B节点 锁定金 委托数据")
                delegate_info_expect_data = {"Released": 0, "RestrictingPlan": 0,
                                             "ReleasedHes": 0, "RestrictingPlanHes": 0,
                                             "LockReleasedHes": del_amt[100],
                                             "LockRestrictingPlanHes": del_amt[200]}
            else:
                logger.info("CD节点 锁定金 委托数据")
                delegate_info_expect_data = {"Released": 0, "RestrictingPlan": 0,
                                             "ReleasedHes": 0, "RestrictingPlanHes": 0,
                                             "LockReleasedHes": del_amt[300], "LockRestrictingPlanHes": 0}
            Assertion.assert_delegate_info_contain(delegate_info, delegate_info_expect_data)

        logger.info(f"账户金额分别 委托 ABCD 自由金额1k 锁仓金额200 第二次锁仓计划中还有1k-100=900-800=剩下100未被委托")
        for i in range(4):
            aide_nt, node_id = all_aide_nt_list[i], all_aide_nt_list[i].node_id
            assert normal_aide0.delegate.delegate(BD.von_k, 0, node_id=node_id,
                                                  private_key=normal_aide0_nt.del_pk)['code'] == 0
            assert normal_aide0.delegate.delegate(del_amt[200], 1, node_id=node_id,
                                                  private_key=normal_aide0_nt.del_pk)['code'] == 0
            delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, aide_nt)
            if i == 0:
                logger.info("A节点 锁定金+账户 委托数据")
                delegate_info_expect_data = {"Released": 0, "RestrictingPlan": 0,
                                             "ReleasedHes": BD.von_k, "RestrictingPlanHes": del_amt[200],
                                             "LockReleasedHes": 0,
                                             "LockRestrictingPlanHes": del_amt[500] + del_amt[300]}
            elif i == 1:
                logger.info("B节点 锁定金+账户 委托数据")
                delegate_info_expect_data = {"Released": 0, "RestrictingPlan": 0,
                                             "ReleasedHes": BD.von_k, "RestrictingPlanHes": del_amt[200],
                                             "LockReleasedHes": del_amt[100],
                                             "LockRestrictingPlanHes": del_amt[200]}
            else:
                logger.info("CD节点 锁定金+账户 委托数据")
                delegate_info_expect_data = {"Released": 0, "RestrictingPlan": 0,
                                             "ReleasedHes": BD.von_k, "RestrictingPlanHes": del_amt[200],
                                             "LockReleasedHes": del_amt[300], "LockRestrictingPlanHes": 0}
            Assertion.assert_delegate_info_contain(delegate_info, delegate_info_expect_data)

        restr_later_2 = PF.p_get_restricting_info(normal_aide0, normal_aide0_nt)
        expect_data2 = {'Pledge': {"old_value": BD.von_k, "new_value": BD.von_k + del_amt[800]}}
        Assertion.assert_restr_amt(restr_later, restr_later_2, expect_data2)

        logger.info(f"账户自由金额委托4k -> 账户余额减4k")
        acc_amt = normal_aide0.platon.get_balance(normal_aide0_nt.del_addr)
        assert red_acc_amt - acc_amt - BD.von_k * 4 < BD.von_min

        assert normal_aide0.platon.block_number < 160 * 2
        return acc_amt, restr_later_2

    @staticmethod
    def _cycle_3_block_321_480(del_amt, loop_delegate, ago_acc_amt, ago_restr_info):
        """
        @Desc:
            - 锁仓计划释放 200 锁仓中未委托金额100 欠释放金额100
            - 无释放金额 提取锁定金
            - 验证所有委托状态 进入生效期
            - 赎回生效期金额 进入 锁定期
            - 使用锁定金额一对多委托 并验证 优先使用解锁周期长的金额,然后再使用先解锁的金额
            - 第三次创建锁仓 验证锁仓合并 1k - 欠释放100 可支配锁仓900 并委托500,未委托400
            - 使用账户自由金额一对多委托
            - 在犹豫期一对多赎回(账户委托 + 锁定期委托)
                * A节点 1100 = 1000自由金额 + 100锁仓金额 / 第三次锁仓 委托400,未委托500
        """
        normal_aide0, normal_aide0_nt, all_aide_nt_list, plan, init_restr_info = loop_delegate
        Released, RestrictingPlan = BD.von_k + del_amt[1100], del_amt[200] + del_amt[100]
        assert normal_aide0.platon.block_number > 160 * 2

        logger.info(f"cycle3 验证锁仓计划 第二次锁仓 (1000 - 100 - 200 * 4)=100未被委托  释放200 账户余额+100 欠释放字段+100")
        restr_info = PF.p_get_restricting_info(normal_aide0, normal_aide0_nt)
        restr_expect_data = {
            'balance': {"old_value": BD.von_k * 2 - del_amt[100], "new_value": BD.von_k * 2 - del_amt[200]},
            'debt': {"old_value": 0, "new_value": del_amt[100]},
            'plans': {'old_value_len': 10, 'new_value_len': 9}, }
        Assertion.assert_restr_amt(ago_restr_info, restr_info, restr_expect_data)
        acc_amt = normal_aide0.platon.get_balance(normal_aide0_nt.del_addr)
        assert abs(acc_amt - ago_acc_amt - del_amt[100]) < BD.von_min
        logger.info(f"锁定期无释放金额去领取 - 只扣手续费")
        acc_amt_before, red_acc_amt, = \
            redeem_del_wait_unlock_diff_balance_restr(normal_aide0, normal_aide0_nt, wait_num=0, )
        assert red_acc_amt - acc_amt_before < BD.von_min

        logger.info(f"验证锁定期 剩下300自由金额")
        lock_info_expect_data = {(3, del_amt[300], 0)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, lock_info_expect_data)

        logger.info(f"验证所有节点委托信息")
        for i in range(4):
            aide_nt, node_id = all_aide_nt_list[i], all_aide_nt_list[i].node_id
            delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, aide_nt)
            if i == 0:
                logger.info("A节点 委托数据")
                delegate_info_expect_data = {"Released": BD.von_k, "RestrictingPlan": BD.von_k,
                                             "ReleasedHes": 0, "RestrictingPlanHes": 0,
                                             "LockReleasedHes": 0, "LockRestrictingPlanHes": 0}
            elif i == 1:
                logger.info("B节点 委托数据")
                delegate_info_expect_data = {"Released": BD.von_k + del_amt[100], "RestrictingPlan": del_amt[400],
                                             "ReleasedHes": 0, "RestrictingPlanHes": 0,
                                             "LockReleasedHes": 0, "LockRestrictingPlanHes": 0}
            else:
                logger.info("CD节点 委托数据")
                delegate_info_expect_data = {"Released": BD.von_k + del_amt[300], "RestrictingPlan": del_amt[200],
                                             "ReleasedHes": 0, "RestrictingPlanHes": 0,
                                             "LockReleasedHes": 0, "LockRestrictingPlanHes": 0}
            Assertion.assert_delegate_info_contain(delegate_info, delegate_info_expect_data)

        logger.info(f'赎回委托 都在生效期从自由金额开始赎回 ABCD 赎回 1200')
        for i in range(4):
            aide_nt, node_id = all_aide_nt_list[i], all_aide_nt_list[i].node_id
            assert normal_aide0.delegate.withdrew_delegate(amount=del_amt[1200],
                                                           staking_block_identifier=aide_nt.StakingBlockNum,
                                                           node_id=node_id,
                                                           private_key=normal_aide0_nt.del_pk, )['code'] == 0
            delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, aide_nt)
            if i == 0:
                logger.info("A节点 赎回委托数据")
                delegate_info_expect_data = {"Released": 0, "RestrictingPlan": del_amt[800],
                                             "ReleasedHes": 0, "RestrictingPlanHes": 0,
                                             "LockReleasedHes": 0, "LockRestrictingPlanHes": 0}
                lock_expect_data = {(3, del_amt[300], 0), (4, BD.von_k, del_amt[200])}
            elif i == 1:
                logger.info("B节点 赎回委托数据")
                delegate_info_expect_data = {"Released": 0, "RestrictingPlan": del_amt[300],
                                             "ReleasedHes": 0, "RestrictingPlanHes": 0,
                                             "LockReleasedHes": 0, "LockRestrictingPlanHes": 0}
                __this_lock_data = {(3, del_amt[300], 0), (4, del_amt[1100], del_amt[100])}
                lock_expect_data = {(3, del_amt[300], 0), (4, Released, RestrictingPlan)}
            else:
                logger.info("CD节点 赎回委托数据")
                delegate_info_expect_data = {"Released": del_amt[100], "RestrictingPlan": del_amt[200],
                                             "ReleasedHes": 0, "RestrictingPlanHes": 0,
                                             "LockReleasedHes": 0, "LockRestrictingPlanHes": 0}
                __this_lock_data = {(3, del_amt[300], 0), (4, del_amt[1200], 0)}

                if i == 2:
                    lock_expect_data = {(3, del_amt[300], 0),
                                        (4, Released + del_amt[1200], RestrictingPlan)}
                else:
                    lock_expect_data = {(3, del_amt[300], 0),
                                        (4, Released + del_amt[1200] * 2, RestrictingPlan)}
            Assertion.assert_delegate_info_contain(delegate_info, delegate_info_expect_data)
            Assertion.del_locks_money(normal_aide0, normal_aide0_nt, lock_expect_data)

        logger.info(f"使用锁定金(3, 300, 0),(4, 4500, 300)委托 总5000  ABCD 1250 会先使用冻结周期数长的锁定金额 剩(3, 100, 0)")
        for i in range(4):
            aide_nt, node_id = all_aide_nt_list[i], all_aide_nt_list[i].node_id
            assert normal_aide0.delegate.delegate(del_amt[1250], 3, node_id=node_id,
                                                  private_key=normal_aide0_nt.del_pk)['code'] == 0

            delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, aide_nt)
            if i == 0:
                logger.info("锁定金委托A节点 1250 ")
                delegate_info_expect_data = {"Released": 0, "RestrictingPlan": del_amt[800],
                                             "ReleasedHes": 0, "RestrictingPlanHes": 0,
                                             "LockReleasedHes": del_amt[950], "LockRestrictingPlanHes": del_amt[300]}
                lock_expect_data = {(3, del_amt[300], 0),
                                    (4, Released + del_amt[1200] * 2 - del_amt[950], 0)}
            elif i == 1:
                logger.info("锁定金委托B节点 1250")
                delegate_info_expect_data = {"Released": 0, "RestrictingPlan": del_amt[300],
                                             "ReleasedHes": 0, "RestrictingPlanHes": 0,
                                             "LockReleasedHes": del_amt[1250], "LockRestrictingPlanHes": 0}
                lock_expect_data = {(3, del_amt[300], 0),
                                    (4, Released + del_amt[1200] * 2 - del_amt[950] - del_amt[1250], 0)}
            else:
                logger.info("锁定金委托CD节点 1250")
                delegate_info_expect_data = {"Released": del_amt[100], "RestrictingPlan": del_amt[200],
                                             "ReleasedHes": 0, "RestrictingPlanHes": 0,
                                             "LockReleasedHes": del_amt[1250], "LockRestrictingPlanHes": 0}

                if i == 2:
                    lock_expect_data = {(3, del_amt[300], 0),
                                        (4, Released + del_amt[1200] * 2 - del_amt[950] - del_amt[1250] * 2, 0)}
                else:
                    lock_expect_data = {(3, del_amt[100], 0)}
            Assertion.assert_delegate_info_contain(delegate_info, delegate_info_expect_data)
            Assertion.del_locks_money(normal_aide0, normal_aide0_nt, lock_expect_data)

        logger.info(f"第三次创建锁仓计划合并(1000-欠释放100=900) 验证账户余额")
        acc_amt_before = normal_aide0.platon.get_balance(normal_aide0_nt.del_addr)
        assert normal_aide0.restricting.restricting(release_address=normal_aide0_nt.del_addr, plans=plan,
                                                    private_key=normal_aide0_nt.del_pk)['code'] == 0
        acc_amt_last = normal_aide0.platon.get_balance(normal_aide0_nt.del_addr)
        restr_info_1 = PF.p_get_restricting_info(normal_aide0, normal_aide0_nt)
        restr_expect_data = {
            'balance': {"old_value": del_amt[1800], "new_value": del_amt[1800] + BD.von_k - del_amt[100]},
            'debt': {"old_value": del_amt[100], "new_value": 0},
            'plans': {'old_value_len': 9, 'new_value_len': 10}, }
        Assertion.assert_restr_amt(restr_info, restr_info_1, restr_expect_data)
        assert acc_amt_last - acc_amt_before - del_amt[100] < BD.von_min

        logger.info(f"使用账户锁仓金额委托 500 剩余未委托金额900-500=400")
        assert normal_aide0.delegate.delegate(del_amt[500], 1, private_key=normal_aide0_nt.del_pk)['code'] == 0
        restr_info_2 = PF.p_get_restricting_info(normal_aide0, normal_aide0_nt)
        expect_data2 = {'Pledge': {"old_value": del_amt[1800], "new_value": del_amt[2300]}}
        Assertion.assert_restr_amt(restr_info_1, restr_info_2, expect_data2)

        logger.info(f"账户金额分别 委托 ABCD 自由金额1k")
        for i in range(4):
            aide_nt, node_id = all_aide_nt_list[i], all_aide_nt_list[i].node_id
            assert normal_aide0.delegate.delegate(BD.von_k, 0, node_id=node_id,
                                                  private_key=normal_aide0_nt.del_pk)['code'] == 0
            delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, aide_nt)
            if i == 0:
                logger.info("A节点 锁定金+账户 委托数据")
                delegate_info_expect_data = {"Released": 0, "RestrictingPlan": del_amt[800],
                                             "ReleasedHes": del_amt[1000], "RestrictingPlanHes": del_amt[500],
                                             "LockReleasedHes": del_amt[950], "LockRestrictingPlanHes": del_amt[300]}
            elif i == 1:
                logger.info("B节点 锁定金+账户 委托数据")
                delegate_info_expect_data = {"Released": 0, "RestrictingPlan": del_amt[300],
                                             "ReleasedHes": del_amt[1000], "RestrictingPlanHes": 0,
                                             "LockReleasedHes": del_amt[1250], "LockRestrictingPlanHes": 0}
            else:
                logger.info("CD节点 锁定金+账户 委托数据")
                delegate_info_expect_data = {"Released": del_amt[100], "RestrictingPlan": del_amt[200],
                                             "ReleasedHes": del_amt[1000], "RestrictingPlanHes": 0,
                                             "LockReleasedHes": del_amt[1250], "LockRestrictingPlanHes": 0}
            Assertion.assert_delegate_info_contain(delegate_info, delegate_info_expect_data)

        logger.info(f"账户和锁定金委托之后 验证在犹豫期赎回 A1100 B1500 C2000 D2500")
        for i in range(4):
            aide_nt, node_id = all_aide_nt_list[i], all_aide_nt_list[i].node_id

            if i == 0:
                logger.info("A节点 赎回1100委托 犹豫期账户自由金额1000 + 犹豫期账户锁仓金额100")
                assert normal_aide0.delegate.withdrew_delegate(amount=del_amt[1100],
                                                               staking_block_identifier=aide_nt.StakingBlockNum,
                                                               node_id=node_id,
                                                               private_key=normal_aide0_nt.del_pk, )['code'] == 0
                restr_info_3 = PF.p_get_restricting_info(normal_aide0, normal_aide0_nt)
                expect_data3 = {'Pledge': {"old_value": del_amt[2300], "new_value": del_amt[2200]}}
                Assertion.assert_restr_amt(restr_info_2, restr_info_3, expect_data3)

                delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, aide_nt)
                delegate_info_expect_data = {"Released": 0, "RestrictingPlan": del_amt[800],
                                             "ReleasedHes": 0, "RestrictingPlanHes": del_amt[400],
                                             "LockReleasedHes": del_amt[950], "LockRestrictingPlanHes": del_amt[300]}
                lock_expect_data = {(3, del_amt[100], 0)}
            elif i == 1:
                logger.info("B节点 赎回1500委托")
                assert normal_aide0.delegate.withdrew_delegate(amount=del_amt[1500],
                                                               staking_block_identifier=aide_nt.StakingBlockNum,
                                                               node_id=node_id,
                                                               private_key=normal_aide0_nt.del_pk, )['code'] == 0
                delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, aide_nt)

                delegate_info_expect_data = {"Released": 0, "RestrictingPlan": del_amt[300],
                                             "ReleasedHes": 0, "RestrictingPlanHes": 0,
                                             "LockReleasedHes": del_amt[750], "LockRestrictingPlanHes": 0}

                lock_expect_data = {(3, del_amt[100], 0), (4, del_amt[500], 0)}

            elif i == 2:
                logger.info("C节点 赎回2000委托")
                assert normal_aide0.delegate.withdrew_delegate(amount=del_amt[2000],
                                                               staking_block_identifier=aide_nt.StakingBlockNum,
                                                               node_id=node_id,
                                                               private_key=normal_aide0_nt.del_pk, )['code'] == 0
                delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, aide_nt)
                delegate_info_expect_data = {"Released": del_amt[100], "RestrictingPlan": del_amt[200],
                                             "ReleasedHes": 0, "RestrictingPlanHes": 0,
                                             "LockReleasedHes": del_amt[250], "LockRestrictingPlanHes": 0}

                lock_expect_data = {(3, del_amt[100], 0), (4, del_amt[1500], 0)}
            else:
                logger.info("D节点 赎回2500委托")
                assert normal_aide0.delegate.withdrew_delegate(amount=del_amt[2500],
                                                               staking_block_identifier=aide_nt.StakingBlockNum,
                                                               node_id=node_id,
                                                               private_key=normal_aide0_nt.del_pk, )['code'] == 0
                delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, aide_nt)
                delegate_info_expect_data = {"Released": 0, "RestrictingPlan": del_amt[50],
                                             "ReleasedHes": 0, "RestrictingPlanHes": 0,
                                             "LockReleasedHes": 0, "LockRestrictingPlanHes": 0}
                lock_expect_data = {(3, del_amt[100], 0),
                                    (4, del_amt[1500] + del_amt[1250] + del_amt[100], del_amt[150])}

            Assertion.assert_delegate_info_contain(delegate_info, delegate_info_expect_data)
            Assertion.del_locks_money(normal_aide0, normal_aide0_nt, lock_expect_data)

        acc_amt = normal_aide0.platon.get_balance(normal_aide0_nt.del_addr)
        assert acc_amt - acc_amt_last < BD.von_min  # 只扣掉了手续费 4次委托 4次赎回委托
        restr_info_4 = PF.p_get_restricting_info(normal_aide0, normal_aide0_nt)
        Assertion.assert_restr_amt(restr_info_3, restr_info_4, {})

        assert normal_aide0.platon.block_number < 160 * 3
        return acc_amt, restr_info_4

    @staticmethod
    def _cycle_4_block_481_640(del_amt, loop_delegate, ago_acc_amt, ago_restr_info):
        """
        @Desc:
            - 提取已释放的锁定期金额 -> 自由金额 100
            - 赎回委托并重新委托
        """

        normal_aide0, normal_aide0_nt, all_aide_nt_list, plan, init_restr_info = loop_delegate

        assert normal_aide0.platon.block_number > 160 * 3

        logger.info(f"cycle4 验证锁仓计划 第三次锁仓 (1000 - 100 - 400)=500未被委托  释放300 账户余额+300 欠释放字段+0")
        restr_info = PF.p_get_restricting_info(normal_aide0, normal_aide0_nt)
        restr_expect_data = {
            'balance': {"old_value": del_amt[2700], "new_value": del_amt[2400]},
            'plans': {'old_value_len': 10, 'new_value_len': 9}, }
        Assertion.assert_restr_amt(ago_restr_info, restr_info, restr_expect_data)
        acc_amt = normal_aide0.platon.get_balance(normal_aide0_nt.del_addr)
        assert abs(acc_amt - ago_acc_amt - del_amt[300]) < BD.von_min

        logger.info(f"验证锁定期 已释放金额: 自由金额100 无锁仓金额")
        lock_info_release_data = {'Released': del_amt[100], 'RestrictingPlan': 0}
        Assertion.del_lock_release_money(normal_aide0, normal_aide0_nt, lock_info_release_data)

        logger.info(f"提取已释放的锁定期金额 -> 自由金额 100")
        acc_amt_before, red_acc_amt, = \
            redeem_del_wait_unlock_diff_balance_restr(normal_aide0, normal_aide0_nt, wait_num=0, )
        assert red_acc_amt - acc_amt_before - del_amt[100] < BD.von_min

        logger.info(f"验证各节点委托信息")
        for i in range(4):
            aide_nt, node_id = all_aide_nt_list[i], all_aide_nt_list[i].node_id
            delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, aide_nt)
            if i == 0:
                logger.info("A节点 委托数据")
                delegate_info_expect_data = {"Released": del_amt[950], "RestrictingPlan": del_amt[1500],
                                             "ReleasedHes": 0, "RestrictingPlanHes": 0,
                                             "LockReleasedHes": 0, "LockRestrictingPlanHes": 0}
            elif i == 1:
                logger.info("B节点 委托数据")
                delegate_info_expect_data = {"Released": del_amt[750], "RestrictingPlan": del_amt[300],
                                             "ReleasedHes": 0, "RestrictingPlanHes": 0,
                                             "LockReleasedHes": 0, "LockRestrictingPlanHes": 0}
            elif i == 2:
                logger.info("C节点 委托数据")
                delegate_info_expect_data = {"Released": del_amt[350], "RestrictingPlan": del_amt[200],
                                             "ReleasedHes": 0, "RestrictingPlanHes": 0,
                                             "LockReleasedHes": 0, "LockRestrictingPlanHes": 0}
            else:
                logger.info("D节点 委托数据")
                delegate_info_expect_data = {"Released": 0, "RestrictingPlan": del_amt[50],
                                             "ReleasedHes": 0, "RestrictingPlanHes": 0,
                                             "LockReleasedHes": 0, "LockRestrictingPlanHes": 0}
            Assertion.assert_delegate_info_contain(delegate_info, delegate_info_expect_data)

        logger.info(f"赎回委托并重新锁定")
        for i in range(4):
            aide_nt, node_id = all_aide_nt_list[i], all_aide_nt_list[i].node_id

            if i == 0:
                logger.info("A节点 赎回1600委托 = 生效期自由金额950 + 生效期锁仓金额650")
                assert normal_aide0.delegate.withdrew_delegate(amount=del_amt[1600],
                                                               staking_block_identifier=aide_nt.StakingBlockNum,
                                                               node_id=node_id,
                                                               private_key=normal_aide0_nt.del_pk, )['code'] == 0

                delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, aide_nt)
                delegate_info_expect_data = {"Released": 0, "RestrictingPlan": del_amt[850],
                                             "ReleasedHes": 0, "RestrictingPlanHes": 0,
                                             "LockReleasedHes": 0, "LockRestrictingPlanHes": 0}
                lock_expect_data = {(4, del_amt[2850], del_amt[150]), (5, del_amt[950], del_amt[650])}
            elif i == 1:
                logger.info("B节点 赎回500 生效期自由金额500")
                assert normal_aide0.delegate.withdrew_delegate(amount=del_amt[500],
                                                               staking_block_identifier=aide_nt.StakingBlockNum,
                                                               node_id=node_id,
                                                               private_key=normal_aide0_nt.del_pk, )['code'] == 0
                delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, aide_nt)

                delegate_info_expect_data = {"Released": del_amt[250], "RestrictingPlan": del_amt[300],
                                             "ReleasedHes": 0, "RestrictingPlanHes": 0,
                                             "LockReleasedHes": 0, "LockRestrictingPlanHes": 0}

                lock_expect_data = {(4, del_amt[2850], del_amt[150]), (5, del_amt[1450], del_amt[650])}
            elif i == 2:
                logger.info("C节点 赎回100 生效期自由金额100")
                assert normal_aide0.delegate.withdrew_delegate(amount=del_amt[100],
                                                               staking_block_identifier=aide_nt.StakingBlockNum,
                                                               node_id=node_id,
                                                               private_key=normal_aide0_nt.del_pk, )['code'] == 0
                delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, aide_nt)
                delegate_info_expect_data = {"Released": del_amt[250], "RestrictingPlan": del_amt[200],
                                             "ReleasedHes": 0, "RestrictingPlanHes": 0,
                                             "LockReleasedHes": 0, "LockRestrictingPlanHes": 0}

                lock_expect_data = {(4, del_amt[2850], del_amt[150]), (5, del_amt[1550], del_amt[650])}
            else:
                logger.info("D节点 赎回10 生效期锁仓金额10")
                assert normal_aide0.delegate.withdrew_delegate(amount=BD.delegate_limit,
                                                               staking_block_identifier=aide_nt.StakingBlockNum,
                                                               node_id=node_id,
                                                               private_key=normal_aide0_nt.del_pk, )['code'] == 0
                delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, aide_nt)
                delegate_info_expect_data = {"Released": 0, "RestrictingPlan": del_amt[50] - BD.delegate_limit,
                                             "ReleasedHes": 0, "RestrictingPlanHes": 0,
                                             "LockReleasedHes": 0, "LockRestrictingPlanHes": 0}
                lock_expect_data = {(4, del_amt[2850], del_amt[150]), (5, del_amt[1550], del_amt[660])}

            Assertion.assert_delegate_info_contain(delegate_info, delegate_info_expect_data)
            Assertion.del_locks_money(normal_aide0, normal_aide0_nt, lock_expect_data)

        logger.info(f"锁定金 委托A节点 2000")
        assert normal_aide0.delegate.delegate(del_amt[2000], 3,
                                              private_key=normal_aide0_nt.del_pk)['code'] == 0
        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        delegate_info_expect_data = {"Released": 0, "RestrictingPlan": del_amt[850],
                                     "ReleasedHes": 0, "RestrictingPlanHes": 0,
                                     "LockReleasedHes": del_amt[1340], "LockRestrictingPlanHes": del_amt[660]}
        Assertion.assert_delegate_info_contain(delegate_info, delegate_info_expect_data)

        lock_expect_data = {(4, del_amt[2850], del_amt[150]), (5, del_amt[210], 0)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, lock_expect_data)

        assert normal_aide0.platon.block_number < 160 * 4
        return red_acc_amt, restr_info

    @staticmethod
    def _cycle_5_block_641_800(del_amt, loop_delegate, ago_acc_amt, ago_restr_info):
        normal_aide0, normal_aide0_nt, all_aide_nt_list, plan, init_restr_info = loop_delegate
        assert normal_aide0.platon.block_number > 160 * 4

        logger.info(f"cycle5 验证锁仓计划 200未被委托  释放300 账户余额+200 欠释放字段+100")
        restr_info = PF.p_get_restricting_info(normal_aide0, normal_aide0_nt)
        restr_expect_data = {
            'balance': {"old_value": del_amt[2400], "new_value": del_amt[2200]},
            'debt': {"old_value": 0, "new_value": del_amt[100]},
            'plans': {'old_value_len': 9, 'new_value_len': 8}, }
        Assertion.assert_restr_amt(ago_restr_info, restr_info, restr_expect_data)
        acc_amt = normal_aide0.platon.get_balance(normal_aide0_nt.del_addr)
        assert abs(acc_amt - ago_acc_amt - del_amt[200]) < BD.von_min

        logger.info(f"锁定期数据")
        lock_expect_data = {(5, del_amt[210], 0)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, lock_expect_data)
        logger.info(f"锁定期已释放数据")
        lock_info_release_data = {'Released': del_amt[2850], 'RestrictingPlan': del_amt[150]}
        Assertion.del_lock_release_money(normal_aide0, normal_aide0_nt, lock_info_release_data)

        logger.info(f"查询A节点委托数据")
        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        delegate_info_expect_data = {"Released": del_amt[1340], "RestrictingPlan": del_amt[1510],
                                     "ReleasedHes": 0, "RestrictingPlanHes": 0,
                                     "LockReleasedHes": 0, "LockRestrictingPlanHes": 0}
        Assertion.assert_delegate_info_contain(delegate_info, delegate_info_expect_data)

        logger.info(f"赎回A节点委托信息 2000 = 生效期自由金额1340 + 生效期锁仓金额660")
        assert normal_aide0.delegate.withdrew_delegate(amount=del_amt[2000],
                                                       staking_block_identifier=normal_aide0_nt.StakingBlockNum,
                                                       node_id=normal_aide0_nt.node_id,
                                                       private_key=normal_aide0_nt.del_pk, )['code'] == 0

        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        delegate_info_expect_data = {"Released": 0, "RestrictingPlan": del_amt[850],
                                     "ReleasedHes": 0, "RestrictingPlanHes": 0,
                                     "LockReleasedHes": 0, "LockRestrictingPlanHes": 0}
        Assertion.assert_delegate_info_contain(delegate_info, delegate_info_expect_data)

        logger.info(f"赎回冻结金委托后验证锁定期数据")
        lock_expect_data = {(5, del_amt[210], 0), (6, del_amt[1340], del_amt[660])}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, lock_expect_data)

        logger.info(f"使用账户自由金额委托 A节点 自由金额100")
        assert normal_aide0.delegate.delegate(del_amt[100], 0, private_key=normal_aide0_nt.del_pk)['code'] == 0
        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        delegate_info_expect_data = {"Released": 0, "RestrictingPlan": del_amt[850],
                                     "ReleasedHes": del_amt[100], "RestrictingPlanHes": 0,
                                     "LockReleasedHes": 0, "LockRestrictingPlanHes": 0}
        Assertion.assert_delegate_info_contain(delegate_info, delegate_info_expect_data)
        acc_amt_2 = normal_aide0.platon.get_balance(normal_aide0_nt.del_addr)
        assert del_amt[100] - (acc_amt - acc_amt_2) < BD.von_min

        acc_amt_before, red_acc_amt, restr_before, restr_later = \
            redeem_del_wait_unlock_diff_balance_restr(normal_aide0, normal_aide0_nt, wait_num=0, diff_restr=True)
        restr_expect_data = {
            'balance': {"old_value": del_amt[2200], "new_value": del_amt[2100]},
            'debt': {"old_value": del_amt[100], "new_value": 0},
            'Pledge': {"old_value": del_amt[2200], "new_value": del_amt[2050]}}
        Assertion.assert_restr_amt(restr_before, restr_later, restr_expect_data)
        assert abs(red_acc_amt - acc_amt_before - del_amt[2850] - del_amt[100]) < BD.von_min

        assert normal_aide0.platon.block_number < 160 * 5
        return red_acc_amt, restr_later

    @staticmethod
    def _cycle_6_block_801_960(del_amt, loop_delegate, ago_acc_amt, ago_restr_info):
        normal_aide0, normal_aide0_nt, all_aide_nt_list, plan, init_restr_info = loop_delegate
        assert normal_aide0.platon.block_number > 160 * 5

        logger.info(f"cycle6 验证锁仓计划 释放300 账户余额+0 欠释放字段+300")
        restr_info = PF.p_get_restricting_info(normal_aide0, normal_aide0_nt)
        restr_expect_data = {
            'balance': {"old_value": del_amt[2100], "new_value": del_amt[2050]},
            'debt': {"old_value": 0, "new_value": del_amt[250]},
            'plans': {'old_value_len': 8, 'new_value_len': 7}, }
        Assertion.assert_restr_amt(ago_restr_info, restr_info, restr_expect_data)
        acc_amt = normal_aide0.platon.get_balance(normal_aide0_nt.del_addr)
        assert abs(acc_amt - ago_acc_amt - del_amt[50]) < BD.von_min

        logger.info(f"验证锁定期已释放金额")
        lock_expect_data = {(6, del_amt[1340], del_amt[660])}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, lock_expect_data)
        logger.info(f"锁定期已释放数据")
        lock_info_release_data = {'Released': del_amt[210], 'RestrictingPlan': 0}
        Assertion.del_lock_release_money(normal_aide0, normal_aide0_nt, lock_info_release_data)

        logger.info(f"领取已释放的锁定金")
        acc_amt_before, red_acc_amt, restr_before, restr_later = \
            redeem_del_wait_unlock_diff_balance_restr(normal_aide0, normal_aide0_nt, wait_num=0, diff_restr=True)
        Assertion.assert_restr_amt(restr_before, restr_later, {})
        assert abs(red_acc_amt - acc_amt_before - del_amt[210]) < BD.von_min

        logger.info("查询A节点的委托信息")
        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        delegate_info_expect_data = {"Released": del_amt[100], "RestrictingPlan": del_amt[850],
                                     "ReleasedHes": 0, "RestrictingPlanHes": 0,
                                     "LockReleasedHes": 0, "LockRestrictingPlanHes": 0}
        Assertion.assert_delegate_info_contain(delegate_info, delegate_info_expect_data)

        logger.info("赎回 ABCD 节点的委托")
        for i in range(4):
            aide_nt, node_id = all_aide_nt_list[i], all_aide_nt_list[i].node_id
            if i == 0:
                logger.info("A节点 赎回100 生效期自由金额100")
                assert normal_aide0.delegate.withdrew_delegate(amount=del_amt[100],
                                                               staking_block_identifier=aide_nt.StakingBlockNum,
                                                               node_id=node_id,
                                                               private_key=normal_aide0_nt.del_pk, )['code'] == 0
                delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, aide_nt)
                delegate_info_expect_data = {"Released": 0, "RestrictingPlan": del_amt[850],
                                             "ReleasedHes": 0, "RestrictingPlanHes": 0,
                                             "LockReleasedHes": 0, "LockRestrictingPlanHes": 0}
                lock_expect_data = {(6, del_amt[1340], del_amt[660]), (7, del_amt[100], 0)}
            elif i == 1:
                logger.info("B节点 赎回550 生效期自由金额250 + 生效期锁仓金额300")
                assert normal_aide0.delegate.withdrew_delegate(amount=del_amt[550],
                                                               staking_block_identifier=aide_nt.StakingBlockNum,
                                                               node_id=node_id,
                                                               private_key=normal_aide0_nt.del_pk, )['code'] == 0
                assert PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, aide_nt) is None
                lock_expect_data = {(6, del_amt[1340], del_amt[660]), (7, del_amt[350], del_amt[300])}
            elif i == 2:
                logger.info("C节点 生效期自由金额250 + 锁仓金额200")
                assert normal_aide0.delegate.withdrew_delegate(amount=del_amt[450],
                                                               staking_block_identifier=aide_nt.StakingBlockNum,
                                                               node_id=node_id,
                                                               private_key=normal_aide0_nt.del_pk, )['code'] == 0
                assert PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, aide_nt) is None
                lock_expect_data = {(6, del_amt[1340], del_amt[660]), (7, del_amt[600], del_amt[500])}
            else:
                logger.info("D节点 赎回40 生效期锁仓金额40")
                del_amt_40 = BD.delegate_limit * 4
                assert normal_aide0.delegate.withdrew_delegate(amount=del_amt_40,
                                                               staking_block_identifier=aide_nt.StakingBlockNum,
                                                               node_id=node_id,
                                                               private_key=normal_aide0_nt.del_pk, )['code'] == 0
                assert PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, aide_nt) is None
                lock_expect_data = {(6, del_amt[1340], del_amt[660]), (7, del_amt[600], del_amt[500] + del_amt_40)}

            Assertion.assert_delegate_info_contain(delegate_info, delegate_info_expect_data)
            Assertion.del_locks_money(normal_aide0, normal_aide0_nt, lock_expect_data)

        assert normal_aide0.platon.block_number < 160 * 6
        return red_acc_amt, restr_later

    @staticmethod
    def _cycle_7_block_961_1120(del_amt, loop_delegate, ago_acc_amt, ago_restr_info):
        normal_aide0, normal_aide0_nt, all_aide_nt_list, plan, init_restr_info = loop_delegate
        assert normal_aide0.platon.block_number > 160 * 6

        logger.info(f"cycle7 验证锁仓计划 释放300 账户余额+0 欠释放字段+300")
        restr_info = PF.p_get_restricting_info(normal_aide0, normal_aide0_nt)
        restr_expect_data = {'debt': {"old_value": del_amt[250], "new_value": del_amt[550]},
                             'plans': {'old_value_len': 7, 'new_value_len': 6}, }
        Assertion.assert_restr_amt(ago_restr_info, restr_info, restr_expect_data)

        logger.info(f"验证锁定期已释放金额")
        lock_expect_data = {(7, del_amt[600], del_amt[540])}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, lock_expect_data)
        logger.info(f"锁定期已释放数据")
        lock_info_release_data = {'Released': del_amt[1340], 'RestrictingPlan': del_amt[660]}
        Assertion.del_lock_release_money(normal_aide0, normal_aide0_nt, lock_info_release_data)

        logger.info(f"领取锁定金 自由金额1340 锁仓金额660")
        acc_amt_before, red_acc_amt, restr_before, restr_later = \
            redeem_del_wait_unlock_diff_balance_restr(normal_aide0, normal_aide0_nt, wait_num=0, diff_restr=True)

        restr_expect_data = {
            'balance': {"old_value": del_amt[2050], "new_value": del_amt[1500]},
            'debt': {"old_value": del_amt[550], "new_value": 0},
            'Pledge': {"old_value": del_amt[2050], "new_value": del_amt[1390]}}
        Assertion.assert_restr_amt(restr_before, restr_later, restr_expect_data)
        assert abs(red_acc_amt - ago_acc_amt - del_amt[1340] - del_amt[550]) < BD.von_min

        logger.info(f"使用锁定金委托 A节点 1000 ")
        assert normal_aide0.delegate.delegate(del_amt[1000], 3, private_key=normal_aide0_nt.del_pk)['code'] == 0
        lock_expect_data = {(7, del_amt[140], 0)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, lock_expect_data)

        logger.info(f"A节点的委托信息")
        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        delegate_info_expect_data = {"Released": 0, "RestrictingPlan": del_amt[850],
                                     "ReleasedHes": 0, "RestrictingPlanHes": 0,
                                     "LockReleasedHes": del_amt[460], "LockRestrictingPlanHes": del_amt[540]}
        Assertion.assert_delegate_info_contain(delegate_info, delegate_info_expect_data)

        assert normal_aide0.platon.block_number < 160 * 7
        return red_acc_amt, restr_later

    @staticmethod
    def _cycle_8_block_1121_1280(del_amt, loop_delegate, ago_acc_amt, ago_restr_info):
        normal_aide0, normal_aide0_nt, all_aide_nt_list, plan, init_restr_info = loop_delegate
        assert normal_aide0.platon.block_number > 160 * 7
        logger.info(f"cycle8 验证锁仓计划 释放300 账户余额+0 欠释放字段+300")
        restr_info = PF.p_get_restricting_info(normal_aide0, normal_aide0_nt)
        restr_expect_data = {
            'balance': {"old_value": del_amt[1500], "new_value": del_amt[1390]},
            'debt': {"old_value": 0, "new_value": del_amt[190]},
            'plans': {'old_value_len': 6, 'new_value_len': 5}, }
        Assertion.assert_restr_amt(ago_restr_info, restr_info, restr_expect_data)
        acc_amt = normal_aide0.platon.get_balance(normal_aide0_nt.del_addr)
        assert abs(acc_amt - ago_acc_amt - del_amt[110]) < BD.von_min

        logger.info(f"锁定期已释放数据")
        lock_info_release_data = {'Released': del_amt[140], 'RestrictingPlan': 0}
        Assertion.del_lock_release_money(normal_aide0, normal_aide0_nt, lock_info_release_data)

        logger.info(f"领取锁定金 自由金额140")
        acc_amt_before, red_acc_amt, restr_before, restr_later = \
            redeem_del_wait_unlock_diff_balance_restr(normal_aide0, normal_aide0_nt, wait_num=0, diff_restr=True)
        Assertion.assert_restr_amt(restr_before, restr_later, {})
        assert abs(red_acc_amt - acc_amt_before - del_amt[140]) < BD.von_min

        logger.info(f"A节点的委托信息")
        delegate_info = PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        delegate_info_expect_data = {"Released": del_amt[460], "RestrictingPlan": del_amt[1390],
                                     "ReleasedHes": 0, "RestrictingPlanHes": 0,
                                     "LockReleasedHes": 0, "LockRestrictingPlanHes": 0}
        Assertion.assert_delegate_info_contain(delegate_info, delegate_info_expect_data)

        logger.info(f"全部赎回 460 + 1390")
        assert normal_aide0.delegate.withdrew_delegate(amount=del_amt[1850],
                                                       staking_block_identifier=normal_aide0_nt.StakingBlockNum,
                                                       node_id=normal_aide0_nt.node_id,
                                                       private_key=normal_aide0_nt.del_pk, )['code'] == 0
        lock_expect_data = {(9, del_amt[460], del_amt[1390])}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, lock_expect_data)
        assert PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt) is None

        assert normal_aide0.platon.block_number < 160 * 8
        return red_acc_amt, restr_later

    @staticmethod
    def _cycle_9(del_amt, loop_delegate, ago_acc_amt, ago_restr_info):
        normal_aide0, normal_aide0_nt, all_aide_nt_list, plan, init_restr_info = loop_delegate
        logger.info(f"cycle9 验证锁仓计划 释放300 账户余额+0 欠释放字段+300")
        restr_info = PF.p_get_restricting_info(normal_aide0, normal_aide0_nt)
        restr_expect_data = {
            'debt': {"old_value": del_amt[190], "new_value": del_amt[490]},
            'plans': {'old_value_len': 5, 'new_value_len': 4}, }
        Assertion.assert_restr_amt(ago_restr_info, restr_info, restr_expect_data)
        acc_amt = normal_aide0.platon.get_balance(normal_aide0_nt.del_addr)
        assert ago_acc_amt - acc_amt < BD.von_min
        return acc_amt, restr_info

    @staticmethod
    def _cycle_10(del_amt, loop_delegate, ago_acc_amt, ago_restr_info):
        normal_aide0, normal_aide0_nt, all_aide_nt_list, plan, init_restr_info = loop_delegate
        logger.info(f"cycle10 验证锁仓计划 释放300 账户余额+0 欠释放字段+300")
        restr_info = PF.p_get_restricting_info(normal_aide0, normal_aide0_nt)

        restr_expect_data = {
            'debt': {"old_value": del_amt[490], "new_value": del_amt[790]},
            'plans': {'old_value_len': 4, 'new_value_len': 3}, }
        Assertion.assert_restr_amt(ago_restr_info, restr_info, restr_expect_data)
        acc_amt = normal_aide0.platon.get_balance(normal_aide0_nt.del_addr)
        assert ago_acc_amt - acc_amt < BD.von_min

        logger.info(f"领取已解锁的锁定金")
        acc_amt_before, red_acc_amt, restr_before, restr_later = \
            redeem_del_wait_unlock_diff_balance_restr(normal_aide0, normal_aide0_nt, wait_num=0, diff_restr=True)

        restr_expect_data = {
            'balance': {"old_value": del_amt[1390], "new_value": del_amt[600]},
            'debt': {"old_value": del_amt[790], "new_value": 0},
            'Pledge': {"old_value": del_amt[1390], "new_value": 0}}
        Assertion.assert_restr_amt(restr_before, restr_later, restr_expect_data)
        assert abs(red_acc_amt - acc_amt_before - del_amt[460] - del_amt[790]) < BD.von_min

        return red_acc_amt, restr_later

    @staticmethod
    def _cycle_11(del_amt, loop_delegate, ago_acc_amt, ago_restr_info):
        normal_aide0, normal_aide0_nt, all_aide_nt_list, plan, init_restr_info = loop_delegate
        logger.info(f"cycle11 验证锁仓计划 释放300 账户余额+300")
        restr_info = PF.p_get_restricting_info(normal_aide0, normal_aide0_nt)

        restr_expect_data = {
            'balance': {"old_value": del_amt[600], "new_value": del_amt[300]},
            'plans': {'old_value_len': 3, 'new_value_len': 2}, }
        Assertion.assert_restr_amt(ago_restr_info, restr_info, restr_expect_data)
        acc_amt = normal_aide0.platon.get_balance(normal_aide0_nt.del_addr)
        assert del_amt[300] - (acc_amt - ago_acc_amt) < BD.von_min

        logger.info(f"已无锁定期数据,并领取")
        Assertion.del_lock_info_zero_money(normal_aide0, normal_aide0_nt)
        acc_amt_before, red_acc_amt = \
            redeem_del_wait_unlock_diff_balance_restr(normal_aide0, normal_aide0_nt, wait_num=0)
        assert red_acc_amt - acc_amt_before < BD.von_min
        return red_acc_amt, restr_info

    @staticmethod
    def _cycle_12(del_amt, loop_delegate, ago_acc_amt, ago_restr_info):
        normal_aide0, normal_aide0_nt, all_aide_nt_list, plan, init_restr_info = loop_delegate
        logger.info(f"cycle12 验证锁仓计划 释放300 账户余额+200")
        restr_info = PF.p_get_restricting_info(normal_aide0, normal_aide0_nt)

        restr_expect_data = {
            'balance': {"old_value": del_amt[300], "new_value": del_amt[100]},
            'plans': {'old_value_len': 2, 'new_value_len': 1}, }
        Assertion.assert_restr_amt(ago_restr_info, restr_info, restr_expect_data)
        acc_amt = normal_aide0.platon.get_balance(normal_aide0_nt.del_addr)
        assert del_amt[200] - (acc_amt - ago_acc_amt) < BD.von_min

        logger.info(f"已无锁定期数据,并领取")
        Assertion.del_lock_info_zero_money(normal_aide0, normal_aide0_nt)
        acc_amt_before, red_acc_amt = \
            redeem_del_wait_unlock_diff_balance_restr(normal_aide0, normal_aide0_nt, wait_num=0)
        assert red_acc_amt - acc_amt_before < BD.von_min
        return red_acc_amt, restr_info

    @staticmethod
    def _cycle_13(del_amt, loop_delegate, ago_acc_amt):
        normal_aide0, normal_aide0_nt, all_aide_nt_list, plan, init_restr_info = loop_delegate
        logger.info(f"cycle12 验证锁仓计划 释放300 账户余额+100")
        # Account is not found on restricting contract
        assert PF.p_get_restricting_info(normal_aide0, normal_aide0_nt) == ERROR_CODE[304005]

        acc_amt = normal_aide0.platon.get_balance(normal_aide0_nt.del_addr)
        assert del_amt[100] - (acc_amt - ago_acc_amt) < BD.von_min

        logger.info(f"已无锁定期数据,并领取")
        Assertion.del_lock_info_zero_money(normal_aide0, normal_aide0_nt)
        acc_amt_before, red_acc_amt = \
            redeem_del_wait_unlock_diff_balance_restr(normal_aide0, normal_aide0_nt, wait_num=0)
        assert red_acc_amt - acc_amt_before < BD.von_min
        logger.info(f"最后账户余额: {red_acc_amt}")
        logger.info(f"质押合约地址金额：{normal_aide0.platon.get_balance(normal_aide0.staking.contract_address)}")
        logger.info(f"锁仓合约地址金额：{normal_aide0.platon.get_balance(normal_aide0.restricting.contract_address)}")
        return red_acc_amt

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
    def test_loop_delegate(self, loop_delegate):
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide0_nt, all_aide_nt_list, plan, init_restr_info = loop_delegate
        all_aide_nt_list.insert(0, normal_aide0_nt)
        del_amt = {i * 10: BD.delegate_limit * i for i in range(5, 301)}

        ago_acc_amt, ago_restr_info = self._cycle_2_block_161_320(del_amt, loop_delegate)
        wait_settlement(normal_aide0)
        ago_acc_amt, ago_restr_info = self._cycle_3_block_321_480(del_amt, loop_delegate, ago_acc_amt, ago_restr_info)
        wait_settlement(normal_aide0)
        ago_acc_amt, ago_restr_info = self._cycle_4_block_481_640(del_amt, loop_delegate, ago_acc_amt, ago_restr_info)
        wait_settlement(normal_aide0)
        ago_acc_amt, ago_restr_info = self._cycle_5_block_641_800(del_amt, loop_delegate, ago_acc_amt, ago_restr_info)
        wait_settlement(normal_aide0)
        ago_acc_amt, ago_restr_info = self._cycle_6_block_801_960(del_amt, loop_delegate, ago_acc_amt, ago_restr_info)
        wait_settlement(normal_aide0)
        ago_acc_amt, ago_restr_info = self._cycle_7_block_961_1120(del_amt, loop_delegate, ago_acc_amt, ago_restr_info)
        wait_settlement(normal_aide0)
        ago_acc_amt, ago_restr_info = self._cycle_8_block_1121_1280(del_amt, loop_delegate, ago_acc_amt, ago_restr_info)
        wait_settlement(normal_aide0)
        ago_acc_amt, ago_restr_info = self._cycle_9(del_amt, loop_delegate, ago_acc_amt, ago_restr_info)
        wait_settlement(normal_aide0)
        ago_acc_amt, ago_restr_info = self._cycle_10(del_amt, loop_delegate, ago_acc_amt, ago_restr_info)
        wait_settlement(normal_aide0)
        ago_acc_amt, ago_restr_info = self._cycle_11(del_amt, loop_delegate, ago_acc_amt, ago_restr_info)
        wait_settlement(normal_aide0)
        ago_acc_amt, ago_restr_info = self._cycle_12(del_amt, loop_delegate, ago_acc_amt, ago_restr_info)
        wait_settlement(normal_aide0)
        acc_amt = self._cycle_13(del_amt, loop_delegate, ago_acc_amt)
        # 所有的钱都已赎回至账户 账户金额10W
        assert BD.init_del_account_amt - acc_amt < BD.von_limit


@pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 1, }], indirect=True)
@pytest.mark.parametrize('many_cycle_restr_redeem_delegate', [{"ManyAcc": False}], indirect=True)
def test_many_cycle_restr_draw_1(many_cycle_restr_redeem_delegate):
    """
    test_LS_UPV_023: 锁仓多个释放期，委托赎回
    """
    normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt = many_cycle_restr_redeem_delegate
    # 查锁仓计划,欠释放100,总额1000
    restr_info = PF.p_get_restricting_info(normal_aide0, normal_aide0_nt)
    assert restr_info['debt'] == BD.delegate_limit * 10

    for i in range(9):
        acc_amt_before, red_acc_amt, restr_info_before, restr_info_later = \
            redeem_del_wait_unlock_diff_balance_restr(normal_aide0, normal_aide0_nt, wait_num=1, diff_restr=True)

        if i == 0:
            restr_expect_data = {
                'balance': {"old_value": BD.delegate_amount, "new_value": BD.delegate_limit * 80},
                'debt': {'new_value': 0, 'old_value': BD.delegate_limit * 10},
                'plans': {'old_value_len': 9, 'new_value_len': 8},
                'Pledge': {"old_value": BD.delegate_amount, "new_value": 0}}
            Assertion.assert_restr_amt(restr_info_before, restr_info_later, restr_expect_data)
            assert red_acc_amt - acc_amt_before - BD.delegate_amount - BD.delegate_limit * 20 < BD.von_min
        else:
            # 因为是全部赎回锁仓金额,这里是锁仓计划正常释放至余额
            init_restr_balance = BD.delegate_limit * 80
            decrease_progressively = BD.delegate_limit * 10
            restr_expect_data = {
                'balance': {"old_value": init_restr_balance - decrease_progressively * i + decrease_progressively,
                            "new_value": init_restr_balance - decrease_progressively * i},
                'plans': {'old_value_len': 9 - i, 'new_value_len': 8 - i}}
            if i == 8:
                Assertion.assert_restr_amt(restr_info_before, restr_info_later, {})
            else:
                Assertion.assert_restr_amt(restr_info_before, restr_info_later, restr_expect_data)
            assert red_acc_amt - acc_amt_before - BD.delegate_limit * 10 < BD.von_min
    pass


@pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 1, }], indirect=True)
def test_many_cycle_restr_draw_2(choose_undelegate_freeze_duration, normal_aides):
    """
    test_LS_UPV_023: 锁仓多个释放期，委托赎回
    """
    chain, new_gen_file = choose_undelegate_freeze_duration
    chain.install(genesis_file=new_gen_file)
    time.sleep(5)

    normal_aide0, normal_aide1 = normal_aides[0], normal_aides[1],

    lockup_amount = BD.delegate_amount  # platon/10 * 100
    lock_amt = BD.delegate_limit * 10
    assert lock_amt * 10 == lockup_amount
    plan = [{'Epoch': i, 'Amount': lock_amt} for i in range(1, 11)]

    normal_aide0_nt = create_sta_del(normal_aide0, plan, mix=True)

    wait_settlement(normal_aide0)
    # 赎回自由金额1000 + 锁仓100
    undelegate_amt = BD.delegate_limit * 10

    assert normal_aide0.delegate.withdrew_delegate(private_key=normal_aide0_nt.del_pk,
                                                   staking_block_identifier=normal_aide0_nt.StakingBlockNum,
                                                   amount=BD.delegate_amount + undelegate_amt, )['code'] == 0
    for i in range(10):
        acc_amt_before, red_acc_amt, restr_info_before, restr_info_later = \
            redeem_del_wait_unlock_diff_balance_restr(normal_aide0, normal_aide0_nt, wait_num=1, diff_restr=True)

        if i != 9:
            assert normal_aide0.delegate.withdrew_delegate(private_key=normal_aide0_nt.del_pk,
                                                           staking_block_identifier=normal_aide0_nt.StakingBlockNum,
                                                           amount=undelegate_amt, )['code'] == 0
        if i == 0:
            restr_expect_data = {
                'balance': {"old_value": BD.delegate_amount, "new_value": BD.delegate_limit * 90},
                'plans': {'old_value_len': 9, 'new_value_len': 8},
                'Pledge': {"old_value": BD.delegate_amount, "new_value": BD.delegate_limit * 90}}
            Assertion.assert_restr_amt(restr_info_before, restr_info_later, restr_expect_data)
            assert red_acc_amt - acc_amt_before - BD.delegate_amount - BD.delegate_limit * 20 < BD.von_min
        elif i == 9:
            assert red_acc_amt - acc_amt_before - BD.delegate_limit * 10 < BD.von_min
        else:
            init_restr_balance = BD.delegate_limit * 90
            decrease_progressively = BD.delegate_limit * 10
            restr_expect_data = {
                'balance': {"old_value": init_restr_balance - decrease_progressively * i + decrease_progressively,
                            "new_value": init_restr_balance - decrease_progressively * i},
                'plans': {'old_value_len': 9 - i, 'new_value_len': 8 - i},
                'Pledge': {"old_value": init_restr_balance - decrease_progressively * i + decrease_progressively,
                           "new_value": init_restr_balance - decrease_progressively * i}}
            if i == 8:
                restr_expect_data = {
                    'balance': {"old_value": init_restr_balance - decrease_progressively * i + decrease_progressively,
                                "new_value": init_restr_balance - decrease_progressively * i},
                    'Pledge': {"old_value": init_restr_balance - decrease_progressively * i + decrease_progressively,
                               "new_value": init_restr_balance - decrease_progressively * i}}
            Assertion.assert_restr_amt(restr_info_before, restr_info_later, restr_expect_data)
            assert red_acc_amt - acc_amt_before - BD.delegate_limit * 10 < BD.von_min


@pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 1, }], indirect=True)
def test_restr_draw_3(choose_undelegate_freeze_duration, normal_aides):
    """
    test_UP_FV_018: 赎回锁仓委托
    """
    chain, new_gen_file = choose_undelegate_freeze_duration
    chain.install(genesis_file=new_gen_file)
    time.sleep(5)

    normal_aide0, normal_aide1 = normal_aides[0], normal_aides[1],

    plan = [{'Epoch': 1, 'Amount': BD.delegate_amount}]

    normal_aide0_nt = create_sta_del(normal_aide0, plan, mix=True)

    wait_settlement(normal_aide0)
    # 赎回自由金额1000 + 锁仓500
    undelegate_amt = BD.delegate_amount + BD.delegate_limit * 50

    amt_before, amt_later, restr_before, restr_later = \
        withdrew_del_diff_balance_restr(normal_aide0, normal_aide0_nt, undelegate_amt, diff_restr=True)
    assert abs(amt_later - amt_before) < BD.von_min
    Assertion.assert_restr_amt(restr_before, restr_later, {})

    acc_amt_before, red_acc_amt, restr_info_before, restr_info_later = \
        redeem_del_wait_unlock_diff_balance_restr(normal_aide0, normal_aide0_nt, wait_num=1, diff_restr=True)
    assert abs(red_acc_amt - acc_amt_before - undelegate_amt) < BD.von_min

    expect_data = {'balance': {"old_value": BD.delegate_amount, "new_value": BD.delegate_limit * 50},
                   'debt': {"old_value": BD.delegate_amount, "new_value": BD.delegate_limit * 50},
                   'Pledge': {"old_value": BD.delegate_amount, "new_value": BD.delegate_limit * 50}}
    Assertion.assert_restr_amt(restr_info_before, restr_info_later, expect_data)


@pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 1, }], indirect=True)
def test_restr_draw_4(choose_undelegate_freeze_duration, normal_aides):
    """锁仓计划中 包含有钱释放/没钱两种状态 结合 赎回委托"""
    chain, new_gen_file = choose_undelegate_freeze_duration
    chain.install(genesis_file=new_gen_file)
    time.sleep(5)

    normal_aide0, normal_aide1 = normal_aides[0], normal_aides[1],
    del_amt = BD.delegate_limit * 20
    plan = [{'Epoch': 1, 'Amount': del_amt},
            {'Epoch': 2, 'Amount': del_amt},
            {'Epoch': 3, 'Amount': del_amt},
            {'Epoch': 4, 'Amount': del_amt},
            {'Epoch': 5, 'Amount': del_amt}]

    sta_addr, sta_pk, del_addr, del_pk = create_sta_del_account(normal_aide0, BD.init_sta_account_amt,
                                                                BD.init_del_account_amt)

    assert normal_aide0.staking.create_staking(benefit_address=sta_addr, private_key=sta_pk)['code'] == 0
    StakingBlockNum = normal_aide0.staking.staking_info.StakingBlockNum

    assert normal_aide0.restricting.restricting(release_address=del_addr, plans=plan,
                                                private_key=del_pk)['code'] == 0
    restr_info = normal_aide0.restricting.get_restricting_info(del_addr)
    logger.info(f"restricting: {restr_info}")

    for i in range(6):
        if i < 3:  # 第四个结算周期 锁仓中已经没钱了
            restricting_contract_1 = normal_aide0.platon.get_balance(normal_aide0.restricting.contract_address)
            logger.info(f"{i} - restricting_contract_1: {restricting_contract_1}")
            del_res = normal_aide0.delegate.delegate(amount=del_amt, balance_type=1, private_key=del_pk)
            assert del_res['code'] == 0

            restricting_contract_2 = normal_aide0.platon.get_balance(normal_aide0.restricting.contract_address)
            logger.info(f"{i} - restricting_contract_2: {restricting_contract_2}")

        delegate_restr_info = normal_aide0.restricting.get_restricting_info(del_addr)
        logger.info(f"{i} - delegate_restr_info: {delegate_restr_info}")

        amt_before = normal_aide0.platon.get_balance(del_addr)
        wait_settlement(normal_aide0)
        amt_last = normal_aide0.platon.get_balance(del_addr)
        if i < 3:
            assert normal_aide0.delegate.withdrew_delegate(del_amt, StakingBlockNum,
                                                           private_key=del_pk)['code'] == 0
            restricting_contract_3 = normal_aide0.platon.get_balance(normal_aide0.restricting.contract_address)
            logger.info(f"{i} - restricting_contract_3: {restricting_contract_3}")

        withdrew_delegate_restr_info = normal_aide0.restricting.get_restricting_info(del_addr)
        logger.info(f"{i} - withdrew_delegate_restr_info: {withdrew_delegate_restr_info}")

        if i < 2:
            # 锁仓计划里还有钱，会正常释放金额 至账户
            assert amt_last - amt_before == del_amt
            # 锁仓合约钱的变化
            # 1. 拿去委托会扣 200
            # 2. 过了结算周期 会自动释放 200
            assert restricting_contract_1 - restricting_contract_2 == del_amt
            assert restricting_contract_2 - restricting_contract_3 == del_amt

        elif i == 2:
            assert restricting_contract_1 - restricting_contract_2 == del_amt
            assert restricting_contract_2 == restricting_contract_3
            expect_data = {'plans': {'old_value_len': 3, 'new_value_len': 2},
                           'debt': {"old_value": 0, "new_value": BD.delegate_limit * 20}}
            Assertion.assert_restr_amt(delegate_restr_info, withdrew_delegate_restr_info, expect_data)

        elif i == 3:
            expect_data = {'plans': {'old_value_len': 2, 'new_value_len': 1},
                           'debt': {"old_value": BD.delegate_limit * 20, "new_value": BD.delegate_limit * 40}}
            Assertion.assert_restr_amt(delegate_restr_info, withdrew_delegate_restr_info, expect_data)

        elif i == 4:
            expect_data = {'debt': {"old_value": BD.delegate_limit * 40, "new_value": BD.delegate_limit * 60}}
            Assertion.assert_restr_amt(delegate_restr_info, withdrew_delegate_restr_info, expect_data)
