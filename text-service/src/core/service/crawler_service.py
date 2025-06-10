import logging
import json
import requests
import asyncio
import time
from typing import Dict, Any
from fastapi import HTTPException

from src.config.settings import CRAWLER_API_BASE_URL
from src.config.logging_config import get_context_logger

logger = logging.getLogger(__name__)

# 禁用所有代理的配置
DISABLE_PROXIES = {
    'http': None,
    'https': None
}

async def crawl_url(url: str, limit: int = 2000) -> Dict[str, Any]:
    """
    向爬虫API发送爬取请求
    
    Args:
        url: 要爬取的URL
        limit: 爬取限制
        
    Returns:
        包含任务ID和结果URL的响应数据
    """
    # 创建带上下文的logger
    crawler_logger = get_context_logger("crawler.crawl_url", url=url, limit=limit)
    
    crawler_logger.info("开始发送爬取请求", extra={
        "event": "crawl_request_start",
        "target_url": url,
        "crawler_api": CRAWLER_API_BASE_URL,
        "limit": limit
    })
    
    payload = {
        "url": url,
        "limit": limit,
        "scrapeOptions": {
            "formats": ["markdown"]
        }
    }
    
    start_time = time.time()
    
    try:
        crawler_logger.debug("发送HTTP请求", extra={
            "event": "http_request_start",
            "endpoint": f"{CRAWLER_API_BASE_URL}/crawl",
            "payload": payload
        })
        
        response = requests.post(
            f"{CRAWLER_API_BASE_URL}/crawl",
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=30,
            proxies=DISABLE_PROXIES
        )
        
        request_time = (time.time() - start_time) * 1000
        
        crawler_logger.debug("收到HTTP响应", extra={
            "event": "http_response_received",
            "status_code": response.status_code,
            "request_time": request_time,
            "response_size": len(response.content)
        })
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                task_id = data.get("id")
                result_url = f"{CRAWLER_API_BASE_URL}/crawl/{task_id}"
                
                crawler_logger.info("爬取请求成功", extra={
                    "event": "crawl_request_success",
                    "task_id": task_id,
                    "result_url": result_url,
                    "request_time": request_time
                })
                
                return {"success": True, "url": result_url}
            else:
                crawler_logger.error("爬虫服务返回失败状态", extra={
                    "event": "crawler_service_failure",
                    "response_data": data,
                    "request_time": request_time
                })
                raise HTTPException(status_code=500, detail="爬取请求失败")
        else:
            crawler_logger.error("HTTP请求失败", extra={
                "event": "http_request_failed",
                "status_code": response.status_code,
                "response_text": response.text[:500],  # 限制日志长度
                "request_time": request_time
            })
            raise HTTPException(
                status_code=response.status_code, 
                detail=f"爬虫服务请求失败: HTTP {response.status_code}"
            )
            
    except requests.Timeout:
        request_time = (time.time() - start_time) * 1000
        crawler_logger.error("爬取请求超时", extra={
            "event": "crawl_request_timeout",
            "timeout": 30,
            "request_time": request_time
        })
        raise HTTPException(status_code=504, detail="爬虫服务请求超时")
        
    except requests.ConnectionError as e:
        request_time = (time.time() - start_time) * 1000
        crawler_logger.error("连接爬虫服务失败", extra={
            "event": "connection_error",
            "error": str(e),
            "request_time": request_time,
            "crawler_api": CRAWLER_API_BASE_URL
        })
        raise HTTPException(status_code=503, detail="无法连接到爬虫服务")
        
    except requests.RequestException as e:
        request_time = (time.time() - start_time) * 1000
        crawler_logger.error("爬取请求发生异常", extra={
            "event": "request_exception",
            "error_type": type(e).__name__,
            "error_message": str(e),
            "request_time": request_time
        }, exc_info=True)
        raise HTTPException(status_code=500, detail=f"爬取请求失败: {str(e)}")
        
    except Exception as e:
        request_time = (time.time() - start_time) * 1000
        crawler_logger.error("未知异常", extra={
            "event": "unknown_exception",
            "error_type": type(e).__name__,
            "error_message": str(e),
            "request_time": request_time
        }, exc_info=True)
        raise HTTPException(status_code=500, detail="爬取服务内部错误")

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
    
    # 创建带上下文的logger
    result_logger = get_context_logger("crawler.get_result", result_url=result_url)
    
    result_logger.info("开始获取爬取结果", extra={
        "event": "get_result_start",
        "result_url": result_url,
        "max_wait_time": 10
    })
    
    start_time = asyncio.get_event_loop().time()
    max_wait_time = 10
    retry_count = 0
    
    while True:
        try:
            retry_count += 1
            request_start = time.time()
            
            result_logger.debug("轮询爬取结果", extra={
                "event": "polling_attempt",
                "retry_count": retry_count,
                "elapsed_time": asyncio.get_event_loop().time() - start_time
            })
            
            response = requests.get(
                result_url, 
                timeout=30,
                proxies=DISABLE_PROXIES
            )
            
            request_time = (time.time() - request_start) * 1000
            
            if response.status_code == 200:
                data = response.json()
                status = data.get("status")
                
                result_logger.debug("收到轮询响应", extra={
                    "event": "polling_response",
                    "status": status,
                    "retry_count": retry_count,
                    "request_time": request_time
                })
                
                if status == "completed":
                    total_time = asyncio.get_event_loop().time() - start_time
                    
                    # 分析结果数据
                    data_count = len(data.get("data", []))
                    content_size = 0
                    if data.get("data") and data["data"]:
                        content_size = len(data["data"][0].get("markdown", ""))
                    
                    result_logger.info("爬取任务完成", extra={
                        "event": "crawl_task_completed",
                        "total_time": total_time,
                        "retry_count": retry_count,
                        "data_count": data_count,
                        "content_size": content_size
                    })
                    
                    return data
                elif status == "failed":
                    result_logger.error("爬取任务失败", extra={
                        "event": "crawl_task_failed",
                        "retry_count": retry_count,
                        "response_data": data
                    })
                    raise HTTPException(status_code=500, detail="爬取任务失败")
                    
                # 检查超时
                elapsed_time = asyncio.get_event_loop().time() - start_time
                if elapsed_time > max_wait_time:
                    result_logger.warning("等待超时，任务仍在进行中", extra={
                        "event": "polling_timeout",
                        "elapsed_time": elapsed_time,
                        "max_wait_time": max_wait_time,
                        "retry_count": retry_count,
                        "status": status
                    })
                    raise HTTPException(status_code=202, detail="爬取任务进行中")
                
                # 等待后重试
                result_logger.debug("任务进行中，等待重试", extra={
                    "event": "waiting_retry",
                    "status": status,
                    "elapsed_time": elapsed_time
                })
                await asyncio.sleep(1)
                continue
                
            else:
                result_logger.error("获取结果请求失败", extra={
                    "event": "get_result_http_error",
                    "status_code": response.status_code,
                    "response_text": response.text[:500],
                    "retry_count": retry_count,
                    "request_time": request_time
                })
                raise HTTPException(
                    status_code=response.status_code, 
                    detail=f"获取爬取结果失败: HTTP {response.status_code}"
                )
                
        except HTTPException:
            # HTTPException直接重新抛出
            raise
            
        except requests.Timeout:
            result_logger.error("获取结果请求超时", extra={
                "event": "get_result_timeout",
                "retry_count": retry_count,
                "timeout": 30
            })
            raise HTTPException(status_code=504, detail="获取爬取结果超时")
            
        except requests.RequestException as e:
            result_logger.error("获取结果请求异常", extra={
                "event": "get_result_request_error",
                "error_type": type(e).__name__,
                "error_message": str(e),
                "retry_count": retry_count
            }, exc_info=True)
            raise HTTPException(status_code=500, detail=f"获取爬取结果失败: {str(e)}")
            
        except asyncio.TimeoutError:
            result_logger.error("异步操作超时", extra={
                "event": "async_timeout",
                "retry_count": retry_count
            })
            raise HTTPException(status_code=408, detail="请求超时")
            
        except Exception as e:
            result_logger.error("获取结果时发生未知异常", extra={
                "event": "get_result_unknown_error",
                "error_type": type(e).__name__,
                "error_message": str(e),
                "retry_count": retry_count
            }, exc_info=True)
            raise HTTPException(status_code=500, detail="获取爬取结果时发生内部错误") 