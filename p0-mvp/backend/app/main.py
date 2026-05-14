"""
P0 MVP - FastAPI 主入口 (集成core模块)
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import os
import uuid
import asyncio
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# ── Core模块导入 ─────────────────────────────────────────
from app.core.sandbox.world_state import WorldState, Location
from app.core.sandbox.turn_scheduler import TurnScheduler, TurnMetrics
from app.core.sandbox.action_executor import (
    ActionExecutor, MockLLMClient, DeepSeekClient, OpenAIClient, ActionResult
)
from app.core.sandbox.event_dispatcher import EventDispatcher, EventType
from app.core.events.event_store import EventStore, Event as DBEvent
from app.core.events.query_engine import QueryEngine
from app.core.knowledge.lorebook import Lorebook, LoreEntry
from app.core.knowledge.knowledge_graph import KnowledgeGraph, KnowledgeNode, KnowledgeRelation, NodeType, RelationType
from app.core.agent.agent import Agent, AgentConfig, MemoryStream
from app.core.agent.planner import Planner
from app.core.agent.reflector import Reflector
from app.core.scoring.scorer import AestheticScorer
from app.core.usage_tracker import UsageTracker
from app.core.onboarding import OnboardingGuide

# 加载环境变量
load_dotenv()

# ── API标签元数据 ────────────────────────────────────────
tags_metadata = [
    {
        "name": "基础",
        "description": "健康检查与API信息，**最先调用**确认服务可用。",
    },
    {
        "name": "模板",
        "description": "预制世界模板查询，**第二步调用**选择世界类型。",
    },
    {
        "name": "小说管理",
        "description": "小说的增删改查，创建世界后可关联小说。",
    },
    {
        "name": "世界管理",
        "description": "世界创建、查询、事件查看，**核心业务流程**。",
    },
    {
        "name": "模拟控制",
        "description": "启动/停止世界模拟、查看运行状态，**最后一步**。",
    },
]

app = FastAPI(
    title="沉浸式AI小说创作平台 - P0 MVP",
    description="""
## 基于LLM的沉浸式小说创作引擎

让AI角色在虚拟世界中自主行动、互动，创造故事感时刻。

### API调用顺序（推荐测试流程）

