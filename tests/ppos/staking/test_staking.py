import time
from decimal import Decimal

import pytest
from loguru import logger
from platon._utils.error_code import ERROR_CODE


from platon_env.genesis import Genesis

from lib.utils import new_account, lat, get_current_year_reward
from setting.account import CDF_ACCOUNT
from setting.setting import GENESIS_FILE
from tests.ppos.conftest import create_sta_free_or_lock


@pytest.mark.P1
def test_check_init_node(init_nodes):
    """
     测试 私链启动后，验证初始验证人节点信息
    @Desc:
     -启动私链，查看验证人列表信息
     -初始验证人重复质押，验证返回code
    """
    init_aide = init_nodes[0].aide
    validator_list = init_aide.staking.get_validator_list()
    logger.info(f"validator_list: {validator_list}")

    assert 0 == len({i.StakingAddress for i in validator_list if i.StakingAddress != CDF_ACCOUNT.address})
    assert {i.node_id for i in init_nodes} == {i.NodeId for i in validator_list}
    # 003 staking_addr == CDF_ACCOUNT.address


@pytest.mark.P1
def test_check_init_node_duplicate_pledge(init_aide):
    """
     测试 私链启动后，初始验证人重复质押
    @Desc:
     -启动私链，初始验证人重复质押，验证返回code
    """
    assert init_aide.staking.create_staking(0, benefit_address=CDF_ACCOUNT.address,
                                            private_key=CDF_ACCOUNT.privateKey).message == ERROR_CODE[301101]


@pytest.mark.P1
def test_delegate_init_node(init_aide):
    """
     测试 私链启动后，委托初始验证节点
    @Desc:
     -启动私链，创建委托账号，委托初始验证人查看返回code
    """
    del_account = new_account(init_aide, lat(100))
    assert init_aide.delegate.delegate(0, private_key=del_account.privateKey).message == ERROR_CODE[301107]


@pytest.mark.P1
def test_increase_init_node(init_aide):
    """
     测试 私链启动后，增持初始验证节点
    @Desc:
     -启动私链，增持初始验证人，查看初始节点质押信息
    """
    logger.info("初始验证人质押金额：{} Von".format(init_aide.staking.staking_info.Released))
    logger.info("初始验证人增持 10000 LAT")
    assert init_aide.staking.increase_staking(0, amount=lat(10000), private_key=CDF_ACCOUNT.privateKey).message == \
           ERROR_CODE[0]
    assert init_aide.staking.staking_info.Shares == lat(160000)


@pytest.mark.P1
def test_init_node_re_pledge(init_aide):
    """
     测试 私链启动后，初始验证节点撤销后重新质押
    @Desc:
     -启动私链，初始验证人，撤销节点
     -等待节点完成退出后，从小用CDF-ACCOUNT质押
    """
    logger.info("初始节点撤销质押")
    assert init_aide.staking.withdrew_staking(private_key=CDF_ACCOUNT.privateKey).message == ERROR_CODE[0]

    init_aide.wait_period('epoch', 3)

    assert init_aide.staking.get_candidate_info().message == ERROR_CODE[301204]
    logger.info("预期初始验证人已退出 --- 重新质押节点")

    assert init_aide.staking.create_staking(private_key=CDF_ACCOUNT.privateKey).message == ERROR_CODE[0]

    logger.info("正常委托新质押节点")
    del_account = new_account(init_aide, lat(100))
    assert init_aide.delegate.delegate(0, private_key=del_account.privateKey).message == ERROR_CODE[0]


@pytest.mark.P1
def test_init_node_edit_(init_aide):
    """
     测试 私链启动后，初始验证节点修改收益地址为普通地址
    @Desc:
     -启动私链，初始验证人修改收益地址
    """
    ben_account = new_account(init_aide)

    assert init_aide.staking.edit_candidate(benifit_address=ben_account.address,
                                            private_key=CDF_ACCOUNT.privateKey).message == ERROR_CODE[0]

    # 收益地址为激励池不可以修改
    # assert init_aide.staking.staking_info.BenefitAddress == ben_account.address


