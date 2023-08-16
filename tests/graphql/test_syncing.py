def test_syncing(normal_aide):
    result = normal_aide.graphql.execute('{syncing {pulledStates knownStates startingBlock currentBlock highestBlock}}')
    syncing = result.get('syncing')
    assert syncing is None


def test_protocolVersion(normal_aide):
    result = normal_aide.graphql.execute('{protocolVersion}')
    protocol_version = result.get('protocolVersion')
    assert protocol_version == 65


def test_chainId(normal_aide):
    result = normal_aide.graphql.execute('{chainID}')
    chainid = int(result.get('chainID')[2:], 16)
    chain_chainid = normal_aide.web3.chain_id
    assert chainid == chain_chainid


def test_gasPrice(normal_aide):
    result = normal_aide.graphql.execute('{gasPrice}')
    gas_price = int(result.get('gasPrice')[2:], 16)
    chain_gas_price = normal_aide.platon.gas_price
    assert gas_price == chain_gas_price


def test_blocks(normal_aide):
    account = normal_aide.platon.account.create()
    address = account.address
    transfer_result = normal_aide.transfer.transfer(address, normal_aide.economic.delegate_limit)
    transfer_number = transfer_result['blockNumber']

    result = normal_aide.graphql.execute('{blocks(from: 0) {transactionCount ommerCount number hash nonce'
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
    blocks_list = result.get('blocks')
    for block in blocks_list:
        block_number = int(block['number'][2:], 16)
        if block_number == transfer_number:
            block['transactionCount'] == 1



def test_logs(normal_aide):
    result = normal_aide.graphql.execute('{logs (filter:{}) {index}}')
    logs = result.get('logs')
    assert logs == []
