1.请求CRAWLER_API_BASE_URL获取爬虫结果集
2.轮询问等待10s直到其成功，若超过10s则返回正在爬取，在日志打印 response.data
3.请求 curl -x "" http://127.0.0.1:3002/v1/crawl/53d47cd3-208d-4659-bc11-e79af7b4022a
4.获取最终响应的 data 例如：
content: {"success":true,"status":"completed","completed":1,"total":1,"creditsUsed":1,"expiresAt":"2025-06-03T08:52:28.000Z","data":[{"markdown":"*   ","scrapeId":"61b9af0d-6039-40f7-bf86-aa4fc976217a","sourceURL":"https://cfm.qq.com/web201801/detail.shtml?docid=5701232412837208438","url":"https://cfm.qq.com/web201801/detail.shtml?docid=5701232412837208438","statusCode":200}}]}

然后将 content 用client 去用 prompt 整理成格式化数据 