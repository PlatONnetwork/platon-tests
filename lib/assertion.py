from deepdiff import DeepDiff
from loguru import logger

from lib.utils import PrintInfo as PF


class Assertion:
    """提供断言方法"""

    @classmethod
    def old_lt_new_dict(cls, old, new):
        """
        对比两个dict当key相同时,验证值 old < new
        @param old:
        @param new:
        @return:
        """
        for k, v in DeepDiff(old, new).get("values_changed").items():
            assert v.get("old_value") < v.get("new_value"), f"{k}, {v}"

    @classmethod
    def del_lock_info_zero_money(cls, normal_aide0, normal_aide0_nt):
        """验证委托锁定期 无锁定与待领取金额"""
        lock_info = PF.p_get_delegate_lock_info(normal_aide0, normal_aide0_nt)
        assert {len(lock_info['Locks']), lock_info['Released'], lock_info['RestrictingPlan']} == {0}

    @classmethod
    def del_locks_money(cls, normal_aide0, normal_aide0_nt, expect_data):
        """验证委托锁定期 锁定中的金额"""
        lock_info = PF.p_get_delegate_lock_info(normal_aide0, normal_aide0_nt)
        assert len(lock_info['Locks']) == len(expect_data), f"'Locks':{lock_info['Locks']}, 'Expect': {expect_data}"
        if len(expect_data) != 0:
            set_data = set()
            for i in lock_info['Locks']:
                set_data.add((i['Epoch'], i['Released'], i['RestrictingPlan']))
            assert set_data == expect_data, f"set_data: {set_data} != expect_data: {expect_data}"

    @classmethod
    def del_lock_release_money(cls, normal_aide0, normal_aide0_nt, expect_data):
        """验证委托锁定 已释放的金额"""
        lock_info = PF.p_get_delegate_lock_info(normal_aide0, normal_aide0_nt)
        assert lock_info['Released'] == expect_data['Released']
        assert lock_info['RestrictingPlan'] == expect_data['RestrictingPlan']

    @classmethod
    def assert_delegate_info_contain(cls, delegate_info, expect_data: dict):
        """delegate_info 包含 expect_data"""
        x = set(delegate_info.items())
        y = set(expect_data.items())
        assert x.issuperset(y), f"delegate_info:{delegate_info}, expect_data:{expect_data}"

    @classmethod
    def assert_withdrew_delegate_response_contain(cls, withdrew_delegate_res, expect_data: dict):
        """withdrew_delegate 包含 expect_data"""
        x = set(withdrew_delegate_res.items())
        y = set(expect_data.items())
        assert x.issuperset(y), f"delegate_info:{withdrew_delegate_res}, expect_data:{expect_data}"

    @classmethod
    def diff_restr_info(cls, before, last) -> dict:
        """
        对比锁仓信息,返回不一致数据
        @param before:
        @param last:
        @return:
        """
        res = DeepDiff(before, last)
        diff_info = dict()
        if res.get('values_changed'):
            for item in res['values_changed'].items():
                title = item[0].split("'")[1]
                diff_info[title] = item[1]
        # 若plans有变化则 单独处理plans,只返回计划长度
        if diff_info.get("plans"):
            diff_info['plans'] = {"old_value_len": len(before['plans']), "new_value_len": len(last['plans'])}
        logger.info(f"diff_restr_info: {diff_info}")
        return diff_info

    @classmethod
    def assert_restr_amt(cls, before, last, expect_data):
        diff_info = cls.diff_restr_info(before, last)
        assert diff_info == expect_data, f"diff_info: {diff_info} != expect_data: {expect_data}"


if __name__ == '__main__':
    data = {"Locks": [], "Released": 0, "RestrictingPlan": 0}
    pass
