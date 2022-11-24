import pytest
from loguru import logger

from lib.account import CDF_ACCOUNT
from lib.basic_data import BaseData
from lib.utils import wait_settlement
from tests.conftest import create_sta_del, create_sta_del_account


def test_operatingThreshold_upward_adjustment(normal_aide, init_aides):
    """
    测试 调整最低委托金额后赎回情况
    @Desc:
            -自由金额委托节点 1000 / 调整最低委托金额为 20
            -等待结算周期 锁仓金额委托节点 1000
            -赎回委托金额 1990 / 检查委托钱包余额
    """
    plan = [{'Epoch': 3, 'Amount': BaseData.delegate_amount}]

    sta_addr, sta_pk, del_addr, del_pk = create_sta_del_account(normal_aide, BaseData.staking_limit * 2,
                                                                BaseData.staking_limit)
    assert normal_aide.staking.create_staking(private_key=sta_pk)['code'] == 0

    assert normal_aide.delegate.delegate(amount=BaseData.delegate_amount, private_key=del_pk)['code'] == 0

    # normal_aide0_namedtuple = create_sta_del(normal_aide, plan)

    assert init_aides[0].govern.param_proposal('staking', 'operatingThreshold', str(BaseData.delegate_limit * 2),
                                               private_key=CDF_ACCOUNT.key)['code'] == 0

    proposal = init_aides[0].govern.get_active_proposal(3)

    for aide in init_aides:
        assert aide.govern.vote(proposal.ProposalID, 1, private_key=CDF_ACCOUNT.key)['code'] == 0

    normal_aide.wait_block(proposal.EndVotingBlock)

    assert normal_aide.restricting.restricting(del_addr, plan, private_key=del_pk)['code'] == 0

    assert normal_aide.delegate.delegate(amount=BaseData.delegate_amount, balance_type=1, private_key=del_pk)[
               'code'] == 0

    del_info = normal_aide.delegate.get_delegate_info(del_addr)
    logger.info(f"赎回前委托信息：{del_info}")

    del_balance = normal_aide.platon.get_balance(del_addr)
    logger.info(f"赎回前委托账户余额：{del_balance}")

    assert normal_aide.delegate.withdrew_delegate(amount=normal_aide.web3.toVon(1990, 'lat'),
                                                  staking_block_identifier=normal_aide.staking.staking_info.StakingBlockNum,
                                                  private_key=del_pk)['code'] == 0

    del_info = normal_aide.delegate.get_delegate_info(del_addr)
    logger.info(f"赎回后委托信息：{del_info}")

    del_lock_info = normal_aide.delegate.get_delegate_lock_info(del_addr)
    logger.info(f"委托锁定期信息：{del_lock_info}")

    wait_settlement(normal_aide, 1)

    del_lock_info = normal_aide.delegate.get_delegate_lock_info(del_addr)
    logger.info(f"委托锁定期信息：{del_lock_info}")

    del_balance1 = normal_aide.platon.get_balance(del_addr)
    logger.info(f"赎回回委托账户余额：{del_balance1}")

