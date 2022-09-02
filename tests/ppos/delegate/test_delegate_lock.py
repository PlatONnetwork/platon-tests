"""
@Author  :  Jw
@Contact :  libai7236@gmail.com
@Time    :  2022/8/23 11:38
@Version :  platon-1.3.0
@Desc    :  委托锁定
"""
import inspect
from decimal import Decimal

import platon_typing
import pytest
from loguru import logger
from platon._utils.error_code import ERROR_CODE

from lib.assertion import Assertion
from lib.basic_data import BaseData as BD
from lib.funcs import wait_settlement, wait_consensus
from lib.utils import p_get_delegate_lock_info, p_get_restricting_info, p_get_delegate_info, get_pledge_list

logger.add("logs/case_{time}.log", rotation="500MB")


def wait_unlock_diff_balance(aide, aide_nt, wait_num=2):
    """
    等待解锁期并领取 / 等待2个结算周期
    @param aide: 发起查询的aide对象
    @param aide_nt: aide_nt.del_addr委托账户地址 aide_nt.del_pk委托账户私钥
    @param wait_num: 等待周期
    @return: 解锁期账户余额前后数据
    """
    acc_amt_before = aide.platon.get_balance(aide_nt.del_addr)
    logger.info(f"redeem_delegate_before_balance: {acc_amt_before}")
    if wait_num == 1:
        wait_settlement(aide)
    else:
        wait_settlement(aide, wait_num - 1)
    assert aide.delegate.redeem_delegate(private_key=aide_nt.del_pk)['code'] == 0
    red_acc_amt = aide.platon.get_balance(aide_nt.del_addr)
    logger.info(f"redeem_delegate_balance: {red_acc_amt}")
    return acc_amt_before, red_acc_amt


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
        p_get_delegate_lock_info(normal_aide0, normal_aide0_nt)

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
        lock_info = p_get_delegate_lock_info(normal_aide0, normal_aide0_nt)
        assert lock_info['Locks'][0]['Released'] == del_amt3

        logger.info("-各节点委托信息")
        del_info_0 = normal_aide0.delegate.get_delegate_info(normal_aide0_nt.del_addr,
                                                             staking_block_identifier=normal_aide0_nt.StakingBlockNum)
        assert del_info_0.LockReleasedHes == del_amt3 + del_amt1 + BD.delegate_limit
        del_info_1 = normal_aide0.delegate.get_delegate_info(normal_aide0_nt.del_addr, normal_aide1.node.node_id,
                                                             staking_block_identifier=normal_aide1_nt.StakingBlockNum)
        assert del_info_1.LockReleasedHes == del_amt1 + BD.delegate_limit

        logger.info("-委托账户领取解锁期金额")
        acc_amt_bef, red_acc_amt = wait_unlock_diff_balance(normal_aide0, normal_aide0_nt)
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
        p_get_delegate_lock_info(normal_aide0, normal_aide0_nt)

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
        lock_info = p_get_delegate_lock_info(normal_aide0, normal_aide0_nt)
        assert lock_info['Locks'][0]['RestrictingPlan'] == del_amt3

        logger.info("-各节点委托信息 犹豫期 LockRestrictingPlanHes")
        del_info_0 = normal_aide0.delegate.get_delegate_info(normal_aide0_nt.del_addr,
                                                             staking_block_identifier=normal_aide0_nt.StakingBlockNum)
        assert del_info_0.LockRestrictingPlanHes == del_amt3 + del_amt1 + BD.delegate_limit
        del_info_1 = normal_aide0.delegate.get_delegate_info(normal_aide0_nt.del_addr, normal_aide1.node.node_id,
                                                             staking_block_identifier=normal_aide1_nt.StakingBlockNum)
        assert del_info_1.LockRestrictingPlanHes == del_amt1 + BD.delegate_limit

        logger.info("-委托账户领取解锁期金额 - 锁仓计划周期为10 暂未释放/余额不变")
        acc_amt_bef, red_acc_amt = wait_unlock_diff_balance(normal_aide0, normal_aide0_nt)
        assert abs(acc_amt_bef - red_acc_amt) < BD.von_limit

        logger.info("-查锁仓计划信息 验证质押金额等字段")
        restr_info = p_get_restricting_info(normal_aide0, normal_aide0_nt)
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
        p_get_delegate_lock_info(normal_aide0, normal_aide0_nt)

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
        del_info_0 = p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        # 锁定期自由金额 = lock_released 全部自由金额 + delegate_limit
        assert del_info_0.LockReleasedHes == lock_released + BD.delegate_limit
        assert del_info_0.LockRestrictingPlanHes == abs(lock_released - BD.delegate_amount)

        del_info_1 = p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide1_nt)
        assert del_info_1.LockReleasedHes == BD.delegate_limit
        assert del_info_1.LockRestrictingPlanHes == del_amt3

        wait_settlement(normal_aide0)
        logger.info(f'{"-锁定期中锁仓解锁/锁仓计划未释放":*^50s}')
        RestrictingPlan = BD.delegate_amount * 2 - (del_amt3 + del_amt2 + del_amt1 + BD.delegate_limit * 2)
        expect_data = {"Released": 0, "RestrictingPlan": RestrictingPlan}
        Assertion.del_release_money(normal_aide0, normal_aide0_nt, expect_data)

        logger.info(f'{"-领取解锁的锁仓金额":*^50s}')
        assert normal_aide0.delegate.redeem_delegate(private_key=normal_aide0_nt.del_pk)['code'] == 0
        restr_info = p_get_restricting_info(normal_aide0, normal_aide0_nt)
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
        p_get_delegate_lock_info(normal_aide0, normal_aide0_nt)

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
        del_info_0 = p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        assert del_info_0.LockReleasedHes == abs(lock_restricting_plan - BD.delegate_amount)
        assert del_info_0.LockRestrictingPlanHes == lock_restricting_plan + BD.delegate_limit

        del_info_1 = p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide1_nt)
        assert del_info_1.LockReleasedHes == del_amt3
        assert del_info_1.LockRestrictingPlanHes == BD.delegate_limit

        logger.info(f'{"-等待锁定期中自由金额解锁并领取":*^50s}')
        Released = BD.delegate_amount * 2 - (del_amt3 + del_amt2 + del_amt1 + BD.delegate_limit * 2)
        acc_amt_bef, red_acc_amt = wait_unlock_diff_balance(normal_aide0, normal_aide0_nt, wait_num=1)
        assert Released - (red_acc_amt - acc_amt_bef) < BD.von_limit

        logger.info(f'{"-锁仓计划信息不变,锁定期锁仓金额已全部再次委托":*^50s}')
        restr_info = p_get_restricting_info(normal_aide0, normal_aide0_nt)
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
        p_get_delegate_lock_info(normal_aide0, normal_aide0_nt)

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
        del_info_0 = p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        assert del_info_0.LockReleasedHes == abs(lock_restricting_plan - BD.delegate_amount)
        assert del_info_0.LockRestrictingPlanHes == lock_restricting_plan + BD.delegate_limit

        del_info_1 = p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide1_nt)
        assert del_info_1.LockReleasedHes == del_amt3
        assert del_info_1.LockRestrictingPlanHes == BD.delegate_limit

        logger.info(f'{"-等待锁定期中自由金额解锁并领取":*^50s}')
        Released = BD.delegate_amount * 2 - (del_amt3 + del_amt2 + del_amt1 + BD.delegate_limit * 2)
        acc_amt_bef, red_acc_amt = wait_unlock_diff_balance(normal_aide0, normal_aide0_nt)
        assert Released - (red_acc_amt - acc_amt_bef) < BD.von_limit

        logger.info(f'{"-锁仓计划信息不变,锁定期锁仓金额已全部再次委托":*^50s}')
        restr_info = p_get_restricting_info(normal_aide0, normal_aide0_nt)
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
        p_get_delegate_lock_info(normal_aide0, normal_aide0_nt)
        p_get_delegate_lock_info(normal_aide1, normal_aide1_nt)

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
        A_A1_del = p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        assert A_A1_del.LockReleasedHes == BD.delegate_limit + del_amt2 + del_amt3
        A_B1_del = p_get_delegate_info(normal_aide0, normal_aide1_nt.del_addr, normal_aide0_nt)
        assert A_B1_del.LockReleasedHes == BD.delegate_limit + del_amt2 + del_amt3

        logger.info("-B节点(A1,B1账户) 委托信息 A1(limit + del_amt2 + del_amt3) / B1(limit + del_amt2)")
        B_A1_del = p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide1_nt)
        assert B_A1_del.LockReleasedHes == BD.delegate_limit + del_amt2 + del_amt3
        B_B1_del = p_get_delegate_info(normal_aide0, normal_aide1_nt.del_addr, normal_aide1_nt)
        assert B_B1_del.LockReleasedHes == BD.delegate_limit + del_amt2

        logger.info("-B1账户领取解锁期金额")
        acc_amt_bef, red_acc_amt = wait_unlock_diff_balance(normal_aide1, normal_aide1_nt)
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
        p_get_delegate_lock_info(normal_aide0, normal_aide0_nt)
        p_get_delegate_lock_info(normal_aide1, normal_aide1_nt)

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
        A_A1_del = p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        assert A_A1_del.LockRestrictingPlanHes == BD.delegate_limit + del_amt2 + del_amt3
        A_B1_del = p_get_delegate_info(normal_aide0, normal_aide1_nt.del_addr, normal_aide0_nt)
        assert A_B1_del.LockRestrictingPlanHes == BD.delegate_limit + del_amt2 + del_amt3

        logger.info("-B节点(A1,B1账户) 委托信息 A1(limit + del_amt2 + del_amt3) / B1(limit + del_amt2)")
        B_A1_del = p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide1_nt)
        assert B_A1_del.LockRestrictingPlanHes == BD.delegate_limit + del_amt2 + del_amt3
        B_B1_del = p_get_delegate_info(normal_aide0, normal_aide1_nt.del_addr, normal_aide1_nt)
        assert B_B1_del.LockRestrictingPlanHes == BD.delegate_limit + del_amt2

        logger.info("-B1账户领取解锁期金额 / 锁仓计划未释放 账户余额不变只扣手续费")
        acc_amt_bef, red_acc_amt = wait_unlock_diff_balance(normal_aide1, normal_aide1_nt)
        assert abs(red_acc_amt - acc_amt_bef) < BD.von_limit
        logger.info("-领取之后 验证B1账户锁定期无数据")
        Assertion.del_lock_info_zero_money(normal_aide1, normal_aide1_nt)

        logger.info("-验证A1账户的锁仓计划")
        restr_info = p_get_restricting_info(normal_aide0, normal_aide0_nt)
        assert restr_info["Pledge"] == restr_info['balance'] == BD.delegate_amount
        assert restr_info["debt"] == 0

        logger.info("-验证B1账户的锁仓计划")
        restr_info = p_get_restricting_info(normal_aide1, normal_aide1_nt)
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
        assert len(p_get_delegate_lock_info(normal_aide0, normal_aide0_nt)['Locks']) == 2
        assert len(p_get_delegate_lock_info(normal_aide0, normal_aide1_nt)['Locks']) == 2

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
        A_A1_del = p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        assert A_A1_del.LockReleasedHes == del_amt2 + BD.delegate_limit
        assert A_A1_del.LockRestrictingPlanHes == del_amt2

        A_B1_del = p_get_delegate_info(normal_aide0, normal_aide1_nt.del_addr, normal_aide0_nt)
        assert A_B1_del.LockReleasedHes == del_amt2 + BD.delegate_limit
        assert A_B1_del.LockRestrictingPlanHes == del_amt2

        logger.info("-验证B节点 A1、B1账户委托信息")
        B_A1_del = p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide1_nt)
        assert B_A1_del.LockReleasedHes == (BD.delegate_amount - del_amt2 - BD.delegate_limit * 2) + BD.delegate_limit
        assert B_A1_del.LockRestrictingPlanHes == del_amt2

        B_B1_del = p_get_delegate_info(normal_aide0, normal_aide1_nt.del_addr, normal_aide1_nt)
        assert B_B1_del.LockReleasedHes == (BD.delegate_amount - del_amt2 - BD.delegate_limit * 2) + BD.delegate_limit
        assert B_B1_del.LockRestrictingPlanHes == BD.delegate_limit * 2

        wait_settlement(normal_aide0)
        logger.info(f'{"-B1账户 锁定期中锁仓金额解锁/锁仓计划未释放":*^50s}')
        RestrictingPlan = BD.delegate_amount * 2 - (del_amt2 * 3 + BD.delegate_limit * 2)
        expect_data = {"Released": 0, "RestrictingPlan": RestrictingPlan}
        Assertion.del_release_money(normal_aide0, normal_aide1_nt, expect_data)

        logger.info(f'{"-B1账户 领取解锁的锁仓金额":*^50s}')
        assert normal_aide0.delegate.redeem_delegate(private_key=normal_aide1_nt.del_pk)['code'] == 0
        restr_info = p_get_restricting_info(normal_aide0, normal_aide1_nt)
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
        assert len(p_get_delegate_lock_info(normal_aide0, normal_aide0_nt)['Locks']) == 2
        assert len(p_get_delegate_lock_info(normal_aide0, normal_aide1_nt)['Locks']) == 2

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
        A_A1_del = p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide0_nt)
        assert A_A1_del.LockReleasedHes == del_amt2
        assert A_A1_del.LockRestrictingPlanHes == del_amt2 + BD.delegate_limit

        A_B1_del = p_get_delegate_info(normal_aide0, normal_aide1_nt.del_addr, normal_aide0_nt)
        assert A_B1_del.LockReleasedHes == del_amt2
        assert A_B1_del.LockRestrictingPlanHes == del_amt2 + BD.delegate_limit

        logger.info("-验证B节点 A1、B1账户委托信息")
        B_A1_del = p_get_delegate_info(normal_aide0, normal_aide0_nt.del_addr, normal_aide1_nt)
        assert B_A1_del.LockReleasedHes == del_amt2
        assert B_A1_del.LockRestrictingPlanHes == lock_restricting_plan - del_amt2 + BD.delegate_limit

        B_B1_del = p_get_delegate_info(normal_aide0, normal_aide1_nt.del_addr, normal_aide1_nt)
        assert B_B1_del.LockReleasedHes == BD.delegate_limit * 2
        assert B_B1_del.LockRestrictingPlanHes == lock_restricting_plan - del_amt2 + BD.delegate_limit

        logger.info(f'{"-B1账户 锁定期中自由金额解锁并领取":*^50s}')
        Released = BD.delegate_amount * 2 - (del_amt2 * 3 + BD.delegate_limit * 2)
        acc_amt_bef, red_acc_amt = wait_unlock_diff_balance(normal_aide0, normal_aide1_nt, wait_num=1)
        assert Released - abs(red_acc_amt - acc_amt_bef) < BD.von_limit

        logger.info(f'{"-B1账户 原锁仓计划信息不变,锁定期锁仓金额已全部再次委托":*^50s}')
        restr_info = p_get_restricting_info(normal_aide0, normal_aide1_nt)
        assert restr_info['Pledge'] == BD.delegate_amount
        assert restr_info['balance'] == BD.delegate_amount and restr_info['debt'] == 0


