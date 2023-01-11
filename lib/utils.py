import decimal
import math
import time
from typing import Union

import rlp
from loguru import logger
from platon_account.signers.local import LocalAccount
from platon_aide import Aide
from platon_aide.staking import StakingInfo
from platon_aide.utils.utils import mock_duplicate_sign
from platon_utils import to_von

NO_PROPOSAL = 'no proposal'
CONDITIONS = set(NO_PROPOSAL)  # 方便用例fixture使用


def assert_chain(chain, condition):
    """ 判断chain是否符合条件
    """
    if not condition:
        return True

    # 是否存在提案
    if condition == NO_PROPOSAL:
        pass

    return False


def new_account(aide: Aide, balance=0, restricting=None) -> LocalAccount:
    """ 创建账户，并给账户转入金额
    注意：restricting代表锁仓计划，而非锁仓金额
    """
    account = aide.platon.account.create(hrp=aide.hrp)
    if balance:
        aide.transfer.transfer(account.address, balance)
    if restricting:
        aide.restricting.restricting(account.address, restricting)

    return account


def lat(number: Union[int, float, str, decimal.Decimal]):
    return to_von(number, unit='lat')


def is_staking_member(node: StakingInfo, nodes: [StakingInfo]):
    """ 判断节点
    """
    node_id = node.NodeId
    for n in nodes:
        if n.NodeId == node_id:
            return True

    return False




def get_switchpoint_by_settlement(aide, number=0):
    """
    Get the last block of the current billing cycle
    :param node: node object
    :param number: number of billing cycles
    :return:
    """
    block_number = aide.economic.epoch_blocks * number
    tmp_current_block = aide.platon.block_number
    current_end_block = math.ceil(
        tmp_current_block / aide.economic.epoch_blocks) * aide.economic.epoch_blocks + block_number
    return current_end_block


def wait_settlement(aide, settlement=0):
    """
    Waiting for a billing cycle to settle
    :param node:
    :param number: number of billing cycles
    :return:
    """
    end_block = get_switchpoint_by_settlement(aide, settlement)
    aide.wait_block(end_block)


def get_switchpoint_by_consensus(aide, consensus=0):
    """
    Get the last block of the current billing cycle
    :param node: node object
    :param consensus: consensus of billing cycles
    :return:
    """
    block_number = aide.economic.consensus_blocks * consensus
    tmp_current_block = aide.platon.block_number
    current_end_block = math.ceil(
        tmp_current_block / aide.economic.consensus_blocks) * aide.economic.consensus_blocks + block_number
    return current_end_block


def wait_consensus(aide, consensus=0):
    """
    Waiting for a consensus round to end
    """
    end_block = get_switchpoint_by_consensus(aide, consensus)
    aide.wait_block(end_block)


def get_pledge_list(func, nodeid=None) -> list:
    """
    todo: 优化
    View the list of specified node IDs
    :param func: Query method, 1. List of current pledge nodes 2,
     the current consensus node list 3, real-time certifier list
    :return:
    """
    validator_info = func()
    logger.info(f'validator_info: {validator_info}')
    if validator_info == "Getting verifierList is failed:The validator is not exist":
        time.sleep(10)
        validator_info = func()
    if validator_info == "Getting candidateList is failed:CandidateList info is not found":
        time.sleep(10)
        validator_info = func()
    if not nodeid:
        validator_list = []
        for info in validator_info:
            validator_list.append(info.NodeId)
        return validator_list
    else:
        for info in validator_info:
            if nodeid == info.NodeId:
                return info.RewardPer, info.NextRewardPer
        raise Exception('node_id {} not in the list'.format(nodeid))


def get_dynamic_gas_parameter(data):
    zero_number, byte_group_len = 0, len(data)
    for i in data:
        if i != 0:
            continue
        zero_number += 1
    dynamic_gas = (byte_group_len - zero_number) * 16 + zero_number * 4
    return dynamic_gas


def withdraw_delegate_reward_gas_fee(aide, staking_num, uncalcwheels, gas_price=None):
    if gas_price is None:
        gas_price = aide.platon.gas_price
    data = rlp.encode([rlp.encode(int(5000))])
    gas = get_dynamic_gas_parameter(data) + 8000 + 3000 + 21000 + staking_num * 1000 + uncalcwheels * 100
    return gas * gas_price


def get_block_count_number(aide, node_id=None, current_block=None, roundnum=1):
    """
        Get the number of blocks out of the verification node
        """
    if current_block is None:
        current_block = aide.platon.block_number
    if node_id is None:
        node_id = aide.node_id

    block_namber = aide.economic.consensus_blocks * roundnum
    count = 0
    for i in range(block_namber):
        if current_block > 0:
            # block = aide.platon.get_block(current_block)
            # print(block)
            public_key = aide.ec_recover(current_block)
            # node_id = get_pub_key(node.url, current_block)
            current_block = current_block - 1
            if node_id == public_key:
                count = count + 1
        else:
            break
    return count


def hex_to_int(data):
    return int(data, 16)


def parse_lock_info(data):
    data = dict(data)
    data['Released'] = hex_to_int(data['Released'])
    data['RestrictingPlan'] = hex_to_int(data['RestrictingPlan'])
    if data['Locks']:
        for item in data['Locks']:
            item['Released'] = hex_to_int(item['Released'])
            item['RestrictingPlan'] = hex_to_int(item['RestrictingPlan'])
    return data


