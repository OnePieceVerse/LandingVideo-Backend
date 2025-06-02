import time
import logging
from fastapi import APIRouter, Query, HTTPException
from typing import Dict, Any, Optional
from pydantic import BaseModel

from src.core.service.crawler_service import crawl_url, get_crawl_result
from src.core.service.openai_service import process_with_openai, format_api_response

logger = logging.getLogger(__name__)
router = APIRouter()

# 定义请求模型
class URLCrawlRequest(BaseModel):
    url: str

@router.post("/api/v1/text/urlCrawl")
async def url_crawl(request: URLCrawlRequest) -> Dict[str, Any]:
    """
    爬取URL并处理内容
    
    Args:
        request: 包含URL的请求体
        
    Returns:
        处理后的结构化数据
    """
    try:
        # 记录开始时间和请求信息
        start_time = time.time()
        request_id = f"req_{int(time.time()*1000)}"
        logger.info(f"[{request_id}] 开始处理URL: {request.url}")
        
        # 步骤1: 发送爬取请求
        logger.info(f"[{request_id}] 步骤1/4: 发送爬取请求")
        crawl_response = await crawl_url(request.url)
        if not crawl_response:
            logger.error(f"[{request_id}] 爬取请求失败")
            raise HTTPException(status_code=500, detail="爬取请求失败")
        
        result_url = crawl_response.get("url")
        if not result_url:
            logger.error(f"[{request_id}] 爬取响应中未找到结果URL")
            raise HTTPException(status_code=500, detail="爬取响应中未找到结果URL")
        
        # 步骤2: 获取爬取结果
        logger.info(f"[{request_id}] 步骤2/4: 获取爬取结果")
        crawl_result = await get_crawl_result(result_url)
        if not crawl_result:
            logger.error(f"[{request_id}] 获取爬取结果失败")
            raise HTTPException(status_code=500, detail="获取爬取结果失败")
        
        # 步骤3: 使用OpenAI处理数据
        logger.info(f"[{request_id}] 步骤3/4: 使用OpenAI处理数据")
        processed_data = await process_with_openai(crawl_result, request_id)
        
        # 步骤4: 格式化为API响应格式
        logger.info(f"[{request_id}] 步骤4/4: 格式化API响应")
        api_response = format_api_response(processed_data)
        
        # 计算并记录处理时间
        end_time = time.time()
        total_time = end_time - start_time
        logger.info(f"[{request_id}] URL处理完成，总耗时: {total_time:.2f} 秒")
        
        return api_response
    
    except HTTPException as e:
        if e.status_code == 202:
            logger.info(f"[{request_id}] 任务正在进行中: {e.detail}")
            return {
                "code": 202,
                "msg": e.detail,
                "data": {"status": "processing"}
            }
        logger.error(f"[{request_id}] 处理失败: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[{request_id}] 处理URL时发生未知错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"处理URL时发生错误: {str(e)}")

@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """健康检查端点"""
    logger.debug("收到健康检查请求")
    return {"status": "ok", "timestamp": time.time()} 