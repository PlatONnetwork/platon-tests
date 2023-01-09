import random
import time

import allure
import pytest
from lib.assertion import Assertion
from lib.blockchain import max_byzantine_node, get_block_number, check_block, check_stop_check
from loguru import logger

from setting import setting


@allure.title("start all nodes normally")
@pytest.mark.P0
def test_all_node_normal(chain, aides):
    """
    @describe: 用于测试启动所有共识节点，查看块情况
    @step: 并发获取所有节点区块
    @expect:
        - 8个节点 出块高度差距 < 5
        - 3秒前 max(区块高度) < 等待3s后节点中最高区块
    """
    pre_block_number = get_block_number(aides)
    assert max(pre_block_number) - min(pre_block_number) < 5
    time.sleep(3)
    later_block_number = get_block_number(aides)
    assert max(pre_block_number) < max(later_block_number)


@allure.title("Start consensus node 2f+1 starts to block")
@pytest.mark.P0
def test_SC_ST_002(chain, init_aides):
    """
    @describe: 达到最小共识数即开始出块
    @step: 部署三个共识节点
    @expect:
        - 更改创世文件，并清理链
        - 部署3个共识节点正常出块
        - 停1个共识节点
    @expect:
        - 三个共识节点正常出块
        - 停1个节点后停止出块
    """
    chain.uninstall()
    _byzantine_node: int = (2 * max_byzantine_node(chain) + 1)

    start_node = list(chain.init_nodes)[:_byzantine_node]
    chain.install(setting.PLATON, setting.NETWORK, setting.GENESIS_FILE, nodes=start_node)
    assert check_block(aides=init_aides[:_byzantine_node], need_number=10, multiple=3)

    stop_node = random.choices(start_node)
    chain.stop(nodes=stop_node)
    check_aide_list = [aide for aide in init_aides[:_byzantine_node] if aide.node != stop_node[0]]
    assert check_stop_check(aides=check_aide_list)


@allure.title("Start all nodes normally, and gradually close f")
@pytest.mark.P0
def test_SC_CL_001(chain, aides):
    """
    启动n个节点后，逐渐关闭f(指作弊节点)，则关闭节点的不出块
    原代码：关闭一个作弊节点后 验证其他节点正常出块, get_all_nodes 获取的是8个节点，随便关闭一个？还是要关闭共识节点
    """
    all_nodes: set = chain.init_nodes.symmetric_difference(chain.normal_nodes)
    stop_node = random.choices(list(all_nodes), k=max_byzantine_node(chain))
    chain.stop(nodes=stop_node)

    check_aide_list = list()
    for aide in aides:
        for node in stop_node:
            if aide.node != node:
                check_aide_list.append(aide)

    # 验证逻辑 需要优化一下
    assert check_block(aides=check_aide_list, need_number=10 + max(get_block_number(check_aide_list)), multiple=1)


@allure.title("Start 2f+1 nodes normally, start one after 30 seconds")
@pytest.mark.P2
def test_SC_IV_001(chain, init_aides):
    """
    @describe: 先启动2f+1, 30后再启动1个节点

    @step:
        - 清理链
        - 重新部署三个共识节点,会根据当前传入节点修改创世文件
        - 再部署一个节点,创世文件不改变 genesis_is_reset=False,指定连接节点 static_nodes=[i.enode for i in chain.init_nodes]

    @expect:
        - 部署三个节点 正常出块
        - 后部署一个节点 end_aides_block_number > start_aides_block_number

    @teardown: chain.uninstall() 清理链
    """
    _byzantine_node: int = (2 * max_byzantine_node(chain) + 1)

    chain.install(setting.PLATON, setting.NETWORK, genesis_file=setting.GENESIS_FILE,
                  nodes=list(chain.init_nodes)[:_byzantine_node])
    time.sleep(30)

    start_block_number: list = get_block_number(init_aides[:_byzantine_node], detail=True)
    logger.info(f"链上节点块高：{start_block_number}")

    chain.install(setting.PLATON, setting.NETWORK, genesis_file=setting.GENESIS_FILE, genesis_is_reset=False,
                  static_nodes=[i.enode for i in chain.init_nodes],
                  nodes=list(chain.init_nodes)[_byzantine_node: _byzantine_node + 1])
    assert check_block(aides=init_aides[_byzantine_node:_byzantine_node + 1], need_number=10, multiple=3)

    end_block_number: list = get_block_number(init_aides[:_byzantine_node + 1], detail=True)
    logger.info(f"链上节点块高：{end_block_number}")

    Assertion.old_lt_new_dict(old=start_block_number, new=end_block_number)