@pytest.mark.P1
def test_check_normal_node_duplicate_pledge(normal_aide):
    """
     测试 私链启动后，普通验证人重复质押
    @Desc:
     -启动私链，普通验证人重复质押，验证返回code
    """
    sta_account = new_account(normal_aide, lat(150000))
    logger.info("普通节点质押")
    assert normal_aide.staking.create_staking(private_key=sta_account.privateKey).message == ERROR_CODE[0]
    logger.info("同个节点重复质押")
    assert normal_aide.staking.create_staking(private_key=sta_account.privateKey).message == ERROR_CODE[301101]


@pytest.mark.P1
def test_normal_node_abnormal_parameters_pledge(init_aide, normal_aide):
    """
     测试 私链启动后，普通节点使用非法参数进行质押
    @Desc:
     -启动私链
     -使用非法node_ID进行质押，验证返回code
     -使用已存在的版本签名进行质押，验证返回code
     -使用非法的blskey进行质押，验证返回code
    """
    illegal_nodeID = "7ee3276fd6b9c7864eb896310b5393324b6db785a2528c00cc28ca8c" \
                     "3f86fc229a86f138b1f1c8e3a942204c03faeb40e3b22ab11b8983c35dc025de42865990"

    sta_account = new_account(normal_aide, lat(150000))
    logger.info("普通节点质押")
    assert normal_aide.staking.create_staking(node_id=illegal_nodeID, private_key=sta_account.privateKey).message == \
           ERROR_CODE[301003]


@pytest.mark.P1
def test_normal_node_abnormal_bls_pubkey_pledge(init_aide, normal_aide):
    """
     测试 私链启动后，普通节点使用非法参数进行质押
    @Desc:
     -启动私链
     -使用非法的bls_pubkey进行质押，验证返回code
     -使用不完整的bls_pubkey进行质押，验证返回code
    """
    sta_account = new_account(normal_aide, lat(150000))
    logger.info("普通节点质押")

    status = True
    try:
        bls_pubkey = init_aide.admin.node_info().blsPubKey + "00000000"
        assert normal_aide.staking.create_staking(bls_pubkey=bls_pubkey,
                                                  private_key=sta_account.privateKey).message == ERROR_CODE[0]

        bls_pubkey = init_aide.admin.node_info().blsPubKey[0:10]
        assert normal_aide.staking.create_staking(bls_pubkey=bls_pubkey,
                                                  private_key=sta_account.privateKey).message == ERROR_CODE[0]
        status = False
    except Exception as e:
        logger.info("Use case success, exception information：{} ".format(str(e)))
        assert status, "ErrMsg:Transfer result {}".format(status)


@pytest.mark.P1
def test_normal_node_abnormal_version_sign_pledge(init_aide, normal_aide):
    """
     测试 私链启动后，普通节点使用非法参数进行质押
    @Desc:
     -启动私链
     -使用已存在的版本签名进行质押，验证返回code
     -使用非法的程序版本进行质押，验证返回code
    """

    sta_account = new_account(normal_aide, lat(150000))
    logger.info("普通节点质押")

    program_version_sign = init_aide.admin.get_program_version().Sign
    assert normal_aide.staking.create_staking(version_sign=program_version_sign,
                                              private_key=sta_account.privateKey).message == ERROR_CODE[301003]

    program_version = 1111
    assert normal_aide.staking.create_staking(version=program_version,
                                              private_key=sta_account.privateKey).message == ERROR_CODE[301003]


@pytest.mark.P1
def test_normal_node_duplicate_pledge(normal_aide):
    """
     测试 私链启动后，普通节点质押金额小于最低门槛
    @Desc:
     -启动私链，节点质押金额小于最低门槛，验证返回code
     - 节点质押，gas费不足
    """
    sta_account = new_account(normal_aide, lat(150000))
    logger.info("普通节点质押")
    assert normal_aide.staking.create_staking(amount=normal_aide.economic.staking_limit - lat(1),
                                              private_key=sta_account.privateKey).message == ERROR_CODE[301100]
    status = True
    try:
        normal_aide.staking.create_staking(txn={'gas': 1}, private_key=sta_account.privateKey)
        status = False
    except Exception as e:
        logger.info("Use case success, exception information：{} ".format(str(e)))
        assert status, "ErrMsg:Transfer result {}".format(status)


