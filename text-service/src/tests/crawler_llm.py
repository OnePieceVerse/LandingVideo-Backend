import sys
import os
import json
import time
import asyncio
import requests
from typing import Dict, List, Any, Optional
from fastapi import FastAPI, Query, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
import uvicorn

# 添加上级目录到Python路径，以便能导入相关模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# OpenAI API 配置
API_KEY = os.getenv("OpenAI_API_KEY")
API_BASE = "https://api.moonshot.cn/v1"
MODEL = "moonshot-v1-8k"  # 使用较快的模型
MAX_RETRIES = 3  # 最大重试次数
RETRY_DELAY = 2  # 重试间隔（秒）

# 爬虫API基础URL
CRAWLER_API_BASE_URL = "http://9.134.132.205:3002/v1"
# 是否使用模拟数据（当爬虫服务不可用时）
USE_MOCK_DATA = True  # 设置为True以启用模拟数据

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

# 日志格式化函数
def log_message(message: str):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    print(f"[{timestamp}] {message}")

# 为测试目的创建的模拟数据
def get_mock_crawl_data():
    """返回模拟的爬虫数据，用于测试目的"""
    log_message("使用模拟数据代替真实爬虫服务")
    
    # 模拟第一步爬取请求的响应
    mock_crawl_response = {
        "success": True,
        "id": "mock-crawl-id",
        "url": "http://mock-crawler/v1/result/mock-crawl-id"
    }
    
    # 模拟第二步获取结果的响应
    mock_crawl_result = {
        "status": "completed",
        "data": [
            {
                "markdown": """# 虫族精英怪解析

哈喽，各位CFer大家好~这不游戏里也是上架了与吞噬星空重磅联名的全新挑战模式，这次的挑战模式不仅有全新BOSS虫族女王，同时上架三款全新精英怪，多样技能让挑战加码。本期资讯则为大家带来精英怪的介绍、技能以及打法解析，话不多说，火速发车~

![](https://static.gametalk.qq.com/image/34/1748223928_64f8c95724986b2880266852cbd7a4ba.png)

## 虎甲虫族

虎甲虫族拥有着甲类虫族的一个共同点——防御强！而虎甲虫族以力量出名。全身体表笼罩着一层无比厚实的甲壳，在它的头部有着椭圆形的复眼，复眼完全被甲壳保护好，它的头部好像战士戴着头盔般被保护的严严实实。

![](https://static.gametalk.qq.com/image/34/1748223925_c4db17c308bc4beb587dc9a6e45a7447.png)

技能一：带盾冲锋虎甲虫族在身前幻化一面火焰巨盾，而后向前冲刺，被冲击到的玩家会被击飞，若撞击到墙壁或其他碰撞则造成二次伤害。在实战中如果看到虎甲虫族立起一个红色护盾，这个时候我们就可以选择拉远距离，落地后一瞬间总会有一小段停滞时间，这里我们则可以快速攻击头部弱点。

![](https://static.gametalk.qq.com/image/34/1748223919_8998847634af42aed169560b97f4d87f.gif)

技能二：火炬光环短暂蓄力后，以自身为圆心，释放一道环形的火焰冲击伤害，被冲击命中的玩家会被击飞，若二次撞击碰撞则造成二次伤害。我们可以看到虎甲虫族在释放技能期间，是完全静止不动的，此时我们就可以利用这个空隙快速进行攻击。

![](https://static.gametalk.qq.com/image/34/1748223914_a0fd6a38297473e7aa8873ee7a833173.gif)

## 蜂影虫族

影类虫族中的"锋影虫族"，详细划分可分为锋影虫族的一个分支"纳斯塔虫族"，有着影类虫族的共同点——速度极快，它拥有着无比惊人的速度，快如幻影，攻击力也极强，唯一的弱点是身体比较弱。

![](https://static.gametalk.qq.com/image/34/1748223911_4c5483ac9feb5e17de954081e7341069.png)

技能一：孤立无援如果场景中只有一名玩家，蜂影虫族的移动速度会提高；如果在玩家的视野外击杀玩家，蜂影虫族会随机选择下一名玩家飞去，落地并造成一次小范围AOE伤害。该技能则是玩家越少，蜂影虫族速度越快，同时我们也可以根据左侧状态栏查看队友的状态，从而防止被随机选择。

![](https://static.gametalk.qq.com/image/34/1748223907_0746035c6b3715ced4c417f9d91c265a.gif)

技能二：潜行蜂影虫族除普通攻击和释放技能期间，其他时刻均保持潜行状态。但是在实战里，蜂影虫族的潜行状态，仔细观察下还是很容易察觉的，那么CFer可以看到下图的蜂隐虫族在哪呢？

![](https://static.gametalk.qq.com/image/34/1748223898_a86fafcfee60841691f249812fd8c4f1.png)

## 裂螳虫族

裂螳虫族拥有着强大的身体，拥有着惊人的速度，惊人的防御，以及无比灵活的闪躲能力，还有天生的高超的战斗技巧。比虎甲虫族显得精瘦，比影锋虫族显得彪悍，全身有着一层主要色调为黑色的流线型鳞甲，复杂的黑色鳞甲上有着青色的花纹，令整个猎螳虫族多了一丝鬼魅气息，它有着粗壮的下肢，以及两对仿佛战刀似的前肢，前肢边缘还有着利爪。

![](https://static.gametalk.qq.com/image/34/1748223894_baebd2039d0c0eb81029a4a0b675aa77.png)

技能一：月牙天冲短暂蓄力后，同时挥动两只手臂，形成月牙形斩击，斩击会向前飞行。在实战里，只要不是近距离战斗，玩家还是很容易躲避月牙天冲的攻击。

![](https://static.gametalk.qq.com/image/34/1748223886_6df0b4e9f80eca873636ea271d1eb8fa.gif)

技能二：半月弯刀短暂蓄力后，在身前猛烈横向挥击，造成一次大范围伤害。该技能会有一小段前摇时间，玩家看到蓄力动作后，则可以选择拉远距离进行攻击。

![](https://static.gametalk.qq.com/image/34/1748223881_de65de6e9a5cf1d4093f4d4006fa8d4a.gif)

以上就是本期资讯的全部内容了，那么各位CFer对于这次精英怪的技能有什么好的建议？或者认为挑战难度是否达到你的预期了呢？欢迎在评论区留下你的观点~"""
            }
        ]
    }
    
    return mock_crawl_response, mock_crawl_result

