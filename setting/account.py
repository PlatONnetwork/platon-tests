from eth_account import Account
from eth_utils import to_checksum_address

# todo: 更改为自动获取
# HRP = 'lat'

REWARD_ADDRESS = to_checksum_address('0x1000000000000000000000000000000000000003')

MAIN_ACCOUNT = Account.from_key('f51ca759562e1daf9e5302d121f933a8152915d34fcbc27e542baf256b5e4b74')
# 0x15866368698d0f2c307E98F9723065B982e61793/lat1zkrxx6rf358jcvr7nruhyvr9hxpwv9unpydt0q
CDF_ACCOUNT = Account.from_key('64bc85af4fa0e165a1753b762b1f45017dd66955e2f8eea00333db352198b77e')
# 0xE0d5743F8572e80CCf76c1Be1f120CEBb44E0575/lat1ur2hg0u9wt5qenmkcxlp7ysvaw6yupt44ffjk0
FUND_ACCOUNT = Account.from_key('5c76634db529cb19871f56f12564d52cfe66529cd2ca658ab61b30010d5415d3')
# 0x83d935fe68270CBC3eb093d700F8F4832D3B280D/lat1s0vntlngyuxtc04sj0tsp785svknk2qdxt5emy
INCENTIVE_POOL_ACCOUNT = '0x1000000000000000000000000000000000000003'


if __name__ == '__main__':
    print(CDF_ACCOUNT.address)