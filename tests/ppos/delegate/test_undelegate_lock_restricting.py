import inspect
import time

from decimal import Decimal

import platon_utils
import pytest
from loguru import logger
from platon._utils.error_code import ERROR_CODE

from lib.assertion import Assertion
from lib.basic_data import BaseData
from lib.funcs import wait_settlement
from lib.utils import p_get_delegate_lock_info, p_get_restricting_info, p_get_delegate_info
from tests.conftest import create_sta_del


class TestRestrictingAndLockUp:
    """"锁仓与锁定期相关用例"""

    def test_undelegate_lock_restricting_release_long(self, update_undelegate_freeze_duration, normal_aide):
        """
       测试 锁定期 锁仓金额 委托多节点
        @Desc:
            -创建锁仓计划 锁仓委托 A 节点 / limit * 100 等待委托生效
            -锁仓赎回委托锁定期 委托 A节点 / limit * 50 锁仓释放周期比委托锁定期长
            -等待委托解锁期领取委托锁仓金 查看锁仓计划
        """
        chain, new_gen_file = update_undelegate_freeze_duration
        chain.install(genesis_file=new_gen_file)
        time.sleep(5)
        lockup_amount = BaseData.delegate_limit * 50
        plan = [{'Epoch': 4, 'Amount': lockup_amount}, {'Epoch': 5, 'Amount': lockup_amount}]

        normal_aide0_namedtuple = create_sta_del(normal_aide, plan)
        wait_settlement(normal_aide)

        assert normal_aide.delegate.withdrew_delegate(BaseData.delegate_amount, normal_aide0_namedtuple.StakingBlockNum,
                                                      private_key=normal_aide0_namedtuple.del_pk)['code'] == 0

        restr_info = normal_aide.restricting.get_restricting_info(normal_aide0_namedtuple.del_addr)
        assert restr_info['balance'] == BaseData.delegate_amount and restr_info['debt'] == 0
        assert restr_info['Pledge'] == BaseData.delegate_amount

        lock_info = normal_aide.delegate.get_delegate_lock_info(normal_aide0_namedtuple.del_addr)
        assert lock_info['Locks'][0]['RestrictingPlan'] == BaseData.delegate_amount

        staking_balance = normal_aide.platon.get_balance(normal_aide.web3.ppos.staking.address)
        print(staking_balance)

        assert normal_aide.delegate.delegate(amount=lockup_amount, balance_type=3,
                                             private_key=normal_aide0_namedtuple.del_pk)['code'] == 0
        staking_balance1 = normal_aide.platon.get_balance(normal_aide.web3.ppos.staking.address)
        print(staking_balance1)
        assert staking_balance == staking_balance1

        restr_info2 = normal_aide.restricting.get_restricting_info(normal_aide0_namedtuple.del_addr)
        assert restr_info2['balance'] == BaseData.delegate_amount and restr_info2['debt'] == 0
        assert restr_info2['Pledge'] == BaseData.delegate_amount

        lock_info = normal_aide.delegate.get_delegate_lock_info(normal_aide0_namedtuple.del_addr)
        assert lock_info['Locks'][0]['RestrictingPlan'] == lockup_amount

        wait_settlement(normal_aide, 1)
        time.sleep(2)
        restr_info3 = normal_aide.restricting.get_restricting_info(normal_aide0_namedtuple.del_addr)
        assert restr_info3['balance'] == BaseData.delegate_amount and restr_info3['debt'] == 0
        assert restr_info3['Pledge'] == BaseData.delegate_amount

        lock_info = normal_aide.delegate.get_delegate_lock_info(normal_aide0_namedtuple.del_addr)
        assert lock_info['Locks'] == []
        assert lock_info['RestrictingPlan'] == lockup_amount

        assert normal_aide.delegate.redeem_delegate(private_key=normal_aide0_namedtuple.del_pk)['code'] == 0

        restr_info4 = normal_aide.restricting.get_restricting_info(normal_aide0_namedtuple.del_addr)
        assert restr_info4['balance'] == BaseData.delegate_amount and restr_info4['debt'] == 0
        assert restr_info4['Pledge'] == lockup_amount
        assert restr_info4['plans'][0]['amount'] == restr_info4['plans'][1]['amount'] == lockup_amount
        lock_info = normal_aide.delegate.get_delegate_lock_info(normal_aide0_namedtuple.del_addr)
        assert lock_info['Locks'] == []
        assert lock_info['RestrictingPlan'] == 0
        assert lock_info['Released'] == 0

    def test_undelegate_lock_restricting_release_same(self, update_undelegate_freeze_duration, normal_aide):
        """
       测试 锁定期 锁仓金额 委托多节点
        @Desc:
            -创建锁仓计划 锁仓委托 A 节点 / limit * 100 等待委托生效
            -锁仓赎回委托锁定期 委托 A节点 / limit * 50 锁仓释放周期比委托锁定期相同
            -等待委托解锁期领取委托锁仓金 查看锁仓计划
        """
        chain, new_gen_file = update_undelegate_freeze_duration
        chain.install(genesis_file=new_gen_file)
        time.sleep(5)
        lockup_amount = BaseData.delegate_limit * 50
        plan = [{'Epoch': 3, 'Amount': lockup_amount}, {'Epoch': 4, 'Amount': lockup_amount}]

        normal_aide0_namedtuple = create_sta_del(normal_aide, plan)
        wait_settlement(normal_aide)

        del_info = normal_aide.delegate.get_delegate_info(address=normal_aide0_namedtuple.del_addr,
                                                          staking_block_identifier=normal_aide0_namedtuple.StakingBlockNum)
        assert del_info is not None

        assert normal_aide.delegate.withdrew_delegate(BaseData.delegate_amount, normal_aide0_namedtuple.StakingBlockNum,
                                                      private_key=normal_aide0_namedtuple.del_pk)['code'] == 0

        restr_info = normal_aide.restricting.get_restricting_info(normal_aide0_namedtuple.del_addr)
        assert restr_info['balance'] == BaseData.delegate_amount and restr_info['debt'] == 0
        assert restr_info['Pledge'] == BaseData.delegate_amount

        del_info1 = normal_aide.delegate.get_delegate_info(address=normal_aide0_namedtuple.del_addr,
                                                           staking_block_identifier=normal_aide0_namedtuple.StakingBlockNum)
        assert del_info1 is None

        lock_info = normal_aide.delegate.get_delegate_lock_info(normal_aide0_namedtuple.del_addr)
        assert lock_info['Locks'][0]['RestrictingPlan'] == BaseData.delegate_amount

        assert normal_aide.delegate.delegate(amount=lockup_amount, balance_type=3,
                                             private_key=normal_aide0_namedtuple.del_pk)['code'] == 0

        restr_info2 = normal_aide.restricting.get_restricting_info(normal_aide0_namedtuple.del_addr)
        assert restr_info2['balance'] == BaseData.delegate_amount and restr_info2['debt'] == 0
        assert restr_info2['Pledge'] == BaseData.delegate_amount

        lock_info = normal_aide.delegate.get_delegate_lock_info(normal_aide0_namedtuple.del_addr)
        assert lock_info['Locks'][0]['RestrictingPlan'] == lockup_amount

        wait_settlement(normal_aide, 1)
        restr_info3 = normal_aide.restricting.get_restricting_info(normal_aide0_namedtuple.del_addr)
        assert restr_info3['balance'] == BaseData.delegate_amount and restr_info3['debt'] == lockup_amount
        assert restr_info3['plans'][0]['amount'] == lockup_amount
        assert restr_info3['Pledge'] == BaseData.delegate_amount

        lock_info = normal_aide.delegate.get_delegate_lock_info(normal_aide0_namedtuple.del_addr)
        assert lock_info['Locks'] == []
        assert lock_info['RestrictingPlan'] == lockup_amount

        del_balance = normal_aide.platon.get_balance(normal_aide0_namedtuple.del_addr)
        assert normal_aide.delegate.redeem_delegate(private_key=normal_aide0_namedtuple.del_pk)['code'] == 0
        del_balance1 = normal_aide.platon.get_balance(normal_aide0_namedtuple.del_addr)
        assert del_balance + lockup_amount - del_balance1 < platon_utils.to_von(0.01, 'lat')

        restr_info4 = normal_aide.restricting.get_restricting_info(normal_aide0_namedtuple.del_addr)
        assert restr_info4['balance'] == lockup_amount and restr_info4['debt'] == 0
        assert restr_info4['Pledge'] == lockup_amount
        assert restr_info4['plans'][0]['amount'] == lockup_amount

        lock_info = normal_aide.delegate.get_delegate_lock_info(normal_aide0_namedtuple.del_addr)
        assert lock_info['Locks'] == []
        assert lock_info['RestrictingPlan'] == 0
        assert lock_info['Released'] == 0

    def test_undelegate_restricting_lock_release_long(self, update_undelegate_freeze_duration_three, normal_aide):
        """
       测试 锁定期 锁仓金额 委托多节点
        @Desc:
            -创建锁仓计划 锁仓委托 A 节点 / limit * 100 等待委托生效
            -锁仓赎回委托锁定期 委托 A节点 / limit * 50 委托锁定期比锁仓释放周期长
            -等待委托解锁期领取委托锁仓金 查看锁仓计划
        """
        chain, new_gen_file = update_undelegate_freeze_duration_three
        chain.install(genesis_file=new_gen_file)
        time.sleep(5)

        lockup_amount = BaseData.delegate_limit * 50
        plan = [{'Epoch': 3, 'Amount': lockup_amount}, {'Epoch': 4, 'Amount': lockup_amount}]

        normal_aide0_namedtuple = create_sta_del(normal_aide, plan)
        wait_settlement(normal_aide)

        assert normal_aide.delegate.withdrew_delegate(BaseData.delegate_amount, normal_aide0_namedtuple.StakingBlockNum,
                                                      private_key=normal_aide0_namedtuple.del_pk)['code'] == 0

        restr_info = normal_aide.restricting.get_restricting_info(normal_aide0_namedtuple.del_addr)
        assert restr_info['balance'] == BaseData.delegate_amount and restr_info['debt'] == 0
        assert restr_info['Pledge'] == BaseData.delegate_amount

        lock_info = normal_aide.delegate.get_delegate_lock_info(normal_aide0_namedtuple.del_addr)
        assert lock_info['Locks'][0]['RestrictingPlan'] == BaseData.delegate_amount

        assert normal_aide.delegate.delegate(amount=lockup_amount, balance_type=3,
                                             private_key=normal_aide0_namedtuple.del_pk)['code'] == 0

        restr_info2 = normal_aide.restricting.get_restricting_info(normal_aide0_namedtuple.del_addr)
        assert restr_info2['balance'] == BaseData.delegate_amount and restr_info2['debt'] == 0
        assert restr_info2['Pledge'] == BaseData.delegate_amount

        lock_info = normal_aide.delegate.get_delegate_lock_info(normal_aide0_namedtuple.del_addr)
        assert lock_info['Locks'][0]['RestrictingPlan'] == lockup_amount

        wait_settlement(normal_aide, 1)
        restr_info3 = normal_aide.restricting.get_restricting_info(normal_aide0_namedtuple.del_addr)
        print('restr_info3', restr_info3)
        assert restr_info3['balance'] == BaseData.delegate_amount and restr_info3['debt'] == lockup_amount
        assert restr_info3['plans'][0]['amount'] == lockup_amount
        assert restr_info3['plans'][0]['blockNumber'] == 640
        assert restr_info3['Pledge'] == BaseData.delegate_amount

        lock_info = normal_aide.delegate.get_delegate_lock_info(normal_aide0_namedtuple.del_addr)
        print(lock_info)
        assert lock_info['Locks'][0]['RestrictingPlan'] == lockup_amount
        assert lock_info['RestrictingPlan'] == 0

        del_balance = normal_aide.platon.get_balance(normal_aide0_namedtuple.del_addr)
        print(del_balance)
        assert normal_aide.delegate.redeem_delegate(private_key=normal_aide0_namedtuple.del_pk)['code'] == 0
        del_balance1 = normal_aide.platon.get_balance(normal_aide0_namedtuple.del_addr)
        print(del_balance1)
        assert del_balance1 - del_balance < platon_utils.to_von(0.01, 'lat')

        restr_info4 = normal_aide.restricting.get_restricting_info(normal_aide0_namedtuple.del_addr)
        print(restr_info4)
        assert restr_info4['balance'] == BaseData.delegate_amount and restr_info4['debt'] == lockup_amount
        assert restr_info4['Pledge'] == BaseData.delegate_amount
        assert restr_info4['plans'][0]['amount'] == lockup_amount

        lock_info = normal_aide.delegate.get_delegate_lock_info(normal_aide0_namedtuple.del_addr)
        assert lock_info['Locks'][0]['RestrictingPlan'] == lockup_amount
        assert lock_info['RestrictingPlan'] == 0

        wait_settlement(normal_aide)

        assert normal_aide.delegate.redeem_delegate(private_key=normal_aide0_namedtuple.del_pk)['code'] == 0
        del_balance2 = normal_aide.platon.get_balance(normal_aide0_namedtuple.del_addr)
        print(del_balance1)
        assert del_balance1 + lockup_amount - del_balance2 < platon_utils.to_von(0.01, 'lat')

        restr_info4 = normal_aide.restricting.get_restricting_info(normal_aide0_namedtuple.del_addr)
        print(restr_info4)
        assert restr_info4['balance'] == lockup_amount and restr_info4['debt'] == lockup_amount
        assert restr_info4['Pledge'] == lockup_amount
        assert restr_info4['plans'] is None

        lock_info = normal_aide.delegate.get_delegate_lock_info(normal_aide0_namedtuple.del_addr)
        assert lock_info['Locks'] == []

        del_info = normal_aide.delegate.get_delegate_info(normal_aide0_namedtuple.del_addr)
        print(del_info)
        assert del_info is not None


