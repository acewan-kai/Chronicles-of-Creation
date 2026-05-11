"""
基础用量统计模块
追踪：模拟时长、事件数、LLM调用次数等
"""

import time
import json
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from enum import Enum
import threading


class UsageEventType(Enum):
    """用量事件类型"""
    SIMULATION_START = "simulation_start"
    SIMULATION_END = "simulation_end"
    TURN_COMPLETE = "turn_complete"
    NPC_ACTION = "npc_action"
    LLM_CALL = "llm_call"
    API_ERROR = "api_error"
    WORLD_EVENT = "world_event"
    USER_ACTION = "user_action"


@dataclass
class UsageRecord:
    """单条用量记录"""
    timestamp: float
    event_type: str
    world_id: Optional[str] = None
    turn: Optional[int] = None
    npc_id: Optional[str] = None
    token_count: Optional[int] = None
    duration_ms: Optional[int] = None
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class WorldUsageStats:
    """单个世界的用量统计"""
    world_id: str
    world_name: str
    template: str
    created_at: float
    last_active: float
    
    # 模拟统计
    total_simulation_time: int = 0  # 秒
    total_turns: int = 0
    total_events: int = 0
    total_npc_actions: int = 0
    
    # LLM统计
    total_llm_calls: int = 0
    total_tokens: int = 0
    total_llm_cost: float = 0.0  # 估算成本(元)
    llm_success_count: int = 0
    llm_error_count: int = 0
    
    # 世界事件统计
    world_events_triggered: int = 0
    unscripted_interactions: int = 0
    storylike_moments: int = 0
    
    # 用户互动
    user_actions: int = 0
    
    # 性能指标
    avg_turn_duration_ms: float = 0.0
    max_turn_duration_ms: float = 0.0
    
    # 状态
    is_running: bool = False
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def get_summary(self) -> dict:
        """获取统计摘要"""
        return {
            "world_id": self.world_id,
            "world_name": self.world_name,
            "status": "运行中" if self.is_running else "已停止",
            "runtime": str(timedelta(seconds=self.total_simulation_time)),
            "turns": self.total_turns,
            "events": self.total_events,
            "llm_calls": self.total_llm_calls,
            "tokens": self.total_tokens,
            "estimated_cost": f"¥{self.total_llm_cost:.4f}",
            "success_rate": f"{(self.llm_success_count / max(1, self.total_llm_calls) * 100):.1f}%"
        }


