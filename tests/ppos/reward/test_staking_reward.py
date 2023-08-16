import time

import pytest

from platon._utils.error_code import ERROR_CODE

from setting.account import CDF_ACCOUNT


def test_init_node_dividend_ratio(init_aide):
    """
     测试 私链启动后初始节点修改分红比例
     @Desc:
         - 启动后初始节点修改分红比例
         - 查看节点信息分红比例字段
     """
    reward = 500
    time.sleep(2)
    init_aide.wait_period('epoch')

    assert init_aide.staking.staking_info.RewardPer == 0
    assert init_aide.staking.edit_candidate(reward_per=reward, private_key=CDF_ACCOUNT.privateKey).message == ERROR_CODE[0]

    assert init_aide.staking.get_candidate_info().RewardPer == 0
    assert init_aide.staking.get_candidate_info().NextRewardPer == 500
