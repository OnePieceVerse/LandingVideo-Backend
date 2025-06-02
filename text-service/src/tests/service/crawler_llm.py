import sys
import os
import json
import time
import asyncio
import requests
import logging
from typing import Dict, List, Any, Optional
from fastapi import FastAPI, Query, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
import uvicorn
from pydantic import BaseModel

# 添加上级目录到Python路径，以便能导入相关模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 配置日志
def setup_logger():
    """配置日志记录器"""
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    log_file = os.path.join(log_dir, f"crawler_llm_{time.strftime('%Y%m%d')}.log")
    
    # 配置根日志记录器
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()  # 同时输出到控制台
        ]
    )
    
    # 设置第三方库的日志级别
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)

# 初始化日志配置
setup_logger()
logger = logging.getLogger(__name__)

# OpenAI API 配置
API_KEY = os.getenv("OpenAI_API_KEY")
API_BASE = "https://api.moonshot.cn/v1"
MODEL = "moonshot-v1-8k"  # 使用较快的模型
MAX_RETRIES = 3  # 最大重试次数
RETRY_DELAY = 2  # 重试间隔（秒）

# 服务配置
SERVICE_HOST = "0.0.0.0"  # 服务监听地址
SERVICE_PORT = 8000       # 服务监听端口

# 爬虫服务配置
CRAWLER_API_BASE_URL = "http://9.134.132.205:3002/v1"  # 爬虫服务地址

# 创建FastAPI应用
app = FastAPI(
    title="URL Crawler and Text Processor API",
    description="API for crawling URLs and processing the content with OpenAI",
    version="1.0.0",
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法
    allow_headers=["*"],  # 允许所有头部
)

