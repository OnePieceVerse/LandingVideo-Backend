import os
import sys
import logging
import logging.handlers
import time
import uvicorn
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 设置项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.api.routes import router
from src.config.settings import SERVICE_HOST, SERVICE_PORT, LOG_DIR, LOG_FORMAT, LOG_LEVEL

def setup_logger():
    """配置日志记录器"""
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)
        
    log_file = os.path.join(LOG_DIR, f"text_service_{time.strftime('%Y%m%d')}.log")
    
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        format=LOG_FORMAT,
        handlers=[
            logging.handlers.TimedRotatingFileHandler(
                filename=log_file,
                when="midnight",
                interval=1,
                backupCount=7,
                encoding="utf-8"
            ),
            logging.StreamHandler()
        ]
    )
    
    # 设置第三方库的日志级别
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)

def create_app() -> FastAPI:
    """创建FastAPI应用"""
    app = FastAPI(
        title="URL Crawler and Text Processor API",
        description="API for crawling URLs and processing the content with OpenAI",
        version="1.0.0",
    )
    
    # 添加CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 注册路由
    app.include_router(router)
    
    return app

def main():
    """主程序入口"""
    # 配置日志
    setup_logger()
    logger = logging.getLogger(__name__)
    
    # 创建应用
    app = create_app()
    
    # 启动服务
    logger.info(f"启动URL爬取和处理服务在 {SERVICE_HOST}:{SERVICE_PORT}...")
    uvicorn.run(
        app,
        host=SERVICE_HOST,
        port=SERVICE_PORT,
        log_config=None  # 禁用uvicorn默认日志配置
    )

if __name__ == "__main__":
    main()
