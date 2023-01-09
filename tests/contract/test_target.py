import allure
import pytest
from platon_account import Account
from platon_utils import to_bech32_address

from setting.setting import *
from tests.ppos.conftest import random_text, create_token_contract


@allure.title("Create createtoken contract normally")
@pytest.mark.P0
@pytest.mark.parametrize("name_bytes_lenght, symbol_bytes_lenght", [
                        (1, 1), (1, 19), (19, 19),(19, 1), (6, 8)])
def test_createTokenContract_001(contract_aide, name_bytes_lenght, symbol_bytes_lenght):
    contract_name = random_text(name_bytes_lenght)
    contract_symbol = random_text(symbol_bytes_lenght)
    receipt = contract_aide.contract.createTokenContract(contract_name, contract_symbol, 18, 100000000, txn={'gas': 2050000}, private_key=contract_ower_prikey)
    assert receipt.status == 1 and receipt['from'] == contract_ower
    tokenContractAddress = contract_aide.contract.getTokenContract(contract_symbol)
    beachtokenContract = to_bech32_address(tokenContractAddress, 'lat')
    assert receipt['logs'][0]['address'] == beachtokenContract


@allure.title("The length of createtoken contract parameter does not meet the requirements")
@pytest.mark.P1
@pytest.mark.parametrize('name_bytes_lenght,symbol_bytes_lenght', [
                        (0, 1), (20, 19), (20, 20), (0, 0), (1, 0), (1, 20)])
def test_createTokenContract_002(contract_aide, name_bytes_lenght, symbol_bytes_lenght):
    contract_name = random_text(name_bytes_lenght)
    contract_symbol = random_text(symbol_bytes_lenght)
    logger.info(f'contract_name={contract_name}, contract_symbol={contract_symbol}')
    receipt = contract_aide.contract.createTokenContract(contract_name, contract_symbol, 18, 100000000, txn={'gas': 2050000}, private_key=contract_ower_prikey)
    assert receipt.status == 0 and receipt['from'] == contract_ower
    tokenContractAddress = contract_aide.contract.getTokenContract(contract_symbol)
    assert tokenContractAddress == '0x0000000000000000000000000000000000000000'
    beachtokenContract = to_bech32_address(tokenContractAddress, 'lat')
    assert receipt['logs'] == []



@allure.title("Createtoken contract parameter symbol already exists")
@pytest.mark.P1
def test_createTokenContract_003(contract_aide):
    contract_name = random_text(3)
    contract_symbol = random_text(3)
    receipt = contract_aide.contract.createTokenContract(contract_name, contract_symbol, 18, 100000000, txn={'gas': 2050000}, private_key=contract_ower_prikey)
    assert receipt.status == 1 and receipt['from'] == contract_ower
    tokenContractAddress = contract_aide.contract.getTokenContract(contract_symbol)
    receipt = contract_aide.contract.createTokenContract(contract_name+'A', contract_symbol, 18, 100000000,txn={'gas': 2050000}, private_key=contract_ower_prikey)
    assert receipt.status == 0 and receipt['from'] == contract_ower
    tokenContractAddress2 = contract_aide.contract.getTokenContract(contract_symbol)
    assert tokenContractAddress == tokenContractAddress2 != '0x0000000000000000000000000000000000000000'
    assert receipt.logs == []


@allure.title("Createtoken contract parameter name verification")
@pytest.mark.P1
@pytest.mark.parametrize('contract_name', [10, 18.8, 0])
def test_createTokenContract_004(contract_aide, contract_name):
    contract_symbol = random_text(3)
    status = True
    try:
        receipt = contract_aide.contract.createTokenContract(contract_name, contract_symbol, 18, 100000000, txn={'gas': 2050000}, private_key=contract_ower_prikey)
    except Exception as e:
        logger.info("exception:{}".format(e))
        status = False
    assert status == False


@allure.title("Createtoken contract parameter symbol verification")
@pytest.mark.P1
@pytest.mark.parametrize('contract_symbol', [10, 18.8, 0])
def test_createTokenContract_005(contract_aide, contract_symbol):
    contract_name = random_text(3)
    status = True
    try:
        receipt = contract_aide.contract.createTokenContract(contract_name, contract_symbol, 18, 100000000, txn={'gas': 2050000}, private_key=contract_ower_prikey)
    except Exception as e:
        logger.info("exception:{}".format(e))
        status = False
    assert status == False


@allure.title("Createtoken contract parameter decimals verification")
@pytest.mark.P1
@pytest.mark.parametrize('decimals', [-1, 2**8, '1', 18.8])
def test_createTokenContract_006(contract_aide, decimals):
    contract_name = random_text(3)
    contract_symbol = random_text(3)
    status = True
    try:
        receipt = contract_aide.contract.createTokenContract(contract_name, contract_symbol, decimals, 100000000, txn={'gas': 2050000}, private_key=contract_ower_prikey)
    except Exception as e:
        logger.info("exception:{}".format(e))
        status = False
    assert status == False


@allure.title("Createtoken contract permission verification")
@pytest.mark.P1
@pytest.mark.parametrize('user_prikey', [contract_witness_prikey, contract_monitor_prikey, contract_user_prikey])
def test_createTokenContract_007(contract_aide, user_prikey):
    # 设置预置的见证人为合约见证人
    contract_aide.contract.setWitness(contract_witness)
    witness_address = to_bech32_address(contract_aide.contract.witness()[0], 'lat')
    assert witness_address == contract_witness
    # 设置预置的监控人为合约监控人
    contract_aide.contract.setMonitor(contract_monitor)
    monitor_address = to_bech32_address(contract_aide.contract.monitor(), 'lat')
    assert monitor_address == contract_monitor

    account = Account.from_key(user_prikey)
    contract_aide.set_default_account(account)
    contract_name = random_text(3)
    contract_symbol = random_text(3)
    receipt = contract_aide.contract.createTokenContract(contract_name, contract_symbol, 18, 100000000, txn={'gas': 2050000}, private_key=account.privateKey)
    assert receipt.status == 0 and receipt['from'] == account.address
    tokenContractAddress = contract_aide.contract.getTokenContract(contract_symbol)
    assert tokenContractAddress == '0x0000000000000000000000000000000000000000'
    assert receipt.logs == []


@allure.title("Createtoken contract tokencreated event verification")
@pytest.mark.P1
@pytest.mark.parametrize('user_prikey', [contract_ower_prikey, contract_witness_prikey, contract_monitor_prikey, contract_user_prikey])
def test_createTokenContract_008(contract_aide, user_prikey):
    contract_name = random_text(3)
    contract_symbol = random_text(3)
    decimals = 10
    cap = 100000000
    receipt = contract_aide.contract.createTokenContract(contract_name, contract_symbol, decimals, cap, txn={'gas': 2050000}, private_key=contract_ower_prikey)
    assert receipt.status == 1 and receipt['from'] == contract_ower
    token_cntract_address = contract_aide.contract.getTokenContract(contract_symbol)
    account = Account.from_key(user_prikey)
    contract_aide.set_default_account(account)
    event_receipt = contract_aide.contract.TokenCreated(receipt)[0]
    assert event_receipt.args.tokenAddress == token_cntract_address
    assert event_receipt.args.symbol == contract_symbol
    assert event_receipt.args.decimals == decimals
    assert event_receipt.args.cap == cap
    assert event_receipt.event == 'TokenCreated'
    assert event_receipt.address == contract_address


