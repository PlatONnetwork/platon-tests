import os.path
import time
from random import choice

import pytest
from client_sdk_python import Account
from hexbytes import HexBytes
from platon_aide import Aide
from platon_env.chain import Chain

from setting import setting
from lib.funcs import assert_chain, get_aides
from lib.account import MAIN_ACCOUNT
from os.path import join

from setting.setting import BASE_DIR


@pytest.fixture(scope='session')
def chain(request):
    """ 返回链对象，不恢复环境，请谨慎使用
    """
    chain_file = request.config.getoption("--chainFile")
    chain = Chain.from_file(join(BASE_DIR, chain_file))
    chain.install()
    # todo：优化等待链出块的方式
    time.sleep(3)

    yield chain
    chain.uninstall()


@pytest.fixture
def condition_chain(chain, request):
    """
    支持在使用该fixture时，传入一个参数，返回一个符合条件的chain对象。
    当前链无法满足条件时，会进行重新部署。
    注意：
    1、通过lib.funcs.CONDITIONS，获取当前支持的判断条件
    2、多个条件，请使用多个fixture来完成
    """
    condition = request.param
    result = assert_chain(chain, condition)
    if not result:
        chain.install()
    return chain


@pytest.fixture()
def defer_reset_chain(chain: Chain):
    """ 返回chain对象，并且在用例运行完成后恢复环境
    """
    yield chain
    chain.install(setting.PLATON,
                  setting.NETWORK,
                  setting.GENESIS_FILE,
                  )
    time.sleep(5)       # 等待链出块


@pytest.fixture(scope='session')
def aides(chain: Chain):
    """ 返回链上所有节点的aide对象列表
    """
    return get_aides(chain, 'all')


@pytest.fixture
def aide(aides) -> Aide:
    """ 返回一个随机节点的aide对象
    """
    return choice(aides)


@pytest.fixture(scope='session')
def init_aides(chain: Chain):
    """ 返回链上创世节点的aide对象列表
    """
    return get_aides(chain, 'init')


@pytest.fixture
def init_aide(init_aides):
    """ 返回一个创世节点的aide对象
    """
    init_aides = choice(init_aides)
    return init_aides


@pytest.fixture(scope='session')
def normal_aides(chain: Chain):
    """ 返回链上普通节点的aide对象列表
    """
    normal_aides = get_aides(chain, 'normal')
    return normal_aides


@pytest.fixture
def normal_aide(normal_aides):
    """ 返回一个普通节点的aide对象
    """
    normal_aide = choice(normal_aides)
    return normal_aide


@pytest.fixture
def validator_aides():
    ...


@pytest.fixture
def validator_aide(validator_aides):
    ...


@pytest.fixture
def verifier_aides():
    ...


@pytest.fixture
def verifier_aide(validator_aides):
    ...


@pytest.fixture()
def solidity(node, request):
    """ 根据传入的合约参数，返回一个solidity合约对象
    注意：
    1、
    """
    name = request.param
    file = ''
    assert os.path.isfile(file), ''
    return node.web3.platon.contract()


@pytest.fixture()
def wasm(node, request):
    """ 根据传入的合约参数，返回一个solidity合约对象
    """
    name = request.param
    file = ''
    assert os.path.isfile(file), ''
    return node.web3.platon.contract(vm_type='wasm')


def generate_account(aide, balance=0):
    account = aide.platon.account.create(hrp=aide.hrp)
    address = account.address
    prikey = account.privateKey.hex()[2:]
    if balance != 0:
        aide.transfer.transfer(address, balance)
    return address, prikey

# def get_datahash(aide, txn, privatekey=Master_prikey):
#     if not txn.get('nonce'):
#         account = aide.web3.platon.account.from_key(privatekey, hrp=aide.web3.hrp)
#         nonce = aide.web3.platon.get_transaction_count(account.address)
#         txn['nonce'] = nonce
#
#     signed_txn = aide.web3.platon.account.sign_transaction(txn, privatekey, hrp=aide.web3.hrp)
#     data_hash = HexBytes(signed_txn.rawTransaction).hex()
#     return data_hash
