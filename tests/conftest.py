import os.path
import time
from random import choice

import pytest
from platon_aide import Aide
from platon_aide.economic import Economic
from platon_env import Node
from platon_env.chain import Chain

from lib.basic_data import BaseData
from lib.utils import assert_chain
from setting.account import MAIN_ACCOUNT, CDF_ACCOUNT


@pytest.fixture
def chain(initializer, request) -> Chain:
    """ 返回一个符合条件的chain对象，如果没有指定条件，会重新初始化chain后返回
    使用方法：
    1、和普通fixture一样直接使用
    2、从测试用例中传入条件到fixture（条件定义：lib.utils.CONDITIONS）

    使用示例：
    @pytest.mark.parametrize('chain', ['test'], indirect=True)
    def test_example(chain):
        ...
    """
    condition = getattr(request, 'param', None)

    # 根据条件判断，是否可以直接使用环境
    if condition:
        result = assert_chain(initializer, condition)
        if result:
            return initializer

    # 重新初始化环境
    initializer.stop()
    initializer.init(force=True)
    initializer.start()
    time.sleep(3)   # 等待节点真正启动

    # 重置默认账户
    for node in initializer.init_nodes:
        node.aide.set_default_account(CDF_ACCOUNT)

    for node in initializer.normal_nodes:
        node.aide.set_default_account(MAIN_ACCOUNT)

    return initializer


@pytest.fixture
def nodes(chain) -> [Node]:
    return chain.nodes


@pytest.fixture
def normal_nodes(chain) -> [Node]:
    return chain.normal_nodes


@pytest.fixture
def init_nodes(chain) -> [Node]:
    return chain.init_nodes


@pytest.fixture
def node(nodes) -> Node:
    """ 返回一个随机节点的aide对象
    """
    return choice(nodes)


@pytest.fixture
def init_node(init_nodes) -> Node:
    """ 返回一个创世节点的aide对象
    """
    return choice(init_nodes)


@pytest.fixture
def normal_node(normal_nodes) -> Node:
    """ 返回一个普通节点的aide对象
    """
    return choice(normal_nodes)


@pytest.fixture
def aides(nodes) -> [Aide]:
    aides = [node.aide for node in nodes]
    BaseData(aides).set_var_info()
    return aides


@pytest.fixture
def init_aides(init_nodes) -> [Aide]:
    aides = [node.aide for node in init_nodes]
    BaseData(aides).set_var_info()
    return aides


@pytest.fixture
def normal_aides(normal_nodes) -> [Aide]:
    aides = [node.aide for node in normal_nodes]
    BaseData(aides).set_var_info()
    return aides


@pytest.fixture
def aide(aides) -> Aide:
    """ 返回一个随机节点的aide对象
    """
    BaseData(aides).set_var_info()
    return choice(aides)


@pytest.fixture
def init_aide(init_aides) -> Aide:
    """ 返回一个创世节点的aide对象
    """
    BaseData(init_aides).set_var_info()
    return choice(init_aides)


@pytest.fixture
def normal_aide(normal_aides) -> Aide:
    """ 返回一个普通节点的aide对象
    """
    BaseData(normal_aides).set_var_info()
    return choice(normal_aides)


@pytest.fixture
def economic(aide) -> Economic:
    """ 返回economic对象
    """
    return aide.economic


@pytest.fixture()
def solidity(aide, request):
    """ 根据传入的合约名称，编译合约，并返回一个solidity合约对象
    # todo: 待实现
    """
    name = request.param
    file = ''
    assert os.path.isfile(file), ''
    return aide.web3.platon.contract()


@pytest.fixture()
def wasm(aide, request):
    """ 根据传入的合约名称，编译合约，返回一个wasm合约对象
    # todo: 待实现
    """
    name = request.param
    file = ''
    assert os.path.isfile(file), ''
    return aide.web3.platon.contract(vm_type='wasm')
