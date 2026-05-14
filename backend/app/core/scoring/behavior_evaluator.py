"""
S2-7 行为一致性评测器
评估 NPC 行动是否与其角色设定(identity/personality/goals)一致
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EvalDimension:
    """单维度评分"""
    name: str
    score: float       # 0.0-1.0
    reasoning: str = ""


@dataclass
class BehaviorReport:
    """单次行为评测报告"""
    agent_id: str
    agent_name: str
    turn: int
    action: str
    target: Optional[str]
    dimensions: list[EvalDimension] = field(default_factory=list)
    overall_score: float = 0.0
    verdict: str = ""  # "consistent" | "neutral" | "divergent"


class BehaviorEvaluator:
    """
    行为一致性评测器

    从四个维度评测 NPC 行动是否符合角色设定：
    1. 身份一致性 — 行动是否符合角色背景/身份
    2. 性格对齐度 — 行动风格是否符合性格描述
    3. 目标关联度 — 行动是否推进当前目标
    4. 关系一致性 — 对目标的互动是否符合知识图谱关系
    """

    # 人格特征关键词映射
    PERSONALITY_CLUES = {
        "冷静": ["观察", "分析", "等待", "计算", "谋划", "隐忍", "克制", "评估"],
        "冲动": ["冲", "怒", "立即", "直接", "打断", "咆哮", "动手", "喝斥"],
        "善良": ["帮助", "救治", "安慰", "保护", "施舍", "开导", "关怀"],
        "狡诈": ["欺骗", "隐瞒", "设局", "暗算", "利诱", "密谋", "挑拨"],
        "豪迈": ["大笑", "畅饮", "高歌", "直言", "挥洒", "豪情"],
        "孤傲": ["独自", "冷冷", "漠然", "孤身", "不语", "疏离"],
        "温柔": ["轻抚", "柔声", "含笑", "细语", "关切", "挽手"],
        "偏执": ["执念", "反复", "纠缠", "誓要", "绝不", "宁死"],
        "忠诚": ["守护", "效忠", "追随", "护主", "赴死", "誓守"],
        "贪婪": ["索取", "独占", "敛财", "趁火", "勒索", "觊觎"],
    }

    # 身份关键词
    IDENTITY_CLUES = {
        "修士": ["修炼", "灵力", "功法", "丹药", "吐纳", "境界", "法术"],
        "剑客": ["剑", "剑法", "剑意", "斩", "锋芒", "决斗"],
        "医师": ["治疗", "药草", "诊脉", "药剂", "伤患", "解毒"],
        "杀手": ["暗杀", "潜伏", "一击", "无声", "猎杀", "毒"],
        "商人": ["交易", "利益", "货物", "钱财", "议价", "买卖"],
        "武者": ["拳", "功法", "劲力", "切磋", "内力", "招式"],
        "掌门": ["宗门", "弟子", "规矩", "师门", "传承", "号令"],
        "散修": ["独自", "漂泊", "隐世", "自由", "流浪", "独行"],
        "少主": ["家族", "威严", "继承", "血统", "责任", "势力"],
        "长老": ["元老", "资历", "仲裁", "守护", "祖训", "大计"],
        "侦探": ["调查", "线索", "推理", "真相", "证据", "谜题"],
        "法师": ["咒语", "魔法", "元素", "结界", "传送", "召唤"],
        "医师(现代)": ["诊断", "手术", "急救", "病房", "药品", "患者"],
    }

    def evaluate(
        self,
        agent_id: str,
        agent_name: str,
        identity: str,
        personality: str,
        goals: list[str],
        action: str,
        target: Optional[str],
        relation_type: Optional[str],
        turn: int,
    ) -> BehaviorReport:
        """评测单次行为"""

        dimensions = [
            self._eval_identity(identity, action),
            self._eval_personality(personality, action),
            self._eval_goal_coherence(goals, action),
            self._eval_relation(relation_type, action, target),
        ]

        overall = sum(d.score for d in dimensions) / len(dimensions)

        if overall >= 0.6:
            verdict = "consistent"
        elif overall >= 0.35:
            verdict = "neutral"
        else:
            verdict = "divergent"

        return BehaviorReport(
            agent_id=agent_id,
            agent_name=agent_name,
            turn=turn,
            action=action,
            target=target,
            dimensions=dimensions,
            overall_score=round(overall, 3),
            verdict=verdict,
        )

    def _eval_identity(self, identity: str, action: str) -> EvalDimension:
        """评估身份一致性"""
        matched = 0
        total = 0
        for id_key, clues in self.IDENTITY_CLUES.items():
            if id_key in identity:
                total = len(clues)
                matched = sum(1 for c in clues if c in action)
                break
        if total == 0:
            return EvalDimension("身份一致性", 0.5, "未识别到明确身份关键词，给予中性分")
        score = min(1.0, matched / max(total * 0.3, 1))
        return EvalDimension("身份一致性", round(score, 2),
            f"匹配 {matched}/{total} 个身份关键词" if matched > 0 else "行动未体现身份特征")

    def _eval_personality(self, personality: str, action: str) -> EvalDimension:
        """评估性格对齐"""
        best_score = 0.0
        best_trait = ""
        matched = 0
        total = 0
        for trait, clues in self.PERSONALITY_CLUES.items():
            if trait in personality:
                hits = sum(1 for c in clues if c in action)
                if hits > matched:
                    matched = hits
                    total = len(clues)
                    best_trait = trait
                    if total > 0:
                        best_score = min(1.0, hits / max(total * 0.3, 1))
        if not best_trait:
            return EvalDimension("性格对齐度", 0.5, "未匹配到性格特征，给予中性分")
        return EvalDimension("性格对齐度", round(best_score, 2),
            f"与「{best_trait}」特质匹配 {matched}/{total} 个关键词")

    def _eval_goal_coherence(self, goals: list[str], action: str) -> EvalDimension:
        """评估目标关联度"""
        if not goals:
            return EvalDimension("目标关联度", 0.5, "未设定目标")
        best = 0.0
        best_goal = ""
        for goal in goals:
            keywords = [w for w in goal if len(w) >= 2]
            if not keywords:
                continue
            hits = sum(1 for kw in keywords if kw in action)
            score = min(1.0, hits / max(len(keywords) * 0.4, 1))
            if score > best:
                best = score
                best_goal = goal
        return EvalDimension("目标关联度", round(best, 2),
            f"与目标「{best_goal[:20]}」相关度" if best_goal else "无明显目标关联")

    def _eval_relation(
        self, relation_type: Optional[str], action: str, target: Optional[str]
    ) -> EvalDimension:
        """评估关系一致性"""
        if not target or not relation_type:
            return EvalDimension("关系一致性", 0.5, "无交互目标")

        hostile_words = ["攻击", "杀", "威胁", "咒骂", "愤怒", "敌意", "偷袭", "暗算"]
        friendly_words = ["帮助", "分享", "微笑", "信任", "合作", "支持", "安慰", "赠"]

        hostile_count = sum(1 for w in hostile_words if w in action)
        friendly_count = sum(1 for w in friendly_words if w in action)

        if relation_type == "enemy":
            score = 0.5 + min(0.5, hostile_count * 0.15) - min(0.3, friendly_count * 0.15)
            return EvalDimension("关系一致性", round(max(0, min(1, score)), 2),
                "敌对关系" + ("，行为符合" if hostile_count > friendly_count else "，行为略显温和"))
        elif relation_type == "friend":
            score = 0.5 + min(0.5, friendly_count * 0.15) - min(0.3, hostile_count * 0.15)
            return EvalDimension("关系一致性", round(max(0, min(1, score)), 2),
                "友好关系" + ("，行为符合" if friendly_count > hostile_count else "，行为略显敌意"))
        else:
            score = 0.5 + min(0.3, (friendly_count + hostile_count) * 0.1)
            return EvalDimension("关系一致性", round(max(0, min(1, score)), 2), "中性关系")


# 累积评测追踪
class EvalTracker:
    """追踪所有Agent的累积评测结果"""

    def __init__(self):
        self._reports: list[BehaviorReport] = []
        self._agent_scores: dict[str, list[float]] = {}

    def record(self, report: BehaviorReport):
        self._reports.append(report)
        if report.agent_id not in self._agent_scores:
            self._agent_scores[report.agent_id] = []
        self._agent_scores[report.agent_id].append(report.overall_score)

    def get_agent_avg(self, agent_id: str) -> float:
        scores = self._agent_scores.get(agent_id, [])
        if not scores:
            return 0.0
        return round(sum(scores) / len(scores), 3)

    def get_summary(self) -> dict:
        if not self._agent_scores:
            return {"total_evaluations": 0, "avg_score": 0.0, "agents": []}
        all_scores = [s for scores in self._agent_scores.values() for s in scores]
        return {
            "total_evaluations": len(self._reports),
            "avg_score": round(sum(all_scores) / len(all_scores), 3) if all_scores else 0.0,
            "consistent_pct": round(
                sum(1 for r in self._reports if r.verdict == "consistent") / max(len(self._reports), 1) * 100, 1
            ),
            "divergent_pct": round(
                sum(1 for r in self._reports if r.verdict == "divergent") / max(len(self._reports), 1) * 100, 1
            ),
            "agents": [
                {
                    "agent_id": aid,
                    "avg_score": self.get_agent_avg(aid),
                    "eval_count": len(scores),
                    "recent_trend": "up" if len(scores) >= 2 and scores[-1] > scores[-2] else "down" if len(scores) >= 2 else "stable",
                }
                for aid, scores in self._agent_scores.items()
            ],
        }
