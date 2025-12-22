from datetime import time

import pytest
from loguru import logger
from platon_env.genesis import Genesis

from lib.utils import lat
from setting.setting import GENESIS_FILE


@pytest.mark.P1
@pytest.mark.parametrize('value', [2, 5, ""])
def test_init_genesis_config_maxEpochMinutes(chain, value, recover):
    """
    测试 调整创世文件maxEpochMinutes参数，初始化链
    @Desc:
        -校验maxEpochMinutes为2时，初始化链
        -校验maxEpochMinutes为8时，初始化链
        -校验maxEpochMinutes为空时，初始化链
    """

    genesis = Genesis(GENESIS_FILE)
    genesis.data['economicModel']['common']['maxEpochMinutes'] = value
    new_gen_file = GENESIS_FILE.replace(".json", "_new.json")
    genesis.save_as(new_gen_file)
    try:
        chain.install(genesis_file=new_gen_file)
    except Exception as e:
        if value == 2:
            error = 'The settlement period must be more than four times the consensus period'
            assert error in str(e)
        if value == 8:
            error = 'CheckEconomicModel configuration: The issuance period must be integer multiples of the settlement period and multiples must be greater than or equal to 4'
            assert error in str(e)
        if value == "":
            error = 'invalid genesis file: json: cannot unmarshal string into Go struct field CommonConfig.economicModel.common.maxEpochMinutes of type uint64'
            assert error in str(e)


@pytest.mark.P1
def test_init_genesis_config_maxValidators(chain, recover):
    """
    测试 调整创世文件maxValidators参数，备选验证人节点数小于验证节点数
    @Desc:
        -校验maxValidators为3时，初始化链
    """

    genesis = Genesis(GENESIS_FILE)
    genesis.data['economicModel']['staking']['maxValidators'] = 3
    new_gen_file = GENESIS_FILE.replace(".json", "_new.json")
    genesis.save_as(new_gen_file)
    try:
        chain.install(genesis_file=new_gen_file)
    except Exception as e:
        print(e)
        error = 'Invalid parameter:The MaxValidators must be [4, 10000]'
        assert error in str(e)


@pytest.mark.parametrize('value', [99999, 100000001, 0])
@pytest.mark.P1
def test_init_genesis_config_stakeThreshold(chain, value, recover):
    """
    测试 调整创世文件stakeThreshold参数，范围外的质押最低Token数
    @Desc:
        -校验maxValidators为99999时，初始化链
        -校验maxValidators为100000001时，初始化链
        -校验maxValidators为0时，初始化链
    """

    genesis = Genesis(GENESIS_FILE)
    genesis.data['economicModel']['staking']['stakeThreshold'] = lat(value)
    new_gen_file = GENESIS_FILE.replace(".json", "_new.json")
    genesis.save_as(new_gen_file)
    try:
        chain.install(genesis_file=new_gen_file)
    except Exception as e:
        print(e)
        error = 'Invalid parameter:The StakeThreshold must be [100000000000000000000000, 10000000000000000000000000] LAT'
        assert error in str(e)


@pytest.mark.parametrize('value', [0.9, 0, 10001])
@pytest.mark.P1
def test_init_genesis_config_operatingThreshold(chain, value, recover):
    """
    测试 调整创世文件operatingThreshold参数，范围外的委托最低Token数
    @Desc:
        -校验operatingThreshold为0.0时，初始化链
        -校验operatingThreshold为0时，初始化链
        -校验operatingThreshold为10001时，初始化链
    """

    genesis = Genesis(GENESIS_FILE)
    genesis.data['economicModel']['staking']['operatingThreshold'] = lat(value)
    new_gen_file = GENESIS_FILE.replace(".json", "_new.json")
    genesis.save_as(new_gen_file)
    try:
        chain.install(genesis_file=new_gen_file)
    except Exception as e:
        print(e)
        error = 'Invalid parameter:The OperatingThreshold must be [10000000000000000000, 10000000000000000000000] LAT'
        assert error in str(e)


@pytest.mark.parametrize('value', [0, 1, 337])
@pytest.mark.P1
def test_init_genesis_config_unStakeFreezeDuration(chain, value, recover):
    """
    测试 调整创世文件unStakeFreezeDuration参数，初始化链
    @Desc:
        -校验operatingThreshold为0时，初始化链
        -校验operatingThreshold为1时，初始化链
        -校验operatingThreshold为336时，初始化链
    """

    genesis = Genesis(GENESIS_FILE)
    genesis.data['economicModel']['staking']['unStakeFreezeDuration'] = value
    new_gen_file = GENESIS_FILE.replace(".json", "_new.json")
    genesis.save_as(new_gen_file)
    try:
        chain.install(genesis_file=new_gen_file)
    except Exception as e:
        print(e)
        error = 'Invalid parameter:The UnStakeFreezeDuration must be (1, 336]'
        assert error in str(e)


