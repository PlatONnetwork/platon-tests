"""
todo: 不能使用质押账户
"""

from platon_aide import Aide


def text_proposal(aide: Aide):
    """ 提交文本提案，并返回交易code与提案id
    """
    rec = aide.govern.text_proposal()

    proposal = ''
    if rec.code == 0:
        proposal = aide.govern.get_newest_proposal(1)
        assert proposal, 'get proposal error'

    return rec.code, proposal


def version_proposal(aide: Aide, version, rounds=4):
    """ 提交升级提案，并返回交易code与提案id
    """
    rec = aide.govern.version_proposal(version, rounds)

    proposal = ''
    if rec.code == 0:
        proposal = aide.govern.get_newest_proposal(2)
        assert proposal, 'get proposal error'

    return rec.code, proposal


def param_proposal(aide: Aide, module, name, value):
    """ 提交参数提案，并返回交易code与提案id
    """
    rec = aide.govern.param_proposal(module, name, value)

    proposal = ''
    if rec.code == 0:
        proposal = aide.govern.get_newest_proposal(3)
        assert proposal, 'get proposal error'

    return rec.code, proposal


def cancel_proposal(aide: Aide, pid, rounds):
    """ 提交取消提案，并返回交易code与提案id
    """
    rec = aide.govern.cancel_proposal(pid, rounds)

    proposal = ''
    if rec.code == 0:
        proposal = aide.govern.get_newest_proposal(4)
        assert proposal, 'get proposal error'

    return rec.code, proposal


def vote(pid, aides, options):
    """
    todo: 怎么使用质押账户进行投票
    """
    if type(options) == int:
        options = [options for _ in range(len(aides))]

    assert len(aides) == len(options)

    for aide, option in zip(aides, options):
        rec = aide.govern.vote(pid, option)
        assert rec.code == 0
