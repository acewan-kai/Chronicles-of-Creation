"""
D01 冲突注入引擎
检测叙事热度下降时自动引入冲突事件
支持≥5种冲突类型：内部/人际/外部/事件/神秘
"""

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from enum import Enum
import time


class ConflictType(Enum):
    """冲突类型"""
    INTERNAL = "internal"      # 内部冲突：角色内心的挣扎
    INTERPERSONAL = "interpersonal"  # 人际冲突：角色间矛盾
    EXTERNAL = "external"    # 外部冲突：外界威胁/压力
    EVENT = "event"          # 事件冲突：突发事故/危机
    MYSTERY = "mystery"      # 神秘冲突：谜团/秘密揭露


@dataclass
class ConflictEvent:
    """冲突事件"""
    conflict_type: ConflictType
    trigger_agent: str  # 触发冲突的角色
    participants: List[str]  # 涉及的角色的agent_id列表
    description: str  # 冲突描述
    severity: float  # 0.0-1.0
    world_impact: str  # 对世界的影响描述
    suggested_narrative: str  # 建议的叙事方向


@dataclass
class HeatMetrics:
    """热度指标"""
    event_density: float = 0.0  # 事件密度
    relationship_change_rate: float = 0.0  # 关系变化率
    goal_achievement_rate: float = 0.0  # 目标达成率
    conflict_resolution_rate: float = 0.0  # 冲突解决率
    new_event_introduction_rate: float = 0.0  # 新事件引入率
    overall_heat: float = 0.5  # 综合热度 0.0-1.0


