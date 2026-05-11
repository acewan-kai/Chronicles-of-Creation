"""
G01 基础审美评分
基于规则的文本质量评分（1-5分）
"""

import re
from dataclasses import dataclass
from typing import List, Dict, Optional
from enum import Enum


class ScoreLevel(Enum):
    """评分级别"""
    POOR = 1      # 1分
    FAIR = 2      # 2分
    GOOD = 3      # 3分
    EXCELLENT = 4 # 4分
    OUTSTANDING = 5  # 5分


@dataclass
class ScoreResult:
    """评分结果"""
    total_score: float
    level: ScoreLevel
    breakdown: Dict[str, float]
    highlights: List[str]
    suggestions: List[str]
    
    def to_dict(self) -> dict:
        return {
            "score": self.total_score,
            "level": self.level.name,
            "breakdown": self.breakdown,
            "highlights": self.highlights,
            "suggestions": self.suggestions
        }


class AestheticScorer:
    """
    审美评分器
    
    基于规则的文本质量评分
    评分维度：
    - 句式多样性
    - 情感密度
    - 意象丰富度
    - 叙事张力
    - 对话自然度
    """
    
    # 情感词库
    EMOTIONAL_WORDS = {
        "positive": [
            "喜悦", "高兴", "开心", "微笑", "兴奋", "激动", "欣慰", "温暖",
            "爱", "喜欢", "欣赏", "敬佩", "感激", "希望", "期待", "憧憬"
        ],
        "negative": [
            "悲伤", "痛苦", "难过", "伤心", "绝望", "愤怒", "怨恨", "恐惧",
            "担忧", "焦虑", "不安", "失望", "遗憾", "叹息", "沮丧", "无奈"
        ],
        "complex": [
            "犹豫", "矛盾", "挣扎", "复杂", "深沉", "微妙", "五味", "百感",
            "心酸", "苦涩", "酸楚", "凄凉", "苍凉", "萧瑟"
        ]
    }
    
    # 叙事意象词
    NARRATIVE_IMAGERY = {
        "visual": ["雾", "烟", "光", "影", "月", "星", "海", "山", "风", "雨", "雪", "云"],
        "action": ["凝视", "眺望", "转身", "漫步", "驻足", "徘徊", "叹息", "低语", "呢喃"],
        "atmosphere": ["静谧", "沉寂", "苍茫", "幽暗", "朦胧", "肃穆", "诡异", "压抑"]
    }
    
    # 高质量叙事词汇
    QUALITY_MARKERS = [
        "仿佛", "似乎", "如同", "恰似",  # 比喻
        "然而", "可是", "却", "竟",      # 转折
        "忽然", "骤然", "陡然", "蓦然",  # 突变
        "缓缓", "渐渐", "慢慢", "逐步",  # 渐进
        "回想起", "记忆", "往事",        # 回忆
    ]
    
    # 负面标记（降低分数）
    NEGATIVE_MARKERS = [
        "非常", "特别", "极其",  # 过度修饰
        "然后", "接着", "之后",  # 平铺直叙
        "说", "问道", "回答",    # 简单对话
    ]
    
    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None
    ):
        # 默认权重
        self.weights = weights or {
            "diversity": 0.20,      # 句式多样性
            "emotion": 0.25,        # 情感密度
            "imagery": 0.20,        # 意象丰富度
            "tension": 0.20,        # 叙事张力
            "dialogue": 0.15,       # 对话自然度
        }
    
    def score(self, text: str) -> ScoreResult:
        """
        对文本进行评分
        
        Args:
            text: 待评分文本
            
        Returns:
            ScoreResult: 评分结果
        """
        if not text or len(text.strip()) < 10:
            return ScoreResult(
                total_score=1.0,
                level=ScoreLevel.POOR,
                breakdown={},
                highlights=[],
                suggestions=["文本过短，无法评分"]
            )
        
        # 各维度评分
        breakdown = {
            "diversity": self._score_diversity(text),
            "emotion": self._score_emotion(text),
            "imagery": self._score_imagery(text),
            "tension": self._score_tension(text),
            "dialogue": self._score_dialogue(text),
        }
        
        # 加权总分
        total = sum(
            breakdown[dim] * self.weights[dim]
            for dim in self.weights
        )
        
        # 确保在1-5范围内
        total = max(1.0, min(5.0, total))
        
        # 确定级别
        level = self._get_level(total)
        
        # 提取亮点和建议
        highlights = self._extract_highlights(text, breakdown)
        suggestions = self._generate_suggestions(text, breakdown)
        
        return ScoreResult(
            total_score=round(total, 2),
            level=level,
            breakdown={k: round(v, 2) for k, v in breakdown.items()},
            highlights=highlights,
            suggestions=suggestions
        )
    
    def _score_diversity(self, text: str) -> float:
        """句式多样性评分"""
        # 句子数量
        sentences = re.split(r'[。！？\n]', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        sentence_count = len(sentences)
        
        if sentence_count == 0:
            return 1.0
        
        # 平均句子长度
        avg_length = sum(len(s) for s in sentences) / sentence_count
        
        # 句子长度变化
        lengths = [len(s) for s in sentences]
        if len(lengths) > 1:
            length_variance = max(lengths) - min(lengths)
        else:
            length_variance = 0
        
        # 标点符号多样性
        punctuation = set(re.findall(r'[，。！？、；：""''（）]', text))
        
        score = 1.0
        
        # 句子长度适中（15-50字符）
        if 15 <= avg_length <= 50:
            score += 0.5
        
        # 有句子长度变化
        if length_variance > 20:
            score += 0.5
        
        # 标点符号丰富
        if len(punctuation) >= 4:
            score += 0.5
        
        return min(5.0, score)
    
    def _score_emotion(self, text: str) -> float:
        """情感密度评分"""
        text_lower = text.lower()
        total_emotional = 0
        
        # 统计各类情感词
        for category, words in self.EMOTIONAL_WORDS.items():
            count = sum(1 for w in words if w in text)
            total_emotional += count
        
        # 文本长度
        text_len = len(text)
        
        # 情感密度（每100字多少情感词）
        density = (total_emotional / text_len) * 100 if text_len > 0 else 0
        
        # 评分
        score = 1.0
        if density >= 3:
            score = 5.0
        elif density >= 2:
            score = 4.0
        elif density >= 1:
            score = 3.0
        elif density >= 0.5:
            score = 2.0
        
        return score
    
    def _score_imagery(self, text: str) -> float:
        """意象丰富度评分"""
        total_imagery = 0
        
        for category, words in self.NARRATIVE_IMAGERY.items():
            count = sum(1 for w in words if w in text)
            total_imagery += count
        
        # 评分
        score = 1.0
        if total_imagery >= 8:
            score = 5.0
        elif total_imagery >= 6:
            score = 4.0
        elif total_imagery >= 4:
            score = 3.0
        elif total_imagery >= 2:
            score = 2.0
        
        return score
    
    def _score_tension(self, text: str) -> float:
        """叙事张力评分"""
        # 高质量标记
        quality_count = sum(1 for m in self.QUALITY_MARKERS if m in text)
        
        # 负面标记
        negative_count = sum(1 for m in self.NEGATIVE_MARKERS if m in text)
        
        # 计算
        score = 2.0 + (quality_count * 0.3) - (negative_count * 0.1)
        
        # 检查是否有转折或突变
        if any(w in text for w in ["忽然", "骤然", "然而", "却", "竟"]):
            score += 0.5
        
        return min(5.0, max(1.0, score))
    
    def _score_dialogue(self, text: str) -> float:
        """对话自然度评分"""
        # 对话引号数量
        quotes = re.findall(r'[""\'""\'""«»]', text)
        dialogue_count = len(quotes) // 2  # 每组对话2个引号
        
        if dialogue_count == 0:
            return 3.0  # 无对话，中等评分
        
        # 检查对话是否自然
        # 自然对话通常有动作描写或情感
        dialogue_sentences = re.split(r'[""\'""\'""«»]', text)
        
        natural_count = 0
        for ds in dialogue_sentences:
            if any(w in ds for w in ["道", "说", "问", "答"]):
                if any(w in ds for w in ["微微", "轻轻", "缓缓", "低声", "抬头"]):
                    natural_count += 1
        
        # 评分
        if natural_count >= dialogue_count * 0.7:
            return 5.0
        elif natural_count >= dialogue_count * 0.4:
            return 4.0
        elif natural_count >= 1:
            return 3.0
        else:
            return 2.0
    
    def _get_level(self, score: float) -> ScoreLevel:
        """根据分数确定级别"""
        if score >= 4.5:
            return ScoreLevel.OUTSTANDING
        elif score >= 3.5:
            return ScoreLevel.EXCELLENT
        elif score >= 2.5:
            return ScoreLevel.GOOD
        elif score >= 1.5:
            return ScoreLevel.FAIR
        else:
            return ScoreLevel.POOR
    
    def _extract_highlights(self, text: str, breakdown: Dict[str, float]) -> List[str]:
        """提取亮点"""
        highlights = []
        
        if breakdown["emotion"] >= 4:
            highlights.append("情感表达丰富动人")
        if breakdown["imagery"] >= 4:
            highlights.append("意象描写生动")
        if breakdown["tension"] >= 4:
            highlights.append("叙事有张力")
        if breakdown["diversity"] >= 4:
            highlights.append("句式变化多样")
        
        return highlights
    
    def _generate_suggestions(self, text: str, breakdown: Dict[str, float]) -> List[str]:
        """生成改进建议"""
        suggestions = []
        
        if breakdown["emotion"] < 3:
            suggestions.append("可增加情感描写，让角色更有血肉")
        if breakdown["imagery"] < 3:
            suggestions.append("可加入更多视觉、听觉等感官描写")
        if breakdown["tension"] < 3:
            suggestions.append("可加入转折或悬念，增强故事张力")
        if breakdown["diversity"] < 3:
            suggestions.append("可变化句式长度，避免平铺直叙")
        if breakdown["dialogue"] < 3:
            suggestions.append("对话可配合动作描写，更加自然")
        
        if not suggestions:
            suggestions.append("整体质量良好")
        
        return suggestions
    
    def batch_score(self, texts: List[str]) -> List[ScoreResult]:
        """批量评分"""
        return [self.score(text) for text in texts]
    
    def score_story_moment(self, text: str) -> float:
        """
        故事时刻专项评分
        
        更关注叙事质量、情感深度
        """
        result = self.score(text)
        
        # 故事时刻加分
        story_bonus = 0.0
        
        # 是否有回忆
        if "回想起" in text or "记得" in text:
            story_bonus += 0.3
        
        # 是否有内心独白
        if "心想" in text or "想到" in text:
            story_bonus += 0.2
        
        # 是否有环境呼应
        if any(w in text for w in ["雨", "风", "雾", "月"]):
            story_bonus += 0.2
        
        return min(5.0, result.total_score + story_bonus)