```
① GET /health        → 确认服务在线
② GET /templates     → 查看可用世界模板
③ POST /worlds       → 用模板创建新世界
④ POST /simulate/start → 启动世界模拟
⑤ GET /simulate/status → 查看模拟进度
⑥ GET /worlds/{id}/events → 查看AI角色事件
⑦ POST /simulate/stop  → 停止模拟
```
""",
    version="0.1.0",
    openapi_tags=tags_metadata,
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 内存存储 ─────────────────────────────────────────────
worlds_db: Dict[str, dict] = {}
books_db: Dict[str, dict] = {}

# 模拟运行时状态: world_id -> SimulationContext
simulations: Dict[str, Dict[str, Any]] = {}
usage_tracker = UsageTracker()
scorer = AestheticScorer()
DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
DATA_DIR.mkdir(exist_ok=True)


class SimulationContext:
    """世界模拟上下文——绑定所有运行时组件"""
    def __init__(self, world_id: str):
        self.world_id = world_id
        self.llm_mode: str = "mock"
        self.scheduler: Optional[TurnScheduler] = None
        self.dispatcher: Optional[EventDispatcher] = None
        self.event_store: Optional[EventStore] = None
        self.query_engine: Optional[QueryEngine] = None
        self.world_state: Optional[WorldState] = None
        self.agents: Dict[str, Agent] = {}
        self.executor: Optional[ActionExecutor] = None
        self.knowledge_graph: Optional[KnowledgeGraph] = None
        self.lorebook: Optional[Lorebook] = None
        self._sim_task: Optional[asyncio.Task] = None
        self._running: bool = False

    @property
    def is_running(self) -> bool:
        return self._running

    def stop(self):
        self._running = False
        if self._sim_task and not self._sim_task.done():
            self._sim_task.cancel()


# ── LLM客户端工厂 ────────────────────────────────────────
def create_llm_client(mode: str = "auto") -> tuple[Any, str]:
    """根据环境变量创建LLM客户端

    Args:
        mode: "auto"|"mock"|"deepseek"|"openai"

    Returns:
        (client, mode_name) — client实例和实际使用的模式名
    """
    if mode == "mock":
        return MockLLMClient(), "mock"

    if mode == "deepseek":
        key = os.getenv("DEEPSEEK_API_KEY")
        if not key:
            print("[LLM] DEEPSEEK_API_KEY not set, falling back to mock")
            return MockLLMClient(), "mock"
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        return DeepSeekClient(api_key=key, base_url=base_url), "deepseek"

    if mode == "openai":
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            print("[LLM] OPENAI_API_KEY not set, falling back to mock")
            return MockLLMClient(), "mock"
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        return OpenAIClient(api_key=key, base_url=base_url), "openai"

    # auto mode
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if deepseek_key:
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        print(f"[LLM] Auto-selected DeepSeek (DEEPSEEK_API_KEY found)")
        return DeepSeekClient(api_key=deepseek_key, base_url=base_url), "deepseek"

    if openai_key:
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        print(f"[LLM] Auto-selected OpenAI (OPENAI_API_KEY found)")
        return OpenAIClient(api_key=openai_key, base_url=base_url), "openai"

    print("[LLM] No API key found, using MockLLMClient (no real LLM calls)")
    return MockLLMClient(), "mock"


def get_llm_cost_estimate(mode_name: str, turn_count: int, npc_count: int) -> dict:
    """估算LLM调用成本"""
    rates = {
        "deepseek": 0.0001,  # ¥0.0001/1K tokens
        "openai": 0.0015,    # $0.0015/1K tokens (gpt-4o-mini)
        "mock": 0.0,
    }
    est_tokens_per_call = 500  # system_prompt ~200 + user_prompt ~100 + response ~200
    est_calls = turn_count * npc_count
    total_tokens = est_calls * est_tokens_per_call
    rate = rates.get(mode_name, 0)
    return {
        "mode": mode_name,
        "estimated_calls": est_calls,
        "estimated_tokens": total_tokens,
        "estimated_cost": round(total_tokens / 1000 * rate, 4),
        "rate_per_1k_tokens": rate,
    }


# ── 请求模型 ─────────────────────────────────────────────
class CreateWorldRequest(BaseModel):
    name: str = Field(..., description="世界名称，如'测试修仙世界'")
    template: str = Field(..., description="模板ID，可选: cultivation(修仙), wuxia(武侠), urban(都市奇幻)")
    description: Optional[str] = Field("", description="世界描述（可选）")


class CreateBookRequest(BaseModel):
    title: str = Field(..., description="小说标题")
    description: Optional[str] = Field("", description="小说简介（可选）")
    genre: Optional[str] = Field("", description="小说类型，如'玄幻'、'都市'（可选）")
    target_audience: Optional[str] = Field("", description="目标读者，如'男性向'、'女性向'（可选）")


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


# ═══════════════════════════════════════════════════════════
# 基础端点
# ═══════════════════════════════════════════════════════════

@app.get("/", tags=["基础"], summary="根路径", description="返回平台欢迎信息，用于快速确认API服务是否在线。")
async def root():
    return {"message": "沉浸式AI小说创作平台 API", "version": "0.1.0"}


@app.get("/health", tags=["基础"], summary="健康检查", description="返回服务健康状态。**测试第一步**：确认后端正常运行。")
@app.get("/api/health", tags=["基础"], summary="健康检查(旧路径)", description="旧版健康检查端点，建议使用 /health。")
async def health():
    return {"status": "healthy", "version": "0.1.0"}


@app.get("/api/info", tags=["基础"], summary="API信息与调用指南", description="返回API基本信息、所有可用端点列表及推荐的API调用顺序。**测试第一步替代方案**。")
async def api_info():
    return {
        "name": "沉浸式AI小说创作平台",
        "version": "0.1.0",
        "api_call_flow": {
            "step_1": "GET /health — 确认服务在线",
            "step_2": "GET /templates — 查看可用世界模板（修仙/武侠/都市）",
            "step_3": "POST /worlds — 选择模板创建新世界，得到world_id",
            "step_4": "POST /simulate/start — 传入world_id启动模拟",
            "step_5": "GET /simulate/status?world_id=xxx — 查看模拟进度",
            "step_6": "GET /worlds/{world_id}/events — 查看AI角色生成的事件",
            "step_7": "POST /simulate/stop — 停止模拟",
        },
        "endpoints": {
            "root": "/",
            "health": "/health",
            "info": "/api/info",
            "templates": "/api/templates",
            "books": "/api/books",
            "worlds": "/api/worlds",
            "simulate": "/api/simulate"
        }
    }


@app.get("/api/templates", tags=["模板"], summary="获取世界模板列表", description="返回3个预制世界模板：青云仙门(修仙)、江湖风云录(武侠)、深夜事务所(都市奇幻)。**测试第二步**：选择感兴趣的模板ID用于创建世界。")
async def list_templates():
    return {
        "templates": [
            {"id": "cultivation", "name": "青云仙门", "genre": "修仙"},
            {"id": "wuxia", "name": "江湖风云录", "genre": "武侠"},
            {"id": "urban", "name": "深夜事务所", "genre": "都市奇幻"}
        ]
    }


# ═══════════════════════════════════════════════════════════
# Books API
# ═══════════════════════════════════════════════════════════

@app.get("/api/books", tags=["小说管理"], summary="获取小说列表", description="返回所有已创建的小说。创建世界后可在此创建关联的小说项目。")
async def list_books():
    return {"books": list(books_db.values()), "total": len(books_db)}


@app.post("/api/books", tags=["小说管理"], summary="创建小说", description="创建一个新小说项目。请求体字段：title(标题,必填)、description(描述)、genre(类型)、target_audience(目标读者)。")
async def create_book(req: CreateBookRequest):
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


@app.get("/api/books/{book_id}", tags=["小说管理"], summary="获取小说详情", description="根据小说ID获取单本小说的详细信息。")
async def get_book(book_id: str):
    if book_id not in books_db:
        raise HTTPException(status_code=404, detail="Book not found")
    return books_db[book_id]


# ═══════════════════════════════════════════════════════════
# Worlds API
# ═══════════════════════════════════════════════════════════

# 模板世界预设
TEMPLATE_WORLDS = {
    "cultivation": {
        "name": "青云仙门",
        "era": "修仙纪元",
        "locations": [
            {"id": "main_peak", "name": "主峰大殿", "desc": "青云宗最高议事之所，灵气最为浓郁"},
            {"id": "training_hall", "name": "练功堂", "desc": "弟子日常修炼之地，功法典籍满架"},
            {"id": "alchemy_lab", "name": "炼丹房", "desc": "丹师炼制丹药处，炉火常年不熄"},
            {"id": "sword_cliff", "name": "剑崖", "desc": "宗门禁地，剑气环绕，传闻藏有上古剑诀"},
            {"id": "guest_pavilion", "name": "迎客亭", "desc": "接待外客之所，可俯瞰云海"},
            {"id": "spirit_spring", "name": "灵泉洞", "desc": "地下灵泉涌出之处，修炼速度翻倍"},
            {"id": "punishment_hall", "name": "戒律堂", "desc": "惩戒违规弟子之所，气氛森严"},
            {"id": "beast_forest", "name": "妖兽林", "desc": "后山密林，妖兽横行，历练之地"},
        ],
        "agents": [
            {"id": "master_qingxu", "name": "清虚真人", "identity": "青云宗掌门", "personality": "威严刚正，剑道通神"},
            {"id": "senior_mingyue", "name": "明月师姐", "identity": "首席弟子", "personality": "天赋异禀，性格清冷"},
            {"id": "junior_xiaofan", "name": "小凡", "identity": "新入门弟子", "personality": "善良执着，资质平平但勤奋"},
            {"id": "elder_yaowang", "name": "药王长老", "identity": "炼丹堂首座", "personality": "痴迷炼丹，性情古怪"},
            {"id": "rival_heifeng", "name": "黑风", "identity": "魔教探子", "personality": "隐忍狡猾，伺机而动"},
            {"id": "elder_tiejian", "name": "铁剑长老", "identity": "戒律堂首座", "personality": "铁面无私，执法如山"},
            {"id": "sister_linglong", "name": "玲珑师妹", "identity": "内门弟子", "personality": "天真烂漫，医术天赋极高"},
            {"id": "hermit_yunyou", "name": "云游道人", "identity": "散修前辈", "personality": "游戏风尘，深藏不露"},
            {"id": "demon_fox", "name": "九尾", "identity": "妖兽林狐妖", "personality": "修炼千年，亦正亦邪"},
            {"id": "envoy_tianji", "name": "天机使者", "identity": "上界使者", "personality": "神秘莫测，传达天机"},
        ],
        "initial_relationships": [
            {"a": "master_qingxu", "b": "senior_mingyue", "type": "师徒", "weight": 0.9},
            {"a": "master_qingxu", "b": "junior_xiaofan", "type": "师徒", "weight": 0.7},
            {"a": "senior_mingyue", "b": "junior_xiaofan", "type": "师姐弟", "weight": 0.6},
            {"a": "elder_yaowang", "b": "sister_linglong", "type": "师徒", "weight": 0.8},
            {"a": "rival_heifeng", "b": "demon_fox", "type": "暗盟", "weight": 0.5},
            {"a": "elder_tiejian", "b": "rival_heifeng", "type": "怀疑", "weight": -0.3},
            {"a": "hermit_yunyou", "b": "master_qingxu", "type": "故交", "weight": 0.7},
        ],
        "active_events": ["外门弟子失踪事件", "灵泉异动", "十年一度的宗门大比临近"],
    },
    "wuxia": {
        "name": "江湖风云录",
        "era": "明末乱世",
        "locations": [
            {"id": "inn", "name": "悦来客栈", "desc": "江湖消息集散地，三教九流汇聚"},
            {"id": "shaolin", "name": "少林寺", "desc": "武林泰山北斗，七十二绝技之源"},
            {"id": "wudang", "name": "武当山", "desc": "道家武学圣地，太极剑法发祥地"},
            {"id": "gov_office", "name": "知府衙门", "desc": "朝廷势力据点，管辖一方治安"},
            {"id": "black_market", "name": "黑市", "desc": "见不得光的交易场，暗器毒药流通"},
            {"id": "emei", "name": "峨眉派", "desc": "女子剑法名门，倚天剑镇派之宝"},
            {"id": "beggar_den", "name": "丐帮总舵", "desc": "天下第一大帮，消息最灵通之处"},
            {"id": "river_dock", "name": "长江渡口", "desc": "南北水运枢纽，商贾云集"},
        ],
        "agents": [
            {"id": "hero_yang", "name": "杨逸风", "identity": "江湖游侠", "personality": "豪爽侠义，武艺高强"},
            {"id": "spy_liu", "name": "柳如烟", "identity": "神秘女侠", "personality": "冷艳聪慧，身世成谜"},
            {"id": "master_kongjian", "name": "空见大师", "identity": "少林方丈", "personality": "慈悲为怀，看透世情"},
            {"id": "official_zhao", "name": "赵明远", "identity": "知府", "personality": "清廉正直，心怀天下"},
            {"id": "bandit_wang", "name": "王霸道", "identity": "黑风寨寨主", "personality": "凶狠贪婪，欺压百姓"},
            {"id": "nun_miejue", "name": "灭绝师太", "identity": "峨眉掌门", "personality": "刚烈严苛，嫉恶如仇"},
            {"id": "beggar_hong", "name": "洪九公", "identity": "丐帮帮主", "personality": "粗犷豪迈，打狗棒法出神入化"},
            {"id": "doctor_xue", "name": "薛神医", "identity": "江湖名医", "personality": "妙手回春，但性情古怪要价极高"},
            {"id": "assassin_wuying", "name": "无影", "identity": "杀手组织头目", "personality": "神秘冷血，拿钱办事"},
            {"id": "prince_rebel", "name": "朱三太子", "identity": "前朝遗孤", "personality": "隐姓埋名，心怀复国之志"},
        ],
        "initial_relationships": [
            {"a": "hero_yang", "b": "spy_liu", "type": "情愫", "weight": 0.7},
            {"a": "hero_yang", "b": "master_kongjian", "type": "忘年交", "weight": 0.8},
            {"a": "bandit_wang", "b": "official_zhao", "type": "敌对", "weight": -0.8},
            {"a": "nun_miejue", "b": "spy_liu", "type": "旧识", "weight": 0.5},
            {"a": "beggar_hong", "b": "hero_yang", "type": "义气之交", "weight": 0.7},
            {"a": "assassin_wuying", "b": "bandit_wang", "type": "雇佣", "weight": 0.3},
            {"a": "prince_rebel", "b": "official_zhao", "type": "暗中联络", "weight": 0.4},
        ],
        "active_events": ["武林大会召开在即", "官府追查前朝余党", "神秘杀手频频作案"],
    },
    "urban": {
        "name": "深夜事务所",
        "era": "现代都市",
        "locations": [
            {"id": "office", "name": "事务所", "desc": "处理超自然委托的秘密基地"},
            {"id": "cafe", "name": "午夜咖啡馆", "desc": "异界生物的中立聚会地"},
            {"id": "hospital", "name": "市立医院", "desc": "频发灵异事件，太平间阴气重"},
            {"id": "old_mansion", "name": "沈家老宅", "desc": "百年凶宅，怨气深重"},
            {"id": "subway", "name": "地铁末班站", "desc": "连接阴阳两界的节点"},
            {"id": "temple", "name": "城隍庙", "desc": "香火旺盛，阴司入口"},
            {"id": "university", "name": "东江大学", "desc": "校园怪谈频发，地下有古墓"},
            {"id": "night_market", "name": "鬼市", "desc": "深夜开启的妖怪集市，只对异类开放"},
        ],
        "agents": [
            {"id": "boss_shen", "name": "沈夜", "identity": "事务所所长", "personality": "冷静理性，能力深不可测"},
            {"id": "partner_bai", "name": "白小葵", "identity": "半妖助手", "personality": "活泼好奇，有治愈能力"},
            {"id": "detective_li", "name": "李警官", "identity": "刑警队长", "personality": "不信鬼神，但总遇到怪事"},
            {"id": "ghost_qing", "name": "阿青", "identity": "地缚灵", "personality": "善良胆小，困在医院的百年游魂"},
            {"id": "vampire_chen", "name": "陈老板", "identity": "吸血鬼咖啡师", "personality": "优雅沉郁，经营午夜咖啡馆"},
            {"id": "exorcist_zhang", "name": "张天师", "identity": "茅山传人", "personality": "古道热肠，但法术时灵时不灵"},
            {"id": "fox_yao", "name": "胡九娘", "identity": "狐妖掌柜", "personality": "鬼市古董商，消息灵通爱财如命"},
            {"id": "student_lin", "name": "林小棠", "identity": "大学生", "personality": "好奇心旺盛，无意中开了天眼"},
            {"id": "judge_zhong", "name": "钟判官", "identity": "城隍庙判官", "personality": "铁面无私，维护阴阳秩序"},
            {"id": "hacker_akira", "name": "Akira", "identity": "黑客", "personality": "技术宅，用现代科技追踪灵异现象"},
        ],
        "initial_relationships": [
            {"a": "boss_shen", "b": "partner_bai", "type": "搭档", "weight": 0.9},
            {"a": "boss_shen", "b": "detective_li", "type": "合作", "weight": 0.6},
            {"a": "vampire_chen", "b": "boss_shen", "type": "老友", "weight": 0.7},
            {"a": "ghost_qing", "b": "partner_bai", "type": "依赖", "weight": 0.8},
            {"a": "fox_yao", "b": "vampire_chen", "type": "生意伙伴", "weight": 0.5},
            {"a": "judge_zhong", "b": "boss_shen", "type": "官方联系", "weight": 0.4},
            {"a": "student_lin", "b": "exorcist_zhang", "type": "师徒", "weight": 0.5},
        ],
        "active_events": ["鬼市年度拍卖会即将举办", "市立医院太平间异动频繁", "东江大学发生第3起学生失踪"],
    }
}


async def _init_world_simulation(world_id: str, template_id: str, world_name: str):
    """初始化世界的模拟上下文"""
    ctx = SimulationContext(world_id)

    # 事件存储
    db_path = DATA_DIR / f"events_{world_id}.db"
    jsonl_path = DATA_DIR / f"events_{world_id}.jsonl"
    ctx.event_store = EventStore(db_path, jsonl_path)
    await ctx.event_store.initialize()
    ctx.query_engine = QueryEngine(ctx.event_store)

    # 事件分发
    ctx.dispatcher = EventDispatcher()

    # 知识图谱
    ctx.knowledge_graph = KnowledgeGraph()
    ctx.lorebook = Lorebook()

    # 世界状态
    template = TEMPLATE_WORLDS.get(template_id, TEMPLATE_WORLDS["cultivation"])
    ctx.world_state = WorldState(
        world_id=world_id,
        world_name=world_name,
        era=template["era"]
    )

    # 加载地点
    for loc_data in template["locations"]:
        loc = Location(
            id=loc_data["id"],
            name=loc_data["name"],
            description=loc_data["desc"]
        )
        ctx.world_state.add_location(loc)

        # 知识图谱节点
        ctx.knowledge_graph.add_node(KnowledgeNode(
            id=loc.id, node_type=NodeType.LOCATION,
            name=loc.name, description=loc.description
        ))

    # 创建智能体
    for agent_data in template["agents"]:
        config = AgentConfig(
            name=agent_data["name"],
            identity=agent_data["identity"],
            personality=agent_data["personality"]
        )
        agent = Agent(agent_id=agent_data["id"], config=config)
        ctx.agents[agent_data["id"]] = agent

        # 知识图谱节点
        ctx.knowledge_graph.add_node(KnowledgeNode(
            id=agent_data["id"], node_type=NodeType.CHARACTER,
            name=agent_data["name"], description=agent_data["identity"]
        ))

    # LLM执行器
    llm_client, llm_mode = create_llm_client(os.getenv("LLM_MODE", "auto"))
    ctx.executor = ActionExecutor(llm_client)
    ctx.llm_mode = llm_mode

    # 回合调度器
    ctx.scheduler = TurnScheduler(total_turns=100, turns_per_day=8)

    # 把智能体随机分布到地点
    loc_ids = list(ctx.world_state.locations.keys())
    for i, agent in enumerate(ctx.agents.values()):
        loc_id = loc_ids[i % len(loc_ids)]
        ctx.world_state.move_npc(agent.agent_id, loc_id)
        agent.update_location(loc_id)

    # 为每个Agent创建Planner并生成初始计划
    for agent in ctx.agents.values():
        agent.planner = Planner(agent.agent_id, planning_interval=10)
        # 生成初始计划（Mock模式用角色化plan，LLM模式用LLM生成）
        situation = ctx.world_state.to_context()
        plan = await agent.planner.generate_plan(
            identity=agent.config.identity,
            personality=agent.config.personality,
            memories=agent.memory.summarize(),
            situation=situation,
            current_turn=0,
            llm_client=llm_client,
        )
        if plan:
            agent.memory.add_plan(f"制定计划: {plan.title}", 0)

    # 加载初始关系边到知识图谱
    _rel_map = {
        "师徒": RelationType.FRIEND, "师姐弟": RelationType.FRIEND, "故交": RelationType.FRIEND,
        "情愫": RelationType.FRIEND, "忘年交": RelationType.FRIEND, "义气之交": RelationType.FRIEND,
        "搭档": RelationType.FRIEND, "老友": RelationType.FRIEND, "依赖": RelationType.FRIEND,
        "暗盟": RelationType.KNOWS, "旧识": RelationType.KNOWS, "雇佣": RelationType.KNOWS,
        "暗中联络": RelationType.KNOWS, "合作": RelationType.KNOWS, "生意伙伴": RelationType.KNOWS,
        "官方联系": RelationType.KNOWS,
        "敌对": RelationType.ENEMY, "怀疑": RelationType.ENEMY,
    }
    for rel in template.get("initial_relationships", []):
        rel_type = _rel_map.get(rel["type"], RelationType.KNOWS)
        ctx.knowledge_graph.add_relation(KnowledgeRelation(
            source=rel["a"], target=rel["b"],
            relation_type=rel_type,
            weight=rel.get("weight", 0.5),
            description=rel["type"],
        ))

    # 注入活跃事件
    for event_desc in template.get("active_events", []):
        ctx.world_state.active_events.append(event_desc)

    simulations[world_id] = ctx
    return ctx


def _update_world_mood(ctx: SimulationContext, metrics):
    """根据回合结果渐进调整世界氛围"""
    mood_cycle = {
        1: ("平静", 0.3), 2: ("暗流涌动", 0.5), 3: ("紧张", 0.6),
        4: ("危机四伏", 0.8), 5: ("风雨欲来", 0.7), 6: ("动荡", 0.9),
        7: ("混乱", 0.95), 8: ("希望萌芽", 0.4), 9: ("重整旗鼓", 0.5),
        10: ("新秩序", 0.6),
    }
    phase = (ctx.world_state.current_day - 1) % 10 + 1
    mood_name, intensity = mood_cycle.get(phase, ("平稳", 0.5))

    # 根据成功率调整
    if metrics.npc_count > 0:
        success_rate = metrics.success_count / metrics.npc_count
        if success_rate < 0.5:
            intensity = min(1.0, intensity + 0.2)
        elif success_rate > 0.9:
            intensity = max(0.2, intensity - 0.1)

    ctx.world_state.update_world_mood(mood_name, intensity)


async def _run_simulation_loop(ctx: SimulationContext, total_turns: int = 100):
    """后台模拟循环"""
    ctx._running = True

    # 构建 name→agent_id 映射（用于解析LLM输出的目标名称）
    name_to_id: dict[str, str] = {}
    for aid, agent in ctx.agents.items():
        name_to_id[agent.config.name] = aid

    try:
        for turn in range(1, total_turns + 1):
            if not ctx._running:
                break

            ctx.world_state.advance_turn()

            # 为每个NPC构建任务
            def make_npc_task(agent):
                async def task():
                    situation = ctx.world_state.to_context()
                    system_prompt = agent.think(situation)
                    user_prompt = f"当前时间：第{ctx.world_state.current_day}天 {ctx.world_state.time_of_day}\n你所在的{agent.current_location}，请决定你的下一步动作。"

                    result = await ctx.executor.execute(
                        agent.agent_id, system_prompt, user_prompt
                    )
                    result.location = agent.current_location

                    # 记录动作
                    agent.act(result.action, turn, target=result.target)
                    if result.target:
                        ctx.world_state.move_npc(result.actor_id, result.location)

                    # 分发事件
                    await ctx.dispatcher.dispatch_action_result(
                        result, turn, ctx.world_state.to_context()
                    )

                    # 评分
                    score_result = scorer.score(result.action)
                    score_result.total_score

                    # 存储事件
                    event = DBEvent(
                        timestamp=datetime.now().isoformat(),
                        turn=turn,
                        day=ctx.world_state.current_day,
                        time_of_day=ctx.world_state.time_of_day,
                        actor_id=result.actor_id,
                        actor_name=result.actor_name,
                        target_name=result.target,
                        action=result.action,
                        action_type=result.action_type,
                        location=result.location,
                        world_mood=ctx.world_state.world_mood,
                        status=result.status,
                        elapsed_time=result.elapsed_time,
                        score=score_result.total_score,
                        raw_response=result.raw_response
                    )
                    await ctx.event_store.save(event)

                    # 动态更新知识图谱关系边
                    if result.target:
                        target_id = name_to_id.get(result.target, result.target)
                        if target_id in ctx.agents or target_id in ctx.knowledge_graph.nodes:
                            ctx.knowledge_graph.update_relation_dynamic(
                                source_id=result.actor_id,
                                target_id=target_id,
                                interaction_type=result.action_type,
                                action_description=result.action,
                            )

                    # 用量追踪
                    usage_tracker.record_npc_action(
                        ctx.world_id, agent.agent_id, turn,
                        action_type=result.action_type
                    )

                    return result
                return task

            tasks = [make_npc_task(agent) for agent in ctx.agents.values()]
            metrics = await ctx.scheduler.run_turn(turn, tasks)

            usage_tracker.record_turn(ctx.world_id, turn, 0)

            # 世界氛围渐进变化 (每10回合微调)
            if turn % 10 == 0:
                _update_world_mood(ctx, metrics)

            # 计划推进 (每回合)
            for agent in ctx.agents.values():
                if agent.planner:
                    agent.planner.progress(turn)

            # 周期性重规划 (每10回合)
            if turn % 10 == 0 and turn > 0:
                for agent in ctx.agents.values():
                    if agent.planner and agent.planner.should_replan(turn):
                        situation = ctx.world_state.to_context()
                        plan = await agent.planner.generate_plan(
                            identity=agent.config.identity,
                            personality=agent.config.personality,
                            memories=agent.memory.summarize(),
                            situation=situation,
                            current_turn=turn,
                            llm_client=ctx.executor.llm_client,
                        )
                        if plan:
                            agent.memory.add_plan(
                                f"制定新计划: {plan.title}", turn
                            )

            # 周期性反思
            if turn % 20 == 0:
                for agent in ctx.agents.values():
                    reflector = Reflector(agent.agent_id)
                    if reflector.should_reflect(turn):
                        reflection = reflector.reflect_simple(turn, agent.memory)
                        if reflection:
                            agent.reflect(reflection.summary, turn)

    finally:
        ctx._running = False


@app.get("/api/worlds", tags=["世界管理"], summary="获取世界列表", description="返回所有已创建的世界。**测试第三步前置**：确认已创建的世界及其ID。")
async def list_worlds():
    return {"worlds": list(worlds_db.values())}


@app.post("/api/worlds", tags=["世界管理"], summary="创建新世界", description="用指定模板创建世界，自动初始化10个NPC、8个地点、角色关系图。请求体字段：name(世界名称,必填)、template(模板ID,必填,可选cultivation/wuxia/urban)。**测试第三步**：创建后得到world_id用于后续步骤。")
async def create_world(req: CreateWorldRequest):
    world_id = str(uuid.uuid4())[:8]

    # 初始化模拟上下文(模板中创建世界状态+智能体等)
    await _init_world_simulation(world_id, req.template, req.name)

    world = World(
        id=world_id,
        name=req.name,
        template=req.template,
        description=req.description,
        created_at=datetime.now().isoformat(),
        status="created"
    )
    worlds_db[world_id] = world.model_dump()

    usage_tracker.start_session(world_id, req.name, req.template)

    return {"world": world.model_dump()}


@app.get("/api/worlds/{world_id}", tags=["世界管理"], summary="获取世界详情", description="返回世界完整信息，包含NPC列表(agents)、地点列表(locations)、知识图谱统计(graph_stats)。")
async def get_world(world_id: str):
    if world_id not in worlds_db:
        raise HTTPException(status_code=404, detail="World not found")

    ctx = simulations.get(world_id)
    world_data = dict(worlds_db[world_id])

    if ctx:
        world_data["agents"] = [
            agent.to_dict() for agent in ctx.agents.values()
        ]
        world_data["locations"] = [
            {"id": loc.id, "name": loc.name, "description": loc.description}
            for loc in ctx.world_state.locations.values()
        ] if ctx.world_state else []
        world_data["graph_stats"] = ctx.knowledge_graph.get_statistics() if ctx.knowledge_graph else {}
        world_data["graph_edges"] = ctx.knowledge_graph.get_edges_for_api() if ctx.knowledge_graph else []

    return world_data


@app.get("/api/worlds/{world_id}/events", tags=["世界管理"], summary="查询世界事件", description="获取AI角色在模拟中生成的事件日志。支持多种筛选：by_turn(按回合)、by_actor(按角色名)、by_type(按类型normal/interaction/story_moment)、by_location(按地点)、min_turn+max_turn(回合范围)。**测试第六步**：查看AI角色的行为和互动。")
async def get_world_events(
    world_id: str,
    limit: int = 100,
    by_turn: Optional[int] = None,
    by_actor: Optional[str] = None,
    by_type: Optional[str] = None,
    by_location: Optional[str] = None,
    min_turn: Optional[int] = None,
    max_turn: Optional[int] = None,
):
    ctx = simulations.get(world_id)
    if not ctx or not ctx.query_engine:
        return {"events": [], "total": 0}

    # 路由到对应查询方法
    if by_turn is not None:
        events = await ctx.query_engine.get_events_by_turn(by_turn)
    elif by_actor:
        events = await ctx.query_engine.get_events_by_actor(by_actor, limit=limit)
    elif by_type:
        events = await ctx.query_engine.store.query(action_type=by_type, limit=limit)
    elif by_location:
        events = await ctx.query_engine.get_location_timeline(by_location, limit=limit)
    elif min_turn is not None and max_turn is not None:
        events = await ctx.query_engine.get_events_by_turns(min_turn, max_turn)
    else:
        events = await ctx.query_engine.store.query(limit=limit)

    return {
        "events": [_event_to_dict(e) for e in events],
        "total": len(events),
        "filters_applied": {
            k: v for k, v in {
                "by_turn": by_turn, "by_actor": by_actor, "by_type": by_type,
                "by_location": by_location, "min_turn": min_turn, "max_turn": max_turn,
            }.items() if v is not None
        }
    }


@app.get("/api/worlds/{world_id}/events/summary", tags=["世界管理"], summary="事件摘要", description="生成世界事件的统计摘要，包括事件总数、互动次数、故事时刻数量等。")
async def get_world_events_summary(world_id: str):
    ctx = simulations.get(world_id)
    if not ctx or not ctx.query_engine:
        return {"error": "world not found"}
    summary = await ctx.query_engine.generate_summary()
    return summary


@app.get("/api/worlds/{world_id}/interactions", tags=["世界管理"], summary="查询角色互动", description="筛选类型为'interaction'的事件，只看角色之间的互动行为。limit参数控制返回数量(默认50)。")
async def get_world_interactions(world_id: str, limit: int = 50):
    ctx = simulations.get(world_id)
    if not ctx or not ctx.query_engine:
        return {"interactions": [], "total": 0}
    events = await ctx.query_engine.store.query(action_type="interaction", limit=limit)
    return {
        "interactions": [_event_to_dict(e) for e in events],
        "total": len(events),
    }


def _event_to_dict(e) -> dict:
    return {
        "id": e.id,
        "turn": e.turn,
        "actor": e.actor_name,
        "action": e.action,
        "target": e.target_name,
        "location": e.location,
        "action_type": e.action_type,
        "score": e.score,
        "timestamp": e.timestamp,
        "world_mood": e.world_mood
    }


@app.get("/api/worlds/{world_id}/metrics", tags=["世界管理"], summary="世界运行指标", description="返回模拟的核心指标：回合数(turns)、事件总数(events)、NPC存活数、互动数(interactions)、故事时刻数(story_moments)、成功率(success_rate)、go_status(P0验收标准是否达标)。")
async def get_world_metrics(world_id: str):
    ctx = simulations.get(world_id)
    usage = usage_tracker.get_world_summary(world_id)

    base = {
        "world_id": world_id,
        "turns": 0,
        "events": 0,
        "llm_calls": 0,
        "tokens": 0,
        "status": worlds_db.get(world_id, {}).get("status", "unknown"),
        "total_npcs_alive": 0,
        "interactions": 0,
        "story_moments": 0,
        "success_rate": "0%",
        "avg_delay": 0,
        "go_status": False
    }

    if ctx and ctx.query_engine:
        metrics = await ctx.event_store.get_metrics()
        base["turns"] = metrics.get("max_turn", 0)
        base["events"] = metrics.get("total_events", 0)
        base["interactions"] = metrics.get("interactions", 0)
        base["story_moments"] = metrics.get("story_moments", 0)
        base["total_npcs_alive"] = len(ctx.agents)
        base["success_rate"] = f"{(metrics.get('success_events', 0) / max(1, metrics.get('total_events', 1)) * 100):.0f}%"
        base["avg_delay"] = metrics.get("avg_elapsed_time", 0)
        base["go_status"] = (
            base["total_npcs_alive"] >= 10 and
            base["interactions"] >= 3 and
            base["story_moments"] >= 1
        )

    if usage:
        base["llm_calls"] = usage.get("llm_calls", 0)
        base["tokens"] = usage.get("tokens", 0)

    return base


@app.post("/api/worlds/{world_id}/start", tags=["模拟控制"], summary="启动模拟(旧路径)", description="旧版启动端点。推荐使用 POST /simulate/start 传入 {\"world_id\": \"xxx\"} 格式。")
async def start_simulation(world_id: str):
    if world_id not in worlds_db:
        raise HTTPException(status_code=404, detail="World not found")

    ctx = simulations.get(world_id)
    if not ctx:
        raise HTTPException(status_code=400, detail="World simulation context not initialized")

    worlds_db[world_id]["status"] = "running"

    # 后台启动模拟
    ctx._sim_task = asyncio.create_task(_run_simulation_loop(ctx, total_turns=100))

    return {"status": "started", "world_id": world_id}


@app.get("/api/worlds/{world_id}/stats", tags=["世界管理"], summary="世界统计(旧路径)", description="旧版统计端点，与 /api/worlds/{id}/metrics 功能相同。")
async def get_world_stats(world_id: str):
    """兼容旧端点"""
    return await get_world_metrics(world_id)


# ═══════════════════════════════════════════════════════════
# Simulation API (前端 api.ts 调用的路径)
# ═══════════════════════════════════════════════════════════

@app.post("/api/simulate/start", tags=["模拟控制"], summary="启动模拟", description="启动指定世界的AI角色模拟。请求体：{\"world_id\": \"xxx\"}(必填)。模拟将在后台运行100回合，10个NPC各自决策行动。**测试第四步**：传入world_id启动。")
async def simulate_start(req: dict):
    """前端路径别名 → /api/worlds/{id}/start"""
    world_id = req.get("world_id", "")
    if not world_id:
        raise HTTPException(status_code=400, detail="world_id required")
    return await start_simulation(world_id)


@app.post("/api/simulate/stop", tags=["模拟控制"], summary="停止模拟", description="停止指定世界的模拟运行。请求体：{\"world_id\": \"xxx\"}(必填)。停止后可以重新启动或查看已有事件。**测试第七步**。")
async def simulate_stop(req: dict):
    """停止模拟"""
    world_id = req.get("world_id", "")
    if not world_id:
        raise HTTPException(status_code=400, detail="world_id required")

    ctx = simulations.get(world_id)
    if ctx:
        ctx.stop()
        usage_tracker.end_session(world_id)
        if world_id in worlds_db:
            worlds_db[world_id]["status"] = "stopped"

    return {"status": "stopped", "world_id": world_id}


@app.get("/api/simulate/status", tags=["模拟控制"], summary="查看模拟状态", description="查询指定世界的模拟运行状态。参数：world_id(必填)。返回：is_running(是否运行中)、turn(当前回合数)、event_count(事件数量)。**测试第五步**：观察回合数是否在增长。")
async def simulate_status(world_id: str = ""):
    """获取模拟状态"""
    if world_id and world_id in simulations:
        ctx = simulations[world_id]
        return {
            "is_running": ctx.is_running,
            "turn": ctx.world_state.current_turn if ctx.world_state else 0,
            "event_count": 0  # 简化
        }
    return {"is_running": False, "turn": 0, "event_count": 0}


# ═══════════════════════════════════════════════════════════
# 无 /api 前缀路由别名 (前端生产环境直连调用)
# ═══════════════════════════════════════════════════════════

@app.get("/info", tags=["基础"], summary="[别名] API信息", description="无/api前缀别名，生产环境使用。")
async def info_alias():
    return await api_info()


@app.get("/templates", tags=["模板"], summary="[别名] 模板列表", description="无/api前缀别名，生产环境使用。")
async def templates_alias():
    return await list_templates()


@app.get("/books", tags=["小说管理"], summary="[别名] 小说列表", description="无/api前缀别名，生产环境使用。")
async def books_list_alias():
    return await list_books()


@app.post("/books", tags=["小说管理"], summary="[别名] 创建小说", description="无/api前缀别名，生产环境使用。")
async def books_create_alias(req: CreateBookRequest):
    return await create_book(req)


@app.get("/books/{book_id}", tags=["小说管理"], summary="[别名] 小说详情", description="无/api前缀别名，生产环境使用。")
async def books_get_alias(book_id: str):
    return await get_book(book_id)


@app.get("/worlds", tags=["世界管理"], summary="[别名] 世界列表", description="无/api前缀别名，生产环境使用。")
async def worlds_list_alias():
    return await list_worlds()


@app.post("/worlds", tags=["世界管理"], summary="[别名] 创建世界", description="无/api前缀别名，生产环境使用。")
async def worlds_create_alias(req: CreateWorldRequest):
    return await create_world(req)


@app.get("/worlds/{world_id}", tags=["世界管理"], summary="[别名] 世界详情", description="无/api前缀别名，生产环境使用。")
async def worlds_get_alias(world_id: str):
    return await get_world(world_id)


@app.get("/worlds/{world_id}/events", tags=["世界管理"], summary="[别名] 查询事件", description="无/api前缀别名，生产环境使用。")
async def worlds_events_alias(
    world_id: str,
    limit: int = 100,
    by_turn: Optional[int] = None,
    by_actor: Optional[str] = None,
    by_type: Optional[str] = None,
    by_location: Optional[str] = None,
    min_turn: Optional[int] = None,
    max_turn: Optional[int] = None,
):
    return await get_world_events(
        world_id, limit, by_turn, by_actor, by_type, by_location, min_turn, max_turn
    )


@app.get("/worlds/{world_id}/metrics", tags=["世界管理"], summary="[别名] 运行指标", description="无/api前缀别名，生产环境使用。")
async def worlds_metrics_alias(world_id: str):
    return await get_world_metrics(world_id)


@app.post("/simulate/start", tags=["模拟控制"], summary="[别名] 启动模拟", description="无/api前缀别名，生产环境使用。")
async def simulate_start_alias(req: dict):
    return await simulate_start(req)


@app.post("/simulate/stop", tags=["模拟控制"], summary="[别名] 停止模拟", description="无/api前缀别名，生产环境使用。")
async def simulate_stop_alias(req: dict):
    return await simulate_stop(req)


@app.get("/simulate/status", tags=["模拟控制"], summary="[别名] 模拟状态", description="无/api前缀别名，生产环境使用。")
async def simulate_status_alias(world_id: str = ""):
    return await simulate_status(world_id)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
