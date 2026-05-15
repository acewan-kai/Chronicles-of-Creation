"""
G04 风格化文本生成器
基于风格向量调用LLM生成章节，支持多风格混合 + 强度调节
"""
import asyncio
import time
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any


# 加载风格预设
_PRESETS_PATH = Path(__file__).parent / "style_presets.yaml"
with open(_PRESETS_PATH, "r", encoding="utf-8") as f:
    _presets_data = yaml.safe_load(f)

STYLE_PRESETS: Dict[str, dict] = _presets_data["presets"]
DEFAULT_BLEND: Dict[str, float] = _presets_data.get("default_blend", {})


@dataclass
class StyleConfig:
    """风格配置"""
    style_name: str = "shuangwen"        # 主导风格
    intensity: int = 50                   # 强度 0-100
    custom_vector: Optional[Dict[str, float]] = None  # 自定义向量（覆盖预设）
    blend_weights: Optional[Dict[str, float]] = None  # 混合权重

    def to_dict(self) -> dict:
        return {
            "style_name": self.style_name,
            "intensity": self.intensity,
            "custom_vector": self.custom_vector,
            "blend_weights": self.blend_weights,
        }


@dataclass
class GenerationResult:
    """生成结果"""
    chapter_text: str
    style_config: StyleConfig
    effective_vector: Dict[str, float]
    llm_provider: str
    tokens_used: int
    generation_time_ms: float

    def to_dict(self) -> dict:
        return {
            "chapter_text": self.chapter_text,
            "style_config": self.style_config.to_dict(),
            "effective_vector": {k: round(v, 3) for k, v in self.effective_vector.items()},
            "llm_provider": self.llm_provider,
            "tokens_used": self.tokens_used,
            "generation_time_ms": round(self.generation_time_ms, 0),
        }