class ConflictInjector:
    """
    冲突注入引擎

    职责：
    1. 监控系统热度指标
    2. 检测热度下降信号
    3. 在适当时机注入冲突事件
    4. 保持冲突与设定兼容

    冲突类型：
    - INTERNAL: 角色内心冲突（目标vs能力/欲望vs道德）
    - INTERPERSONAL: 人际冲突（竞争/背叛/误会/争夺）
    - EXTERNAL: 外部威胁（天灾/外敌/压迫/危机）
    - EVENT: 突发事件（发现/背叛/死亡/觉醒）
    - MYSTERY: 神秘冲突（秘密揭露/阴谋曝光/身份谜团）
    """

    # 各类型冲突的关键词模板
    CONFLICT_TEMPLATES = {
        ConflictType.INTERNAL: [
            "{agent}陷入了深深的自我怀疑，{internal_struggle}",
            "{agent}面临艰难抉择：{choice}",
            "{agent}的过去阴影突然袭来，{past_trauma}",
        ],
        ConflictType.INTERPERSONAL: [
            "{agent}与{target}因{reason}产生激烈争执",
            "{agent}发现{target}似乎在隐瞒什么",
            "{agent}与{target}为{resource}展开竞争",
        ],
        ConflictType.EXTERNAL: [
            "突如其来的{disaster}打破了平静",
            "{agent}面临来自外部的威胁：{threat}",
            "外界变化让{agent}的处境变得危险",
        ],
        ConflictType.EVENT: [
            "{agent}意外发现了{discovery}",
            "关键人物{dead_person}的死亡突然曝光",
            "{agent}意外获得了{unexpected_gain}，但代价未知",
        ],
        ConflictType.MYSTERY: [
            "{agent}察觉到{target}背后的秘密",
            "关于{subject}的真相开始浮出水面",
            "{agent}发现了{target}隐瞒的重大秘密",
        ],
    }

    # 内部冲突子类型
    INTERNAL_STRUGGLES = [
        "是否要放弃一直以来的坚持",
        "个人利益与他人期望的抉择",
        "过去错误带来的愧疚感",
        "对未来的恐惧与不确定",
        "能力不足带来的无力感",
    ]

    CHOICES = [
        "忠诚还是自保",
        "真相还是谎言",
        "复仇还是宽恕",
        "理想还是现实",
        "感情还是理智",
    ]

    PAST_TRAUMAS = [
        "那段不愿回首的记忆",
        "曾经犯下的错误",
        "失去至亲的悲痛",
        "被背叛的伤痛",
        "失败的耻辱",
    ]

    REASONS = [
        "误会和猜疑",
        "资源的争夺",
        "理念的冲突",
        "过往的恩怨",
        "地位的竞争",
    ]

    RESOURCES = [
        "稀缺的上古遗物",
        "关键的晋升机会",
        "某人的信任",
        "有限的修炼资源",
        "主导话语权",
    ]

    DISASTERS = [
        "山洪突然爆发",
        "瘟疫开始蔓延",
        "异象降临",
        "灵气突然紊乱",
        "天劫降临",
    ]

    THREATS = [
        "神秘势力的逼近",
        "自然的怒火",
        "敌对阵营的阴谋",
        "失控的妖兽",
        "未知的危险",
    ]

    DISCOVERIES = [
        "一个隐藏的密室",
        "一封尘封的信件",
        "某人不可告人的秘密",
        "一个惊人的真相",
        "一件改变一切的事物",
    ]

    UNEXPECTED_GAINS = [
        "一股神秘力量",
        "失落的传承",
        "强大的盟友",
        "关键的线索",
        "逆转局势的机会",
    ]

    def __init__(self, world_id: str):
        self.world_id = world_id
        self._last_conflict_turn: int = 0
        self._conflict_cooldown: int = 10  # 冲突冷却回合数
        self._active_conflicts: List[ConflictEvent] = []
        self._history: List[ConflictEvent] = []
        self._heat_history: List[HeatMetrics] = []

    def assess_heat(
        self,
        recent_events: List[Dict],
        relationship_changes: int,
        total_interactions: int,
        current_turn: int
    ) -> HeatMetrics:
        """
        评估当前世界热度

        Returns:
            HeatMetrics 包含各项热度指标
        """
        if not recent_events:
            return HeatMetrics()

        # 事件密度：最近N回合的事件数量
        event_count = len(recent_events)
        turns_span = max(1, current_turn - (recent_events[0].get("turn", current_turn) if recent_events else 0))
        event_density = min(1.0, event_count / max(1, turns_span * 2))

        # 关系变化率
        relationship_change_rate = min(1.0, relationship_changes / max(1, total_interactions))

        # 目标达成率（简版：事件中有success类型的比例）
        success_count = sum(1 for e in recent_events if e.get("action_type") == "story_moment")
        goal_achievement_rate = success_count / max(1, event_count)

        # 冲突解决率
        conflict_count = sum(1 for e in recent_events if "conflict" in e.get("tags", []))
        resolution_count = sum(1 for e in recent_events if "resolved" in e.get("tags", []))
        conflict_resolution_rate = resolution_count / max(1, conflict_count) if conflict_count > 0 else 0.5

        # 新事件引入率
        new_event_count = sum(1 for e in recent_events if e.get("action_type") == "story_moment")
        new_event_introduction_rate = new_event_count / max(1, event_count)

        # 综合热度
        overall_heat = (
            event_density * 0.2 +
            relationship_change_rate * 0.15 +
            goal_achievement_rate * 0.25 +
            conflict_resolution_rate * 0.15 +
            new_event_introduction_rate * 0.25
        )

        metrics = HeatMetrics(
            event_density=event_density,
            relationship_change_rate=relationship_change_rate,
            goal_achievement_rate=goal_achievement_rate,
            conflict_resolution_rate=conflict_resolution_rate,
            new_event_introduction_rate=new_event_introduction_rate,
            overall_heat=round(overall_heat, 3)
        )

        self._heat_history.append(metrics)
        # 只保留最近20条历史
        if len(self._heat_history) > 20:
            self._heat_history = self._heat_history[-20:]

        return metrics

    def should_inject_conflict(
        self,
        heat: HeatMetrics,
        current_turn: int
    ) -> bool:
        """
        判断是否应该注入冲突

        条件：
        1. 距离上次冲突已过冷却期
        2. 综合热度低于阈值 或 热度下降趋势明显
        """
        # 冷却期检查
        if current_turn - self._last_conflict_turn < self._conflict_cooldown:
            return False

        # 热度过低
        if heat.overall_heat < 0.3:
            return True

        # 热度下降趋势检测
        if len(self._heat_history) >= 3:
            recent_heats = [h.overall_heat for h in self._heat_history[-3:]]
            if all(recent_heats[i] > recent_heats[i+1] for i in range(len(recent_heats)-1)):
                # 连续下降
                if recent_heats[-1] < 0.5:
                    return True

        return False

    def select_conflict_type(self, heat: HeatMetrics) -> ConflictType:
        """
        根据热度指标选择冲突类型

        热度低时倾向于外部/事件冲突来重启剧情
        热度中等时倾向于人际冲突
        热度较高时倾向于内部/神秘冲突
        """
        if heat.overall_heat < 0.3:
            # 低热度：选择能快速推动剧情的类型
            weights = {
                ConflictType.EXTERNAL: 0.35,
                ConflictType.EVENT: 0.35,
                ConflictType.INTERPERSONAL: 0.2,
                ConflictType.INTERNAL: 0.05,
                ConflictType.MYSTERY: 0.05,
            }
        elif heat.overall_heat < 0.6:
            # 中热度：平衡类型
            weights = {
                ConflictType.INTERPERSONAL: 0.35,
                ConflictType.MYSTERY: 0.25,
                ConflictType.EXTERNAL: 0.15,
                ConflictType.EVENT: 0.15,
                ConflictType.INTERNAL: 0.10,
            }
        else:
            # 高热度：选择深化类型
            weights = {
                ConflictType.INTERNAL: 0.30,
                ConflictType.MYSTERY: 0.30,
                ConflictType.INTERPERSONAL: 0.25,
                ConflictType.EXTERNAL: 0.10,
                ConflictType.EVENT: 0.05,
            }

        # 加权随机选择
        rand = random.random()
        cumulative = 0.0
        for conflict_type, weight in weights.items():
            cumulative += weight
            if rand <= cumulative:
                return conflict_type

        return ConflictType.INTERPERSONAL

    def select_participants(
        self,
        agents: Dict[str, any],
        conflict_type: ConflictType,
        count: int = 2
    ) -> List[str]:
        """选择冲突参与者"""
        agent_ids = list(agents.keys())
        if not agent_ids:
            return []

        if conflict_type == ConflictType.INTERNAL:
            # 内部冲突只需要一个人
            return [random.choice(agent_ids)]

        # 其他冲突类型需要多个参与者
        participants = random.sample(agent_ids, min(count, len(agent_ids)))
        return participants

    def generate_conflict(
        self,
        agents: Dict[str, any],
        heat: HeatMetrics,
        current_turn: int
    ) -> Optional[ConflictEvent]:
        """
        生成冲突事件

        Returns:
            ConflictEvent 如果应该注入冲突，否则 None
        """
        if not self.should_inject_conflict(heat, current_turn):
            return None

        conflict_type = self.select_conflict_type(heat)
        participants = self.select_participants(agents, conflict_type)

        if not participants:
            return None

        trigger_agent = participants[0]

        # 根据冲突类型生成描述
        template = random.choice(self.CONFLICT_TEMPLATES[conflict_type])

        # 填充模板参数
        agent_name = agents.get(trigger_agent, {}).get("name", trigger_agent) if hasattr(agents, 'get') else trigger_agent

        context = self._build_template_context(conflict_type, agents, participants)

        description = template.format(
            agent=agent_name,
            target=agents.get(participants[1], {}).get("name", participants[1]) if len(participants) > 1 and hasattr(agents, 'get') else "某人",
            **context
        )

        # 计算严重度
        severity = self._calculate_severity(conflict_type, heat)

        # 世界影响
        world_impact = self._generate_world_impact(conflict_type, description)

        # 建议叙事方向
        suggested_narrative = self._generate_narrative_suggestion(conflict_type, description)

        conflict = ConflictEvent(
            conflict_type=conflict_type,
            trigger_agent=trigger_agent,
            participants=participants,
            description=description,
            severity=severity,
            world_impact=world_impact,
            suggested_narrative=suggested_narrative
        )

        self._active_conflicts.append(conflict)
        self._history.append(conflict)
        self._last_conflict_turn = current_turn

        return conflict

    def _build_template_context(
        self,
        conflict_type: ConflictType,
        agents: Dict,
        participants: List[str]
    ) -> Dict[str, str]:
        """构建模板上下文"""
        context = {}

        if conflict_type == ConflictType.INTERNAL:
            context["internal_struggle"] = random.choice(self.INTERNAL_STRUGGLES)
            context["choice"] = random.choice(self.CHOICES)
            context["past_trauma"] = random.choice(self.PAST_TRAUMAS)
        elif conflict_type == ConflictType.INTERPERSONAL:
            context["reason"] = random.choice(self.REASONS)
            context["resource"] = random.choice(self.RESOURCES)
        elif conflict_type == ConflictType.EXTERNAL:
            context["disaster"] = random.choice(self.DISASTERS)
            context["threat"] = random.choice(self.THREATS)
        elif conflict_type == ConflictType.EVENT:
            context["discovery"] = random.choice(self.DISCOVERIES)
            context["dead_person"] = random.choice(participants) if participants else "某人"
            context["unexpected_gain"] = random.choice(self.UNEXPECTED_GAINS)
        elif conflict_type == ConflictType.MYSTERY:
            context["subject"] = random.choice(["身份", "过去", "目的", "关系"])
            context["target"] = participants[1] if len(participants) > 1 else "某人"

        return context

    def _calculate_severity(self, conflict_type: ConflictType, heat: HeatMetrics) -> float:
        """计算冲突严重度"""
        base_severity = {
            ConflictType.INTERNAL: 0.4,
            ConflictType.INTERPERSONAL: 0.6,
            ConflictType.EXTERNAL: 0.7,
            ConflictType.EVENT: 0.8,
            ConflictType.MYSTERY: 0.5,
        }

        severity = base_severity.get(conflict_type, 0.5)

        # 热度越低，冲突严重度可以适当提高以重启剧情
        if heat.overall_heat < 0.3:
            severity = min(1.0, severity + 0.2)

        return round(severity, 2)

    def _generate_world_impact(self, conflict_type: ConflictType, description: str) -> str:
        """生成世界影响描述"""
        impacts = {
            ConflictType.INTERNAL: "角色内心波动，可能影响后续决策",
            ConflictType.INTERPERSONAL: "角色间关系发生变化，互动模式可能改变",
            ConflictType.EXTERNAL: "世界状态受到影响，可能引发连锁反应",
            ConflictType.EVENT: "重大事件，可能改变局势走向",
            ConflictType.MYSTERY: "新的谜团浮出水面，吸引各方关注",
        }
        return impacts.get(conflict_type, "局势发生变化")

    def _generate_narrative_suggestion(self, conflict_type: ConflictType, description: str) -> str:
        """生成叙事建议"""
        suggestions = {
            ConflictType.INTERNAL: "让角色在内心挣扎中展现深度，后续可考虑与过去和解或彻底黑化",
            ConflictType.INTERPERSONAL: "通过冲突展现角色性格，误会型冲突可转化为深厚友谊或不死不休的仇敌",
            ConflictType.EXTERNAL: "外部威胁可以团结内部，也可能暴露内部矛盾",
            ConflictType.EVENT: "突发事件打破原有计划，让角色应对变化，可能触发隐藏剧情线",
            ConflictType.MYSTERY: "谜团引发调查热忱，各方势力可能因此产生交集",
        }
        return suggestions.get(conflict_type, "继续观察事态发展")

    def resolve_conflict(self, conflict_id: int, resolution: str):
        """标记冲突已解决"""
        for i, conflict in enumerate(self._active_conflicts):
            if hash(conflict.description) == conflict_id:
                conflict.description += f"\n[已解决] {resolution}"
                self._active_conflicts.pop(i)
                break

    def get_active_conflicts(self) -> List[ConflictEvent]:
        """获取当前活跃冲突"""
        return self._active_conflicts

    def get_conflict_stats(self) -> Dict:
        """获取冲突统计"""
        type_counts = {}
        for conflict in self._history:
            ct = conflict.conflict_type.value
            type_counts[ct] = type_counts.get(ct, 0) + 1

        return {
            "total_conflicts": len(self._history),
            "active_conflicts": len(self._active_conflicts),
            "last_conflict_turn": self._last_conflict_turn,
            "conflicts_by_type": type_counts,
            "avg_severity": sum(c.severity for c in self._history) / max(1, len(self._history))
        }

    def to_dict(self) -> Dict:
        """序列化"""
        return {
            "world_id": self.world_id,
            "stats": self.get_conflict_stats(),
            "active_conflicts": [
                {
                    "type": c.conflict_type.value,
                    "trigger_agent": c.trigger_agent,
                    "participants": c.participants,
                    "description": c.description,
                    "severity": c.severity,
                    "world_impact": c.world_impact,
                    "suggested_narrative": c.suggested_narrative
                }
                for c in self._active_conflicts
            ]
        }
