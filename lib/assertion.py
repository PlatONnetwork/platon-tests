from deepdiff import DeepDiff

from lib.utils import p_get_delegate_lock_info


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
        lock_info = p_get_delegate_lock_info(normal_aide0, normal_aide0_nt)
        assert {len(lock_info['Locks']), lock_info['Released'], lock_info['RestrictingPlan']} == {0}

    @classmethod
    def del_locks_money(cls, normal_aide0, normal_aide0_nt, expect_data):
        """验证委托锁定期 锁定中的金额"""
        lock_info = p_get_delegate_lock_info(normal_aide0, normal_aide0_nt)
        assert len(lock_info['Locks']) == len(expect_data), f"'Locks':{lock_info['Locks']}, 'Expect': {expect_data}"
        set_data = set()
        for i in lock_info['Locks']:
            set_data.add((i['Epoch'], i['Released'], i['RestrictingPlan']))
        assert set_data == expect_data, f"set_data: {set_data} != expect_data: {expect_data}"

    @classmethod
    def del_release_money(cls, normal_aide0, normal_aide0_nt, expect_data):
        """验证委托锁定 已释放的金额"""
        lock_info = p_get_delegate_lock_info(normal_aide0, normal_aide0_nt)
        assert lock_info['Released'] == expect_data['Released']
        assert lock_info['RestrictingPlan'] == expect_data['RestrictingPlan']


if __name__ == '__main__':
    data = {"Locks": [], "Released": 0, "RestrictingPlan": 0}
    pass
