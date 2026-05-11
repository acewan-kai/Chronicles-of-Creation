"""
P0 MVP - FastAPI 主入口
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

app = FastAPI(
    title="沉浸式AI小说创作平台 - P0 MVP",
    description="基于LLM的沉浸式小说创作引擎",
    version="0.1.0"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "沉浸式AI小说创作平台 API", "version": "0.1.0"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


# 导入并注册路由
@app.get("/api/worlds")
async def list_worlds():
    """列出所有世界"""
    return {"worlds": []}


@app.get("/api/worlds/{world_id}")
async def get_world(world_id: str):
    """获取世界详情"""
    return {"world_id": world_id, "name": "雾隐村"}


@app.get("/api/worlds/{world_id}/events")
async def get_world_events(world_id: str, limit: int = 100):
    """获取世界事件"""
    return {"events": []}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
