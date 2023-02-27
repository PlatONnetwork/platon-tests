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
    rec = aide.govern.version_proposal(version, rounds, txn={"gas": 5000000})

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


def cancel_proposal(aide: Aide, pid, rounds=4):
    """ 提交取消提案，并返回交易code与提案id
    """
    rec = aide.govern.cancel_proposal(pid, rounds)

    proposal = ''
    if rec.code == 0:
        proposal = aide.govern.get_newest_proposal(4)
        assert proposal, 'get proposal error'

    return rec.code, proposal


def votes(pid, aides, options=1):
    """ 对提案进行投票，支持多个节点操作
    todo: 怎么使用质押账户进行投票（手动设置默认账户）
    """
    # 支持单个aide、单个option操作
    if type(aides) is Aide:
        aides: [Aide] = [aides]

    if type(options) == int:
        options = [options for _ in range(len(aides))]

    assert len(aides) == len(options), f'aides and options are not the same length'

    # 进行投票
    for aide, option in zip(aides, options):

        rec = aide.govern.vote(pid, option)
        assert rec.code == 0, f'{aide.uri} vote failed'


