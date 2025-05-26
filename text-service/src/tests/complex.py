import requests
import json
import time
import sys
import ollama

# 爬虫API基础URL
CRAWLER_API_BASE_URL = "http://9.134.132.205:3002/v1"


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


def process_with_ollama(crawl_result):
    """
    使用Ollama处理爬取结果
    
    Args:
        crawl_result (dict): 爬取结果数据
        
    Returns:
        dict: 处理后的数据，格式为{data: [{text: str, materiels: [str]}]}
    """
    print("步骤3: 使用Ollama处理数据...")
    
    # 记录开始时间
    thinking_start_time = time.time()
    
    # 从爬取结果中提取markdown内容
    if not (crawl_result and "data" in crawl_result and crawl_result["data"] and "markdown" in crawl_result["data"][0]):
        print("错误: 爬取结果中未找到markdown内容")
        return {"error": "未找到markdown内容", "data": []}
    
    markdown_content = crawl_result["data"][0]["markdown"]
    
    # 目标格式示例
    target_format = {
        "data": [
            {
                "text": "段落1",
                "materiels": [
                    "https://test.example.com/image1.jpg",
                    "https://test.example.com/image2.jpg"
                ]
            },
            {
                "text": "段落2",
                "materiels": [
                    "https://test.example.com/image1.jpg",
                    "https://test.example.com/image2.jpg"
                ]
            }
        ]
    }
    
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
    
    print("正在调用Ollama模型处理数据...")
    # 调用Ollama API
    response = ollama.chat(
        model="deepseek-r1:8b",
        messages=[
            {"role": "system", "content": "你是一个专业的JSON数据处理专家。"},
            {"role": "user", "content": prompt}
        ],
        stream=False
    )
    
    # 记录模型返回时间
    thinking_end_time = time.time()
    thinking_time = thinking_end_time - thinking_start_time
    print(f"\n模型共思考了 {thinking_time:.2f} 秒")
    
    # 获取模型返回的内容
    result_text = response["message"]["content"]
    
    # 保存原始返回内容用于调试
    with open("model_response.txt", "w", encoding="utf-8") as f:
        f.write(result_text)
    print("原始模型返回内容已保存到model_response.txt")
    
    # 移除<think>...</think>标签内容
    if "<think>" in result_text and "</think>" in result_text:
        think_start = result_text.find("<think>")
        think_end = result_text.find("</think>") + len("</think>")
        result_text = result_text[:think_start] + result_text[think_end:]
        result_text = result_text.strip()
    
    # 尝试提取JSON部分 - 支持对象{}或数组[]格式
    try:
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
            print("未找到有效的JSON对象或数组")
            print(f"处理后的文本: {result_text}")
            return {"error": "未找到JSON内容", "data": []}
    
    except json.JSONDecodeError as e:
        print(f"JSON解析错误: {e}")
        print(f"原始返回内容已保存到model_response.txt")
        return {"error": "JSON解析错误", "data": []}


def format_api_response(processed_data):
    """
    将处理后的数据格式化为API响应格式
    
    Args:
        processed_data (dict): 处理后的数据
        
    Returns:
        dict: 格式化后的数据
    """
    print("步骤4: 格式化最终输出")
    
    # 直接返回处理后的数据，确保保持原始格式
    if "data" in processed_data:
        # 确保data字段是正确的格式
        data_items = processed_data["data"]
        for item in data_items:
            # 确保每个条目包含text和materiels字段
            if "text" not in item:
                item["text"] = ""
            if "materiels" not in item:
                item["materiels"] = []
                
        return processed_data
    else:
        # 如果没有data字段，创建一个符合要求的空结构
        return {
            "data": []
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
    url = sys.argv[1] if len(sys.argv) > 1 else "https://cfm.qq.com/web201801/detail.shtml?docid=7924797936662049421"

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

    # 步骤3: 使用Ollama处理数据
    processed_data = process_with_ollama(crawl_result)
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
    save_result_to_file(api_response, "example.json")
    print("结果已保存到文件: example.json")


if __name__ == "__main__":
    main()