"""
E01-E03 故事淘洗引擎
从海量事件日志中发现高价值叙事线并转化为可读文本

核心功能：
- E01: 演化日志简化处理（hash分组代替MinHash）
- E02: 叙事切片发现（三维度评分：意外性/逻辑性/情感冲击力）
- E03: LLM文本化重写（复用NarrativeExtractor）
"""

import asyncio
import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple, Set, TYPE_CHECKING
from datetime import datetime
from enum import Enum

if TYPE_CHECKING:
    from ..sandbox.action_executor import BaseLLMClient
    from .narrative_extractor import NarrativeExtractor


# ═══════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════

class SliceQuality(Enum):
    """切片质量等级"""
    EXCELLENT = "excellent"   # 必选
    GOOD = "good"             # 推荐
    FAIR = "fair"            # 可选
    SKIP = "skip"            # 跳过


@dataclass
class SliceScores:
    """切片三维度评分"""
    surprise: float = 0.0   # 意外性：事件发展是否符合预期（0-1）
    logic: float = 0.0       # 逻辑性：因果链是否连贯（0-1）
    emotion: float = 0.0     # 情感冲击力（0-1）
    overall: float = 0.0     # 综合评分

    def to_dict(self) -> dict:
        return {
            "surprise": round(self.surprise, 2),
            "logic": round(self.logic, 2),
            "emotion": round(self.emotion, 2),
            "overall": round(self.overall, 2),
        }


@dataclass
class NarrativeSlice:
    """叙事切片"""
    slice_id: str
    start_turn: int
    end_turn: int
    event_count: int
    core_actors: List[str]          # 核心角色
    core_action: str                 # 核心动作/事件
    setup: str                        # 铺垫描述
    development: str                   # 发展描述
    climax: str                       # 高潮描述
    quality: SliceQuality
    scores: SliceScores
    tags: List[str] = field(default_factory=list)  # 标签：conflict/tension/revelation等

    def to_dict(self) -> dict:
        return {
            "slice_id": self.slice_id,
            "start_turn": self.start_turn,
            "end_turn": self.end_turn,
            "event_count": self.event_count,
            "core_actors": self.core_actors,
            "core_action": self.core_action[:50] + "..." if len(self.core_action) > 50 else self.core_action,
            "quality": self.quality.value,
            "scores": self.scores.to_dict(),
            "tags": self.tags,
            "preview": f"{self.setup[:30]}...{self.climax[-30:]}" if self.setup and self.climax else "",
        }


@dataclass
class StorySiftResult:
    """完整淘洗结果"""
    total_events: int
    candidate_slices: int
    excellent_slices: List[NarrativeSlice]
    good_slices: List[NarrativeSlice]
    fair_slices: List[NarrativeSlice]
    sift_time_ms: float
    generated_at: str = ""


# ═══════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════

DEFAULT_CONFIG = {
    "min_slice_events": 3,         # 最小事件数
    "max_slice_events": 15,        # 最大事件数
    "overlap_threshold": 0.6,       # 事件重叠阈值（超过则合并）
    "min_quality_score": 0.3,      # 最低质量阈值
    "excellent_threshold": 0.75,   # EXCELLENT阈值
    "good_threshold": 0.55,        # GOOD阈值
    "fair_threshold": 0.30,        # FAIR阈值
    "max_return_slices": 10,       # 最多返回切片数
}


# ═══════════════════════════════════════════════════════════
# E01: 简化向量化（hash分组）
# ═══════════════════════════════════════════════════════════

def simple_event_hash(event) -> str:
    """生成事件的简化hash（用于去重/分组）"""
    parts = [
        str(getattr(event, 'actor_name', '')),
        str(getattr(event, 'action', ''))[:20],
        str(getattr(event, 'action_type', '')),
    ]
    content = "|".join(parts)
    return hashlib.md5(content.encode()).hexdigest()[:8]


def group_similar_events(events: List[Any]) -> Dict[str, List[Any]]:
    """将相似事件分组（简化版MinHash）"""
    groups: Dict[str, List[Any]] = {}

    for event in events:
        h = simple_event_hash(event)
        if h not in groups:
            groups[h] = []
        groups[h].append(event)

    return groups


