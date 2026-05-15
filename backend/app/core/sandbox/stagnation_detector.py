"""
D02 演化停滞检测
5项指标实时检测叙事停滞，作为D01冲突注入的自动触发器
"""
import statistics
import time
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from enum import Enum
from datetime import datetime, timezone


class StagnationType(Enum):
    """停滞类型"""
    EVENT_DENSITY_DROP = "event_density_drop"
    RELATIONSHIP_STALL = "relationship_stall"
    GOAL_STAGNATION = "goal_stagnation"
    CONFLICT_ABSENCE = "conflict_absence"
    LOW_NOVELTY = "low_novelty"


@dataclass
class StagnationAlert:
    """单条停滞告警"""
    stagnation_type: StagnationType
    severity: float
    description: str
    metric_value: float
    threshold: float
    current_turn: int
    suggested_action: str

    def to_dict(self) -> dict:
        return {
            "type": self.stagnation_type.value,
            "severity": self.severity,
            "description": self.description,
            "metric_value": round(self.metric_value, 4),
            "threshold": self.threshold,
            "current_turn": self.current_turn,
            "suggested_action": self.suggested_action,
        }


@dataclass
class StagnationReport:
    """停滞检测报告"""
    overall_stagnation_score: float
    is_stagnant: bool
    alerts: List[StagnationAlert]
    metrics_snapshot: Dict[str, float]
    current_turn: int
    timestamp: str

    def to_dict(self) -> dict:
        return {
            "overall_stagnation_score": round(self.overall_stagnation_score, 4),
            "is_stagnant": self.is_stagnant,
            "alerts": [a.to_dict() for a in self.alerts],
            "metrics_snapshot": {k: round(v, 4) for k, v in self.metrics_snapshot.items()},
            "current_turn": self.current_turn,
            "timestamp": self.timestamp,
        }


