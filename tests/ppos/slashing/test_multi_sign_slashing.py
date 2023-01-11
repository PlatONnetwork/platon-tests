import allure
import pytest
from platon._utils.error_code import ERROR_CODE

from lib.utils import *
from setting.account import *


@pytest.mark.parametrize('repor_type', [1, 2, 3])
def test_incentive_node_report_duplicate_sign(init_nodes, repor_type):
    """
     测试 私链启动后初始验证节点双签举报
     @Desc:
         -举报 prepareBlock类型
         -举报 prepareVote类型
         -举报 viewChange类型
     """
    aide1 = init_nodes[0].aide
    aide2 = init_nodes[1].aide
    report_account = new_account(aide1, lat(200000))

    # 构建双签证据
    evidence_info = generate_evidence(init_nodes[0], repor_type)

    node_balance = aide1.staking.get_candidate_info(aide1.staking.staking_info.NodeId)['Released']
    incentive_pool_balance = aide1.platon.get_balance(INCENTIVE_POOL_ACCOUNT)
    stk_balance = aide1.platon.get_balance(aide1.staking.ADDRESS)
    acc_balance = aide1.platon.get_balance(report_account.address)

    aide1.set_result_type('txn')
    # 举报节点双签
    rep_info = aide1.slashing.report_duplicate_sign(repor_type, evidence_info, private_key=report_account.privateKey)
    gas = rep_info['gas'] * rep_info['gasPrice']

    aide1.set_result_type('auto')
    assert aide1.slashing.report_duplicate_sign(repor_type, evidence_info, private_key=report_account.privateKey).message == ERROR_CODE[0]

    pro_reward, inc_reward = get_report_reward(aide2, aide1.staking.staking_info.Shares)
    node_balance1 = aide2.staking.get_candidate_info(aide1.staking.staking_info.NodeId)['Released']
    incentive_pool_balance1 = aide2.platon.get_balance(INCENTIVE_POOL_ACCOUNT)
    stk_balance1 = aide2.platon.get_balance(aide1.staking.ADDRESS)
    acc_balance1 = aide2.platon.get_balance(report_account.address)

    assert node_balance1 == node_balance - (pro_reward + inc_reward)
    assert stk_balance1 == stk_balance - (pro_reward + inc_reward)
    assert incentive_pool_balance1 == incentive_pool_balance + inc_reward + gas
    assert acc_balance1 == acc_balance + pro_reward - gas


def test_check_evidence(init_nodes):
    aide1 = init_nodes[0].aide
    aide2 = init_nodes[1].aide
    report_account = new_account(aide1, lat(200000))
    aide1.set_result_type('event')
    aide1.wait_period('consensus')
    # 构建双签证据
    evidence_info = generate_evidence(init_nodes[0], 1, 41)
    result = aide2.slashing.check_duplicate_sign(1, 41, aide1.staking.staking_info.NodeId)
    print(result)
    aide1.slashing.report_duplicate_sign(1, evidence_info, private_key=report_account.privateKey)

    result = aide2.slashing.check_duplicate_sign(1, 41, aide1.staking.staking_info.NodeId)
    assert result is not None



