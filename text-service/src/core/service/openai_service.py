import logging
import json
import asyncio
import time
from typing import Dict, Any
from fastapi import HTTPException
from openai import OpenAI

from src.config.settings import (
    API_KEY, API_BASE, MODEL,
    MAX_RETRIES, RETRY_DELAY,
    INPUT_PRICE, OUTPUT_PRICE
)
from src.config.logging_config import get_context_logger

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
    # 创建带上下文的logger
    openai_logger = get_context_logger(
        "openai.process",
        request_id=request_id,
        model=MODEL
    )
    
    openai_logger.info("开始OpenAI处理", extra={
        "event": "openai_process_start",
        "model": MODEL,
        "api_base": API_BASE
    })
    
    if not (crawl_result and "data" in crawl_result and crawl_result["data"] and "markdown" in crawl_result["data"][0]):
        openai_logger.error("爬取结果格式错误", extra={
            "event": "invalid_crawl_result",
            "has_data": bool(crawl_result and "data" in crawl_result),
            "data_length": len(crawl_result.get("data", [])) if crawl_result else 0
        })
        raise HTTPException(status_code=500, detail="爬取结果中未找到markdown内容")
    
    markdown_content = crawl_result["data"][0]["markdown"]
    content_length = len(markdown_content)
    
    openai_logger.info("提取markdown内容", extra={
        "event": "markdown_extracted",
        "content_length": content_length,
        "content_preview": markdown_content[:200] + "..." if content_length > 200 else markdown_content
    })
    
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
            "materials": ["图片URL1", "图片URL2"]
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
    
    openai_logger.info("准备发送OpenAI请求", extra={
        "event": "prepare_openai_request",
        "estimated_input_tokens": input_tokens,
        "prompt_length": len(prompt),
        "content_truncated": content_length > 10000
    })
    
    # 初始化OpenAI客户端
    client = OpenAI(base_url=API_BASE, api_key=API_KEY)
    
    total_start_time = time.time()
    
    for attempt in range(MAX_RETRIES):
        try:
            attempt_start_time = time.time()
            
            openai_logger.info("发送OpenAI API请求", extra={
                "event": "openai_api_request",
                "attempt": attempt + 1,
                "max_retries": MAX_RETRIES,
                "model": MODEL,
                "temperature": 0.1,
                "max_tokens": 4000
            })
            
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=0.1,
                max_tokens=4000,
                response_format={"type": "json_object"}
            )
            
            request_time = (time.time() - attempt_start_time) * 1000
            result_text = response.choices[0].message.content
            output_tokens = estimate_tokens(result_text)
            
            # 获取实际token使用情况（如果API返回）
            actual_input_tokens = getattr(response.usage, 'prompt_tokens', input_tokens) if hasattr(response, 'usage') else input_tokens
            actual_output_tokens = getattr(response.usage, 'completion_tokens', output_tokens) if hasattr(response, 'usage') else output_tokens
            
            # 计算成本
            cost = (actual_input_tokens / 1000000 * INPUT_PRICE + 
                   actual_output_tokens / 1000000 * OUTPUT_PRICE)
            
            openai_logger.info("收到OpenAI响应", extra={
                "event": "openai_api_response",
                "attempt": attempt + 1,
                "request_time": request_time,
                "input_tokens": actual_input_tokens,
                "output_tokens": actual_output_tokens,
                "estimated_cost": cost,
                "response_length": len(result_text)
            })
            
            # 记录性能日志
            perf_logger = logging.getLogger("performance")
            perf_logger.info("OpenAI API调用性能", extra={
                "request_id": request_id,
                "event": "openai_api_performance",
                "model": MODEL,
                "input_tokens": actual_input_tokens,
                "output_tokens": actual_output_tokens,
                "request_time": request_time,
                "cost": cost,
                "attempt": attempt + 1
            })
            
            try:
                parsed_data = json.loads(result_text)
                
                # 验证返回数据结构
                data_items = len(parsed_data.get("data", []))
                
                openai_logger.info("成功解析JSON响应", extra={
                    "event": "json_parse_success",
                    "data_items": data_items,
                    "total_time": (time.time() - total_start_time) * 1000
                })
                
                if "data" not in parsed_data:
                    openai_logger.warning("响应缺少data字段", extra={
                        "event": "missing_data_field",
                        "response_keys": list(parsed_data.keys())
                    })
                    return {"data": parsed_data if isinstance(parsed_data, list) else []}
                
                # 验证数据质量
                valid_items = 0
                for item in parsed_data.get("data", []):
                    if isinstance(item, dict) and "text" in item and len(item.get("text", "").strip()) > 0:
                        valid_items += 1
                
                openai_logger.info("数据质量检查", extra={
                    "event": "data_quality_check",
                    "total_items": data_items,
                    "valid_items": valid_items,
                    "quality_ratio": valid_items / data_items if data_items > 0 else 0
                })
                
                return parsed_data
                
            except json.JSONDecodeError as e:
                openai_logger.error("JSON解析失败", extra={
                    "event": "json_parse_error",
                    "attempt": attempt + 1,
                    "error": str(e),
                    "response_preview": result_text[:500] + "..." if len(result_text) > 500 else result_text
                })
                
                if attempt == MAX_RETRIES - 1:
                    openai_logger.error("所有重试的JSON解析都失败", extra={
                        "event": "all_json_parse_failed",
                        "final_response": result_text
                    })
                    raise HTTPException(status_code=500, detail="无法解析OpenAI返回的JSON")
                
                openai_logger.info("等待后重试", extra={
                    "event": "retry_wait",
                    "delay": RETRY_DELAY,
                    "reason": "json_parse_error"
                })
                await asyncio.sleep(RETRY_DELAY)
        
        except Exception as e:
            request_time = (time.time() - attempt_start_time) * 1000 if 'attempt_start_time' in locals() else 0
            
            openai_logger.error("OpenAI API请求异常", extra={
                "event": "openai_api_error",
                "attempt": attempt + 1,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "request_time": request_time
            }, exc_info=True)
            
            if attempt == MAX_RETRIES - 1:
                total_time = (time.time() - total_start_time) * 1000
                openai_logger.error("所有OpenAI API重试都失败", extra={
                    "event": "all_openai_retries_failed",
                    "total_time": total_time,
                    "final_error": str(e)
                })
                raise HTTPException(status_code=500, detail=f"调用OpenAI API失败: {str(e)}")
            
            openai_logger.info("等待后重试", extra={
                "event": "retry_wait",
                "delay": RETRY_DELAY,
                "reason": "api_error"
            })
            await asyncio.sleep(RETRY_DELAY)
    
    # 这里不应该到达，但为了安全
    openai_logger.error("意外的代码路径", extra={"event": "unexpected_code_path"})
    raise HTTPException(status_code=500, detail="无法使用OpenAI API处理数据")

