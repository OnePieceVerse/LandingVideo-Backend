import logging
import json
import asyncio
from typing import Dict, Any
from fastapi import HTTPException
from openai import OpenAI

from src.config.settings import (
    API_KEY, API_BASE, MODEL,
    MAX_RETRIES, RETRY_DELAY,
    INPUT_PRICE, OUTPUT_PRICE
)

logger = logging.getLogger(__name__)

def estimate_tokens(text: str) -> int:
    """估算token数量"""
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars
    return chinese_chars * 2 + int(other_chars * 0.25)

async def process_with_openai(crawl_result: Dict[str, Any], request_id: str) -> Dict[str, Any]:
    """
    使用OpenAI处理爬取结果
    
    Args:
        crawl_result: 爬取结果数据
        request_id: 请求ID
        
    Returns:
        处理后的数据
    """
    logger.info(f"开始使用OpenAI {MODEL} 处理数据")
    
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
            "materiels": ["图片URL1", "图片URL2"]
        }}
    ]
}}

Markdown内容如下:
{markdown_content[:10000]}
"""
    
    # 构造messages
    messages = [
        {"role": "system", "content": "你是一个专业的数据处理助手，擅长提取结构化数据并输出JSON格式。"},
        {"role": "user", "content": prompt}
    ]
    
    # 估算token
    input_tokens = sum(estimate_tokens(msg["content"]) for msg in messages)
    logger.info(f"预估输入token数: {input_tokens}")
    
    # 初始化OpenAI客户端
    client = OpenAI(base_url=API_BASE, api_key=API_KEY)
    
    for attempt in range(MAX_RETRIES):
        try:
            logger.info(f"尝试 {attempt+1}/{MAX_RETRIES}: 发送请求到OpenAI API")
            logger.debug(f"使用模型: {MODEL}, 温度: 0.1, 最大tokens: 4000")
            
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=0.1,
                max_tokens=4000,
                response_format={"type": "json_object"}
            )
            
            result_text = response.choices[0].message.content
            output_tokens = estimate_tokens(result_text)
            
            # 记录token使用情况
            cost = (input_tokens / 1000000 * INPUT_PRICE + 
                   output_tokens / 1000000 * OUTPUT_PRICE)
            logger.info(f"Token使用 - 输入: {input_tokens}, 输出: {output_tokens}")
            logger.info(f"预估成本: ¥{cost:.4f}")
            
            try:
                parsed_data = json.loads(result_text)
                logger.info("成功解析JSON响应")
                logger.debug(f"解析后的数据: {json.dumps(parsed_data)}")
                
                if "data" not in parsed_data:
                    logger.warning("响应缺少'data'字段，添加默认结构")
                    return {"data": parsed_data if isinstance(parsed_data, list) else []}
                
                return parsed_data
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON解析失败: {str(e)}", exc_info=True)
                logger.debug(f"原始响应文本: {result_text}")
                
                if attempt == MAX_RETRIES - 1:
                    raise HTTPException(status_code=500, detail="无法解析OpenAI返回的JSON")
                
                logger.info(f"等待 {RETRY_DELAY} 秒后重试...")
                await asyncio.sleep(RETRY_DELAY)
        
        except Exception as e:
            logger.error(f"请求OpenAI API出错: {str(e)}", exc_info=True)
            
            if attempt == MAX_RETRIES - 1:
                raise HTTPException(status_code=500, detail=f"调用OpenAI API失败: {str(e)}")
            
            logger.info(f"等待 {RETRY_DELAY} 秒后重试...")
            await asyncio.sleep(RETRY_DELAY)
    
    logger.error("所有重试都失败")
    raise HTTPException(status_code=500, detail="无法使用OpenAI API处理数据")

def format_api_response(processed_data: Dict[str, Any]) -> Dict[str, Any]:
    """格式化API响应"""
    logger.info("格式化API响应")
    
    api_data = []
    for item in processed_data.get("data", []):
        text = item.get("text", "")
        materials = item.get("materiels", [])
        
        if not isinstance(materials, list):
            materials = [materials] if materials else []
        
        if len(text.strip()) < 5:
            continue
            
        api_data.append({
            "text": text,
            "materiels": materials
        })
    
    if not api_data:
        raise HTTPException(status_code=500, detail="未能提取到有效内容")
    
    return {
        "code": 200,
        "data": api_data,
        "msg": "success"
    } 