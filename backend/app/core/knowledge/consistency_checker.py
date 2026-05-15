"""
B02 设定一致性实时检测
检测种类≥3类：因果矛盾/属性冲突/时序矛盾
单次检测≤2秒
准确率≥85%
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Any
from enum import Enum
import time


class ContradictionType(Enum):
    """矛盾类型"""
    CAUSAL = "causal"           # 因果矛盾：A导致B，但B与A矛盾
    ATTRIBUTE = "attribute"     # 属性冲突：角色属性前后不一致
    TEMPORAL = "temporal"       # 时序矛盾：事件时间顺序冲突
    RELATION = "relation"       # 关系矛盾：角色关系冲突
    KNOWLEDGE = "knowledge"     # 知识矛盾：与世界设定冲突


@dataclass
class Contradiction:
    """检测到的矛盾"""
    contradiction_type: ContradictionType
    severity: float  # 0.0-1.0，1.0最严重
    description: str
    involved_entities: List[str]  # 涉及的实体ID列表
    evidence: str  # 证据文本
    suggested_fix: str  # 建议修复方案
    detected_at_turn: int = 0


@dataclass
class ConsistencyReport:
    """一致性检测报告"""
    world_id: str
    total_checks: int = 0
    contradictions_found: List[Contradiction] = field(default_factory=list)
    check_duration_ms: float = 0.0
    consistency_score: float = 1.0  # 0.0-1.0，1.0表示完全一致
    last_check_turn: int = 0

    def to_dict(self) -> dict:
        return {
            "world_id": self.world_id,
            "total_checks": self.total_checks,
            "contradictions_count": len(self.contradictions_found),
            "contradictions": [
                {
                    "type": c.contradiction_type.value,
                    "severity": c.severity,
                    "description": c.description,
                    "involved_entities": c.involved_entities,
                    "evidence": c.evidence,
                    "suggested_fix": c.suggested_fix,
                    "detected_at_turn": c.detected_at_turn
                }
                for c in self.contradictions_found
            ],
            "check_duration_ms": round(self.check_duration_ms, 2),
            "consistency_score": round(self.consistency_score, 3),
            "last_check_turn": self.last_check_turn
        }


class ConsistencyChecker:
    """
    设定一致性检测器

    检测类型：
    1. 因果矛盾（Causal）：A事件导致B结果，但B与已知事实矛盾
    2. 属性冲突（Attribute）：角色属性、性格、身份前后不一致
    3. 时序矛盾（Temporal）：事件发生顺序与时间线矛盾
    4. 关系矛盾（Relation）：角色间关系与已知互动矛盾
    5. 知识矛盾（Knowledge）：与世界观设定冲突
    """

    def __init__(self, world_id: str):
        self.world_id = world_id
        self._death_records: Dict[str, int] = {}  # agent_id -> death_turn
        self._attribute_snapshots: Dict[str, Dict[str, Any]] = {}  # agent_id -> {attrs}
        self._event_timeline: List[Tuple[int, str, str]] = []  # (turn, event_type, description)
        self._knowledge_cache: Set[str] = set()  # 已确立的世界知识

    def record_death(self, agent_id: str, turn: int):
        """记录角色死亡"""
        self._death_records[agent_id] = turn

    def record_alive(self, agent_id: str):
        """撤销死亡记录（复活情况）"""
        if agent_id in self._death_records:
            del self._death_records[agent_id]

    def snapshot_attributes(self, agent_id: str, attributes: Dict[str, Any], turn: int):
        """记录角色属性快照"""
        if agent_id not in self._attribute_snapshots:
            self._attribute_snapshots[agent_id] = {}
        self._attribute_snapshots[agent_id][f"turn_{turn}"] = attributes

    def add_event(self, turn: int, event_type: str, description: str):
        """添加事件到时间线"""
        self._event_timeline.append((turn, event_type, description))

    def add_knowledge(self, knowledge: str):
        """添加已确立的世界知识"""
        self._knowledge_cache.add(knowledge.lower())

    # ========== 因果矛盾检测 ==========

    def _check_causal_contradictions(
        self,
        agent_id: str,
        action: str,
        turn: int
    ) -> List[Contradiction]:
        """检测因果矛盾"""
        contradictions = []

        # 检查死亡后行动
        if agent_id in self._death_records:
            death_turn = self._death_records[agent_id]
            if turn > death_turn:
                contradictions.append(Contradiction(
                    contradiction_type=ContradictionType.CAUSAL,
                    severity=1.0,
                    description=f"角色在第{death_turn}回合已死亡，但第{turn}回合执行了动作",
                    involved_entities=[agent_id],
                    evidence=f"死亡记录：turn {death_turn}，动作：{action}",
                    suggested_fix="要么修改死亡记录，要么修改动作时间，或解释为回忆/幻觉",
                    detected_at_turn=turn
                ))

        # 检查"知道"与"不可能知道"的矛盾
        impossible_after_keywords = [
            (r"死亡|去世|死去|丧命", "死亡状态"),
            (r"被封印|被困", "被控制状态"),
        ]

        for pattern, state in impossible_after_keywords:
            if agent_id in self._death_records:
                continue  # 已处理死亡矛盾
            if re.search(pattern, action):
                # 检查之前的记忆是否有矛盾
                for past_turn, _, past_desc in self._event_timeline:
                    if past_turn >= turn:
                        continue
                    if "死亡" in past_desc and "死亡" in action:
                        contradictions.append(Contradiction(
                            contradiction_type=ContradictionType.CAUSAL,
                            severity=0.8,
                            description=f"角色行为与过去已确立的死亡事实矛盾",
                            involved_entities=[agent_id],
                            evidence=f"过去事件：{past_desc}，当前动作：{action}",
                            suggested_fix="确认角色状态一致性",
                            detected_at_turn=turn
                        ))
                        break

        return contradictions

    # ========== 属性冲突检测 ==========

    def _check_attribute_contradictions(
        self,
        agent_id: str,
        new_attributes: Dict[str, Any],
        turn: int
    ) -> List[Contradiction]:
        """检测属性冲突"""
        contradictions = []

        if agent_id not in self._attribute_snapshots:
            return contradictions

        # 获取最近一次快照
        snapshots = self._attribute_snapshots[agent_id]
        recent_key = None
        recent_snapshot = None
        for key in sorted(snapshots.keys(), reverse=True):
            if key.startswith("turn_"):
                turn_num = int(key.split("_")[1])
                if turn_num < turn:
                    recent_key = key
                    recent_snapshot = snapshots[key]
                    break

        if not recent_snapshot:
            return contradictions

        # 检查性格关键词冲突
        personality_conflicts = [
            ("勇敢", ["胆怯", "懦弱", "害怕"]),
            ("善良", ["邪恶", "残忍", "恶毒"]),
            ("忠诚", ["背叛", "叛变", "欺骗"]),
            ("聪明", ["愚蠢", "愚笨", "笨拙"]),
            ("冷静", ["暴躁", "冲动", "易怒"]),
        ]

        old_personality = recent_snapshot.get("personality", "")
        new_personality = new_attributes.get("personality", old_personality)

        if old_personality and new_personality:
            for core_trait, contradictions_traits in personality_conflicts:
                if core_trait in old_personality:
                    for contr_trait in contradictions_traits:
                        if contr_trait in new_personality:
                            contradictions.append(Contradiction(
                                contradiction_type=ContradictionType.ATTRIBUTE,
                                severity=0.7,
                                description=f"角色性格从'{core_trait}'突变为'{contr_trait}'",
                                involved_entities=[agent_id],
                                evidence=f"之前性格：{old_personality}，新性格：{new_personality}",
                                suggested_fix="如果要改变性格，需要渐变过程或重大事件触发",
                                detected_at_turn=turn
                            ))

        # 检查身份冲突
        old_identity = recent_snapshot.get("identity", "")
        new_identity = new_attributes.get("identity", old_identity)

        if old_identity and new_identity and old_identity != new_identity:
            # 排除合理的身份变化
            normal_changes = ["晋升", "拜师", "觉醒", "转修"]
            is_normal_change = any(change in str(new_attributes) for change in normal_changes)

            if not is_normal_change:
                contradictions.append(Contradiction(
                    contradiction_type=ContradictionType.ATTRIBUTE,
                    severity=0.9,
                    description=f"角色身份发生重大变化（排除合理变化）",
                    involved_entities=[agent_id],
                    evidence=f"之前身份：{old_identity}，新身份：{new_identity}",
                    suggested_fix="确认是合理的世界事件导致，还是设定错误",
                    detected_at_turn=turn
                ))

        return contradictions

    # ========== 时序矛盾检测 ==========

    def _check_temporal_contradictions(
        self,
        event: str,
        turn: int
    ) -> List[Contradiction]:
        """检测时序矛盾"""
        contradictions = []

        # 检查时间状语与当前时间是否矛盾
        temporal_patterns = [
            (r"昨天|昨日", "past"),
            (r"明天|明日", "future"),
            (r"刚才|方才|不久", "recent"),
            (r"很久以前|曾经|当年", "long_ago"),
        ]

        current_day_estimate = turn // 8 + 1  # 粗略估算

        for pattern, temporal_type in temporal_patterns:
            if re.search(pattern, event):
                # 检查是否存在矛盾的时间记忆
                for past_turn, _, past_desc in self._event_timeline[-10:]:  # 只检查最近10条
                    if "今天" in past_desc and "今天" in event and abs(past_turn - turn) > 3:
                        # 同一天但回合差太大
                        contradictions.append(Contradiction(
                            contradiction_type=ContradictionType.TEMPORAL,
                            severity=0.5,
                            description=f"时间状语与事件发生时间矛盾",
                            involved_entities=[],
                            evidence=f"时间状语包含'{pattern}'，但事件序列暗示不同时间",
                            suggested_fix="统一时间表达",
                            detected_at_turn=turn
                        ))
                        break

        return contradictions

    # ========== 关系矛盾检测 ==========

    def _check_relation_contradictions(
        self,
        agent_id: str,
        target_id: str,
        action: str,
        turn: int
    ) -> List[Contradiction]:
        """检测关系矛盾"""
        contradictions = []

        if not target_id:
            return contradictions

        # 检查与已知敌友关系的一致性
        hostile_keywords = ["攻击", "刺杀", "暗算", "背叛", "欺骗"]
        friendly_keywords = ["帮助", "保护", "感谢", "信任"]

        is_hostile_action = any(kw in action for kw in hostile_keywords)
        is_friendly_action = any(kw in action for kw in friendly_keywords)

        # 这里可以扩展，检查角色间历史关系
        # 目前是简化版，未来可以结合knowledge_graph的关系数据
        if is_hostile_action and is_friendly_action:
            contradictions.append(Contradiction(
                contradiction_type=ContradictionType.RELATION,
                severity=0.4,
                description=f"动作同时包含敌意和友好行为",
                involved_entities=[agent_id, target_id],
                evidence=action,
                suggested_fix="明确角色意图",
                detected_at_turn=turn
            ))

        return contradictions

    # ========== 知识矛盾检测 ==========

    def _check_knowledge_contradictions(
        self,
        event: str,
        turn: int
    ) -> List[Contradiction]:
        """检测与已有世界知识的矛盾"""
        contradictions = []

        event_lower = event.lower()

        # 检查是否与已确立知识矛盾
        for knowledge in self._knowledge_cache:
            # 简单检查：knowledge中的关键词与event的矛盾
            knowledge_words = knowledge.split()
            for word in knowledge_words:
                if len(word) < 3:  # 忽略短词
                    continue
                # 检测明显的否定矛盾
                negation_patterns = [
                    (f"不{word}", word),
                    (f"没有{word}", word),
                    (f"不是{word}", word),
                ]
                for neg, pos in negation_patterns:
                    if neg in event_lower and word in self._knowledge_cache:
                        contradictions.append(Contradiction(
                            contradiction_type=ContradictionType.KNOWLEDGE,
                            severity=0.6,
                            description=f"事件与已确立的世界知识矛盾",
                            involved_entities=[],
                            evidence=f"已知知识包含'{word}'，但事件描述'{neg}'",
                            suggested_fix="确认世界观设定的准确性",
                            detected_at_turn=turn
                        ))

        return contradictions

    # ========== 主检测接口 ==========

    def check_event(
        self,
        agent_id: str,
        event: str,
        action: str,
        turn: int,
        attributes: Optional[Dict[str, Any]] = None,
        target_id: Optional[str] = None
    ) -> List[Contradiction]:
        """
        检测单个事件的一致性

        Returns:
            检测到的矛盾列表
        """
        all_contradictions = []

        # 1. 因果矛盾检测
        all_contradictions.extend(
            self._check_causal_contradictions(agent_id, action, turn)
        )

        # 2. 属性冲突检测
        if attributes:
            all_contradictions.extend(
                self._check_attribute_contradictions(agent_id, attributes, turn)
            )

        # 3. 时序矛盾检测
        all_contradictions.extend(
            self._check_temporal_contradictions(event, turn)
        )

        # 4. 关系矛盾检测
        if target_id:
            all_contradictions.extend(
                self._check_relation_contradictions(agent_id, target_id, action, turn)
            )

        # 5. 知识矛盾检测
        all_contradictions.extend(
            self._check_knowledge_contradictions(event, turn)
        )

        return all_contradictions

    def check_consistency(
        self,
        events: List[Dict[str, Any]],
        agents: Dict[str, Dict[str, Any]],
        turn: int
    ) -> ConsistencyReport:
        """
        批量检测一致性

        Args:
            events: 事件列表，每项包含 event, action, actor, target 等
            agents: 角色字典
            turn: 当前回合
        """
        start_time = time.time()

        report = ConsistencyReport(world_id=self.world_id)
        report.last_check_turn = turn

        # 先更新死亡记录
        for agent_id, agent_data in agents.items():
            if agent_data.get("is_alive", True) is False:
                death_turn = agent_data.get("death_turn", turn)
                self.record_death(agent_id, death_turn)

        # 检查每个事件
        for event_data in events:
            agent_id = event_data.get("actor", event_data.get("agent_id", ""))
            event = event_data.get("event", "")
            action = event_data.get("action", event)
            target_id = event_data.get("target", "")
            event_turn = event_data.get("turn", turn)

            contradictions = self.check_event(
                agent_id=agent_id,
                event=event,
                action=action,
                turn=event_turn,
                attributes=agents.get(agent_id, {}),
                target_id=target_id
            )

            report.contradictions_found.extend(contradictions)
            report.total_checks += 1

            # 更新事件时间线
            self.add_event(event_turn, event_data.get("type", "normal"), event)

        # 计算一致性分数
        if report.total_checks > 0:
            total_severity = sum(c.severity for c in report.contradictions_found)
            max_possible_severity = report.total_checks * 1.0
            report.consistency_score = max(0.0, 1.0 - (total_severity / max_possible_severity))

        report.check_duration_ms = (time.time() - start_time) * 1000

        return report

    def quick_check(self, text: str, agent_id: str, turn: int) -> Optional[Contradiction]:
        """
        快速检测文本中的明显矛盾

        用于在生成时实时检测
        """
        contradictions = self.check_event(
            agent_id=agent_id,
            event=text,
            action=text,
            turn=turn
        )

        # 只返回高严重度的矛盾
        for c in contradictions:
            if c.severity >= 0.7:
                return c

        return None if not contradictions else contradictions[0]
