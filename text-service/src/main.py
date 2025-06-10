import os
import sys
import logging
import uvicorn
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 设置项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.api.routes import router
from src.api.middleware import RequestLogMiddleware, ErrorHandlingMiddleware, HealthCheckMiddleware
from src.config.logging_config import setup_logging
from src.config.settings import (
    SERVICE_HOST, SERVICE_PORT, LOG_DIR, LOG_LEVEL, LOG_MAX_BYTES,
    LOG_BACKUP_COUNT, LOG_ENABLE_JSON, LOG_ENABLE_CONSOLE_COLORS,
    ENABLE_PERFORMANCE_LOGGING, CRAWLER_API_BASE_URL
)

def create_app() -> FastAPI:
    """创建FastAPI应用"""
    app = FastAPI(
        title="URL Crawler and Text Processor API",
        description="API for crawling URLs and processing the content with OpenAI",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    # 添加中间件（注意顺序很重要）
    # 1. 健康检查中间件（最外层，避免健康检查产生过多日志）
    app.add_middleware(HealthCheckMiddleware)
    
    # 2. 全局错误处理中间件
    app.add_middleware(ErrorHandlingMiddleware)
    
    # 3. 请求日志中间件
    app.add_middleware(RequestLogMiddleware)
    
    # 4. CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 添加启动和关闭事件
    @app.on_event("startup")
    async def startup_event():
        logger = logging.getLogger("app.startup")
        logger.info("应用程序启动", extra={
            "event": "app_startup",
            "service_host": SERVICE_HOST,
            "service_port": SERVICE_PORT,
            "crawler_api_url": CRAWLER_API_BASE_URL,
            "log_dir": LOG_DIR,
            "log_level": LOG_LEVEL,
            "performance_logging": ENABLE_PERFORMANCE_LOGGING
        })
    
    @app.on_event("shutdown")
    async def shutdown_event():
        logger = logging.getLogger("app.shutdown")
        logger.info("应用程序关闭", extra={
            "event": "app_shutdown"
        })
    
    # 注册路由
    app.include_router(router)
    
    return app

def main():
    """主程序入口"""
    # 配置日志系统
    setup_logging(
        log_dir=LOG_DIR,
        log_level=LOG_LEVEL,
        max_bytes=LOG_MAX_BYTES,
        backup_count=LOG_BACKUP_COUNT,
        enable_json=LOG_ENABLE_JSON,
        enable_console_colors=LOG_ENABLE_CONSOLE_COLORS
    )
    
    logger = logging.getLogger(__name__)
    
    # 记录启动信息
    logger.info("正在启动文本处理服务", extra={
        "event": "service_starting",
        "host": SERVICE_HOST,
        "port": SERVICE_PORT,
        "log_config": {
            "log_dir": LOG_DIR,
            "log_level": LOG_LEVEL,
            "json_enabled": LOG_ENABLE_JSON,
            "colors_enabled": LOG_ENABLE_CONSOLE_COLORS
        }
    })
    
    # 创建应用
    app = create_app()
    
    # 配置uvicorn日志
    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s [%(levelname)8s] uvicorn - %(message)s",
                "datefmt": "%H:%M:%S"
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "uvicorn": {"handlers": ["default"], "level": "INFO"},
            "uvicorn.error": {"level": "INFO"},
            "uvicorn.access": {"handlers": ["default"], "level": "WARNING", "propagate": False},
        },
    }
    
    # 启动服务
    try:
        uvicorn.run(
            app,
            host=SERVICE_HOST,
            port=SERVICE_PORT,
            log_config=log_config,
            access_log=False  # 我们使用自己的请求日志中间件
        )
    except Exception as e:
        logger.error("服务启动失败", extra={
            "event": "service_start_failed",
            "error": str(e)
        }, exc_info=True)
        raise

if __name__ == "__main__":
    main()
