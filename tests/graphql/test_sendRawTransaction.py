from lib.utils import wait_settlement
from tests.conftest import get_datahash
from setting.account import new_account


def test_sendRawTransaction(normal_aide):
    # transfer
    result = normal_aide.graphql.execute('mutation{sendRawTransaction(data:"0xf87080843b9aca0082520894d6c367877edc89cb53bb8893b5b641aaf21f4b698a021e19e0c9bab24000008083062298a053e3c549adf8c41563587344d56fa3561cc6810e6fc350f86fcd427b9a0a1c0aa06b6bc3f464e7f19fcc295dd828cdb39d9c3254a5f1426c92470a131e724802d4")}')
    tx_hash = result.get('sendRawTransaction')
    assert tx_hash[:2] == '0x'



def test_sendRawTransaction_staking(normal_aide):
    # create_staking
    address, prikey = new_account(normal_aide, normal_aide.economic.staking_limit * 2)
    normal_aide.set_returns(returns='txn')
    txn = normal_aide.staking.create_staking(benifit_address=address, private_key=prikey)
    data_hash = get_datahash(normal_aide, txn, privatekey=prikey)

    result = normal_aide.graphql.execute('mutation{sendRawTransaction(data:"' + data_hash + '")}')
    tx_hash = result.get('sendRawTransaction')

    receipt = normal_aide.web3.platon.wait_for_transaction_receipt(tx_hash)
    print(receipt)
    assert receipt['from'] == address
    assert receipt['status'] == 1
    assert receipt['to'] == normal_aide.web3.ppos.staking.address == receipt['logs'][0]['address']
    assert tx_hash == receipt['transactionHash'].hex() == receipt['logs'][0]['transactionHash'].hex()



def test_sendRawTransaction_increase_staking(normal_aide):
    # increase_staking
    address, prikey = new_account(normal_aide, normal_aide.economic.staking_limit * 2)
    normal_aide.staking.create_staking(benifit_address=address, private_key=prikey)
    normal_aide.set_returns(returns='txn')
    txn = normal_aide.staking.increase_staking(private_key=prikey)
    data_hash = get_datahash(normal_aide, txn, privatekey=prikey)

    result = normal_aide.graphql.execute('mutation{sendRawTransaction(data:"' + data_hash + '")}')
    tx_hash = result.get('sendRawTransaction')

    receipt = normal_aide.web3.platon.wait_for_transaction_receipt(tx_hash)
    print(receipt)
    assert receipt['from'] == address
    assert receipt['status'] == 1
    assert receipt['to'] == normal_aide.web3.ppos.staking.address == receipt['logs'][0]['address']
    assert tx_hash == receipt['transactionHash'].hex() == receipt['logs'][0]['transactionHash'].hex()


def test_sendRawTransaction_edit_staking(normal_aide):
    # edit_staking
    address, prikey = new_account(normal_aide, normal_aide.economic.staking_limit * 2)
    normal_aide.staking.create_staking(benifit_address=address, private_key=prikey)
    normal_aide.set_returns(returns='txn')
    node_name = 'hello platon'
    txn = normal_aide.staking.edit_candidate(node_name=node_name, private_key=prikey)
    data_hash = get_datahash(normal_aide, txn, privatekey=prikey)

    result = normal_aide.graphql.execute('mutation{sendRawTransaction(data:"' + data_hash + '")}')
    tx_hash = result.get('sendRawTransaction')

    receipt = normal_aide.web3.platon.wait_for_transaction_receipt(tx_hash)
    print(receipt)
    assert receipt['from'] == address
    assert receipt['status'] == 1
    assert receipt['to'] == normal_aide.web3.ppos.staking.address == receipt['logs'][0]['address']
    assert tx_hash == receipt['transactionHash'].hex() == receipt['logs'][0]['transactionHash'].hex()



