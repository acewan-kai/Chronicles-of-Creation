"""
P0 MVP - FastAPI 主入口 (集成core模块)
"""

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
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
    ActionExecutor, ActionResult
)
from app.core.sandbox.event_dispatcher import EventDispatcher, EventType
from app.core.events.event_store import EventStore, Event as DBEvent
from app.core.events.query_engine import QueryEngine
from app.core.knowledge.lorebook import Lorebook, LoreEntry
from app.core.knowledge.knowledge_graph import KnowledgeGraph, KnowledgeNode, KnowledgeRelation, NodeType, RelationType
from app.core.knowledge.budget_manager import BudgetManager
from app.core.agent.agent import Agent, AgentConfig, MemoryStream
from app.core.agent.planner import Planner
from app.core.agent.reflector import Reflector
from app.core.agent.dialogue import DialogueManager, DialogueIntent
from app.core.ws_manager import ws_manager
from app.core.scoring.scorer import AestheticScorer
from app.core.scoring.behavior_evaluator import BehaviorEvaluator, EvalTracker
from app.core.sandbox.narrative_extractor import NarrativeExtractor
from app.core.sandbox.story_sifter import StorySifter
from app.core.sandbox.multi_llm_client import LLMClientFactory, MultiLLMClient, LLMProvider
from app.core.usage_tracker import UsageTracker
from app.core.onboarding import OnboardingGuide

# 加载项目根目录 .env（兼容本地/服务器两种路径层级）
_env_path = Path(__file__).resolve().parent.parent / '.env'   # 服务器: ~/p0-mvp-backend/.env
if not _env_path.exists():
    _env_path = Path(__file__).resolve().parent.parent.parent / '.env'  # 本地: project/.env
load_dotenv(_env_path)

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
        self.budget_manager: Optional[BudgetManager] = None
        self.eval_tracker: Optional[EvalTracker] = None
        self.behavior_evaluator: Optional[BehaviorEvaluator] = None
        self.dialogue_manager: Optional[DialogueManager] = None
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
    """根据环境变量创建LLM客户端（多Provider统一接口）

    支持Provider:
    - deepseek, openai, kimi, minimax, zhipu, qwen, hunyuan, doubao, custom, mock
    - 别名: xiaomi/xiaoai → deepseek; moonshot → kimi; glm → zhipu; etc.

    Returns:
        (client, provider_name)
    """
    factory = LLMClientFactory()
    return factory.create(mode)


