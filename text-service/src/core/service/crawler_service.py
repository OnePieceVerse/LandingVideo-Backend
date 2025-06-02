import logging
import json
import requests
import asyncio
from typing import Dict, Any
from fastapi import HTTPException

from src.config.settings import CRAWLER_API_BASE_URL

logger = logging.getLogger(__name__)

async def crawl_url(url: str, limit: int = 2000) -> Dict[str, Any]:
    """
    向爬虫API发送爬取请求
    
    Args:
        url: 要爬取的URL
        limit: 爬取限制
        
    Returns:
        包含任务ID和结果URL的响应数据
    """
    logger.info(f"开始爬取URL: {url}")
    
    payload = {
        "url": url,
        "limit": limit,
        "scrapeOptions": {
            "formats": ["markdown"]
        }
    }
    
    try:
        logger.info(f"发送请求到: {CRAWLER_API_BASE_URL}/crawl")
        logger.debug(f"请求负载: {json.dumps(payload)}")
        
        response = requests.post(
            f"{CRAWLER_API_BASE_URL}/crawl",
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                task_id = data.get("id")
                result_url = f"{CRAWLER_API_BASE_URL}/crawl/{task_id}"
                logger.info(f"爬取请求成功，任务ID: {task_id}")
                logger.debug(f"结果URL: {result_url}")
                return {"success": True, "url": result_url}
            else:
                logger.error(f"爬取请求失败: {data}")
                raise HTTPException(status_code=500, detail="爬取请求失败")
        else:
            logger.error(f"请求失败，状态码: {response.status_code}")
            raise HTTPException(status_code=response.status_code, detail=f"爬虫服务请求失败: {response.text}")
            
    except requests.RequestException as e:
        logger.error(f"爬取请求发生异常: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"爬取请求失败: {str(e)}")

async def get_crawl_result(result_url: str) -> Dict[str, Any]:
    """
    获取爬取结果，带有10秒超时的轮询机制
    
    Args:
        result_url: 从爬取请求获取的结果URL
        
    Returns:
        爬取结果数据
    """
    if result_url.startswith("https"):
        result_url = "http" + result_url[5:]
    
    logger.info(f"开始获取爬取结果，URL: {result_url}")
    
    start_time = asyncio.get_event_loop().time()
    max_wait_time = 10
    
    while True:
        try:
            response = requests.get(result_url, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                logger.debug(f"爬虫响应数据: {json.dumps(data)}")
                
                status = data.get("status")
                if status == "completed":
                    logger.info("爬取任务已完成")
                    return data
                    
                if asyncio.get_event_loop().time() - start_time > max_wait_time:
                    logger.warning(f"等待超过{max_wait_time}秒，任务仍在进行中")
                    raise HTTPException(status_code=202, detail="爬取任务进行中")
                
                logger.debug("任务进行中，等待1秒后重试")
                await asyncio.sleep(1)
                continue
                
            else:
                logger.error(f"请求失败，状态码: {response.status_code}")
                raise HTTPException(status_code=response.status_code, detail=f"获取爬取结果失败: {response.text}")
                
        except requests.RequestException as e:
            logger.error(f"获取爬取结果请求失败: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"获取爬取结果失败: {str(e)}")
            
        except asyncio.TimeoutError:
            logger.error("请求超时", exc_info=True)
            raise HTTPException(status_code=408, detail="请求超时") 