@allure.title("Createtoken contract TokenCapChanged event verification")
@pytest.mark.P1
@pytest.mark.parametrize('user_prikey', [contract_ower_prikey, contract_witness_prikey, contract_monitor_prikey, contract_user_prikey])
def test_createTokenContract_009(contract_aide, user_prikey):
    contract_name = random_text(3)
    contract_symbol = random_text(3)
    decimals = 10
    cap = 100000000
    receipt = contract_aide.contract.createTokenContract(contract_name, contract_symbol, decimals, cap, txn={'gas': 2050000}, private_key=contract_ower_prikey)
    assert receipt.status == 1 and receipt['from'] == contract_ower
    account = Account.from_key(contract_user_prikey)
    contract_aide.set_default_account(account)
    account = Account.from_key(user_prikey)
    contract_aide.set_default_account(account)
    event_receipt = contract_aide.contract.TokenCapChanged(receipt)[0]
    print(event_receipt)
    assert event_receipt.args.symbol == contract_symbol
    assert event_receipt.args.oldCap == 0
    assert event_receipt.args.newCap == cap
    assert event_receipt.event == 'TokenCapChanged'
    assert event_receipt.address == contract_address



@allure.title("getTokenContract parameter is correct")
@pytest.mark.P0
@pytest.mark.parametrize('user_prikey', [contract_witness_prikey, contract_monitor_prikey, contract_user_prikey])
def test_getTokenContract_001(contract_aide, user_prikey):
    # 设置预置的见证人为合约见证人
    contract_aide.contract.setWitness(contract_witness)
    witness_address = to_bech32_address(contract_aide.contract.witness()[0], 'lat')
    assert witness_address == contract_witness
    # 设置预置的监控人为合约监控人
    contract_aide.contract.setMonitor(contract_monitor)
    monitor_address = to_bech32_address(contract_aide.contract.monitor(), 'lat')
    assert monitor_address == contract_monitor

    contract_name = random_text(3)
    contract_symbol = random_text(3)
    receipt = contract_aide.contract.createTokenContract(contract_name, contract_symbol, 18, 100000000, txn={'gas': 2050000}, private_key=contract_ower_prikey)
    logs_address = receipt.logs[0].address
    account = Account.from_key(user_prikey)
    contract_aide.set_default_account(account)
    token_contract = to_bech32_address(contract_aide.contract.getTokenContract(contract_symbol), 'lat')
    assert logs_address == token_contract


@allure.title("getTokenContract passed in error parameter")
@pytest.mark.P1
@pytest.mark.parametrize('symbol_bytes_lenght', [0, 4])
def test_getTokenContract_002(contract_aide, symbol_bytes_lenght):
    contract_symbol = random_text(symbol_bytes_lenght)
    assert contract_aide.contract.getTokenContract(contract_symbol) == '0x0000000000000000000000000000000000000000'


@allure.title("getTokenCap parameter is correct")
@pytest.mark.P0
@pytest.mark.parametrize('user_prikey', [contract_witness_prikey, contract_monitor_prikey, contract_user_prikey])
def test_getTokenCap_001(contract_aide, user_prikey):
    contract_symbol, cap, _ = create_token_contract(contract_aide)
    account = Account.from_key(user_prikey)
    contract_aide.set_default_account(account)
    token_cap = contract_aide.contract.getTokenCap(contract_symbol)
    assert token_cap == cap


@allure.title("getTokenCap passed in error parameter")
@pytest.mark.P1
@pytest.mark.parametrize('symbol_bytes_lenght', [0, 4])
def test_getTokenContract_002(contract_aide, symbol_bytes_lenght):
    contract_symbol = random_text(symbol_bytes_lenght)
    status = True
    try:
        token_cap = contract_aide.contract.getTokenCap(contract_symbol)
    except Exception as e:
        logger.info("exception:{}".format(e))
        status = False
    assert status == False


@allure.title("Settokencap succeeded")
@pytest.mark.P0
def test_setTokenCap_001(contract_aide):
    contract_symbol, cap, _ = create_token_contract(contract_aide)
    assert contract_aide.contract.getTokenCap(contract_symbol) == cap
    new_cap = 200000000
    receipt = contract_aide.contract.setTokenCap(contract_symbol, new_cap)
    assert receipt['from'] == contract_ower and receipt.status == 1
    assert receipt.logs[0]['address'] == contract_address
    new_token_cap = contract_aide.contract.getTokenCap(contract_symbol)
    assert new_token_cap == new_cap != cap


@allure.title("Settokencap parameter symbol verification")
@pytest.mark.P1
@pytest.mark.parametrize('symbol_bytes_lenght', [0, 4])
def test_setTokenCap_002(contract_aide, symbol_bytes_lenght):
    contract_symbol = random_text(symbol_bytes_lenght)
    new_cap = 200000000
    status = True
    try:
        receipt = contract_aide.contract.setTokenCap(contract_symbol, new_cap)
    except Exception as e:
        logger.info("exception:{}".format(e))
        status = False
    assert status == False


@allure.title("Settokencap parameter newCap verification")
@pytest.mark.P1
@pytest.mark.parametrize('new_cap', [-1, 2**256, 10.8, '100'])
def test_setTokenCap_003(contract_aide, new_cap):
    contract_symbol, _ , _= create_token_contract(contract_aide)
    status = True
    try:
        receipt = contract_aide.contract.setTokenCap(contract_symbol, new_cap)
    except Exception as e:
        logger.info("exception:{}".format(e))
        status = False
    assert status == False


@allure.title("Settokencap permission verification")
@pytest.mark.P1
@pytest.mark.parametrize('user_prikey', [contract_witness_prikey, contract_monitor_prikey, contract_user_prikey])
def test_setTokenCap_004(contract_aide, user_prikey):
    contract_symbol, _ , _= create_token_contract(contract_aide)
    new_cap = 200000000
    account = Account.from_key(user_prikey)
    contract_aide.set_default_account(account)
    status = True
    try:
        receipt = contract_aide.contract.setTokenCap(contract_symbol, new_cap)
    except Exception as e:
        logger.info("exception:{}".format(e))
        status = False
    assert status == False


@allure.title("Settokencap contract tokenchanged event verification")
@pytest.mark.P1
def test_setTokenCap_005(contract_aide):
    contract_symbol, cap, _ = create_token_contract(contract_aide)
    new_cap = 200000000
    receipt = contract_aide.contract.setTokenCap(contract_symbol, new_cap)
    event_receipt = contract_aide.contract.TokenCapChanged(receipt)[0]
    assert event_receipt.args.symbol == contract_symbol
    assert event_receipt.args.oldCap == cap
    assert event_receipt.args.newCap == new_cap
    assert event_receipt.event == 'TokenCapChanged'



@allure.title("SetTokenFee succeeded")
@pytest.mark.P0
def test_setTokenFee_001(contract_aide):
    contract_symbol, _ , _= create_token_contract(contract_aide)
    new_token_fee = 100
    token_fee = contract_aide.contract.getTokenFee(contract_symbol)
    assert token_fee == 0
    receipt = contract_aide.contract.setTokenFee(contract_symbol, new_token_fee)
    assert receipt['from'] == contract_ower and receipt.status == 1
    assert receipt.logs[0]['address'] == contract_address
    new_token = contract_aide.contract.getTokenFee(contract_symbol)
    assert new_token == new_token_fee


