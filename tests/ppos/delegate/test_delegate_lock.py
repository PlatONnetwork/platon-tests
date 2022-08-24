"""
@Author  :  Jw
@Contact :  libai7236@gmail.com
@Time    :  2022/8/23 11:38
@Version :  platon-1.3.0
@Desc    :  委托锁定
"""
import inspect
from decimal import Decimal

from loguru import logger
from platon._utils.error_code import ERROR_CODE


class TestDelegateLockOneAcc(object):
    """ 测试单账户-多节点场景 """

    def test_lock_free_amt(self, create_lock_amt):
        """
        测试 锁定期 自由金额 委托多节点
        @param create_lock_amt:
        @return:
        """
        logger.info(f"case_name: {inspect.stack()[0][3]}")
        normal_aide0, normal_aide1, normal_aide0_nt, normal_aide1_nt = create_lock_amt
        lock_info = normal_aide0.delegate.get_delegate_lock_info(address=normal_aide0_nt.del_addr)
        logger.info(f"lock_info: {lock_info}")

        # -委托 A、B 节点 / limit
        assert normal_aide0.delegate.delegate(private_key=normal_aide0_nt.del_pk, balance_type=3)['code'] == 0
        assert normal_aide0.delegate.delegate(private_key=normal_aide0_nt.del_pk, balance_type=3,
                                              node_id=normal_aide1.node.node_id)['code'] == 0

        # -委托 A、B 节点 / limit * 5
        del_amt1 = normal_aide0.delegate_limit * 5
        assert normal_aide0.delegate.delegate(del_amt1, 3, private_key=normal_aide0_nt.del_pk)['code'] == 0
        assert normal_aide0.delegate.delegate(del_amt1, 3, normal_aide1.node.node_id,
                                              private_key=normal_aide0_nt.del_pk, )['code'] == 0

        # -委托 A、B 节点 / limit * 110 -> fail
        del_amt2 = normal_aide0.delegate_limit * 110
        res = normal_aide0.delegate.delegate(del_amt2, 3, private_key=normal_aide0_nt.del_pk)
        assert ERROR_CODE[301207] == res['message']
        res = normal_aide0.delegate.delegate(del_amt2, 3, normal_aide1.node.node_id, private_key=normal_aide0_nt.del_pk)
        assert ERROR_CODE[301207] == res['message']

        # -委托 A、B 节点 / limit * 110 -> A pass/ B fail
        residue_amt = normal_aide0.delegate_amount - (del_amt1 * 2) - (normal_aide0.delegate_limit * 2)
        del_amt3 = int(Decimal(residue_amt) / Decimal(2))
        assert normal_aide0.delegate.delegate(del_amt3, 3, private_key=normal_aide0_nt.del_pk)['code'] == 0
        res = normal_aide0.delegate.delegate(del_amt3 + normal_aide0.web3.toVon(1, "lat"), 3, normal_aide1.node.node_id,
                                             private_key=normal_aide0_nt.del_pk)
        assert ERROR_CODE[301207] == res['message']
