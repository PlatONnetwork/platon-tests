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


if __name__ == '__main__':
    a = {'Code': 0, 'Ret': {'NodeId': '966326648797161111f7ba289b68be670f143d83de2ae0145ed086f461e936ce579024d558b4c992c5086f13264c45dc258e02d01080bb45fe54881237ee05a7', 'BlsPubKey': 'b076e161310a73245609c2b71e83ccb8b43d4d003c8efb1683db2457f6e2f0b10ba90c33a337a2d4e1bba0fb58ca01146348f43cc622eda4d68006eed94354c0228bccba600a0ebdc71f488067f28cff594285fc13ec3abd5c2f131d0c2b0712', 'StakingAddress': 'atp14p46hkp9dumat675nk8lkjd2pcwvynlz8zaxqy', 'BenefitAddress': 'atp13wwyjsvjzkq66z2hw220xmmx67xenfn6u29pm0', 'RewardPer': 1000, 'NextRewardPer': 1000, 'RewardPerChangeEpoch': 1, 'StakingTxIndex': 0, 'ProgramVersion': 4352, 'Status': 0, 'StakingEpoch': 1, 'StakingBlockNum': 24, 'Shares': 20001000000000000000000, 'Released': 20000000000000000000000, 'ReleasedHes': 0, 'RestrictingPlan': 0, 'RestrictingPlanHes': 0, 'DelegateEpoch': 2, 'DelegateTotal': 1000000000000000000, 'DelegateTotalHes': 0, 'DelegateRewardTotal': 0, 'ExternalId': 'externalId', 'NodeName': 'nodeName', 'Website': 'website', 'Details': 'details'}}
    b = {'Code': 0, 'Ret': {'NodeId': '966326648797161111f7ba289b68be670f143d83de2ae0145ed086f461e936ce579024d558b4c992c5086f13264c45dc258e02d01080bb45fe54881237ee05a7', 'BlsPubKey': 'b076e161310a73245609c2b71e83ccb8b43d4d003c8efb1683db2457f6e2f0b10ba90c33a337a2d4e1bba0fb58ca01146348f43cc622eda4d68006eed94354c0228bccba600a0ebdc71f488067f28cff594285fc13ec3abd5c2f131d0c2b0712', 'StakingAddress': 'atp14p46hkp9dumat675nk8lkjd2pcwvynlz8zaxqy', 'BenefitAddress': 'atp13wwyjsvjzkq66z2hw220xmmx67xenfn6u29pm0', 'RewardPer': 1000, 'NextRewardPer': 1500, 'RewardPerChangeEpoch': 3, 'StakingTxIndex': 0, 'ProgramVersion': 4352, 'Status': 0, 'StakingEpoch': 1, 'StakingBlockNum': 24, 'Shares': 20000000000000000000000, 'Released': 20000000000000000000000, 'ReleasedHes': 0, 'RestrictingPlan': 0, 'RestrictingPlanHes': 0, 'DelegateEpoch': 2, 'DelegateTotal': 0, 'DelegateTotalHes': 0, 'DelegateRewardTotal': 0, 'ExternalId': 'externalId', 'NodeName': 'nodeName', 'Website': 'website', 'Details': 'details'}}
    res = DeepDiff(a, b)
    pass
