"""
@Author  :  Jw
@Contact :  libai7236@gmail.com
@Time    :  2022/8/23 11:38
@Version :  platon-1.3.0
@Desc    :  委托锁定
"""
import inspect
from decimal import Decimal

from loguru import logger
from platon._utils.error_code import ERROR_CODE

from lib.assertion import Assertion
from lib.basic_data import BaseData
from lib.funcs import wait_settlement


def wait_unlock_diff_balance(aide, del_addr, del_pk):
    """
    等待解锁期并领取
    @param aide:
    @param del_addr: 委托账户地址
    @param del_pk: 委托账户私钥
    @return: 解锁期账户余额前后数据
    """
    acc_amt_before = aide.platon.get_balance(del_addr)
    logger.info(f"redeem_delegate_before_wallet_balance: {acc_amt_before}")
    wait_settlement(aide, 1)
    assert aide.delegate.redeem_delegate(private_key=del_pk)['code'] == 0
    red_acc_amt = aide.platon.get_balance(del_addr)
    logger.info(f"redeem_delegate_wallet_balance: {red_acc_amt}")
    return acc_amt_before, red_acc_amt


def _get_delegate_lock_info(aide, aide_nt):
    lock_info = aide.delegate.get_delegate_lock_info(address=aide_nt.del_addr)
    logger.info(f"lock_info: {lock_info}")
    return lock_info


def _get_restricting_info(aide, aide_nt):
    restr_info = aide.restricting.get_restricting_info(aide_nt.del_addr)
    logger.info(f'restr_info: {restr_info}')
    return restr_info


