from typing import List

from loguru import logger

from lib.funcs import wait_settlement
from tests.conftest import generate_account


def create_restricting_plan(aide):
    address, prikey = generate_account(aide, aide.delegate._economic.staking_limit * 10)
    restrict_address, restrict_prikey = generate_account(aide, aide.delegate._economic.staking_limit)
    plan = [
        {'Epoch': 5, 'Amount': aide.web3.toVon(1000, 'lat')}
    ]
    result = aide.transfer.restricting(release_address=restrict_address,
                                       plans=plan, private_key=prikey)
    assert  result.status == 1
    return restrict_address, restrict_prikey


def nodes_staking_update_reward_per(aides: List, amount: List, reward_per: List):
    if not aides:
        return "Please pass staking node information"

    for item in range(len(reward_per)):
        aide, rew_per = aides[item], reward_per[item]

        address, prikey = generate_account(aide, aide.delegate._economic.staking_limit * 10)
        res = aide.staking.create_staking(amount=amount[item], benefit_address=address, private_key=prikey,
                                          reward_per=rew_per)
        assert res['code'] == 0
        logger.info(f"staking_node: {aide.node.node_id}, amount: {amount[item]},  reward_per: {rew_per}")


def one_to_nodes_delegate(req_aide, delegate_aides: List, private_key, amount: List):
    for item in range(len(delegate_aides)):
        result = req_aide.delegate.delegate(private_key=private_key, amount=amount[item],
                                            node_id=delegate_aides[item].node.node_id, )
        assert result['code'] == 0
        logger.info(f"delegate successfully, amount: {amount[item]}")


def test_EI_BC_083(normal_aides):
    normal_aide1, normal_aide2 = normal_aides[0], normal_aides[1]
    restrict_address, restrict_prikey = create_restricting_plan(normal_aide1)

    staking_limit = normal_aide1.delegate._economic.staking_limit
    delegate_limit = normal_aide1.delegate._economic.delegate_limit

    nodes_staking_update_reward_per(aides=[normal_aide1, normal_aide2], amount=[staking_limit * 2, staking_limit * 2],
                                    reward_per=[1000, 2000])
    one_to_nodes_delegate(req_aide=normal_aide1, delegate_aides=[normal_aide1, normal_aide2],
                          private_key=restrict_prikey, amount=[delegate_limit * 10, delegate_limit * 10])
    wait_settlement(normal_aide1)
    logger.info(f"Current block height :{normal_aide1.platon.block_number}")
    # 链上奖励
    set_2_staking_reward, set_2_block_reward = normal_aide1.calculator.get_rewards_from_epoch()
    logger.info(f'链上奖励: set_2_staking_reward:{set_2_staking_reward}, set_2_block_reward:{set_2_block_reward}')

    set_2_balance = normal_aide1.transfer.get_balance(restrict_address)
    logger.info(f"settlement_2 :{set_2_balance}")

    wait_settlement(normal_aide1)
    logger.info(f"Current block height :{normal_aide1.platon.block_number}")
    # 上个周期出了多少个块
    block_num = normal_aide1.calculator.get_blocks_from_miner(start=160, end=320, node_id=normal_aide1.node.node_id)
    logger.info(f"normal_aide1 block_num : {block_num}")
    # 节点奖励信息
    staking_reward, block_reward = normal_aide1.calculator.calc_staking_reward(set_2_staking_reward, set_2_block_reward,
                                                                               5, block_num)
    logger.info(f'节点奖励: staking_reward: {staking_reward}, block_reward: {block_reward}')

    normal_aide1.calculator.calc_delegate_reward(staking_reward + block_reward,
                                                 1000,
                                                 delegate_limit * 2,
                                                 delegate_limit * 2)

    block_num = normal_aide2.calculator.get_blocks_from_miner(start=160, end=320, node_id=normal_aide2.node.node_id)
    staking_reward, block_reward = normal_aide2.calculator.calc_staking_reward(set_2_staking_reward, set_2_block_reward,
                                                                               5, block_num)
    normal_aide2.calculator.calc_delegate_reward(staking_reward + block_reward,
                                                 2000,
                                                 delegate_limit * 2,
                                                 delegate_limit * 2)

    res = normal_aide1.delegate.withdrew_delegate(restrict_address)
    assert res['code'] == 0

    # 查委托信息
    # normal_aide1.delegate.get_delegate_reward()
    delegate_info_1 = normal_aide1.delegate.get_delegate_info(address=restrict_address,
                                                              node_id=normal_aide1.node.node_id,
                                                              staking_block_identifier=normal_aide1.staking.staking_info.StakingBlockNum)

    logger.info(f'delegate_info_1 : {delegate_info_1}')

    delegate_info_2 = normal_aide2.delegate.get_delegate_info(address=restrict_address,
                                                              node_id=normal_aide2.node.node_id,
                                                              staking_block_identifier=normal_aide2.staking.staking_info.StakingBlockNum)
    logger.info(f'delegate_info_2 : {delegate_info_2}')


    pass
