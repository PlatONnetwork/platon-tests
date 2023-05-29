import os
import sys
from datetime import datetime

from loguru import logger

# 项目路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SCHEME = 'http'  # 包括：ws/wss/http/https
NETWORK = 'private'

# 版本信息（通过版本获取二进制文件）
CURRENT_VERSION = '1.4.0'
PREVIOUS_VERSION = '1.3.3'  # 上一个发布版本，用于验证从该历史版本升级到测试版本的过程

# platon二进制文件存放目录
BIN_DIR = os.path.join(BASE_DIR, 'env-files/bin')
PIP_BIN_DIR = os.path.join(BASE_DIR, 'env-files/pip-bin')

# 部署链的配置文件
CHAIN_FILE = os.path.join(BASE_DIR, 'env-files/chain_file.yml')
GENESIS_FILE = os.path.join(BASE_DIR, 'env-files/genesis.json')

# 钱包文件存放目录
KEYSTORE_DIR = os.path.join(BASE_DIR, 'env-files/keystore')

# 日志设置
logger.remove()
logger.add(sys.stderr, level="INFO")
log_file = datetime.strftime(datetime.now(), 'log/log-%m%d%H%M%S.log')
logger.add(log_file, level="INFO")