class TestDelegateLockOneAcc(object):
    """ 测试单账户-多节点场景 """

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
        logger.info(f"test_case_name: {inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt = create_lock_free_amt
        _get_delegate_lock_info(normal_aide0, normal_aide0_nt)

        logger.info("-委托 A、B 节点 / limit - 1 -> fail")
        del_amt0 = BaseData.delegate_limit - 1
        assert normal_aide0.delegate.delegate(del_amt0, 3,
                                              private_key=normal_aide0_nt.del_pk)['message'] == ERROR_CODE[301105]
        assert normal_aide0.delegate.delegate(del_amt0, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide0_nt.del_pk)['message'] == ERROR_CODE[301105]

        logger.info("case-委托 A、B 节点 / limit")
        assert normal_aide0.delegate.delegate(private_key=normal_aide0_nt.del_pk, balance_type=3)['code'] == 0
        assert normal_aide0.delegate.delegate(private_key=normal_aide0_nt.del_pk, balance_type=3,
                                              node_id=normal_aide1.node.node_id)['code'] == 0

        logger.info("-委托 A、B 节点 / limit * 5")
        del_amt1 = BaseData.delegate_limit * 5
        assert normal_aide0.delegate.delegate(del_amt1, 3, private_key=normal_aide0_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(del_amt1, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide0_nt.del_pk, )['code'] == 0

        logger.info("-委托 A、B 节点 / limit * 110 -> fail")
        del_amt2 = BaseData.delegate_limit * 110
        res = normal_aide0.delegate.delegate(del_amt2, 3, private_key=normal_aide0_nt.del_pk)
        assert ERROR_CODE[301207] == res['message']
        res = normal_aide0.delegate.delegate(del_amt2, 3, normal_aide1.node.node_id, private_key=normal_aide0_nt.del_pk)
        assert ERROR_CODE[301207] == res['message']

        logger.info("-委托 A(剩余金额/2) -> pass / B(剩余金额/2)+von_limit -> fail")
        residue_amt = BaseData.delegate_amount - (del_amt1 * 2) - (BaseData.delegate_limit * 2)
        del_amt3 = int(Decimal(residue_amt) / Decimal(2))
        assert normal_aide0.delegate.delegate(del_amt3, 3, private_key=normal_aide0_nt.del_pk)['code'] == 0
        res = normal_aide0.delegate.delegate(del_amt3 + BaseData.von_limit, 3, normal_aide1.node.node_id,
                                             private_key=normal_aide0_nt.del_pk)
        assert ERROR_CODE[301207] == res['message']

        logger.info("-查询锁定期 自由余额 == del_amt3(剩余金额/2)")
        lock_info = _get_delegate_lock_info(normal_aide0, normal_aide0_nt)
        assert lock_info['Locks'][0]['Released'] == del_amt3

        logger.info("-各节点委托信息")
        del_info_0 = normal_aide0.delegate.get_delegate_info(normal_aide0_nt.del_addr,
                                                             staking_block_identifier=normal_aide0_nt.StakingBlockNum)
        assert del_info_0.LockReleasedHes == del_amt3 + del_amt1 + BaseData.delegate_limit
        del_info_1 = normal_aide0.delegate.get_delegate_info(normal_aide0_nt.del_addr, normal_aide1.node.node_id,
                                                             staking_block_identifier=normal_aide1_nt.StakingBlockNum)
        assert del_info_1.LockReleasedHes == del_amt1 + BaseData.delegate_limit

        logger.info("-委托账户领取解锁期金额")
        acc_amt_bef, red_acc_amt = wait_unlock_diff_balance(normal_aide0, normal_aide0_nt.del_addr,
                                                            normal_aide0_nt.del_pk)
        assert del_amt3 - (red_acc_amt - acc_amt_bef) < BaseData.von_limit
        logger.info("-验证锁定期数据")
        Assertion.del_lock_info_zero_money(_get_delegate_lock_info(normal_aide0, normal_aide0_nt))

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
        logger.info(f"test_case_name: {inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt = create_lock_restr_amt
        _get_delegate_lock_info(normal_aide0, normal_aide0_nt)

        logger.info("-委托 A、B 节点 / limit")
        assert normal_aide0.delegate.delegate(private_key=normal_aide0_nt.del_pk, balance_type=3)['code'] == 0
        assert normal_aide0.delegate.delegate(private_key=normal_aide0_nt.del_pk, balance_type=3,
                                              node_id=normal_aide1.node.node_id)['code'] == 0

        logger.info("-委托 A、B 节点 / limit * 5")
        del_amt1 = BaseData.delegate_limit * 5
        assert normal_aide0.delegate.delegate(del_amt1, 3, private_key=normal_aide0_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(del_amt1, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide0_nt.del_pk, )['code'] == 0

        logger.info("-委托 A、B 节点 / limit * 110 -> fail")
        del_amt2 = BaseData.delegate_limit * 110
        res = normal_aide0.delegate.delegate(del_amt2, 3, private_key=normal_aide0_nt.del_pk)
        assert ERROR_CODE[301207] == res['message']
        res = normal_aide0.delegate.delegate(del_amt2, 3, normal_aide1.node.node_id, private_key=normal_aide0_nt.del_pk)
        assert ERROR_CODE[301207] == res['message']

        logger.info("-委托 A(剩余金额/2) -> pass / B(剩余金额/2)+von_limit -> fail")
        residue_amt = BaseData.delegate_amount - (del_amt1 * 2) - (BaseData.delegate_limit * 2)
        del_amt3 = int(Decimal(residue_amt) / Decimal(2))
        assert normal_aide0.delegate.delegate(del_amt3, 3, private_key=normal_aide0_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(del_amt3 + BaseData.von_limit, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide0_nt.del_pk)['message'] == ERROR_CODE[301207]

        logger.info("-查询锁定期 锁仓金额 RestrictingPlan == del_amt3(剩余金额/2)")
        lock_info = _get_delegate_lock_info(normal_aide0, normal_aide0_nt)
        assert lock_info['Locks'][0]['RestrictingPlan'] == del_amt3

        logger.info("-各节点委托信息 犹豫期 LockRestrictingPlanHes")
        del_info_0 = normal_aide0.delegate.get_delegate_info(normal_aide0_nt.del_addr,
                                                             staking_block_identifier=normal_aide0_nt.StakingBlockNum)
        assert del_info_0.LockRestrictingPlanHes == del_amt3 + del_amt1 + BaseData.delegate_limit
        del_info_1 = normal_aide0.delegate.get_delegate_info(normal_aide0_nt.del_addr, normal_aide1.node.node_id,
                                                             staking_block_identifier=normal_aide1_nt.StakingBlockNum)
        assert del_info_1.LockRestrictingPlanHes == del_amt1 + BaseData.delegate_limit

        logger.info("-委托账户领取解锁期金额 - 锁仓计划周期为10 暂未释放/余额不变")
        acc_amt_bef, red_acc_amt = wait_unlock_diff_balance(normal_aide0, normal_aide0_nt.del_addr,
                                                            normal_aide0_nt.del_pk)
        assert acc_amt_bef - red_acc_amt < BaseData.von_limit

        logger.info("-查锁仓计划信息 验证质押金额等字段")
        restr_info = _get_restricting_info(normal_aide0, normal_aide0_nt)
        assert restr_info["Pledge"] == del_amt3 + (del_amt1 * 2) + (BaseData.delegate_limit * 2)
        assert restr_info["debt"] == 0

    def test_lock_mix_amt_free_unlock_long(self, create_lock_mix_amt_free_unlock_long):
        logger.info(f"test_case_name: {inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt = create_lock_mix_amt_free_unlock_long
        _get_delegate_lock_info(normal_aide0, normal_aide0_nt)

        logger.info("-委托 A、B 节点 / limit / 使用自由金额委托")
        assert normal_aide0.delegate.delegate(private_key=normal_aide0_nt.del_pk, balance_type=3)['code'] == 0
        assert normal_aide0.delegate.delegate(private_key=normal_aide0_nt.del_pk, balance_type=3,
                                              node_id=normal_aide1.node.node_id)['code'] == 0
        lock_info = _get_delegate_lock_info(normal_aide0, normal_aide0_nt)

        pass

