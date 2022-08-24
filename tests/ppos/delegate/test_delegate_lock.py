"""
@Author  :  Jw
@Contact :  libai7236@gmail.com
@Time    :  2022/8/23 11:38
@Version :  platon-1.3.0
@Desc    :  委托锁定
"""
from loguru import logger

from lib.funcs import wait_settlement
from tests.conftest import generate_account


class DelegateLock(object):
    staking_limit = 0
    delegate_limit = 0

    # 用例常用金额 / cls.delegate_limit * 100
    delegate_amount = 0

    nodes_account_info = list()

    # 构造账户初始金额 获取动态添加的数据/ cls.staking_limit * 10
    init_sta_amt = 0
    init_del_amt = 0

    def init_sta_del(self, aides):
        """
        构造数据
            - 获取常用变量信息:staking/delegate limit
            - 创建质押和委托账户
        """
        self.get_var_info(aides[0])
        self.create_sta_del_account(aides, sta_amt=self.init_sta_amt, del_amt=self.init_del_amt)

    @classmethod
    def get_var_info(cls, aide):
        """获取常用变量信息"""
        DelegateLock.staking_limit = aide.delegate._economic.staking_limit
        DelegateLock.delegate_limit = aide.delegate._economic.delegate_limit

        DelegateLock.delegate_amount = cls.delegate_limit * 100

        DelegateLock.init_sta_amt = cls.staking_limit * 10
        DelegateLock.init_del_amt = cls.staking_limit * 10

    def create_sta_del_account(self, aides: list, sta_amt, del_amt):
        """
        创建质押和委托账户
        @param aides:
        @param sta_amt: 账户中质押金额
        @param del_amt: 账户中委托金额
        """
        node_account = dict()
        for aide in aides:
            node_account["sta_addr"], node_account["sta_pk"] = generate_account(aide, sta_amt)
            node_account["del_addr"], node_account["del_pk"] = generate_account(aide, del_amt)
            self.nodes_account_info.append(node_account)

    def create_sta_del(self, aide, ben_addr, sta_pk, sta_amt, del_pk, del_amt, del_type, **kwargs):
        """

        @param aide:
        @param ben_addr: 质押收益地址
        @param sta_pk: 质押private_key
        @param sta_amt: 质押金额
        @param del_pk: 委托pk
        @param del_amt: 委托金额
        @param del_type: 委托类型
        @param kwargs: #TODO: 应对其他场景传kw进来解析
        @return: StakingBlockNum
        """
        assert aide.staking.create_staking(amount=sta_amt, benefit_address=ben_addr, private_key=sta_pk)['code'] == 0
        StakingBlockNum = aide.staking.staking_info.StakingBlockNum
        assert aide.delegate.delegate(amount=del_amt, balance_type=del_type, private_key=del_pk)['code'] == 0
        return StakingBlockNum

    def create_lock_amt(self, aide, account_index, del_amt, wit_del_amt, del_type):
        """
        构造 锁定期 金额
            - 发起质押和委托
            - wait 160
            - 赎回委托 -> 进入锁定期
        """
        # ben_addr, sta_pk, sta_amt, del_pk, del_amt, del_type
        del_pk = self.nodes_account_info[account_index].get("del_pk")
        data = {
            "ben_addr": self.nodes_account_info[account_index].get("sta_addr"),
            "sta_pk": self.nodes_account_info[account_index].get("sta_pk"),
            "sta_amt": self.staking_limit,
            "del_pk": del_pk,
            "del_amt": del_amt,
            "del_type": del_type,
        }
        StakingBlockNum = self.create_sta_del(aide, **data)

        wait_settlement(aide)

        assert aide.delegate.withdrew_delegate(amount=wit_del_amt, staking_block_identifier=StakingBlockNum,
                                               private_key=del_pk)['code'] == 0

    def lock_free_money_fixture(self, aides: list):
        self.init_sta_del(aides)
        self.create_lock_amt(aides[0], account_index=0, del_amt=self.delegate_amount,
                             wit_del_amt=self.delegate_amount, del_type=0)
        pass


class TestDelegateLockOneAccount(DelegateLock):
    """ 测试单账户-多节点场景 """

    def test_01(self, normal_aides):
        normal_aide0, normal_aide1 = normal_aides[0], normal_aides[1]

        self.lock_free_money_fixture([normal_aide0])

        res = normal_aide0.delegate.get_delegate_lock_info(address=self.nodes_account_info[0].get("del_addr"))
        logger.info(f"lock_info: {res}")
        pass
