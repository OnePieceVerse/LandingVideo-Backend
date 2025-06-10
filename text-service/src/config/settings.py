import os

# OpenAI API 配置
API_KEY = os.getenv("OpenAI_API_KEY")
API_BASE = "https://api.moonshot.cn/v1"
MODEL = "moonshot-v1-8k"
MAX_RETRIES = 3
RETRY_DELAY = 2

# 服务配置
SERVICE_HOST = "0.0.0.0"
SERVICE_PORT = 8008

# 爬虫服务配置
CRAWLER_API_IP = os.getenv("CRAWLER_API_IP", "localhost")
CRAWLER_API_PORT = "3002"
CRAWLER_API_BASE_URL = f"http://{CRAWLER_API_IP}:{CRAWLER_API_PORT}/v1"

# 日志配置
LOG_DIR = os.getenv("LOG_DIR", "logs")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", "10485760"))  # 10MB
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))
LOG_ENABLE_JSON = os.getenv("LOG_ENABLE_JSON", "true").lower() == "true"
LOG_ENABLE_CONSOLE_COLORS = os.getenv("LOG_ENABLE_CONSOLE_COLORS", "true").lower() == "true"

# Token价格配置（每百万token）
INPUT_PRICE = 2.0  # ¥2/M tokens
OUTPUT_PRICE = 10.0  # ¥10/M tokens

# 性能监控配置
ENABLE_PERFORMANCE_LOGGING = os.getenv("ENABLE_PERFORMANCE_LOGGING", "true").lower() == "true"
SLOW_REQUEST_THRESHOLD = float(os.getenv("SLOW_REQUEST_THRESHOLD", "1000.0"))  # 毫秒

# 请求日志配置
LOG_REQUEST_BODY = os.getenv("LOG_REQUEST_BODY", "true").lower() == "true"
LOG_RESPONSE_BODY = os.getenv("LOG_RESPONSE_BODY", "false").lower() == "true"
MAX_BODY_LOG_SIZE = int(os.getenv("MAX_BODY_LOG_SIZE", "1000"))  # 字符 