class UsageTracker:
    """
    用量统计追踪器
    
    追踪内容：
    - 模拟时长（总运行时间）
    - 事件数量（回合数、动作数、世界事件）
    - LLM调用次数和Token消耗
    - 成本估算
    - 性能指标（延迟等）
    """
    
    # LLM成本估算（每1000 token）
    COST_PER_1K_TOKENS = {
        "deepseek-chat": {"input": 0.001, "output": 0.002},  # DeepSeek V3
        "gpt-4o": {"input": 0.005, "output": 0.015},
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    }
    
    def __init__(self, default_model: str = "deepseek-chat"):
        self.default_model = default_model
        self._worlds: Dict[str, WorldUsageStats] = {}
        self._records: List[UsageRecord] = []
        self._lock = threading.Lock()
        
        # 当前活跃世界
        self._active_world: Optional[str] = None
        self._session_start_time: Optional[float] = None
    
    def start_session(self, world_id: str, world_name: str, template: str):
        """开始一个新的模拟会话"""
        with self._lock:
            if world_id not in self._worlds:
                self._worlds[world_id] = WorldUsageStats(
                    world_id=world_id,
                    world_name=world_name,
                    template=template,
                    created_at=time.time(),
                    last_active=time.time()
                )
            
            stats = self._worlds[world_id]
            stats.is_running = True
            stats.last_active = time.time()
            
            self._active_world = world_id
            self._session_start_time = time.time()
            
            self._add_record(UsageRecord(
                timestamp=time.time(),
                event_type=UsageEventType.SIMULATION_START.value,
                world_id=world_id,
                metadata={"world_name": world_name, "template": template}
            ))
    
    def end_session(self, world_id: str):
        """结束模拟会话"""
        with self._lock:
            if world_id in self._worlds:
                stats = self._worlds[world_id]
                stats.is_running = False
                stats.last_active = time.time()
                
                if self._session_start_time:
                    session_duration = int(time.time() - self._session_start_time)
                    stats.total_simulation_time += session_duration
                
                self._add_record(UsageRecord(
                    timestamp=time.time(),
                    event_type=UsageEventType.SIMULATION_END.value,
                    world_id=world_id,
                    duration_ms=int((time.time() - (self._session_start_time or time.time())) * 1000)
                ))
                
                self._active_world = None
                self._session_start_time = None
    
    def record_turn(self, world_id: str, turn: int, duration_ms: float):
        """记录回合完成"""
        with self._lock:
            if world_id in self._worlds:
                stats = self._worlds[world_id]
                stats.total_turns += 1
                stats.total_events += 1
                stats.last_active = time.time()
                
                # 更新性能指标
                stats.avg_turn_duration_ms = (
                    (stats.avg_turn_duration_ms * (stats.total_turns - 1) + duration_ms) 
                    / stats.total_turns
                )
                stats.max_turn_duration_ms = max(stats.max_turn_duration_ms, duration_ms)
                
                self._add_record(UsageRecord(
                    timestamp=time.time(),
                    event_type=UsageEventType.TURN_COMPLETE.value,
                    world_id=world_id,
                    turn=turn,
                    duration_ms=int(duration_ms)
                ))
    
    def record_npc_action(self, world_id: str, npc_id: str, turn: int, 
                         action_type: str = "default", metadata: dict = None):
        """记录NPC动作"""
        with self._lock:
            if world_id in self._worlds:
                stats = self._worlds[world_id]
                stats.total_npc_actions += 1
                stats.last_active = time.time()
                
                self._add_record(UsageRecord(
                    timestamp=time.time(),
                    event_type=UsageEventType.NPC_ACTION.value,
                    world_id=world_id,
                    turn=turn,
                    npc_id=npc_id,
                    metadata={**(metadata or {}), "action_type": action_type}
                ))
    
    def record_llm_call(self, world_id: str, npc_id: str, turn: int,
                        input_tokens: int, output_tokens: int,
                        model: str = None, success: bool = True,
                        duration_ms: int = 0):
        """记录LLM调用"""
        with self._lock:
            if world_id in self._worlds:
                stats = self._worlds[world_id]
                stats.total_llm_calls += 1
                stats.total_tokens += input_tokens + output_tokens
                
                if success:
                    stats.llm_success_count += 1
                else:
                    stats.llm_error_count += 1
                
                # 计算成本
                model_key = model or self.default_model
                cost_info = self.COST_PER_1K_TOKENS.get(model_key, {"input": 0.001, "output": 0.002})
                cost = (input_tokens / 1000) * cost_info["input"] + \
                       (output_tokens / 1000) * cost_info["output"]
                stats.total_llm_cost += cost
                
                stats.last_active = time.time()
                
                self._add_record(UsageRecord(
                    timestamp=time.time(),
                    event_type=UsageEventType.LLM_CALL.value,
                    world_id=world_id,
                    turn=turn,
                    npc_id=npc_id,
                    token_count=input_tokens + output_tokens,
                    duration_ms=duration_ms,
                    metadata={
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "model": model_key,
                        "success": success
                    }
                ))
    
    def record_world_event(self, world_id: str, event_id: str, event_name: str):
        """记录世界事件触发"""
        with self._lock:
            if world_id in self._worlds:
                stats = self._worlds[world_id]
                stats.world_events_triggered += 1
                stats.last_active = time.time()
                
                self._add_record(UsageRecord(
                    timestamp=time.time(),
                    event_type=UsageEventType.WORLD_EVENT.value,
                    world_id=world_id,
                    metadata={"event_id": event_id, "event_name": event_name}
                ))
    
    def record_unscripted_interaction(self, world_id: str, interaction_type: str):
        """记录非预设互动"""
        with self._lock:
            if world_id in self._worlds:
                stats = self._worlds[world_id]
                stats.unscripted_interactions += 1
                stats.last_active = time.time()
    
    def record_storylike_moment(self, world_id: str, moment_type: str):
        """记录故事感时刻"""
        with self._lock:
            if world_id in self._worlds:
                stats = self._worlds[world_id]
                stats.storylike_moments += 1
                stats.last_active = time.time()
    
    def record_user_action(self, world_id: str, action_type: str, metadata: dict = None):
        """记录用户动作"""
        with self._lock:
            if world_id in self._worlds:
                stats = self._worlds[world_id]
                stats.user_actions += 1
                stats.last_active = time.time()
                
                self._add_record(UsageRecord(
                    timestamp=time.time(),
                    event_type=UsageEventType.USER_ACTION.value,
                    world_id=world_id,
                    metadata={**(metadata or {}), "action_type": action_type}
                ))
    
    def get_world_stats(self, world_id: str) -> Optional[dict]:
        """获取特定世界的统计"""
        with self._lock:
            if world_id in self._worlds:
                return self._worlds[world_id].to_dict()
            return None
    
    def get_world_summary(self, world_id: str) -> Optional[dict]:
        """获取世界统计摘要"""
        with self._lock:
            if world_id in self._worlds:
                return self._worlds[world_id].get_summary()
            return None
    
    def get_all_worlds_summary(self) -> List[dict]:
        """获取所有世界的统计摘要"""
        with self._lock:
            return [stats.get_summary() for stats in self._worlds.values()]
    
    def get_total_stats(self) -> dict:
        """获取全局统计汇总"""
        with self._lock:
            total_sim_time = sum(w.total_simulation_time for w in self._worlds.values())
            total_turns = sum(w.total_turns for w in self._worlds.values())
            total_events = sum(w.total_events for w in self._worlds.values())
            total_llm_calls = sum(w.total_llm_calls for w in self._worlds.values())
            total_tokens = sum(w.total_tokens for w in self._worlds.values())
            total_cost = sum(w.total_llm_cost for w in self._worlds.values())
            total_worlds = len(self._worlds)
            running_worlds = sum(1 for w in self._worlds.values() if w.is_running)
            
            return {
                "total_worlds": total_worlds,
                "running_worlds": running_worlds,
                "total_simulation_time": total_sim_time,
                "total_simulation_time_human": str(timedelta(seconds=total_sim_time)),
                "total_turns": total_turns,
                "total_events": total_events,
                "total_llm_calls": total_llm_calls,
                "total_tokens": total_tokens,
                "total_cost": f"¥{total_cost:.4f}",
                "avg_tokens_per_turn": total_tokens // max(1, total_turns) if total_turns > 0 else 0,
                "timestamp": time.time()
            }
    
    def export_records(self, world_id: str = None, limit: int = 1000) -> List[dict]:
        """导出用量记录"""
        with self._lock:
            records = self._records
            if world_id:
                records = [r for r in records if r.world_id == world_id]
            return [r.to_dict() for r in records[-limit:]]
    
    def _add_record(self, record: UsageRecord):
        """添加记录"""
        self._records.append(record)
        # 保持记录数量在合理范围
        if len(self._records) > 10000:
            self._records = self._records[-5000:]


# 全局实例
_usage_tracker: Optional[UsageTracker] = None


def get_usage_tracker() -> UsageTracker:
    """获取全局用量追踪器实例"""
    global _usage_tracker
    if _usage_tracker is None:
        _usage_tracker = UsageTracker()
    return _usage_tracker


def create_tracker(model: str = "deepseek-chat") -> UsageTracker:
    """创建新的追踪器实例"""
    global _usage_tracker
    _usage_tracker = UsageTracker(default_model=model)
    return _usage_tracker
