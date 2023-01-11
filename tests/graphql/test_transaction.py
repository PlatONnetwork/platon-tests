from setting.setting import Master_account


def test_hash(normal_aide):
    address = normal_aide.platon.account.create(hrp=normal_aide.hrp).address
    transfer_result = normal_aide.transfer.transfer(address, normal_aide.economic.delegate_limit)
    transfer_hash = transfer_result['transactionHash'].hex()
    result = normal_aide.graphql.execute('{transaction(hash: "' + transfer_hash + '") {hash}}')
    hash = result.get('transaction').get('hash')
    assert transfer_hash == hash


def test_nonce(normal_aide):
    address = normal_aide.platon.account.create(hrp=normal_aide.hrp).address
    transfer_result = normal_aide.transfer.transfer(address, normal_aide.economic.delegate_limit)
    transfer_hash = transfer_result['transactionHash'].hex()
    result = normal_aide.graphql.execute('{transaction(hash: "' + transfer_hash + '") {nonce}}')
    nonce = result.get('transaction').get('nonce')
    assert nonce[:2] == '0x'


def test_index(normal_aide):
    address = normal_aide.platon.account.create(hrp=normal_aide.hrp).address
    transfer_result = normal_aide.transfer.transfer(address, normal_aide.economic.delegate_limit)
    transfer_hash = transfer_result['transactionHash'].hex()
    result = normal_aide.graphql.execute('{transaction(hash: "' + transfer_hash + '") {index}}')
    index = result.get('transaction').get('index')
    assert index == 0


def test_from(normal_aide):
    address = normal_aide.platon.account.create(hrp=normal_aide.hrp).address
    transfer_result = normal_aide.transfer.transfer(address, normal_aide.economic.delegate_limit)
    transfer_hash = transfer_result['transactionHash'].hex()
    result = normal_aide.graphql.execute('{transaction(hash: "' + transfer_hash + '") {  from(block:0){address transactionCount balance code storage(slot: "0xa98e6baea6233965a0740e20e626c5500ecf16121547e8255ee5a28a4f08fc57")}}}')
    address = result.get('transaction').get('from').get('address')
    assert address == Master_account


def test_to(normal_aide):
    # todo: 网页可以用但是这里不知道为什么报错
    address = normal_aide.platon.account.create(hrp=normal_aide.hrp).address
    transfer_result = normal_aide.transfer.transfer(address, normal_aide.economic.delegate_limit)
    transfer_hash = transfer_result['transactionHash'].hex()
    print(transfer_hash)
    result = normal_aide.graphql.execute('{transaction(hash: "' + transfer_hash + '") {to(block:100){address transactionCount balance code storage(slot: "0xa98e6baea6233965a0740e20e626c5500ecf16121547e8255ee5a28a4f08fc57")}}}')
    to_address = result.get('transaction').get('to').get('address')
    assert address == to_address


def test_value(normal_aide):
    address = normal_aide.platon.account.create(hrp=normal_aide.hrp).address
    transfer_result = normal_aide.transfer.transfer(address, normal_aide.economic.delegate_limit)
    transfer_hash = transfer_result['transactionHash'].hex()
    result = normal_aide.graphql.execute('{transaction(hash: "' + transfer_hash + '") {value}}')
    value = int(result.get('transaction').get('value')[2:], 16)
    assert value == normal_aide.economic.delegate_limit


def test_gasPrice(normal_aide):
    address = normal_aide.platon.account.create(hrp=normal_aide.hrp).address
    transfer_result = normal_aide.transfer.transfer(address, normal_aide.economic.delegate_limit)
    transfer_hash = transfer_result['transactionHash'].hex()
    result = normal_aide.graphql.execute('{transaction(hash: "' + transfer_hash + '") {gasPrice}}')
    gas_price = int(result.get('transaction').get('gasPrice')[2:], 16)
    assert gas_price == normal_aide.platon.gas_price


def test_gas(normal_aide):
    address = normal_aide.platon.account.create(hrp=normal_aide.hrp).address
    transfer_result = normal_aide.transfer.transfer(address, normal_aide.economic.delegate_limit)
    transfer_hash = transfer_result['transactionHash'].hex()
    transfer_gas = transfer_result['gasUsed']
    result = normal_aide.graphql.execute('{transaction(hash: "' + transfer_hash + '") {gas}}')
    gas = int(result.get('transaction').get('gas')[2:], 16)
    assert gas == transfer_gas


def test_inputData(normal_aide):
    address = normal_aide.platon.account.create(hrp=normal_aide.hrp).address
    transfer_result = normal_aide.transfer.transfer(address, normal_aide.economic.delegate_limit)
    transfer_hash = transfer_result['transactionHash'].hex()
    result = normal_aide.graphql.execute('{transaction(hash: "' + transfer_hash + '") {inputData}}')
    input_data = result.get('transaction').get('inputData')
    assert input_data == '0x'


def test_block(normal_aide):
    address = normal_aide.platon.account.create(hrp=normal_aide.hrp).address
    transfer_result = normal_aide.transfer.transfer(address, normal_aide.economic.delegate_limit)
    transfer_hash = transfer_result['transactionHash'].hex()
    result = normal_aide.graphql.execute('{transaction(hash: "' + transfer_hash + '") {block {transactionCount}}}')
    transaction_count = result.get('transaction').get('block').get('transactionCount')
    assert transaction_count == 1