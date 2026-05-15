"""
C02 角色一致性守护
3类实时检测：行为一致性 / 语言风格 / 关系逻辑
偏离超阈值时触发LLM辅助修复prompt，恢复率目标≥85%
"""
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from datetime import datetime, timezone


class DeviationType(Enum):
    BEHAVIOR = "behavior"          # 行为偏离：动作与性格/身份不符
    LANGUAGE = "language"          # 语言偏离：对话风格突变
    RELATION = "relation"          # 关系偏离：互动违反已建立关系


class Severity(Enum):
    NORMAL = "normal"              # 正常，无需干预
    MILD = "mild"                  # 轻微偏离，记录但不干预
    MODERATE = "moderate"          # 中度偏离，触发软纠正
    SEVERE = "severe"              # 严重偏离，强制修正


@dataclass
class Deviation:
    """单条偏离记录"""
    deviation_type: DeviationType
    severity: Severity
    score: float                   # 0-1, 越高越偏离
    agent_id: str
    agent_name: str
    description: str
    evidence: str                  # 证据文本
    expected_pattern: str          # 期望的行为/语言/关系模式
    suggested_correction: str      # LLM生成的修正建议
    detected_at_turn: int = 0

    def to_dict(self) -> dict:
        return {
            "type": self.deviation_type.value,
            "severity": self.severity.value,
            "score": round(self.score, 3),
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "description": self.description,
            "evidence": self.evidence[:120],
            "expected_pattern": self.expected_pattern[:120],
            "suggested_correction": self.suggested_correction[:200],
            "detected_at_turn": self.detected_at_turn,
        }


@dataclass
class GuardianReport:
    """一致性守护报告"""
    world_id: str
    total_checks: int = 0
    deviations: List[Deviation] = field(default_factory=list)
    overall_consistency: float = 1.0  # 0-1
    recovery_rate: float = 0.0        # 干预后恢复率
    check_duration_ms: float = 0.0
    last_check_turn: int = 0

    def to_dict(self) -> dict:
        return {
            "world_id": self.world_id,
            "total_checks": self.total_checks,
            "deviations": [d.to_dict() for d in self.deviations],
            "overall_consistency": round(self.overall_consistency, 3),
            "recovery_rate": round(self.recovery_rate, 3),
            "check_duration_ms": round(self.check_duration_ms, 1),
            "last_check_turn": self.last_check_turn,
        }