@pytest.mark.P1
def test_normal_node_desc_exceed_pledge(normal_aide):
    """
     测试 私链启动后，普通节点质押节点描述信息长度
    @Desc:
     -启动私链，节点质押节点描述信息长度，验证返回code
    """

    external_id = "11111111111111111111111111111111111111111111111111111111111111111111111111111111111"
    node_name = "1111111111111111111111111111111111111111111111111111111111111111111111111111111111111"
    website = "1111111111111111111111111111111111111111111111111111111111111111111111111111111111111111"
    details = "1111111111111111111111111111111111111111111111111111111111111111111111111111111111111111"

    sta_account = new_account(normal_aide, lat(150000))
    logger.info("普通节点质押")

    assert normal_aide.staking.create_staking(external_id=external_id, node_name=node_name, website=website,
                                              details=details, private_key=sta_account.privateKey).message == \
           ERROR_CODE[301002]


@pytest.mark.P2
def test_normal_node_punish_edit_candidate_info(normal_nodes):
    """
     测试 私链启动后，普通节点质押节点描述信息长度
    @Desc:
     -启动私链，节点质押节点描述信息长度，验证返回code
    """
    aide1 = normal_nodes[0].aide
    aide2 = normal_nodes[1].aide

    sta_account = new_account(aide1, lat(150000))
    new_ben_account = new_account(aide1)

    logger.info("普通节点质押")

    assert aide1.staking.create_staking(private_key=sta_account.privateKey).message == ERROR_CODE[0]

    aide1.wait_period('epoch')

    normal_nodes[0].stop()

    aide2.wait_period('consensus', 3)

    candidate_info = aide2.staking.get_candidate_info(normal_nodes[0].node_id)
    logger.info("被处罚节点信息：{}".format(candidate_info))

    assert aide2.staking.edit_candidate(node_id=normal_nodes[0].node_id, benifit_address=new_ben_account.address,
                                        private_key=sta_account.privateKey).message == ERROR_CODE[301103]


@pytest.mark.P1
def test_vary_period_re_pledge(normal_aide):
    """
     测试 私链启动后，不同时期普通节点退出重新重复质押
    @Desc:
     -启动私链，节点质押节点，犹豫期重新质押
     -启动私链，节点质押节点，犹豫期撤销质押后又重新质押
     -启动私链，节点质押节点，生效期撤销质押后又重新质押
    """
    sta_account = new_account(normal_aide, lat(150000))

    assert normal_aide.staking.create_staking(private_key=sta_account.privateKey).message == ERROR_CODE[0]
    logger.info("犹豫期重复质押")
    assert normal_aide.staking.create_staking(private_key=sta_account.privateKey).message == ERROR_CODE[301101]
    logger.info("犹豫期撤销质押后重新质押")
    assert normal_aide.staking.withdrew_staking(private_key=sta_account.privateKey).message == ERROR_CODE[0]
    assert normal_aide.staking.create_staking(private_key=sta_account.privateKey).message == ERROR_CODE[0]

    normal_aide.wait_period('epoch')
    logger.info("生效期撤销质押后重新质押")
    assert normal_aide.staking.withdrew_staking(private_key=sta_account.privateKey).message == ERROR_CODE[0]
    assert normal_aide.staking.create_staking(private_key=sta_account.privateKey).message == ERROR_CODE[301101]


