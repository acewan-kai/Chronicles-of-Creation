"""
C01 反思模块
周期性总结最近行为模式
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable
from datetime import datetime

from .agent import Memory, MemoryStream, MemoryType


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
    """
    反思模块
    
    周期性分析记忆流，识别行为模式
    """
    
    def __init__(
        self,
        agent_id: str,
        reflection_interval: int = 20,  # 每N回合反思一次
        min_memories_for_reflection: int = 10
    ):
        self.agent_id = agent_id
        self.reflection_interval = reflection_interval
        self.min_memories_for_reflection = min_memories_for_reflection
        
        self.reflections: List[Reflection] = []
        self._reflection_counter = 0
        self._last_reflection_turn = 0
    
    def should_reflect(self, current_turn: int) -> bool:
        """检查是否应该反思"""
        # 距离上次反思是否足够
        if current_turn - self._last_reflection_turn < self.reflection_interval:
            return False
        
        return True
    
    async def reflect(
        self,
        current_turn: int,
        memory_stream: MemoryStream,
        llm_client: Optional[Callable] = None
    ) -> Optional[Reflection]:
        """
        执行反思
        
        分析最近的记忆，识别模式
        """
        memories = memory_stream.get_recent(self.min_memories_for_reflection)
        
        if len(memories) < 5:
            return None
        
        self._reflection_counter += 1
        reflection_id = f"{self.agent_id}_ref_{self._reflection_counter}"
        
        # 简化实现：基于规则的模式识别
        patterns = self._identify_patterns(memories)
        insights = self._generate_insights(memories, patterns)
        
        reflection = Reflection(
            reflection_id=reflection_id,
            turn=current_turn,
            summary=self._summarize_memories(memories),
            patterns=patterns,
            insights=insights,
            recommendations=self._generate_recommendations(patterns, insights)
        )
        
        self.reflections.append(reflection)
        self._last_reflection_turn = current_turn
        
        return reflection
    
    def reflect_simple(
        self,
        current_turn: int,
        memory_stream: MemoryStream
    ) -> Optional[Reflection]:
        """
        简化反思（无需LLM）
        """
        memories = memory_stream.get_recent(self.min_memories_for_reflection)
        
        if len(memories) < 5:
            return None
        
        self._reflection_counter += 1
        reflection_id = f"{self.agent_id}_ref_{self._reflection_counter}"
        
        # 分析模式
        patterns = self._identify_patterns(memories)
        insights = self._generate_insights(memories, patterns)
        
        reflection = Reflection(
            reflection_id=reflection_id,
            turn=current_turn,
            summary=self._summarize_memories(memories),
            patterns=patterns,
            insights=insights,
            recommendations=self._generate_recommendations(patterns, insights)
        )
        
        self.reflections.append(reflection)
        self._last_reflection_turn = current_turn
        
        return reflection
    
    def _identify_patterns(self, memories: List[Memory]) -> List[str]:
        """识别行为模式"""
        patterns = []
        
        # 统计动作类型
        action_count = sum(1 for m in memories if m.memory_type == MemoryType.ACTION)
        observation_count = sum(1 for m in memories if m.memory_type == MemoryType.OBSERVATION)
        
        # 观察模式
        if observation_count > action_count * 2:
            patterns.append("倾向于观察而非行动")
        
        # 互动模式（检查是否与多个角色互动）
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
        
        # 地点模式
        locations = {}
        for m in memories:
            for loc in ["茶馆", "码头", "祠堂", "海边", "村中"]:
                if loc in m.content:
                    locations[loc] = locations.get(loc, 0) + 1
        
        if locations:
            most_common = max(locations.items(), key=lambda x: x[1])
            if most_common[1] >= 3:
                patterns.append(f"经常出现在{most_common[0]}")
        
        return patterns
    
    def _generate_insights(self, memories: List[Memory], patterns: List[str]) -> List[str]:
        """生成洞察"""
        insights = []
        
        # 分析情绪变化
        emotional_words = ["叹息", "悲伤", "喜悦", "愤怒", "犹豫"]
        emotional_count = sum(
            1 for m in memories 
            if any(word in m.content for word in emotional_words)
        )
        
        if emotional_count > len(memories) * 0.3:
            insights.append("情感丰富，对周围事物反应强烈")
        
        # 分析目标进展
        recent_actions = [
            m.content for m in memories 
            if m.memory_type == MemoryType.ACTION
        ][:5]
        
        if recent_actions:
            insights.append(f"最近行动：{recent_actions[0][:30]}...")
        
        return insights
    
    def _summarize_memories(self, memories: List[Memory]) -> str:
        """总结记忆"""
        summary_parts = []
        
        # 统计
        summary_parts.append(f"共{len(memories)}条记忆")
        
        # 动作
        actions = [m for m in memories if m.memory_type == MemoryType.ACTION]
        if actions:
            summary_parts.append(f"其中{len(actions)}条动作记录")
        
        # 观察
        observations = [m for m in memories if m.memory_type == MemoryType.OBSERVATION]
        if observations:
            summary_parts.append(f"{len(observations)}条观察")
        
        return " | ".join(summary_parts)
    
    def _generate_recommendations(
        self,
        patterns: List[str],
        insights: List[str]
    ) -> List[str]:
        """生成建议"""
        recommendations = []
        
        if "倾向于观察而非行动" in patterns:
            recommendations.append("考虑更主动地采取行动")
        
        if len(patterns) < 2:
            recommendations.append("当前行为模式尚不明显，继续观察")
        
        return recommendations
    
    def get_recent_reflections(self, n: int = 3) -> List[Reflection]:
        """获取最近的反思"""
        return self.reflections[-n:]
    
    def get_latest_insight(self) -> Optional[str]:
        """获取最新洞察"""
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
            ]
        }