class ConsistencyGuardian:
    """
    角色一致性守护器

    持续监测所有NPC的三个维度：
    1. 行为一致性：动作是否匹配预设的性格/身份/目标
    2. 语言风格：对话是否匹配角色设定语言风格
    3. 关系逻辑：互动是否符合已建立的关系网络

    偏离阈值：
    - <0.3: 正常
    - 0.3-0.5: 轻微
    - 0.5-0.7: 中度（触发LLM软纠正）
    - >0.7: 严重（强制修正prompt注入）
    """

    # 可配置阈值
    DEFAULT_THRESHOLDS = {
        "mild_threshold": 0.3,
        "moderate_threshold": 0.5,
        "severe_threshold": 0.7,
        "check_interval": 10,         # 每10回合全量检测
        "intervention_cooldown": 5,   # 同一NPC干预冷却
    }

    def __init__(self, world_id: str, thresholds: Optional[Dict] = None):
        self.world_id = world_id
        self.thresholds = {**self.DEFAULT_THRESHOLDS, **(thresholds or {})}
        self._deviations: List[Deviation] = []
        self._interventions: Dict[str, int] = {}     # agent_id -> last_intervention_turn
        self._recovery_tracking: Dict[str, List[bool]] = {}  # agent_id -> [recovered, ...]
        self._last_check_turn = 0

    def check_agent(
        self,
        agent: Any,
        recent_actions: List[Dict],
        recent_dialogues: List[Dict],
        relationships: Dict[str, Any],
        current_turn: int,
    ) -> List[Deviation]:
        """
        对单个NPC执行三维一致性检测

        Args:
            agent: Agent实例（含config.name/identity/personality/goals）
            recent_actions: 最近N条动作
            recent_dialogues: 最近N条对话
            relationships: 关系网络 {target_id: relation_info}
            current_turn: 当前回合
        """
        deviations: List[Deviation] = []
        config = agent.config if hasattr(agent, 'config') else agent

        # 1. 行为一致性检测
        behavior_dev = self._check_behavior(config, recent_actions, current_turn)
        if behavior_dev:
            deviations.append(behavior_dev)

        # 2. 语言风格检测
        language_dev = self._check_language_style(config, recent_dialogues, current_turn)
        if language_dev:
            deviations.append(language_dev)

        # 3. 关系逻辑检测
        relation_dev = self._check_relation_logic(
            config, recent_actions, recent_dialogues, relationships, current_turn
        )
        if relation_dev:
            deviations.append(relation_dev)

        # 过滤：冷却期内同类型不重复报告
        filtered = []
        last_intervention = self._interventions.get(config.agent_id, -999)
        cooldown = self.thresholds["intervention_cooldown"]
        for d in deviations:
            if d.severity in (Severity.MODERATE, Severity.SEVERE):
                if current_turn - last_intervention < cooldown:
                    continue
                self._interventions[config.agent_id] = current_turn
            filtered.append(d)

        self._deviations.extend(filtered)
        if len(self._deviations) > 200:
            self._deviations = self._deviations[-200:]

        return filtered

    # ── 行为检测 ──────────────────────────────────────────

    def _check_behavior(
        self, config: Any, actions: List[Dict], turn: int
    ) -> Optional[Deviation]:
        """检测动作是否匹配角色性格/身份/目标"""
        if len(actions) < 3:
            return None

        personality = getattr(config, 'personality', '') or ''
        identity = getattr(config, 'identity', '') or ''
        goals = getattr(config, 'goals', []) or []
        agent_id = getattr(config, 'agent_id', 'unknown')
        agent_name = getattr(config, 'name', 'unknown')

        # 规则1：性格-行为匹配
        personality_traits = self._extract_traits(personality)
        action_texts = [a.get('action', '') or a.get('description', '') for a in actions[-5:]]
        behavior_score = self._personality_action_mismatch(personality_traits, action_texts)

        # 规则2：身份一致性
        identity_keywords = set(identity.lower().split())
        action_violations = 0
        for text in action_texts:
            if self._identity_violation(identity_keywords, text.lower()):
                action_violations += 1
        identity_score = action_violations / max(len(action_texts), 1)

        # 综合
        overall = max(behavior_score, identity_score * 0.8)
        severity = self._score_to_severity(overall)

        if severity == Severity.NORMAL:
            return None

        return Deviation(
            deviation_type=DeviationType.BEHAVIOR,
            severity=severity,
            score=overall,
            agent_id=agent_id,
            agent_name=agent_name,
            description=f"行为偏离检测：性格={personality[:20]}，身份={identity[:20]}",
            evidence=action_texts[-1][:100] if action_texts else "",
            expected_pattern=f"应符合{personality[:30]}性格与{identity[:30]}身份的行为模式",
            suggested_correction=self._generate_behavior_fix(personality, identity, action_texts[-1] if action_texts else ""),
            detected_at_turn=turn,
        )

    def _extract_traits(self, personality: str) -> List[str]:
        """提取性格关键词"""
        traits = []
        keywords = ["冷静", "冲动", "善良", "邪恶", "谨慎", "鲁莽", "傲慢", "谦逊",
                     "阴险", "正直", "狡诈", "忠诚", "勇敢", "胆怯", "智慧", "愚钝"]
        for kw in keywords:
            if kw in personality:
                traits.append(kw)
        return traits or ["中性"]

    def _personality_action_mismatch(self, traits: List[str], actions: List[str]) -> float:
        """检测行为是否与性格特征矛盾（简化规则匹配）"""
        mismatch_count = 0
        for action in actions:
            for trait in traits:
                if self._trait_action_conflict(trait, action):
                    mismatch_count += 1
                    break
        return min(1.0, mismatch_count / max(len(actions), 1) * 1.5)

    def _trait_action_conflict(self, trait: str, action: str) -> bool:
        """简单规则判断特定性格与行为是否矛盾"""
        conflicts = {
            "谨慎": ["鲁莽地", "毫不顾忌", "不假思索", "贸然"],
            "善良": ["残忍地", "无情地", "冷酷地", "虐杀"],
            "正直": ["偷偷地", "暗中", "贿赂", "欺骗性地"],
            "忠诚": ["背叛", "出卖", "暗中勾结"],
            "冷静": ["暴怒", "失控地", "歇斯底里", "发狂"],
        }
        for keyword in conflicts.get(trait, []):
            if keyword in action:
                return True
        return False

    def _identity_violation(self, identity_kw: set, action_text: str) -> bool:
        """检测行为是否严重违背身份"""
        # 简化规则：修仙者不应使用现代词汇，商人不应无偿施舍等
        immortal_kw = {"修炼", "灵气", "仙", "道", "法术", "丹"}
        modern_kw = {"手机", "电脑", "咖啡", "公司", "股票", "地铁"}
        if identity_kw & immortal_kw and modern_kw & set(action_text.split()):
            return True
        return False

    # ── 语言风格检测 ──────────────────────────────────────

    def _check_language_style(
        self, config: Any, dialogues: List[Dict], turn: int
    ) -> Optional[Deviation]:
        """检测对话是否匹配角色设定的语言风格"""
        if len(dialogues) < 2:
            return None

        agent_id = getattr(config, 'agent_id', 'unknown')
        agent_name = getattr(config, 'name', 'unknown')
        personality = getattr(config, 'personality', '')
        identity = getattr(config, 'identity', '')

        # 提取最近的对话文本
        lines = [d.get('content', '') or d.get('text', '') for d in dialogues[-5:]]
        lines = [l for l in lines if l]

        if not lines:
            return None

        # 规则：检测风格突变
        style_score = self._style_volatility(lines, personality)

        severity = self._score_to_severity(style_score)
        if severity == Severity.NORMAL:
            return None

        return Deviation(
            deviation_type=DeviationType.LANGUAGE,
            severity=severity,
            score=style_score,
            agent_id=agent_id,
            agent_name=agent_name,
            description=f"语言风格偏离：性格={personality[:20]}",
            evidence=lines[-1][:100],
            expected_pattern=f"应符合{personality[:30]}性格的语言风格",
            suggested_correction=f"调整对话语气，保持{personality[:20]}性格特征的语言风格",
            detected_at_turn=turn,
        )

    def _style_volatility(self, lines: List[str], personality: str) -> float:
        """检测语言风格波动程度"""
        if len(lines) < 2:
            return 0.0

        # 简化：比较句子长度、感叹号使用、敬语等特征
        features = []
        for line in lines:
            features.append({
                "len": len(line),
                "exclam": line.count("！") + line.count("!"),
                "formal": sum(1 for w in ["您", "请", "阁下", "大人", "师尊"] if w in line),
                "casual": sum(1 for w in ["哈哈", "嗯", "哦", "吧", "嘛"] if w in line),
            })

        # 计算相邻对话的特征变化
        volatility = 0.0
        for i in range(1, len(features)):
            prev, curr = features[i - 1], features[i]
            if prev["len"] > 0:
                len_change = abs(curr["len"] - prev["len"]) / prev["len"]
                volatility += len_change * 0.3
            volatility += abs(curr["exclam"] - prev["exclam"]) * 0.15
            volatility += abs(curr["formal"] - prev["formal"]) * 0.3
            volatility += abs(curr["casual"] - prev["casual"]) * 0.25

        return min(1.0, volatility / len(features))

    # ── 关系逻辑检测 ──────────────────────────────────────

    def _check_relation_logic(
        self,
        config: Any,
        actions: List[Dict],
        dialogues: List[Dict],
        relationships: Dict[str, Any],
        turn: int,
    ) -> Optional[Deviation]:
        """检测互动是否违反已建立的关系网络"""
        agent_id = getattr(config, 'agent_id', 'unknown')
        agent_name = getattr(config, 'name', 'unknown')

        if not relationships or not actions:
            return None

        # 检查最近互动对象的关系一致性
        violation_count = 0
        evidence = ""
        for action in actions[-5:]:
            target = action.get('target', '') or action.get('target_name', '')
            if not target:
                continue
            # 查找关系
            rel = self._find_relationship(relationships, target)
            if rel:
                rel_type = rel.get('type', '')
                action_type = action.get('action_type', '')
                if self._relation_action_conflict(rel_type, action_type, action.get('action', '')):
                    violation_count += 1
                    evidence = action.get('action', '')[:100]

        rel_score = violation_count / max(len(actions[-5:]), 1)
        severity = self._score_to_severity(rel_score)

        if severity == Severity.NORMAL:
            return None

        return Deviation(
            deviation_type=DeviationType.RELATION,
            severity=severity,
            score=rel_score,
            agent_id=agent_id,
            agent_name=agent_name,
            description=f"关系逻辑偏离：违反已建立的关系模式",
            evidence=evidence,
            expected_pattern="互动行为应符合已有关系类型",
            suggested_correction=f"检查与目标角色的关系状态，调整互动方式以保持一致性",
            detected_at_turn=turn,
        )

    def _find_relationship(self, relationships: Dict, target_name: str) -> Optional[Dict]:
        """在关系网络中查找目标"""
        for rid, rel in relationships.items():
            if isinstance(rel, dict):
                if rel.get('source') == target_name or rel.get('target') == target_name:
                    return rel
        return None

    def _relation_action_conflict(self, rel_type: str, action_type: str, action_text: str) -> bool:
        """检测行为是否与关系矛盾"""
        # 敌人关系不应有亲密互动
        if rel_type in ("enemy", "敌对"):
            friendly = ["帮助", "关心", "拥抱", "倾诉", "信任", "合作"]
            if any(w in action_text for w in friendly):
                return True
        # 朋友关系不应有敌对行为
        if rel_type in ("friend", "好友", "ally", "盟友"):
            hostile = ["攻击", "背叛", "陷害", "出卖", "暗算"]
            if any(w in action_text for w in hostile):
                return True
        return False

    # ── 辅助方法 ──────────────────────────────────────────

    def _score_to_severity(self, score: float) -> Severity:
        if score >= self.thresholds["severe_threshold"]:
            return Severity.SEVERE
        elif score >= self.thresholds["moderate_threshold"]:
            return Severity.MODERATE
        elif score >= self.thresholds["mild_threshold"]:
            return Severity.MILD
        return Severity.NORMAL

    def _generate_behavior_fix(self, personality: str, identity: str, action: str) -> str:
        """生成行为修正建议（轻量规则版，LLM版通过async方法）"""
        return f"作为{personality}的{identity}，建议重新考虑'{action[:30]}'这一行为的合理性"

    async def generate_llm_fix(
        self, deviation: Deviation, llm_client
    ) -> str:
        """使用LLM生成更精准的修正建议"""
        prompt = f"""角色信息：
- 名称：{deviation.agent_name}
- 偏离类型：{deviation.deviation_type.value}
- 偏离描述：{deviation.description}
- 证据：{deviation.evidence}
- 期望模式：{deviation.expected_pattern}

请生成1-2句简短的修正建议，帮助角色回归一致的行为模式。直接输出建议："""
        try:
            completion = await llm_client.chat.completions.create(
                model="auto",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=150,
            )
            return completion.choices[0].message.content or deviation.suggested_correction
        except Exception:
            return deviation.suggested_correction

    # ── 统计方法 ──────────────────────────────────────────

    def track_recovery(self, agent_id: str, recovered: bool):
        """追踪干预后恢复情况"""
        if agent_id not in self._recovery_tracking:
            self._recovery_tracking[agent_id] = []
        self._recovery_tracking[agent_id].append(recovered)
        if len(self._recovery_tracking[agent_id]) > 50:
            self._recovery_tracking[agent_id] = self._recovery_tracking[agent_id][-50:]

    def get_recovery_rate(self) -> float:
        """计算整体恢复率"""
        all_results = []
        for results in self._recovery_tracking.values():
            all_results.extend(results)
        if not all_results:
            return 1.0
        return sum(1 for r in all_results if r) / len(all_results)

    def get_deviations(self, limit: int = 20) -> List[Dict]:
        return [d.to_dict() for d in self._deviations[-limit:]]

    def to_dict(self) -> Dict:
        return {
            "world_id": self.world_id,
            "total_deviations": len(self._deviations),
            "recovery_rate": round(self.get_recovery_rate(), 3),
            "recent_deviations": self.get_deviations(limit=10),
        }