def format_api_response(processed_data: Dict[str, Any]) -> Dict[str, Any]:
    """格式化API响应"""
    format_logger = get_context_logger("openai.format")
    
    format_logger.info("开始格式化API响应", extra={
        "event": "format_start",
        "input_items": len(processed_data.get("data", []))
    })
    
    api_data = []
    filtered_items = 0
    
    for index, item in enumerate(processed_data.get("data", [])):
        if not isinstance(item, dict):
            format_logger.warning("跳过非字典项", extra={
                "event": "skip_non_dict",
                "index": index,
                "item_type": type(item).__name__
            })
            continue
        
        text = item.get("text", "")
        materials = item.get("materials", [])
        
        # 确保materials是列表
        if not isinstance(materials, list):
            materials = [materials] if materials else []
            format_logger.debug("转换materials为列表", extra={
                "event": "convert_materials",
                "index": index,
                "original_type": type(item.get("materials", [])).__name__
            })
        
        # 过滤太短的文本
        if len(text.strip()) < 5:
            filtered_items += 1
            format_logger.debug("过滤短文本", extra={
                "event": "filter_short_text",
                "index": index,
                "text_length": len(text.strip()),
                "text_preview": text.strip()[:50]
            })
            continue
            
        # 验证和清理materials URL
        valid_materials = []
        for material in materials:
            if isinstance(material, str) and material.strip():
                valid_materials.append(material.strip())
            else:
                format_logger.debug("过滤无效材料", extra={
                    "event": "filter_invalid_material",
                    "material": material,
                    "material_type": type(material).__name__
                })
        
        api_data.append({
            "text": text.strip(),
            "materials": valid_materials
        })
    
    format_logger.info("完成响应格式化", extra={
        "event": "format_complete",
        "input_items": len(processed_data.get("data", [])),
        "output_items": len(api_data),
        "filtered_items": filtered_items,
        "total_materials": sum(len(item["materials"]) for item in api_data)
    })
    
    if not api_data:
        format_logger.error("没有有效内容", extra={
            "event": "no_valid_content",
            "original_items": len(processed_data.get("data", [])),
            "filtered_count": filtered_items
        })
        raise HTTPException(status_code=500, detail="未能提取到有效内容")
    
    return {
        "code": 200,
        "data": api_data,
        "msg": "success"
    } 