"""
D03 外部扰动投放
基于世界状态的智能扰动注入，频率可配置，模板库 20+ 种
"""
import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum


class DisturbanceCategory(Enum):
    """扰动类别"""
    DISASTER = "disaster"           # 天灾
    INVASION = "invasion"           # 外敌入侵
    FORTUITOUS = "fortuitous"       # 奇遇/机遇
    SECRET = "secret"               # 秘密揭露
    RUMOR = "rumor"                 # 谣言/流言
    ACCIDENT = "accident"           # 意外事件
    MYSTERY = "mystery"             # 神秘现象
    SOCIAL = "social"               # 社会变动


@dataclass
class DisturbanceTemplate:
    """扰动模板"""
    category: DisturbanceCategory
    name: str
    description: str                   # 描述模板，可用 {agent} {location} 占位符
    severity_range: Tuple[float, float]  # 严重度范围 (min, max)
    preferred_moods: List[str]         # 偏好的世界氛围 ["平静","紧张","混乱"]
    cooldown: int = 10                 # 冷却回合数
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "category": self.category.value,
            "name": self.name,
            "description": self.description,
            "severity_range": list(self.severity_range),
            "preferred_moods": self.preferred_moods,
            "cooldown": self.cooldown,
            "tags": self.tags,
        }


@dataclass
class DisturbanceEvent:
    """一次扰动事件"""
    template_name: str
    category: DisturbanceCategory
    description: str
    severity: float
    target_agents: List[str]
    target_locations: List[str]
    world_impact: str
    turn: int

    def to_dict(self) -> dict:
        return {
            "template_name": self.template_name,
            "category": self.category.value,
            "description": self.description,
            "severity": self.severity,
            "target_agents": self.target_agents,
            "target_locations": self.target_locations,
            "world_impact": self.world_impact,
            "turn": self.turn,
        }


class Frequency(Enum):
    """扰动注入频率"""
    NONE = "none"       # 关闭
    LOW = "low"         # 每 20-30 回合
    MEDIUM = "medium"   # 每 10-20 回合
    HIGH = "high"       # 每 5-10 回合


