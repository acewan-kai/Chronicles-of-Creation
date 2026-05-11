"""
C01 智能体核心
包含：Agent基类、MemoryStream记忆流
"""

import asyncio
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum


class MemoryType(Enum):
    """记忆类型"""
    OBSERVATION = "observation"  # 观察
    ACTION = "action"           # 动作
    REFLECTION = "reflection"   # 反思
    PLAN = "plan"              # 计划


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
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.memory_type.value,
            "content": self.content,
            "turn": self.turn,
            "timestamp": self.timestamp,
            "importance": self.importance,
            "tags": self.tags
        }


class MemoryStream:
    """
    记忆流
    
    管理NPC的所有记忆，支持：
    - 添加记忆
    - 检索相关记忆
    - 定期总结/遗忘
    """
    
    def __init__(
        self,
        agent_id: str,
        max_memories: int = 100,
        importance_threshold: float = 0.3
    ):
        self.agent_id = agent_id
        self.max_memories = max_memories
        self.importance_threshold = importance_threshold
        
        self.memories: List[Memory] = []
        self._next_id = 1
    
    def add(
        self,
        content: str,
        memory_type: MemoryType,
        turn: int,
        importance: float = 0.5,
        tags: Optional[List[str]] = None
    ) -> Memory:
        """添加记忆"""
        memory = Memory(
            id=f"{self.agent_id}_mem_{self._next_id}",
            memory_type=memory_type,
            content=content,
            turn=turn,
            importance=importance,
            tags=tags or []
        )
        self._next_id += 1
        
        # 插入到列表开头（最新的在前）
        self.memories.insert(0, memory)
        
        # 遗忘低重要性记忆
        self._prune()
        
        return memory
    
    def add_observation(self, content: str, turn: int) -> Memory:
        """添加观察记忆"""
        return self.add(content, MemoryType.OBSERVATION, turn, importance=0.4)
    
    def add_action(self, content: str, turn: int) -> Memory:
        """添加动作记忆"""
        return self.add(content, MemoryType.ACTION, turn, importance=0.6)
    
    def add_reflection(self, content: str, turn: int) -> Memory:
        """添加反思记忆"""
        return self.add(content, MemoryType.REFLECTION, turn, importance=0.8)
    
    def add_plan(self, content: str, turn: int) -> Memory:
        """添加计划记忆"""
        return self.add(content, MemoryType.PLAN, turn, importance=0.7)
    
    def _prune(self):
        """遗忘低重要性记忆"""
        if len(self.memories) > self.max_memories:
            # 按重要性和时间排序
            self.memories.sort(key=lambda m: (m.importance, m.turn), reverse=True)
            self.memories = self.memories[:self.max_memories]
    
    def recall(
        self,
        query: str,
        memory_types: Optional[List[MemoryType]] = None,
        limit: int = 10
    ) -> List[Memory]:
        """
        检索相关记忆
        
        简单实现：关键词匹配
        后续可升级为向量检索
        """
        query_lower = query.lower()
        results = []
        
        for memory in self.memories:
            if memory_types and memory.memory_type not in memory_types:
                continue
            
            # 简单的关键词匹配
            if (query_lower in memory.content.lower() or
                any(tag.lower() in query_lower for tag in memory.tags)):
                results.append(memory)
            
            if len(results) >= limit:
                break
        
        return results
    
    def get_recent(self, n: int = 10) -> List[Memory]:
        """获取最近的N条记忆"""
        return self.memories[:n]
    
    def get_context(self, max_chars: int = 1000) -> str:
        """生成记忆上下文"""
        context_parts = []
        current_chars = 0
        
        for memory in self.memories:
            part = f"[{memory.memory_type.value}] {memory.content}"
            if current_chars + len(part) > max_chars:
                break
            context_parts.append(part)
            current_chars += len(part)
        
        return "\n".join(context_parts) if context_parts else "无相关记忆"
    
    def summarize(self, llm_client) -> str:
        """
        总结记忆（需要LLM）
        
        简化版：返回最近记忆的摘要
        """
        if not self.memories:
            return "无记忆"
        
        recent = self.get_recent(20)
        summary = f"最近{len(recent)}条记忆：\n"
        
        for m in recent[:5]:
            summary += f"- {m.content[:50]}...\n"
        
        return summary
    
    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "memory_count": len(self.memories),
            "memories": [m.to_dict() for m in self.memories]
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
    包含：配置、记忆流、当前状态
    """
    
    def __init__(
        self,
        agent_id: str,
        config: AgentConfig,
        memory_stream: Optional[MemoryStream] = None
    ):
        self.agent_id = agent_id
        self.config = config
        self.memory = memory_stream or MemoryStream(agent_id)
        
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
        """
        生成思考
        
        整合记忆和状态生成上下文
        """
        memories = self.memory.get_context(max_chars=800)
        relationships = self._format_relationships()
        
        return self.config.format_system_prompt(
            situation=situation,
            memories=memories,
            relationships=relationships
        )
    
    def observe(self, content: str, turn: int):
        """记录观察"""
        self.memory.add_observation(content, turn)
    
    def act(self, action: str, turn: int, target: Optional[str] = None):
        """记录动作"""
        content = f"{self.name}：{action}"
        if target:
            content += f" → {target}"
        
        self.memory.add_action(content, turn, importance=0.7)
        self.last_action = action
        self.survival_turns += 1
    
    def reflect(self, reflection: str, turn: int):
        """添加反思"""
        self.memory.add_reflection(reflection, turn, importance=0.8)
    
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
            "memory_count": len(self.memory.memories)
        }
