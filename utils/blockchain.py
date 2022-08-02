import time
from typing import List, Set, Dict
from platon_env.node import Node

from lib.aide import Aide


def get_max_cheat_node(init_nodes: Set[Node]) -> int:
    """
    获取作弊节点的最大数量
    @param init_nodes: 共识节点列表
    @return: 最大作弊节点值 int
    """
    num = len(init_nodes)
    if num < 3:
        raise Exception("the number of consensus nodes is less than 3")
    if num == 3:
        return 0
    f = (num - 1) / 3
    return int(f)


def max_byzantine_node(chain) -> int:
    """最大拜占庭节点数"""
    return get_max_cheat_node(chain.init_nodes)


def check_block(aides: List[Aide], need_number=10, multiple=3):
    """
    验证链上节点出块
    @param need_number: 出块总数量
    @param multiple: 周期
    @param aides: 节点列表
    @return:
    """
    if aides is None:
        raise Exception("Please pass in mandatory parameter aides")

    use_time = int(need_number * aides[0].economic.block_time * multiple)
    while use_time:
        block_number_list = get_block_number(aides)
        if max(block_number_list) < need_number:
            time.sleep(1)
            use_time -= 1
            continue
        return True
    raise Exception("The environment is not working properly")


def check_stop_check(aides: List[Aide]):
    start = max(get_block_number(aides))
    time.sleep(3)
    return True if start == max(get_block_number(aides)) else False


def get_block_number(aides, detail=False):
    if detail:
        return [{aide.uri.replace("http://", ""): aide.get_block_number} for aide in aides]
    else:
        return [aide.get_block_number for aide in aides]