def get_llm_cost_estimate(mode_name: str, turn_count: int, npc_count: int) -> dict:
    """估算LLM调用成本"""
    rates = {
        # DeepSeek - ¥0.001/1K tokens (极低价)
        "deepseek": 0.001,
        # OpenAI - $0.0015/1K tokens (gpt-4o-mini)
        "openai": 0.011,
        # Kimi (Moonshot) - ¥0.012/1K tokens
        "kimi": 0.012,
        # MiniMax - ¥0.01/1K tokens
        "minimax": 0.01,
        # 智谱GLM - ¥0.001/1K tokens
        "zhipu": 0.001,
        # 通义千问 - ¥0.002/1K tokens
        "qwen": 0.002,
        # 混元 - ¥0.006/1K tokens
        "hunyuan": 0.006,
        # 豆包 - ¥0.003/1K tokens
        "doubao": 0.003,
        # Custom - 默认0
        "custom": 0.0,
        # Mock - 免费
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
    ctx.budget_manager = BudgetManager(total_chars_per_turn=2000)
    ctx.behavior_evaluator = BehaviorEvaluator()
    ctx.eval_tracker = EvalTracker()
    ctx.dialogue_manager = DialogueManager()

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

    # 为每个Agent创建Planner和Reflector
    for agent in ctx.agents.values():
        agent.planner = Planner(agent.agent_id, planning_interval=10)
        agent.reflector = Reflector(agent.agent_id, reflection_interval=20)
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

    # 从模板加载Lorebook词条
    _load_lorebook_from_template(ctx, template)

    simulations[world_id] = ctx
    return ctx


def _load_lorebook_from_template(ctx: SimulationContext, template: dict):
    """从世界模板加载Lorebook词条"""
    # 地点词条
    for loc in template.get("world", {}).get("locations", []):
        ctx.lorebook.add_entry(LoreEntry(
            key=loc["name"],
            content=loc.get("description", ""),
            aliases=[loc["id"]],
            priority=2,
        ))

    # 势力词条
    for faction in template.get("world", {}).get("factions", []):
        ctx.lorebook.add_entry(LoreEntry(
            key=faction["name"],
            content=faction.get("description", ""),
            aliases=[faction["id"]],
            priority=3,
        ))

    # 世界规则
    for rule in template.get("world", {}).get("rules", []):
        ctx.lorebook.add_entry(LoreEntry(
            key=rule["name"],
            content=rule.get("description", ""),
            aliases=[rule["id"]],
            priority=1,
        ))

    # NPC背景（取前80字作为关键信息）
    for npc in template.get("npcs", []):
        bg = npc.get("background", "").strip()
        if bg:
            lines = bg.split("\n")
            short_bg = lines[0][:120] if lines else bg[:120]
            ctx.lorebook.add_entry(LoreEntry(
                key=npc["name"],
                content=f"{npc.get('role', '')} — {short_bg}",
                aliases=[npc["id"]],
                priority=2,
            ))

    # 世界事件
    for evt in template.get("world_events", []):
        ctx.lorebook.add_entry(LoreEntry(
            key=evt["name"],
            content=evt.get("description", ""),
            aliases=[evt["id"]],
            priority=4,
        ))


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

    # 预算管理：追踪近期互动目标
    recent_targets: set[str] = set()
    # 验收指标累计 (用dict绕过Python闭包nonlocal限制)
    _gauges: dict[str, float] = {"interactions": 0, "story_moments": 0, "elapsed": 0.0, "actions": 0}

    try:
        for turn in range(1, total_turns + 1):
            if not ctx._running:
                break

            ctx.world_state.advance_turn()

            # 每回合分配 Lorebook 注入预算
            budgets = ctx.budget_manager.allocate(ctx.agents, recent_targets, turn)
            recent_targets.clear()

            # 为每个NPC构建任务
            def make_npc_task(agent):
                agent_budget = budgets.get(agent.agent_id, 400)

                async def task():
                    situation = ctx.world_state.to_context()
                    system_prompt = agent.think(situation)

                    # Lorebook上下文注入（使用分配预算）
                    lore_context = ctx.lorebook.inject_context(
                        system_prompt, max_chars=agent_budget
                    )
                    chars_injected = len(lore_context) - len(system_prompt)
                    if lore_context != system_prompt:
                        system_prompt = lore_context
                        ctx.budget_manager.track_usage(
                            agent.agent_id, chars_injected,
                            lore_entries=1
                        )

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

                    # WebSocket: 推送新事件
                    await ws_manager.broadcast(ctx.world_id, "NEW_EVENT", {
                        "turn": turn,
                        "day": ctx.world_state.current_day,
                        "time_of_day": ctx.world_state.time_of_day,
                        "actor": result.actor_name,
                        "action": result.action,
                        "target": result.target,
                        "action_type": result.action_type,
                        "location": result.location,
                        "score": score_result.total_score,
                        "world_mood": ctx.world_state.world_mood,
                    })

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

                    # 追踪近期互动目标 + 验收指标计数
                    if result.target:
                        target_id = name_to_id.get(result.target, result.target)
                        if target_id in ctx.agents:
                            recent_targets.add(target_id)
                    if result.action_type == "interaction":
                        _gauges["interactions"] += 1
                    elif result.action_type == "story_moment":
                        _gauges["story_moments"] += 1
                    _gauges["elapsed"] += result.elapsed_time
                    _gauges["actions"] += 1

                    # 行为一致性评测
                    if ctx.behavior_evaluator:
                        target_rel = None
                        if result.target:
                            tgt_id = name_to_id.get(result.target, result.target)
                            edge_data = ctx.knowledge_graph.graph.get_edge_data(result.actor_id, tgt_id)
                            if edge_data:
                                rel_type = list(edge_data.values())[0].get("type", "")
                                target_rel = rel_type
                        report = ctx.behavior_evaluator.evaluate(
                            agent_id=agent.agent_id,
                            agent_name=agent.config.name,
                            identity=agent.config.identity,
                            personality=agent.config.personality,
                            goals=agent.config.goals,
                            action=result.action,
                            target=result.target,
                            relation_type=target_rel,
                            turn=turn,
                        )
                        ctx.eval_tracker.record(report)

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

            # 周期性反思 (使用agent上已有的reflector，传入LLM)
            if turn % 20 == 0:
                for agent in ctx.agents.values():
                    if agent.reflector and agent.reflector.should_reflect(turn):
                        situation = ctx.world_state.to_context()
                        reflection = await agent.reflector.reflect(
                            current_turn=turn,
                            memory_stream=agent.memory,
                            llm_client=ctx.executor.llm_client,
                            identity=agent.config.identity,
                            personality=agent.config.personality,
                            situation=situation,
                        )
                        if reflection:
                            agent.reflect_simple(reflection.summary, turn)

            # 回合预算结算
            ctx.budget_manager.finish_turn()

            # 计算实时验收指标
            npc_alive = len(ctx.agents)
            interactions = int(_gauges["interactions"])
            story_moments = int(_gauges["story_moments"])
            total_acts = max(1, int(_gauges["actions"]))
            avg_delay = round(_gauges["elapsed"] / total_acts, 2)
            success_rate = round(metrics.success_count / max(1, metrics.npc_count) * 100, 1)
            go_status = npc_alive >= 10 and interactions >= 3 and story_moments >= 1

            # WebSocket: 每回合结束推送状态快照
            await ws_manager.broadcast(ctx.world_id, "TURN_COMPLETE", {
                "turn": turn,
                "day": ctx.world_state.current_day,
                "time_of_day": ctx.world_state.time_of_day,
                "world_mood": ctx.world_state.world_mood,
                "agents": [a.to_dict() for a in ctx.agents.values()],
                "event_count": total_acts,
                "success_count": metrics.success_count,
                "success_rate": success_rate,
                "npc_count": npc_alive,
                "total_npcs_alive": npc_alive,
                "interactions": interactions,
                "story_moments": story_moments,
                "avg_delay": avg_delay,
                "go_status": go_status,
                "graph_edges": ctx.knowledge_graph.get_edges_for_api(),
                "budget": ctx.budget_manager.get_stats(),
                "behavior": ctx.eval_tracker.get_summary() if ctx.eval_tracker else {},
            })

    finally:
        ctx._running = False
        # WebSocket: 推送模拟终止
        await ws_manager.broadcast(ctx.world_id, "STATUS_CHANGE", {
            "status": "stopped",
            "turn": ctx.world_state.current_turn if ctx.world_state else 0,
        })


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


@app.get("/api/worlds/{world_id}/agents", tags=["世界管理"], summary="获取角色列表", description="返回世界上所有NPC的详细信息，包括身份、位置、记忆统计、当前计划等。")
async def list_agents(world_id: str):
    """获取所有角色"""
    ctx = simulations.get(world_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="World not found")
    return {
        "agents": [a.to_dict() for a in ctx.agents.values()],
        "count": len(ctx.agents)
    }


@app.delete("/api/worlds/{world_id}", tags=["世界管理"], summary="删除世界", description="删除世界及其所有相关数据（事件、对话、模拟状态）。删除后不可恢复。")
async def delete_world(world_id: str):
    """删除世界"""
    if world_id not in worlds_db:
        raise HTTPException(status_code=404, detail="World not found")

    # 停止模拟
    ctx = simulations.get(world_id)
    if ctx:
        ctx.stop()
        simulations.pop(world_id, None)

    # 删除事件数据库
    if ctx and ctx.event_store:
        import os
        db_path = ctx.event_store.db_path
        jsonl_path = ctx.event_store.jsonl_path
        if os.path.exists(db_path):
            os.remove(db_path)
        if os.path.exists(jsonl_path):
            os.remove(jsonl_path)

    # 从数据库移除
    worlds_db.pop(world_id, None)
    usage_tracker.end_session(world_id)

    return {"status": "deleted", "world_id": world_id}


@app.patch("/api/worlds/{world_id}/agents/{agent_id}", tags=["世界管理"], summary="更新角色信息", description="修改NPC的名称、身份、性格等属性。用于用户自定义角色。")
async def update_agent(world_id: str, agent_id: str, req: dict):
    """更新角色信息"""
    ctx = simulations.get(world_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="World not found")

    agent = ctx.agents.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # 更新字段
    if "name" in req:
        agent.config.name = req["name"]
    if "identity" in req:
        agent.config.identity = req["identity"]
    if "personality" in req:
        agent.config.personality = req["personality"]

    return {"agent": agent.to_dict()}


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


@app.get("/api/worlds/{world_id}/behavior", tags=["世界管理"], summary="行为一致性评测", description="获取NPC行为与角色设定的一致性评分：身份/性格/目标/关系四维度+总体趋势。")
async def get_world_behavior(world_id: str):
    ctx = simulations.get(world_id)
    if not ctx or not ctx.eval_tracker:
        return {"behavior": None, "message": "Behavior evaluator not initialized"}
    return {"behavior": ctx.eval_tracker.get_summary()}


@app.get("/api/worlds/{world_id}/budget", tags=["世界管理"], summary="Lorebook预算使用", description="获取World Info注入预算的分配与使用统计，按角色优先级排序。")
async def get_world_budget(world_id: str):
    ctx = simulations.get(world_id)
    if not ctx or not ctx.budget_manager:
        return {"budget": None, "message": "Budget manager not initialized"}
    return {"budget": ctx.budget_manager.get_stats()}


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
# ═══════════════════════════════════════════════════════════
# Narrative API — A05 叙事提取引擎
# ═══════════════════════════════════════════════════════════

class NarrativeExtractRequest(BaseModel):
    world_id: str
    min_turn: Optional[int] = Field(1, description="起始回合")
    max_turn: Optional[int] = Field(None, description="结束回合")
    max_events: int = Field(50, description="最大事件数")


@app.post("/api/narrative/extract", tags=["叙事提取"], summary="提取叙事章节", description="将指定回合范围内的事件序列转化为带起承转合结构的叙事章节文本。")
async def extract_narrative(req: NarrativeExtractRequest):
    """A05 叙事提取引擎API"""
    ctx = simulations.get(req.world_id)
    if not ctx or not ctx.query_engine:
        raise HTTPException(status_code=404, detail="World not found")

    # 查询事件
    if req.max_turn:
        events = await ctx.query_engine.get_events_by_turns(req.min_turn, req.max_turn)
    else:
        events = await ctx.query_engine.store.query(
            turn_range=(req.min_turn, 9999),
            limit=req.max_events
        )

    if not events:
        return {"chapter": None, "message": "No events found in specified range"}

    # 使用叙事提取器
    extractor = NarrativeExtractor(max_turns_per_chapter=20)
    llm_client = ctx.executor.llm_client if ctx.executor else None

    chapter = await extractor.extract(events, llm_client=llm_client)

    return {"chapter": extractor.to_dict(chapter)}


@app.get("/api/worlds/{world_id}/narrative/preview", tags=["世界管理"], summary="预览章节叙事", description="快速预览指定回合范围内的事件叙事（轻量版，不调用LLM）。")
async def preview_narrative(world_id: str, min_turn: int = 1, max_turn: int = 20):
    ctx = simulations.get(world_id)
    if not ctx or not ctx.query_engine:
        raise HTTPException(status_code=404, detail="World not found")

    events = await ctx.query_engine.get_events_by_turns(min_turn, max_turn)
    if not events:
        return {"preview": None, "message": "No events found"}

    extractor = NarrativeExtractor()
    # 使用fallback模式（无LLM）
    chapter = await extractor.extract(events, llm_client=None)

    return {"preview": extractor.to_dict(chapter)}


# ═══════════════════════════════════════════════════════════
# Story Sifting API — E01-E03 故事淘洗引擎
# ═══════════════════════════════════════════════════════════

class StorySiftRequest(BaseModel):
    world_id: str
    min_turn: Optional[int] = Field(1, description="起始回合")
    max_turn: Optional[int] = Field(None, description="结束回合")
    min_quality: float = Field(0.3, description="最低质量阈值(0-1)")
    max_slices: int = Field(10, description="最多返回切片数")


@app.post("/api/story/sift", tags=["故事淘洗"], summary="筛选叙事切片", description="从指定回合范围内的事件中筛选高价值叙事切片，按三维度（意外性/逻辑性/情感）评分排序。")
async def sift_story(req: StorySiftRequest):
    """E02 叙事切片发现API"""
    ctx = simulations.get(req.world_id)
    if not ctx or not ctx.query_engine:
        raise HTTPException(status_code=404, detail="World not found")

    # 查询事件
    if req.max_turn:
        events = await ctx.query_engine.get_events_by_turns(req.min_turn, req.max_turn)
    else:
        events = await ctx.query_engine.store.query(
            turn_range=(req.min_turn, 9999),
            limit=500
        )

    if not events:
        return {"slices": [], "message": "No events found"}

    # 使用故事淘洗引擎
    sifter = StorySifter()
    result = await sifter.sift(events, min_quality=req.min_quality, max_slices=req.max_slices)

    return sifter.to_api_response(result)


class StoryRewriteRequest(BaseModel):
    world_id: str
    slice_id: str
    start_turn: int
    end_turn: int


@app.post("/api/story/rewrite", tags=["故事淘洗"], summary="重写叙事切片", description="将指定叙事切片重写为可读的章节文本（调用LLM）。")
async def rewrite_story(req: StoryRewriteRequest):
    """E03 LLM文本化重写API"""
    ctx = simulations.get(req.world_id)
    if not ctx or not ctx.query_engine:
        raise HTTPException(status_code=404, detail="World not found")

    # 获取切片内事件
    events = await ctx.query_engine.get_events_by_turns(req.start_turn, req.end_turn)
    if not events:
        return {"rewrite": None, "message": "No events found in slice"}

    # 构造切片对象
    actors = set()
    for e in events:
        if hasattr(e, 'actor_name') and e.actor_name:
            actors.add(e.actor_name)
        if hasattr(e, 'target_name') and e.target_name:
            actors.add(e.target_name)

    from app.core.sandbox.story_sifter import NarrativeSlice, SliceScores, SliceQuality
    slice_obj = NarrativeSlice(
        slice_id=req.slice_id,
        start_turn=req.start_turn,
        end_turn=req.end_turn,
        event_count=len(events),
        core_actors=list(actors)[:5],
        core_action=events[0].action if hasattr(events[0], 'action') else "事件",
        setup="",
        development="",
        climax="",
        quality=SliceQuality.GOOD,
        scores=SliceScores(),
    )

    # 使用故事淘洗引擎重写
    sifter = StorySifter()
    llm_client = ctx.executor.llm_client if ctx.executor else None
    rewrite_text = await sifter.rewrite_slice(slice_obj, events, llm_client=llm_client)

    return {"rewrite": rewrite_text}


# ═══════════════════════════════════════════════════════════
# Dialogue API — C03 智能体对话系统
# ═══════════════════════════════════════════════════════════

class DialogueRequest(BaseModel):
    world_id: str
    speaker_a_id: str = Field(..., description="发言方A的agent_id")
    speaker_b_id: str = Field(..., description="发言方B的agent_id")
    topic: str = Field(..., description="对话主题")
    max_turns: int = Field(8, description="最大对话轮数")


@app.post("/api/dialogue/generate", tags=["智能体对话"], summary="生成NPC对话", description="生成两个NPC之间的自然语言对话，写入双方记忆流。")
async def generate_dialogue(req: DialogueRequest):
    """C03 智能体对话生成API"""
    ctx = simulations.get(req.world_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="World not found")

    # 获取Agent
    agent_a = ctx.agents.get(req.speaker_a_id)
    agent_b = ctx.agents.get(req.speaker_b_id)

    if not agent_a or not agent_b:
        raise HTTPException(status_code=404, detail="Agent not found")

    # 获取上下文
    context = ctx.world_state.to_context() if ctx.world_state else ""

    # 生成对话
    llm_client = ctx.executor.llm_client if ctx.executor else None

    if not llm_client:
        return {"dialogue": None, "message": "No LLM client available, use mock mode"}

    dialogue = await ctx.dialogue_manager.generate_dialogue(
        speaker_a=agent_a,
        speaker_b=agent_b,
        topic=req.topic,
        context=context,
        llm_client=llm_client,
        max_turns=req.max_turns,
    )

    # 写入记忆流
    current_turn = ctx.world_state.current_turn if ctx.world_state else 0
    ctx.dialogue_manager.write_to_memory(
        dialogue, agent_a, agent_b, current_turn
    )

    return {"dialogue": ctx.dialogue_manager.to_dict(dialogue)}


class DialogueHistoryRequest(BaseModel):
    world_id: str
    agent_a_id: str
    agent_b_id: str


@app.post("/api/dialogue/history", tags=["智能体对话"], summary="获取对话历史", description="获取两个NPC之间的历史对话记录。")
async def get_dialogue_history(req: DialogueHistoryRequest):
    """获取对话历史"""
    ctx = simulations.get(req.world_id)
    if not ctx or not ctx.dialogue_manager:
        raise HTTPException(status_code=404, detail="World not found")

    dialogue = ctx.dialogue_manager.get_dialogue_history(
        req.agent_a_id, req.agent_b_id
    )

    if not dialogue:
        return {"dialogue": None, "message": "No dialogue history found"}

    return {"dialogue": ctx.dialogue_manager.to_dict(dialogue)}


# ═══════════════════════════════════════════════════════════
# Novel Export API — 小说导出
# ═══════════════════════════════════════════════════════════

class NovelExportRequest(BaseModel):
    world_id: str
    start_turn: int = Field(1, description="起始回合")
    end_turn: Optional[int] = Field(None, description="结束回合")
    include_dialogue: bool = Field(True, description="包含对话")
    format: str = Field("markdown", description="导出格式: markdown/html")


@app.post("/api/novel/export", tags=["小说导出"], summary="导出小说", description="将世界的事件和对话导出为可读的小说格式（Markdown或HTML）。")
async def export_novel(req: NovelExportRequest):
    """导出小说"""
    ctx = simulations.get(req.world_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="World not found")

    # 获取事件
    events = []
    if ctx.event_store:
        current_max = ctx.world_state.current_turn if ctx.world_state else 100
        event_objs = await ctx.event_store.query(
            turn_range=(req.start_turn, req.end_turn or current_max),
            limit=5000
        )
        events = [e.to_dict() for e in event_objs]

    # 获取对话历史
    dialogues = []
    if ctx.dialogue_manager:
        for (a_id, b_id), dlg in ctx.dialogue_manager._dialogues.items():
            dialogues.append(ctx.dialogue_manager.to_dict(dlg))

    # 世界信息
    world_info = {
        "name": worlds_db.get(req.world_id, {}).get("name", "未命名"),
        "template": worlds_db.get(req.world_id, {}).get("template", "unknown")
    }

    # 导出小说
    from app.core.novel.novel_exporter import NovelExporter

    exporter = NovelExporter(events, dialogues, world_info)
    result = exporter.export(format=req.format)

    return {
        "novel": result.title,
        "world_name": result.world_name,
        "template": result.template,
        "chapters": [
            {
                "num": ch.chapter_num,
                "title": ch.title,
                "turns": ch.turns_covered,
            }
            for ch in result.chapters
        ],
        "total_events": result.total_events,
        "total_dialogues": result.total_dialogues,
        "content_markdown": result.to_markdown() if req.format == "markdown" else result.to_html(),
    }


# ═══════════════════════════════════════════════════════════
# WebSocket 实时推送
# ═══════════════════════════════════════════════════════════

@app.websocket("/ws/{world_id}")
async def websocket_endpoint(ws: WebSocket, world_id: str):
    await ws_manager.connect(world_id, ws)
    try:
        while True:
            # 保持连接，等待客户端消息（心跳 / 断开）
            await ws.receive_text()
    except WebSocketDisconnect:
        await ws_manager.disconnect(world_id, ws)
    except Exception:
        await ws_manager.disconnect(world_id, ws)


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


@app.post("/api/simulate/pause", tags=["模拟控制"], summary="暂停模拟", description="暂停指定世界的模拟运行。可通过 /simulate/resume 恢复。")
async def simulate_pause(req: dict):
    """暂停模拟"""
    world_id = req.get("world_id", "")
    if not world_id:
        raise HTTPException(status_code=400, detail="world_id required")

    ctx = simulations.get(world_id)
    if ctx and ctx.scheduler:
        ctx.scheduler.pause()

    if world_id in worlds_db:
        worlds_db[world_id]["status"] = "paused"

    return {"status": "paused", "world_id": world_id}


@app.post("/api/simulate/resume", tags=["模拟控制"], summary="恢复模拟", description="恢复已暂停的模拟。")
async def simulate_resume(req: dict):
    """恢复模拟"""
    world_id = req.get("world_id", "")
    if not world_id:
        raise HTTPException(status_code=400, detail="world_id required")

    ctx = simulations.get(world_id)
    if ctx and ctx.scheduler:
        ctx.scheduler.resume()

    if world_id in worlds_db:
        worlds_db[world_id]["status"] = "running"

    return {"status": "resumed", "world_id": world_id}


@app.post("/api/simulate/step", tags=["模拟控制"], summary="单步执行", description="让模拟前进指定回合数。请求体：{\"world_id\": \"xxx\", \"turns\": N}。用于细粒度控制模拟进度。")
async def simulate_step(req: dict):
    """单步执行模拟"""
    world_id = req.get("world_id", "")
    turns = req.get("turns", 1)

    if not world_id:
        raise HTTPException(status_code=400, detail="world_id required")

    ctx = simulations.get(world_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="World not found or simulation not initialized")

    # 如果模拟未运行，先启动
    if not ctx.is_running:
        worlds_db[world_id]["status"] = "running"
        ctx._running = True

    # 执行指定回合数
    from app.core.sandbox.turn_scheduler import TurnScheduler
    scheduler = ctx.scheduler or TurnScheduler(total_turns=100)

    current_turn = ctx.world_state.current_turn if ctx.world_state else 0
    end_turn = min(current_turn + turns, 100)

    # 构建NPC任务
    async def run_turns():
        for turn in range(current_turn + 1, end_turn + 1):
            tasks = []
            for agent in ctx.agents.values():
                tasks.append(_make_npc_task(agent, turn, ctx))
            await scheduler.run_turn(turn, tasks)
            # 保存事件
            for agent_id, result in zip(ctx.agents.keys(), tasks):
                if result and hasattr(result, 'action'):
                    from app.core.events.event_store import Event
                    event = Event(
                        turn=turn,
                        actor_id=agent_id,
                        actor_name=ctx.agents[agent_id].config.name,
                        action=result.action,
                        action_type=result.action_type or "normal",
                        location=result.location or "",
                    )
                    if ctx.event_store:
                        await ctx.event_store.save(event)

    try:
        await run_turns()
    except Exception as e:
        return {"status": "error", "world_id": world_id, "message": str(e)}

    return {
        "status": "stepped",
        "world_id": world_id,
        "from_turn": current_turn,
        "to_turn": end_turn,
        "events_generated": turns
    }


def _make_npc_task(agent, turn, ctx):
    """为NPC创建任务"""
    async def task():
        from app.core.sandbox.action_result import ActionResult
        # 简单的模拟任务
        return ActionResult(
            actor_id=agent.agent_id,
            actor_name=agent.config.name,
            action=f"{agent.config.name} 在回合 {turn} 行动",
            target=None,
            target_name=None,
            location=agent.current_location or "未知",
            action_type="normal",
        )
    return task


@app.post("/api/worlds/{world_id}/reset", tags=["世界管理"], summary="重置世界", description="停止模拟并重置世界到初始状态（保留配置但清空事件和记忆）。用于重新运行同一世界设定。")
async def reset_world(world_id: str):
    """重置世界"""
    if world_id not in worlds_db:
        raise HTTPException(status_code=404, detail="World not found")

    ctx = simulations.get(world_id)
    if ctx:
        ctx.stop()
        simulations.pop(world_id, None)

    # 清空事件存储
    if ctx and ctx.event_store:
        await ctx.event_store.clear()

    # 重置状态
    worlds_db[world_id]["status"] = "created"

    return {"status": "reset", "world_id": world_id}


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
