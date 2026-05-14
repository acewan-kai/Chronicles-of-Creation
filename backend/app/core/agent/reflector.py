"""
C01 反思模块 — LLM驱动的角色化深度反思
"""

import json
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable, TYPE_CHECKING
from datetime import datetime

from .agent import Memory, MemoryStream, MemoryType

if TYPE_CHECKING:
    from ..sandbox.action_executor import BaseLLMClient


# ── LLM反思系统提示词 ──────────────────────────────

REFLECTION_SYSTEM_PROMPT = """你是一位擅长角色心理分析的叙事顾问。你需要为虚构角色生成深度内心反思。

反思要求：
- 以角色的第一人称视角，结合其身份和性格特点进行反思
- 分析最近经历中显露出的人物特质、行为模式和情感倾向
- 洞察要有个性化，不能是泛泛而谈的套话
- 用简洁的中文，summary 2-3句话，每个pattern/insight/recommendation 1句话

返回JSON（不要其他内容）：
{
  "summary": "角色的内心独白，2-3句话，体现其性格和情感",
  "patterns": ["行为模式1", "行为模式2"],
  "insights": ["深层洞察1", "深层洞察2"],
  "recommendations": ["行动建议1", "行动建议2"]
}"""


@dataclass
class Reflection:
    """反思结果"""
    reflection_id: str
    turn: int
    summary: str
    patterns: List[str] = field(default_factory=list)
    insights: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.reflection_id,
            "turn": self.turn,
            "summary": self.summary,
            "patterns": self.patterns,
            "insights": self.insights,
            "recommendations": self.recommendations
        }