def get_current_year_reward(aide):
    """
    Get the first year of the block reward, pledge reward
    :return:
    """
    # if new_block_rate is None:
    #     new_block_rate = self.genesis.economicModel.reward.newBlockRate
    # # current_block = node.eth.blockNumber
    # annualcycle = (self.additional_cycle_time * 60) // self.settlement_size
    # annual_size = annualcycle * self.settlement_size
    # # starting_block_height = math.floor(current_block / annual_size) * annual_size
    # time.sleep(10)
    # # amount = node.eth.getBalance(self.cfg.INCENTIVEPOOL_ADDRESS, starting_block_height)
    # if amount is None:
    #     amount = 262215742000000000000000000
    # block_proportion = str(new_block_rate / 100)
    # staking_proportion = str(1 - new_block_rate / 100)
    # block_reward = int(Decimal(str(amount)) * Decimal(str(block_proportion)) / Decimal(str(annual_size))) - node.web3.toWei(1 , 'ether')
    # staking_reward = int(
    #     Decimal(str(amount)) * Decimal(str(staking_proportion)) / Decimal(str(annualcycle)) / Decimal(
    #         str(verifier_num)))
    # # staking_reward = amount - block_reward
    block_reward = aide.staking.get_block_reward()
    staking_reward_total = aide.staking.get_staking_reward()
    logger.info("block_reward: {} staking_reward_total: {}".format(block_reward, staking_reward_total))
    verifier_num = aide.calculator.get_verifier_count()
    staking_reward = int(decimal.Decimal(str(staking_reward_total)) / decimal.Decimal(str(verifier_num)))
    logger.info("质押奖励：{}".format(staking_reward))

    return block_reward, staking_reward


def get_report_reward(aide, amount=None, penalty_ratio=None, proportion_ratio=None):
    """
    Gain income from double sign whistleblower and incentive pool
    """
    if not amount:
        amount = aide.staking.staking_info.Shares
    if not penalty_ratio:
        penalty_ratio = aide.economic.slashing.slashFractionDuplicateSign
    if not proportion_ratio:
        proportion_ratio = aide.economic.slashing.duplicateSignReportReward
        print(type(penalty_ratio), type(proportion_ratio))
    penalty_reward = int(decimal.Decimal(str(amount)) * decimal.Decimal(str(penalty_ratio / 10000)))
    proportion_reward = int(decimal.Decimal(str(penalty_reward)) * decimal.Decimal(str(proportion_ratio / 100)))
    incentive_pool_reward = penalty_reward - proportion_reward
    return proportion_reward, incentive_pool_reward


def generate_evidence(node, evidence_type=1, report_block=None):
    """
    Generate double sign evidence according to node private key information
    """
    if report_block is None:
        report_block = node.aide.platon.block_number
        if report_block < 41:
            report_block = 41
            node.aide.wait_period('consensus')
    evidence = mock_duplicate_sign(evidence_type, node.node_key, node.bls_prikey, report_block)

    return evidence


class PrintInfo:

    @staticmethod
    def p_get_delegate_lock_info(aide, aide_nt):
        """
        aide_nt.del_addr的锁定期信息
        @param aide: 发起查询的aide对象
        @param aide_nt: 查询aide_nt.del_addr的锁定期信息
        @return: aide_nt.del_addr的锁定期信息
        """
        lock_info = aide.delegate.get_delegate_lock_info(address=aide_nt.del_addr)
        logger.info(f"lock_info: {lock_info}")
        return lock_info

    @staticmethod
    def p_get_restricting_info(aide, aide_nt):
        """
        aide_nt.del_addr的锁仓计划
        @param aide: 发起查询的aide对象
        @param aide_nt: 查询aide_nt.del_addr的锁仓计划
        @return: aide_nt.del_addr的锁仓计划
        """
        restr_info = aide.restricting.get_restricting_info(aide_nt.del_addr)
        logger.info(f'restr_info: {restr_info}')
        return restr_info

    def p_get_delegate_info(aide, del_addr, aide_nt):
        """
        查询del_addr 在 aide_nt.node_id 的委托信息
        @param aide: 发起查询的aide对象
        @param del_addr: 查询地址
        @param aide_nt: 包含需查询的节点ID 和 节点质押块高
        @return: del_addr 在 aide_nt.node_id 的委托信息
        """
        del_info = aide.delegate.get_delegate_info(del_addr, aide_nt.node_id, aide_nt.StakingBlockNum)
        logger.info(f"delegate_info: {del_info}")
        return del_info

    @staticmethod
    def p_get_candidate_info(run_aide, query_aide):
        """
        查询并打印 node_id 质押信息
        @param run_aide: 存活aide
        @param query_aide: 查询aide
        """
        candidate_info = run_aide.staking.get_candidate_info(node_id=query_aide.node_id)
        logger.info(f"{candidate_info}")
        return candidate_info

    @staticmethod
    def p_withdrew_delegate(run_aide, withdrew_amt, withdrew_aide_nt, del_pk):
        """@return: 赎回委托数据中data"""
        response = run_aide.delegate.withdrew_delegate(withdrew_amt, withdrew_aide_nt.StakingBlockNum,
                                                       node_id=withdrew_aide_nt.node_id,
                                                       private_key=del_pk)
        logger.info(f'withdrew_delegate: {response}')
        assert response['code'] == 0
        return response.data
