"""
A01 事件分发器
负责将动作结果分发给各模块：日志记录、知识图谱更新、智能体状态更新
"""

import asyncio
from dataclasses import dataclass, field
from typing import List, Callable, Dict, Any, Optional
from datetime import datetime
from enum import Enum

from .action_executor import ActionResult


class EventType(Enum):
    """事件类型"""
    NPC_ACTION = "npc_action"
    WORLD_STATE_CHANGE = "world_state_change"
    RELATIONSHIP_CHANGE = "relationship_change"
    STORY_MOMENT = "story_moment"
    SYSTEM_EVENT = "system_event"


@dataclass
class DispatchEvent:
    """分发事件"""
    event_type: EventType
    timestamp: str
    turn: int
    data: Dict[str, Any]
    source: str  # 事件来源


class EventDispatcher:
    """
    事件分发器
    收集事件并分发给各个订阅者
    """
    
    def __init__(self):
        # 订阅者列表：event_type -> [callback]
        self._subscribers: Dict[EventType, List[Callable]] = {
            EventType.NPC_ACTION: [],
            EventType.WORLD_STATE_CHANGE: [],
            EventType.RELATIONSHIP_CHANGE: [],
            EventType.STORY_MOMENT: [],
            EventType.SYSTEM_EVENT: [],
        }
        
        # 事件队列
        self._event_queue: List[DispatchEvent] = []
        
        # 统计
        self.stats = {
            "total_dispatched": 0,
            "by_type": {et.value: 0 for et in EventType}
        }
    
    def subscribe(self, event_type: EventType, callback: Callable):
        """订阅事件"""
        if callback not in self._subscribers[event_type]:
            self._subscribers[event_type].append(callback)
    
    def unsubscribe(self, event_type: EventType, callback: Callable):
        """取消订阅"""
        if callback in self._subscribers[event_type]:
            self._subscribers[event_type].remove(callback)
    
    async def dispatch(self, event: DispatchEvent):
        """分发事件"""
        self.stats["total_dispatched"] += 1
        self.stats["by_type"][event.event_type.value] += 1
        self._event_queue.append(event)
        
        # 调用所有订阅者
        subscribers = self._subscribers.get(event.event_type, [])
        for callback in subscribers:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                print(f"事件处理错误: {e}")
    
    async def dispatch_action_result(
        self,
        result: ActionResult,
        turn: int,
        world_context: str
    ):
        """分发动作结果事件"""
        event = DispatchEvent(
            event_type=EventType.NPC_ACTION,
            timestamp=datetime.now().isoformat(),
            turn=turn,
            data={
                "actor_id": result.actor_id,
                "actor_name": result.actor_name,
                "action": result.action,
                "target": result.target,
                "target_id": result.target_id,
                "location": result.location,
                "action_type": result.action_type,
                "status": result.status,
                "elapsed_time": result.elapsed_time,
                "world_context": world_context
            },
            source="action_executor"
        )
        await self.dispatch(event)
        
        # 如果是故事时刻，额外分发
        if result.action_type == "story_moment":
            story_event = DispatchEvent(
                event_type=EventType.STORY_MOMENT,
                timestamp=datetime.now().isoformat(),
                turn=turn,
                data=event.data.copy(),
                source="action_executor"
            )
            await self.dispatch(story_event)
    
    async def dispatch_relationship_change(
        self,
        actor_id: str,
        target_id: str,
        change_type: str,  # "increase", "decrease", "new", "broken"
        change_value: float,
        reason: str,
        turn: int
    ):
        """分发关系变化事件"""
        event = DispatchEvent(
            event_type=EventType.RELATIONSHIP_CHANGE,
            timestamp=datetime.now().isoformat(),
            turn=turn,
            data={
                "actor_id": actor_id,
                "target_id": target_id,
                "change_type": change_type,
                "change_value": change_value,
                "reason": reason
            },
            source="agent"
        )
        await self.dispatch(event)
    
    def get_events(
        self,
        event_type: Optional[EventType] = None,
        turn_range: Optional[tuple] = None
    ) -> List[DispatchEvent]:
        """获取事件列表"""
        events = self._event_queue
        
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        if turn_range:
            events = [e for e in events if turn_range[0] <= e.turn <= turn_range[1]]
        
        return events
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            "queue_size": len(self._event_queue),
            "subscribers": {
                et.value: len(callbacks) 
                for et, callbacks in self._subscribers.items()
            }
        }
    
    def clear(self):
        """清空事件队列"""
        self._event_queue.clear()