@pytest.mark.parametrize('value', [0, 3, 10001])
@pytest.mark.P1
def test_init_genesis_config_maxValidators(chain, value, recover):
    """
    测试 调整创世文件maxValidators参数，初始化链
    @Desc:
        -校验maxValidators为0时，初始化链
        -校验maxValidators为3时，初始化链
        -校验maxValidators为10001时，初始化链
    """

    genesis = Genesis(GENESIS_FILE)
    genesis.data['economicModel']['staking']['maxValidators'] = value
    new_gen_file = GENESIS_FILE.replace(".json", "_new.json")
    genesis.save_as(new_gen_file)
    try:
        chain.install(genesis_file=new_gen_file)
    except Exception as e:
        print(e)
        error = 'Invalid parameter:The MaxValidators must be [4, 10000]'
        assert error in str(e)


@pytest.mark.parametrize('value', [0, 10001])
@pytest.mark.P1
def test_init_genesis_config_slashFractionDuplicateSign(chain, value, recover):
    """
    测试 调整创世文件slashFractionDuplicateSign参数，初始化链
    @Desc:
        -校验slashFractionDuplicateSign为3时，初始化链
        -校验slashFractionDuplicateSign为10001时，初始化链
    """

    genesis = Genesis(GENESIS_FILE)
    genesis.data['economicModel']['slashing']['slashFractionDuplicateSign'] = value
    new_gen_file = GENESIS_FILE.replace(".json", "_new.json")
    genesis.save_as(new_gen_file)
    try:
        chain.install(genesis_file=new_gen_file)
    except Exception as e:
        print(e)
        error = 'Invalid parameter:SlashFractionDuplicateSign must be  (0, 10000]'
        assert error in str(e)


@pytest.mark.parametrize('value', [0, 2])
@pytest.mark.P1
def test_init_genesis_config_maxEvidenceAge(chain, value, recover):
    """
    测试 调整创世文件maxEvidenceAge参数，初始化链
    @Desc:
        -校验maxEvidenceAge为0时，初始化链
        -校验maxEvidenceAge为2时，初始化链
    """

    genesis = Genesis(GENESIS_FILE)
    genesis.data['economicModel']['slashing']['maxEvidenceAge'] = value
    new_gen_file = GENESIS_FILE.replace(".json", "_new.json")
    genesis.save_as(new_gen_file)
    try:
        chain.install(genesis_file=new_gen_file)
    except Exception as e:
        print(e)
        if value == 0:
            error = 'Invalid parameter:The MaxEvidenceAge must be (0, 2)'
            assert error in str(e)
        if value == 2:
            # 开发设计如此
            error = 'Invalid parameter:The UnStakeFreezeDuration must be (2, 336]'
            assert error in str(e)


@pytest.mark.parametrize('value', [0, 81])
@pytest.mark.P1
def test_init_genesis_config_duplicateSignReportReward(chain, value, recover):
    """
    测试 调整创世文件duplicateSignReportReward参数，初始化链
    @Desc:
        -校验duplicateSignReportReward为0时，初始化链
        -校验duplicateSignReportReward为81时，初始化链
    """

    genesis = Genesis(GENESIS_FILE)
    genesis.data['economicModel']['slashing']['duplicateSignReportReward'] = value
    new_gen_file = GENESIS_FILE.replace(".json", "_new.json")
    genesis.save_as(new_gen_file)
    try:
        chain.install(genesis_file=new_gen_file)
    except Exception as e:
        print(e)
        error = 'Invalid parameter:The DuplicateSignReportReward must be (0, 80]'
        assert error in str(e)


@pytest.mark.parametrize('value', [-1, 0.1, 50000])
@pytest.mark.P1
def test_init_genesis_config_slashBlocksReward(chain, value, recover):
    """
    测试 调整创世文件slashBlocksReward参数，初始化链
    @Desc:
        -校验slashBlocksReward为0时，初始化链
        -校验slashBlocksReward为5000时，初始化链
    """

    genesis = Genesis(GENESIS_FILE)
    genesis.data['economicModel']['slashing']['slashBlocksReward'] = value
    new_gen_file = GENESIS_FILE.replace(".json", "_new.json")
    genesis.save_as(new_gen_file)
    try:
        chain.install(genesis_file=new_gen_file)
    except Exception as e:
        print(e)
        if value == -1 or value == 0.1:
            error = 'field SlashingConfig.economicModel.slashing.slashBlocksReward of type uint32'
            assert error in str(e)
        if value == 50000:
            error = 'Invalid parameter:The SlashBlocksReward must be [0, 50000)'
            assert error in str(e)


