import requests
import json
import time
import sys
from openai import OpenAI
import os


# 爬虫API基础URL
CRAWLER_API_BASE_URL = "http://9.134.132.205:3002/v1"

# OpenAI API 配置
API_KEY = os.getenv("OpenAI_API_KEY")
API_BASE = "https://api.moonshot.cn/v1"
MODEL = "moonshot-v1-8k"  # 使用较快的模型
MAX_RETRIES = 3  # 最大重试次数
RETRY_DELAY = 2  # 重试间隔（秒）


def crawl_url(url, limit=2000):
    """
    向爬虫API发送爬取请求 (第一步)

    Args:
        url (str): 要爬取的URL
        limit (int): 爬取限制

    Returns:
        dict: 包含任务ID和结果URL的响应数据
    """
    print(f"步骤1: 正在发送爬取请求: {url}")

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
            print(f"爬取请求成功，任务ID: {data.get('id')}")
            print(f"结果URL: {data.get('url')}")
            return data
        else:
            print(f"爬取请求失败: {data}")
            return None
    else:
        print(f"请求失败，状态码: {response.status_code}")
        return None


def get_crawl_result(result_url, max_retries=10, retry_delay=3):
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

    print(f"步骤2: 正在获取爬取结果，URL: {result_url}")

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
                print(f"爬取任务已完成，状态: {status}")
                return data
            # 如果仍在进行中，等待后重试
            elif status in ["pending", "processing", "scraping"]:
                print(f"爬取任务进行中 ({status})，等待 {retry_delay} 秒后重试... (尝试 {retries + 1}/{max_retries})")
                time.sleep(retry_delay)
                retries += 1
            # 其他状态视为失败
            else:
                print(f"爬取任务状态异常: {status}")
                return data
        else:
            print(f"请求失败，状态码: {response.status_code}")
            retries += 1
            time.sleep(retry_delay)

    # 达到最大重试次数，返回最后一次获取的结果
    print(f"达到最大重试次数 ({max_retries})，返回最后获取的结果")
    return data


def process_with_openai(crawl_result):
    """
    使用OpenAI处理爬取结果
    
    Args:
        crawl_result (dict): 爬取结果数据
        
    Returns:
        dict: 处理后的数据，格式为{data: [{text: str, materiels: [str]}]}
    """
    print(f"步骤3: 使用OpenAI {MODEL} 处理数据...")
    
    # 记录开始时间
    thinking_start_time = time.time()
    
    # 从爬取结果中提取markdown内容
    if not (crawl_result and "data" in crawl_result and crawl_result["data"] and "markdown" in crawl_result["data"][0]):
        print("错误: 爬取结果中未找到markdown内容")
        return {"error": "未找到markdown内容", "data": []}
    
    markdown_content = crawl_result["data"][0]["markdown"]
    
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
            
            # 记录模型返回时间
            thinking_end_time = time.time()
            thinking_time = thinking_end_time - thinking_start_time
            print(f"\n模型共思考了 {thinking_time:.2f} 秒")
            
            # 保存原始响应以便调试
            with open("openai_response.txt", "w", encoding="utf-8") as f:
                f.write(result_text)
            print("[process_with_openai] 原始响应已保存到 openai_response.txt")
            
            # 尝试解析JSON
            try:
                parsed_data = json.loads(result_text)
                print("[process_with_openai] 成功解析JSON响应")
                
                # 验证返回的JSON格式是否正确
                if "data" not in parsed_data:
                    print("[process_with_openai] 响应缺少'data'字段，添加默认结构")
                    return {"data": parsed_data if isinstance(parsed_data, list) else []}
                
                return parsed_data
            except json.JSONDecodeError as e:
                print(f"[process_with_openai] JSON解析失败: {e}")
                
                # 如果已达到最大重试次数，返回错误响应
                if attempt == MAX_RETRIES - 1:
                    print("[process_with_openai] 达到最大重试次数，返回错误响应")
                    return {
                        "error": "JSON解析错误",
                        "data": []
                    }
                
                print(f"[process_with_openai] 尝试 {attempt+1} 失败，{RETRY_DELAY}秒后重试...")
                time.sleep(RETRY_DELAY)
        
        except Exception as e:
            print(f"[process_with_openai] 请求OpenAI API出错: {e}")
            
            # 如果已达到最大重试次数，返回错误响应
            if attempt == MAX_RETRIES - 1:
                print("[process_with_openai] 达到最大重试次数，返回错误响应")
                return {
                    "error": f"调用OpenAI API失败: {str(e)}",
                    "data": []
                }
            
            print(f"[process_with_openai] 尝试 {attempt+1} 失败，{RETRY_DELAY}秒后重试...")
            time.sleep(RETRY_DELAY)
    
    # 如果所有重试都失败，返回错误响应
    return {
        "error": "无法使用OpenAI API处理数据。",
        "data": []
    }


def format_api_response(processed_data):
    """
    将处理后的数据格式化为API响应格式
    
    Args:
        processed_data (dict): 处理后的数据
        
    Returns:
        dict: 格式化后的数据
    """
    print("步骤4: 格式化最终输出")
    
    # 如果处理数据中有错误，添加到结果中
    if "error" in processed_data:
        error_message = processed_data["error"]
        print(f"处理数据时出现错误: {error_message}")
    
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
    
    # 如果没有数据，创建一个空记录
    if not api_data:
        api_data.append({
            "text": "未能提取到有效内容",
            "materiels": []
        })
    
    return {
        "code": 200,
        "data": api_data,
        "msg": "success"
    }


def save_result_to_file(data, filename):
    """
    将结果保存到文件

    Args:
        data (dict): 结果数据
        filename (str): 文件名
    """
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print(f"结果已保存到文件: {filename}")


def main():
    # 记录脚本开始时间
    script_start_time = time.time()

    # 从命令行参数获取URL或使用默认URL
    url = sys.argv[1] if len(sys.argv) > 1 else "https://cfm.qq.com/web201801/detail.shtml?docid=12876428461341193393"

    print(f"开始处理URL: {url}")

    # 步骤1: 发送爬取请求，获取任务ID和结果URL
    crawl_response = crawl_url(url)
    if not crawl_response:
        print("爬取请求失败，退出程序")
        return

    # 获取结果URL
    result_url = crawl_response.get("url")
    if not result_url:
        print("响应中未找到结果URL，退出程序")
        return

    # 步骤2: 获取爬取结果
    crawl_result = get_crawl_result(result_url)
    if not crawl_result:
        print("获取爬取结果失败，退出程序")
        return

    # 步骤3: 使用OpenAI处理数据
    processed_data = process_with_openai(crawl_result)
    if "error" in processed_data:
        print(f"处理数据失败: {processed_data.get('error')}")

    # 步骤4: 格式化为API响应格式
    api_response = format_api_response(processed_data)

    # 计算脚本总运行时间
    script_end_time = time.time()
    script_total_time = script_end_time - script_start_time
    print(f"\n脚本总运行时间: {script_total_time:.2f} 秒")

    # 输出最终JSON结果
    print("\n最终处理结果:")
    print(json.dumps(api_response, ensure_ascii=False, indent=4))

    # 保存最终结果到文件
    save_result_to_file(api_response, "openai_result.json")
    print("结果已保存到文件: openai_result.json")


if __name__ == "__main__":
    main()