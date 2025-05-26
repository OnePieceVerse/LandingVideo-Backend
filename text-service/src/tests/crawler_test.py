import requests
import json
import time
import sys

# 爬虫API基础URL
CRAWLER_API_BASE_URL = "http://9.134.132.205:3002/v1"

def crawl_url(url, limit=2000):
    """
    向爬虫API发送爬取请求
    
    Args:
        url (str): 要爬取的URL
        limit (int): 爬取限制
        
    Returns:
        dict: 包含任务ID的响应数据
    """
    print(f"正在发送爬取请求: {url}")
    
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
            return data
        else:
            print(f"爬取请求失败: {data}")
            return None
    else:
        print(f"请求失败，状态码: {response.status_code}")
        return None

def get_crawl_result(task_id, max_retries=5, retry_delay=2):
    """
    获取爬取结果
    
    Args:
        task_id (str): 爬取任务ID
        max_retries (int): 最大重试次数
        retry_delay (int): 重试间隔(秒)
        
    Returns:
        dict: 爬取结果数据
    """
    print(f"正在获取爬取结果，任务ID: {task_id}")
    
    retries = 0
    while retries < max_retries:
        # 发送GET请求
        response = requests.get(f"{CRAWLER_API_BASE_URL}/crawl/{task_id}")
        
        # 检查响应状态
        if response.status_code == 200:
            data = response.json()
            status = data.get("status")
            
            # 如果爬取完成，返回结果
            if status == "completed":
                print("爬取任务已完成")
                return data
            # 如果仍在进行中，等待后重试
            elif status in ["pending", "processing"]:
                print(f"爬取任务进行中 ({status})，等待 {retry_delay} 秒后重试...")
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
    
    print(f"达到最大重试次数 ({max_retries})，未能获取结果")
    return None

def save_result_to_file(data, filename):
    """
    将爬取结果保存到文件
    
    Args:
        data (dict): 爬取结果数据
        filename (str): 文件名
    """
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print(f"结果已保存到文件: {filename}")

def main():
    # 从命令行参数获取URL或使用默认URL
    url = sys.argv[1] if len(sys.argv) > 1 else "https://cfm.qq.com/web201801/detail.shtml?docid=7924797936662049421"
    
    # 步骤1: 发送爬取请求
    crawl_response = crawl_url(url)
    if not crawl_response:
        print("爬取请求失败，退出程序")
        return
    
    # 获取任务ID
    task_id = crawl_response.get("id")
    
    # 步骤2: 获取爬取结果
    result = get_crawl_result(task_id)
    if not result:
        print("获取爬取结果失败，退出程序")
        return
    
    # 打印爬取结果概要
    if "data" in result and isinstance(result["data"], list):
        print(f"成功获取 {len(result['data'])} 条数据")
        
        # 打印第一条数据的部分内容（如果存在）
        if result["data"] and "markdown" in result["data"][0]:
            markdown = result["data"][0]["markdown"]
            preview = markdown[:200] + "..." if len(markdown) > 200 else markdown
            print(f"数据预览:\n{preview}")
    
    # 保存结果到文件
    save_result_to_file(result, "crawl_result.json")
    
    print("爬取流程完成")

if __name__ == "__main__":
    main() 