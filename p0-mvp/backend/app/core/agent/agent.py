"""
C01 智能体核心
包含：Agent基类、MemoryStream记忆流（含艾宾浩斯遗忘曲线）
"""

import asyncio
import math
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple, TYPE_CHECKING
from datetime import datetime
from enum import Enum

if TYPE_CHECKING:
    from .planner import Planner


class MemoryType(Enum):
    """记忆类型"""
    OBSERVATION = "observation"  # 观察
    ACTION = "action"           # 动作
    REFLECTION = "reflection"   # 反思
    PLAN = "plan"              # 计划


# ── 艾宾浩斯遗忘曲线配置 ─────────────────────────────

@dataclass
class ForgettingConfig:
    """遗忘曲线参数

    艾宾浩斯公式: retention = e^(-turns_elapsed / strength)
    其中 strength 由记忆类型、重要性、回忆次数共同决定
    """
    # 各类型记忆的基础强度（值越大遗忘越慢）
    base_strength: dict = field(default_factory=lambda: {
        "reflection": 100.0,   # 反思记忆保留最久
        "plan": 70.0,          # 计划记忆
        "action": 50.0,        # 动作记忆
        "observation": 30.0,   # 观察记忆遗忘最快
    })
    # 重要性对强度的影响系数 (strength *= min_strength + importance * strength_range)
    min_strength_mult: float = 0.5   # 最低重要性(0)时，强度×0.5
    max_strength_mult: float = 2.0   # 最高重要性(1)时，强度×2.0
    # 每次recall提升的强度值
    recall_boost: float = 5.0
    # 最近N回合内的记忆永不遗忘
    recent_protection_turns: int = 3
    # 遗忘阈值：retention低于此值的记忆可能被遗忘
    retention_threshold: float = 0.05
    # 软限制：超过此数量时触发遗忘
    soft_limit: int = 80
    # 硬限制：超过此数量时强制遗忘（即使高于阈值）
    hard_limit: int = 100


# 默认遗忘配置
DEFAULT_FORGETTING = ForgettingConfig()


@dataclass
class Memory:
    """记忆条目"""
    id: str
    memory_type: MemoryType
    content: str
    turn: int
    timestamp: str = ""
    importance: float = 0.5  # 重要性 0-1
    tags: List[str] = field(default_factory=list)
    # 遗忘曲线追踪字段
    last_recalled_turn: int = 0  # 最后被回忆的回合
    times_recalled: int = 0      # 被回忆次数

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
        if self.last_recalled_turn == 0:
            self.last_recalled_turn = self.turn

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.memory_type.value,
            "content": self.content,
            "turn": self.turn,
            "timestamp": self.timestamp,
            "importance": self.importance,
            "tags": self.tags,
            "times_recalled": self.times_recalled,
        }


