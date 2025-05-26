import os
import sys
import requests
import time
import httpx
import ollama
import json
import asyncio
import re
from typing import Dict, List, Any

# 将项目根目录添加到路径以修复导入错误
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Pydantic models (AiDataItem, AiResponse) are defined in the API layer (e.g., src/api/image_to_ai.py)
# or a shared models module.
# This service returns a dictionary, and the API layer is responsible for constructing the AiResponse Pydantic model.

class ImageToAIService:
    def __init__(self, ollama_model_name: str = "deepseek-r1:8b"):
        self.ollama_model_name = ollama_model_name
        # External service URLs
        self.crawl_post_url = "http://9.134.132.205:3002/v1/crawl"
        # Poll settings
        self.max_poll_retries = 30  # Increased from 10 to 30
        self.poll_interval = 3  # Increased from 2 to 3 seconds
        # Use data from a still-scraping response if we've polled at least this many times
        self.min_poll_attempts = 15
        print(f"[ImageToAIService] Initialized with model: {ollama_model_name}")

    async def _call_llm(self, markdown_content: str) -> Dict[str, Any]:
        prompt_template = """你是一个专业的JSON数据处理助手。请严格按以下要求处理输入数据：

1. **输入**：原始JSON（Markdown格式），内含多个文本段落和图片链接。
2. **任务**：
   - 提取所有有效的文本段落（删除空行、广告、导航链接等无关内容）。
   - 提取所有图片URL（格式为 `![](...)` 或 `<img>` 标签的链接）。
   - 将文本和图片配对组合（一段文本跟随一张相关图片）。
3. **输出格式**：
```json
{
    "code": 200,
    "data": [
        {"text": "段落1", "materiels": ["https://example.com/image1.jpg"]},
        {"text": "段落2", "materiels": ["https://example.com/image2.gif"]}
    ],
    "msg": "success"
}
```

请处理以下Markdown内容：
"""
        full_prompt = f"{prompt_template}\n\n{markdown_content}"

        try:
            print(f"[_call_llm] Calling Ollama with {self.ollama_model_name} model")
            print(f"[_call_llm] Prompt length: {len(full_prompt)} characters")
            response = ollama.generate(
                model=self.ollama_model_name,
                prompt=full_prompt,
                stream=False  # Get the full response as a single JSON string
            )
            llm_output_str = response.get('response', '{}')
            print(f"[_call_llm] Received response from Ollama, length: {len(llm_output_str)} characters")
            
            # Try to extract JSON from the response if it's not already valid JSON
            try:
                parsed_llm_output = json.loads(llm_output_str)
                print(f"[_call_llm] Successfully parsed JSON response")
            except json.JSONDecodeError:
                # Try to extract JSON from the text (it might be wrapped in other text)
                json_match = re.search(r'```json\s*(.*?)\s*```', llm_output_str, re.DOTALL)
                if json_match:
                    try:
                        json_str = json_match.group(1)
                        parsed_llm_output = json.loads(json_str)
                        print(f"[_call_llm] Extracted JSON from code block")
                    except json.JSONDecodeError as e:
                        print(f"[_call_llm] Failed to parse JSON from code block: {e}")
                        raise ValueError(f"LLM output JSON extraction failed: {e}")
                else:
                    # Try to find any JSON-like structure with { }
                    json_match = re.search(r'({.*})', llm_output_str, re.DOTALL)
                    if json_match:
                        try:
                            json_str = json_match.group(1)
                            parsed_llm_output = json.loads(json_str)
                            print(f"[_call_llm] Extracted JSON from text")
                        except json.JSONDecodeError as e:
                            print(f"[_call_llm] Failed to parse JSON from text: {e}")
                            raise ValueError(f"LLM output JSON extraction failed: {e}")
                    else:
                        print(f"[_call_llm] No JSON structure found in LLM output")
                        raise ValueError("No JSON structure found in LLM output")
            
            return parsed_llm_output
        except Exception as e:
            print(f"[_call_llm] Error calling Ollama: {str(e)}")
            print(f"[_call_llm] Response received: {llm_output_str[:500]}... (truncated)")
            raise

    def _extract_text_image_pairs(self, markdown_content: str) -> List[Dict[str, Any]]:
        """直接解析markdown内容，提取文本和图片对"""
        print(f"[_extract_text_image_pairs] Starting extraction from markdown, length: {len(markdown_content)} characters")
        
        # 首先提取所有图片URL
        img_pattern = r'!\[.*?\]\((.*?)\)'
        img_pattern2 = r'<img.*?src=[\'"]([^\'"]+)[\'"].*?>'
        all_images = re.findall(img_pattern, markdown_content) + re.findall(img_pattern2, markdown_content)
        print(f"[_extract_text_image_pairs] Found {len(all_images)} images in markdown content")
        
        # 按段落分割内容
        paragraphs = re.split(r'\n\s*\n', markdown_content)
        print(f"[_extract_text_image_pairs] Split content into {len(paragraphs)} paragraphs")
        
        result = []
        current_img_index = 0
        
        for paragraph in paragraphs:
            # 跳过导航链接、目录和空段落
            if paragraph.strip() == '' or \
               (paragraph.startswith('*') and ('[' in paragraph and '](' in paragraph)) or \
               '[返回]' in paragraph or \
               paragraph.strip().startswith('#') or \
               '目录' in paragraph or \
               len(paragraph.strip()) < 5:  # 忽略过短段落
                continue
                
            # 查找段落中的图片
            paragraph_images = re.findall(img_pattern, paragraph) + re.findall(img_pattern2, paragraph)
            
            # 移除段落中的图片标记，只保留文本
            clean_text = re.sub(img_pattern, '', paragraph)
            clean_text = re.sub(img_pattern2, '', clean_text)
            clean_text = re.sub(r'\n+', ' ', clean_text)  # 替换换行为空格
            clean_text = clean_text.strip()
            
            if not clean_text:  # 如果清理后没有文本内容，跳过
                continue
                
            # 收集与此段落关联的图片
            materiels = []
            if paragraph_images:
                # 如果段落中有图片，使用这些图片
                materiels = paragraph_images
            elif current_img_index < len(all_images):
                # 否则，尝试从全局图片列表中获取下一张图片
                materiels = [all_images[current_img_index]]
                current_img_index += 1
                
            # 如果没有找到相关图片但还有更多文本，检查是否需要添加没有图片的文本
            if clean_text and not materiels and len(result) > 0 and len(result) < 10:
                # 尝试从之前结果中获取一个图片
                if result[-1].get("materiels"):
                    materiels = result[-1].get("materiels")
            
            # 添加结果
            if clean_text:
                result.append({
                    "text": clean_text,
                    "materiels": materiels if materiels else []
                })
                print(f"[_extract_text_image_pairs] Added paragraph: '{clean_text[:50]}...' with {len(materiels)} images")
        
        print(f"[_extract_text_image_pairs] Extraction complete. Found {len(result)} valid text-image pairs")
        
        # 确保至少返回一些内容
        if not result and all_images:
            # 如果没有提取到有效的文本-图片对，但有图片，尝试拆分整个文本
            cleaned_text = re.sub(img_pattern, '', markdown_content)
            cleaned_text = re.sub(img_pattern2, '', cleaned_text)
            cleaned_text = re.sub(r'#.*?\n', '', cleaned_text)  # 移除标题
            
            # 拆分为句子
            sentences = re.split(r'[.。!！?？;；]+\s*', cleaned_text)
            
            # 删除太短的句子和空白行
            sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
            
            print(f"[_extract_text_image_pairs] Fallback extraction: found {len(sentences)} sentences and {len(all_images)} images")
            
            # 创建文本-图片对
            for i, sentence in enumerate(sentences[:10]):  # 限制到前10个句子
                img_index = min(i, len(all_images) - 1) if all_images else -1
                result.append({
                    "text": sentence,
                    "materiels": [all_images[img_index]] if img_index >= 0 else []
                })
                
            print(f"[_extract_text_image_pairs] Fallback extraction complete. Created {len(result)} text-image pairs")
        
        return result

    async def process_url(self, target_url: str) -> Dict[str, Any]:
        print(f"[process_url] Starting to process URL: {target_url}")
        
        async with httpx.AsyncClient(timeout=90.0) as client:  # Increased timeout from 60 to 90 seconds
            # Step 1: HTTP Request A (POST)
            payload_a = {
                "url": target_url,
                "limit": 5000,  # 增加获取的内容限制
                "scrapeOptions": {
                    "formats": ["markdown"]
                }
            }
            try:
                print(f"[process_url] Sending POST request to {self.crawl_post_url} with payload: {json.dumps(payload_a)}")
                response_a = await client.post(self.crawl_post_url, json=payload_a)
                response_a.raise_for_status()
                data_a = response_a.json()
                print(f"[process_url] POST response: {json.dumps(data_a)}")
            except httpx.HTTPStatusError as e:
                print(f"[process_url] HTTP error during POST request A: {e.response.status_code} - {e.response.text}")
                raise ValueError(f"Failed to initiate crawl: {e.response.status_code}")
            except httpx.RequestError as e:
                print(f"[process_url] Request error during POST request A: {e}")
                raise ValueError(f"Request failed for crawl initiation: {e}")

            poll_url = data_a.get("url")
            if not poll_url:
                print(f"[process_url] Polling URL not found in response: {json.dumps(data_a)}")
                raise ValueError("Polling URL not found in response from crawl initiation.")
            
            if poll_url.startswith("https://9.134.132.205:3002"):
                 poll_url = poll_url.replace("https://9.134.132.205:3002", "http://9.134.132.205:3002", 1)
            
            print(f"[process_url] Polling URL: {poll_url}")

            # Step 2: HTTP Request B (GET) with polling
            data_b = None
            last_data_with_content = None
            
            for attempt in range(self.max_poll_retries):
                try:
                    print(f"[process_url] Sending GET request to {poll_url}, attempt {attempt+1}/{self.max_poll_retries}")
                    response_b = await client.get(poll_url)
                    response_b.raise_for_status()
                    data_b = response_b.json()
                    
                    print(f"[process_url] Poll response status: {data_b.get('status')}, success: {data_b.get('success')}")
                    
                    # Check if data is available even if still scraping
                    markdown_data_available = False
                    if data_b.get("data") and isinstance(data_b.get("data"), list) and len(data_b.get("data")) > 0:
                        if "markdown" in data_b.get("data")[0] and data_b.get("data")[0]["markdown"]:
                            markdown_content_preview = data_b.get("data")[0]["markdown"][:100] + "..."
                            print(f"[process_url] Found markdown content (preview): {markdown_content_preview}")
                            markdown_data_available = True
                            last_data_with_content = data_b  # Save this data for potential use if we time out
                    
                    if data_b.get("success") and data_b.get("status") == "completed":
                        # Successfully completed
                        print(f"[process_url] Crawl completed successfully after {attempt+1} attempts.")
                        break
                    elif data_b.get("status") == "scraping" or data_b.get("status") == "pending":
                        # Still in progress, but check if we have enough data already
                        if markdown_data_available and attempt >= self.min_poll_attempts:
                            print(f"[process_url] Crawl still in progress, but we have markdown content after {attempt+1} attempts. Using available data.")
                            break
                        
                        # Otherwise wait and retry
                        print(f"[process_url] Crawl in progress (status: {data_b.get('status')}). Polling attempt {attempt+1}/{self.max_poll_retries}")
                        await asyncio.sleep(self.poll_interval)
                    else:
                        # Other status (error, etc.)
                        print(f"[process_url] Crawl failed with status: {data_b.get('status')}")
                        raise ValueError(f"Crawl failed with status: {data_b.get('status')}")
                except httpx.HTTPStatusError as e:
                    print(f"[process_url] HTTP error during GET request B: {e.response.status_code} - {e.response.text}")
                    raise ValueError(f"Failed to fetch crawl data: {e.response.status_code}")
                except httpx.RequestError as e:
                    print(f"[process_url] Request error during GET request B: {e}")
                    raise ValueError(f"Request failed for crawl data fetching: {e}")
            
            # Check if we exhausted all retries
            if data_b is None:
                print(f"[process_url] Crawl did not return any data after {self.max_poll_retries} polling attempts.")
                raise ValueError(f"Crawl did not return any data after {self.max_poll_retries} polling attempts.")
            
            # If we have data with content but status isn't completed, use the last data with content
            if data_b.get("status") != "completed" and last_data_with_content is not None:
                print(f"[process_url] Using available data despite status being '{data_b.get('status')}'")
                data_b = last_data_with_content
                
            # Even if status isn't "completed", we'll try to use the data if it exists
            markdown_data_list = data_b.get("data", [])
            if not markdown_data_list or not isinstance(markdown_data_list, list) or len(markdown_data_list) == 0 or "markdown" not in markdown_data_list[0]:
                print(f"[process_url] Markdown content not found in response: {json.dumps(data_b)}")
                raise ValueError("Markdown content not found or in unexpected format in crawl data.")
            
            markdown_content = markdown_data_list[0]["markdown"]
            if not markdown_content:
                print(f"[process_url] Markdown content is empty.")
                raise ValueError("Markdown content is empty.")
                
            print(f"[process_url] Successfully retrieved markdown content. Length: {len(markdown_content)} characters")
            print(f"[process_url] Markdown preview: {markdown_content[:200]}...")

            # 尝试两种方法：直接解析和使用LLM
            try:
                # 首先尝试直接解析
                print("[process_url] Attempting direct extraction of text-image pairs from markdown...")
                text_image_pairs = self._extract_text_image_pairs(markdown_content)
                
                # 如果直接解析提取的内容太少，尝试使用LLM
                if len(text_image_pairs) < 3:
                    print(f"[process_url] Direct extraction only found {len(text_image_pairs)} pairs, trying LLM...")
                    llm_result = await self._call_llm(markdown_content)
                    
                    # 检查LLM结果是否有效
                    if llm_result and "data" in llm_result and isinstance(llm_result["data"], list) and len(llm_result["data"]) > 0:
                        # 确保结果格式正确
                        llm_data = llm_result["data"]
                        for item in llm_data:
                            # 将 'img' 字段转换为 'materiels' 字段
                            if "img" in item and "materiels" not in item:
                                item["materiels"] = [item["img"]] if item["img"] else []
                                del item["img"]
                            elif "images" in item and "materiels" not in item:
                                item["materiels"] = item["images"] if isinstance(item["images"], list) else [item["images"]]
                                del item["images"]
                            elif "materiels" not in item:
                                item["materiels"] = []
                                
                            # 确保 materiels 是列表类型
                            if not isinstance(item["materiels"], list):
                                item["materiels"] = [item["materiels"]] if item["materiels"] else []
                                
                        text_image_pairs = llm_data
                        print(f"[process_url] Using LLM result, found {len(text_image_pairs)} text-image pairs")
                else:
                    print(f"[process_url] Using direct extraction result, found {len(text_image_pairs)} text-image pairs")
            except Exception as e:
                print(f"[process_url] Error during extraction: {str(e)}")
                print("[process_url] Falling back to direct extraction method...")
                text_image_pairs = self._extract_text_image_pairs(markdown_content)
            
            # 构造与预期格式相同的响应
            result = {
                "code": 200,
                "data": text_image_pairs,
                "msg": "success"
            }
            
            print(f"[process_url] Final result contains {len(text_image_pairs)} text-image pairs")
            print(f"[process_url] Result preview: {json.dumps(result)[:300]}...")
            return result 