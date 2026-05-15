"""
G02/G04 品味学习模块
- TasteEncoder: 用户采纳/拒绝行为 → 审美偏好向量
- StyleGenerator: 风格向量 → LLM风格化章节生成
- StylePresets: 5种中文小说风格预设包
"""
from .taste_encoder import TasteEncoder, TasteProfile, VECTOR_DIMENSIONS, taste_encoder
from .style_generator import (
    StyleGenerator, StyleConfig, GenerationResult,
    STYLE_PRESETS, DEFAULT_BLEND, style_generator,
)

__all__ = [
    "TasteEncoder",
    "TasteProfile",
    "VECTOR_DIMENSIONS",
    "taste_encoder",
    "StyleGenerator",
    "StyleConfig",
    "GenerationResult",
    "STYLE_PRESETS",
    "DEFAULT_BLEND",
    "style_generator",
]
