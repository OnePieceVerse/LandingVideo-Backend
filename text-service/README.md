# Text Service

一个用于将图片URL转换为AI数据的服务，包括文本和图片对的提取和处理。

## 安装和设置

### 前提条件

- Python 3.8+
- [Ollama](https://github.com/ollama/ollama) 安装并运行
- `deepseek-r1:8b` 模型在Ollama中可用

### 安装步骤

1. 克隆代码库并进入项目目录

```bash
cd text-service
```

2. 安装依赖项

```bash
pip install -r requirements.txt
```

3. 确保Ollama已启动并加载了所需模型

```bash
# 启动Ollama (如果尚未运行)
ollama serve

# 在另一个终端中，拉取所需模型
ollama pull deepseek-r1:8b
```

## 运行服务

启动FastAPI服务器:

```bash
python run.py
```

服务器将在 `http://localhost:8000` 上运行，API文档可在 `http://localhost:8000/docs` 访问。

## API端点

### 图片URL转AI数据 (`/api/image-to-ai/crawler`)

将图片URL转换为AI数据，包括文本和图片对。

**请求:**

```http
POST /api/image-to-ai/crawler
Content-Type: application/json

{
    "url": "https://cfm.qq.com/web201801/detail.shtml?docid=7924797936662049421"
}
```

**响应:**

```json
{
    "code": 200,
    "data": [
        {
            "text": "文本段落1",
            "img": "https://example.com/image1.jpg"
        },
        {
            "text": "文本段落2",
            "img": "https://example.com/image2.jpg"
        }
    ],
    "msg": "success"
}
```

## 测试

### 运行服务测试

要测试服务功能，运行:

```bash
python test_crawler.py
```

该测试将:
1. 测试`ImageToAIService.process_url`方法
2. 如果服务测试成功，询问是否要测试API端点（需要服务器运行中）

## 工作原理

1. **爬虫请求**: 服务首先向爬虫API发送POST请求，获取URL的爬取任务ID
2. **获取爬取结果**: 使用任务ID向爬虫API发送GET请求，获取爬取的Markdown内容
3. **LLM处理**: 使用Ollama调用`deepseek-r1:8b`模型，将Markdown内容处理为结构化的文本和图片对
4. **响应返回**: 返回处理后的数据，包括文本和图片URL
```
curl -X POST http://9.134.132.205:3002/v1/crawl \
    -H 'Content-Type: application/json' \
    -d '{
      "url": "https://cfm.qq.com/web201801/detail.shtml?docid=7924797936662049421",
            "limit": 2000,
      "scrapeOptions": {
        "formats": ["markdown"]
      }
    }'
```

http A的响应：

```
{"success":true,"id":"74c82fd4-3ad9-40a2-a142-e237d3ef5470","url":"https://9.134.132.205:3002/v1/crawl/74c82fd4-3ad9-40a2-a142-e237d3ef5470"}
```



再用响应中的 url 构造 http 请求B，注意是http

```
curl -X GET "http://9.134.132.205:3002/v1/crawl/74c82fd4-3ad9-40a2-a142-e237d3ef5470"
```


http B返回响应是：

```
{"success":true,"status":"completed","completed":1,"total":1,"creditsUsed":1,"expiresAt":"2025-04-27T12:08:51.000Z","data":[{"markdown":"*   [首页](https://cfm.qq.com/m/index.shtml)\n    \n*   [视频](https://cfm.qq.com/m/web201701/video.htm)\n    \n*   [攻略](https://cfm.qq.com/m/web201701/raiders.htm)\n    \n*   [赛事](https://cfm.qq.com/m/web201701/match.htm)\n    \n\n**穿越火线:枪战王者** _原汁原味，CF正版FPS手游_\n\n[下载游戏](https://cfm.qq.com/zlkdatasys/mct/d/play.shtml)\n\n哈喽小伙伴们大家好，奉先无双夺宝已经如期上线了，此次夺宝不仅首发了各种无双系列万化皮肤，还有奉先副武器及近战武器的无双皮肤，本期就带大家来看下蟒蛇-奉先-无双和方天画戟-无双的皮肤展示。\n\n![](https://static.gametalk.qq.com/image/34/1745540974_9de5a53216490310e9d6657f6d260248.jpg)\n\n**【蟒蛇-奉先-无双】**\n\n蟒蛇-奉先装备了无双皮肤以后，整个枪械的颜色变为了蓝粉相间的颜色，枪口处还有蓝色能量在不断闪烁，值得注意的是枪械两边同样装饰有赛博翎羽，静止状态下在随风飘动，给人一种赛博猛将的既视感。\n\n![](https://static.gametalk.qq.com/image/34/1745540971_aa07401eac2e02d68981f77ade2b2fb1.gif)\n\n点击换弹手枪会甩出弹巢，随即有多枚子弹自动装填上，一套动作行云流水，让人眼花缭乱。\n\n![](https://static.gametalk.qq.com/image/34/1745540968_607bd1a6f463a8ce2cba435ec69d1858.gif)\n\n点击切枪枪械会随着手腕转动而旋转一圈，速度之快让人目不暇接。\n\n![](https://static.gametalk.qq.com/image/34/1745540964_2f40668a1cd9b63f0f771c80db086410.gif)\n\n**【实战展示】**\n\n在实战中点位枪械检视按钮，可以看到右手轻轻甩出弹巢，随即转动左轮的弹巢，齿轮的旋转会擦出蓝色的火花，枪械也会由于惯性在抖动，像是在检查子弹是否装填完毕。\n\n![](https://static.gametalk.qq.com/image/34/1745540961_9e9ff0ee348908a7069b654c0d1c6e5c.gif)\n\n随后再利用惯性将弹巢收回枪械中，枪械绕着手指旋转几圈之后一直保持警戒状态，不得不说这个枪械检视功能真的太帅气了。\n\n![](https://static.gametalk.qq.com/image/34/1745540954_665950ceb3940341808d196853fafff7.gif)\n\n点击开火后，枪口火焰的颜色也是科技蓝色，枪口处蓝色的火焰会随着开火而喷射，给人带来了视觉上的享受。\n\n![](https://static.gametalk.qq.com/image/34/1745540951_c7a4bf732a472348329dc0dbab7e9f51.gif)\n\n实战开火后可以看到就连击杀图标都是具有无双皮肤特色的，感觉装备上无双皮肤以后，整个枪械的外观给人一种高科技的感觉。\n\n![](https://static.gametalk.qq.com/image/34/1745540947_e245a395c6858f717aff64a468a12232.gif)\n\n**【方天画戟-无双】**\n\n方天画戟装备了无双皮肤后整个近战也像是变为了高科技产物，近战整体颜色为蓝粉相间，方天画戟的金属枪尖和月牙形利刃不像是古代冷兵器，更像是未来科技制造出来的，荧光蓝色的戟头散发着幽幽蓝光，似乎在吸收着能量一样。\n\n![](https://static.gametalk.qq.com/image/34/1745540941_43de3e32ac1481eeff6db48c3861ee1c.gif)\n\n戟身有多个发光的直刺和挑刺，这是方便用来扎挑敌人的，现在变成了荧光蓝色，手握的地方还能清晰的看到能量环，能量在不断的像前输出，让人看了不寒而栗。\n\n![](https://static.gametalk.qq.com/image/34/1745540938_0148e323bcce67a68b7bc3295b306d51.jpg)\n\n点击切枪，手里的方天画戟-无双会腾空旋转好几圈，而且还会发出蓝色的光芒，随后稳稳落在手里真的很帅气。\n\n![](https://static.gametalk.qq.com/image/34/1745540936_d6f6c7f1346bc0b67e34e231752dec13.gif)\n\n**【实战展示】**\n\n点击近战检视按钮，手里的方天画戟先向后蓄力，能量在不断的像戟头输出，随机方天画戟的枪尖闭合，在手中旋转之后用力刺向前方，同时还能看刺破物体的碎裂动画，真的超级酷炫。\n\n![](https://static.gametalk.qq.com/image/34/1745540932_5c9cf8e7c7ace0cd9447826d1762a79d.gif)\n\n不得不说装备了无双皮肤的方天画戟攻击特效更帅气，在视觉和手感上都是极致的享受。\n\n![](https://static.gametalk.qq.com/image/34/1745540928_828ab40314e7bcac6aac84f358b5d6c2.gif)\n\n**【总结】**\n\n那么以上就是蟒蛇-奉先-无双和方天画戟-无双的皮肤展示，想要凑齐无双皮肤可以直接参与奉先无双夺宝。这种赛博朋克的皮肤相信大家都比较喜爱，不知道各位入手没？\n\n[返回](javascript:history.go(-1);)","metadata":{"author":"Tencent-TGideas","Description":"原汁原味 最CF的手游-穿越火线手游官方网站","Copyright":"Tencent","title":"穿越火线手游攻略中心","viewport":"user-scalable=no, width=device-width, initial-scale=1, maximum-scale=1","Keywords":"穿越火线手游、穿越火线、腾讯游戏、CF的手游、经典玩法、移动射击、CROSSFIRE原班人马倾力打造、","robots":"all","scrapeId":"ae417295-b9c0-44c6-af4c-c7d072e0ed49","sourceURL":"https://cfm.qq.com/web201801/detail.shtml?docid=7924797936662049421","url":"https://cfm.qq.com/web201801/detail.shtml?docid=7924797936662049421","statusCode":200}}]}
```



然后再将data中的数据通过本地的 deepseek-r1:8b  模型转化为

prompt：
```
你是一个专业的JSON数据处理助手。请严格按以下要求处理输入数据：

1. **输入**：原始JSON（Markdown格式），内含多个文本段落和图片链接。
2. **任务**：
   - 提取所有有效的文本段落（删除空行、广告、导航链接等无关内容）。
   - 提取所有图片URL（格式为 `![](...)` 或 `<img>` 标签的链接）。
   - 将文本和图片配对组合（一段文本跟随一张相关图片）。
3. **输出格式**：
```json
{

    "data": [
        {"text": "段落1", "materiels": [

 "https://test.example.com/image1.jpg",
"https://test.example.com/image2.jpg"

]},
        {"text": "段落2", "materiels": [
 "https://test.example.com/image1.jpg",
"https://test.example.com/image2.jpg"
]}
    ]
}

```


转化后的最终响应

```
{
    "code": 200,
    "data": [
        {
            "text": "文本1",
            "img": "https://static.gametalk.qq.com/image/34/1745540932_5c9cf8e7c7ace0cd9447826d1762a79d.gif1"
        },
        {
            "text": "文本2",
            "img": "https://static.gametalk.qq.com/image/34/1745540932_5c9cf8e7c7ace0cd9447826d1762a79d.gif2"
        },
        ...
    ],
    "msg": "successs"
}
```

格式的数组进行响应返回



