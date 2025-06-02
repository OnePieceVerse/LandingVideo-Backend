# URL Crawler and Text Processor Service

这是一个基于FastAPI的Web服务，用于爬取URL内容并使用OpenAI API进行处理。

## 功能特点

- URL内容爬取
- Markdown内容提取
- OpenAI API集成
- 结构化JSON输出
- 完整的日志记录
- Token使用统计
- 健康检查接口

## 项目结构

```
src/
├── api/                # API路由定义
│   └── routes.py      # API端点
├── core/              # 核心业务逻辑
│   └── service/       
│       ├── crawler_service.py   # 爬虫服务
│       └── openai_service.py    # OpenAI服务
├── config/            # 配置文件
│   └── settings.py    # 全局配置
├── main.py           # 应用入口
└── requirements.txt   # 依赖项
```

## 安装

1. 创建虚拟环境：
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

## 配置

1. 设置环境变量：
```bash
export OpenAI_API_KEY="your-api-key"
```

2. 配置服务参数（可选）：
编辑 `config/settings.py` 文件以修改：
- 服务地址和端口
- 爬虫服务URL
- 日志配置
- API参数

## 运行

启动服务：
```bash
python main.py
```

服务将在配置的地址和端口上运行（默认：http://0.0.0.0:8000）。

## API文档

启动服务后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 主要端点

1. URL爬取和处理
```
POST /api/v1/text/urlCrawl?url={url}
```

测试：

```
curl -X POST http://localhost:8008/api/v1/text/urlCrawl \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://cfm.qq.com/web201801/detail.shtml?docid=5701232412837208438"
  }'
```

```
nohup python3 main.py > logs/app.log 2>&1 &
```


2. 健康检查
```
GET /health
```

## 日志

日志文件位于 `logs` 目录，按日期自动轮转。

## 监控

服务包含以下监控特性：
- 请求跟踪ID
- 处理时间统计
- Token使用统计
- 成本估算

## 错误处理

服务实现了完整的错误处理机制：
- HTTP异常处理
- 重试机制
- 超时控制
- 详细的错误日志

## 许可证

MIT 