class StagnationDetector:
    """
    演化停滞检测器

    5项检测指标（与D01 HeatMetrics对齐）：
    1. event_density          — 近期事件产出密度
    2. relationship_change    — 角色关系变化频率
    3. goal_achievement       — 故事时刻/目标达成频率
    4. conflict_activity      — 冲突产生与解决活跃度
    5. novelty_introduction   — 新类型事件引入率

    每项指标都有可配置的阈值和冷却期，支持趋势分析（连续下降检测）。
    输出 StagnationReport 供上层（D01 ConflictInjector / D03 DisturbanceInjector）消费。
    """

    # 默认阈值（适用于大多数世界模板）
    DEFAULT_THRESHOLDS = {
        "event_density_min": 0.25,
        "relationship_change_min": 0.10,
        "goal_achievement_min": 0.10,
        "conflict_activity_min": 0.08,
        "novelty_introduction_min": 0.12,
        "window_size": 10,               # 滑动窗口大小（回合数）
        "stagnation_threshold": 0.35,    # 综合停滞分告警阈值
        "trend_window": 3,               # 趋势检测窗口
        "alert_cooldown": 5,             # 同类型告警冷却
    }

    # 各类型对应的建议动作
    SUGGESTED_ACTIONS = {
        StagnationType.EVENT_DENSITY_DROP: "注入突发性事件，提高事件产出节奏",
        StagnationType.RELATIONSHIP_STALL: "引入新角色或制造角色间矛盾，激活关系网络",
        StagnationType.GOAL_STAGNATION: "为关键角色设置紧迫目标或截止期限",
        StagnationType.CONFLICT_ABSENCE: "注入人际或外部冲突，打破平稳局面",
        StagnationType.LOW_NOVELTY: "引入世界观中未探索的元素或设定",
    }

    def __init__(self, world_id: str, thresholds: Optional[Dict] = None):
        self.world_id = world_id
        self.thresholds = {**self.DEFAULT_THRESHOLDS, **(thresholds or {})}
        self._metrics_history: List[Dict] = []  # 逐回合指标快照
        self._alerts: List[StagnationAlert] = []
        self._last_alert_turn: Dict[str, int] = {}  # type -> last turn

    def assess(
        self,
        recent_events: List[Dict],
        current_turn: int,
    ) -> StagnationReport:
        """
        执行完整的停滞检测

        Args:
            recent_events: 最近N回合事件列表，每项含 turn/action_type/tags 等
            current_turn:   当前回合数

        Returns:
            StagnationReport
        """
        window = self.thresholds["window_size"]
        events = recent_events[-window:] if len(recent_events) > window else recent_events

        # 1. 计算5项原始指标
        metrics = self._compute_metrics(events, current_turn)

        # 2. 记录历史
        self._metrics_history.append(metrics)
        if len(self._metrics_history) > 50:
            self._metrics_history = self._metrics_history[-50:]

        # 3. 逐项检测告警
        alerts = self._detect_alerts(metrics, recent_events, current_turn)

        # 4. 综合停滞分
        stagnation_score = self._compute_stagnation_score(metrics, alerts)

        # 5. 生成报告
        report = StagnationReport(
            overall_stagnation_score=stagnation_score,
            is_stagnant=stagnation_score > self.thresholds["stagnation_threshold"],
            alerts=alerts,
            metrics_snapshot=metrics,
            current_turn=current_turn,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        return report

    # ── 指标计算 ────────────────────────────────────────────

    def _compute_metrics(self, events: List[Dict], current_turn: int) -> Dict[str, float]:
        """计算5项原始指标（归一化到 0-1，1=最活跃）"""
        if not events:
            return {
                "event_density": 0.0,
                "relationship_change": 0.0,
                "goal_achievement": 0.0,
                "conflict_activity": 0.0,
                "novelty_introduction": 0.0,
            }

        n = len(events)

        # 事件密度：实际事件数 / 窗口最大期望
        max_expected = min(self.thresholds["window_size"], 100)
        event_density = min(1.0, n / max(max_expected, 1))

        # 关系变化率：interaction 类型占比
        interaction_count = sum(
            1 for e in events if e.get("action_type") in ("interaction", "dialogue")
        )
        relationship_change = interaction_count / n

        # 目标达成率：story_moment 类型占比
        story_count = sum(
            1 for e in events if e.get("action_type") == "story_moment"
        )
        goal_achievement = story_count / n

        # 冲突活跃度：含冲突标签的事件占比
        conflict_count = sum(
            1 for e in events if "conflict" in e.get("tags", [])
        )
        resolved_count = sum(
            1 for e in events if "resolved" in e.get("tags", [])
        )
        raw_conflict_activity = (conflict_count - resolved_count) / n
        conflict_activity = max(0.0, raw_conflict_activity)

        # 新颖性引入率：不同类型的事件数 / 总事件数
        unique_types = len(set(e.get("action_type", "normal") for e in events))
        novelty_introduction = unique_types / max(len(set(
            e.get("action_type", "normal") for e in events
        )), 3)

        return {
            "event_density": round(event_density, 4),
            "relationship_change": round(relationship_change, 4),
            "goal_achievement": round(goal_achievement, 4),
            "conflict_activity": round(conflict_activity, 4),
            "novelty_introduction": round(novelty_introduction, 4),
        }

    # ── 告警检测 ────────────────────────────────────────────

    def _detect_alerts(
        self,
        metrics: Dict[str, float],
        events: List[Dict],
        current_turn: int,
    ) -> List[StagnationAlert]:
        """逐项检测指标是否低于阈值，结合趋势判断"""
        alerts: List[StagnationAlert] = []
        checks = [
            ("event_density", StagnationType.EVENT_DENSITY_DROP,
             self.thresholds["event_density_min"]),
            ("relationship_change", StagnationType.RELATIONSHIP_STALL,
             self.thresholds["relationship_change_min"]),
            ("goal_achievement", StagnationType.GOAL_STAGNATION,
             self.thresholds["goal_achievement_min"]),
            ("conflict_activity", StagnationType.CONFLICT_ABSENCE,
             self.thresholds["conflict_activity_min"]),
            ("novelty_introduction", StagnationType.LOW_NOVELTY,
             self.thresholds["novelty_introduction_min"]),
        ]

        for metric_key, st_type, threshold in checks:
            value = metrics.get(metric_key, 1.0)
            should_alert = False
            severity = 0.0

            # 条件A：当前值低于阈值
            if value < threshold:
                severity = max(0.0, 1.0 - (value / max(threshold, 0.01)))
                should_alert = True

            # 条件B：连续下降趋势（最近3次检测持续下降）
            if not should_alert and len(self._metrics_history) >= 3:
                recent = self._metrics_history[-3:]
                values = [m.get(metric_key, 1.0) for m in recent]
                if all(values[i] > values[i + 1] for i in range(len(values) - 1)):
                    trend_severity = max(0.0, 1.0 - (values[-1] / 0.5))
                    if trend_severity > 0.3:
                        severity = trend_severity
                        should_alert = True

            if should_alert:
                # 冷却检查（last_turn=0 表示从未告警过，不冷却）
                last_turn = self._last_alert_turn.get(st_type.value, 0)
                if last_turn > 0 and current_turn - last_turn < self.thresholds["alert_cooldown"]:
                    continue

                alert = StagnationAlert(
                    stagnation_type=st_type,
                    severity=round(min(1.0, severity), 3),
                    description=self._describe_stagnation(st_type, metric_key, value, threshold),
                    metric_value=value,
                    threshold=threshold,
                    current_turn=current_turn,
                    suggested_action=self.SUGGESTED_ACTIONS.get(st_type, "继续观察"),
                )
                alerts.append(alert)
                self._alerts.append(alert)
                self._last_alert_turn[st_type.value] = current_turn

        # 保留最近50条告警
        if len(self._alerts) > 50:
            self._alerts = self._alerts[-50:]

        return alerts

    def _describe_stagnation(
        self, st_type: StagnationType, metric_key: str,
        value: float, threshold: float,
    ) -> str:
        """生成可读的停滞描述"""
        descriptions = {
            StagnationType.EVENT_DENSITY_DROP:
                f"事件密度偏低 ({value:.2f} < {threshold})，叙事节奏放缓",
            StagnationType.RELATIONSHIP_STALL:
                f"角色互动不足 ({value:.2f} < {threshold})，关系网络趋于静止",
            StagnationType.GOAL_STAGNATION:
                f"缺少故事时刻 ({value:.2f} < {threshold})，目标推进停滞",
            StagnationType.CONFLICT_ABSENCE:
                f"冲突活跃度过低 ({value:.2f} < {threshold})，缺乏戏剧张力",
            StagnationType.LOW_NOVELTY:
                f"事件类型单一 ({value:.2f} < {threshold})，缺乏新意",
        }
        return descriptions.get(st_type, f"{metric_key} 指标异常 ({value:.2f})")

    # ── 综合评分 ────────────────────────────────────────────

    def _compute_stagnation_score(
        self,
        metrics: Dict[str, float],
        alerts: List[StagnationAlert],
    ) -> float:
        """
        综合停滞分（0-1, 越高越停滞）

        算法：(阈值差距的加权平均) + 告警惩罚
        """
        weights = {
            "event_density": 0.25,
            "relationship_change": 0.20,
            "goal_achievement": 0.25,
            "conflict_activity": 0.15,
            "novelty_introduction": 0.15,
        }

        thresholds_map = {
            "event_density": self.thresholds["event_density_min"],
            "relationship_change": self.thresholds["relationship_change_min"],
            "goal_achievement": self.thresholds["goal_achievement_min"],
            "conflict_activity": self.thresholds["conflict_activity_min"],
            "novelty_introduction": self.thresholds["novelty_introduction_min"],
        }

        score = 0.0
        for key, weight in weights.items():
            value = metrics.get(key, 1.0)
            thresh = thresholds_map.get(key, 0.2)
            # 距离阈值越远，贡献越大
            if value < thresh:
                score += weight * (1.0 - value / max(thresh, 0.01))
            else:
                score += weight * max(0.0, 1.0 - value)

        # 活跃告警惩罚
        alert_penalty = len(alerts) * 0.05
        score = min(1.0, score + alert_penalty)

        return round(score, 4)

    # ── 趋势分析 ────────────────────────────────────────────

    def get_trend(self, metric_key: str, window: int = 5) -> Dict:
        """
        获取指定指标的短期趋势

        Returns:
            {"direction": "up"/"down"/"stable", "delta": float, "values": [...]}
        """
        if len(self._metrics_history) < 2:
            return {"direction": "stable", "delta": 0.0, "values": []}

        recent = self._metrics_history[-window:]
        values = [m.get(metric_key, 0.5) for m in recent]

        if len(values) >= 2:
            delta = values[-1] - values[0]
            if delta > 0.05:
                direction = "up"
            elif delta < -0.05:
                direction = "down"
            else:
                direction = "stable"
        else:
            direction = "stable"
            delta = 0.0

        return {
            "direction": direction,
            "delta": round(delta, 4),
            "values": [round(v, 4) for v in values],
        }

    # ── 快照/清空 ────────────────────────────────────────────

    def get_alerts(self, since_turn: Optional[int] = None) -> List[Dict]:
        """获取告警历史"""
        if since_turn is not None:
            return [a.to_dict() for a in self._alerts if a.current_turn >= since_turn]
        return [a.to_dict() for a in self._alerts[-20:]]

    def get_history(self, limit: int = 20) -> List[Dict]:
        """获取指标历史"""
        return self._metrics_history[-limit:]

    def to_dict(self) -> Dict:
        """完整快照"""
        last_report = None
        latest_history = self._metrics_history[-1] if self._metrics_history else {}

        return {
            "world_id": self.world_id,
            "thresholds": self.thresholds,
            "latest_metrics": latest_history,
            "active_alert_count": len(self._alerts),
            "recent_alerts": self.get_alerts(limit=5),
        }