def test_sendRawTransaction_withdrew_staking(normal_aide):
    # withdrew_staking
    address, prikey = new_account(normal_aide, normal_aide.economic.staking_limit * 2)
    normal_aide.staking.create_staking(benifit_address=address, private_key=prikey)
    normal_aide.set_returns(returns='txn')
    txn = normal_aide.staking.withdrew_staking(private_key=prikey)
    data_hash = get_datahash(normal_aide, txn, privatekey=prikey)

    result = normal_aide.graphql.execute('mutation{sendRawTransaction(data:"' + data_hash + '")}')
    tx_hash = result.get('sendRawTransaction')

    receipt = normal_aide.web3.platon.wait_for_transaction_receipt(tx_hash)
    print(receipt)
    assert receipt['from'] == address
    assert receipt['status'] == 1
    assert receipt['to'] == normal_aide.web3.ppos.staking.address == receipt['logs'][0]['address']
    assert tx_hash == receipt['transactionHash'].hex() == receipt['logs'][0]['transactionHash'].hex()


def test_sendRawTransaction_delegate(normal_aide):
    # delegate
    address, prikey = new_account(normal_aide, normal_aide.economic.staking_limit * 2)
    normal_aide.staking.create_staking(benifit_address=address, private_key=prikey)
    delegate_address, delegate_prikey = new_account(normal_aide, normal_aide.economic.delegate_limit * 2)
    normal_aide.set_returns(returns='txn')
    txn = normal_aide.delegate.delegate(private_key=delegate_prikey)
    data_hash = get_datahash(normal_aide, txn, privatekey=delegate_prikey)

    result = normal_aide.graphql.execute('mutation{sendRawTransaction(data:"' + data_hash + '")}')
    tx_hash = result.get('sendRawTransaction')

    receipt = normal_aide.web3.platon.wait_for_transaction_receipt(tx_hash)
    print(receipt)
    assert receipt['from'] == delegate_address
    assert receipt['status'] == 1
    assert receipt['to'] == normal_aide.web3.ppos.staking.address == receipt['logs'][0]['address']
    assert tx_hash == receipt['transactionHash'].hex() == receipt['logs'][0]['transactionHash'].hex()


def test_sendRawTransaction_withdrew_delegate(normal_aide):
    # withdrew_delegate
    address, prikey = new_account(normal_aide, normal_aide.economic.staking_limit * 2)
    normal_aide.staking.create_staking(benifit_address=address, private_key=prikey)
    delegate_address, delegate_prikey = new_account(normal_aide, normal_aide.economic.delegate_limit * 2)
    normal_aide.delegate.delegate(private_key=delegate_prikey)

    normal_aide.set_returns(returns='txn')
    txn = normal_aide.delegate.withdrew_delegate(private_key=delegate_prikey)
    data_hash = get_datahash(normal_aide, txn, privatekey=delegate_prikey)

    result = normal_aide.graphql.execute('mutation{sendRawTransaction(data:"' + data_hash + '")}')
    tx_hash = result.get('sendRawTransaction')

    receipt = normal_aide.web3.platon.wait_for_transaction_receipt(tx_hash)
    print(receipt)
    assert receipt['from'] == delegate_address
    assert receipt['status'] == 1
    assert receipt['to'] == normal_aide.web3.ppos.staking.address == receipt['logs'][0]['address']
    assert tx_hash == receipt['transactionHash'].hex() == receipt['logs'][0]['transactionHash'].hex()
    delegate_info = normal_aide.delegate.get_delegate_info(address=delegate_address)
    assert delegate_info is None


