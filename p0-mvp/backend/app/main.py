"""
P0 MVP - FastAPI 主入口
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import os
import uuid
from datetime import datetime

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

# 内存存储 (MVP阶段)
worlds_db = {}
books_db = {}

# 请求模型
class CreateWorldRequest(BaseModel):
    name: str
    template: str
    description: Optional[str] = ""

class CreateBookRequest(BaseModel):
    title: str
    description: Optional[str] = ""
    genre: Optional[str] = ""
    target_audience: Optional[str] = ""

class World(BaseModel):
    id: str
    name: str
    template: str
    description: str
    created_at: str
    status: str = "created"

class Book(BaseModel):
    id: str
    title: str
    description: str
    genre: str
    target_audience: str
    created_at: str
    status: str = "draft"

@app.get("/")
async def root():
    return {"message": "沉浸式AI小说创作平台 API", "version": "0.1.0"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/api/info")
async def api_info():
    """API信息"""
    return {
        "name": "沉浸式AI小说创作平台",
        "version": "0.1.0",
        "endpoints": {
            "root": "/",
            "health": "/health",
            "info": "/api/info",
            "templates": "/api/templates",
            "books": "/api/books",
            "worlds": "/api/worlds"
        }
    }

@app.get("/api/templates")
async def list_templates():
    """列出可用模板"""
    return {
        "templates": [
            {"id": "cultivation", "name": "青云仙门", "genre": "修仙"},
            {"id": "wuxia", "name": "江湖风云录", "genre": "武侠"},
            {"id": "urban", "name": "深夜事务所", "genre": "都市奇幻"}
        ]
    }

# ============= Books API =============
@app.get("/api/books")
async def list_books():
    """列出所有小说"""
    return {"books": list(books_db.values()), "total": len(books_db)}

@app.post("/api/books")
async def create_book(req: CreateBookRequest):
    """创建新小说"""
    book_id = str(uuid.uuid4())[:8]
    book = Book(
        id=book_id,
        title=req.title,
        description=req.description or "",
        genre=req.genre or "未分类",
        target_audience=req.target_audience or "通用",
        created_at=datetime.now().isoformat(),
        status="draft"
    )
    books_db[book_id] = book.model_dump()
    return {"book": book.model_dump()}

@app.get("/api/books/{book_id}")
async def get_book(book_id: str):
    """获取小说详情"""
    if book_id not in books_db:
        raise HTTPException(status_code=404, detail="Book not found")
    return books_db[book_id]

# ============= Worlds API =============
@app.get("/api/worlds")
async def list_worlds():
    """列出所有世界"""
    return {"worlds": list(worlds_db.values())}

@app.post("/api/worlds")
async def create_world(req: CreateWorldRequest):
    """创建新世界"""
    world_id = str(uuid.uuid4())[:8]
    world = World(
        id=world_id,
        name=req.name,
        template=req.template,
        description=req.description,
        created_at=datetime.now().isoformat(),
        status="created"
    )
    worlds_db[world_id] = world.model_dump()
    return {"world": world.model_dump()}

@app.get("/api/worlds/{world_id}")
async def get_world(world_id: str):
    """获取世界详情"""
    if world_id not in worlds_db:
        raise HTTPException(status_code=404, detail="World not found")
    return worlds_db[world_id]

@app.get("/api/worlds/{world_id}/events")
async def get_world_events(world_id: str, limit: int = 100):
    """获取世界事件"""
    if world_id not in worlds_db:
        raise HTTPException(status_code=404, detail="World not found")
    return {"events": [], "total": 0}

@app.post("/api/worlds/{world_id}/start")
async def start_simulation(world_id: str):
    """启动世界模拟"""
    if world_id not in worlds_db:
        raise HTTPException(status_code=404, detail="World not found")
    worlds_db[world_id]["status"] = "running"
    return {"status": "started", "world_id": world_id}

@app.get("/api/worlds/{world_id}/stats")
async def get_world_stats(world_id: str):
    """获取世界统计"""
    if world_id not in worlds_db:
        raise HTTPException(status_code=404, detail="World not found")
    return {
        "world_id": world_id,
        "turns": 0,
        "events": 0,
        "llm_calls": 0,
        "tokens": 0,
        "status": worlds_db[world_id]["status"]
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
