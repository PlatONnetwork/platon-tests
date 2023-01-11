
def test_number(normal_aide):
    result = normal_aide.graphql.execute('{block(number: 1) {number}}')
    number = result.get('block').get('number')[2:]
    block_number = normal_aide.platon.get_block(1).number
    assert int(number) == 0 == block_number


def test_hash(normal_aide):
    result = normal_aide.graphql.execute('{block(number: 1) {hash}}')
    hash = result.get('block').get('hash')
    block_hash = normal_aide.platon.get_block(1).hash
    assert block_hash.hex() == hash


def test_parent(normal_aide):
    result = normal_aide.graphql.execute('{block(number: 1) {parent {hash}}}')
    hash = result.get('block').get('parent').get('hash')
    block_hash = normal_aide.platon.get_block(1).parentHash
    assert block_hash.hex() == hash


def test_nonce(normal_aide):
    result = normal_aide.graphql.execute('{block(number: 1) {nonce}}')
    nonce = result.get('block').get('nonce')
    block_nonce = normal_aide.platon.get_block(1).nonce
    assert block_nonce.hex() == nonce



def test_transactionsRoot(normal_aide):
    result = normal_aide.graphql.execute('{block(number: 1) {transactionsRoot}}')
    transactions_root = result.get('block').get('transactionsRoot')
    block_transactions_root = normal_aide.platon.get_block(1).transactionsRoot
    assert block_transactions_root.hex() == transactions_root


def test_transactionCount(normal_aide):
    address = normal_aide.platon.account.create(hrp=normal_aide.hrp).address
    result = normal_aide.transfer.transfer(address, normal_aide.economic.delegate_limit)
    number = result.blockNumber
    print(number)
    result = normal_aide.graphql.execute('{block(number: 1) {transactionCount}}')
    block_transactions_count = result.get('block').get('transactionCount')
    assert block_transactions_count == 0


def test_stateRoot(normal_aide):
    result = normal_aide.graphql.execute('{block(number: 1) {stateRoot}}')
    stat_root = result.get('block').get('stateRoot')
    block_state_root = normal_aide.platon.get_block(1).stateRoot
    assert block_state_root.hex() == stat_root


def test_receiptsRoot(normal_aide):
    result = normal_aide.graphql.execute('{block(number: 1) {receiptsRoot}}')
    receipts_root = result.get('block').get('receiptsRoot')
    block_receipts_root = normal_aide.platon.get_block(1).receiptsRoot
    assert block_receipts_root.hex() == receipts_root


def test_miner(normal_aide):
    result = normal_aide.graphql.execute('{block(number: 1) {miner {address code balance transactionCount}}}')
    miner_address = result.get('block').get('miner').get('address')
    miner_balance = int(result.get('block').get('miner').get('balance')[2:])
    block_miner = normal_aide.platon.get_block(1).miner
    address_balance = normal_aide.platon.get_balance(miner_address)
    assert miner_address == block_miner
    assert miner_balance == address_balance


def test_extraData(normal_aide):
    result = normal_aide.graphql.execute('{block(number: 1) {extraData}}')
    extra_data = result.get('block').get('extraData')
    block_proofOfAuthorityData = normal_aide.platon.get_block(1).proofOfAuthorityData
    assert block_proofOfAuthorityData.hex() == extra_data


def test_gasLimit(normal_aide):
    result = normal_aide.graphql.execute('{block(number: 1) {gasLimit}}')
    gas_limit = int(result.get('block').get('gasLimit')[2:], 16)
    block_gas_limit = normal_aide.platon.get_block(1).gasLimit
    assert gas_limit == block_gas_limit



def test_gasUsed(normal_aide):
    result = normal_aide.graphql.execute('{block(number: 1) {gasUsed}}')
    gas_used = int(result.get('block').get('gasUsed')[2:], 16)
    block_gas_used = normal_aide.platon.get_block(1).gasUsed
    assert gas_used == block_gas_used


def test_timestamp(normal_aide):
    result = normal_aide.graphql.execute('{block(number: 1) {timestamp}}')
    timestamp = int(result.get('block').get('timestamp')[2:], 16)
    block_timestamp = normal_aide.platon.get_block(1).timestamp
    assert timestamp == block_timestamp


def test_logsBloom(normal_aide):
    result = normal_aide.graphql.execute('{block(number: 1) {logsBloom}}')
    logs_bloom = result.get('block').get('logsBloom')
    block_logs_bloom = normal_aide.platon.get_block(1).logsBloom
    assert logs_bloom == block_logs_bloom.hex()


def test_mixHash(normal_aide):
    result = normal_aide.graphql.execute('{block(number: 1) {mixHash}}')
    mix_hash = result.get('block').get('mixHash')
    assert mix_hash[:2] == '0x'


def test_difficulty(normal_aide):
    result = normal_aide.graphql.execute('{block(number: 1) {difficulty}}')
    logs_bloom = int(result.get('block').get('difficulty')[2:], 16)
    assert logs_bloom == 0


def test_TotalDifficulty(normal_aide):
    result = normal_aide.graphql.execute('{block(number: 1) {totalDifficulty}}')
    logs_bloom = result.get('block').get('totalDifficulty')
    block_logs_bloom = normal_aide.platon.get_block(1).totalDifficulty
    assert logs_bloom == block_logs_bloom


def test_ommerCount(normal_aide):
    result = normal_aide.graphql.execute('{block(number: 1) {ommerCount}}')
    ommer_count = result.get('block').get('ommerCount')
    assert ommer_count is None


