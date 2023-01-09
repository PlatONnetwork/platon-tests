import time

from lib.version import current_version, next_version, next_patch_version, Version
from lib.utils import new_account, lat, is_staking_member
from tests.pip.conftest import version_proposal, param_proposal, votes, cancel_proposal

"""
检查对升级节点，未升级节点的处理
检查对选举的影响
升级后，被踢出节点的奖励
"""


class TestAllProcess:

    def test_upgrade_detail(self, aides, normal_aide, nodes):
        """ 检查升级提案从提案到投票的状态变化
        """
        # 质押一个普通节点，等待其进入验证人列表
        account = new_account(normal_aide, balance=lat(10000000))
        result = normal_aide.staking.create_staking(lat(2000000))
        normal_aide.wait_period('epoch')
        verifiers = normal_aide.staking.get_verifier_list()
        assert normal_aide.staking.staking_info in verifiers

        # 提交升级提案，并等待其
        normal_aide.govern.version_proposal()


class TestSubmitStage:
    """ 提交阶段的用例 """

    def test_submit_when_version_proposal_active(self, init_nodes, init_aides, init_aide):
        """
        1、当链上已经存在激活的升级提案时（在投票期），提交升级提案失败
        2、当该升级提案通过后，重新提交升级提案成功
        """
        code, proposal = version_proposal(init_aide, next_version.int())
        assert code == 0 and proposal

        # 提交升级提案，提案互斥
        future_version = next_version.upgrade(minor=1)
        code, _ = version_proposal(init_aide, future_version.int())
        assert code == 302012

        # 提案预生效期，再次提交升级提案，提案仍互斥（互斥的边界值）
        for node in init_nodes:
            node.upload_platon(next_version.path())
            node.restart()

        votes(proposal.ProposalID, init_aides, 1)
        init_aide.wait_block(proposal.EndVotingBlock)
        result = init_aide.govern.get_proposal_result(proposal.ProposalID)
        assert result.status == 4  # pre-active

        code, _ = version_proposal(init_aide, future_version.int())
        assert code == 302013

        # 提案生效后，再次提交升级提案，提案不再互斥（互斥的边界值）
        init_aide.wait_block(proposal.ActiveBlock)
        result = init_aide.govern.get_proposal_result(proposal.ProposalID)
        assert result.status == 5  # active
        code, _ = version_proposal(init_aide, future_version.int())
        assert code == 0

    def test_submit_after_version_proposal_failed(self, init_aide):
        """ 在升级提案失效后，重新提交升级提案，提交成功
        """
        code, proposal = version_proposal(init_aide, next_version.int(), rounds=1)
        assert code == 0 and proposal

        init_aide.wait_block(proposal.ActiveBlock)
        result = init_aide.govern.get_proposal_result(proposal.ProposalID)
        assert result.status == 3  # failed

        code, _ = version_proposal(init_aide, next_version.int())
        assert code == 0

    def test_submit_after_version_proposal_canceled(self, init_aides, init_aide):
        """ 在升级提案被取消后，重新提交升级提案，提交成功
        """
        code, proposal = version_proposal(init_aide, next_version.int())
        assert code == 0 and proposal

        code, proposal = cancel_proposal(init_aide, proposal.ProposalID, rounds=3)
        assert code == 0

        # 投票并等待取消提案生效
        votes(proposal.ProposalID, init_aides, 1)
        init_aide.wait_block(proposal.EndVotingBlock)
        result = init_aide.govern.get_proposal_result(proposal.ProposalID)
        assert result.status == 2  # passed

        code, proposal = version_proposal(init_aide, next_version.int())
        assert code == 0 and proposal

    def test_submit_when_param_proposal_active(self, init_aides, init_aide):
        """
        1、当链上已经存在激活的参数提案时（在投票期），提交升级提案失败
        2、当该升级提案通过后，重新提交升级提案成功
        """
        code, proposal = param_proposal(init_aide, "staking", "maxValidators", "6")
        assert code == 0 and proposal

        # 提交升级提案，提案互斥
        code, _ = version_proposal(init_aide, next_version.int())
        assert code == 302032

        # 提案生效后，再次提交升级提案，提案不再互斥（互斥的边界值）
        votes(proposal.ProposalID, init_aides, 1)
        init_aide.wait_block(proposal.EndVotingBlock + 1)
        result = init_aide.govern.get_proposal_result(proposal.ProposalID)
        assert result.status == 2  # passed
        code, _ = version_proposal(init_aide, next_version.int())
        assert code == 0

    def test_submit_after_param_proposal_failed(self, init_aide):
        """ 在参数提案失效后，重新提交升级提案，提交成功
        """
        code, proposal = param_proposal(init_aide, "staking", "maxValidators", "6")
        assert code == 0 and proposal

        init_aide.wait_block(proposal.EndVotingBlock + 1)
        result = init_aide.govern.get_proposal_result(proposal.ProposalID)
        assert result.status == 3  # failed

        code, _ = version_proposal(init_aide, next_version.int())
        assert code == 0

    def test_submit_after_param_proposal_canceled(self, init_aide, init_aides):
        """ 在升级提案被取消后，重新提交升级提案，提交成功
        """
        code, proposal = param_proposal(init_aide, "staking", "maxValidators", "6")
        assert code == 0 and proposal

        code, proposal = cancel_proposal(init_aide, proposal.ProposalID)
        assert code == 0

        # 投票并等待取消提案生效
        votes(proposal.ProposalID, init_aides, 1)
        init_aide.wait_block(proposal.EndVotingBlock + 1)
        result = init_aide.govern.get_proposal_result(proposal.ProposalID)
        assert result.status == 2  # active

        code, proposal = version_proposal(init_aide, next_version.int())
        assert code == 0 and proposal

    def test_proposer_is_candidate(self, normal_aide):
        """ 提案人是候选人，并通过增持变成验证人（犹豫期、生效期）
        """
        account = new_account(normal_aide, balance=lat(2100000))
        normal_aide.set_default_account(account)

        rec = normal_aide.staking.create_staking(amount=lat(1000000))
        assert rec.code == 0

        # 等待节点质押生效，变成候选人，进行提案失败
        normal_aide.wait_period('epoch', 1)
        candidates = normal_aide.staking.get_candidate_list()
        assert is_staking_member(normal_aide.staking.staking_info, candidates)

        verifiers = normal_aide.staking.get_verifier_list()
        assert is_staking_member(normal_aide.staking.staking_info, verifiers) is False

        code, _ = version_proposal(normal_aide, next_version.int())
        assert code == 0

        # 增持节点，并在犹豫期进行提案，提案失败
        normal_aide.staking.increase_staking(amount=lat(1000000))
        code, _ = version_proposal(normal_aide, next_version.int())
        assert code == 0

        # 等待增持生效，节点变成验证人，提案成功
        normal_aide.wait_period('epoch', 1)
        verifiers = normal_aide.staking.get_verifier_list()
        assert is_staking_member(normal_aide.staking.staking_info, verifiers)

        code, proposal = version_proposal(normal_aide, next_version.int())
        assert code == 0 and proposal

    def test_proposer_is_verifier(self, normal_aide):
        """ 提案人是初始验证人、新增验证人（犹豫期、生效期）
        """
        # 初始验证人场景省略（其他用例常用）
        account = new_account(normal_aide, balance=lat(2100000))
        normal_aide.set_default_account(account)

        rec = normal_aide.staking.create_staking(amount=lat(2000000), private_key=account.key)
        assert rec.code == 0

        code, _ = version_proposal(normal_aide, next_version.int())
        assert code == 0

        # 等待验证人变成生效期，再次进行提案
        normal_aide.wait_period('epoch', 1)
        verifiers = normal_aide.staking.get_verifier_list()
        assert is_staking_member(normal_aide.staking.staking_info, verifiers)

        code, proposal = version_proposal(normal_aide, next_version.int())
        assert code == 0 and proposal

    def test_proposer_is_withdrew_verifier(self, init_aide):
        # 退出中、退出后
        rec = init_aide.staking.withdrew_staking()
        assert rec.code == 0

        candidates = init_aide.staking.get_candidate_list()
        assert is_staking_member(init_aide.staking.staking_info, candidates)

        code, proposal = version_proposal(init_aide, next_version.int())
        assert code == 0 and proposal

    def test_proposer_is_double_sign_validator(self):
        # 处罚中、处罚后
        pass

    def test_proposer_is_no_block_validator(self, init_nodes):
        """ 提案人是零出块节点，被处罚冻结期中进行提案
        todo: 补充有冻结期、没冻结期、解冻后的场景，投票是否计入
        """
        opt_node = init_nodes[0]
        opt_node.stop()

        quire_node = init_nodes[1]
        quire_node.aide.wait_period('consensus', 1)
        slashes = quire_node.aide.debug.get_wait_slashing_node_list()
        assert opt_node.node_id in slashes

        opt_node.start()
        candidates = opt_node.aide.staking.get_candidate_list()
        assert is_staking_member(opt_node.aide.staking.staking_info, candidates) is False

        code, proposal = version_proposal(opt_node.aide, next_version.int())
        assert code == 0 and proposal

    def test_pip_number_used_by_version_proposal(self, init_aide, init_nodes):
        """ pip-number已被其他升级提案使用，再该提案生效前后，使用相同pip-number进行提案
        """
        pip_number = 100
        rec = init_aide.govern.version_proposal(next_version.int(), pip_number=pip_number)
        assert rec.code == 0

        # 投票并等待提案生效
        for node in init_nodes:
            node.upload_platon(next_version.path())
            node.restart()

        proposal = init_aide.govern.get_newest_proposal(2)
        votes(proposal.ProposalID, init_nodes, 1)
        init_aide.wait_block(proposal.ActiveBlock)
        result = init_aide.govern.get_proposal_result(proposal.ProposalID)
        assert result.status == 5  # active

        # 使用相同pip-number，重新提交升级提案
        rec = init_aide.govern.version_proposal(next_version.upgrade(minor=1).int(), pip_number=pip_number)
        assert rec.code == 0

    def test_pip_number_used_by_param_proposal(self, init_aide, init_nodes):
        """ pip-number已被其他参数提案使用，再该提案生效前后，使用相同pip-number进行提案
        """
        pip_number = 100
        rec = init_aide.govern.param_proposal("staking", "maxValidators", 6, pip_number=pip_number)
        assert rec.code == 0

        # 投票并等待提案生效
        for node in init_nodes:
            node.upload_platon(next_version.path())
            node.restart()

        proposal = init_aide.govern.get_newest_proposal(3)
        votes(proposal.ProposalID, init_nodes, 1)
        init_aide.wait_block(proposal.ActiveBlock)
        result = init_aide.govern.get_proposal_result(proposal.ProposalID)
        assert result.status == 5  # active

        # 使用相同提案pip-number，重新提交升级提案
        rec = init_aide.govern.version_proposal(next_version.int(), pip_number=pip_number)
        assert rec.code == 0

    def test_proposal_major_version(self, init_aide):
        """ 提案到当前大版本、上一个大版本、下一个大版本
        """
        code, _ = version_proposal(init_aide, current_version.int())
        assert code == 0

        code, _ = version_proposal(init_aide, current_version.upgrade(major=-1).int())
        assert code == 0

        # 升级到下一个大版本，子版本和补丁版本归零
        code, _ = version_proposal(init_aide, Version(major=current_version.major + 1,
                                                      minor=0,
                                                      patch=0)
                                   )
        assert code == 0

    def test_proposal_minor_version(self, init_aide):
        """ 提案到当前子版本、上一个子版本、下一个子版本
        """
        code, _ = version_proposal(init_aide, current_version.int())
        assert code == 0

        code, _ = version_proposal(init_aide, current_version.upgrade(minor=-1).int())
        assert code == 0

        # 升级到下一个版本，补丁版本归零
        code, _ = version_proposal(init_aide, Version(major=current_version.major,
                                                      minor=current_version.minor + 1,
                                                      patch=0)
                                   )
        assert code == 0

    def test_proposal_patch_version(self, init_aide):
        """ 仅更新补丁版本号，不影响共识，无需提交升级提案，提案失败
        """
        code, _ = version_proposal(init_aide, next_patch_version.int())
        assert code == 0


class TestVoteStage:

    def test_less_support_rate(self):
        pass

    def test_equal_support_rate(self):
        pass

    def test_more_support_rate(self):
        pass

    def test_cale_support_rate(self):
        pass


class TestActiveStage:

    def test_rollback_version_after_vote(self):
        pass

    def test_health_check_after_upgrade(self):
        pass