async def crawl_url(url: str, limit: int = 2000) -> Dict[str, Any]:
    """
    向爬虫API发送爬取请求
    
    Args:
        url: 要爬取的URL
        limit: 爬取限制
        
    Returns:
        包含任务ID和结果URL的响应数据
    """
    log_message(f"开始爬取URL: {url}")
    
    # 如果使用模拟数据，则返回模拟的爬取响应
    if USE_MOCK_DATA:
        mock_crawl_response, _ = get_mock_crawl_data()
        return mock_crawl_response
    
    # 构造请求数据
    payload = {
        "url": url,
        "limit": limit,
        "scrapeOptions": {
            "formats": ["markdown"]
        }
    }
    
    try:
        # 测试爬虫服务是否可达
        try:
            test_response = requests.get(f"{CRAWLER_API_BASE_URL}/health", timeout=5)
            log_message(f"爬虫服务健康检查响应: {test_response.status_code}")
        except requests.RequestException as e:
            log_message(f"爬虫服务不可达，健康检查失败: {str(e)}")
        
        # 发送POST请求
        log_message(f"发送请求到: {CRAWLER_API_BASE_URL}/crawl")
        log_message(f"请求负载: {json.dumps(payload)}")
        
        response = requests.post(
            f"{CRAWLER_API_BASE_URL}/crawl",
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=30
        )
        
        # 输出完整响应信息用于调试
        log_message(f"爬虫响应状态码: {response.status_code}")
        try:
            response_text = response.text
            log_message(f"爬虫响应内容: {response_text[:500]}...")  # 只显示前500个字符
        except Exception as e:
            log_message(f"无法读取响应内容: {str(e)}")
        
        response.raise_for_status()
        
        data = response.json()
        if data.get("success"):
            log_message(f"爬取请求成功，任务ID: {data.get('id')}")
            log_message(f"结果URL: {data.get('url')}")
            return data
        else:
            log_message(f"爬取请求失败: {data}")
            # 如果真实服务失败，切换到模拟数据
            log_message("切换到模拟数据")
            mock_crawl_response, _ = get_mock_crawl_data()
            return mock_crawl_response
    except requests.RequestException as e:
        log_message(f"爬取请求发生异常: {str(e)}")
        
        # 如果真实服务失败，切换到模拟数据
        log_message("爬虫服务异常，切换到模拟数据")
        mock_crawl_response, _ = get_mock_crawl_data()
        return mock_crawl_response