# ── 扰动模板库（20+ 模板，6 大类别）─────────────────────────
DISTURBANCE_LIBRARY: List[DisturbanceTemplate] = [
    # ── 天灾 ──
    DisturbanceTemplate(
        DisturbanceCategory.DISASTER, "地震地陷",
        "大地突然剧烈震动，{location}地面开裂，建筑倒塌，{agent}险些坠入裂缝",
        (0.5, 0.8), ["平静", "暗流涌动", "紧张"], tags=["灾难", "环境"],
    ),
    DisturbanceTemplate(
        DisturbanceCategory.DISASTER, "灵脉暴动",
        "{location}的灵脉突然暴动，灵气狂乱涌出，修为较低的{agent}被冲击震伤",
        (0.6, 0.9), ["平静", "暗流涌动"], tags=["灾难", "超自然"],
    ),
    DisturbanceTemplate(
        DisturbanceCategory.DISASTER, "瘟疫蔓延",
        "一种奇怪的瘟疫在{location}蔓延，{agent}发现身边的人开始出现诡异症状",
        (0.7, 0.9), ["紧张", "危机四伏"], tags=["灾难", "健康"],
    ),
    DisturbanceTemplate(
        DisturbanceCategory.DISASTER, "天降异象",
        "天空撕裂出诡异的光芒，{location}上空出现前所未有的天象异变",
        (0.4, 0.7), ["平静", "暗流涌动"], tags=["灾难", "神秘"],
    ),
    DisturbanceTemplate(
        DisturbanceCategory.DISASTER, "妖兽潮",
        "大批妖兽从{location}方向涌来，兽潮铺天盖地，{agent}被卷入其中",
        (0.7, 1.0), ["危机四伏", "混乱"], tags=["灾难", "战斗"],
    ),

    # ── 外敌入侵 ──
    DisturbanceTemplate(
        DisturbanceCategory.INVASION, "敌对势力突袭",
        "{location}遭到不明势力的突然袭击，{agent}匆忙应对来犯之敌",
        (0.6, 0.9), ["紧张", "危机四伏", "暗流涌动"], tags=["入侵", "战斗"],
    ),
    DisturbanceTemplate(
        DisturbanceCategory.INVASION, "卧底暴露",
        "{agent}发现身边最信任的{target}竟然是敌对势力安插的卧底",
        (0.5, 0.8), ["暗流涌动", "平静"], tags=["入侵", "背叛"],
    ),
    DisturbanceTemplate(
        DisturbanceCategory.INVASION, "领地侵犯",
        "一股外部势力悍然闯入{location}，声称拥有此地的主权，与{agent}当面对峙",
        (0.5, 0.7), ["平静", "紧张"], tags=["入侵", "冲突"],
    ),
    DisturbanceTemplate(
        DisturbanceCategory.INVASION, "蛊惑渗透",
        "神秘说客悄然潜入{location}，以利诱和威胁拉拢人心，{agent}察觉气氛不对",
        (0.4, 0.6), ["平静", "暗流涌动"], tags=["入侵", "阴谋"],
    ),

    # ── 奇遇/机遇 ──
    DisturbanceTemplate(
        DisturbanceCategory.FORTUITOUS, "神秘传承",
        "{agent}在{location}意外发现了一处上古传承，但入口处有强大禁制守护",
        (0.3, 0.6), ["平静", "暗流涌动"], tags=["机遇", "传承"],
    ),
    DisturbanceTemplate(
        DisturbanceCategory.FORTUITOUS, "天材地宝出世",
        "天地异象预示着绝世宝物即将在{location}出世，各方势力闻风而动",
        (0.4, 0.7), ["紧张", "暗流涌动", "混乱"], tags=["机遇", "争夺"],
    ),
    DisturbanceTemplate(
        DisturbanceCategory.FORTUITOUS, "贵人相助",
        "一位身份神秘的强者突然出现在{agent}面前，表示愿意提供帮助但条件未知",
        (0.2, 0.5), ["危机四伏", "动荡"], tags=["机遇", "盟友"],
    ),
    DisturbanceTemplate(
        DisturbanceCategory.FORTUITOUS, "情报交易",
        "{agent}意外获得了一份关于{location}重要情报，但情报的真伪和代价都未知",
        (0.2, 0.5), ["平静", "暗流涌动"], tags=["机遇", "情报"],
    ),

    # ── 秘密揭露 ──
    DisturbanceTemplate(
        DisturbanceCategory.SECRET, "身世之谜",
        "{agent}无意中发现了关于自己身世的惊人线索——自己并非如所认知的那般",
        (0.5, 0.8), ["平静", "暗流涌动"], tags=["秘密", "身份"],
    ),
    DisturbanceTemplate(
        DisturbanceCategory.SECRET, "陈年旧案",
        "一封尘封的信件揭露了多年前发生在{location}的旧案真相，牵扯诸多当事人",
        (0.4, 0.7), ["平静", "紧张"], tags=["秘密", "历史"],
    ),
    DisturbanceTemplate(
        DisturbanceCategory.SECRET, "双重身份",
        "{target}的真实身份曝光——他/她同时效忠于两个敌对的势力",
        (0.5, 0.8), ["暗流涌动", "紧张"], tags=["秘密", "背叛"],
    ),
    DisturbanceTemplate(
        DisturbanceCategory.SECRET, "隐藏血脉",
        "{agent}的血脉之力在{location}意外觉醒，揭示了被封印的古老血统",
        (0.4, 0.7), ["平静", "暗流涌动", "动荡"], tags=["秘密", "血脉"],
    ),

    # ── 谣言/流言 ──
    DisturbanceTemplate(
        DisturbanceCategory.RUMOR, "恶意谣言",
        "一则关于{agent}的恶意谣言在{location}迅速传播，声誉受损，人人侧目",
        (0.3, 0.6), ["平静", "暗流涌动"], tags=["谣言", "社交"],
    ),
    DisturbanceTemplate(
        DisturbanceCategory.RUMOR, "宝藏传说",
        "关于{location}藏有惊天宝藏的流言不胫而走，引来各路寻宝者和冒险者",
        (0.2, 0.5), ["平静", "紧张"], tags=["谣言", "宝藏"],
    ),
    DisturbanceTemplate(
        DisturbanceCategory.RUMOR, "叛徒传闻",
        "{location}流传着内部出了叛徒的传闻，人人自危，信任崩塌",
        (0.4, 0.7), ["紧张", "危机四伏"], tags=["谣言", "猜疑"],
    ),

    # ── 意外事件 ──
    DisturbanceTemplate(
        DisturbanceCategory.ACCIDENT, "关键物品失窃",
        "{agent}发现一件至关重要的物品在{location}失窃，线索指向内部人员",
        (0.4, 0.7), ["平静", "暗流涌动"], tags=["意外", "失窃"],
    ),
    DisturbanceTemplate(
        DisturbanceCategory.ACCIDENT, "重要人物失踪",
        "关键人物{target}突然在{location}失踪，{agent}必须决定是否展开搜索",
        (0.5, 0.8), ["紧张", "危机四伏"], tags=["意外", "失踪"],
    ),
    DisturbanceTemplate(
        DisturbanceCategory.ACCIDENT, "传讯中断",
        "{location}与外界的所有联系突然中断，传讯法阵失灵，孤立无援",
        (0.3, 0.6), ["暗流涌动", "紧张"], tags=["意外", "封锁"],
    ),

    # ── 神秘现象 ──
    DisturbanceTemplate(
        DisturbanceCategory.MYSTERY, "时间异常",
        "{location}的时间流速变得异常——里面过了数日，外面才过了一刻钟",
        (0.6, 0.9), ["平静", "神秘"], tags=["神秘", "时空"],
    ),
    DisturbanceTemplate(
        DisturbanceCategory.MYSTERY, "幻境蔓延",
        "{location}被一片诡异的迷雾笼罩，陷入迷雾的人会看到内心最恐惧的画面",
        (0.5, 0.8), ["暗流涌动", "危机四伏"], tags=["神秘", "幻境"],
    ),
    DisturbanceTemplate(
        DisturbanceCategory.MYSTERY, "预言应验",
        "古老的预言突然在{location}应验——铭文发光，星辰移位，{agent}被卷入命中注定的漩涡",
        (0.6, 0.9), ["动荡", "混乱"], tags=["神秘", "预言"],
    ),
    DisturbanceTemplate(
        DisturbanceCategory.MYSTERY, "镜中异界",
        "{location}的镜子中映出的不是现实场景——另一个世界的景象在镜中浮现",
        (0.5, 0.8), ["平静", "暗流涌动"], tags=["神秘", "异界"],
    ),
]