@pytest.mark.parametrize('use_type', ['free', 'lock', 'mix'])
@pytest.mark.P1
def test_mix_pledge(normal_aides, use_type):
    """
     测试 私链启动后，普通节点使用混合金额质押
    @Desc:
     -启动私链，混合金额质押，仅使用锁仓进行质押
     -启动私链，混合金额质押，仅使用自由金额进行质押
    """
    if use_type == 'lock':
        sta_account = new_account(lat(1))
        plan = [{'Epoch': 1, 'Amount': lat(8330)},
                {'Epoch': 2, 'Amount': lat(8330)},
                {'Epoch': 3, 'Amount': lat(8330)},
                {'Epoch': 4, 'Amount': lat(8330)},
                {'Epoch': 5, 'Amount': lat(8330)},
                {'Epoch': 6, 'Amount': lat(8330)},
                {'Epoch': 7, 'Amount': lat(8330)},
                {'Epoch': 8, 'Amount': lat(8330)},
                {'Epoch': 9, 'Amount': lat(8330)},
                {'Epoch': 10, 'Amount': lat(8330)},
                {'Epoch': 11, 'Amount': lat(8330)},
                {'Epoch': 12, 'Amount': lat(8370)}]

        restricting_balance = normal_aides[0].platon.get_balance(normal_aides[0].restricting.contract_address)
        assert normal_aides[0].restricting.restricting(sta_account.address, plan,
                                                       private_key=sta_account.privateKey).message == ERROR_CODE[0]
        assert normal_aides[0].staking.create_staking(balance_type=2, private_key=sta_account.privateKey).message == \
               ERROR_CODE[0]
        staking_balance = normal_aides[0].platon.get_balance(normal_aides[0].staking.contract_address)
        restricting_info = normal_aides[0].restricting.get_restricting_info(sta_account.address)
        assert restricting_info['balance'] == normal_aides[0].economic.create_staking_limit
        assert restricting_info['Pledge'] == normal_aides[0].economic.create_staking_limit
        assert restricting_info['debt'] == 0
        assert normal_aides[0].staking.staking_info.RestrictingPlanHes == normal_aides[0].economic.staking_limit
        assert normal_aides[0].staking.staking_info.ReleasedHes == 0

        assert normal_aides[0].staking.withdrew_staking(private_key=sta_account.privateKey).message == ERROR_CODE[0]
        restricting_balance1 = normal_aides[0].platon.get_balance(normal_aides[0].restricting.contract_address)
        staking_balance1 = normal_aides[0].platon.get_balance(normal_aides[0].staking.contract_address)

        assert restricting_balance1 == restricting_balance + normal_aides[0].economic.staking_limit
        assert staking_balance1 == staking_balance - normal_aides[0].economic.staking_limit

    if use_type == 'free':
        sta_account = new_account(lat(150000))
        assert normal_aides[1].staking.create_staking(balance_type=2, private_key=sta_account.privateKey).message == \
               ERROR_CODE[0]
        staking_balance = normal_aides[1].platon.get_balance(normal_aides[1].staking.contract_address)

        assert normal_aides[1].staking.staking_info.ReleasedHes == normal_aides[1].economic.staking_limit
        assert normal_aides[1].staking.staking_info.RestrictingPlanHes == 0

        assert normal_aides[1].staking.withdrew_staking(private_key=sta_account.privateKey).message == ERROR_CODE[0]
        staking_balance1 = normal_aides[1].platon.get_balance(normal_aides[1].staking.contract_address)

        assert staking_balance1 == staking_balance - normal_aides[1].economic.staking_limit

    if use_type == 'mix':
        sta_account = new_account(lat(100000))
        plan = [{'Epoch': 1, 'Amount': lat(10000)},
                {'Epoch': 2, 'Amount': lat(10000)},
                {'Epoch': 3, 'Amount': lat(10000)},
                {'Epoch': 4, 'Amount': lat(10000)},
                {'Epoch': 5, 'Amount': lat(10000)}]
        restricting_balance = normal_aides[2].platon.get_balance(normal_aides[2].restricting.contract_address)
        assert normal_aides[2].restricting.restricting(sta_account.address, plan,
                                                       private_key=sta_account.privateKey).message == ERROR_CODE[0]
        assert normal_aides[2].staking.create_staking(balance_type=2, private_key=sta_account.privateKey).message == \
               ERROR_CODE[0]
        staking_balance = normal_aides[2].platon.get_balance(normal_aides[2].staking.contract_address)
        restricting_info = normal_aides[2].restricting.get_restricting_info(sta_account.address)
        assert restricting_info['balance'] == lat(50000)
        assert restricting_info['Pledge'] == lat(50000)
        assert restricting_info['debt'] == 0
        assert normal_aides[2].staking.staking_info.RestrictingPlanHes == lat(50000)
        assert normal_aides[2].staking.staking_info.ReleasedHes == lat(50000)

        assert normal_aides[2].staking.withdrew_staking(private_key=sta_account.privateKey).message == ERROR_CODE[0]
        restricting_balance1 = normal_aides[2].platon.get_balance(normal_aides[2].restricting.contract_address)
        staking_balance1 = normal_aides[2].platon.get_balance(normal_aides[2].staking.contract_address)

        assert restricting_balance1 == restricting_balance + lat(50000)
        assert staking_balance1 == staking_balance - lat(50000)