class TestDelegateLockNodeException:
    """测试节点异常 使用锁定期金额进行委托和赎回委托"""

    @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 10, }], indirect=True)
    @pytest.mark.parametrize('create_lock_restr_amt', [{"ManyAcc": True, "MixAcc": True}], indirect=True)
    def test_lock_mix_amt_free_unlock_long(self, create_lock_mix_amt_free_unlock_long):
        logger.info(f"test_case_name: {self.__class__.__name__}/{inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt = create_lock_mix_amt_free_unlock_long
        assert len(p_get_delegate_lock_info(normal_aide0, normal_aide0_nt)['Locks']) == 2
        assert len(p_get_delegate_lock_info(normal_aide0, normal_aide1_nt)['Locks']) == 2

        validator_list = get_pledge_list(normal_aide1.staking.get_validator_list)
        assert normal_aide1.node.node_id in validator_list

        candidate_info = normal_aide1.staking.get_candidate_info(node_id=normal_aide1.node.node_id)
        logger.info(f"{normal_aide1.node}: {candidate_info}")

        logger.info(f"stop_node_id: {normal_aide1.node.node_id}:")
        normal_aide1.node.stop()

        total_staking_reward, per_block_reward = normal_aide0.calculator.get_reward_info()
        logger.info(f"total_staking_reward: {total_staking_reward}")
        logger.info(f"per_block_reward: {per_block_reward}, total:{per_block_reward * 5}")

        for i in range(4):
            wait_consensus(normal_aide0)
            candidate_info = normal_aide0.staking.get_candidate_info(node_id=normal_aide1.node.node_id)
            logger.info(f"{normal_aide1.node}: {candidate_info}")
            if candidate_info.Status == 0:
                logger.info(f"已等待共识轮{i + 1}: -> 节点状态未变更前进行委托")
                assert normal_aide0.delegate.delegate(BD.delegate_limit, 3, normal_aide1.node.node_id,
                                                      private_key=normal_aide1_nt.del_pk)['code'] == 0
            else:
                logger.info(f"已等待共识轮{i + 1}: -> 节点状态异常进行委托")
                res = normal_aide0.delegate.delegate(BD.delegate_limit, 3, normal_aide1.node.node_id,
                                                     private_key=normal_aide1_nt.del_pk)
                assert res['message'] == ERROR_CODE[301103]
                break

        wait_settlement(normal_aide0)

        candidate_info = normal_aide0.staking.get_candidate_info(node_id=normal_aide1.node.node_id)
        logger.info(f"{normal_aide1.node}: {candidate_info}")

        assert normal_aide0.delegate.delegate(BD.delegate_limit, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide1_nt.del_pk)['code'] == 0
        logger.info(f"start_node_id: {normal_aide1.node.node_id}:")
        normal_aide1.node.start()
        logger.info(f"{normal_aide1.node}: 委托BD.delegate_amount, 会使用锁定期自由金额+锁仓金额")
        assert normal_aide0.delegate.delegate(BD.delegate_amount, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide1_nt.del_pk)['code'] == 0
        lock_info = p_get_delegate_lock_info(normal_aide0, normal_aide1_nt)
        logger.info(f"{normal_aide1.node}: 锁定期只剩下锁仓金额")
        assert len(lock_info["Locks"]) == 1

        assert normal_aide0.delegate.delegate(BD.delegate_amount, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide0_nt.del_pk)['code'] == 0

    pass
