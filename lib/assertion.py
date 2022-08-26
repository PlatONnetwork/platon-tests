from deepdiff import DeepDiff


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
    def del_lock_info_zero_money(cls, lock_info: dict):
        """验证委托锁定期 无锁定与待领取金额"""
        assert {len(lock_info['Locks']), lock_info['Released'], lock_info['RestrictingPlan']} == {0}

    @classmethod
    def del_locks_money(cls, lock_info, locks_len, free_amt, restr_amt):
        """验证委托锁定期 锁定中的金额"""
        assert len(lock_info['Locks']) == locks_len
        for i in lock_info['Locks']:
            pass


if __name__ == '__main__':
    data = {"Locks": [], "Released": 0, "RestrictingPlan": 0}
    Assertion.del_lock_info_zero_money(data)
    pass