class Reflector:
    """反思模块 — LLM驱动的周期性深度反思"""

    def __init__(
        self,
        agent_id: str,
        reflection_interval: int = 20,
        min_memories_for_reflection: int = 10,
        max_memories_for_prompt: int = 15,
    ):
        self.agent_id = agent_id
        self.reflection_interval = reflection_interval
        self.min_memories_for_reflection = min_memories_for_reflection
        self.max_memories_for_prompt = max_memories_for_prompt

        self.reflections: List[Reflection] = []
        self._reflection_counter = 0
        self._last_reflection_turn = 0

    def should_reflect(self, current_turn: int) -> bool:
        return current_turn - self._last_reflection_turn >= self.reflection_interval

    # ── 主入口 ─────────────────────────────────────

    async def reflect(
        self,
        current_turn: int,
        memory_stream: MemoryStream,
        llm_client: Optional[Callable] = None,
        identity: str = "",
        personality: str = "",
        situation: str = "",
    ) -> Optional[Reflection]:
        """执行反思——LLM路径优先，_reflect_simple作为fallback"""
        memories = memory_stream.get_recent(self.min_memories_for_reflection)
        if len(memories) < 5:
            return None

        if llm_client is not None:
            result = await self._reflect_llm(
                current_turn, memories, llm_client,
                identity, personality, situation
            )
            if result is not None:
                return result

        return self._reflect_simple(current_turn, memories)

    # ── LLM反思路径 ────────────────────────────────

    async def _reflect_llm(
        self,
        current_turn: int,
        memories: List[Memory],
        llm_client: Callable,
        identity: str,
        personality: str,
        situation: str,
    ) -> Optional[Reflection]:
        """使用LLM生成角色化深度反思"""
        # 构建记忆叙事行
        narrative_lines = []
        for i, m in enumerate(memories[:self.max_memories_for_prompt]):
            narrative_lines.append(f"[回合{m.turn}] [{m.memory_type.value}] {m.content}")
        narrative_text = "\n".join(reversed(narrative_lines))

        # 前2次反思摘要
        prior_text = "暂无"
        if self.reflections:
            prior_summaries = [r.summary for r in self.reflections[-2:]]
            prior_text = " | ".join(prior_summaries)

        user_prompt = f"""角色身份：{identity}
性格特点：{personality}
当前处境：{situation}

最近经历：
{narrative_text}

此前反思摘要：{prior_text}

请基于以上信息，以{identity}的第一人称视角，生成深度内心反思。"""

        messages = [
            {"role": "system", "content": REFLECTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        try:
            response = await llm_client.generate(messages, temperature=0.8, max_tokens=500)
        except Exception:
            return None

        if not response:
            return None

        data = self._parse_reflection_json(response)
        if data is None:
            return None

        return self._store_reflection(current_turn, data)

    def _parse_reflection_json(self, response: str) -> Optional[dict]:
        """解析LLM返回的JSON（regex提取 + 容错）"""
        try:
            json_match = re.search(r'\{[\s\S]*"summary"[\s\S]*\}', response)
            raw = json_match.group() if json_match else response
            return json.loads(raw)
        except (json.JSONDecodeError, KeyError, AttributeError):
            return None

    # ── 简化反思路径（私有fallback） ────────────────

    def _reflect_simple(
        self,
        current_turn: int,
        memories: List[Memory],
    ) -> Optional[Reflection]:
        """无LLM时的规则模式反思"""
        data = {
            "summary": self._summarize_memories(memories),
            "patterns": self._identify_patterns(memories),
            "insights": self._generate_insights(memories),
            "recommendations": self._generate_recommendations_simple(memories),
        }
        return self._store_reflection(current_turn, data)

    def _store_reflection(self, current_turn: int, data: dict) -> Reflection:
        """存储反思结果（共用）"""
        self._reflection_counter += 1
        reflection_id = f"{self.agent_id}_ref_{self._reflection_counter}"

        reflection = Reflection(
            reflection_id=reflection_id,
            turn=current_turn,
            summary=data.get("summary", ""),
            patterns=data.get("patterns", []),
            insights=data.get("insights", []),
            recommendations=data.get("recommendations", []),
        )

        self.reflections.append(reflection)
        self._last_reflection_turn = current_turn
        return reflection

    # ── 规则模式识别（供_reflect_simple使用） ──────

    def _identify_patterns(self, memories: List[Memory]) -> List[str]:
        patterns = []
        action_count = sum(1 for m in memories if m.memory_type == MemoryType.ACTION)
        observation_count = sum(1 for m in memories if m.memory_type == MemoryType.OBSERVATION)

        if observation_count > action_count * 2:
            patterns.append("倾向于观察而非行动")

        targets = set()
        for m in memories:
            if "→" in m.content:
                parts = m.content.split("→")
                if len(parts) > 1:
                    targets.add(parts[1].strip().split("：")[0])
        if len(targets) >= 3:
            patterns.append("善于社交，与多人互动")
        elif len(targets) == 1:
            patterns.append(f"专注于与{targets.pop()}的互动")

        locations = {}
        for m in memories:
            for loc in ["茶馆", "码头", "祠堂", "海边", "村中", "大殿", "丹房", "客栈"]:
                if loc in m.content:
                    locations[loc] = locations.get(loc, 0) + 1
        if locations:
            most_common = max(locations.items(), key=lambda x: x[1])
            if most_common[1] >= 3:
                patterns.append(f"经常出现在{most_common[0]}")

        return patterns

    def _generate_insights(self, memories: List[Memory]) -> List[str]:
        insights = []
        emotional_words = ["叹息", "悲伤", "喜悦", "愤怒", "犹豫", "思念", "坚定", "泪", "心"]
        emotional_count = sum(1 for m in memories if any(word in m.content for word in emotional_words))
        if emotional_count > len(memories) * 0.3:
            insights.append("情感丰富，对周围事物反应强烈")

        recent_actions = [m.content for m in memories if m.memory_type == MemoryType.ACTION][:5]
        if recent_actions:
            insights.append(f"最近行动：{recent_actions[0][:40]}...")

        return insights

    def _summarize_memories(self, memories: List[Memory]) -> str:
        parts = [f"共{len(memories)}条记忆"]
        actions = [m for m in memories if m.memory_type == MemoryType.ACTION]
        if actions:
            parts.append(f"其中{len(actions)}条动作记录")
        observations = [m for m in memories if m.memory_type == MemoryType.OBSERVATION]
        if observations:
            parts.append(f"{len(observations)}条观察")
        return " | ".join(parts)

    def _generate_recommendations_simple(self, memories: List[Memory]) -> List[str]:
        recommendations = []
        action_count = sum(1 for m in memories if m.memory_type == MemoryType.ACTION)
        observation_count = sum(1 for m in memories if m.memory_type == MemoryType.OBSERVATION)
        if observation_count > action_count * 2:
            recommendations.append("考虑更主动地采取行动")
        if action_count + observation_count < 8:
            recommendations.append("当前行为模式尚不明显，继续观察")
        return recommendations

    # ── 查询 ───────────────────────────────────────

    def get_recent_reflections(self, n: int = 3) -> List[Reflection]:
        return self.reflections[-n:]

    def get_latest_insight(self) -> Optional[str]:
        if self.reflections:
            latest = self.reflections[-1]
            if latest.insights:
                return latest.insights[0]
        return None

    def to_dict(self) -> dict:
        return {
            "reflection_count": len(self.reflections),
            "last_reflection_turn": self._last_reflection_turn,
            "recent_insights": [
                insight
                for r in self.reflections[-3:]
                for insight in r.insights
            ],
            "latest_summary": self.reflections[-1].summary if self.reflections else None,
        }
