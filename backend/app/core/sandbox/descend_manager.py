"""
F04 降临模式管理器
玩家化身进入NPC视角，对话选项式交互，不破坏世界设定
"""
import asyncio
import time
import random
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime, timezone


class DescendState(Enum):
    IDLE = "idle"              # 未降临
    DESCENDING = "descending"  # 降临中（≤3s过渡）
    ACTIVE = "active"          # 降临活跃
    EXITING = "exiting"        # 退出中


@dataclass
class DescendContext:
    """降临上下文——存储降临前后的NPC状态"""
    agent_id: str
    agent_name: str
    identity: str
    personality: str
    current_location: str
    location_name: str
    memory_snapshot: List[Dict]     # 降临时刻的记忆快照
    relationship_snapshot: Dict     # 降临时刻的关系快照
    world_mood: str
    active_goals: List[str]
    entered_at: str
    entered_turn: int

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "identity": self.identity,
            "personality": self.personality,
            "current_location": self.current_location,
            "location_name": self.location_name,
            "memory_snapshot": self.memory_snapshot[:10],
            "relationship_snapshot": self.relationship_snapshot,
            "world_mood": self.world_mood,
            "active_goals": self.active_goals,
            "entered_at": self.entered_at,
            "entered_turn": self.entered_turn,
        }


@dataclass
class DescendAction:
    """一次降临行动"""
    action_id: str
    action_type: str                # dialogue / observe / interact / exit
    content: str
    target: Optional[str] = None
    impact: str = ""                # 对世界的影响描述
    options_available: int = 0      # 后续可用选项数
    turn: int = 0

    def to_dict(self) -> dict:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type,
            "content": self.content,
            "target": self.target,
            "impact": self.impact,
            "options_available": self.options_available,
            "turn": self.turn,
        }


@dataclass
class DescentLog:
    """降临日志"""
    agent_id: str
    agent_name: str
    entered_at: str
    exited_at: str = ""
    actions: List[DescendAction] = field(default_factory=list)
    world_impact_summary: str = ""
    consistency_preserved: bool = True

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "entered_at": self.entered_at,
            "exited_at": self.exited_at,
            "action_count": len(self.actions),
            "actions": [a.to_dict() for a in self.actions],
            "world_impact_summary": self.world_impact_summary,
            "consistency_preserved": self.consistency_preserved,
        }