@allure.title("Settokenfee parameter symbol verification")
@pytest.mark.P1
@pytest.mark.parametrize('symbol_bytes_lenght', [0, 4])
def test_setTokenFee_002(contract_aide, symbol_bytes_lenght):
    contract_symbol = random_text(symbol_bytes_lenght)
    new_token_fee = 100
    token_fee = contract_aide.contract.getTokenFee(contract_symbol)
    receipt = contract_aide.contract.setTokenFee(contract_symbol, new_token_fee)
    assert receipt['from'] == contract_ower and receipt.status == 1
    assert receipt.logs[0]['address'] == contract_address
    token_fee = contract_aide.contract.getTokenFee(contract_symbol)
    assert token_fee == new_token_fee



@allure.title("Settokenfee parameter newFee verification")
@pytest.mark.P1
@pytest.mark.parametrize('new_token_fee', [-1, 2**256, 100.2, '100'])
def test_setTokenFee_003(contract_aide, new_token_fee):
    contract_symbol, _, _ = create_token_contract(contract_aide)
    token_fee = contract_aide.contract.getTokenFee(contract_symbol)
    assert token_fee == 0
    status = True
    try:
        receipt = contract_aide.contract.setTokenFee(contract_symbol, new_token_fee)
    except Exception as e:
        logger.info("exception:{}".format(e))
        status = False
    assert status == False


@allure.title("setTokenFee permission verification")
@pytest.mark.P1
@pytest.mark.parametrize('user_prikey', [contract_witness_prikey, contract_monitor_prikey, contract_user_prikey])
def test_setTokenFee_004(contract_aide, user_prikey):
    contract_symbol, _, _ = create_token_contract(contract_aide)
    token_fee = contract_aide.contract.getTokenFee(contract_symbol)
    assert token_fee == 0
    new_token_fee = 200
    status = True
    account = Account.from_key(user_prikey)
    contract_aide.set_default_account(account)
    try:
        receipt = contract_aide.contract.setTokenFee(contract_symbol, new_token_fee)
    except Exception as e:
        logger.info("exception:{}".format(e))
        status = False
    assert status == False


@allure.title("Settokenfeed contract tokenfeeset event verification")
@pytest.mark.P1
def test_setTokenFee_005(contract_aide):
    contract_symbol, _ , _= create_token_contract(contract_aide)
    new_token_fee = 100
    receipt = contract_aide.contract.setTokenFee(contract_symbol, new_token_fee)

    event_receipt = contract_aide.contract.TokenFeeSetted(receipt)[0]
    assert event_receipt.args.symbol == contract_symbol
    assert event_receipt.args.fee == new_token_fee
    assert event_receipt.event == 'TokenFeeSetted'



@allure.title("getTokenFee succeeded")
@pytest.mark.P0
@pytest.mark.parametrize('user_prikey', [contract_witness_prikey, contract_monitor_prikey, contract_user_prikey])
def test_getTokenFee_001(contract_aide, user_prikey):
    contract_symbol, _, _ = create_token_contract(contract_aide)
    token_fee = contract_aide.contract.getTokenFee(contract_symbol)
    assert token_fee == 0
    new_token_fee = 200
    receipt = contract_aide.contract.setTokenFee(contract_symbol, new_token_fee)
    account = Account.from_key(user_prikey)
    contract_aide.set_default_account(account)
    fee = contract_aide.contract.getTokenFee(contract_symbol)
    assert new_token_fee == fee


@allure.title("getTokenFe parameter symbol verification")
@pytest.mark.P1
@pytest.mark.parametrize('symbol_bytes_lenght', [0, 4])
def test_getTokenFee_002(contract_aide, symbol_bytes_lenght):
    contract_symbol = random_text(symbol_bytes_lenght)
    new_token_fee = 200
    receipt = contract_aide.contract.setTokenFee(contract_symbol, new_token_fee)
    fee = contract_aide.contract.getTokenFee(contract_symbol)
    assert new_token_fee == fee


@allure.title("getTokenFee succeeded")
@pytest.mark.P0
def test_mintToken_001(contract_aide):
    contract_symbol, cap, _ = create_token_contract(contract_aide)
    account = Account.from_key(contract_witness_prikey)
    contract_aide.set_default_account(account)
    tx_hash = '0x385c8ea0c63484ed791b6b540a1b62ce5c0abac466efa8a966def867d88a140f'
    receipt = contract_aide.contract.mintToken(tx_hash,account.address,account.address,contract_symbol,cap-1000)
    print(receipt)
    assert receipt.status == 1 and receipt['from'] == account.address == contract_witness
    tokenContractAddress = contract_aide.contract.getTokenContract(contract_symbol)
    token_info = contract_aide.contract.getTokenInfo(contract_symbol)
    assert to_bech32_address(token_info[0], 'lat') == receipt.logs[0].address


@allure.title("mintToken parameter txHash verification")
@pytest.mark.P1
@pytest.mark.parametrize('tx_hash', ['0x1616', '038a54faa49a1f71c2611f2d45e56092fa3bc63669b10741292c04b4c49dd7c8'])
def test_mintToken_002_001(contract_aide, tx_hash):
    # todo: tx_hash 好像只要是哈希就可以
    contract_symbol, cap, _ = create_token_contract(contract_aide)
    account = Account.from_key(contract_witness_prikey)
    contract_aide.set_default_account(account)
    receipt = contract_aide.contract.mintToken(tx_hash, account.address, account.address, contract_symbol, cap - 1000)
    assert receipt.status == 1 and receipt['from'] == account.address == contract_witness
    tokenContractAddress = contract_aide.contract.getTokenContract(contract_symbol)
    token_info = contract_aide.contract.getTokenInfo(contract_symbol)
    assert to_bech32_address(token_info[0], 'lat') == receipt.logs[0].address


@allure.title("mintToken parameter txHash verification")
@pytest.mark.P1
@pytest.mark.parametrize('tx_hash', [100000000, 10000000.2, -1, 'hello'])
def test_mintToken_002(contract_aide, tx_hash):
    contract_symbol, cap, _ = create_token_contract(contract_aide)
    account = Account.from_key(contract_witness_prikey)
    contract_aide.set_default_account(account)
    status = True
    try:
        receipt = contract_aide.contract.mintToken(tx_hash, account.address, account.address, contract_symbol, cap - 1000)
    except Exception as e:
        logger.info("exception:{}".format(e))
        status = False
    assert status == False


@allure.title("mintToken parameter localAddress verification")
@pytest.mark.P1
@pytest.mark.parametrize('local_address', [100000000, 10000000.2, -1, 'hello', '0x68C45AEC85A2E1683a63C4EcD64dc0Ac66792f4d'])
def test_mintToken_003(contract_aide, local_address):
    contract_symbol, cap, _ = create_token_contract(contract_aide)
    account = Account.from_key(contract_witness_prikey)
    contract_aide.set_default_account(account)
    tx_hash = '0x385c8ea0c63484ed791b6b540a1b62ce5c0abac466efa8a966def867d88a140f'
    status = True
    try:
        receipt = contract_aide.contract.mintToken(tx_hash, local_address, account.address, contract_symbol, cap - 1000)
    except Exception as e:
        logger.info("exception:{}".format(e))
        status = False
    assert status == False


@allure.title("mintToken parameter remoteAddress verification")
@pytest.mark.P1
@pytest.mark.parametrize('remote_address', [100000000, 10000000.2, -1, 'hello', '0x68C45AEC85A2E1683a63C4EcD64dc0Ac66792f4d'])
def test_mintToken_004(contract_aide, remote_address):
    contract_symbol, cap, _ = create_token_contract(contract_aide)
    account = Account.from_key(contract_witness_prikey)
    contract_aide.set_default_account(account)
    tx_hash = '0x385c8ea0c63484ed791b6b540a1b62ce5c0abac466efa8a966def867d88a140f'
    status = True
    try:
        receipt = contract_aide.contract.mintToken(tx_hash, account.address, remote_address, contract_symbol, cap - 1000)
    except Exception as e:
        logger.info("exception:{}".format(e))
        status = False
    assert status == False