@pytest.mark.parametrize('use_type', ['free', 'lock_Insufficient', 'lock_insufficient_gas', 'mix_insufficient_gas'])
@pytest.mark.P1
def test_mix_pledge_insufficient_gas(normal_aide, use_type):
    """
     测试 私链启动后，普通节点使用混合金额质押,gas费用不足
    @Desc:
     -混合金额进行质押，金额低于最低质押门槛
     -混合金额进行质押，账户金额等于最低质押门槛
     -混合金额进行质押，锁仓与账户余额低于质押最低门槛
     -混合金额进行质押，锁仓金额等于最低质押门槛，手续费不足
     -混合金额进行质押，锁仓金额+账户余额等于最低质押门槛，手续费不足
    """

    if use_type == 'free':
        sta_account = new_account(normal_aide, lat(100000))

        logger.info("质押时低于最低门槛")
        assert normal_aide.staking.create_staking(balance_type=2, amount=normal_aide.economic.staking_limit - lat(1),
                                                  private_key=sta_account.privateKey).message == ERROR_CODE[301100]
        logger.info("账户余额等于最低质押门槛，不足gas费用")
        assert normal_aide.staking.create_staking(balance_type=2, amount=normal_aide.economic.staking_limit,
                                                  private_key=sta_account.privateKey).message == ERROR_CODE[301111]

    if use_type == 'lock_Insufficient':
        sta_account = new_account(normal_aide, lat(1))
        plan = [{'Epoch': 1, 'Amount': lat(10000)}]
        normal_aide.restricting.restricting(sta_account.address, plan, private_key=sta_account.privateKey)
        logger.info("质押时低于最低门槛")
        assert normal_aide.staking.create_staking(balance_type=2, amount=normal_aide.economic.staking_limit - lat(1),
                                                  private_key=sta_account.privateKey).message == ERROR_CODE[301100]
    if use_type == 'lock_insufficient_gas':
        sta_account = new_account(normal_aide, lat(0))
        plan = [{'Epoch': 1, 'Amount': lat(100000)}]
        normal_aide.restricting.restricting(sta_account.address, plan, private_key=sta_account.privateKey)
        logger.info("账户余额等于最低质押门槛，不足gas费用")
        status = True
        try:
            assert normal_aide.staking.create_staking(balance_type=2, amount=normal_aide.economic.staking_limit,
                                                      private_key=sta_account.privateKey).message == ERROR_CODE[0]
            status = False
        except Exception as e:
            logger.info("Use case success, exception information：{} ".format(str(e)))
            assert status, "ErrMsg:Transfer result {}".format(status)

    if use_type == 'mix_insufficient_gas':
        sta_account = new_account(normal_aide, lat(50000))
        plan = [{'Epoch': 1, 'Amount': lat(50000)}]
        normal_aide.restricting.restricting(sta_account.address, plan, private_key=sta_account.privateKey)
        logger.info("质押时低于最低门槛")
        assert normal_aide.staking.create_staking(balance_type=2, amount=normal_aide.economic.staking_limit,
                                                  private_key=sta_account.privateKey).message == ERROR_CODE[304015]