assert len(DISTURBANCE_LIBRARY) >= 20, f"扰动模板不足20个: {len(DISTURBANCE_LIBRARY)}"


class DisturbanceInjector:
    """
    外部扰动投放引擎

    职责：
    1. 管理扰动模板库 (26个模板，7大类)
    2. 基于世界状态智能选择扰动事件
    3. 频率可配置 (无/低/中/高)
    4. 与 D02 StagnationDetector 联动，自动在停滞时触发
    """

    def __init__(self, world_id: str):
        self.world_id = world_id
        self.frequency: Frequency = Frequency.MEDIUM
        self._last_disturbance_turn: Dict[str, int] = {}  # template_name -> turn
        self._history: List[DisturbanceEvent] = []
        self._injected_count: int = 0
        self._active_effects: List[Dict] = []  # 仍在生效的扰动

    # ── 频率配置 ────────────────────────────────────────────

    def set_frequency(self, freq: str):
        """设置注入频率: none/low/medium/high"""
        try:
            self.frequency = Frequency(freq)
        except ValueError:
            raise ValueError(f"无效频率: {freq}, 可选: none/low/medium/high")

    def get_frequency_interval(self) -> Optional[int]:
        """根据当前频率返回注入间隔（回合数）"""
        intervals = {
            Frequency.NONE: None,
            Frequency.LOW: random.randint(20, 30),
            Frequency.MEDIUM: random.randint(10, 20),
            Frequency.HIGH: random.randint(5, 10),
        }
        return intervals.get(self.frequency)

    # ── 模板选择 ────────────────────────────────────────────

    def select_templates(
        self,
        world_mood: str,
        count: int = 1,
        exclude: Optional[List[str]] = None,
        current_turn: int = 0,
    ) -> List[DisturbanceTemplate]:
        """
        基于世界状态智能选择扰动模板

        策略：
        1. 过滤掉冷却中的模板
        2. 按世界氛围匹配度评分
        3. 按类别多样性选择
        """
        exclude = exclude or []
        candidates = [
            t for t in DISTURBANCE_LIBRARY
            if t.name not in exclude
            and self._is_off_cooldown(t, current_turn)
        ]

        if not candidates:
            return []

        # 为候选模板评分
        scored = []
        for t in candidates:
            score = 0.0
            # 氛围匹配
            if world_mood in t.preferred_moods:
                score += 3.0
            # 靠近分数
            for mood in t.preferred_moods:
                if self._mood_similarity(world_mood, mood) > 0.5:
                    score += 1.0
            # 历史使用衰减（避免重复选同一类别）
            same_category_used = sum(
                1 for h in self._history[-5:]
                if h.category == t.category
            )
            score -= same_category_used * 0.5
            scored.append((t, score))

        # 加权随机选择
        scored.sort(key=lambda x: x[1], reverse=True)
        top_templates = [t for t, s in scored[:max(count * 3, 3)]]
        selected = random.sample(top_templates, min(count, len(top_templates)))
        return selected

    def _is_off_cooldown(self, template: DisturbanceTemplate, current_turn: int) -> bool:
        """检查模板是否在冷却中"""
        last_turn = self._last_disturbance_turn.get(template.name, -999)
        return (current_turn - last_turn) >= template.cooldown

    @staticmethod
    def _mood_similarity(mood_a: str, mood_b: str) -> float:
        """计算世界氛围相似度（简化版）"""
        mood_groups = [
            {"平静", "平稳"},
            {"暗流涌动", "紧张", "危机四伏"},
            {"混乱", "动荡"},
            {"希望萌芽", "重整旗鼓", "新秩序"},
        ]
        if mood_a == mood_b:
            return 1.0
        for group in mood_groups:
            if mood_a in group and mood_b in group:
                return 0.7
        return 0.0

    # ── 扰动生成 ────────────────────────────────────────────

    def inject(
        self,
        templates: List[DisturbanceTemplate],
        agents: Dict[str, any],
        locations: Dict[str, any],
        current_turn: int,
        force_severity: Optional[float] = None,
    ) -> List[DisturbanceEvent]:
        """
        注入扰动事件

        Args:
            templates:     选择的扰动模板列表
            agents:        agent_id -> agent_info
            locations:     loc_id -> loc_info
            current_turn:  当前回合
            force_severity: 强制严重度 (None=自动)

        Returns:
            注入的扰动事件列表
        """
        events = []
        agent_ids = list(agents.keys())
        loc_ids = list(locations.keys()) if locations else []

        for template in templates:
            if not agent_ids:
                continue

            # 选择参与者和地点
            target_agents = random.sample(
                agent_ids, min(random.randint(1, 3), len(agent_ids))
            )
            target_locations = []
            if loc_ids:
                target_locations = random.sample(
                    loc_ids, min(2, len(loc_ids))
                )

            # 填充描述
            agent_names = {
                aid: (agents[aid].get("name", aid)
                      if isinstance(agents.get(aid), dict)
                      else str(agents.get(aid, aid)))
                for aid in target_agents
            }
            loc_name = ""
            if target_locations:
                first_loc = target_locations[0]
                loc_name = (
                    locations[first_loc].get("name", first_loc)
                    if isinstance(locations.get(first_loc), dict)
                    else first_loc
                )

            description = template.description.format(
                agent=next(iter(agent_names.values()), "某人"),
                target=random.choice(list(agent_names.values())) if len(agent_names) > 1 else "某人",
                location=loc_name or "某处",
            )

            # 严重度
            if force_severity is not None:
                severity = force_severity
            else:
                severity = round(
                    random.uniform(*template.severity_range), 2
                )

            # 世界影响
            world_impact = self._generate_impact(template.category, severity)

            event = DisturbanceEvent(
                template_name=template.name,
                category=template.category,
                description=description,
                severity=severity,
                target_agents=target_agents,
                target_locations=target_locations,
                world_impact=world_impact,
                turn=current_turn,
            )

            self._last_disturbance_turn[template.name] = current_turn
            self._history.append(event)
            self._injected_count += 1
            self._active_effects.append({
                "template_name": template.name,
                "category": template.category.value,
                "severity": severity,
                "injected_at": current_turn,
                "duration": random.randint(3, 8),
            })
            events.append(event)

        # 清理过期效果
        self._active_effects = [
            e for e in self._active_effects
            if current_turn - e["injected_at"] < e["duration"]
        ]

        return events

    def _generate_impact(self, category: DisturbanceCategory, severity: float) -> str:
        """根据类别和严重度生成世界影响描述"""
        impacts = {
            DisturbanceCategory.DISASTER: "环境受到破坏，可能导致连锁灾害",
            DisturbanceCategory.INVASION: "势力格局发生变化，安全等级提升",
            DisturbanceCategory.FORTUITOUS: "力量平衡被打破，机遇与风险并存",
            DisturbanceCategory.SECRET: "信任基础动摇，人际关系面临重新洗牌",
            DisturbanceCategory.RUMOR: "社会氛围紧张，决策可能受舆论影响",
            DisturbanceCategory.ACCIDENT: "原有计划受阻，应急响应机制启动",
            DisturbanceCategory.MYSTERY: "未知因素介入，世界规则可能被改写",
        }
        base = impacts.get(category, "局势发生变化")
        if severity > 0.7:
            return f"[严重] {base}，影响范围可能持续扩大"
        elif severity > 0.4:
            return f"[中等] {base}，需要关注后续发展"
        return f"[轻微] {base}，暂时可控"

    # ── 自动触发（D02 联动） ────────────────────────────────

    def auto_inject(
        self,
        stagnation_score: float,
        agents: Dict[str, any],
        locations: Dict[str, any],
        world_mood: str,
        current_turn: int,
    ) -> Optional[List[DisturbanceEvent]]:
        """
        基于停滞分数自动注入扰动

        用于 D02 检测到停滞时联动调用：
        - 分数 0.3-0.5: 低概率注入1个低严重度
        - 分数 0.5-0.7: 中等概率注入1-2个
        - 分数 >0.7: 高概率注入2-3个高严重度
        """
        if self.frequency == Frequency.NONE:
            return None

        if stagnation_score < 0.3:
            return None

        # 决定注入数量
        if stagnation_score > 0.7:
            count = random.randint(2, 3)
            severity_bonus = 0.2
        elif stagnation_score > 0.5:
            count = random.randint(1, 2)
            severity_bonus = 0.1
        else:
            count = 1 if random.random() < 0.3 else 0
            severity_bonus = 0.0

        if count == 0:
            return None

        templates = self.select_templates(
            world_mood=world_mood,
            count=count,
            current_turn=current_turn,
        )

        if not templates:
            return None

        return self.inject(templates, agents, locations, current_turn,
                          force_severity=None)

    # ── 快照/统计 ────────────────────────────────────────────

    def get_history(self, limit: int = 20) -> List[Dict]:
        """获取注入历史"""
        return [e.to_dict() for e in self._history[-limit:]]

    def get_stats(self) -> Dict:
        """获取统计"""
        category_counts = {}
        for e in self._history:
            cat = e.category.value
            category_counts[cat] = category_counts.get(cat, 0) + 1

        return {
            "total_injections": self._injected_count,
            "frequency": self.frequency.value,
            "active_effects": len(self._active_effects),
            "by_category": category_counts,
            "avg_severity": (
                round(sum(e.severity for e in self._history) / len(self._history), 2)
                if self._history else 0.0
            ),
        }

    def to_dict(self) -> Dict:
        """完整快照"""
        return {
            "world_id": self.world_id,
            "stats": self.get_stats(),
            "active_effects": self._active_effects,
            "recent_injections": self.get_history(limit=5),
        }
