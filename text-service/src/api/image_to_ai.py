import os
import sys

# 将项目根目录添加到路径以修复导入错误
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, AnyUrl
from typing import Dict, List, Any, Optional

from src.core.service.image_to_ai_service import ImageToAIService

router = APIRouter(prefix="/image-to-ai", tags=["Image to AI"])
image_to_ai_service = ImageToAIService()

class UrlRequest(BaseModel):
    url: str

class AiDataItem(BaseModel):
    text: str
    img: str

class AiResponse(BaseModel):
    code: int
    data: List[AiDataItem]
    msg: str

@router.post("/crawler", response_model=AiResponse)
async def convert_image_to_ai(request: UrlRequest):
    """
    将图片URL转换为AI数据
    
    参数:
    - url: 要转换的URL
    
    返回:
    - 包含文本和图片对的AI数据的字典
    """
    try:
        result = await image_to_ai_service.process_url(request.url)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理URL时出错: {str(e)}") 