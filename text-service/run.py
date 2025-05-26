#!/usr/bin/env python
import os
import sys

# Add project root to path
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 不再直接导入app对象
# from src.main import app
import uvicorn

if __name__ == "__main__":
    # 使用导入字符串而不是app对象
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)