@pytest.mark.parametrize('value', [0, 51])
@pytest.mark.P1
def test_init_genesis_config_zeroProduceCumulativeTime(chain, value, recover):
    """
    测试 调整创世文件zeroProduceCumulativeTime参数，初始化链
    @Desc:
        -校验zeroProduceCumulativeTime为0时，初始化链
        -校验zeroProduceCumulativeTime为51时，初始化链
    """

    genesis = Genesis(GENESIS_FILE)
    genesis.data['economicModel']['slashing']['zeroProduceCumulativeTime'] = value
    new_gen_file = GENESIS_FILE.replace(".json", "_new.json")
    genesis.save_as(new_gen_file)
    try:
        chain.install(genesis_file=new_gen_file)
    except Exception as e:
        print(e)
        error = 'Invalid parameter:The ZeroProduceCumulativeTime must be [1, 50]'
        assert error in str(e)


@pytest.mark.parametrize('value', [0, 2])
@pytest.mark.P1
def test_init_genesis_config_zeroProduceNumberThreshold(chain, value, recover):
    """
    测试 调整创世文件zeroProduceNumberThreshold参数，初始化链
    @Desc:
        -校验zeroProduceNumberThreshold为0时，初始化链
        -校验zeroProduceNumberThreshold为51时，初始化链
    """

    genesis = Genesis(GENESIS_FILE)
    genesis.data['economicModel']['slashing']['zeroProduceNumberThreshold'] = value
    new_gen_file = GENESIS_FILE.replace(".json", "_new.json")
    genesis.save_as(new_gen_file)
    try:
        chain.install(genesis_file=new_gen_file)
    except Exception as e:
        print(e)
        error = 'Invalid parameter:The ZeroProduceNumberThreshold must be [1, 1]'
        assert error in str(e)


@pytest.mark.parametrize('value', [0, 2001])
@pytest.mark.P1
def test_init_genesis_config_rewardPerMaxChangeRange(chain, value, recover):
    """
    测试 调整创世文件rewardPerMaxChangeRange参数，初始化链
    @Desc:
        -校验rewardPerMaxChangeRange为0时，初始化链
        -校验rewardPerMaxChangeRange为2001时，初始化链
    """

    genesis = Genesis(GENESIS_FILE)
    genesis.data['economicModel']['staking']['rewardPerMaxChangeRange'] = value
    new_gen_file = GENESIS_FILE.replace(".json", "_new.json")
    genesis.save_as(new_gen_file)
    try:
        chain.install(genesis_file=new_gen_file)
    except Exception as e:
        print(e)
        error = 'Invalid parameter:The RewardPerMaxChangeRange must be [1, 2000]'
        assert error in str(e)


@pytest.mark.parametrize('value', [1, 29])
@pytest.mark.P1
def test_init_genesis_config_rewardPerChangeInterval(chain, value, recover):
    """
    测试 调整创世文件rewardPerChangeInterval参数，初始化链
    @Desc:
        -校验rewardPerChangeInterval为2时，初始化链
        -校验rewardPerChangeInterval为29时，初始化链
    """

    genesis = Genesis(GENESIS_FILE)
    genesis.data['economicModel']['staking']['rewardPerChangeInterval'] = value
    new_gen_file = GENESIS_FILE.replace(".json", "_new.json")
    genesis.save_as(new_gen_file)
    try:
        chain.install(genesis_file=new_gen_file)
    except Exception as e:
        print(e)
        error = 'Invalid parameter:The RewardPerChangeInterval must be [2, 28]'
        assert error in str(e)


@pytest.mark.parametrize('value', [-1, 0.1, 2001])
@pytest.mark.P1
def test_init_genesis_config_increaseIssuanceRatio(chain, value, recover):
    """
    测试 调整创世文件increaseIssuanceRatio参数，初始化链
    @Desc:
        -校验increaseIssuanceRatio为0时，初始化链
        -校验increaseIssuanceRatio为2001时，初始化链
    """

    genesis = Genesis(GENESIS_FILE)
    genesis.data['economicModel']['reward']['increaseIssuanceRatio'] = value
    new_gen_file = GENESIS_FILE.replace(".json", "_new.json")
    genesis.save_as(new_gen_file)
    try:
        chain.install(genesis_file=new_gen_file)
    except Exception as e:
        print(e)
        if value == -1 or value == 0.1:
            error1 = 'invalid genesis file: json: cannot unmarshal number'
            error2 = 'into Go struct field RewardConfig.economicModel.reward.increaseIssuanceRatio of type uint16'
            assert error1 in str(e)
            assert error2 in str(e)
        if value == 2001:
            error = 'Invalid parameter:The IncreaseIssuanceRatio must be [0, 2000]'
            assert error in str(e)


