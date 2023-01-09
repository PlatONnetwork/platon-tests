from lib.version import CURRENT_VERSION
from tests.pip.conftest import version_proposal, cancel_proposal, param_proposal


def test_cancel_version_proposal(init_aide):
    """ 取消升级提案
    """
    code, proposal = version_proposal(init_aide, CURRENT_VERSION.next_major_version())
    assert code == 0
    # 取消升级提案
    code, _ = cancel_proposal(init_aide, proposal.ProposalID)
    assert code == 0
    # 再次取消同一个升级提案
    code, _ = cancel_proposal(init_aide, proposal.ProposalID)
    assert code == 0


def test_cancel_param_proposal(init_aide):
    """ 取消参数提案
    """
    code, proposal = param_proposal(init_aide, "staking", "maxValidators", 6)
    assert code == 0
    # 取消参数提案
    code, _ = cancel_proposal(init_aide, proposal.ProposalID)
    assert code == 0
    # 再次取消同一个参数提案
    code, _ = cancel_proposal(init_aide, proposal.ProposalID)
    assert code == 0

