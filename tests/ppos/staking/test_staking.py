import pytest
from loguru import logger
from platon._utils.error_code import ERROR_CODE

from lib.account import CDF_ACCOUNT
from tests.conftest import generate_account


@pytest.mark.P1
def test_IV_001_002_003_010(init_aides):
    """
    001:Verify the validity of human parameters
    002:The built-in account is found with the verifier list query
    003:Verify the validity of human parameters
    010:The initial number of nodes is consistent with the number of verifier consensus nodes set
    """
    validator_list = init_aides[0].staking.get_validator_list()
    logger.info(f"validator_list: {validator_list}")

    assert 0 == len({i.StakingAddress for i in validator_list if i.StakingAddress != CDF_ACCOUNT.address})
    assert {i.node.node_id for i in init_aides} == {i.NodeId for i in validator_list}
    # 003 staking_addr == CDF_ACCOUNT.address
    assert init_aides[0].staking.create_staking(0, benefit_address=CDF_ACCOUNT.address,
                                                private_key=CDF_ACCOUNT.privateKey).message == ERROR_CODE[301101]


@pytest.mark.P1
def test_IV_004(init_aide):
    """004:The initial verifier accepts the delegate"""
    del_addr, del_pk = generate_account(init_aide, init_aide.web3.toVon(1, "lat"))
    assert init_aide.delegate.delegate(0, private_key=del_pk).message == ERROR_CODE[301107]


@pytest.mark.P1
def test_IV_005(init_aide):
    """The initial verifier holds an additional pledge"""
    res = init_aide.staking.increase_staking(0, private_key=CDF_ACCOUNT.privateKey)
    logger.info(f"{res}")
    assert res.code == 0
