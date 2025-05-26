import os
import sys

# Add project root to path to fix import errors
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from fastapi import APIRouter
from src.api.image_to_ai import router as image_to_ai_router
from src.api.text import router as text_router

router = APIRouter()
router.include_router(image_to_ai_router)
router.include_router(text_router, prefix="/v1")
