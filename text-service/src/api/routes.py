import time
import logging
from fastapi import APIRouter, Request, HTTPException
from typing import Dict, Any
from pydantic import BaseModel

from src.core.service.crawler_service import crawl_url, get_crawl_result
from src.core.service.openai_service import process_with_openai, format_api_response
from src.config.logging_config import get_context_logger
from src.config.settings import SLOW_REQUEST_THRESHOLD

logger = logging.getLogger(__name__)
router = APIRouter()

# 定义请求模型
class URLCrawlRequest(BaseModel):
    url: str

@router.post("/api/v1/text/urlCrawl")
async def url_crawl(request_data: URLCrawlRequest, request: Request) -> Dict[str, Any]:
    """
    爬取URL并处理内容
    
    Args:
        request_data: 包含URL的请求体
        request: FastAPI请求对象
        
    Returns:
        处理后的结构化数据
    """
    # 获取请求ID（由中间件设置）
    request_id = getattr(request.state, "request_id", "unknown")
    start_time = getattr(request.state, "start_time", time.time())
    
    # 创建带上下文的logger
    context_logger = get_context_logger(
        "api.url_crawl",
        request_id=request_id,
        url=request_data.url
    )
    
    try:
        context_logger.info("开始处理URL爬取请求", extra={
            "event": "crawl_start",
            "target_url": request_data.url,
            "user_agent": request.headers.get("user-agent", "unknown"),
            "client_ip": request.client.host if request.client else "unknown"
        })
        
        # 步骤1: 发送爬取请求
        step_start = time.time()
        context_logger.info("步骤1/4: 发送爬取请求", extra={"event": "step_1_start"})
        
        crawl_response = await crawl_url(request_data.url)
        step_time = (time.time() - step_start) * 1000
        
        if not crawl_response:
            context_logger.error("爬取请求失败", extra={
                "event": "crawl_request_failed",
                "step": 1,
                "step_time": step_time
            })
            raise HTTPException(status_code=500, detail="爬取请求失败")
        
        result_url = crawl_response.get("url")
        if not result_url:
            context_logger.error("爬取响应中未找到结果URL", extra={
                "event": "no_result_url",
                "step": 1,
                "response": crawl_response
            })
            raise HTTPException(status_code=500, detail="爬取响应中未找到结果URL")
        
        context_logger.info("爬取请求成功", extra={
            "event": "step_1_complete",
            "step_time": step_time,
            "result_url": result_url
        })
        
        # 步骤2: 获取爬取结果
        step_start = time.time()
        context_logger.info("步骤2/4: 获取爬取结果", extra={"event": "step_2_start"})
        
        crawl_result = await get_crawl_result(result_url)
        step_time = (time.time() - step_start) * 1000
        
        if not crawl_result:
            context_logger.error("获取爬取结果失败", extra={
                "event": "get_result_failed",
                "step": 2,
                "step_time": step_time
            })
            raise HTTPException(status_code=500, detail="获取爬取结果失败")
        
        # 分析爬取结果
        content_length = 0
        if crawl_result.get("data") and crawl_result["data"]:
            content_length = len(crawl_result["data"][0].get("markdown", ""))
        
        context_logger.info("获取爬取结果成功", extra={
            "event": "step_2_complete",
            "step_time": step_time,
            "content_length": content_length,
            "data_count": len(crawl_result.get("data", []))
        })
        
        # 步骤3: 使用OpenAI处理数据
        step_start = time.time()
        context_logger.info("步骤3/4: 使用OpenAI处理数据", extra={"event": "step_3_start"})
        
        processed_data = await process_with_openai(crawl_result, request_id)
        step_time = (time.time() - step_start) * 1000
        
        context_logger.info("OpenAI处理完成", extra={
            "event": "step_3_complete",
            "step_time": step_time,
            "processed_items": len(processed_data.get("data", []))
        })
        
        # 步骤4: 格式化为API响应格式
        step_start = time.time()
        context_logger.info("步骤4/4: 格式化API响应", extra={"event": "step_4_start"})
        
        api_response = format_api_response(processed_data)
        step_time = (time.time() - step_start) * 1000
        
        context_logger.info("响应格式化完成", extra={
            "event": "step_4_complete",
            "step_time": step_time,
            "response_items": len(api_response.get("data", []))
        })
        
        # 计算并记录总处理时间
        total_time = (time.time() - start_time) * 1000
        
        # 性能警告
        if total_time > SLOW_REQUEST_THRESHOLD:
            context_logger.warning("请求处理时间过长", extra={
                "event": "slow_request",
                "total_time": total_time,
                "threshold": SLOW_REQUEST_THRESHOLD
            })
        
        context_logger.info("URL处理完成", extra={
            "event": "crawl_complete",
            "total_time": total_time,
            "success": True,
            "response_code": 200
        })
        
        return api_response
    
    except HTTPException as e:
        if e.status_code == 202:
            context_logger.info("任务正在进行中", extra={
                "event": "task_in_progress",
                "status_code": 202,
                "detail": e.detail
            })
            return {
                "code": 202,
                "msg": e.detail,
                "data": {"status": "processing", "request_id": request_id}
            }
        
        context_logger.error("HTTP异常", extra={
            "event": "http_exception",
            "status_code": e.status_code,
            "detail": e.detail
        })
        raise
    
    except Exception as e:
        total_time = (time.time() - start_time) * 1000
        context_logger.error("处理URL时发生未知错误", extra={
            "event": "unknown_error",
            "error_type": type(e).__name__,
            "error_message": str(e),
            "total_time": total_time
        }, exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"处理URL时发生错误: {str(e)}"
        )

@router.get("/health")
async def health_check(request: Request) -> Dict[str, Any]:
    """健康检查端点"""
    # 健康检查使用简单日志，避免过多噪音
    if not getattr(request.state, "skip_logging", False):
        logger.debug("健康检查请求", extra={
            "event": "health_check",
            "client_ip": request.client.host if request.client else "unknown"
        })
    
    return {
        "status": "ok", 
        "timestamp": time.time(),
        "service": "text-processing-api",
        "version": "1.0.0"
    } 