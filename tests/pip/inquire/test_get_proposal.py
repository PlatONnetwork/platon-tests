def test_proposal_info(init_aide):
    """ 检查升级提案的信息
    """
    # 提交提案，并获取用于校验的信息
    pip_number = 'Test'
    rounds = 4
    result = init_aide.govern.version_proposal(VERSION.next_major_version(),
                                               rounds,
                                               pip_number=pip_number,
                                               )
    assert result['status'] == 1
    submit_block = result['blockNumber']
    active_block = init_aide.calculator.get_period_ends(init_aide.calculator.get_period_ends(submit_block) + rounds) + 1

    event = init_aide.govern.get_event(result)
    assert event['code'] == 0
    # 校验提案信息
    proposal = init_aide.govern.get_newest_proposal(2)
    assert proposal
    assert proposal.Proposer == init_aide.govern._node_id
    assert proposal.ProposalType == 2
    assert proposal.PIPID == pip_number
    assert proposal.SubmitBlock == submit_block
    assert proposal.EndVotingRounds == rounds
    assert proposal.EndVotingBlock == active_block - 21
    assert proposal.ActiveBlock == active_block
    assert proposal.NewVersion == VERSION.next_major_version()