@pytest.mark.parametrize('value', [0, 2])
@pytest.mark.P1
def test_init_genesis_config_zeroProduceFreezeDuration(chain, value, recover):
    """
    测试 调整创世文件zeroProduceFreezeDuration参数，初始化链
    @Desc:
        -校验zeroProduceFreezeDuration为0时，初始化链
        -校验zeroProduceFreezeDuration为2001时，初始化链
    """
    genesis = Genesis(GENESIS_FILE)

    genesis.data['economicModel']['slashing']['zeroProduceFreezeDuration'] = value
    new_gen_file = GENESIS_FILE.replace(".json", "_new.json")
    genesis.save_as(new_gen_file)
    try:
        chain.install(genesis_file=new_gen_file)
    except Exception as e:
        print(e)
        error = 'Invalid parameter:The ZeroProduceFreezeDuration must be [1, 1]'
        assert error in str(e)


@pytest.mark.parametrize('key', ['slashFractionDuplicateSign', 'duplicateSignReportReward', 'slashBlocksReward', 'maxEvidenceAge'])
@pytest.mark.P1
def test_init_genesis_config_slashing_invalid_argument(chain, key, recover):
    """
    测试 调整创世文件slashing模块的非法输入参数，初始化链
    @Desc:
        -校验slashFractionDuplicateSign输入空字符串‘’时，初始化链
        -校验duplicateSignReportReward输入空字符串‘’时，初始化链
        -校验slashBlocksReward输入空字符串‘’时，初始化链
        -校验maxEvidenceAge输入空字符串‘’时，初始化链
    """
    genesis = Genesis(GENESIS_FILE)
    genesis.data['economicModel']['slashing'][key] = ''
    new_gen_file = GENESIS_FILE.replace(".json", "_new.json")
    genesis.save_as(new_gen_file)
    try:
        chain.install(genesis_file=new_gen_file)
    except Exception as e:
        print(e)
        error = 'invalid genesis file: json: cannot unmarshal string into Go struct field SlashingConfig.economicModel.slashing.{} of type uint32'.format(key)
        assert error in str(e)


@pytest.mark.parametrize('value', [99, 10000001])
@pytest.mark.P1
def test_init_genesis_config_minimumRelease(chain, value, recover):
    """
    测试 调整创世文件minimumRelease参数，初始化链
    @Desc:
        -校验minimumRelease为0时，初始化链
        -校验minimumRelease为2001时，初始化链
    """

    genesis = Genesis(GENESIS_FILE)
    genesis.data['economicModel']['restricting']['minimumRelease'] = lat(value)
    new_gen_file = GENESIS_FILE.replace(".json", "_new.json")
    genesis.save_as(new_gen_file)
    try:
        chain.install(genesis_file=new_gen_file)
    except Exception as e:
        print(e)
        error = 'Invalid parameter:The MinimumRelease must be [100000000000000000000, 10000000000000000000000000]'
        assert error in str(e)


@pytest.mark.parametrize('value', [0.1, -1, 101])
@pytest.mark.P1
def test_init_genesis_config_newBlockRate(chain, value, recover):
    """
    测试 调整创世文件newBlockRate参数，初始化链
    @Desc:
        -校验newBlockRate为0.1时，初始化链
        -校验newBlockRate为-1时，初始化链
        -校验newBlockRate为101时，初始化链
    """

    genesis = Genesis(GENESIS_FILE)
    genesis.data['economicModel']['reward']['newBlockRate'] = value
    new_gen_file = GENESIS_FILE.replace(".json", "_new.json")
    genesis.save_as(new_gen_file)
    try:
        chain.install(genesis_file=new_gen_file)
    except Exception as e:
        print(e)
        if value == 0.1 or value == -1:
            error = 'field RewardConfig.economicModel.reward.newBlockRate of type uint64'
            assert error in str(e)
        if value == 101:
            error = 'The NewBlockRate must be greater than or equal to 0 and less than or equal to 100'
            assert error in str(e)


@pytest.mark.parametrize('value', [0.1, "ss", ""])
@pytest.mark.P1
def test_init_genesis_config_chainId(chain, value, recover):
    """
    测试 调整创世文件chainId参数，初始化链
    @Desc:
        -校验chainId为0.1时，初始化链
        -校验chainId为字符串时，初始化链
        -校验chainId为空字符串时，初始化链
    """

    genesis = Genesis(GENESIS_FILE)
    genesis.data['config']['chainId'] = value
    new_gen_file = GENESIS_FILE.replace(".json", "_new.json")
    genesis.save_as(new_gen_file)
    try:
        chain.install(genesis_file=new_gen_file)
    except Exception as e:
        print(e)
        error = 'Fatal: invalid genesis file: math/big: cannot unmarshal'
        assert error in str(e)