def test_ommers(normal_aide):
    result = normal_aide.graphql.execute('{block(number: 1) {ommers {transactionCount ommerCount}}}')
    ommers = result.get('block').get('ommers')
    assert ommers is None


def test_ommerAt(normal_aide):
    # todo: 要填参数不知道填什么
    result = normal_aide.graphql.execute('{block(number: 1) {ommerAt(index: 0) {transactionCount ommerCount}}}')
    print(result)


def test_ommerHash(normal_aide):
    result = normal_aide.graphql.execute('{block(number: 1) {ommerHash}}')
    ommer_hash = result.get('block').get('ommerHash')
    assert ommer_hash[:2] == '0x'


def test_transactions(normal_aide):
    result = normal_aide.graphql.execute('{block(number: 1) {transactions {index status gasUsed cumulativeGasUsed}}}')
    transactions = result.get('block').get('transactions')
    block_transactions = normal_aide.platon.get_block(1).transactions
    assert transactions == block_transactions


def test_transactionAt(normal_aide):
    result = normal_aide.graphql.execute('{block(number: 1) {transactionAt (index:0){index status gasUsed cumulativeGasUsed}}}')
    transactionAt = result.get('block').get('transactionAt')
    assert transactionAt is None


def test_logs(normal_aide):
    result = normal_aide.graphql.execute('{block(number: 1) {logs (filter:{}) {index}}}')
    logs = result.get('block').get('logs')
    assert logs == []



def test_account(normal_aide):
    result = normal_aide.graphql.execute('{block(number: 1) {account(address: atp1zkrxx6rf358jcvr7nruhyvr9hxpwv9uncjmns0) {address balance transactionCount code storage(slot: "0xa98e6baea6233965a0740e20e626c5500ecf16121547e8255ee5a28a4f08fc57")}}}')
    account_address = result.get('block').get('account').get('address')
    assert account_address == 'atp1zkrxx6rf358jcvr7nruhyvr9hxpwv9uncjmns0'


def test_call(normal_aide):
    result = normal_aide.graphql.execute('{block(number: 1) {call(data: {from:atp1zkrxx6rf358jcvr7nruhyvr9hxpwv9uncjmns0 to:atp1x3r5qyx6mzn98h6kvp0r9r4zkq89c9qedjmxew gas:21000 gasPrice:1000000000 value:0 data: "0x"}){data gasUsed status}}}')
    status = int(result.get('block').get('call').get('status')[2:])
    assert status == 1


def test_estimateGas(normal_aide):
    result = normal_aide.graphql.execute('{block(number: 1) {estimateGas(data: {from:atp1zkrxx6rf358jcvr7nruhyvr9hxpwv9uncjmns0 to:atp1x3r5qyx6mzn98h6kvp0r9r4zkq89c9qedjmxew gas:21000 gasPrice:1000000000 value:0 data: "0x"})}}')
    estimate_gas = int(result.get('block').get('estimateGas')[2:], 16)
    assert estimate_gas == 21000



def test_block(normal_aide):
    account = normal_aide.platon.account.create(hrp=normal_aide.hrp)
    address = account.address
    transfer_result = normal_aide.transfer.transfer(address, normal_aide.economic.delegate_limit)
    transfer_number = str(transfer_result['blockNumber'])

    result = normal_aide.graphql.execute('{block(number: ' + transfer_number + ') {transactionCount ommerCount number hash nonce'
                                         ' parent {hash}'
                                         ' transactionsRoot'
                                         ' stateRoot'
                                         ' receiptsRoot'
                                         ' miner {address code balance transactionCount}'
                                         ' extraData'
                                         ' gasLimit'
                                         ' gasUsed'
                                         ' timestamp'
                                         ' logsBloom'
                                         ' mixHash'
                                         ' difficulty'
                                         ' totalDifficulty'
                                         ' ommerCount'
                                         ' ommers {transactionCount ommerCount}'
                                         ' ommerAt(index: 0) {transactionCount ommerCount}'
                                         ' ommerHash'
                                         ' transactions {index status gasUsed cumulativeGasUsed}'
                                         ' transactionAt (index:0){index status gasUsed cumulativeGasUsed}'
                                         ' logs (filter:{}) {index}'
                                         ' account(address: atp1zkrxx6rf358jcvr7nruhyvr9hxpwv9uncjmns0) {address balance transactionCount code storage(slot: "0xa98e6baea6233965a0740e20e626c5500ecf16121547e8255ee5a28a4f08fc57")}'
                                         ' call(data: {from:atp1zkrxx6rf358jcvr7nruhyvr9hxpwv9uncjmns0 to:atp1x3r5qyx6mzn98h6kvp0r9r4zkq89c9qedjmxew gas:21000 gasPrice:1000000000 value:0 data: "0x"}){data gasUsed status}'
                                         ' estimateGas(data: {from:atp1zkrxx6rf358jcvr7nruhyvr9hxpwv9uncjmns0 to:atp1x3r5qyx6mzn98h6kvp0r9r4zkq89c9qedjmxew gas:21000 gasPrice:1000000000 value:0 data: "0x"})'
                                         '}'
                                         '}')

    miner_address = result.get('block').get('miner').get('address')
    transfer_address = result.get('block').get('account').get('address')
    address = normal_aide.web3.to_bech32_address('0x1000000000000000000000000000000000000003', normal_aide.hrp)
    master_address = normal_aide.web3.to_bech32_address('0x15866368698d0f2c307e98f9723065b982e61793', normal_aide.hrp)
    assert miner_address == address
    assert transfer_address == master_address