@pytest.mark.P1
def test_mix_pledge_(normal_aide):
    """
     测试 私链启动后，普通节点使用混合金额质押，再增持
    @Desc:
     -启动私链，混合金额质押，自由金额 50000、锁仓金额50000
     -增持自由/锁仓最低增持金额 10
     -跨结算周期再增持自由/锁仓最低增持金额 10 查看节点信息
     -撤销质押，查看账户和锁仓计划金额
    """
    sta_account = new_account(normal_aide, lat(100000))
    plan = [{'Epoch': 1, 'Amount': lat(10000)},
            {'Epoch': 2, 'Amount': lat(10000)},
            {'Epoch': 3, 'Amount': lat(10000)},
            {'Epoch': 4, 'Amount': lat(10000)},
            {'Epoch': 5, 'Amount': lat(10000)}]
    assert normal_aide.restricting.restricting(sta_account.address, plan,
                                               private_key=sta_account.privateKey).message == ERROR_CODE[0]
    assert normal_aide.staking.create_staking(balance_type=2, private_key=sta_account.privateKey).message == \
           ERROR_CODE[0]

    assert normal_aide.restricting.restricting(sta_account.address, plan,
                                               private_key=sta_account.privateKey).message == ERROR_CODE[0]

    assert normal_aide.staking.increase_staking(private_key=sta_account.privateKey).message == ERROR_CODE[0]
    assert normal_aide.staking.increase_staking(balance_type=1, private_key=sta_account.privateKey).message == \
           ERROR_CODE[0]

    assert normal_aide.staking.staking_info.ReleasedHes == lat(50000) + normal_aide.economic.add_staking_limit
    assert normal_aide.staking.staking_info.RestrictingPlanHes == lat(50000) + normal_aide.economic.add_staking_limit

    normal_aide.wait_period('epoch')

    assert normal_aide.staking.increase_staking(private_key=sta_account.privateKey).message == ERROR_CODE[0]
    assert normal_aide.staking.increase_staking(balance_type=1, private_key=sta_account.privateKey).message == \
           ERROR_CODE[0]

    assert normal_aide.staking.staking_info.Released == lat(50000) + normal_aide.economic.add_staking_limit
    assert normal_aide.staking.staking_info.RestrictingPlan == lat(50000) + normal_aide.economic.add_staking_limit

    assert normal_aide.staking.staking_info.Released == normal_aide.economic.add_staking_limit
    assert normal_aide.staking.staking_info.RestrictingPlan == normal_aide.economic.add_staking_limit

    staking_balance = normal_aide.platon.get_balance(normal_aide.staking.contract_address)

    assert normal_aide.staking.withdrew_staking(private_key=sta_account.privateKey).message == ERROR_CODE[0]

    staking_balance1 = normal_aide.platon.get_balance(normal_aide.staking.contract_address)
    assert staking_balance1 == staking_balance - normal_aide.economic.staking_limit + normal_aide.economic.add_staking_limit * 4
    restricting_info = normal_aide.restricting.get_restricting_info(sta_account.address)
    assert restricting_info['balance'] == lat(100000) - lat(10000)
    assert restricting_info['Pledge'] == 0


@pytest.mark.P1
def test_mix_pledge_zero_execution_block(chain, normal_nodes, recover):
    """
     测试 私链启动后，普通节点使用混合金额质押，锁仓金额不足质押金、自由金额补上-零出块处罚
    @Desc:
     -启动私链，混合金额质押，自由金额 50000、锁仓金额50000
     -增持自由/锁仓最低增持金额 10
     -跨结算周期再增持自由/锁仓最低增持金额 10
     -撤销质押，查看账户和锁仓计划金额
    """
    genesis = Genesis(GENESIS_FILE)
    genesis.data['economicModel']['slashing']['slashBlocksReward'] = 2
    new_gen_file = GENESIS_FILE.replace(".json", "_new.json")
    genesis.save_as(new_gen_file)
    chain.install(genesis_file=new_gen_file)
    time.sleep(5)

    aide1 = normal_nodes[0].aide
    aide2 = normal_nodes[1].aide
    sta_account = new_account(aide1, lat(100000))
    plan = [{'Epoch': 1, 'Amount': lat(10000)},
            {'Epoch': 2, 'Amount': lat(10000)},
            {'Epoch': 3, 'Amount': lat(10000)},
            {'Epoch': 4, 'Amount': lat(10000)},
            {'Epoch': 5, 'Amount': lat(10000)}]
    assert aide1.restricting.restricting(sta_account.address, plan).message == ERROR_CODE[0]
    assert aide1.staking.create_staking(balance_type=2, private_key=sta_account.privateKey).message == \
           ERROR_CODE[0]

    aide1.wait_period('epoch')

    block_reward, staking_reward = get_current_year_reward(aide1)

    logger.info("停止节点")
    normal_nodes[0].stop()

    aide2.wait_period('epoch')

    penalty_amount = int(Decimal(str(block_reward)) * Decimal(str(2)))
    print(penalty_amount)