class UndelegateLockUpSpecialScenes:
    """
    异常场景用例集合
    """


def test_restrictingPlan_debt_redeem_delegate(update_undelegate_freeze_duration_three, normal_aide):
    """
           测试 锁定期 锁仓金额 委托多节点
            @Desc:
                -创建锁仓计划 锁仓委托 A 节点 / limit * 100 等待委托生效
                -锁仓赎回委托锁定期 委托 A节点 / limit * 50 委托锁定期比锁仓释放周期长
                -等待锁仓计划欠释放，在发起新的锁仓计划 / limit * 100
                -等待委托解锁期领取委托锁仓金 查看锁仓计划
    """
    chain, new_gen_file = update_undelegate_freeze_duration_three
    chain.install(genesis_file=new_gen_file)
    time.sleep(5)

    lockup_amount = BaseData.delegate_limit * 50
    plan = [{'Epoch': 3, 'Amount': lockup_amount}, {'Epoch': 4, 'Amount': lockup_amount}]

    normal_aide0_namedtuple = create_sta_del(normal_aide, plan)
    wait_settlement(normal_aide)

    assert normal_aide.delegate.withdrew_delegate(BaseData.delegate_amount, normal_aide0_namedtuple.StakingBlockNum,
                                                  private_key=normal_aide0_namedtuple.del_pk)['code'] == 0

    restr_info = normal_aide.restricting.get_restricting_info(normal_aide0_namedtuple.del_addr)
    assert restr_info['balance'] == BaseData.delegate_amount and restr_info['debt'] == 0
    assert restr_info['Pledge'] == BaseData.delegate_amount

    lock_info = normal_aide.delegate.get_delegate_lock_info(normal_aide0_namedtuple.del_addr)
    assert lock_info['Locks'][0]['RestrictingPlan'] == BaseData.delegate_amount

    assert normal_aide.delegate.delegate(amount=lockup_amount, balance_type=3,
                                         private_key=normal_aide0_namedtuple.del_pk)['code'] == 0

    restr_info2 = normal_aide.restricting.get_restricting_info(normal_aide0_namedtuple.del_addr)
    assert restr_info2['balance'] == BaseData.delegate_amount and restr_info2['debt'] == 0
    assert restr_info2['Pledge'] == BaseData.delegate_amount

    lock_info = normal_aide.delegate.get_delegate_lock_info(normal_aide0_namedtuple.del_addr)
    assert lock_info['Locks'][0]['RestrictingPlan'] == lockup_amount

    wait_settlement(normal_aide, 1)
    restr_info3 = normal_aide.restricting.get_restricting_info(normal_aide0_namedtuple.del_addr)
    print('restr_info3', restr_info3)
    assert restr_info3['balance'] == BaseData.delegate_amount and restr_info3['debt'] == lockup_amount
    assert restr_info3['plans'][0]['amount'] == lockup_amount
    assert restr_info3['plans'][0]['blockNumber'] == 640
    assert restr_info3['Pledge'] == BaseData.delegate_amount

    time.sleep(1)
    plan1 = [{'Epoch': 1, 'Amount': lockup_amount}]
    normal_aide.restricting.restricting(normal_aide0_namedtuple.del_addr, plan1)

    lock_info = normal_aide.delegate.get_delegate_lock_info(normal_aide0_namedtuple.del_addr)
    print(lock_info)
    assert lock_info['Locks'][0]['RestrictingPlan'] == lockup_amount
    assert lock_info['RestrictingPlan'] == 0

    restr_info4 = normal_aide.restricting.get_restricting_info(normal_aide0_namedtuple.del_addr)
    print('restr_info4', restr_info4)
    assert restr_info4['balance'] == BaseData.delegate_amount and restr_info4['debt'] == 0
    assert restr_info4['plans'][0]['amount'] == BaseData.delegate_amount
    assert restr_info4['plans'][0]['blockNumber'] == 640
    assert restr_info4['Pledge'] == BaseData.delegate_amount

    del_balance = normal_aide.platon.get_balance(normal_aide0_namedtuple.del_addr)
    print(del_balance)
    assert normal_aide.delegate.redeem_delegate(private_key=normal_aide0_namedtuple.del_pk)['code'] == 0
    del_balance1 = normal_aide.platon.get_balance(normal_aide0_namedtuple.del_addr)
    print(del_balance1)
    assert del_balance1 - del_balance < platon_utils.to_von(0.01, 'lat')

    restr_info5 = normal_aide.restricting.get_restricting_info(normal_aide0_namedtuple.del_addr)
    print(restr_info5)
    assert restr_info5['balance'] == BaseData.delegate_amount and restr_info5['debt'] == 0
    assert restr_info5['Pledge'] == BaseData.delegate_amount
    assert restr_info5['plans'][0]['amount'] == BaseData.delegate_amount
    assert restr_info5['plans'][0]['blockNumber'] == 640

    lock_info = normal_aide.delegate.get_delegate_lock_info(normal_aide0_namedtuple.del_addr)
    assert lock_info['Locks'][0]['RestrictingPlan'] == lockup_amount
    assert lock_info['RestrictingPlan'] == 0

    wait_settlement(normal_aide)
    lock_info = normal_aide.delegate.get_delegate_lock_info(normal_aide0_namedtuple.del_addr)
    assert lock_info['Locks'] == []

    del_info = normal_aide.delegate.get_delegate_info(normal_aide0_namedtuple.del_addr)
    print(del_info)
    assert del_info is not None

    restr_info6 = normal_aide.restricting.get_restricting_info(normal_aide0_namedtuple.del_addr)
    print(restr_info6)
    assert restr_info6['balance'] == BaseData.delegate_amount and restr_info6['debt'] == BaseData.delegate_amount
    assert restr_info6['Pledge'] == BaseData.delegate_amount
    assert restr_info6['plans'] is None
