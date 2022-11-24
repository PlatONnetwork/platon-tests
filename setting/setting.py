import os
import sys
from datetime import datetime
from loguru import logger

# 日志设置
from lib.version import Version

logger.remove()
logger.add(sys.stderr, level="INFO")
log_file = datetime.strftime(datetime.now(), 'log/log-%m%d%H%M%S.log')
logger.add(log_file, level="INFO")

# 项目路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SCHEME = 'http'  # ws/wss/http/https
NETWORK = 'private'

# 部署链的配置文件
CHAIN_FILE = os.path.join(BASE_DIR, 'env-files/chain_file.yml')
GENESIS_FILE = os.path.join(BASE_DIR, 'env-files/genesis.json')

# 当前测试版本
PLATON = os.path.join(BASE_DIR, 'env-files/bin/platon')
VERSION = Version('1.2.0')

# 历史版本，通常使用线上版本，用于验证从该历史版本升级到测试版本的过程
HISTORY_PLATON = os.path.join(BASE_DIR, '../env-files/history/platon')
HISTORY_VERSION = '1.1.0'

# 治理测试版本
PIP_BIN_DIR = os.path.join(BASE_DIR, 'env-files/pip-bin')

# keystore
KEYSTORE = os.path.join(BASE_DIR, 'env-files/keystore')
