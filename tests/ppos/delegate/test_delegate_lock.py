"""
@Author  :  Jw
@Contact :  libai7236@gmail.com
@Time    :  2022/8/23 11:38
@Version :  platon-1.3.0
@Desc    :  委托锁定
"""
import inspect
from decimal import Decimal

import pytest
from loguru import logger
from platon._utils.error_code import ERROR_CODE

from lib.assertion import Assertion
from lib.basic_data import BaseData as BD
from lib.funcs import wait_settlement, wait_consensus
from lib.utils import get_pledge_list, PrintInfo as PF
from tests.conftest import generate_account

logger.add("logs/case_{time}.log", rotation="500MB")


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
        assert del_amt3 - (red_acc_amt - acc_amt_bef) < BD.von_limit
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
        assert Released - (red_acc_amt - acc_amt_bef) < BD.von_limit

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
        assert Released - (red_acc_amt - acc_amt_bef) < BD.von_limit

        logger.info(f'{"-锁仓计划信息不变,锁定期锁仓金额已全部再次委托":*^50s}')
        restr_info = PF.p_get_restricting_info(normal_aide0, normal_aide0_nt)
        assert restr_info['Pledge'] == BD.delegate_amount
        assert restr_info['balance'] == BD.delegate_amount and restr_info['debt'] == 0


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
        assert del_amt3 - (red_acc_amt - acc_amt_bef) < BD.von_limit
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
        assert Released - abs(red_acc_amt - acc_amt_bef) < BD.von_limit

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
        测试节点状态异常(主动赎回质押金额) 使用锁定期金额 自由金额进行委托
        - 锁定期无锁定金额 有释放金额 进行委托
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
        assert normal_aide0.delegate.withdrew_delegate(BD.delegate_amount, normal_aide1_nt.StakingBlockNum,
                                                       node_id=normal_aide1_nt.node_id,
                                                       private_key=normal_aide1_nt.del_pk)['code'] == 0
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
    """测试赎回委托"""

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
        assert normal_aide0.delegate.withdrew_delegate(BD.delegate_limit * 10,
                                                       private_key=normal_aide0_nt.del_pk)['code'] == 0
        expect_data1 = {(3, lock_residue_amt + BD.delegate_limit * 10, 0)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data1)

        logger.info(f"-赎回委托 delegate_amount = limit * 100")
        assert normal_aide0.delegate.withdrew_delegate(BD.delegate_amount,
                                                       private_key=normal_aide0_nt.del_pk)['code'] == 0

        expect_data2 = {(3, BD.delegate_amount, lock_residue_amt + BD.delegate_limit * 10)}
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data2)

        logger.info(f"-赎回委托 limit * 80 -> fail")
        res = normal_aide0.delegate.withdrew_delegate(BD.delegate_limit * 80, private_key=normal_aide0_nt.del_pk)
        assert res['message'] == ERROR_CODE[301113]

        wait_settlement(normal_aide0)

        logger.info(f"-跨结算周期赎回委托 limit * 70")
        assert normal_aide0.delegate.withdrew_delegate(BD.delegate_limit * 70,
                                                       private_key=normal_aide0_nt.del_pk)['code'] == 0
        expect_data2.add((4, 0, BD.delegate_limit * 70))
        Assertion.del_locks_money(normal_aide0, normal_aide0_nt, expect_data2)

        logger.info(f"-等待锁定期自由金额解锁并领取")
        acc_amt_before, red_acc_amt, restr_info_before, restr_info_later = \
            redeem_del_wait_unlock_diff_balance_restr(normal_aide0, normal_aide0_nt, wait_num=1, diff_restr=True)
        assert BD.delegate_amount - abs(red_acc_amt - acc_amt_before) < BD.von_limit
        logger.info(f"-锁定期锁仓金额解锁领取后 验证锁仓计划")
        expect_data = {'Pledge': {"old_value": BD.delegate_amount,
                                  "new_value": BD.delegate_amount - (lock_residue_amt + BD.delegate_limit * 10)}}
        Assertion.assert_restr_amt(restr_info_before, restr_info_later, expect_data)

        acc_amt_before, red_acc_amt, restr_info_before, restr_info_later = \
            redeem_del_wait_unlock_diff_balance_restr(normal_aide0, normal_aide0_nt, wait_num=1, diff_restr=True)
        logger.info(f"-等待解锁期领取,无自由金额,账户余额未增加")
        assert BD.von_limit - abs(red_acc_amt - acc_amt_before) < BD.von_limit
        logger.info(f"-锁定期锁仓金额解锁领取后 验证锁仓计划")
        old_value = BD.delegate_amount - (lock_residue_amt + BD.delegate_limit * 10)
        expect_data = {'Pledge': {"old_value": old_value,
                                  "new_value": old_value - BD.delegate_limit * 70}}
        Assertion.assert_restr_amt(restr_info_before, restr_info_later, expect_data)
        logger.info(f"-lock_info 锁定期无锁定数据、无已释放金额")
        Assertion.del_lock_info_zero_money(normal_aide0, normal_aide0_nt)

        assert PF.p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt) is None


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
        assert BD.delegate_amount - (red_acc_amt - acc_amt_before) < BD.von_min

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
        assert release - abs(red_acc_amt - acc_amt_before) < BD.von_min

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
        assert release - abs(red_acc_amt - acc_amt_before) < BD.von_min

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
        assert release - abs(red_acc_amt - acc_amt_before) < BD.von_min

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
        assert release - abs(red_acc_amt - acc_amt_before) < BD.von_min
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
        assert release - abs(red_acc_amt - acc_amt_before) < BD.von_min
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
        assert release - abs(red_acc_amt - acc_amt_before) < BD.von_min
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
            - 自由金额 犹豫期 / 锁仓金额 生效期
            - 自由金额 生效期 / 锁仓金额 犹豫期
            - 同时生效期
    - 自由金额 生效期  /  锁仓金额 犹豫期
        * 锁定期Mix金额
            - 同时犹豫期
            - 自由金额 犹豫期 / 锁仓金额 生效期
            - 自由金额 生效期 / 锁仓金额 犹豫期
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
        @param mix_diff_cycle_delegate: 自由金额 犹豫期  /  锁仓金额 生效期
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


class TestLockMixDiffCycle:
    """
    锁定期Mix金额(不同周期)
    - 自由金额 犹豫期  /  锁仓金额 生效期
        * 账户Mix金额
            - 同时犹豫期
            - 自由金额 犹豫期 / 锁仓金额 生效期
            - 自由金额 生效期 / 锁仓金额 犹豫期
            - 同时生效期
    - 自由金额 生效期  /  锁仓金额 犹豫期
        * 账户Mix金额
            - 同时犹豫期
            - 自由金额 犹豫期 / 锁仓金额 生效期
            - 自由金额 生效期 / 锁仓金额 犹豫期
            - 同时生效期
    """
    pass


def test_ghost_bug_001(normal_aide):
    """赎回质押后再次进行质押"""
    sta_addr, sta_pk = generate_account(normal_aide, BD.staking_limit * 5)
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
