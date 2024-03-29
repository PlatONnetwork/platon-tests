from os.path import join

import pytest
from platon_env import Chain

from setting.account import MAIN_ACCOUNT, CDF_ACCOUNT
from setting.setting import BASE_DIR


def pytest_addoption(parser):
    # todo: 增加清理缓存的参数（需要platon_env增加清理缓存功能）
    # todo: 增加强制部署的参数（需要platon_env增加强制部署功能）
    parser.addoption("--chainFile", action="store", help="chainFile: chain data file")


@pytest.fixture(scope='session')
def initializer(request) -> Chain:
    """ 初始化链对象，不建议直接使用
    """
    chain_file = request.config.getoption("--chainFile")
    chain = Chain.from_file(join(BASE_DIR, chain_file))
    # 先清理supervisor，再进行安装
    for host in chain.hosts:
        host.supervisor.clean()
    chain.install()

    # 设置默认账户
    for node in chain.init_nodes:
        node.aide.set_default_account(CDF_ACCOUNT)

    for node in chain.normal_nodes:
        node.aide.set_default_account(MAIN_ACCOUNT)

    yield chain
    # chain.uninstall()


@pytest.fixture
def recover(initializer):
    """ 在用例运行结束后恢复环境，仅用于用例更改了环境的情况
    """
    yield
    # 先清理supervisor，再进行安装
    for host in initializer.hosts:
        host.supervisor.clean()
    initializer.install()
