"""
A01 世界状态管理
管理地点、NPC位置、世界氛围、时间流逝
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum


class TimeOfDay(Enum):
    DAWN = "黎明"
    MORNING = "清晨"
    NOON = "正午"
    AFTERNOON = "下午"
    DUSK = "傍晚"
    EVENING = "入夜"
    NIGHT = "深夜"
    MIDNIGHT = "午夜"


@dataclass
class Location:
    """地点"""
    id: str
    name: str
    description: str
    lat: float = 0.0
    lng: float = 0.0
    npcs: List[str] = field(default_factory=list)
    properties: Dict = field(default_factory=dict)
    mood_modifier: float = 1.0  # 氛围修正因子

    def add_npc(self, npc_id: str):
        if npc_id not in self.npcs:
            self.npcs.append(npc_id)

    def remove_npc(self, npc_id: str):
        if npc_id in self.npcs:
            self.npcs.remove(npc_id)


@dataclass
class WorldState:
    """
    世界状态管理器
    管理时间、地点、NPC位置、世界氛围
    """
    world_id: str
    world_name: str
    era: str  # 时代背景
    locations: Dict[str, Location] = field(default_factory=dict)
    
    # 时间系统
    current_turn: int = 0
    current_day: int = 1
    time_of_day: str = TimeOfDay.DAWN.value
    turns_per_day: int = 8  # 8回合 = 1天
    
    # 世界氛围
    world_mood: str = "平静"
    mood_intensity: float = 0.5  # 0-1
    active_events: List[str] = field(default_factory=list)
    
    # NPC位置缓存
    npc_locations: Dict[str, str] = field(default_factory=dict)  # npc_id -> location_id
    
    def add_location(self, location: Location):
        """添加地点"""
        self.locations[location.id] = location
    
    def get_location(self, location_id: str) -> Optional[Location]:
        """获取地点"""
        return self.locations.get(location_id)
    
    def get_location_by_name(self, name: str) -> Optional[Location]:
        """通过名称获取地点"""
        for loc in self.locations.values():
            if loc.name == name:
                return loc
        return None
    
    def move_npc(self, npc_id: str, location_id: str):
        """移动NPC到新地点"""
        # 从旧地点移除
        old_loc_id = self.npc_locations.get(npc_id)
        if old_loc_id and old_loc_id in self.locations:
            self.locations[old_loc_id].remove_npc(npc_id)
        
        # 添加到新地点
        if location_id in self.locations:
            self.locations[location_id].add_npc(npc_id)
            self.npc_locations[npc_id] = location_id
    
    def advance_turn(self):
        """推进一个回合"""
        self.current_turn += 1
        
        # 计算当前时段
        turn_in_day = (self.current_turn - 1) % self.turns_per_day
        time_order = [
            TimeOfDay.DAWN, TimeOfDay.MORNING, TimeOfDay.NOON, 
            TimeOfDay.AFTERNOON, TimeOfDay.DUSK, TimeOfDay.EVENING,
            TimeOfDay.NIGHT, TimeOfDay.MIDNIGHT
        ]
        self.time_of_day = time_order[turn_in_day].value
        
        # 新的一天
        if turn_in_day == 0 and self.current_turn > 1:
            self.current_day += 1
    
    def get_npcs_at_location(self, location_id: str) -> List[str]:
        """获取某地点的所有NPC"""
        loc = self.get_location(location_id)
        return loc.npcs if loc else []
    
    def update_world_mood(self, mood: str, intensity: float = 0.5):
        """更新世界氛围"""
        self.world_mood = mood
        self.mood_intensity = intensity
    
    def to_context(self) -> str:
        """生成上下文描述"""
        context = f"""【{self.world_name}】{self.era} | 第{self.current_day}天 {self.time_of_day}
世界氛围：{self.world_mood}（强度：{self.mood_intensity*100:.0f}%）
当前事件：{', '.join(self.active_events) if self.active_events else '无特殊事件'}

【地点】
"""
        for loc in self.locations.values():
            npc_names = [self._get_npc_name(nid) for nid in loc.npcs]
            context += f"- {loc.name}：{', '.join(npc_names) if npc_names else '无人'}\n"
        return context
    
    def _get_npc_name(self, npc_id: str) -> str:
        """获取NPC名称（需要外部注入）"""
        return npc_id
    
    def set_npc_name_resolver(self, resolver):
        """设置NPC名称解析器"""
        self._get_npc_name = resolver
    
    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "world_id": self.world_id,
            "world_name": self.world_name,
            "era": self.era,
            "current_turn": self.current_turn,
            "current_day": self.current_day,
            "time_of_day": self.time_of_day,
            "world_mood": self.world_mood,
            "mood_intensity": self.mood_intensity,
            "active_events": self.active_events,
            "locations": {
                k: {
                    "id": v.id,
                    "name": v.name,
                    "description": v.description,
                    "lat": v.lat,
                    "lng": v.lng,
                    "npcs": v.npcs,
                    "properties": v.properties
                }
                for k, v in self.locations.items()
            },
            "npc_locations": self.npc_locations
        }