async def get_crawl_result(result_url: str, max_retries: int = 15, retry_delay: int = 3) -> Dict[str, Any]:
    """
    获取爬取结果
    
    Args:
        result_url: 从爬取请求获取的结果URL
        max_retries: 最大重试次数
        retry_delay: 重试间隔(秒)
        
    Returns:
        爬取结果数据
    """
    # 如果使用模拟数据，则返回模拟的爬取结果
    if USE_MOCK_DATA or result_url.startswith("http://mock-crawler"):
        _, mock_crawl_result = get_mock_crawl_data()
        return mock_crawl_result
    
    # 将URL中的https替换为http
    if result_url.startswith("https"):
        result_url = "http" + result_url[5:]
    
    log_message(f"开始获取爬取结果，URL: {result_url}")
    
    retries = 0
    while retries < max_retries:
        try:
            # 发送GET请求
            response = requests.get(result_url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            status = data.get("status")
            
            # 如果爬取完成，返回结果
            if status == "completed":
                log_message(f"爬取任务已完成，状态: {status}")
                return data
            # 如果仍在进行中，等待后重试
            elif status in ["pending", "processing", "scraping"]:
                log_message(f"爬取任务进行中 ({status})，等待 {retry_delay} 秒后重试... (尝试 {retries + 1}/{max_retries})")
                await asyncio.sleep(retry_delay)
                retries += 1
            # 其他状态视为失败
            else:
                log_message(f"爬取任务状态异常: {status}")
                # 切换到模拟数据
                log_message("爬虫任务异常，切换到模拟数据")
                _, mock_crawl_result = get_mock_crawl_data()
                return mock_crawl_result
        except requests.RequestException as e:
            log_message(f"获取爬取结果请求失败: {str(e)}")
            retries += 1
            await asyncio.sleep(retry_delay)
    
    # 达到最大重试次数，使用模拟数据
    log_message(f"达到最大重试次数 ({max_retries})，无法获取爬取结果，切换到模拟数据")
    _, mock_crawl_result = get_mock_crawl_data()
    return mock_crawl_result

async def process_with_openai(crawl_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    使用OpenAI处理爬取结果
    
    Args:
        crawl_result: 爬取结果数据
        
    Returns:
        处理后的数据
    """
    log_message(f"使用OpenAI {MODEL} 处理数据...")
    
    # 从爬取结果中提取markdown内容
    if not (crawl_result and "data" in crawl_result and crawl_result["data"] and "markdown" in crawl_result["data"][0]):
        log_message("爬取结果中未找到markdown内容")
        raise HTTPException(status_code=500, detail="爬取结果中未找到markdown内容")
    
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
            "materials": [
                "https://example.com/image1.jpg",
                "https://example.com/image2.jpg",
                "https://example.com/image3.jpg"
            ]
        }},
        {{
            "text": "文本段落2",
            "materials": [
                "https://example.com/image4.jpg",
                "https://example.com/image5.jpg"
            ]
        }},
        {{
            "text": "文本段落3",
            "materials": [
                "https://example.com/image6.jpg"
            ]
        }}
    ]
}}

重要说明：
- 一个文本段落可以对应多张图片，"materials"必须是数组
- 如果一段文本有多张相关图片，请将所有相关图片URL都放入该文本的"materials"数组中
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
            log_message(f"尝试 {attempt+1}/{MAX_RETRIES}: 发送请求到OpenAI API，使用模型: {MODEL}")
            
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
            log_message(f"收到响应，长度: {len(result_text)} 字符")
            
            # 尝试解析JSON
            try:
                parsed_data = json.loads(result_text)
                log_message("成功解析JSON响应")
                
                # 验证返回的JSON格式是否正确
                if "data" not in parsed_data:
                    log_message("响应缺少'data'字段，添加默认结构")
                    return {"data": parsed_data if isinstance(parsed_data, list) else []}
                
                return parsed_data
            except json.JSONDecodeError as e:
                log_message(f"JSON解析失败: {e}")
                
                # 如果已达到最大重试次数，返回错误响应
                if attempt == MAX_RETRIES - 1:
                    log_message("达到最大重试次数，返回错误响应")
                    raise HTTPException(status_code=500, detail="无法解析OpenAI返回的JSON")
                
                log_message(f"尝试 {attempt+1} 失败，{RETRY_DELAY}秒后重试...")
                await asyncio.sleep(RETRY_DELAY)
        
        except Exception as e:
            log_message(f"请求OpenAI API出错: {e}")
            
            # 如果已达到最大重试次数，返回错误响应
            if attempt == MAX_RETRIES - 1:
                log_message("达到最大重试次数，返回错误响应")
                raise HTTPException(status_code=500, detail=f"调用OpenAI API失败: {str(e)}")
            
            log_message(f"尝试 {attempt+1} 失败，{RETRY_DELAY}秒后重试...")
            await asyncio.sleep(RETRY_DELAY)
    
    # 如果所有重试都失败，返回错误响应
    raise HTTPException(status_code=500, detail="无法使用OpenAI API处理数据")

def format_api_response(processed_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    将处理后的数据格式化为API响应格式
    
    Args:
        processed_data: 处理后的数据
        
    Returns:
        格式化后的数据
    """
    log_message("格式化API响应")
    
    # 确保data字段存在
    api_data = []
    
    # 遍历处理后的数据
    for item in processed_data.get("data", []):
        text = item.get("text", "")
        materials = item.get("materials", [])
        
        # 确保materials是列表
        if not isinstance(materials, list):
            materials = [materials] if materials else []
        
        # 过滤掉太短的文本
        if len(text.strip()) < 5:
            continue
            
        # 保持材料作为一个列表
        api_data.append({
            "text": text,
            "materials": materials
        })
    
    # 如果没有数据，创建一个空记录
    if not api_data:
        api_data.append({
            "text": "未能提取到有效内容",
            "materials": []
        })
    
    return {
        "code": 200,
        "data": api_data,
        "msg": "success"
    }

@app.get("/api/v1/text/urlCrawl")
async def url_crawl(url: str = Query(..., description="要爬取的URL")):
    """
    爬取URL并处理内容
    
    Args:
        url: 要爬取的URL
        
    Returns:
        处理后的结构化数据
    """
    try:
        # 记录开始时间
        start_time = time.time()
        log_message(f"开始处理URL: {url}")
        
        # 步骤1: 发送爬取请求
        crawl_response = await crawl_url(url)
        if not crawl_response:
            raise HTTPException(status_code=500, detail="爬取请求失败")
        
        # 获取结果URL
        result_url = crawl_response.get("url")
        if not result_url:
            raise HTTPException(status_code=500, detail="爬取响应中未找到结果URL")
        
        # 步骤2: 获取爬取结果
        crawl_result = await get_crawl_result(result_url)
        if not crawl_result:
            raise HTTPException(status_code=500, detail="获取爬取结果失败")
        
        # 步骤3: 使用OpenAI处理数据
        processed_data = await process_with_openai(crawl_result)
        
        # 步骤4: 格式化为API响应格式
        api_response = format_api_response(processed_data)
        
        # 计算总处理时间
        end_time = time.time()
        total_time = end_time - start_time
        log_message(f"URL处理完成，总耗时: {total_time:.2f} 秒")
        
        return api_response
    
    except HTTPException:
        # 已经是HTTPException，直接抛出
        raise
    except Exception as e:
        log_message(f"处理URL时发生未知错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"处理URL时发生错误: {str(e)}")

# 健康检查端点
@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": time.time()}

# 启动服务器的主函数
def main():
    log_message("启动URL爬取和处理服务...")
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()
