"""
G02 Passive Taste 学习 — 用户采纳/拒绝行为编码为审美偏好向量

冷启动阶段：使用预设风格包（style_presets.yaml）
数据积累后：≥10次采纳启动私人编码器
"""
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
from collections import defaultdict


# 风格向量维度（与 style_presets.yaml 对齐）
VECTOR_DIMENSIONS = [
    "pace", "density", "tension", "emotion_depth",
    "description_richness", "dialogue_ratio", "inner_monologue",
    "humor", "darkness", "poetry", "action_ratio", "world_detail",
]


@dataclass
class TasteProfile:
    """用户审美偏好画像"""
    user_id: str
    vector: Dict[str, float]     # 12维偏好向量
    sample_count: int = 0        # 采纳+拒绝总次数
    accepted_count: int = 0
    rejected_count: int = 0
    last_updated: str = ""
    drift_score: float = 0.0     # 品味漂移检测（>0.3 表示显著变化）
    history: List[Dict] = field(default_factory=list)  # 最近20条

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "vector": {k: round(v, 3) for k, v in self.vector.items()},
            "sample_count": self.sample_count,
            "accepted_count": self.accepted_count,
            "rejected_count": self.rejected_count,
            "last_updated": self.last_updated,
            "drift_score": round(self.drift_score, 3),
        }

    @property
    def is_cold_start(self) -> bool:
        """冷启动：样本<10次"""
        return self.sample_count < 10

    def dominant_style(self) -> str:
        """推断最近似风格"""
        from .style_generator import STYLE_PRESETS
        best, best_score = "shuangwen", -1.0
        for name, preset in STYLE_PRESETS.items():
            sim = self._cosine_sim(self.vector, preset["vector"])
            if sim > best_score:
                best_score = sim
                best = name
        return best

    @staticmethod
    def _cosine_sim(a: Dict[str, float], b: Dict[str, float]) -> float:
        dot = sum(a.get(k, 0) * b.get(k, 0) for k in VECTOR_DIMENSIONS)
        na = math.sqrt(sum(v**2 for v in a.values()))
        nb = math.sqrt(sum(v**2 for v in b.values()))
        return dot / max(na * nb, 0.001)


class TasteEncoder:
    """
    被动品味编码器

    从用户对生成章节的采纳/拒绝行为中学习审美偏好。
    冷启动阶段返回预设风格包向量；≥10样本后启动私人模型。

    学习率动态调整：早期样本权重大（快速收敛），后期平稳微调。
    """

    COLD_START_THRESHOLD = 10
    INITIAL_LEARNING_RATE = 0.15  # 早期快速学习
    STABLE_LEARNING_RATE = 0.03   # 后期微调
    DRIFT_WINDOW = 10             # 品味漂移检测窗口

    def __init__(self):
        self._profiles: Dict[str, TasteProfile] = {}

    def get_or_create_profile(self, user_id: str) -> TasteProfile:
        """获取或创建用户品味画像"""
        if user_id in self._profiles:
            return self._profiles[user_id]

        # 冷启动：默认均衡向量
        profile = TasteProfile(
            user_id=user_id,
            vector={dim: 0.5 for dim in VECTOR_DIMENSIONS},
            last_updated=datetime.now(timezone.utc).isoformat(),
        )
        self._profiles[user_id] = profile
        return profile

    def record_feedback(
        self,
        user_id: str,
        chapter_style_vector: Dict[str, float],
        accepted: bool,
        chapter_id: str = "",
    ) -> TasteProfile:
        """
        记录用户对章节的采纳/拒绝反馈

        Args:
            user_id: 用户ID
            chapter_style_vector: 本章的风格向量
            accepted: 是否采纳
            chapter_id: 章节ID（可选，用于去重）

        Returns:
            更新后的品味画像
        """
        profile = self.get_or_create_profile(user_id)

        # 去重检查
        if any(h.get("chapter_id") == chapter_id for h in profile.history[-5:]):
            return profile

        # 学习率
        lr = (
            self.INITIAL_LEARNING_RATE
            if profile.sample_count < self.COLD_START_THRESHOLD
            else self.STABLE_LEARNING_RATE
        )

        # 更新向量：采纳→靠近，拒绝→远离
        sign = 1.0 if accepted else -1.0
        for dim in VECTOR_DIMENSIONS:
            delta = (chapter_style_vector.get(dim, 0.5) - profile.vector[dim]) * lr * sign
            profile.vector[dim] = max(0.0, min(1.0, profile.vector[dim] + delta))

        # 统计
        profile.sample_count += 1
        if accepted:
            profile.accepted_count += 1
        else:
            profile.rejected_count += 1

        # 历史记录
        profile.history.append({
            "chapter_id": chapter_id,
            "accepted": accepted,
            "vector_snapshot": {k: round(v, 3) for k, v in chapter_style_vector.items()},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        if len(profile.history) > 20:
            profile.history = profile.history[-20:]

        # 品味漂移检测
        if len(profile.history) >= self.DRIFT_WINDOW:
            profile.drift_score = self._detect_drift(profile)

        profile.last_updated = datetime.now(timezone.utc).isoformat()
        return profile

    def _detect_drift(self, profile: TasteProfile) -> float:
        """检测品味是否发生显著漂移"""
        recent = profile.history[-self.DRIFT_WINDOW:]
        if not recent:
            return 0.0

        early = profile.history[:max(1, len(profile.history) // 2)]
        early_vec = self._avg_vector(early)
        recent_vec = self._avg_vector(recent)

        # 余弦距离
        sim = TasteProfile._cosine_sim(early_vec, recent_vec)
        return round(1.0 - sim, 3)

    def _avg_vector(self, history: List[Dict]) -> Dict[str, float]:
        """计算历史记录的平均向量"""
        if not history:
            return {dim: 0.5 for dim in VECTOR_DIMENSIONS}
        avg = defaultdict(float)
        for h in history:
            for dim in VECTOR_DIMENSIONS:
                avg[dim] += h["vector_snapshot"].get(dim, 0.5)
        n = len(history)
        return {dim: round(v / n, 3) for dim, v in avg.items()}

    def blend_vectors(
        self,
        vectors: List[Tuple[Dict[str, float], float]],
    ) -> Dict[str, float]:
        """
        多风格向量加权混合

        Args:
            vectors: [(vector, weight), ...] 权重总和应为1

        Returns:
            混合后的12维向量
        """
        blended = {dim: 0.0 for dim in VECTOR_DIMENSIONS}
        total_weight = sum(w for _, w in vectors) or 1.0

        for vec, weight in vectors:
            for dim in VECTOR_DIMENSIONS:
                blended[dim] += vec.get(dim, 0.5) * weight / total_weight

        return {k: round(max(0.0, min(1.0, v)), 3) for k, v in blended.items()}


# 全局单例
taste_encoder = TasteEncoder()