@allure.title("mintToken parameter symbol verification")
@pytest.mark.P1
@pytest.mark.parametrize('symbol_bytes_lenght', [0, 4])
def test_mintToken_005(contract_aide, symbol_bytes_lenght):
    contract_symbol = random_text(symbol_bytes_lenght)
    symbol, cap, _ = create_token_contract(contract_aide)
    account = Account.from_key(contract_witness_prikey)
    contract_aide.set_default_account(account)
    tx_hash = '0x385c8ea0c63484ed791b6b540a1b62ce5c0abac466efa8a966def867d88a140f'
    status = True
    try:
        receipt = contract_aide.contract.mintToken(tx_hash, account.address, account.address, contract_symbol, cap - 1000)
    except Exception as e:
        logger.info("exception:{}".format(e))
        status = False
    assert status == False


@allure.title("mintToken parameter amount verification")
@pytest.mark.P1
@pytest.mark.parametrize('amount, expect', [(1, False), (-10000001, False), (2**256, False),
                                            (0, True), (10000000, True)])
def test_mintToken_006(contract_aide, amount, expect):
    contract_symbol, cap, _ = create_token_contract(contract_aide)
    account = Account.from_key(contract_witness_prikey)
    contract_aide.set_default_account(account)
    tx_hash = '0x385c8ea0c63484ed791b6b540a1b62ce5c0abac466efa8a966def867d88a140f'
    status = True
    cap = cap+amount
    try:
        receipt = contract_aide.contract.mintToken(tx_hash, account.address, account.address, contract_symbol, cap)
        print(receipt)
    except Exception as e:
        logger.info("exception:{}".format(e))
        status = False
    assert status == expect


@allure.title("mintToken parameter txHash verification")
@pytest.mark.P1
@pytest.mark.parametrize('user_prikey', [contract_ower_prikey, contract_monitor_prikey, contract_user_prikey])
def test_mintToken_007(contract_aide, user_prikey):
    contract_symbol, cap, _ = create_token_contract(contract_aide)
    account = Account.from_key(user_prikey)
    contract_aide.set_default_account(account)
    tx_hash = '038a54faa49a1f71c2611f2d45e56092fa3bc63669b10741292c04b4c49dd7c8'
    status = True
    try:
        receipt = contract_aide.contract.mintToken(tx_hash, account.address, account.address, contract_symbol, cap)
        print(receipt)
    except Exception as e:
        logger.info("exception:{}".format(e))
        status = False
    assert status == False


@allure.title("When the minttoken contract switch is turned off")
@pytest.mark.P1
def test_mintToken_008(contract_aide):
    contract_symbol, cap, _ = create_token_contract(contract_aide)
    result = contract_aide.contract.setSwitch(False)
    switch = contract_aide.contract.getSwitch()
    tx_hash = '038a54faa49a1f71c2611f2d45e56092fa3bc63669b10741292c04b4c49dd7c8'
    account = Account.from_key(contract_witness_prikey)
    contract_aide.set_default_account(account)
    status = True
    try:
        receipt = contract_aide.contract.mintToken(tx_hash, contract_witness, contract_witness, contract_symbol, cap)
        print(receipt)
    except Exception as e:
        logger.info("exception:{}".format(e))
        status = False
    assert status == False


@allure.title("Minttoken contract assetminated event verification")
@pytest.mark.P1
def test_mintToken_009(contract_aide):
    contract_symbol, cap, _ = create_token_contract(contract_aide)
    account = Account.from_key(contract_witness_prikey)
    contract_aide.set_default_account(account)
    tx_hash = '0x385c8ea0c63484ed791b6b540a1b62ce5c0abac466efa8a966def867d88a140f'
    receipt = contract_aide.contract.mintToken(tx_hash,account.address,account.address,contract_symbol,cap)
    assert receipt.status == 1 and receipt['from'] == account.address == contract_witness
    token_contract_address = contract_aide.contract.getTokenContract(contract_symbol)
    token_info = contract_aide.contract.getTokenInfo(contract_symbol)
    event_receipt = contract_aide.contract.AssetMinted(receipt)[0]
    assert event_receipt.args.txHash.hex() == tx_hash[2:]
    assert to_bech32_address(event_receipt.args.localAddress, 'lat') == account.address
    assert to_bech32_address(event_receipt.args.remoteAddress, 'lat') == account.address
    assert event_receipt.args.symbol == contract_symbol
    assert event_receipt.args.tokenAddress == token_contract_address == token_info[0]
    assert event_receipt.args.amount == cap




@allure.title("RedeemToken succeeded")
@pytest.mark.P0
@pytest.mark.parametrize('user_prikey', [contract_ower_prikey, contract_witness_prikey, contract_monitor_prikey, contract_user_prikey])
def test_redeemToken_001(contract_aide,user_prikey):
    contract_symbol, cap, _ = create_token_contract(contract_aide)
    contract_aide.contract.setSingleMaxCap(contract_symbol, cap-1000)
    contract_aide.contract.setTokenFee(contract_symbol, 100)
    account = Account.from_key(contract_witness_prikey)
    contract_aide.set_default_account(account)
    tx_hash = '038a54faa49a1f71c2611f2d45e56092fa3bc63669b10741292c04b4c49dd7c8'
    account_user = Account.from_key(user_prikey)
    receipt = contract_aide.contract.mintToken(tx_hash, account_user.address, account_user.address, contract_symbol, cap)
    contract_aide.set_default_account(account_user)
    receipt = contract_aide.contract.redeemToken(account.address, contract_symbol, cap - 1000000)
    assert receipt.status == 1 and receipt['from'] == account_user.address


@allure.title("redeemToken parameter symbol verification")
@pytest.mark.P1
@pytest.mark.parametrize('symbol_bytes_lenght', [0, 4])
def test_redeemToken_002(contract_aide, symbol_bytes_lenght):
    contract_symbol, cap, _ = create_token_contract(contract_aide)
    symbol = random_text(symbol_bytes_lenght)
    contract_aide.contract.setSingleMaxCap(contract_symbol, cap-1000)
    contract_aide.contract.setSingleMaxCap(contract_symbol, 0)
    contract_aide.contract.setTokenFee(contract_symbol, 100)
    account = Account.from_key(contract_witness_prikey)
    contract_aide.set_default_account(account)
    tx_hash = '038a54faa49a1f71c2611f2d45e56092fa3bc63669b10741292c04b4c49dd7c8'
    receipt = contract_aide.contract.mintToken(tx_hash, account.address, account.address, contract_symbol, cap)
    address = to_bech32_address(contract_aide.contract.getTokenContract(contract_symbol), 'lat')
    print(address)
    status = True
    try:
        receipt = contract_aide.contract.redeemToken(account.address, symbol, cap - 1000000)
        print(receipt)
    except Exception as e:
        logger.info("exception:{}".format(e))
        status = False
    assert status == False