class MemoryStream:
    """
    记忆流 — 基于艾宾浩斯遗忘曲线的智能记忆管理

    核心机制:
    1. 每条记忆有基于时间的衰减曲线: retention = e^(-turns_elapsed / strength)
    2. strength 由记忆类型、重要性、回忆次数共同决定
    3. 最近N回合记忆受保护永不遗忘
    4. 被recall过的记忆获得强度加成（记忆在被使用时更牢固）
    5. 超过soft_limit触发遗忘检查，超过hard_limit强制清理
    """

    def __init__(
        self,
        agent_id: str,
        forgetting_config: Optional[ForgettingConfig] = None,
    ):
        self.agent_id = agent_id
        self.config = forgetting_config or DEFAULT_FORGETTING

        self.memories: List[Memory] = []
        self._next_id = 1
        # 统计
        self.total_forgotten: int = 0
        self.total_added: int = 0
        self._current_turn: int = 0

    def set_turn(self, turn: int):
        """更新当前回合（用于计算衰减）"""
        self._current_turn = turn

    # ── 记忆强度计算 ─────────────────────────────────

    def _get_memory_strength(self, memory: Memory) -> float:
        """计算记忆的综合强度 S

        S = base_strength[type] * importance_mult + recall_boost * times_recalled

        强度越高，遗忘越慢。
        """
        base = self.config.base_strength.get(memory.memory_type.value, 50.0)
        # 重要性乘数: importance 0→0.5x, importance 1→2.0x
        imp_mult = self.config.min_strength_mult + memory.importance * (
            self.config.max_strength_mult - self.config.min_strength_mult
        )
        strength = base * imp_mult + self.config.recall_boost * memory.times_recalled
        return max(1.0, strength)

    def _calculate_retention(self, memory: Memory) -> float:
        """艾宾浩斯遗忘曲线: R = e^(-t / S)

        Returns:
            retention: 0.0 (完全遗忘) ~ 1.0 (完全保留)
        """
        t = max(0, self._current_turn - memory.turn)
        if t == 0:
            return 1.0
        S = self._get_memory_strength(memory)
        return math.exp(-t / S)

    def _is_recent(self, memory: Memory) -> bool:
        """检查是否为最近记忆（受保护）"""
        return (self._current_turn - memory.turn) < self.config.recent_protection_turns

    # ── 添加记忆 ─────────────────────────────────────

    def add(
        self,
        content: str,
        memory_type: MemoryType,
        turn: int,
        importance: float = 0.5,
        tags: Optional[List[str]] = None
    ) -> Memory:
        """添加新记忆"""
        self._current_turn = max(self._current_turn, turn)
        memory = Memory(
            id=f"{self.agent_id}_mem_{self._next_id}",
            memory_type=memory_type,
            content=content,
            turn=turn,
            importance=importance,
            tags=tags or []
        )
        self._next_id += 1
        self.total_added += 1

        # 插入到列表开头
        self.memories.insert(0, memory)

        # 遗忘检查
        self._prune()

        return memory

    def add_observation(self, content: str, turn: int, importance: float = 0.4) -> Memory:
        return self.add(content, MemoryType.OBSERVATION, turn, importance=importance)

    def add_action(self, content: str, turn: int, importance: float = 0.6) -> Memory:
        return self.add(content, MemoryType.ACTION, turn, importance=importance)

    def add_reflection(self, content: str, turn: int, importance: float = 0.8) -> Memory:
        return self.add(content, MemoryType.REFLECTION, turn, importance=importance)

    def add_plan(self, content: str, turn: int) -> Memory:
        return self.add(content, MemoryType.PLAN, turn, importance=0.7)

    # ── 遗忘算法 ─────────────────────────────────────

    def _prune(self):
        """基于艾宾浩斯遗忘曲线的智能遗忘

        遗忘优先级（从高到低）:
        1. 超过 hard_limit → 强制遗忘 retention 最低的
        2. 超过 soft_limit → 遗忘 retention < threshold 的
        3. retention 太低且非recent → 主动遗忘
        """
        if not self.memories:
            return

        # 计算每条记忆的retention
        scored: List[Tuple[Memory, float]] = [
            (m, self._calculate_retention(m)) for m in self.memories
        ]

        # 已达到硬限制 → 强制删除retention最低的记忆
        while len(self.memories) > self.config.hard_limit:
            # 找出retention最低的非recent记忆
            candidates = [(m, r) for m, r in scored if not self._is_recent(m)]
            if not candidates:
                # 所有都是recent，强制保留最新的hard_limit条
                break
            worst_memory, worst_retention = min(candidates, key=lambda x: x[1])
            self._forget(worst_memory, worst_retention, "hard_limit")
            scored = [(m, r) for m, r in scored if m is not worst_memory]

        # 超过软限制 → 遗忘retention低于阈值的
        if len(self.memories) > self.config.soft_limit:
            for memory, retention in scored:
                if len(self.memories) <= self.config.soft_limit:
                    break
                if self._is_recent(memory):
                    continue
                if retention < self.config.retention_threshold:
                    self._forget(memory, retention, "below_threshold")

        # 主动清理：retention极低的非recent记忆（即使未超soft_limit）
        for memory, retention in list(scored):
            if len(self.memories) <= self.config.soft_limit * 0.7:
                break
            if self._is_recent(memory):
                continue
            if retention < 0.01:  # 几乎完全遗忘
                self._forget(memory, retention, "fully_decayed")

    def _forget(self, memory: Memory, retention: float, reason: str):
        """遗忘一条记忆"""
        self.memories.remove(memory)
        self.total_forgotten += 1

    # ── 检索记忆 ─────────────────────────────────────

    def recall(
        self,
        query: str,
        memory_types: Optional[List[MemoryType]] = None,
        limit: int = 10
    ) -> List[Memory]:
        """
        检索相关记忆（关键词匹配 + 遗忘曲线排序）

        被检索到的记忆会获得 recall_boost (被使用=被强化)
        """
        query_lower = query.lower()
        results: List[Tuple[Memory, float]] = []

        for memory in self.memories:
            if memory_types and memory.memory_type not in memory_types:
                continue

            relevance = 0.0
            if query_lower in memory.content.lower():
                relevance = 1.0
            elif any(tag.lower() in query_lower for tag in memory.tags):
                relevance = 0.7

            if relevance > 0:
                # 综合排序: 相关性 × retention
                retention = self._calculate_retention(memory)
                results.append((memory, relevance * retention))

        # 按综合分数排序
        results.sort(key=lambda x: x[1], reverse=True)
        top_memories = [m for m, _ in results[:limit]]

        # recall boost: 被回忆的记忆获得强度加成
        for memory in top_memories:
            memory.last_recalled_turn = self._current_turn
            memory.times_recalled += 1

        return top_memories

    def get_recent(self, n: int = 10) -> List[Memory]:
        """获取最近的N条记忆（按turn倒序）"""
        sorted_memories = sorted(self.memories, key=lambda m: m.turn, reverse=True)
        return sorted_memories[:n]

    def get_context(self, max_chars: int = 1000) -> str:
        """生成记忆上下文（优先高retention记忆）"""
        # 按retention排序，取最牢固的记忆
        scored = [(m, self._calculate_retention(m)) for m in self.memories]
        scored.sort(key=lambda x: x[1], reverse=True)

        context_parts = []
        current_chars = 0

        for memory, retention in scored:
            part = f"[{memory.memory_type.value} r={retention:.2f}] {memory.content}"
            if current_chars + len(part) > max_chars:
                break
            context_parts.append(part)
            current_chars += len(part)

        return "\n".join(context_parts) if context_parts else "无相关记忆"

    def summarize(self, llm_client=None) -> str:
        """返回记忆摘要"""
        if not self.memories:
            return "无记忆"

        recent = self.get_recent(20)
        # 统计retention分布
        retentions = [self._calculate_retention(m) for m in self.memories]
        avg_retention = sum(retentions) / len(retentions) if retentions else 0

        summary = (
            f"共{len(self.memories)}条记忆，"
            f"平均留存率{avg_retention:.1%}，"
            f"已遗忘{self.total_forgotten}条"
        )
        return summary

    # ── 统计与诊断 ───────────────────────────────────

    def get_stats(self) -> dict:
        """获取记忆流统计（用于API返回）"""
        if not self.memories:
            return {
                "total": 0, "avg_retention": 0, "total_forgotten": self.total_forgotten,
                "by_type": {}, "retention_distribution": {"high": 0, "medium": 0, "low": 0}
            }

        retentions = [self._calculate_retention(m) for m in self.memories]
        avg_retention = sum(retentions) / len(retentions)

        by_type = {}
        for m in self.memories:
            t = m.memory_type.value
            by_type[t] = by_type.get(t, 0) + 1

        dist = {"high": 0, "medium": 0, "low": 0}
        for r in retentions:
            if r > 0.5:
                dist["high"] += 1
            elif r > 0.1:
                dist["medium"] += 1
            else:
                dist["low"] += 1

        return {
            "total": len(self.memories),
            "avg_retention": round(avg_retention, 3),
            "total_forgotten": self.total_forgotten,
            "total_added": self.total_added,
            "by_type": by_type,
            "retention_distribution": dist,
        }

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "memory_count": len(self.memories),
            "stats": self.get_stats(),
            "memories": [m.to_dict() for m in self.memories[:20]],  # 只返回前20条
        }