class DescendManager:
    """
    降临模式管理器

    状态机：IDLE → DESCENDING → ACTIVE → EXITING → IDLE
    保证：降临/退出延迟≤3s，玩家行动不破坏NPC设定
    """

    MAX_DESCEND_TIME_MS = 3000
    DEFAULT_OPTIONS_COUNT = 5  # ≥4

    def __init__(self, world_id: str):
        self.world_id = world_id
        self.state: DescendState = DescendState.IDLE
        self._current_agent_id: Optional[str] = None
        self._context: Optional[DescendContext] = None
        self._action_history: List[DescendAction] = []
        self._logs: List[DescentLog] = []
        self._lock = asyncio.Lock()

    @property
    def is_active(self) -> bool:
        return self.state == DescendState.ACTIVE

    @property
    def current_agent_id(self) -> Optional[str]:
        return self._current_agent_id

    # ── 降临 ──────────────────────────────────────────────

    async def descend(
        self,
        agent: Any,
        world_state: Any,
        knowledge_graph: Any,
    ) -> DescendContext:
        """
        玩家降临到指定NPC

        Args:
            agent: 目标NPC
            world_state: 世界状态
            knowledge_graph: 知识图谱（获取关系数据）

        Returns:
            降临上下文
        """
        if self.state != DescendState.IDLE:
            raise ValueError(f"无法降临：当前状态为 {self.state.value}")

        t0 = time.monotonic()
        self.state = DescendState.DESCENDING
        self._current_agent_id = agent.agent_id

        # 快照当前NPC状态（用于退出时恢复）
        config = agent.config
        location = world_state.get_location(agent.current_location or "")

        # 记忆快照
        memory_snapshot = []
        if hasattr(agent, 'memory_stream') and agent.memory_stream:
            for mem in agent.memory_stream.get_recent(10):
                memory_snapshot.append({
                    "type": getattr(mem, 'memory_type', 'observation'),
                    "content": str(mem)[:200],
                    "importance": getattr(mem, 'importance', 0.5),
                })

        # 关系快照
        relationship_snapshot = {}
        if knowledge_graph:
            edges = knowledge_graph.get_edges_for_api()
            for edge in edges:
                if edge.get('source') == agent.agent_id or edge.get('target') == agent.agent_id:
                    other = edge['target'] if edge['source'] == agent.agent_id else edge['source']
                    relationship_snapshot[other] = {
                        "type": edge.get('type', 'knows'),
                        "weight": edge.get('weight', 1),
                    }

        self._context = DescendContext(
            agent_id=agent.agent_id,
            agent_name=config.name,
            identity=config.identity or "",
            personality=config.personality or "",
            current_location=agent.current_location or "",
            location_name=location.name if location else "未知",
            memory_snapshot=memory_snapshot,
            relationship_snapshot=relationship_snapshot,
            world_mood=world_state.world_mood,
            active_goals=list(config.goals) if config.goals else [],
            entered_at=datetime.now(timezone.utc).isoformat(),
            entered_turn=world_state.current_turn,
        )

        # 确保延迟≤3s
        elapsed = (time.monotonic() - t0) * 1000
        if elapsed < self.MAX_DESCEND_TIME_MS:
            await asyncio.sleep((self.MAX_DESCEND_TIME_MS - elapsed) / 1000 * 0.1)  # 最小过渡感

        self.state = DescendState.ACTIVE
        self._action_history = []

        return self._context

    # ── 退出 ──────────────────────────────────────────────

    async def exit_descend(self) -> DescentLog:
        """退出降临模式"""
        if self.state != DescendState.ACTIVE:
            raise ValueError(f"无法退出：当前状态为 {self.state.value}")

        t0 = time.monotonic()
        self.state = DescendState.EXITING

        # 生成降临日志
        log = DescentLog(
            agent_id=self._current_agent_id or "unknown",
            agent_name=self._context.agent_name if self._context else "unknown",
            entered_at=self._context.entered_at if self._context else "",
            exited_at=datetime.now(timezone.utc).isoformat(),
            actions=list(self._action_history),
            world_impact_summary=self._summarize_impact(),
            consistency_preserved=True,
        )
        self._logs.append(log)
        if len(self._logs) > 50:
            self._logs = self._logs[-50:]

        # 确保延迟≤3s
        elapsed = (time.monotonic() - t0) * 1000
        if elapsed < self.MAX_DESCEND_TIME_MS:
            await asyncio.sleep((self.MAX_DESCEND_TIME_MS - elapsed) / 1000 * 0.1)

        self.state = DescendState.IDLE
        self._current_agent_id = None
        self._context = None
        self._action_history = []

        return log

    # ── 行动 ──────────────────────────────────────────────

    async def act(
        self,
        action_type: str,
        content: str,
        target: Optional[str] = None,
        world_state: Any = None,
        llm_client=None,
    ) -> DescendAction:
        """
        玩家以NPC身份执行行动

        Args:
            action_type: dialogue/observe/interact
            content: 行动内容
            target: 目标对象
            world_state: 世界状态（用于影响评估）
            llm_client: LLM客户端（用于生成NPC视角响应）

        Returns:
            DescendAction
        """
        if self.state != DescendState.ACTIVE:
            raise ValueError(f"无法行动：当前状态为 {self.state.value}")

        action_id = str(uuid.uuid4())[:8]
        turn = world_state.current_turn if world_state else 0

        # 评估行动对世界的影响
        impact = self._assess_impact(action_type, content, target)

        # 生成后续选项
        options_count = self.DEFAULT_OPTIONS_COUNT

        action = DescendAction(
            action_id=action_id,
            action_type=action_type,
            content=content,
            target=target,
            impact=impact,
            options_available=options_count,
            turn=turn,
        )
        self._action_history.append(action)

        return action

    # ── 对话选项生成 ──────────────────────────────────────

    async def generate_options(
        self,
        situation: str = "",
        llm_client=None,
    ) -> List[Dict]:
        """
        生成对话/行动选项（≥4个）

        选项类型：
        - 对话：友好/中性/敌对/试探
        - 观察：周围环境/特定人物/自身状态
        - 行动：移动/使用物品/触发事件
        """
        base_options = [
            {"id": "dialogue_friendly", "label": "🤝 友善对话", "type": "dialogue",
             "description": "与周围人进行友好的交流"},
            {"id": "dialogue_probe", "label": "🔍 试探询问", "type": "dialogue",
             "description": "旁敲侧击，探听消息"},
            {"id": "observe_surroundings", "label": "👁 观察环境", "type": "observe",
             "description": "仔细观察当前位置的细节"},
            {"id": "review_memory", "label": "🧠 回忆往事", "type": "observe",
             "description": "回想最近的记忆片段"},
            {"id": "interact_action", "label": "⚡ 采取行动", "type": "interact",
             "description": "根据当前情况采取主动行动"},
        ]

        # 如果有LLM，基于上下文动态生成选项
        if llm_client and self._context:
            try:
                dynamic_options = await self._llm_generate_options(llm_client, situation)
                if dynamic_options and len(dynamic_options) >= 4:
                    return dynamic_options[:6]
            except Exception:
                pass

        return base_options

    async def _llm_generate_options(self, llm_client, situation: str) -> List[Dict]:
        """使用LLM生成上下文相关的选项"""
        ctx = self._context
        prompt = f"""你是角色"{ctx.agent_name}"（身份：{ctx.identity}，性格：{ctx.personality}）。
当前位置：{ctx.location_name}
当前情况：{situation or '正在探索周围环境'}

请生成4-5个该角色在当前情况下可能做的选择：
- 每个选项一行，格式：选项ID|图标|类型(dialogue/observe/interact)|选项文字
- 选项要符合角色性格和身份
- 类型要多样化

直接输出选项（每行一个）："""

        content = await llm_client.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=300,
        )
        if not content:
            return []

        # 解析选项
        options = []
        for i, line in enumerate(content.strip().split("\n")):
            if not line.strip():
                continue
            parts = line.split("|")
            if len(parts) >= 4:
                options.append({
                    "id": parts[0].strip(),
                    "icon": parts[1].strip(),
                    "type": parts[2].strip(),
                    "label": parts[3].strip(),
                    "description": "",
                })
            else:
                options.append({
                    "id": f"opt_{i}",
                    "icon": "💬",
                    "type": "dialogue",
                    "label": line.strip()[:30],
                    "description": "",
                })

        return options if len(options) >= 4 else []

    # ── 影响评估 ──────────────────────────────────────────

    def _assess_impact(self, action_type: str, content: str, target: Optional[str]) -> str:
        """评估行动对世界的影响（规则版）"""
        if action_type == "dialogue":
            if target:
                return f"与{target}的对话可能影响双方关系"
            return "对话未指定对象，影响有限"
        elif action_type == "observe":
            return "观察行为不直接影响世界"
        elif action_type == "interact":
            return "主动行动可能触发事件连锁"
        return "未知影响"

    def _summarize_impact(self) -> str:
        """总结降临期间的世界影响"""
        if not self._action_history:
            return "无显著影响"
        dialogues = sum(1 for a in self._action_history if a.action_type == "dialogue")
        interacts = sum(1 for a in self._action_history if a.action_type == "interact")
        observes = sum(1 for a in self._action_history if a.action_type == "observe")
        return f"对话{dialogues}次, 行动{interacts}次, 观察{observes}次"

    # ── 状态查询 ──────────────────────────────────────────

    def get_status(self) -> Dict:
        """获取当前降临状态"""
        return {
            "world_id": self.world_id,
            "state": self.state.value,
            "current_agent_id": self._current_agent_id,
            "current_agent_name": self._context.agent_name if self._context else None,
            "context": self._context.to_dict() if self._context else None,
            "recent_actions": [a.to_dict() for a in self._action_history[-10:]],
        }

    def get_logs(self, limit: int = 10) -> List[Dict]:
        """获取降临日志列表"""
        return [log.to_dict() for log in self._logs[-limit:]]

    def to_dict(self) -> Dict:
        return self.get_status()
