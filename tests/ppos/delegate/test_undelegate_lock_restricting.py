import inspect
import time

from decimal import Decimal

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


def test_lock_blend_undelegate(update_undelegate_freeze_duration, normal_aide):

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

    assert normal_aide.delegate.delegate(amount=lockup_amount, balance_type=3,
                                         private_key=normal_aide0_namedtuple.del_pk)['code'] == 0

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

    dele_info = normal_aide.delegate.get_delegate_info(normal_aide0_namedtuple.del_addr)
    print(dele_info)

    assert normal_aide.delegate.withdraw_delegate_reward(normal_aide0_namedtuple.del_pk)['code'] == 0

    restr_info4 = normal_aide.restricting.get_restricting_info(normal_aide0_namedtuple.del_addr)
    print(restr_info4)
    assert restr_info4['balance'] == lockup_amount and restr_info4['debt'] == 0
    assert restr_info4['Pledge'] == lockup_amount

    assert normal_aide.delegate.get_delegate_lock_info(normal_aide0_namedtuple.del_addr)['code'] == 305001
