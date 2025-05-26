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
                print(f"爬取任务进行中 ({status})，等待 {retry_delay} 秒后重试... (尝试 {retries+1}/{max_retries})")
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

def process_with_ollama(markdown_data):
    """
    使用Ollama处理Markdown数据
    
    Args:
        markdown_data (str): 原始Markdown数据
        
    Returns:
        dict: 处理后的数据，格式为{data: [{text: str, materiels: [str]}]}
    """
    print("步骤3: 正在使用Ollama处理数据...")
    

    
    # 构造提示词
    prompt = f"""你是一个专业的JSON数据处理助手。请严格按以下要求处理输入数据：

1. **输入**：原始Markdown格式文本，内含多个文本段落和图片链接。
2. **任务**：
   - 提取所有有效的文本段落（删除空行、广告、导航链接等无关内容）。
   - 提取所有图片URL（格式为 `![](...)` 的链接）。
   - 将文本和图片配对组合（一段文本跟随一张或多张相关图片）。
3. **输出格式**：
```json
{
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
```

以下是需要处理的Markdown内容:
{markdown_data}

请直接返回符合格式的JSON字符串，不要包含任何其他解释文字。
"""
    
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
    
    # 尝试提取JSON部分
    try:
        # 查找JSON开始和结束的位置
        json_start = result_text.find("{")
        json_end = result_text.rfind("}")
        
        if json_start >= 0 and json_end >= 0:
            json_str = result_text[json_start:json_end+1]
            # 解析JSON
            result_data = json.loads(json_str)
            return result_data
        else:
            print("无法在响应中找到JSON格式数据")
            return {"error": "无法解析返回内容", "data": []}
    
    except json.JSONDecodeError as e:
        print(f"JSON解析错误: {e}")
        print(f"原始返回内容: {result_text}")
        return {"error": "JSON解析错误", "data": []}

def format_api_response(processed_data):
    """
    将处理后的数据格式化为API响应格式
    
    Args:
        processed_data (dict): 处理后的数据
        
    Returns:
        dict: API响应格式的数据
    """
    print("步骤4: 格式化为API响应格式")
    api_data = []
    
    # 遍历处理后的数据
    for item in processed_data.get("data", []):
        text = item.get("text", "")
        materials = item.get("materiels", [])
        
        # 对每个图片创建一个条目
        for i, img_url in enumerate(materials):
            api_data.append({
                "text": text,
                "img": img_url
            })
    
    # 如果没有图片，仍然保留文本
    if not api_data and processed_data.get("data"):
        for item in processed_data.get("data", []):
            if item.get("text"):
                api_data.append({
                    "text": item.get("text", ""),
                    "img": ""
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
    result = get_crawl_result(result_url)
    if not result:
        print("获取爬取结果失败，退出程序")
        return
    
    # 提取Markdown内容
    if "data" in result and result["data"] and "markdown" in result["data"][0]:
        markdown_content = result["data"][0]["markdown"]
        
        # 步骤3: 使用Ollama处理数据
        processed_data = process_with_ollama(markdown_content)
        
        # 步骤4: 格式化为API响应格式
        api_response = format_api_response(processed_data)
        
        # 输出最终JSON结果
        print("\n最终处理结果:")
        print(json.dumps(api_response, ensure_ascii=False, indent=4))
        
        # 保存最终结果到文件
        save_result_to_file(api_response, "example.json")
        print("结果已保存到文件: example.json")
    else:
        print("爬取结果中未找到Markdown内容")

if __name__ == "__main__":
    main() 