@dataclass
class AgentConfig:
    """智能体配置"""
    name: str
    identity: str  # 身份描述
    personality: str  # 性格特点
    goals: List[str] = field(default_factory=list)  # 短期目标
    relationships: Dict[str, str] = field(default_factory=dict)  # 关系
    
    system_prompt_template: str = """
你扮演{name}，一个{identity}。
性格特点：{personality}
当前情况：{situation}

你的记忆：
{memories}

{relationships_context}

请基于以上信息，决定下一步动作。
"""
    
    def format_system_prompt(
        self,
        situation: str,
        memories: str,
        relationships: str
    ) -> str:
        return self.system_prompt_template.format(
            name=self.name,
            identity=self.identity,
            personality=self.personality,
            situation=situation,
            memories=memories,
            relationships_context=relationships
        )


class Agent:
    """
    智能体

    代表世界中的NPC角色
    包含：配置、记忆流、规划器、当前状态
    """

    def __init__(
        self,
        agent_id: str,
        config: AgentConfig,
        memory_stream: Optional[MemoryStream] = None,
        planner: Optional["Planner"] = None,
    ):
        self.agent_id = agent_id
        self.config = config
        self.memory = memory_stream or MemoryStream(agent_id)
        self.planner = planner  # 规划器（首次计划在初始化后由main设置LLM后生成）

        # 当前状态
        self.current_location = "unknown"
        self.last_action = ""
        self.survival_turns = 0
        self.is_alive = True

        # 内部状态
        self._state: Dict[str, Any] = {}
    
    @property
    def name(self) -> str:
        return self.config.name
    
    def think(self, situation: str) -> str:
        """生成思考——整合记忆+计划+状态"""
        self.memory.set_turn(self.survival_turns)
        memories = self.memory.get_context(max_chars=800)
        relationships = self._format_relationships()

        # 注入计划上下文
        plan_context = ""
        if self.planner:
            plan_context = self.planner.get_action_context()

        # 在system_prompt末尾追加计划上下文
        base_prompt = self.config.format_system_prompt(
            situation=situation,
            memories=memories,
            relationships=relationships
        )
        if plan_context:
            base_prompt += f"\n\n{plan_context}"

        return base_prompt

    def observe(self, content: str, turn: int):
        """记录观察"""
        self.memory.set_turn(turn)
        self.memory.add_observation(content, turn)
    
    def act(self, action: str, turn: int, target: Optional[str] = None):
        """记录动作"""
        self.memory.set_turn(turn)
        content = f"{self.name}：{action}"
        if target:
            content += f" → {target}"

        # 情感分析提升重要性
        importance = self._calc_action_importance(content, target)
        self.memory.add_action(content, turn, importance=importance)
        self.last_action = action
        self.survival_turns += 1

    def reflect(self, reflection: str, turn: int):
        """添加反思"""
        self.memory.set_turn(turn)
        self.memory.add_reflection(reflection, turn, importance=0.8)

    def _calc_action_importance(self, content: str, target: Optional[str]) -> float:
        """计算动作重要性（情感内容+互动=更高重要性）"""
        importance = 0.6
        emotional_words = ["叹息", "悲伤", "喜悦", "愤怒", "思念", "犹豫",
                          "坚定", "微笑", "泪", "心", "忽然", "突然", "命运"]
        if any(w in content for w in emotional_words):
            importance += 0.15
        if target:
            importance += 0.1
        return min(1.0, importance)
    
    def update_location(self, location: str):
        """更新位置"""
        self.current_location = location
    
    def _format_relationships(self) -> str:
        """格式化关系上下文"""
        if not self.config.relationships:
            return "你与他人关系尚不明朗。"
        
        parts = []
        for other, relation in self.config.relationships.items():
            parts.append(f"- 与{other}：{relation}")
        
        return "你与他人关系：\n" + "\n".join(parts)
    
    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "config": {
                "name": self.config.name,
                "identity": self.config.identity,
                "personality": self.config.personality,
                "goals": self.config.goals
            },
            "current_location": self.current_location,
            "last_action": self.last_action,
            "survival_turns": self.survival_turns,
            "is_alive": self.is_alive,
            "memory_count": len(self.memory.memories),
            "memory_stats": self.memory.get_stats(),
            "planner": self.planner.to_dict() if self.planner else None,
        }
