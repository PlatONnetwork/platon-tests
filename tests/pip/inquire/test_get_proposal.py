from lib.version import next_major_version


def test_proposal_info(init_aide):
    """ 检查升级提案的信息
    """
    # 提交提案，并获取用于校验的信息
    pip_number = 'Test'
    rounds = 4
    print(next_major_version.int())
    init_aide.set_result_type('receipt')
    result = init_aide.govern.version_proposal(next_major_version.int(), rounds, pip_number=pip_number)
    print(result)
    assert result['status'] == 1
    submit_block = result['blockNumber']
    period, _, _ = init_aide.calculator.get_period_info(submit_block, 'consensus')
    active_block = (period + rounds) * init_aide.economic.consensus_blocks + 1
    print(active_block)

    event = init_aide.decode_data(result)
    assert event['code'] == 0
    # 校验提案信息
    proposal = init_aide.govern.get_newest_proposal(2)
    assert proposal
    assert proposal.Proposer == init_aide.node_id
    assert proposal.ProposalType == 2
    assert proposal.PIPID == pip_number
    assert proposal.SubmitBlock == submit_block
    assert proposal.EndVotingRounds == rounds
    assert proposal.EndVotingBlock == active_block - 21
    assert proposal.ActiveBlock == active_block
    assert proposal.NewVersion == next_major_version.int()
