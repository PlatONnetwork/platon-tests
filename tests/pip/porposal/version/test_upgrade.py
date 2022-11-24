from lib.utils import new_account, lat

"""
检查对升级节点，未升级节点的处理
检查对选举的影响
升级后，被踢出节点的奖励
 
"""


def test_upgrade(aides, normal_aide, nodes):
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

