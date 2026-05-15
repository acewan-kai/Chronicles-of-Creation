"""
A01 沙盒模拟核心模块
包含：世界状态管理、回合调度器、NPC动作执行器、事件分发器
D01 冲突注入引擎
D02 演化停滞检测
D03 外部扰动投放
"""

from .world_state import WorldState, Location
from .turn_scheduler import TurnScheduler
from .action_executor import ActionExecutor
from .event_dispatcher import EventDispatcher
from .conflict_injector import ConflictInjector, ConflictType, ConflictEvent, HeatMetrics
from .stagnation_detector import StagnationDetector, StagnationReport, StagnationAlert, StagnationType
from .disturbance_injector import DisturbanceInjector, DisturbanceEvent, DisturbanceTemplate, DisturbanceCategory, Frequency

__all__ = [
    "WorldState",
    "Location",
    "TurnScheduler",
    "ActionExecutor",
    "EventDispatcher",
    "ConflictInjector",
    "ConflictType",
    "ConflictEvent",
    "HeatMetrics",
    "StagnationDetector",
    "StagnationReport",
    "StagnationAlert",
    "StagnationType",
    "DisturbanceInjector",
    "DisturbanceEvent",
    "DisturbanceTemplate",
    "DisturbanceCategory",
    "Frequency",
]
