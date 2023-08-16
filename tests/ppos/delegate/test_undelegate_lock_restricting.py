import inspect
import time

from decimal import Decimal

import eth_utils
import pytest
import web3
from loguru import logger
from platon._utils.error_code import ERROR_CODE

from lib.assertion import Assertion
from lib.basic_data import BaseData
from lib.utils import wait_settlement
# from lib.utils import p_get_delegate_lock_info, p_get_restricting_info, p_get_delegate_info
from lib.utils import get_dynamic_gas_parameter
from tests.ppos.conftest import create_sta_del


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
        for host in chain.hosts:
            host.supervisor.clean()
        chain.install(genesis_file=new_gen_file)
        time.sleep(5)
        lockup_amount = BaseData.delegate_limit * 50
        plan = [{'Epoch': 4, 'Amount': lockup_amount}, {'Epoch': 5, 'Amount': lockup_amount}]

        normal_aide0_namedtuple = create_sta_del(normal_aide, plan)
        wait_settlement(normal_aide)
        staking_info = normal_aide.staking.staking_info
        staking_balance = normal_aide.platon.get_balance(normal_aide.staking.ADDRESS)

        assert normal_aide.delegate.withdrew_delegate(BaseData.delegate_amount, normal_aide0_namedtuple.StakingBlockNum,
                                                      private_key=normal_aide0_namedtuple.del_pk)['code'] == 0

        staking_info1 = normal_aide.staking.staking_info
        assert staking_info1.DelegateTotal == staking_info.DelegateTotal - BaseData.delegate_amount

        restr_info = normal_aide.restricting.get_restricting_info(normal_aide0_namedtuple.del_addr)
        assert restr_info['balance'] == BaseData.delegate_amount and restr_info['debt'] == 0
        assert restr_info['Pledge'] == BaseData.delegate_amount

        lock_info = normal_aide.delegate.get_delegate_lock_info(normal_aide0_namedtuple.del_addr)
        assert lock_info['Locks'][0]['RestrictingPlan'] == BaseData.delegate_amount

        staking_balance1 = normal_aide.platon.get_balance(normal_aide.staking.ADDRESS)
        print(staking_balance1)
        assert staking_balance == staking_balance1

        assert normal_aide.delegate.delegate(amount=lockup_amount, balance_type=3,
                                             private_key=normal_aide0_namedtuple.del_pk)['code'] == 0
        staking_balance2 = normal_aide.platon.get_balance(normal_aide.staking.ADDRESS)
        print(staking_balance2)
        assert staking_balance1 == staking_balance2

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

        staking_balance3 = normal_aide.platon.get_balance(normal_aide.staking.ADDRESS)
        print(staking_balance3)
        assert staking_balance2 == staking_balance3

        assert normal_aide.delegate.redeem_delegate(private_key=normal_aide0_namedtuple.del_pk)['code'] == 0

        restr_info4 = normal_aide.restricting.get_restricting_info(normal_aide0_namedtuple.del_addr)
        assert restr_info4['balance'] == BaseData.delegate_amount and restr_info4['debt'] == 0
        assert restr_info4['Pledge'] == lockup_amount
        assert restr_info4['plans'][0]['amount'] == restr_info4['plans'][1]['amount'] == lockup_amount
        lock_info = normal_aide.delegate.get_delegate_lock_info(normal_aide0_namedtuple.del_addr)
        assert lock_info['Locks'] == []
        assert lock_info['RestrictingPlan'] == 0
        assert lock_info['Released'] == 0
        staking_balance4 = normal_aide.platon.get_balance(normal_aide.staking.ADDRESS)
        print(staking_balance4)
        assert staking_balance3 - lockup_amount == staking_balance4

    def test_undelegate_lock_restricting_release_same(self, update_undelegate_freeze_duration, normal_aide):
        """
       测试 锁定期 锁仓金额 委托多节点
        @Desc:
            -创建锁仓计划 锁仓委托 A 节点 / limit * 100 等待委托生效
            -锁仓赎回委托锁定期 委托 A节点 / limit * 50 锁仓释放周期比委托锁定期相同
            -等待委托解锁期领取委托锁仓金 查看锁仓计划
        """
        chain, new_gen_file = update_undelegate_freeze_duration
        for host in chain.hosts:
            host.supervisor.clean()
        chain.install(genesis_file=new_gen_file)
        time.sleep(5)
        lockup_amount = BaseData.delegate_limit * 50
        plan = [{'Epoch': 3, 'Amount': lockup_amount}, {'Epoch': 4, 'Amount': lockup_amount}]

        normal_aide0_namedtuple = create_sta_del(normal_aide, plan)
        wait_settlement(normal_aide)

        del_info = normal_aide.delegate.get_delegate_info(address=normal_aide0_namedtuple.del_addr,
                                                          staking_block_identifier=normal_aide0_namedtuple.StakingBlockNum)
        assert del_info is not None

        staking_balance = normal_aide.platon.get_balance(normal_aide.staking.ADDRESS)
        print(staking_balance)

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

        staking_balance1 = normal_aide.platon.get_balance(normal_aide.staking.ADDRESS)
        print(staking_balance1)
        assert staking_balance == staking_balance1

        assert normal_aide.delegate.delegate(amount=lockup_amount, balance_type=3,
                                             private_key=normal_aide0_namedtuple.del_pk)['code'] == 0

        restr_info2 = normal_aide.restricting.get_restricting_info(normal_aide0_namedtuple.del_addr)
        assert restr_info2['balance'] == BaseData.delegate_amount and restr_info2['debt'] == 0
        assert restr_info2['Pledge'] == BaseData.delegate_amount

        lock_info = normal_aide.delegate.get_delegate_lock_info(normal_aide0_namedtuple.del_addr)
        assert lock_info['Locks'][0]['RestrictingPlan'] == lockup_amount

        staking_balance2 = normal_aide.platon.get_balance(normal_aide.staking.ADDRESS)
        print(staking_balance2)
        assert staking_balance1 == staking_balance2

        wait_settlement(normal_aide, 1)
        restr_info3 = normal_aide.restricting.get_restricting_info(normal_aide0_namedtuple.del_addr)
        assert restr_info3['balance'] == BaseData.delegate_amount and restr_info3['debt'] == lockup_amount
        assert restr_info3['plans'][0]['amount'] == lockup_amount
        assert restr_info3['Pledge'] == BaseData.delegate_amount

        lock_info = normal_aide.delegate.get_delegate_lock_info(normal_aide0_namedtuple.del_addr)
        assert lock_info['Locks'] == []
        assert lock_info['RestrictingPlan'] == lockup_amount

        staking_balance3 = normal_aide.platon.get_balance(normal_aide.staking.ADDRESS)
        print(staking_balance3)
        assert staking_balance2 == staking_balance3

        del_balance = normal_aide.platon.get_balance(normal_aide0_namedtuple.del_addr)
        assert normal_aide.delegate.redeem_delegate(private_key=normal_aide0_namedtuple.del_pk)['code'] == 0
        time.sleep(1)
        del_balance1 = normal_aide.platon.get_balance(normal_aide0_namedtuple.del_addr)
        assert del_balance + lockup_amount - del_balance1 < eth_utils.to_wei(0.01, 'ether')

        restr_info4 = normal_aide.restricting.get_restricting_info(normal_aide0_namedtuple.del_addr)
        assert restr_info4['balance'] == lockup_amount and restr_info4['debt'] == 0
        assert restr_info4['Pledge'] == lockup_amount
        assert restr_info4['plans'][0]['amount'] == lockup_amount

        lock_info = normal_aide.delegate.get_delegate_lock_info(normal_aide0_namedtuple.del_addr)
        assert lock_info['Locks'] == []
        assert lock_info['RestrictingPlan'] == 0
        assert lock_info['Released'] == 0

        staking_balance4 = normal_aide.platon.get_balance(normal_aide.staking.ADDRESS)
        print(staking_balance4)
        assert staking_balance3 - lockup_amount == staking_balance4

    def test_undelegate_restricting_lock_release_long(self, update_undelegate_freeze_duration_three, normal_aide):
        """
       测试 锁定期 锁仓金额 委托多节点
        @Desc:
            -创建锁仓计划 锁仓委托 A 节点 / limit * 100 等待委托生效
            -锁仓赎回委托锁定期 委托 A节点 / limit * 50 委托锁定期比锁仓释放周期长
            -等待委托解锁期领取委托锁仓金 查看锁仓计划
        """
        chain, new_gen_file = update_undelegate_freeze_duration_three
        for host in chain.hosts:
            host.supervisor.clean()
        chain.install(genesis_file=new_gen_file)
        time.sleep(5)

        lockup_amount = BaseData.delegate_limit * 50
        plan = [{'Epoch': 3, 'Amount': lockup_amount}, {'Epoch': 4, 'Amount': lockup_amount}]

        normal_aide0_namedtuple = create_sta_del(normal_aide, plan)
        wait_settlement(normal_aide)

        staking_balance = normal_aide.platon.get_balance(normal_aide.staking.ADDRESS)
        print(staking_balance)

        assert normal_aide.delegate.withdrew_delegate(BaseData.delegate_amount, normal_aide0_namedtuple.StakingBlockNum,
                                                      private_key=normal_aide0_namedtuple.del_pk)['code'] == 0

        restr_info = normal_aide.restricting.get_restricting_info(normal_aide0_namedtuple.del_addr)
        assert restr_info['balance'] == BaseData.delegate_amount and restr_info['debt'] == 0
        assert restr_info['Pledge'] == BaseData.delegate_amount

        lock_info = normal_aide.delegate.get_delegate_lock_info(normal_aide0_namedtuple.del_addr)
        assert lock_info['Locks'][0]['RestrictingPlan'] == BaseData.delegate_amount

        staking_balance1 = normal_aide.platon.get_balance(normal_aide.staking.ADDRESS)
        print(staking_balance1)
        assert staking_balance == staking_balance1

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
        assert restr_info3['plans'][0]['blockNumber'] == 640
        assert restr_info3['Pledge'] == BaseData.delegate_amount

        lock_info = normal_aide.delegate.get_delegate_lock_info(normal_aide0_namedtuple.del_addr)
        print(lock_info)
        assert lock_info['Locks'][0]['RestrictingPlan'] == lockup_amount
        assert lock_info['RestrictingPlan'] == 0

        staking_balance2 = normal_aide.platon.get_balance(normal_aide.staking.ADDRESS)
        print(staking_balance2)
        assert staking_balance1 == staking_balance2

        del_balance = normal_aide.platon.get_balance(normal_aide0_namedtuple.del_addr)
        print(del_balance)

        assert normal_aide.delegate.redeem_delegate(private_key=normal_aide0_namedtuple.del_pk)['code'] == 0
        del_balance1 = normal_aide.platon.get_balance(normal_aide0_namedtuple.del_addr)
        print(del_balance1)
        assert del_balance1 - del_balance < eth_utils.to_wei(0.01, 'ether')

        restr_info4 = normal_aide.restricting.get_restricting_info(normal_aide0_namedtuple.del_addr)
        print(restr_info4)
        assert restr_info4['balance'] == BaseData.delegate_amount and restr_info4['debt'] == lockup_amount
        assert restr_info4['Pledge'] == BaseData.delegate_amount
        assert restr_info4['plans'][0]['amount'] == lockup_amount

        lock_info = normal_aide.delegate.get_delegate_lock_info(normal_aide0_namedtuple.del_addr)
        assert lock_info['Locks'][0]['RestrictingPlan'] == lockup_amount
        assert lock_info['RestrictingPlan'] == 0

        staking_balance2 = normal_aide.platon.get_balance(normal_aide.staking.ADDRESS)
        print(staking_balance1)
        assert staking_balance1 == staking_balance2

        wait_settlement(normal_aide)

        assert normal_aide.delegate.redeem_delegate(private_key=normal_aide0_namedtuple.del_pk)['code'] == 0
        del_balance2 = normal_aide.platon.get_balance(normal_aide0_namedtuple.del_addr)
        print(del_balance1)
        assert del_balance1 + lockup_amount - del_balance2 < eth_utils.to_wei(0.01, 'ether')

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

        staking_balance3 = normal_aide.platon.get_balance(normal_aide.staking.ADDRESS)
        print(staking_balance3)
        assert staking_balance2 - lockup_amount == staking_balance3


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
    for host in chain.hosts:
        host.supervisor.clean()
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
    assert del_balance1 - del_balance < eth_utils.to_wei(0.01, 'ether')

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


@pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
@pytest.mark.parametrize('create_lock_free_amt', [{"ManyAcc": False}], indirect=True)
def test_undelegate_lock_gas(create_lock_free_amt):
    """
    测试 锁定期再委托和领取委托金gas费用
    @Desc:
        -创建锁定期 只有自由金额
        -计算锁定期委托gas费用，锁定期委托金再委托时自定义gas
        -计算委托金领取gas费用，领取委托金时自定义gas
    """
    normal_aide0, normal_aide1, normal_aide0_namedtuple, normal_aide1_namedtuple, req_param = create_lock_free_amt

    # 计算委托锁定gas费用
    normal_aide0.set_result_type('txn')
    del_info = normal_aide0.delegate.delegate(BaseData.delegate_limit, balance_type=3,
                                              private_key=normal_aide0_namedtuple.del_pk)
    data_gas = get_dynamic_gas_parameter(del_info['data'])
    del_gas = 21000 + 6000 + 16000 + data_gas
    assert del_info['gas'] == del_gas

    redeem_info = normal_aide0.delegate.redeem_delegate(private_key=normal_aide0_namedtuple.del_pk)
    data_gas = get_dynamic_gas_parameter(redeem_info['data'])
    redeem_gas = 21000 + 6000 + 6000 + data_gas
    assert redeem_info['gas'] == redeem_gas

    normal_aide0.set_result_type('event')
    del_balance = normal_aide0.platon.get_balance(normal_aide0_namedtuple.del_addr)
    normal_aide0.delegate.delegate(BaseData.delegate_limit, txn={'gas': del_gas}, balance_type=3,
                                   private_key=normal_aide0_namedtuple.del_pk)
    time.sleep(1)
    del_balance1 = normal_aide0.platon.get_balance(normal_aide0_namedtuple.del_addr)
    assert del_balance - del_balance1 == del_gas * normal_aide0.platon.gas_price

    redeem_balance = normal_aide0.platon.get_balance(normal_aide0_namedtuple.del_addr)
    normal_aide0.delegate.redeem_delegate(txn={'gas': redeem_gas}, private_key=normal_aide0_namedtuple.del_pk)
    time.sleep(1)
    redeem_balance1 = normal_aide0.platon.get_balance(normal_aide0_namedtuple.del_addr)
    assert redeem_balance - redeem_balance1 == redeem_gas * normal_aide0.platon.gas_price

    wait_settlement(normal_aide0, 1)
    lock_info = normal_aide0.delegate.get_delegate_lock_info(normal_aide0_namedtuple.del_addr)
    redeem_balance3 = normal_aide0.platon.get_balance(normal_aide0_namedtuple.del_addr)
    normal_aide0.delegate.redeem_delegate(txn={'gas': redeem_gas}, private_key=normal_aide0_namedtuple.del_pk)
    time.sleep(1)
    redeem_balance4 = normal_aide0.platon.get_balance(normal_aide0_namedtuple.del_addr)
    assert redeem_balance3 - (redeem_balance4 - lock_info['Released']) == redeem_gas * normal_aide0.platon.gas_price


@pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
@pytest.mark.parametrize('create_lock_free_amt', [{"ManyAcc": False}], indirect=True)
def test_undelegate_lock_gas_insufficient(create_lock_free_amt):
    """
    测试 锁定期再委托和领取委托金gas费用不足
    @Desc:
        -创建锁定期 只有自由金额
        -计算锁定期委托gas费用，锁定期委托金再委托时gas不足
        -计算委托金领取gas费用，领取委托金时gas不足
    """

    normal_aide0, normal_aide1, normal_aide0_namedtuple, normal_aide1_namedtuple, req_param = create_lock_free_amt

    # 调用委托和领取委托接口
    del_balance = normal_aide0.platon.get_balance(normal_aide0_namedtuple.del_addr)
    del_amount = del_balance - (normal_aide0.platon.gas_price * 21000)
    normal_aide0.transfer.transfer(normal_aide0.staking.ADDRESS, del_amount,
                                   private_key=normal_aide0_namedtuple.del_pk)
    del_balance = normal_aide0.platon.get_balance(normal_aide0_namedtuple.del_addr)
    # normal_aide0.delegate.delegate(balance_type=3, private_key=normal_aide0_namedtuple.del_pk)

    with pytest.raises(ValueError) as exception_info:
        normal_aide0.delegate.delegate(private_key=normal_aide0_namedtuple.del_pk)
    assert str(exception_info.value) == "{'code': -32000, 'message': 'insufficient funds for gas * price + value'}"

    lock_info = normal_aide0.delegate.get_delegate_lock_info(normal_aide0_namedtuple.del_addr)
    print(lock_info)
    assert lock_info['Locks'][0]['Released'] == BaseData.delegate_amount and lock_info['Released'] == 0

    with pytest.raises(ValueError) as exception_info:
        normal_aide0.delegate.redeem_delegate(private_key=normal_aide0_namedtuple.del_pk)
    assert str(exception_info.value) == "{'code': -32000, 'message': 'insufficient funds for gas * price + value'}"

    wait_settlement(normal_aide0, 1)
    lock_info = normal_aide0.delegate.get_delegate_lock_info(normal_aide0_namedtuple.del_addr)
    assert lock_info['Released'] == BaseData.delegate_amount

    with pytest.raises(ValueError) as exception_info:
        normal_aide0.delegate.redeem_delegate(private_key=normal_aide0_namedtuple.del_pk)
    assert str(exception_info.value) == "{'code': -32000, 'message': 'insufficient funds for gas * price + value'}"