# 定义请求模型
class URLCrawlRequest(BaseModel):
    url: str

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
    
    # 构造请求数据
    payload = {
        "url": url,
        "limit": limit,
        "scrapeOptions": {
            "formats": ["markdown"]
        }
    }
    
    try:
        # 发送POST请求到firecrawl服务
        logger.info(f"发送请求到: {CRAWLER_API_BASE_URL}/crawl")
        logger.debug(f"请求负载: {json.dumps(payload)}")
        
        response = requests.post(
            f"{CRAWLER_API_BASE_URL}/crawl",
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=30
        )
        
        # 检查响应状态
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
    # 将URL中的https替换为http
    if result_url.startswith("https"):
        result_url = "http" + result_url[5:]
    
    logger.info(f"开始获取爬取结果，URL: {result_url}")
    
    start_time = time.time()
    max_wait_time = 10  # 最大等待时间（秒）
    
    while True:
        try:
            # 发送GET请求获取爬取结果
            response = requests.get(result_url, timeout=30)
            
            # 检查响应状态
            if response.status_code == 200:
                data = response.json()
                logger.debug(f"爬虫响应数据: {json.dumps(data)}")  # 详细数据放在debug级别
                
                status = data.get("status")
                
                # 如果爬取完成，返回结果
                if status == "completed":
                    logger.info("爬取任务已完成")
                    return data
                    
                # 检查是否超时
                if time.time() - start_time > max_wait_time:
                    logger.warning(f"等待超过{max_wait_time}秒，任务仍在进行中")
                    raise HTTPException(status_code=202, detail="爬取任务进行中")
                    
                # 等待1秒后重试
                logger.debug("任务进行中，等待1秒后重试")
                await asyncio.sleep(1)
                continue
                
            else:
                logger.error(f"请求失败，状态码: {response.status_code}, 响应: {response.text}")
                raise HTTPException(status_code=response.status_code, detail=f"获取爬取结果失败: {response.text}")
                
        except requests.RequestException as e:
            logger.error(f"获取爬取结果请求失败: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"获取爬取结果失败: {str(e)}")
            
        except asyncio.TimeoutError:
            logger.error("请求超时", exc_info=True)
            raise HTTPException(status_code=408, detail="请求超时")

async def process_with_openai(crawl_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    使用OpenAI处理爬取结果
    
    Args:
        crawl_result: 爬取结果数据
        
    Returns:
        处理后的数据
    """
    logger.info(f"开始使用OpenAI {MODEL} 处理数据")
    
    # 从爬取结果中提取markdown内容
    if not (crawl_result and "data" in crawl_result and crawl_result["data"] and "markdown" in crawl_result["data"][0]):
        logger.error("爬取结果中未找到markdown内容")
        raise HTTPException(status_code=500, detail="爬取结果中未找到markdown内容")
    
    markdown_content = crawl_result["data"][0]["markdown"]
    logger.debug(f"提取到markdown内容，长度: {len(markdown_content)} 字符")
    
    # 构造提示词
    prompt = f"""你是一个专业的JSON数据处理助手。你的任务是从Markdown内容中提取有意义的文本段落和图片URL，并将它们按照要求的格式组织成JSON。

请从以下Markdown内容中提取有意义的文本段落和图片URL，并按照指定格式返回JSON:

1. 过滤掉导航链接、广告、页脚等无关内容
2. 提取所有图片URL（格式为 `![](图片URL)` 的链接）
3. 提取所有有意义的文本段落
4. 将文本和图片智能配对组合成JSON

只返回以下格式的JSON，不要有任何前缀、注释或额外文本:
{{
    "data": [
        {{
            "text": "文本段落1",
            "materiels": [
                "https://example.com/image1.jpg",
                "https://example.com/image2.jpg",
                "https://example.com/image3.jpg"
            ]
        }},
        {{
            "text": "文本段落2",
            "materiels": [
                "https://example.com/image4.jpg",
                "https://example.com/image5.jpg"
            ]
        }},
        {{
            "text": "文本段落3",
            "materiels": [
                "https://example.com/image6.jpg"
            ]
        }}
    ]
}}

重要说明：
- 一个文本段落可以对应多张图片，"materiels"必须是数组
- 如果一段文本有多张相关图片，请将所有相关图片URL都放入该文本的"materiels"数组中
- 如果无法确定某张图片属于哪段文本，可以将其分配给最近的文本段落
- 过滤掉无意义的文本（如单个标点、符号等）
- 删除页面的导航链接、页脚信息等无关内容

Markdown内容如下:
{markdown_content[:10000]}  # 限制长度避免超出token限制
"""
    
    # 初始化OpenAI客户端
    client = OpenAI(base_url=API_BASE, api_key=API_KEY)
    
    # 构造messages
    messages = [
        {"role": "system", "content": "你是一个专业的数据处理助手，擅长提取结构化数据并输出JSON格式。"},
        {"role": "user", "content": prompt}
    ]
    
    # 估算token数量（粗略估算：中文1字≈2token，英文1字≈0.25token）
    def estimate_tokens(text: str) -> int:
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        return chinese_chars * 2 + int(other_chars * 0.25)
    
    input_tokens = sum(estimate_tokens(msg["content"]) for msg in messages)
    logger.info(f"预估输入token数: {input_tokens}")
    
    # 添加重试机制
    for attempt in range(MAX_RETRIES):
        try:
            logger.info(f"尝试 {attempt+1}/{MAX_RETRIES}: 发送请求到OpenAI API")
            logger.debug(f"使用模型: {MODEL}, 温度: 0.1, 最大tokens: 4000")
            
            # 调用OpenAI API
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=0.1,
                max_tokens=4000,
                response_format={"type": "json_object"}
            )
            
            # 获取响应文本和token使用情况
            result_text = response.choices[0].message.content
            output_tokens = estimate_tokens(result_text)
            
            # 记录token使用情况
            logger.info(f"Token使用情况 - 输入: {input_tokens}, 输出: {output_tokens}")
            logger.info(f"预估费用 - 输入: ¥{input_tokens/1000000:.6f}, 输出: ¥{output_tokens/1000000*4:.6f}")
            
            # 尝试解析JSON
            try:
                parsed_data = json.loads(result_text)
                logger.info("成功解析JSON响应")
                logger.debug(f"解析后的数据: {json.dumps(parsed_data)}")
                
                # 验证返回的JSON格式是否正确
                if "data" not in parsed_data:
                    logger.warning("响应缺少'data'字段，添加默认结构")
                    return {"data": parsed_data if isinstance(parsed_data, list) else []}
                
                return parsed_data
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON解析失败: {str(e)}", exc_info=True)
                logger.debug(f"原始响应文本: {result_text}")
                
                if attempt == MAX_RETRIES - 1:
                    logger.error("达到最大重试次数，返回错误响应")
                    raise HTTPException(status_code=500, detail="无法解析OpenAI返回的JSON")
                
                logger.info(f"等待 {RETRY_DELAY} 秒后重试...")
                await asyncio.sleep(RETRY_DELAY)
        
        except Exception as e:
            logger.error(f"请求OpenAI API出错: {str(e)}", exc_info=True)
            
            if attempt == MAX_RETRIES - 1:
                logger.error("达到最大重试次数，返回错误响应")
                raise HTTPException(status_code=500, detail=f"调用OpenAI API失败: {str(e)}")
            
            logger.info(f"等待 {RETRY_DELAY} 秒后重试...")
            await asyncio.sleep(RETRY_DELAY)
    
    # 如果所有重试都失败，返回错误响应
    logger.error("所有重试都失败")
    raise HTTPException(status_code=500, detail="无法使用OpenAI API处理数据")

def format_api_response(processed_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    将处理后的数据格式化为API响应格式
    
    Args:
        processed_data: 处理后的数据
        
    Returns:
        格式化后的数据
    """
    logger.info("格式化API响应")
    
    # 确保data字段存在
    api_data = []
    
    # 遍历处理后的数据
    for item in processed_data.get("data", []):
        text = item.get("text", "")
        materials = item.get("materiels", [])
        
        # 确保materiels是列表
        if not isinstance(materials, list):
            materials = [materials] if materials else []
        
        # 过滤掉太短的文本
        if len(text.strip()) < 5:
            continue
            
        # 保持材料作为一个列表
        api_data.append({
            "text": text,
            "materiels": materials
        })
    
    # 如果没有数据，返回错误响应
    if not api_data:
        raise HTTPException(status_code=500, detail="未能提取到有效内容")
    
    return {
        "code": 200,
        "data": api_data,
        "msg": "success"
    }

@app.post("/api/v1/text/urlCrawl")
async def url_crawl(request: URLCrawlRequest):
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
        request_id = f"req_{int(time.time()*1000)}"  # 生成请求ID
        logger.info(f"[{request_id}] 开始处理URL: {request.url}")
        
        # 步骤1: 发送爬取请求
        logger.info(f"[{request_id}] 步骤1/4: 发送爬取请求")
        crawl_response = await crawl_url(request.url)
        if not crawl_response:
            logger.error(f"[{request_id}] 爬取请求失败")
            raise HTTPException(status_code=500, detail="爬取请求失败")
        
        # 获取结果URL
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
        processed_data = await process_with_openai(crawl_result)
        
        # 步骤4: 格式化为API响应格式
        logger.info(f"[{request_id}] 步骤4/4: 格式化API响应")
        api_response = format_api_response(processed_data)
        
        # 计算并记录处理时间
        end_time = time.time()
        total_time = end_time - start_time
        logger.info(f"[{request_id}] URL处理完成，总耗时: {total_time:.2f} 秒")
        
        return api_response
    
    except HTTPException as e:
        # 如果是202状态码（任务进行中），返回特殊响应
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

# 健康检查端点
@app.get("/health")
async def health_check():
    logger.debug("收到健康检查请求")
    return {"status": "ok", "timestamp": time.time()}

# 启动服务器的主函数
def main():
    logger.info(f"启动URL爬取和处理服务在 {SERVICE_HOST}:{SERVICE_PORT}...")
    uvicorn.run(app, host=SERVICE_HOST, port=SERVICE_PORT, log_config=None)  # 禁用uvicorn默认日志配置

if __name__ == "__main__":
    main()