@allure.title("redeemToken parameter remoteAddress verification")
@pytest.mark.P1
@pytest.mark.parametrize('remote_address', [100000000, 10000000.2, -1, 'hello', '0x68C45AEC85A2E1683a63C4EcD64dc0Ac66792f4d'])
def test_redeemToken_003(contract_aide, remote_address):
    contract_symbol, cap, _ = create_token_contract(contract_aide)
    contract_aide.contract.setSingleMaxCap(contract_symbol, cap-1000)
    contract_aide.contract.setTokenFee(contract_symbol, 100)
    account = Account.from_key(contract_witness_prikey)
    contract_aide.set_default_account(account)
    tx_hash = '038a54faa49a1f71c2611f2d45e56092fa3bc63669b10741292c04b4c49dd7c8'
    receipt = contract_aide.contract.mintToken(tx_hash, account.address, account.address, contract_symbol, cap)
    address = to_bech32_address(contract_aide.contract.getTokenContract(contract_symbol), 'lat')
    print(address)
    status = True
    try:
        receipt = contract_aide.contract.redeemToken(remote_address, contract_symbol, cap - 1000000)
        print(receipt)
    except Exception as e:
        logger.info("exception:{}".format(e))
        status = False
    assert status == False



@allure.title("Minttoken parameter amount > singlemaxcaps")
@pytest.mark.P1
def test_redeemToken_004(contract_aide):
    contract_symbol, cap, _ = create_token_contract(contract_aide)
    contract_aide.contract.setSingleMaxCap(contract_symbol, cap-1)
    max_cap = contract_aide.contract.getSingleMaxCap(contract_symbol)
    contract_aide.contract.setTokenFee(contract_symbol, 100)
    account = Account.from_key(contract_witness_prikey)
    contract_aide.set_default_account(account)
    tx_hash = '038a54faa49a1f71c2611f2d45e56092fa3bc63669b10741292c04b4c49dd7c8'
    receipt = contract_aide.contract.mintToken(tx_hash, account.address, account.address, contract_symbol, cap)
    status = True
    amount = cap
    try:
        receipt = contract_aide.contract.redeemToken(account.address, contract_symbol, amount)
        print(receipt)
    except Exception as e:
        logger.info("exception:{}".format(e))
        status = False
    assert status == False


@allure.title("Minttoken parameter amount < singleMinCaps")
@pytest.mark.P1
def test_redeemToken_005(contract_aide):
    contract_symbol, cap, _ = create_token_contract(contract_aide)
    contract_aide.contract.setSingleMinCap(contract_symbol, cap+1)
    contract_aide.contract.setTokenFee(contract_symbol, 100)
    account = Account.from_key(contract_witness_prikey)
    contract_aide.set_default_account(account)
    tx_hash = '038a54faa49a1f71c2611f2d45e56092fa3bc63669b10741292c04b4c49dd7c8'
    receipt = contract_aide.contract.mintToken(tx_hash, account.address, account.address, contract_symbol, cap)
    status = True
    amount = cap
    try:
        receipt = contract_aide.contract.redeemToken(account.address, contract_symbol, amount)
        print(receipt)
    except Exception as e:
        logger.info("exception:{}".format(e))
        status = False
    assert status == False


@allure.title("Minttoken parameter amount <= token_fee")
@pytest.mark.P1
@pytest.mark.parametrize('amount', [0, 1])
def test_redeemToken_006(contract_aide, amount):
    contract_symbol, cap, _ = create_token_contract(contract_aide)
    contract_aide.contract.setSingleMaxCap(contract_symbol, cap)
    token_fee = 100
    contract_aide.contract.setTokenFee(contract_symbol, token_fee)
    account = Account.from_key(contract_witness_prikey)
    contract_aide.set_default_account(account)
    tx_hash = '038a54faa49a1f71c2611f2d45e56092fa3bc63669b10741292c04b4c49dd7c8'
    receipt = contract_aide.contract.mintToken(tx_hash, account.address, account.address, contract_symbol, cap)
    status = True
    amount = token_fee -amount
    try:
        receipt = contract_aide.contract.redeemToken(account.address, contract_symbol, amount)
        print(receipt)
    except Exception as e:
        logger.info("exception:{}".format(e))
        status = False
    assert status == False


@allure.title("Minttoken parameter amount > balance(address)")
@pytest.mark.P1
@pytest.mark.parametrize('amount', [0, 1])
def test_redeemToken_007(contract_aide, amount):
    contract_symbol, cap, _ = create_token_contract(contract_aide)
    contract_aide.contract.setSingleMaxCap(contract_symbol, cap * 2)
    token_fee = 100
    contract_aide.contract.setTokenFee(contract_symbol, token_fee)
    account = Account.from_key(contract_witness_prikey)
    contract_aide.set_default_account(account)
    tx_hash = '038a54faa49a1f71c2611f2d45e56092fa3bc63669b10741292c04b4c49dd7c8'
    receipt = contract_aide.contract.mintToken(tx_hash, account.address, account.address, contract_symbol, cap)
    status = True
    amount = cap + 1
    try:
        receipt = contract_aide.contract.redeemToken(account.address, contract_symbol, amount)
        print(receipt)
    except Exception as e:
        logger.info("exception:{}".format(e))
        status = False
    assert status == False


@allure.title("Redeemtoken for nonexistent tokens")
@pytest.mark.P1
def test_redeemToken_008(contract_aide):
    symbol = random_text(4)
    cap = 100000000000
    contract_aide.contract.setSingleMaxCap(symbol, cap * 2)
    token_fee = 100
    contract_aide.contract.setTokenFee(symbol, token_fee)
    account = Account.from_key(contract_witness_prikey)
    contract_aide.set_default_account(account)
    status = True
    try:
        receipt = contract_aide.contract.redeemToken(account.address, symbol, cap-10000)
        print(receipt)
    except Exception as e:
        logger.info("exception:{}".format(e))
        status = False
    assert status == False



@allure.title("Redeemtoken contract assetreedemed event verification")
@pytest.mark.P1
@pytest.mark.parametrize('user_prikey', [contract_ower_prikey, contract_witness_prikey, contract_monitor_prikey, contract_user_prikey])
def test_redeemToken_009(contract_aide,user_prikey):
    contract_symbol, cap, _ = create_token_contract(contract_aide)
    contract_aide.contract.setSingleMaxCap(contract_symbol, cap)
    token_fee = 100
    contract_aide.contract.setTokenFee(contract_symbol, token_fee)
    account = Account.from_key(contract_witness_prikey)
    contract_aide.set_default_account(account)
    tx_hash = '038a54faa49a1f71c2611f2d45e56092fa3bc63669b10741292c04b4c49dd7c8'
    account_user = Account.from_key(user_prikey)
    receipt = contract_aide.contract.mintToken(tx_hash, account_user.address, account_user.address, contract_symbol, cap)
    contract_aide.set_default_account(account_user)
    receipt = contract_aide.contract.redeemToken(account.address, contract_symbol, cap - token_fee * 10)
    assert receipt.status == 1 and receipt['from'] == account_user.address

    event_receipt = contract_aide.contract.AssetRedeemed(receipt)[0]
    assert to_bech32_address(event_receipt.args.localAddress, 'lat') ==account_user.address
    assert to_bech32_address(event_receipt.args.remoteAddress, 'lat') == account.address
    assert event_receipt.args.symbol == contract_symbol
    assert event_receipt.args.tokenAddress == contract_aide.contract.getTokenContract(contract_symbol)
    assert event_receipt.args.amount == cap - token_fee * (10+1)
    assert event_receipt.args.fee == token_fee
    assert event_receipt.event == 'AssetRedeemed'



@allure.title("Gettokeninfo is called normally")
@pytest.mark.P0
@pytest.mark.parametrize('user_prikey', [contract_ower_prikey, contract_witness_prikey, contract_monitor_prikey, contract_user_prikey])
def test_getTokenInfo_001(contract_aide, user_prikey):
    contract_symbol, cap, contract_name = create_token_contract(contract_aide)
    account = Account.from_key(user_prikey)
    contract_aide.set_default_account(account)
    token_info = contract_aide.contract.getTokenInfo(contract_symbol)
    address = to_bech32_address(contract_aide.contract.getTokenContract(contract_symbol), 'lat')
    token_info_address = to_bech32_address(token_info[0], 'lat')
    assert address == token_info_address
    assert token_info[1] == contract_name and  token_info[2] == 18


