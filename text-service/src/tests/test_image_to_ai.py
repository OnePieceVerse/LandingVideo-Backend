import os
import sys
import unittest
from unittest.mock import patch, MagicMock
import asyncio

# 将项目根目录添加到路径以修复导入错误
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.core.service.image_to_ai_service import ImageToAIService



class TestImageToAIService(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.service = ImageToAIService()
        self.test_url = "https://example.com"
        
    @patch('requests.post')
    @patch('requests.get')
    async def test_process_url(self, mock_get, mock_post):
        # 模拟POST响应
        mock_post_response = MagicMock()
        mock_post_response.ok = True
        mock_post_response.json.return_value = {
            "success": True,
            "id": "test-id",
            "url": "https://9.134.132.205:3002/v1/crawl/test-id"
        }
        mock_post.return_value = mock_post_response
        
        # 模拟GET响应
        mock_get_response = MagicMock()
        mock_get_response.ok = True
        mock_get_response.json.return_value = {
            "success": True,
            "status": "completed",
            "data": [
                {
                    "markdown": "Test text\n\n![](https://example.com/image.jpg)\n\nMore text"
                }
            ]
        }
        mock_get.return_value = mock_get_response
        
        # 调用方法
        result = await self.service.process_url(self.test_url)
        
        # 验证结果
        self.assertEqual(len(result["data"]), 2)
        self.assertEqual(result["data"][0]["text"], "Test text")
        self.assertEqual(result["data"][0]["img"], "https://example.com/image.jpg")
        self.assertEqual(result["data"][1]["text"], "More text")
        self.assertEqual(result["data"][1]["img"], "https://example.com/image.jpg")
        
        # 验证API调用
        mock_post.assert_called_once()
        mock_get.assert_called_once()


if __name__ == '__main__':
    unittest.main() 