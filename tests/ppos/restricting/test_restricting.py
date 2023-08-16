from loguru import logger

import allure
import inspect
import time
import pytest
from platon._utils.error_code import ERROR_CODE

from lib.utils import new_account, lat


@pytest.mark.P0
def test_init_lockout_plan(init_aide):
    """
     测试 私链启动后，初始锁仓计划
    @Desc:
     -私链启动后，查询初始锁仓计划
    """
    inspect.stack()
    assert init_aide.restricting.get_restricting_info(init_aide.restricting.ADDRESS) == ERROR_CODE[304005]


@pytest.mark.P1
def test_lockout_plan_parameter_check(normal_aide):
    """
     测试 私链启动后，创建锁仓计划，校验计划参数有效性
    @Desc:
     -私链启动后，创建锁仓计划，Amount 参数输入空字符串""
     -私链启动后，创建锁仓计划，Amount 参数输入 0
     -私链启动后，创建锁仓计划，Amount 参数输入 0.1
     -私链启动后，创建锁仓计划，Amount 参数输入 -1
     -私链启动后，创建锁仓计划，Amount 参数输入空字符串None
    """
    res_account = new_account(normal_aide, lat(1000))
    plan = [{'Epoch': 1, 'Amount': ""}]
    assert normal_aide.restricting.restricting(res_account.address, plan, private_key=res_account.privateKey).message == ERROR_CODE[304011]

    plan = [{'Epoch': 1, 'Amount': 0}]
    assert normal_aide.restricting.restricting(res_account.address, plan, private_key=res_account.privateKey).message == ERROR_CODE[304011]

    plan = [{'Epoch': 1, 'Amount': 0.1}]
    assert normal_aide.restricting.restricting(res_account.address, plan, private_key=res_account.privateKey).message == ERROR_CODE[304014]

    plan = [{'Epoch': 1, 'Amount': -1}]
    try:
        normal_aide.restricting.restricting(res_account.address, plan, private_key=res_account.privateKey)
    except Exception as e:
        print(e)
        assert str(e) == 'Did not find sedes handling type int'

    plan = [{'Epoch': 1, 'Amount': None}]
    try:
        normal_aide.restricting.restricting(res_account.address, plan, private_key=res_account.privateKey)
    except Exception as e:
        print(e)
        assert str(e) == 'Did not find sedes handling type NoneType'


@pytest.mark.P1
def test_lockout_plan_parameter_check(normal_aide):
    """
     测试 私链启动后，创建锁仓计划，校验计划参数有效性
    @Desc:
     -私链启动后，创建锁仓计划，Epoch 参数输入空字符串""
     -私链启动后，创建锁仓计划，Epoch 参数输入 0
     -私链启动后，创建锁仓计划，Epoch 参数输入 0.1
     -私链启动后，创建锁仓计划，Epoch 参数输入 -1
     -私链启动后，创建锁仓计划，Epoch 参数输入空字符串None
    """
    res_account = new_account(normal_aide, lat(10000))
    plan = [{'Epoch': "", 'Amount': lat(1000)}]
    assert normal_aide.restricting.restricting(res_account.address, plan, private_key=res_account.privateKey).message == ERROR_CODE[304001]

    plan = [{'Epoch': 0, 'Amount': lat(1000)}]
    assert normal_aide.restricting.restricting(res_account.address, plan, private_key=res_account.privateKey).message == ERROR_CODE[304001]

    plan = [{'Epoch': 0.1, 'Amount': lat(1000)}]
    try:
        normal_aide.restricting.restricting(res_account.address, plan, private_key=res_account.privateKey)
    except Exception as e:
        print(e)
        assert str(e) == 'Did not find sedes handling type float'

    plan = [{'Epoch': -1, 'Amount': lat(1000)}]
    try:
        normal_aide.restricting.restricting(res_account.address, plan, private_key=res_account.privateKey)
    except Exception as e:
        print(e)
        assert str(e) == 'Did not find sedes handling type int'

    plan = [{'Epoch': None, 'Amount': lat(1000)}]
    try:
        normal_aide.restricting.restricting(res_account.address, plan, private_key=res_account.privateKey)
    except Exception as e:
        print(e)
        assert str(e) == 'Did not find sedes handling type NoneType'


@pytest.mark.P1
@pytest.mark.parametrize('number', [1, 5, 36, 37])
def test_lockout_plan_max(normal_aide, number):
    """
     测试 私链启动后，创建锁仓计划，校验计划参数有效性
    @Desc:
     -私链启动后，创建锁仓计划，Epoch 参数输入空字符串""
     -私链启动后，创建锁仓计划，Epoch 参数输入 0
     -私链启动后，创建锁仓计划，Epoch 参数输入 0.1
     -私链启动后，创建锁仓计划，Epoch 参数输入 -1
     -私链启动后，创建锁仓计划，Epoch 参数输入空字符串None
    """
    res_account = new_account(normal_aide, lat(10000))
    plan = []
    for i in range(number):
        plan.append({'Epoch': i + 1, 'Amount': lat(100)})
    if number == 37:
        assert normal_aide.restricting.restricting(res_account.address, plan, private_key=res_account.privateKey).message == ERROR_CODE[304002]

    else:
        assert normal_aide.restricting.restricting(res_account.address, plan, private_key=res_account.privateKey).message == ERROR_CODE[0]


@pytest.mark.P1
def test_lockout_plan_single_plan_insufficient(normal_aide):
    """
     测试 私链启动后，创建锁仓计划，校验计划参数有效性
    @Desc:
     -私链启动后，创建锁仓计划，Epoch 参数输入空字符串""
     -私链启动后，创建锁仓计划，Epoch 参数输入 0
     -私链启动后，创建锁仓计划，Epoch 参数输入 0.1
     -私链启动后，创建锁仓计划，Epoch 参数输入 -1
     -私链启动后，创建锁仓计划，Epoch 参数输入空字符串None
    """
    time.sleep(180)
    blockNumber = normal_aide.platon.block_number
    print("blockNumber: ", blockNumber)
    block = normal_aide.platon.getBlock(blockNumber)
    print("block: ", block)
    blockQuorumCert = normal_aide.platon.getBlockQuorumCert([block.hash.hex()])
    print("blockQuorumCert: ", blockQuorumCert)
    validator = normal_aide.debug.get_validator_by_blockNumber(blockNumber)
    print("validator: ", validator)
    account = new_account(normal_aide)
    print(normal_aide.economic.round_blocks)