@allure.title("Gettokeninfo parameter symbol verification")
@pytest.mark.P1
@pytest.mark.parametrize('symbol', [100000000, 10000000.2, -1, 'hello', '0x68C45AEC85A2E1683a63C4EcD64dc0Ac66792f4d'])
def test_getTokenInfo_002(contract_aide, symbol):
    status = True
    try:
        token_info = contract_aide.contract.getTokenInfo(symbol)
    except Exception as e:
        logger.info("exception:{}".format(e))
        status = False
    assert status == False


@allure.title("Gettokeninfo parameter symbol does not exist")
@pytest.mark.P1
@pytest.mark.parametrize('symbol_bytes_lenght', [0, 4])
def test_getTokenInfo_003(contract_aide, symbol_bytes_lenght):
    symbol = random_text(symbol_bytes_lenght)
    status = True
    try:
        token_info = contract_aide.contract.getTokenInfo(symbol)
    except Exception as e:
        logger.info("exception:{}".format(e))
        status = False
    assert status == False


@allure.title("Regtokencontract succeeded")
@pytest.mark.P0
def test_regTokenContract_001(contract_aide):
    # =erc20token地址,注册一次之后就不行了,如果失败就重新布合约换地址再跑
    token_contract_address = 'lat1mac9q4d9hss3yvzuevt4lgjhf6zk7dtulc3lnc'
    receipt = contract_aide.contract.regTokenContract(token_contract_address, txn={'gas': 2050000}, private_key=contract_ower_prikey)
    assert receipt.status == 1 and receipt['from'] == contract_ower and receipt.logs[0].address == contract_address
    event_receipt = contract_aide.contract.TokenCreated(receipt)[0]
    assert to_bech32_address(event_receipt.args.tokenAddress, 'lat') == to_bech32_address(contract_aide.contract.getTokenContract('ETH'), 'lat') == token_contract_address
    assert event_receipt.args.symbol == 'ETH'
    assert event_receipt.args.name == 'Platon ETH'
    assert event_receipt.args.decimals == 18
    assert event_receipt.args.cap == 9000000000000000000000000000
    assert event_receipt.event == 'TokenCreated'
    assert event_receipt.address == contract_address

    event_receipt = contract_aide.contract.TokenCapChanged(receipt)[0]
    assert event_receipt.args.symbol == 'ETH'
    assert event_receipt.args.oldCap == 0
    assert event_receipt.args.newCap == 9000000000000000000000000000
    assert event_receipt.event == 'TokenCapChanged'
    assert event_receipt.address == contract_address


@allure.title("rollBackToken succeeded")
@pytest.mark.P0
def test_rollBackToken_001(contract_aide):
    contract_symbol, cap, contract_name = create_token_contract(contract_aide)
    account = Account.from_key(contract_witness_prikey)
    contract_aide.set_default_account(account)
    receipt = contract_aide.contract.rollBackToken('0x385c8ea0c63484ed791b6b540a1b62ce5c0abac466efa8a966def867d88a140f',contract_witness,contract_symbol,cap - 1000000, 100)
    assert receipt.status == 1 and receipt['from'] == account.address == contract_witness


@allure.title("rollBackToken parameter txHash verification")
@pytest.mark.P1
@pytest.mark.parametrize('tx_hash', ['0x1616', '038a54faa49a1f71c2611f2d45e56092fa3bc63669b10741292c04b4c49dd7c8'])
def test_rollBackToken_002(contract_aide, tx_hash):
    contract_symbol, cap, contract_name = create_token_contract(contract_aide)
    account = Account.from_key(contract_witness_prikey)
    contract_aide.set_default_account(account)
    receipt = contract_aide.contract.rollBackToken(tx_hash,contract_witness,contract_symbol,cap - 1000000, 100)
    assert receipt.status == 1 and receipt['from'] == account.address == contract_witness


@allure.title("rollBackToken parameter receiveAddress verification")
@pytest.mark.P1
@pytest.mark.parametrize('receive_address', [100000000, 10000000.2, -1, 'hello', '0x68C45AEC85A2E1683a63C4EcD64dc0Ac66792f4d'])
def test_rollBackToken_003(contract_aide, receive_address):
    contract_symbol, cap, contract_name = create_token_contract(contract_aide)
    account = Account.from_key(contract_witness_prikey)
    contract_aide.set_default_account(account)
    status = True
    try:
        receipt = contract_aide.contract.rollBackToken('0x385c8ea0c63484ed791b6b540a1b62ce5c0abac466efa8a966def867d88a140f', receive_address, contract_symbol,cap - 1000000, 100)
    except Exception as e:
        logger.info("exception:{}".format(e))
        status = False
    assert status == False


@allure.title("rollBackToken parameter symbol verification")
@pytest.mark.P1
@pytest.mark.parametrize('symbol_bytes_lenght', [0, 4])
def test_rollBackToken_004(contract_aide, symbol_bytes_lenght):
    contract_symbol = random_text(symbol_bytes_lenght)
    cap = 100000000000
    account = Account.from_key(contract_witness_prikey)
    contract_aide.set_default_account(account)
    status = True
    try:
        receipt = contract_aide.contract.rollBackToken('0x385c8ea0c63484ed791b6b540a1b62ce5c0abac466efa8a966def867d88a140f', account.address, contract_symbol ,cap - 1000000, 100)
        print(receipt)
    except Exception as e:
        logger.info("exception:{}".format(e))
        status = False
    assert status == False


@allure.title("rollBackToken parameter amount verification")
@pytest.mark.P1
@pytest.mark.parametrize('amount', [99, -10000001, 100000000001, '100', 100.1, 2**256])
def test_rollBackToken_005(contract_aide, amount):
    contract_symbol, cap, contract_name = create_token_contract(contract_aide)
    account = Account.from_key(contract_witness_prikey)
    contract_aide.set_default_account(account)
    status = True
    try:
        receipt = contract_aide.contract.rollBackToken('0x385c8ea0c63484ed791b6b540a1b62ce5c0abac466efa8a966def867d88a140f', account.address, contract_symbol,cap - amount, 100)
        print(receipt)
    except Exception as e:
        logger.info("exception:{}".format(e))
        status = False
    assert status == False


@allure.title("rollBackToken parameter redeemFee verification")
@pytest.mark.P1
@pytest.mark.parametrize('redeem_fee', [-10000001, 100000000001, '100', 100.1, 2**256])
def test_rollBackToken_006(contract_aide, redeem_fee):
    contract_symbol, cap, contract_name = create_token_contract(contract_aide)
    account = Account.from_key(contract_witness_prikey)
    contract_aide.set_default_account(account)
    status = True
    try:
        receipt = contract_aide.contract.rollBackToken('0x385c8ea0c63484ed791b6b540a1b62ce5c0abac466efa8a966def867d88a140f', account.address, contract_symbol,cap - redeem_fee-2, redeem_fee)
        print(receipt)
    except Exception as e:
        logger.info("exception:{}".format(e))
        status = False
    assert status == False


