"""
@Author  :  Jw
@Contact :  libai7236@gmail.com
@Time    :  2022/8/25 12:16
@Version :  V1.0
@Desc    :  链上常用基础数据
"""
from decimal import Decimal


class BaseData(object):
    delegate_limit = None
    staking_limit = None

    delegate_amount = None

    init_del_account_amt = None
    init_sta_account_amt = None

    von_limit = None
    von_k = None
    von_min = None

    def __init__(self, aides: list):
        self.aides = aides

    def set_var_info(self):
        """获取/设置 常用变量数据"""
        aide = self.aides[0]
        BaseData.staking_limit = aide.economic.staking_limit
        BaseData.delegate_limit = aide.economic.delegate_limit

        BaseData.delegate_amount = BaseData.delegate_limit * 100

        BaseData.init_sta_account_amt = BaseData.staking_limit * 10
        BaseData.init_del_account_amt = BaseData.staking_limit * 10

        BaseData.von_limit = aide.web3.toVon(1, "lat")
        BaseData.von_k = BaseData.von_limit * 1000
        BaseData.von_min = int(Decimal(BaseData.von_limit) * Decimal(0.001))
        pass