def test_sendRawTransaction_version_proposal(normal_aide):
    # version_proposal
    address, prikey = new_account(normal_aide, normal_aide.economic.staking_limit * 3)
    normal_aide.staking.create_staking(amount=normal_aide.economic.staking_limit * 2 ,benifit_address=address, private_key=prikey)
    wait_settlement(normal_aide)

    normal_aide.set_returns(returns='txn')
    txn={'gas':2100000, 'gasPrice':30000000000000}
    txn = normal_aide.govern.version_proposal(version=591617, txn=txn, private_key=prikey)
    data_hash = get_datahash(normal_aide, txn, privatekey=prikey)

    result = normal_aide.graphql.execute('mutation{sendRawTransaction(data:"' + data_hash + '")}')
    tx_hash = result.get('sendRawTransaction')

    receipt = normal_aide.web3.platon.wait_for_transaction_receipt(tx_hash)
    print(receipt)
    assert receipt['from'] == address
    assert receipt['status'] == 1
    assert receipt['to'] == normal_aide.govern.address == receipt['logs'][0]['address']
    assert tx_hash == receipt['transactionHash'].hex() == receipt['logs'][0]['transactionHash'].hex()
    proposal_list = normal_aide.govern.proposal_list()
    assert receipt['blockNumber'] == proposal_list[0]['SubmitBlock']



def test_sendRawTransaction_cancel_proposal(normal_aide):
    # version_proposal
    # todo: 返回码报错302008PIPID已存在
    address, prikey = new_account(normal_aide, normal_aide.economic.staking_limit * 3)
    normal_aide.staking.create_staking(amount=normal_aide.economic.staking_limit * 2 ,benifit_address=address, private_key=prikey)
    wait_settlement(normal_aide)
    txn = {'gas': 2100000, 'gasPrice': 30000000000000}
    normal_aide.govern.version_proposal(version=591617, voting_rounds=1, txn=txn, private_key=prikey)
    proposal_list = normal_aide.govern.proposal_list()
    print(proposal_list)
    proposal_id = proposal_list[0]['ProposalID']
    print(proposal_id)

    # normal_aide.set_returns(returns='txn')
    txn = normal_aide.govern.cancel_proposal(proposal_id=proposal_id, txn=txn, private_key=prikey)
    print(txn)
    data_hash = get_datahash(normal_aide, txn, privatekey=prikey)

    result = normal_aide.graphql.execute('mutation{sendRawTransaction(data:"' + data_hash + '")}')
    tx_hash = result.get('sendRawTransaction')

    receipt = normal_aide.web3.platon.wait_for_transaction_receipt(tx_hash)
    print(receipt)
    assert receipt['from'] == address
    assert receipt['status'] == 1
    assert receipt['to'] == normal_aide.govern.address == receipt['logs'][0]['address']
    assert tx_hash == receipt['transactionHash'].hex() == receipt['logs'][0]['transactionHash'].hex()
    proposal_list = normal_aide.govern.proposal_list()
    print(proposal_list)
    # assert receipt['blockNumber'] == proposal_list[0]['SubmitBlock']


def test_sendRawTransaction_declare_proposal(normal_aide):
    # version_proposal
    address, prikey = new_account(normal_aide, normal_aide.economic.staking_limit * 3)
    normal_aide.staking.create_staking(amount=normal_aide.economic.staking_limit * 2 ,benifit_address=address, private_key=prikey)
    # wait_settlement(normal_aide)

    normal_aide.set_returns(returns='txn')
    txn={'gas':2100000, 'gasPrice':30000000000000}
    txn = normal_aide.govern.declare_version(private_key=prikey)
    data_hash = get_datahash(normal_aide, txn, privatekey=prikey)

    result = normal_aide.graphql.execute('mutation{sendRawTransaction(data:"' + data_hash + '")}')
    tx_hash = result.get('sendRawTransaction')

    receipt = normal_aide.web3.platon.wait_for_transaction_receipt(tx_hash)
    print(receipt)
    assert receipt['from'] == address
    assert receipt['status'] == 1
    assert receipt['to'] == normal_aide.govern.address == receipt['logs'][0]['address']
    assert tx_hash == receipt['transactionHash'].hex() == receipt['logs'][0]['transactionHash'].hex()



def test_sendRawTransaction_restricting(normal_aide):
    # restricting
    address, prikey = new_account(normal_aide, normal_aide.economic.staking_limit * 3)