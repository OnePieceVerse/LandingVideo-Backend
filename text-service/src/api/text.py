import os
import sys
import json
import time
import asyncio
import requests
import ollama
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, List, Any, Optional

# 将项目根目录添加到路径以修复导入错误
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

router = APIRouter(prefix="/text", tags=["Text Processing"])

# 爬虫API基础URL
CRAWLER_API_BASE_URL = "http://9.134.132.205:3002/v1"

class TextResponse(BaseModel):
    code: int
    msg: str
    data: Any

async def crawl_url(url, limit=2000):
    """
    向爬虫API发送爬取请求 (第一步)
    
    Args:
        url (str): 要爬取的URL
        limit (int): 爬取限制
        
    Returns:
        dict: 包含任务ID和结果URL的响应数据
    """
    # 构造请求数据
    payload = {
        "url": url,
        "limit": limit,
        "scrapeOptions": {
            "formats": ["markdown"]
        }
    }
    
    # 发送POST请求
    response = requests.post(
        f"{CRAWLER_API_BASE_URL}/crawl",
        headers={"Content-Type": "application/json"},
        json=payload
    )
    
    # 检查响应状态
    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            return data
        else:
            raise HTTPException(status_code=500, detail=f"爬取请求失败: {data}")
    else:
        raise HTTPException(status_code=response.status_code, detail="请求爬虫API失败")

async def get_crawl_result(result_url, max_retries=10, retry_delay=3):
    """
    获取爬取结果 (第二步)
    
    Args:
        result_url (str): 从第一步获取的结果URL
        max_retries (int): 最大重试次数
        retry_delay (int): 重试间隔(秒)
        
    Returns:
        dict: 爬取结果数据
    """
    # 将URL中的https替换为http
    if result_url.startswith("https"):
        result_url = "http" + result_url[5:]
    
    retries = 0
    while retries < max_retries:
        # 发送GET请求
        response = requests.get(result_url)
        
        # 检查响应状态
        if response.status_code == 200:
            data = response.json()
            status = data.get("status")
            
            # 如果爬取完成，返回结果
            if status == "completed":
                return data
            # 如果仍在进行中，等待后重试
            elif status in ["pending", "processing", "scraping"]:
                await asyncio.sleep(retry_delay)
                retries += 1
            # 其他状态视为失败
            else:
                raise HTTPException(status_code=500, detail=f"爬取任务状态异常: {status}")
        else:
            retries += 1
            await asyncio.sleep(retry_delay)
    
    # 达到最大重试次数
    raise HTTPException(status_code=500, detail=f"达到最大重试次数 ({max_retries})，未能获取结果")

async def process_with_ollama(crawl_result):
    """
    使用Ollama处理爬取结果
    
    Args:
        crawl_result (dict): 爬取结果数据
        
    Returns:
        dict: 处理后的数据，格式为{data: [{text: str, materiels: [str]}]}
    """
    # 从爬取结果中提取markdown内容
    if not (crawl_result and "data" in crawl_result and crawl_result["data"] and "markdown" in crawl_result["data"][0]):
        raise HTTPException(status_code=500, detail="爬取结果中未找到markdown内容")
    
    markdown_content = crawl_result["data"][0]["markdown"]
    
    # 构造提示词
    prompt = f"""你是一个专业的JSON数据处理助手。请严格按以下要求处理输入数据：

1. **输入**：原始Markdown格式文本，内含多个文本段落和图片链接。
2. **任务**：
   - 提取所有有效的文本段落（删除空行、广告、导航链接等无关内容）。
   - 提取所有图片URL（格式为 `![](...)` 的链接）。
   - 将文本和图片配对组合（一段文本跟随一张或多张相关图片）。
3. **输出格式**：
```json
{{
    "data": [
        {{
            "text": "段落1",
            "materiels": [
                "https://test.example.com/image1.jpg",
                "https://test.example.com/image2.jpg"
            ]
        }},
        {{
            "text": "段落2",
            "materiels": [
                "https://test.example.com/image1.jpg",
                "https://test.example.com/image2.jpg"
            ]
        }}
    ]
}}
```

以下是需要处理的Markdown内容:
{markdown_content}

请直接返回符合格式的JSON字符串，不要包含任何其他解释文字。
"""
    
    try:
        # 调用Ollama API
        response = ollama.chat(
            model="deepseek-r1:8b",
            messages=[
                {"role": "system", "content": "你是一个专业的JSON数据处理专家。"},
                {"role": "user", "content": prompt}
            ],
            stream=False
        )
        
        # 获取模型返回的内容
        result_text = response["message"]["content"]
        
        # 移除<think>...</think>标签内容
        if "<think>" in result_text and "</think>" in result_text:
            think_start = result_text.find("<think>")
            think_end = result_text.find("</think>") + len("</think>")
            result_text = result_text[:think_start] + result_text[think_end:]
            result_text = result_text.strip()
        
        # 尝试提取JSON部分 - 支持对象{}或数组[]格式
        # 尝试提取JSON对象
        json_obj_start = result_text.find("{")
        json_obj_end = result_text.rfind("}")
        
        # 尝试提取JSON数组
        json_arr_start = result_text.find("[")
        json_arr_end = result_text.rfind("]")
        
        # 判断是对象还是数组格式
        if json_obj_start >= 0 and json_obj_end >= 0 and (json_arr_start < 0 or json_obj_start < json_arr_start):
            # 找到对象格式
            json_str = result_text[json_obj_start:json_obj_end+1]
            # 解析JSON
            parsed_data = json.loads(json_str)
            if "data" in parsed_data:
                return parsed_data
            else:
                return {"data": [parsed_data]}
        elif json_arr_start >= 0 and json_arr_end >= 0:
            # 找到数组格式
            json_str = result_text[json_arr_start:json_arr_end+1]
            # 解析JSON
            parsed_data = json.loads(json_str)
            return {"data": parsed_data}
        else:
            raise HTTPException(status_code=500, detail="未找到有效的JSON对象或数组")
    
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"JSON解析错误: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理数据时出错: {str(e)}")

@router.get("/urlCrawl", response_model=TextResponse)
async def url_crawl(url: str = Query(..., description="要爬取的URL")):
    """
    爬取URL并处理内容，返回结构化数据
    
    参数:
    - url: 要爬取的URL
    
    返回:
    - 包含处理后文本和图片的结构化数据
    """
    try:
        # 步骤1: 发送爬取请求，获取任务ID和结果URL
        crawl_response = await crawl_url(url)
        
        # 获取结果URL
        result_url = crawl_response.get("url")
        if not result_url:
            raise HTTPException(status_code=500, detail="响应中未找到结果URL")
        
        # 步骤2: 获取爬取结果
        crawl_result = await get_crawl_result(result_url)
        
        # 步骤3: 使用Ollama处理数据
        processed_data = await process_with_ollama(crawl_result)
        
        # 返回处理后的数据
        return {
            "code": 200,
            "msg": "success",
            "data": processed_data["data"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理URL时出错: {str(e)}") 