@allure.title("When the rollBackToken contract switch is turned off")
@pytest.mark.P1
def test_rollBackToken_007(contract_aide):
    contract_symbol, cap, contract_name = create_token_contract(contract_aide)
    account = Account.from_key(contract_ower_prikey)
    contract_aide.set_default_account(account)
    contract_aide.contract.setSwitch(False)
    status = True
    account = Account.from_key(contract_witness_prikey)
    contract_aide.set_default_account(account)
    try:
        receipt = contract_aide.contract.rollBackToken('0x385c8ea0c63484ed791b6b540a1b62ce5c0abac466efa8a966def867d88a140f',contract_witness, contract_symbol, cap - 1000000, 100)
    except Exception as e:
        logger.info("exception:{}".format(e))
        status = False
    assert status == False
    # 环境重置
    account = Account.from_key(contract_ower_prikey)
    contract_aide.set_default_account(account)
    contract_aide.contract.setSwitch(True)


@allure.title("Rollbacktoken contract assetreeemrollback event verification")
@pytest.mark.P1
def test_rollBackToken_008(contract_aide):
    contract_symbol, cap, contract_name = create_token_contract(contract_aide)
    account = Account.from_key(contract_witness_prikey)
    contract_aide.set_default_account(account)
    tx_hash = '0x385c8ea0c63484ed791b6b540a1b62ce5c0abac466efa8a966def867d88a140f'
    redeem_fee = 100
    receipt = contract_aide.contract.rollBackToken(tx_hash,contract_witness,contract_symbol,cap - (redeem_fee*10), 100)
    assert receipt.status == 1 and receipt['from'] == account.address == contract_witness

    event_receipt = contract_aide.contract.AssetRedeemRollback(receipt)[0]
    assert to_bech32_address(event_receipt.args.receiveAddress, 'lat') == contract_witness
    assert event_receipt.args.txHash.hex() == tx_hash[2:]
    assert event_receipt.args.symbol == contract_symbol
    assert event_receipt.args.tokenAddress == contract_aide.contract.getTokenContract(contract_symbol)
    assert event_receipt.args.amount == cap - (redeem_fee*10)
    assert event_receipt.args.redeemFee == redeem_fee
    assert event_receipt.event == 'AssetRedeemRollback'


@allure.title("Allsymbollength successfully called")
@pytest.mark.P0
def test_all_symbol_length_001(contract_aide):
    all_symbol_length = contract_aide.contract.allSymbolLength()
    contract_symbol, cap, contract_name = create_token_contract(contract_aide)
    all_symbol_length_after = contract_aide.contract.allSymbolLength()
    assert all_symbol_length_after - all_symbol_length == 1


@allure.title("When there is no registration, the length of allsymbollength does not increase")
@pytest.mark.P1
def test_allSymbolLength_002(contract_aide):
    allSymbolLength = contract_aide.contract.allSymbolLength()
    token_info = contract_aide.contract.getTokenInfo('ETH')
    allSymbolLengthAfter = contract_aide.contract.allSymbolLength()
    assert allSymbolLengthAfter == allSymbolLength


@allure.title("Call isowner of base")
@pytest.mark.P0
@pytest.mark.skip(reason='框架不能传入0x地址，但是合约时用0x地址校验')
@pytest.mark.parametrize('user_prikey, expect', [
                                                # (contract_ower_prikey,True),
                                                 (contract_witness_prikey,False),
                                                 (contract_monitor_prikey,False),
                                                 (contract_user_prikey,False)
                                                 ])
def test_isOwner_001(contract_aide, user_prikey, expect):
    account = Account.from_key(user_prikey)
    contract_aide.set_default_account(account)
    result = contract_aide.contract.isOwner()
    assert result == expect


@allure.title("Call owner of base")
@pytest.mark.P0
@pytest.mark.parametrize('user_prikey', [contract_ower_prikey, contract_witness_prikey, contract_monitor_prikey, contract_user_prikey])
def test_owner_001(contract_aide, user_prikey):
    account = Account.from_key(user_prikey)
    contract_aide.set_default_account(account)
    owner = to_bech32_address(contract_aide.contract.owner(), 'lat')
    assert owner == contract_ower


@allure.title("Call isWitness of base")
@pytest.mark.P0
@pytest.mark.parametrize('user_prikey, expect', [(contract_ower_prikey,False),
                                                 # (contract_witness_prikey,True),
                                                 (contract_monitor_prikey,False),
                                                 (contract_user_prikey,False)
                                                 ])
def test_isWitness_001(contract_aide, user_prikey, expect):
    account = Account.from_key(user_prikey)
    contract_aide.set_default_account(account)
    result = contract_aide.contract.isWitness()
    assert result == expect


@allure.title("Call witness of base")
@pytest.mark.P0
@pytest.mark.parametrize('user_prikey', [contract_ower_prikey, contract_witness_prikey, contract_monitor_prikey, contract_user_prikey])
def test_witness_001(contract_aide, user_prikey):
    account = Account.from_key(user_prikey)
    contract_aide.set_default_account(account)
    witness = to_bech32_address(contract_aide.contract.witness()[0], 'lat')
    assert witness == contract_witness


@allure.title("Call isMonitor of base")
@pytest.mark.P0
@pytest.mark.parametrize('user_prikey, expect', [(contract_ower_prikey,False),
                                                 (contract_witness_prikey,False),
                                                 # (contract_monitor_prikey,True),
                                                 (contract_user_prikey,False)
                                                 ])
def test_isMonitor_001(contract_aide, user_prikey, expect):
    account = Account.from_key(user_prikey)
    contract_aide.set_default_account(account)
    result = contract_aide.contract.isMonitor()
    assert result == expect


@allure.title("Call monitor of base")
@pytest.mark.P0
@pytest.mark.parametrize('user_prikey', [contract_ower_prikey, contract_witness_prikey, contract_monitor_prikey, contract_user_prikey])
def test_monitor_001(contract_aide, user_prikey):
    account = Account.from_key(user_prikey)
    contract_aide.set_default_account(account)
    witness = to_bech32_address(contract_aide.contract.monitor(), 'lat')
    assert witness == contract_monitor



@allure.title("Call getSwitch of base")
@pytest.mark.P0
@pytest.mark.parametrize('user_prikey', [contract_ower_prikey, contract_witness_prikey, contract_monitor_prikey, contract_user_prikey])
def test_getSwitch_001(contract_aide, user_prikey):
    account = Account.from_key(user_prikey)
    contract_aide.set_default_account(account)
    switch = contract_aide.contract.getSwitch()
    assert switch == True


@allure.title("After modifying Switch, call getSwitch")
@pytest.mark.P0
@pytest.mark.parametrize('user_prikey', [contract_ower_prikey, contract_witness_prikey, contract_monitor_prikey, contract_user_prikey])
def test_Switch_001(contract_aide, user_prikey):
    account = Account.from_key(user_prikey)
    contract_aide.set_default_account(account)
    switch = contract_aide.contract.getSwitch()
    assert switch == True
    account = Account.from_key(contract_ower_prikey)
    contract_aide.set_default_account(account)
    result = contract_aide.contract.setSwitch(False)
    account = Account.from_key(user_prikey)
    contract_aide.set_default_account(account)
    switch = contract_aide.contract.getSwitch()
    assert switch == False
    # 环境重置
    account = Account.from_key(contract_ower_prikey)
    contract_aide.set_default_account(account)
    result = contract_aide.contract.setSwitch(True)


@allure.title("Transferownership call succeeded")
@pytest.mark.P0
def test_transfer_ownership_001(contract_aide):
    result = contract_aide.contract.transferOwnership(contract_user)
    assert result.status == 1 and result['from'] == contract_ower
    owner = to_bech32_address(contract_aide.contract.owner(), 'lat')
    assert owner == contract_user

    account = Account.from_key(contract_user_prikey)
    contract_aide.set_default_account(account)
    result = contract_aide.contract.transferOwnership(contract_ower)
    print(result)
    assert result.status == 1 and result['from'] == contract_user
    owner = to_bech32_address(contract_aide.contract.owner(), 'lat')
    assert owner == contract_ower


