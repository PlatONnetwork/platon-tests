from platon_account import Account
from platon_utils import to_bech32_address

# todo: 更改为自动获取
HRP = 'lat'

REWARD_ADDRESS = to_bech32_address('0x1000000000000000000000000000000000000003', HRP)

MAIN_ACCOUNT = Account.from_key('f51ca759562e1daf9e5302d121f933a8152915d34fcbc27e542baf256b5e4b74', HRP)
CDF_ACCOUNT = Account.from_key('64bc85af4fa0e165a1753b762b1f45017dd66955e2f8eea00333db352198b77e', HRP)
FUND_ACCOUNT = Account.from_key('5c76634db529cb19871f56f12564d52cfe66529cd2ca658ab61b30010d5415d3', HRP)
INCENTIVE_POOL_ACCOUNT = 'lat1zqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqrdyjj2v'



if __name__ == '__main__':
    print(CDF_ACCOUNT.address)