#
# @pytest.mark.parametrize('choose_undelegate_freeze_duration', [{"duration": 2, }], indirect=True)
# @pytest.mark.parametrize('create_lock_mix_amt_unlock_eq', [{"ManyAcc": True}], indirect=True)
# def test_9999(create_lock_mix_amt_unlock_eq):
#     normal_aide0, normal_aide1, normal_aide0_namedtuple, normal_aide1_namedtuple = create_lock_mix_amt_unlock_eq
#
#     lockup_amount = BaseData.delegate_amount
#     plan = [{'Epoch': 3, 'Amount': lockup_amount}, {'Epoch': 4, 'Amount': lockup_amount}]
#     normal_aide0.restricting.restricting(normal_aide0_namedtuple.del_addr, plan)
#     normal_aide0.delegate.delegate(amount=BaseData.delegate_amount, balance_type=1,
#                                    private_key=normal_aide0_namedtuple.del_pk)
#
#     normal_aide0.delegate.delegate(amount=BaseData.delegate_amount, balance_type=0,
#                                    private_key=normal_aide0_namedtuple.del_pk)
#
#     normal_aide0.delegate.delegate(amount=BaseData.delegate_amount, balance_type=3,
#                                    private_key=normal_aide0_namedtuple.del_pk)
#
#     wait_settlement(normal_aide0)
#
#     normal_aide0.delegate.delegate(amount=BaseData.delegate_amount, balance_type=1,
#                                    private_key=normal_aide0_namedtuple.del_pk)
#
#     normal_aide0.delegate.delegate(amount=BaseData.delegate_amount, balance_type=0,
#                                    private_key=normal_aide0_namedtuple.del_pk)
#
#     normal_aide0.delegate.delegate(amount=BaseData.delegate_amount, balance_type=3,
#                                    private_key=normal_aide0_namedtuple.del_pk)
#
#     del_info = normal_aide0.delegate.get_delegate_info(normal_aide0_namedtuple.del_addr)
#     print(del_info)
#
#     event = normal_aide0.delegate.withdrew_delegate(amount=normal_aide0.web3.toVon(5999, 'lat'),
#                                                     private_key=normal_aide0_namedtuple.del_pk)
#     print(event)


# def test_777777(normal_aide):
#     """
#     测试 锁定期再委托和领取委托金gas费用
#     @Desc:
#         -创建锁定期 只有自由金额
#         -计算锁定期委托gas费用，锁定期委托金再委托时自定义gas
#         -计算委托金领取gas费用，领取委托金时自定义gas
#     """
#     normal_aide0_namedtuple = create_sta_del(normal_aide)
#
#     wait_settlement(normal_aide)
#
#     print(normal_aide.delegate.get_delegate_info(normal_aide0_namedtuple.del_addr)['CumulativeIncome'])
#     print(normal_aide.delegate.get_delegate_reward(normal_aide0_namedtuple.del_addr)[0]['reward'])
#
#     wait_settlement(normal_aide)
#     normal_aide.delegate.withdrew_delegate(amount=BaseData.delegate_limit * 50, private_key=normal_aide0_namedtuple.del_pk)
#     print(normal_aide.delegate.get_delegate_info(normal_aide0_namedtuple.del_addr)['CumulativeIncome'])
#     print(normal_aide.delegate.get_delegate_reward(normal_aide0_namedtuple.del_addr)[0]['reward'])
#
#
#