@allure.title("Transferownership call permission verification")
@pytest.mark.P0
@pytest.mark.parametrize('user_prikey', [contract_witness_prikey, contract_monitor_prikey, contract_user_prikey])
def test_transfer_ownership_002(contract_aide, user_prikey):
    account = Account.from_key(user_prikey)
    contract_aide.set_default_account(account)
    status = True
    try:
        result = contract_aide.contract.transferOwnership(contract_user)
    except Exception as e:
        logger.info("exception:{}".format(e))
        status = False
    assert status == False


@allure.title("Transferownership call succeeded")
@pytest.mark.P1
def test_transfer_ownership_003(contract_aide):
    receipt = contract_aide.contract.transferOwnership(contract_user)
    assert receipt.status == 1 and receipt['from'] == contract_ower
    owner = to_bech32_address(contract_aide.contract.owner(), 'lat')
    assert owner == contract_user

    event_receipt = contract_aide.contract.OwnershipTransferred(receipt)[0]
    assert to_bech32_address(event_receipt.args.previousOwner, 'lat') == contract_ower
    assert to_bech32_address(event_receipt.args.newOwner, 'lat') == contract_user
    assert event_receipt.event == 'OwnershipTransferred'

    # 环境重置
    account = Account.from_key(contract_user_prikey)
    contract_aide.set_default_account(account)
    result = contract_aide.contract.transferOwnership(contract_ower)
    assert result.status == 1 and result['from'] == contract_user
    owner = to_bech32_address(contract_aide.contract.owner(), 'lat')
    assert owner == contract_ower



@allure.title("Setwitness parameter address verification")
@pytest.mark.P1
@pytest.mark.parametrize('user_prikey', [contract_witness_prikey, contract_monitor_prikey, contract_user_prikey])
def test_transfer_setwitness_001(contract_aide, user_prikey):
    account = Account.from_key(user_prikey)
    contract_aide.set_default_account(account)
    status = True
    try:
        result = contract_aide.contract.setWitness(contract_user)
    except Exception as e:
        logger.info("exception:{}".format(e))
        status = False
    assert status == False


@allure.title("Setwitness parameter address verification")
@pytest.mark.P1
@pytest.mark.parametrize('address', [100000000, 10000000.2, -1, 'hello', '0x68C45AEC85A2E1683a63C4EcD64dc0Ac66792f4d'])
def test_transfer_setwitness_002(contract_aide, address):
    status = True
    try:
        result = contract_aide.contract.setWitness(address)
    except Exception as e:
        logger.info("exception:{}".format(e))
        status = False
    assert status == False



@allure.title("Setwitness contract witness changed event verification")
@pytest.mark.P1
def test_transfer_setwitness_003(contract_aide):
    create_token_contract(contract_aide)
    receipt = contract_aide.contract.setWitness(contract_user)
    event_receipt = contract_aide.contract.WitnessChanged(receipt)[0]
    assert to_bech32_address(event_receipt.args.oldWitness, 'lat') == contract_witness
    assert to_bech32_address(event_receipt.args.newWitness, 'lat') == contract_user
    assert event_receipt.event == 'WitnessChanged'


@allure.title("Setwitness succeeded")
@pytest.mark.P0
def test_transfer_setMonitor_001(contract_aide):
    result = contract_aide.contract.setMonitor(contract_user)
    print(result)

    monitor = to_bech32_address(contract_aide.contract.monitor(), 'lat')
    assert monitor == contract_user

    result = contract_aide.contract.setMonitor(contract_monitor)
    monitor = to_bech32_address(contract_aide.contract.monitor(), 'lat')
    assert monitor == contract_monitor


@allure.title("setMonitor parameter address verification")
@pytest.mark.P1
@pytest.mark.parametrize('user_prikey', [contract_witness_prikey, contract_monitor_prikey, contract_user_prikey])
def test_transfer_setMonitor_002(contract_aide, user_prikey):
    account = Account.from_key(user_prikey)
    contract_aide.set_default_account(account)
    status = True
    try:
        result = contract_aide.contract.setMonitor(contract_user)
    except Exception as e:
        logger.info("exception:{}".format(e))
        status = False
    assert status == False


@allure.title("setMonitor parameter address verification")
@pytest.mark.P1
@pytest.mark.parametrize('address', [100000000, 10000000.2, -1, 'hello', '0x68C45AEC85A2E1683a63C4EcD64dc0Ac66792f4d'])
def test_transfer_setMonitor_003(contract_aide, address):
    status = True
    try:
        result = contract_aide.contract.setMonitor(address)
    except Exception as e:
        logger.info("exception:{}".format(e))
        status = False
    assert status == False


@allure.title("Setmonitor contract monitorchanged event verification")
@pytest.mark.P0
def test_transfer_setMonitor_001(contract_aide):
    receipt = contract_aide.contract.setMonitor(contract_user)
    event_receipt = contract_aide.contract.MonitorChanged(receipt)[0]
    assert to_bech32_address(event_receipt.args.oldMonitor, 'lat') == contract_monitor
    assert to_bech32_address(event_receipt.args.newMonitor, 'lat') == contract_user
    assert event_receipt.event == 'MonitorChanged'



@allure.title("setSwitch succeeded")
@pytest.mark.P0
def test_transfer_setSwitch_001(contract_aide):
    result = contract_aide.contract.setSwitch(True)
    assert result.status == 1 and result['from'] == contract_ower
    assert result.logs == []
    switch = contract_aide.contract.getSwitch()
    assert switch == True

    result = contract_aide.contract.setSwitch(False)
    assert result.status == 1 and result['from'] == contract_ower
    assert result.logs == []
    switch = contract_aide.contract.getSwitch()
    assert switch == False
    # 环境重置
    result = contract_aide.contract.setSwitch(True)
    assert result.status == 1 and result['from'] == contract_ower
    assert result.logs == []
    switch = contract_aide.contract.getSwitch()
    assert switch == True


@allure.title("setSwitch parameter newSwitch verification")
@pytest.mark.P1
@pytest.mark.parametrize('new_switch', ['True', bool, '1', 1, 1.1])
def test_transfer_setSwitch_002(contract_aide, new_switch):
    status = True
    try:
        result = contract_aide.contract.setSwitch(new_switch)
    except Exception as e:
        logger.info("exception:{}".format(e))
        status = False
    assert status == False


@allure.title("Setwitness permission verification")
@pytest.mark.P1
@pytest.mark.parametrize('user_prikey', [contract_witness_prikey, contract_user_prikey])
def test_transfer_setSwitch_003(contract_aide, user_prikey):
    account = Account.from_key(user_prikey)
    contract_aide.set_default_account(account)
    status = True
    try:
        result = contract_aide.contract.setSwitch(True)
    except Exception as e:
        logger.info("exception:{}".format(e))
        status = False
    assert status == False


@allure.title("Setwitness permission verification")
@pytest.mark.P1
@pytest.mark.parametrize('user_prikey', [contract_ower_prikey, contract_monitor_prikey])
def test_transfer_setSwitch_004(contract_aide, user_prikey):
    account = Account.from_key(user_prikey)
    contract_aide.set_default_account(account)
    result = contract_aide.contract.setSwitch(True)
    assert result.status == 1 and result['from'] == account.address
    assert result.logs == []
