import time

import rlp
from loguru import logger
from platon_aide.economic import Economic, new_economic
from platon_aide.utils import ec_recover


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
        node_id = aide.staking._node_id

    block_namber = aide.economic.consensus_blocks * roundnum
    count = 0
    for i in range(block_namber):
        if current_block > 0:
            block = aide.platon.get_block(current_block)
            public_key = ec_recover(block)
            # node_id = get_pub_key(node.url, current_block)
            current_block = current_block - 1
            if node_id == public_key:
                count = count + 1
        else:
            break
    return count
