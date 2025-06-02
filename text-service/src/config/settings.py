import os
import logging

# 配置基础日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# OpenAI API 配置
API_KEY = os.getenv("OpenAI_API_KEY")
API_BASE = "https://api.moonshot.cn/v1"
MODEL = "moonshot-v1-8k"
MAX_RETRIES = 3
RETRY_DELAY = 2

# 服务配置
SERVICE_HOST = "0.0.0.0"
SERVICE_PORT = 8000

# 爬虫服务配置
CRAWLER_API_IP = os.getenv("CRAWLER_API_IP", "localhost")
logger.info(f"从环境变量读取到的 CRAWLER_API_IP: {CRAWLER_API_IP}")
logger.info(f"环境变量中的所有值: {dict(os.environ)}")

CRAWLER_API_PORT = "3002"
CRAWLER_API_BASE_URL = f"http://{CRAWLER_API_IP}:{CRAWLER_API_PORT}/v1"
logger.info(f"最终构建的 CRAWLER_API_BASE_URL: {CRAWLER_API_BASE_URL}")

# 日志配置
LOG_DIR = "logs"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
LOG_LEVEL = "INFO"

# Token价格配置（每百万token）
INPUT_PRICE = 2.0  # ¥2/M tokens
OUTPUT_PRICE = 10.0  # ¥10/M tokens 