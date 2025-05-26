#!/usr/bin/env python
import requests
import json
import sys

def test_url_crawl_api(url=None):
    """
    测试URL爬取API
    
    Args:
        url (str, optional): 要爬取的URL，如果不提供则使用默认URL
    """
    # 设置API端点
    api_url = "http://localhost:8000/api/v1/text/urlCrawl"
    
    # 使用提供的URL或默认URL
    test_url = url if url else "https://cfm.qq.com/web201801/detail.shtml?docid=7924797936662049421"
    
    print(f"测试URL爬取API，请求URL: {test_url}")
    
    # 发送GET请求
    response = requests.get(api_url, params={"url": test_url})
    
    # 检查响应状态
    if response.status_code == 200:
        result = response.json()
        print(f"API调用成功! 状态码: {response.status_code}")
        print(f"消息: {result.get('msg')}")
        print(f"代码: {result.get('code')}")
        
        # 打印数据概述
        data = result.get('data', [])
        print(f"返回 {len(data)} 条数据项")
        
        # 保存完整响应到文件
        with open("api_response.json", "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=4)
        
        print("完整响应已保存到 api_response.json")
        
    else:
        print(f"API调用失败! 状态码: {response.status_code}")
        print(f"错误信息: {response.text}")

if __name__ == "__main__":
    # 从命令行获取URL(如果提供)
    url = sys.argv[1] if len(sys.argv) > 1 else None
    test_url_crawl_api(url) 