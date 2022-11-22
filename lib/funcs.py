import math
from typing import Literal

from setting.account import MAIN_ACCOUNT
from platon_env.chain import Chain

from lib.aide import Aide

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


def get_aides(chain: Chain, _type: Literal['all', 'init', 'normal'] = 'all'):
    """ 根据不同的类型，获取
    todo: 待扩展 validator、verifier、staking 等实时方式
    """
    assert _type in ['all', 'init', 'normal']

    nodes = []
    if _type == 'all':
        nodes = chain.nodes
    elif _type == 'init':
        nodes = chain.init_nodes
    elif _type == 'normal':
        nodes = chain.normal_nodes

    aides = []
    for node in nodes:
        aide = Aide(node)
        aide.set_default_account(MAIN_ACCOUNT)
        aides.append(aide)

    return aides


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