# ═══════════════════════════════════════════════════════════
# E02: 叙事切片发现引擎
# ═══════════════════════════════════════════════════════════

class StorySifter:
    """
    故事淘洗引擎

    E02核心：从事件序列中发现高价值叙事切片
    E01简化：用hash分组代替MinHash向量
    E03复用：NarrativeExtractor生成文本
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}

        # 情感关键词
        self._emotion_words = {
            "positive": ["喜悦", "欣慰", "感激", "兴奋", "感动", "温暖", "希望", "爱"],
            "negative": ["愤怒", "悲伤", "恐惧", "绝望", "痛苦", "仇恨", "嫉妒", "怨恨"],
            "tension": ["紧张", "犹豫", "对峙", "危机", "阴谋", "秘密", "发现", "揭穿"],
        }

        # 意外性关键词（通常不应发生的事）
        self._surprise_words = ["意外", "突然", "竟然", "居然", "万万没想到",
                                "却", "然而", "不料", "谁知", "没想到"]

        # 关系变化关键词
        self._relation_change_words = ["背叛", "和好", "误会", "揭穿", "发现", "求助", "决裂"]

    async def sift(
        self,
        events: List[Any],
        min_quality: float = 0.3,
        max_slices: int = 10,
    ) -> StorySiftResult:
        """
        从事件序列中筛选叙事切片

        Args:
            events: 事件列表（按turn排序）
            min_quality: 最低质量阈值
            max_slices: 最多返回切片数

        Returns:
            StorySiftResult: 分类好的切片列表
        """
        start_time = asyncio.get_event_loop().time()

        if not events:
            return StorySiftResult(
                total_events=0,
                candidate_slices=0,
                excellent_slices=[],
                good_slices=[],
                fair_slices=[],
                sift_time_ms=0,
            )

        # Step 1: 去重分组（E01简化）
        groups = group_similar_events(events)

        # Step 2: 发现叙事候选
        candidates = self._discover_candidates(events, groups)

        # Step 3: 评分排序
        scored_slices = []
        for candidate in candidates:
            scores = self._score_slice(candidate, events)
            candidate.scores = scores
            candidate.quality = self._classify_quality(scores.overall)

            if scores.overall >= min_quality:
                scored_slices.append(candidate)

        # Step 4: 合并重叠切片
        scored_slices = self._merge_overlapping(scored_slices)

        # Step 5: 排序并分配等级
        scored_slices.sort(key=lambda s: s.scores.overall, reverse=True)

        excellent = [s for s in scored_slices if s.quality == SliceQuality.EXCELLENT]
        good = [s for s in scored_slices if s.quality == SliceQuality.GOOD]
        fair = [s for s in scored_slices if s.quality == SliceQuality.FAIR]

        # 截断max_slices
        result = StorySiftResult(
            total_events=len(events),
            candidate_slices=len(candidates),
            excellent_slices=excellent[:max_slices],
            good_slices=good[:max_slices],
            fair_slices=fair[:max_slices],
            sift_time_ms=round((asyncio.get_event_loop().time() - start_time) * 1000, 1),
            generated_at=datetime.now().isoformat(),
        )

        return result

    def _discover_candidates(
        self,
        events: List[Any],
        groups: Dict[str, List[Any]],
    ) -> List[NarrativeSlice]:
        """发现叙事切片候选"""
        candidates: List[NarrativeSlice] = []

        # 按滑动窗口发现切片
        min_events = self.config["min_slice_events"]
        max_events = self.config["max_slice_events"]

        for window_size in range(min_events, min(max_events + 1, len(events) + 1)):
            for start_idx in range(len(events) - window_size + 1):
                window = events[start_idx:start_idx + window_size]

                # 检查是否值得作为切片
                if self._is_narrative_worthy(window):
                    slice_obj = self._create_slice(window, start_idx)
                    if slice_obj:
                        candidates.append(slice_obj)

        return candidates

    def _is_narrative_worthy(self, window: List[Any]) -> bool:
        """判断窗口是否值得作为叙事切片"""
        if len(window) < self.config["min_slice_events"]:
            return False

        # 检查是否有互动
        has_interaction = any(
            getattr(e, 'action_type', '') == 'interaction'
            for e in window
        )

        # 检查是否有高分事件
        has_high_score = any(
            (getattr(e, 'score', 0) or 0) >= 3.0
            for e in window
        )

        # 检查是否有冲突标签
        has_conflict = any(
            any(tag in getattr(e, 'action', '') for tag in ["冲突", "争执", "对峙", "战斗"])
            for e in window
        )

        return has_interaction or has_high_score or has_conflict

    def _create_slice(self, window: List[Any], start_idx: int) -> Optional[NarrativeSlice]:
        """从事件窗口创建切片"""
        if not window:
            return None

        # 提取核心角色
        actors: Set[str] = set()
        for e in window:
            if hasattr(e, 'actor_name') and e.actor_name:
                actors.add(e.actor_name)
            if hasattr(e, 'target_name') and e.target_name:
                actors.add(e.target_name)

        # 提取核心动作（取最高分事件的action）
        scored_events = sorted(
            window,
            key=lambda e: (getattr(e, 'score', 0) or 0),
            reverse=True
        )
        core_action = getattr(scored_events[0], 'action', '未知事件') if scored_events else '未知事件'

        # 生成切片ID
        slice_id = f"slice_{getattr(window[0], 'turn', start_idx)}_{getattr(window[-1], 'turn', start_idx)}"

        # 生成各阶段描述
        setup = self._summarize_phase(window[:len(window)//3], "起")
        development = self._summarize_phase(window[len(window)//3: 2*len(window)//3], "承")
        climax = self._summarize_phase(window[2*len(window)//3:], "转" if len(window) > 3 else "合")

        # 提取标签
        tags = self._extract_tags(window)

        return NarrativeSlice(
            slice_id=slice_id,
            start_turn=getattr(window[0], 'turn', 1),
            end_turn=getattr(window[-1], 'turn', 1),
            event_count=len(window),
            core_actors=list(actors)[:5],
            core_action=core_action,
            setup=setup,
            development=development,
            climax=climax,
            quality=SliceQuality.SKIP,  # 待评分
            scores=SliceScores(),       # 待评分
            tags=tags,
        )

    def _summarize_phase(self, events: List[Any], phase: str) -> str:
        """生成阶段性描述"""
        if not events:
            return ""

        lines = []
        phase_labels = {
            "起": "起初，",
            "承": "随后，",
            "转": "然而，",
            "合": "最终，"
        }
        label = phase_labels.get(phase, "")

        for e in events[:3]:
            actor = getattr(e, 'actor_name', '?')
            action = getattr(e, 'action', '?')[:30]
            target = getattr(e, 'target_name', '')
            loc = getattr(e, 'location', '')

            part = f"{actor}"
            if target:
                part += f"与{target}"
            part += f"：{action}"
            if loc:
                part += f"于{loc}"
            lines.append(part)

        return label + "，".join(lines) + "。"

    def _extract_tags(self, events: List[Any]) -> List[str]:
        """从事件中提取标签"""
        tags: List[str] = []
        all_text = " ".join(getattr(e, 'action', '') for e in events)

        # 检测标签类型
        if any(w in all_text for w in ["冲突", "争执", "战斗", "对峙"]):
            tags.append("conflict")
        if any(w in all_text for w in ["发现", "揭穿", "秘密", "真相"]):
            tags.append("revelation")
        if any(w in all_text for w in ["和好", "和解", "结盟", "信任"]):
            tags.append("reconciliation")
        if any(w in all_text for w in ["背叛", "出卖", "欺骗"]):
            tags.append("betrayal")
        if any(w in all_text for w in ["计划", "阴谋", "策略"]):
            tags.append("conspiracy")
        if any(getattr(e, 'action_type', '') == 'story_moment' for e in events):
            tags.append("story_moment")

        return tags[:5]  # 最多5个标签

    def _score_slice(
        self,
        slice_obj: NarrativeSlice,
        all_events: List[Any],
    ) -> SliceScores:
        """计算切片的三维度评分"""
        # 获取切片内的事件
        slice_events = [
            e for e in all_events
            if getattr(e, 'turn', 0) >= slice_obj.start_turn
            and getattr(e, 'turn', 0) <= slice_obj.end_turn
        ]

        scores = SliceScores()

        # 1. 意外性评分（surprise）
        scores.surprise = self._calc_surprise(slice_events)

        # 2. 逻辑性评分（logic）
        scores.logic = self._calc_logic(slice_events, all_events)

        # 3. 情感冲击力评分（emotion）
        scores.emotion = self._calc_emotion(slice_events)

        # 综合评分（加权平均）
        scores.overall = (
            scores.surprise * 0.3 +
            scores.logic * 0.4 +
            scores.emotion * 0.3
        )

        return scores

    def _calc_surprise(self, events: List[Any]) -> float:
        """计算意外性"""
        all_text = " ".join(getattr(e, 'action', '') for e in events)

        # 计算意外关键词出现率
        surprise_count = sum(1 for w in self._surprise_words if w in all_text)

        # 计算意外分数事件的占比
        high_score = sum(1 for e in events if (getattr(e, 'score', 0) or 0) >= 3.5)
        surprise_ratio = high_score / len(events) if events else 0

        return min(1.0, (surprise_count * 0.1 + surprise_ratio * 0.5))

    def _calc_logic(self, events: List[Any], all_events: List[Any]) -> float:
        """计算逻辑性（因果链连贯度）"""
        if len(events) < 2:
            return 0.3

        # 检查角色连续性（同一角色是否在相邻事件中出现）
        actor_continuity = 0.0
        for i in range(len(events) - 1):
            current_actors = {getattr(events[i], 'actor_name', ''), getattr(events[i], 'target_name', '')}
            next_actors = {getattr(events[i+1], 'actor_name', ''), getattr(events[i+1], 'target_name', '')}
            if current_actors & next_actors:  # 有交集
                actor_continuity += 1

        continuity_score = actor_continuity / (len(events) - 1) if len(events) > 1 else 0

        # 检查时间连续性（相邻事件turn差距不应太大）
        time_gaps = []
        for i in range(len(events) - 1):
            gap = getattr(events[i+1], 'turn', 0) - getattr(events[i], 'turn', 0)
            time_gaps.append(gap)

        avg_gap = sum(time_gaps) / len(time_gaps) if time_gaps else 0
        time_score = 1.0 if avg_gap <= 5 else max(0.3, 1.0 - (avg_gap - 5) * 0.1)

        return (continuity_score * 0.6 + time_score * 0.4)

    def _calc_emotion(self, events: List[Any]) -> float:
        """计算情感冲击力"""
        all_text = " ".join(getattr(e, 'action', '') for e in events)

        # 情感词密度
        emotion_count = 0
        for category, words in self._emotion_words.items():
            for word in words:
                if word in all_text:
                    emotion_count += 1

        # 情感词密度
        density = emotion_count / len(all_text) if all_text else 0

        # 最高分事件的分数
        max_score = max((getattr(e, 'score', 0) or 0) for e in events)

        return min(1.0, density * 2 + max_score * 0.1)

    def _classify_quality(self, overall: float) -> SliceQuality:
        """根据综合评分分类"""
        if overall >= self.config["excellent_threshold"]:
            return SliceQuality.EXCELLENT
        elif overall >= self.config["good_threshold"]:
            return SliceQuality.GOOD
        elif overall >= self.config["fair_threshold"]:
            return SliceQuality.FAIR
        else:
            return SliceQuality.SKIP

    def _merge_overlapping(self, slices: List[NarrativeSlice]) -> List[NarrativeSlice]:
        """合并重叠的切片"""
        if not slices:
            return []

        # 按结束turn排序
        sorted_slices = sorted(slices, key=lambda s: s.end_turn)

        merged: List[NarrativeSlice] = []
        overlap_thresh = self.config["overlap_threshold"]

        for slice_obj in sorted_slices:
            # 检查与已合并切片的重叠
            should_merge = False
            for existing in merged:
                overlap = self._calc_overlap(slice_obj, existing)
                if overlap >= overlap_thresh:
                    should_merge = True
                    # 合并到existing
                    existing.end_turn = max(existing.end_turn, slice_obj.end_turn)
                    existing.event_count = existing.end_turn - existing.start_turn + 1
                    # 保留更高的评分
                    if slice_obj.scores.overall > existing.scores.overall:
                        existing.scores = slice_obj.scores
                    break

            if not should_merge:
                merged.append(slice_obj)

        return merged

    def _calc_overlap(self, a: NarrativeSlice, b: NarrativeSlice) -> float:
        """计算两个切片的重叠度"""
        # 计算重叠事件数
        a_turns = set(range(a.start_turn, a.end_turn + 1))
        b_turns = set(range(b.start_turn, b.end_turn + 1))

        intersection = len(a_turns & b_turns)
        union = len(a_turns | b_turns)

        return intersection / union if union > 0 else 0

    # ═══════════════════════════════════════════════════════════
    # E03: 文本化重写（复用NarrativeExtractor）
    # ═══════════════════════════════════════════════════════════

    async def rewrite_slice(
        self,
        slice_obj: NarrativeSlice,
        all_events: List[Any],
        llm_client: Optional["BaseLLMClient"] = None,
    ) -> str:
        """
        将切片重写为可读的叙事文本

        Args:
            slice_obj: 叙事切片
            all_events: 所有事件（用于获取切片内事件）
            llm_client: LLM客户端

        Returns:
            str: 重写后的叙事文本
        """
        if not llm_client:
            # 无LLM时使用简化重写
            return self._simple_rewrite(slice_obj)

        # 获取切片内事件
        slice_events = [
            e for e in all_events
            if getattr(e, 'turn', 0) >= slice_obj.start_turn
            and getattr(e, 'turn', 0) <= slice_obj.end_turn
        ]

        # 复用NarrativeExtractor
        try:
            from .narrative_extractor import NarrativeExtractor
            extractor = NarrativeExtractor()
            chapter = await extractor.extract(slice_events, llm_client=llm_client)

            # 合并所有段落
            full_text = f"## {slice_obj.core_action[:30]}\n\n"
            for section in chapter.sections:
                phase_name = {"setup": "【起】", "development": "【承】",
                              "climax": "【转】", "resolution": "【合】"}.get(section.phase, "")
                full_text += f"{phase_name}{section.content}\n\n"

            return full_text
        except Exception as e:
            print(f"[StorySifter] Rewrite failed: {e}")
            return self._simple_rewrite(slice_obj)

    def _simple_rewrite(self, slice_obj: NarrativeSlice) -> str:
        """简化重写（无LLM时）"""
        lines = [
            f"## {slice_obj.core_action[:40]}",
            "",
            f"【起】{slice_obj.setup}",
            "",
            f"【承】{slice_obj.development}",
            "",
            f"【转】{slice_obj.climax}",
            "",
            f"—— 第{slice_obj.start_turn}至{slice_obj.end_turn}回合，"
            f"{len(slice_obj.core_actors)}位角色参与",
        ]
        return "\n".join(lines)

    # ═══════════════════════════════════════════════════════════
    # API响应格式化
    # ═══════════════════════════════════════════════════════════

    def to_api_response(self, result: StorySiftResult) -> Dict[str, Any]:
        """转换为API响应格式"""
        return {
            "total_events": result.total_events,
            "candidate_slices": result.candidate_slices,
            "sift_time_ms": result.sift_time_ms,
            "slices": {
                "excellent": [s.to_dict() for s in result.excellent_slices],
                "good": [s.to_dict() for s in result.good_slices],
                "fair": [s.to_dict() for s in result.fair_slices],
            },
            "generated_at": result.generated_at,
        }