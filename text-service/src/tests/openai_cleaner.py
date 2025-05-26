import json
import re
import sys
import time
from typing import Dict, List, Any
from openai import OpenAI
import os

# OpenAI API 配置
API_KEY = os.getenv("OpenAI_API_KEY")


API_BASE = "https://api.moonshot.cn/v1"
MODEL = "moonshot-v1-8k"  # 使用较快的模型
MAX_RETRIES = 3  # 最大重试次数
RETRY_DELAY = 2  # 重试间隔（秒）

def process_with_openai(markdown_data: str) -> Dict[str, Any]:
    """
    使用OpenAI API处理Markdown数据
    
    Args:
        markdown_data: 原始Markdown数据
        
    Returns:
        处理后的数据，格式为{data: [{text: str, materiels: [str]}]}
    """
    print(f"[process_with_openai] 开始使用{MODEL}处理Markdown数据...")
    
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
{markdown_data[:10000]}  # 限制长度避免超出token限制
"""

    # 初始化OpenAI客户端
    client = OpenAI(base_url=API_BASE, api_key=API_KEY)
    
    # 添加重试机制
    for attempt in range(MAX_RETRIES):
        try:
            print(f"[process_with_openai] 尝试 {attempt+1}/{MAX_RETRIES}: 发送请求到OpenAI API，使用模型: {MODEL}")
            
            # 调用OpenAI API
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "你是一个专业的数据处理助手，擅长提取结构化数据并输出JSON格式。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # 降低随机性
                max_tokens=4000,  # 增加输出长度上限
                response_format={"type": "json_object"}  # 请求返回JSON格式
            )
            
            # 获取响应文本
            result_text = response.choices[0].message.content
            print(f"[process_with_openai] 收到响应，长度: {len(result_text)} 字符")
            
            # 保存原始响应以便调试
            with open("openai_response.txt", "w", encoding="utf-8") as f:
                f.write(result_text)
            print("[process_with_openai] 原始响应已保存到 openai_response.txt")
            
            # 尝试解析JSON
            try:
                result_data = json.loads(result_text)
                print("[process_with_openai] 成功解析JSON响应")
                
                # 验证返回的JSON格式是否正确
                if "data" not in result_data:
                    print("[process_with_openai] 响应缺少'data'字段，添加默认结构")
                    result_data = {"data": result_data if isinstance(result_data, list) else []}
                
                return result_data
            except json.JSONDecodeError as e:
                print(f"[process_with_openai] JSON解析失败: {e}")
                
                # 如果已达到最大重试次数，返回错误响应
                if attempt == MAX_RETRIES - 1:
                    print("[process_with_openai] 达到最大重试次数，返回错误响应")
                    return {
                        "data": [
                            {
                                "text": "无法解析OpenAI返回的JSON。原始响应已保存到openai_response.txt文件中。",
                                "materiels": []
                            }
                        ]
                    }
                
                print(f"[process_with_openai] 尝试 {attempt+1} 失败，{RETRY_DELAY}秒后重试...")
                time.sleep(RETRY_DELAY)
        
        except Exception as e:
            print(f"[process_with_openai] 请求OpenAI API出错: {e}")
            
            # 如果已达到最大重试次数，返回错误响应
            if attempt == MAX_RETRIES - 1:
                print("[process_with_openai] 达到最大重试次数，返回错误响应")
                return {
                    "data": [
                        {
                            "text": f"调用OpenAI API失败: {str(e)}",
                            "materiels": []
                        }
                    ]
                }
            
            print(f"[process_with_openai] 尝试 {attempt+1} 失败，{RETRY_DELAY}秒后重试...")
            time.sleep(RETRY_DELAY)
    
    # 如果所有重试都失败，返回错误响应
    return {
        "data": [
            {
                "text": "无法使用OpenAI API处理数据。",
                "materiels": []
            }
        ]
    }

def format_api_response(processed_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    将处理后的数据格式化为API响应格式
    
    Args:
        processed_data: 处理后的数据
        
    Returns:
        API响应格式的数据
    """
    print("[format_api_response] 格式化为API响应格式")
    
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
    
    # 如果没有数据，创建一个空记录
    if not api_data:
        api_data.append({
            "text": "新闻资讯",
            "materiels": []
        })
    
    return {
        "code": 200,
        "data": api_data,
        "msg": "success"
    }

def process_json_file(input_file: str, output_file: str = "cleaned_game.json"):
    """
    处理JSON文件
    
    Args:
        input_file: 输入的JSON文件路径
        output_file: 输出的JSON文件路径
    """
    print(f"[process_json_file] 开始处理文件: {input_file}")
    
    try:
        # 读取JSON文件
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 提取Markdown内容
        if "data" in data and data["data"] and "markdown" in data["data"][0]:
            markdown_content = data["data"][0]["markdown"]
            print(f"[process_json_file] 成功提取Markdown内容，长度: {len(markdown_content)} 字符")
            
            # 使用OpenAI处理数据
            processed_data = process_with_openai(markdown_content)
            
            # 格式化为API响应格式
            api_response = format_api_response(processed_data)
            
            # 保存处理后的数据
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(api_response, f, ensure_ascii=False, indent=4)
            
            print(f"[process_json_file] 处理完成，结果已保存到: {output_file}")
            
            # 输出结果预览
            print("\n处理结果预览:")
            print(json.dumps(api_response, ensure_ascii=False, indent=4))
            
            return api_response
        else:
            print("[process_json_file] 无法从JSON中提取Markdown内容")
            return None
        
    except Exception as e:
        print(f"[process_json_file] 处理文件时出错: {e}")
        return None

def main():
    # 获取输入文件路径（默认为game.json）
    input_file = sys.argv[1] if len(sys.argv) > 1 else "game.json"
    
    # 获取输出文件路径（默认为cleaned_game.json）
    output_file = sys.argv[2] if len(sys.argv) > 2 else "cleaned_openai.json"
    
    # 处理文件
    process_json_file(input_file, output_file)

if __name__ == "__main__":
    main() 