class StyleGenerator:
    """
    风格化文本生成器

    将风格向量映射为LLM提示词，生成符合审美偏好的章节文本。
    支持：
    - 5种预设风格 + 自定义向量
    - 强度 0-100 可调
    - 多风格混合（用户×角色×世界×预设）
    """

    VECTOR_DIMENSIONS = [
        "pace", "density", "tension", "emotion_depth",
        "description_richness", "dialogue_ratio", "inner_monologue",
        "humor", "darkness", "poetry", "action_ratio", "world_detail",
    ]

    def __init__(self):
        self._llm = None  # AsyncOpenAI or compatible client

    def set_llm(self, client):
        """设置LLM客户端（AsyncOpenAI或其兼容实现）"""
        self._llm = client

    def get_presets(self) -> List[dict]:
        """获取所有风格预设列表"""
        return [
            {
                "id": name,
                "name": preset["name"],
                "description": preset["description"],
                "vector": preset["vector"],
            }
            for name, preset in STYLE_PRESETS.items()
        ]

    def get_preset(self, style_name: str) -> Optional[dict]:
        """获取单个风格预设"""
        return STYLE_PRESETS.get(style_name)

    def resolve_vector(self, config: StyleConfig) -> Dict[str, float]:
        """
        解析有效的风格向量

        优先级：custom_vector > 预设向量
        强度映射：0=完全自然（0.5均衡），100=极致风格（预设向量）
        """
        # 基准向量
        if config.custom_vector:
            base = dict(config.custom_vector)
        else:
            preset = STYLE_PRESETS.get(config.style_name, STYLE_PRESETS["shuangwen"])
            base = dict(preset["vector"])

        # 强度映射：从均衡(0.5)到目标向量
        intensity_ratio = max(0.0, min(1.0, config.intensity / 100.0))
        result = {}
        for dim in self.VECTOR_DIMENSIONS:
            target = base.get(dim, 0.5)
            result[dim] = 0.5 + (target - 0.5) * intensity_ratio

        return result

    def blend_vectors(
        self,
        user_vector: Optional[Dict[str, float]] = None,
        world_vector: Optional[Dict[str, float]] = None,
        character_vector: Optional[Dict[str, float]] = None,
        preset_name: str = "shuangwen",
        weights: Optional[Dict[str, float]] = None,
    ) -> Dict[str, float]:
        """
        多源风格混合

        Args:
            user_vector: 用户品味向量（冷启动可为None）
            world_vector: 世界模板推荐风格
            character_vector: 角色视角风格
            preset_name: 预设风格包名
            weights: 自定义权重，默认用DEFAULT_BLEND
        """
        w = weights or DEFAULT_BLEND
        preset = STYLE_PRESETS.get(preset_name, STYLE_PRESETS["shuangwen"])

        # 冷启动处理：用户向量不存在时增大其他权重
        sources = []
        if user_vector and w.get("user_weight", 0) > 0:
            sources.append((user_vector, w["user_weight"]))
        if world_vector:
            sources.append((world_vector, w.get("world_weight", 0.4)))
        if character_vector:
            sources.append((character_vector, w.get("character_weight", 0.3)))
        sources.append((preset["vector"], w.get("preset_weight", 0.3)))

        # 重新归一化
        total = sum(s[1] for s in sources) or 1.0
        return {
            dim: round(sum(s[0].get(dim, 0.5) * s[1] / total for s in sources), 3)
            for dim in self.VECTOR_DIMENSIONS
        }

    async def generate(
        self,
        world_context: str,
        story_context: str,
        config: StyleConfig,
        chapter_number: int = 1,
    ) -> GenerationResult:
        """
        生成风格化章节

        Args:
            world_context: 世界观背景描述
            story_context: 当前剧情上下文
            config: 风格配置
            chapter_number: 章节编号
        """
        if not self._llm:
            raise RuntimeError("LLM client not set. Call set_llm() first.")

        t0 = time.monotonic()

        # 解析有效向量
        effective_vector = self.resolve_vector(config)

        # 获取提示词模板
        preset = STYLE_PRESETS.get(config.style_name, STYLE_PRESETS["shuangwen"])
        template = preset["prompt_template"]

        # 构建上下文摘要
        world_ctx = world_context[:800] if world_context else "默认修仙世界观"
        story_ctx = story_context[:600] if story_context else "故事刚开篇，主角即将面临第一个转折"

        prompt = template.format(
            world_context=world_ctx,
            story_context=story_ctx,
            intensity=config.intensity,
        )

        # 风格向量注入提示词
        vector_hint = self._vector_to_hint(effective_vector, config.intensity)
        prompt += f"\n\n[风格参数] {vector_hint}\n[章节编号] 第{chapter_number}章"

        # LLM调用 (AsyncOpenAI-compatible)
        system_prompt = f"你是{STYLE_PRESETS[config.style_name]['name']}风格的AI小说作者。严格按照风格参数写作。"
        try:
            completion = await self._llm.chat.completions.create(
                model="auto",  # provider-specific default
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7 + (config.intensity / 100) * 0.3,
                max_tokens=2000,
            )
            content = completion.choices[0].message.content or ""
            tokens = completion.usage.total_tokens if completion.usage else 0
        except Exception as e:
            # 降级：返回错误信息
            content = f"[生成失败: {str(e)}]"
            tokens = 0

        elapsed_ms = (time.monotonic() - t0) * 1000

        return GenerationResult(
            chapter_text=content,
            style_config=config,
            effective_vector=effective_vector,
            llm_provider="auto",
            tokens_used=tokens,
            generation_time_ms=elapsed_ms,
        )

    def _vector_to_hint(self, vector: Dict[str, float], intensity: int) -> str:
        """将风格向量转化为自然语言提示"""
        hints = []
        if vector.get("pace", 0.5) > 0.6:
            hints.append(f"节奏快({vector['pace']:.1f})")
        elif vector["pace"] < 0.4:
            hints.append(f"节奏慢({vector['pace']:.1f})")
        if vector.get("emotion_depth", 0.5) > 0.6:
            hints.append(f"情感深({vector['emotion_depth']:.1f})")
        if vector.get("description_richness", 0.5) > 0.6:
            hints.append(f"描写丰富({vector['description_richness']:.1f})")
        if vector.get("action_ratio", 0.5) > 0.6:
            hints.append(f"动作密集({vector['action_ratio']:.1f})")
        if vector.get("dialogue_ratio", 0.5) > 0.6:
            hints.append(f"对话主导({vector['dialogue_ratio']:.1f})")
        if vector.get("darkness", 0.5) > 0.6:
            hints.append(f"暗黑色调({vector['darkness']:.1f})")
        if vector.get("poetry", 0.5) > 0.5:
            hints.append(f"诗意表达({vector['poetry']:.1f})")
        hints.append(f"风格强度:{intensity}%")
        return ", ".join(hints)


# 全局单例
style_generator = StyleGenerator()
