"""
A02 事件查询引擎
支持时间范围、角色、类型等多维度查询
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from pathlib import Path

from .event_store import EventStore, Event


class QueryEngine:
    """
    事件查询引擎
    提供灵活的事件查询接口
    """
    
    def __init__(self, event_store: EventStore):
        self.store = event_store
    
    async def get_events_by_turn(self, turn: int) -> List[Event]:
        """获取指定回合的所有事件"""
        return await self.store.query(turn_range=(turn, turn))
    
    async def get_events_by_turns(self, start_turn: int, end_turn: int) -> List[Event]:
        """获取回合范围内的事件"""
        return await self.store.query(turn_range=(start_turn, end_turn))
    
    async def get_events_by_actor(self, actor_id: str, limit: int = 100) -> List[Event]:
        """获取指定角色的所有事件"""
        return await self.store.query(actor_id=actor_id, limit=limit)
    
    async def get_interactions_between(self, actor1_id: str, actor2_id: str) -> List[Event]:
        """获取两个角色之间的所有互动"""
        events = await self.store.query(
            action_type="interaction",
            limit=500
        )
        
        # 筛选出这两个角色之间的互动
        return [
            e for e in events
            if {e.actor_id, e.target_id} == {actor1_id, actor2_id}
        ]
    
    async def get_recent_events(self, hours: int = 1) -> List[Event]:
        """获取最近N小时的事件"""
        # 简化：按turn数估算
        # 假设8回合 = 1天24小时 = 1440分钟
        # 每回合约180分钟
        turns_ago = hours * 8 // 24 + 1
        metrics = await self.store.get_metrics()
        current_turn = metrics.get("max_turn", 0)
        start_turn = max(1, current_turn - turns_ago)
        
        return await self.store.query(turn_range=(start_turn, current_turn))
    
    async def get_highlight_events(
        self,
        min_score: float = 3.0,
        action_types: Optional[List[str]] = None
    ) -> List[Event]:
        """获取高亮事件（高分或故事时刻）"""
        all_events = []
        
        if action_types is None:
            action_types = ["story_moment", "interaction"]
        
        for at in action_types:
            events = await self.store.query(action_type=at, limit=200)
            all_events.extend(events)
        
        # 排序
        all_events.sort(
            key=lambda e: (e.score or 0, e.turn),
            reverse=True
        )
        
        return [e for e in all_events if (e.score or 0) >= min_score]
    
    async def get_location_timeline(self, location: str, limit: int = 100) -> List[Event]:
        """获取某地点的事件时间线"""
        return await self.store.query(location=location, limit=limit)
    
    async def get_npc_relationships_summary(self) -> Dict[str, Dict[str, int]]:
        """获取NPC关系摘要"""
        events = await self.store.query(action_type="interaction", limit=5000)
        
        relationships: Dict[str, Dict[str, int]] = {}
        
        for event in events:
            if not event.target_id:
                continue
            
            # 初始化
            if event.actor_id not in relationships:
                relationships[event.actor_id] = {}
            if event.target_id not in relationships:
                relationships[event.target_id] = {}
            
            # 计数
            relationships[event.actor_id][event.target_id] = \
                relationships[event.actor_id].get(event.target_id, 0) + 1
        
        return relationships
    
    async def generate_summary(self) -> Dict[str, Any]:
        """生成事件摘要"""
        metrics = await self.store.get_metrics()
        story_moments = await self.store.get_story_moments()
        interactions = await self.store.get_cross_interactions()
        
        return {
            "metrics": metrics,
            "story_moments_count": len(story_moments),
            "unique_interactions_count": len(interactions),
            "top_moments": [
                {
                    "turn": e.turn,
                    "actor": e.actor_name,
                    "action": e.action[:100],
                    "score": e.score
                }
                for e in story_moments[:5]
            ]
        }
