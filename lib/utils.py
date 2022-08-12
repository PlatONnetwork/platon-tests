import time

import rlp
from loguru import logger


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

