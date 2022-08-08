"""
测试各个设置下的出块情况
"""
import time

import allure
import pytest
from platon_env.genesis import Genesis

from setting import setting


@allure.title("Test node interconnections between different init_node founding files")
@pytest.mark.P0
def test_diff_init_node_connect(init_aide, normal_aide):
    """
    @describe: 测试不同init_node创世文件之间的节点互连

    @setup:
        - 部署测试环境(8个)节点
        - 获取共识节点 和 标准节点

    @step:
        - 获取标准节点 更改 创世文件并重新部署
        - 部署节点连接共识节点
        - net.peerCount 返回当前节点上已经连接的其他节点数量

    @expect: 重新部署节点正常运行 、net.peerCount == 0

    @teardown: chain.uninstall() 清理链
    """
    redeploy_one_node(normal_aide)
    normal_aide.admin.add_peer(init_aide.node.enode)
    time.sleep(5)
    assert normal_aide.web3.net.peer_count == 0


@allure.title("Test deployment of a single-node private chain, synchronization of single-node blocks")
@pytest.mark.P0
def test_deploy_one_node_connect(init_aide, normal_aide):
    """
    @describe: 测试部署单节点 同步单节点块

    @setup:
        - 部署测试环境(8个)节点
        - 获取共识节点 和 标准节点

    @step:
        - 获取标准节点 更改 创世文件并重新部署
        - 共识节点使用更改后的创建文件重新部署
        - 两个节点连接, net.peerCount == 1

    @expect: 标准节点 和 共识节点 都正常出块

    @teardown: chain.uninstall() 清理链
    """
    genesis_one_init_node_file = redeploy_one_node(normal_aide)
    time.sleep(5)
    assert normal_aide.platon.block_number > 0, "block height has not increased"
    _ = redeploy_one_node(init_aide, genesis_file=genesis_one_init_node_file)
    init_aide.admin.add_peer(normal_aide.node.enode)
    time.sleep(5)
    assert init_aide.platon.block_number > 0, "block height has not increased"


def redeploy_one_node(aide_obj, genesis_file=None):
    """
    重新部署一个单节点
    @param aide_obj: Aide对象
    @param genesis_file: 有值则按文件部署，不传按当前节点信息修改创世文件
    @return: 当前节点修改后创建文件 or None
    """
    genesis_one_init_node_file = None
    test_node = aide_obj.node
    if not genesis_file:
        genesis = Genesis(setting.GENESIS_FILE)
        genesis.fill_init_nodes(nodes=[test_node])
        genesis_one_init_node_file = setting.GENESIS_FILE.replace("genesis", "genesis_one_init_node")
        genesis.save(genesis_one_init_node_file)
        # 将genesis_13_path 上传至服务并更名 genesis 可手动查看验证
        test_node.install(setting.PLATON, setting.NETWORK, genesis_file=genesis_one_init_node_file)
    else:
        test_node.install(setting.PLATON, setting.NETWORK, genesis_file=genesis_file)
    assert test_node.status(), "Node deployment failure"
    return genesis_one_init_node_file
