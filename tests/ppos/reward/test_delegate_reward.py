from typing import List

from loguru import logger
from platon_aide.economic import Economic

from lib import utils
from lib.funcs import wait_settlement
from tests.conftest import generate_account


def create_restricting_plan(aide):
    address, prikey = generate_account(aide, aide.delegate._economic.staking_limit * 10)
    restrict_address, restrict_prikey = generate_account(aide, aide.delegate._economic.staking_limit)
    plan = [
        {'Epoch': 5, 'Amount': aide.web3.toVon(1000, 'lat')}
    ]
    result = aide.restricting.restricting(release_address=restrict_address,
                                          plans=plan, private_key=prikey)
    assert result['code'] == 0  # TODO 旧框架这里验证 code == 0
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


def withdraw_reward_assert_delegate_info(restrict_address, assert_aide_list, ):
    for aide in assert_aide_list:
        delegate_info = aide.delegate.get_delegate_info(address=restrict_address,
                                                        node_id=aide.node.node_id,
                                                        staking_block_identifier=aide.staking.staking_info.StakingBlockNum)
        logger.info(f'assert delegate_info : {delegate_info}')
        assert delegate_info.DelegateEpoch == 3
        assert delegate_info.CumulativeIncome == 0


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
    balance_settlement_2 = normal_aide1.platon.get_balance(restrict_address)
    logger.info(f"balance_settlement_2 :{balance_settlement_2}")
    # 链上全质押奖励 与 单出块奖励
    chain_staking_reward, chain_block_reward = normal_aide1.calculator.get_reward_info()
    logger.info(f'链上奖励: chain_staking_reward:{chain_staking_reward}, chain_block_reward:{chain_block_reward}')
    verifier_count = normal_aide1.calculator.get_verifier_count()
    wait_settlement(normal_aide1)

    logger.info(f"Current block height :{normal_aide1.platon.block_number}")
    # block_num = normal_aide1.calculator.get_blocks_from_miner(start=160, end=320, node_id=normal_aide1.node.node_id)
    block_num1 = utils.get_block_count_number(normal_aide1, roundnum=5)
    logger.info(f"normal_aide1 block_num : {block_num1}")

    block_num2 = utils.get_block_count_number(normal_aide1, roundnum=5)
    logger.info(f"normal_aide2 block_num : {block_num2}")

    # 节点奖励信息
    # max_validators = normal_aide1.staking._economic.maxValidators
    # node_staking_reward = normal_aide1.calculator.calc_staking_reward(chain_staking_reward, 5)
    # logger.info(f'节点奖励: node_staking_reward: {node_staking_reward}, node_block_reward: {chain_block_reward}')

    node1_reward = normal_aide1.calculator.calc_delegate_reward(chain_staking_reward, verifier_count,
                                                                chain_block_reward, block_num1,
                                                                normal_aide1.staking.staking_info.RewardPer)
    logger.info(f'node1_reward: {node1_reward}')

    node2_reward = normal_aide1.calculator.calc_delegate_reward(chain_staking_reward, verifier_count,
                                                                chain_block_reward, block_num2,
                                                                normal_aide2.staking.staking_info.RewardPer)
    logger.info(f'node2_reward: {node2_reward}')




    # 计算提取奖励 gas_fee
    gas_fee = utils.withdraw_delegate_reward_gas_fee(normal_aide1, staking_num=2, uncalcwheels=2)
    logger.info(f'gas_fee: {gas_fee}')
    # 提取委托奖励， 对于地址而言会将所有奖励全部提取
    assert normal_aide1.delegate.withdraw_delegate_reward(private_key=restrict_prikey)['code'] == 0
    # 提取奖励后验证委托信息
    withdraw_reward_assert_delegate_info(restrict_address, assert_aide_list=[normal_aide1, normal_aide2])
    balance_settlement_3 = normal_aide1.transfer.get_balance(restrict_address)
    logger.info(f"balance_settlement_3 :{balance_settlement_3}")

    assert balance_settlement_2 + node1_reward + node2_reward - gas_fee == balance_settlement_3

    # 再次提取奖励
    gas_fee = utils.withdraw_delegate_reward_gas_fee(normal_aide1, staking_num=2, uncalcwheels=0)
    assert normal_aide1.delegate.withdraw_delegate_reward(private_key=restrict_prikey).get('code') == 0
    balance_settlement_3_2 = normal_aide1.transfer.get_balance(restrict_address)

    assert balance_settlement_3 - gas_fee == balance_settlement_3_2
