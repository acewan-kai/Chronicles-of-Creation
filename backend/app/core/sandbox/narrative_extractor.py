"""
A05 叙事提取引擎
将事件日志序列转化为结构化叙事文本

核心功能：
1. 从事件序列中提取高质量叙事线
2. 生成带"起承转合"结构的章节文本
3. 支持流式输出和LLM降级fallback
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Literal, TYPE_CHECKING
from datetime import datetime
from enum import Enum

if TYPE_CHECKING:
    from ..sandbox.action_executor import BaseLLMClient


# ═══════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════

@dataclass
class StorySection:
    """章节段落"""
    phase: Literal["setup", "development", "climax", "resolution"]  # 起承转合
    turn_range: str          # 回合范围，如"第1-3回合"
    content: str             # 段落内容
    key_event: str           # 核心事件描述


@dataclass
class NarrativeChapter:
    """完整叙事章节"""
    chapter_title: str
    total_turns: int
    sections: List[StorySection]
    characters: List[str]        # 出现的角色列表
    locations: List[str]         # 出现的地点列表
    theme: str = ""              # 主题/核心冲突
    quality_score: float = 0.0  # 质量评分


# ═══════════════════════════════════════════════════════════
# Prompt 模板
# ═══════════════════════════════════════════════════════════

NARRATIVE_SYSTEM_PROMPT = """你是一个网络小说叙事重构专家。你的任务是将一段段事件记录重新组织为一章流畅的故事文本。

写作风格要求：
- 文风：第三人称叙事，冷峻白描为主，避免冗长心理描写
- 节奏：事件驱动，对话简洁有力，环境描写点到即止
- 人物：突出性格特征，通过行为而非陈述展现内心
- 禁止：总结式陈述（如"这一天发生了很多事"）

章节结构要求（必须包含四段，每段以【起】【承】【转】【合】标记开头）：

【起】背景与情境（第X-X回合）
- 交代时间、地点、人物关系
- 铺设核心冲突的前因
- 约100-150字

【承】冲突发展（第X-X回合）
- 推进核心冲突
- 多角色参与或对比
- 约150-200字

【转】高潮与转折（第X-X回合）
- 事件走向关键节点
- 意外或冲突爆发
- 约100-150字

【合】余韵与展望（第X-X回合）
- 事件暂告段落
- 暗示后续发展
- 约80-100字

重要规则：
- 必须严格使用【起】【承】【转】【合】标记段落开头
- 不能虚构事件，只能重组已有事件
- 保留关键对话和行动细节
- 角色对话使用「」标记"""


NARRATIVE_USER_PROMPT_TEMPLATE = """请将以下事件序列重构为一章故事：

{events_context}

请严格按【起】【承】【转】【合】四段结构输出，每段都要标注回合范围。"""


FALLBACK_SUMMARY_TEMPLATE = """第{total_turns}回合纪事

【起】这一天，青云仙门迎来了不平静的一天。
【承】门中弟子们各怀心思，暗流涌动。
【转】然而就在此时，一场意外悄然发生。
【合】这一日的种种，或将成为日后风云变幻的伏笔。

—— 本章内容为自动生成，事件详情请参见事件日志 ——"""


# ═══════════════════════════════════════════════════════════
# 叙事提取引擎
# ═══════════════════════════════════════════════════════════

class NarrativeExtractor:
    """
    叙事提取引擎

    将事件日志转化为结构化叙事章节
    """

    def __init__(
        self,
        max_turns_per_chapter: int = 20,
        min_events_for_chapter: int = 5,
    ):
        self.max_turns_per_chapter = max_turns_per_chapter
        self.min_events_for_chapter = min_events_for_chapter

        # 质量阈值
        self.min_event_score: float = 0.0
        self.preferred_action_types: set = {"interaction", "story_moment", "normal"}

    async def extract(
        self,
        events: List[Any],
        llm_client: Optional["BaseLLMClient"] = None,
        enable_streaming: bool = False,
    ) -> NarrativeChapter:
        """
        从事件序列中提取引擎章节

        Args:
            events: 事件列表（按turn排序）
            llm_client: LLM客户端（None时使用fallback）
            enable_streaming: 是否启用流式输出（暂不支持）

        Returns:
            NarrativeChapter: 完整章节结构
        """
        if not events or len(events) < self.min_events_for_chapter:
            return self._create_fallback_chapter(events)

        # 预处理：按turn分组，过滤低质量事件
        processed_events = self._preprocess_events(events)

        # 提取元信息
        characters = self._extract_characters(events)
        locations = self._extract_locations(events)
        theme = self._infer_theme(events)

        # 确定章节标题
        chapter_title = self._generate_chapter_title(events)

        # 如果有LLM客户端，使用LLM生成
        if llm_client:
            try:
                sections = await self._generate_with_llm(
                    processed_events, llm_client
                )
                return NarrativeChapter(
                    chapter_title=chapter_title,
                    total_turns=len(events),
                    sections=sections,
                    characters=characters,
                    locations=locations,
                    theme=theme,
                    quality_score=self._calculate_quality_score(events),
                )
            except Exception as e:
                print(f"[Narrative] LLM generation failed: {e}, using fallback")
                return self._create_fallback_chapter(
                    events, chapter_title, characters, locations, theme
                )
        else:
            return self._create_fallback_chapter(
                events, chapter_title, characters, locations, theme
            )

    def _preprocess_events(self, events: List[Any]) -> List[Dict]:
        """预处理事件序列"""
        processed = []
        for event in events:
            # 跳过低分事件
            score = getattr(event, 'score', None)
            if score is not None and score < self.min_event_score:
                continue

            # 跳过纯状态更新事件
            action = getattr(event, 'action', '')
            if not action or len(action) < 5:
                continue

            processed.append({
                "turn": getattr(event, 'turn', 0),
                "day": getattr(event, 'day', 1),
                "actor": getattr(event, 'actor_name', '未知'),
                "target": getattr(event, 'target_name', ''),
                "action": action,
                "action_type": getattr(event, 'action_type', 'normal'),
                "location": getattr(event, 'location', ''),
                "score": score or 0.0,
            })

        return processed

    def _extract_characters(self, events: List[Any]) -> List[str]:
        """提取出现的角色列表"""
        chars = {}
        for event in events:
            actor = getattr(event, 'actor_name', '')
            if actor:
                chars[actor] = True
            target = getattr(event, 'target_name', '')
            if target:
                chars[target] = True
        return list(chars.keys())[:10]  # 最多10个角色

    def _extract_locations(self, events: List[Any]) -> List[str]:
        """提取出现的地点列表"""
        locs = {}
        for event in events:
            loc = getattr(event, 'location', '')
            if loc:
                locs[loc] = True
        return list(locs.keys())[:5]  # 最多5个地点

    def _infer_theme(self, events: List[Any]) -> str:
        """推断章节主题"""
        interaction_count = sum(
            1 for e in events
            if getattr(e, 'action_type', '') == 'interaction'
        )
        story_moment_count = sum(
            1 for e in events
            if getattr(e, 'action_type', '') == 'story_moment'
        )

        if story_moment_count > 0:
            return "关键事件"
        elif interaction_count > 3:
            return "人际纠葛"
        else:
            return "日常修炼"

    def _generate_chapter_title(self, events: List[Any]) -> str:
        """生成章节标题"""
        if not events:
            return "序幕"

        first_turn = getattr(events[0], 'turn', 1)
        last_turn = getattr(events[-1], 'turn', first_turn)

        if first_turn == last_turn:
            return f"第{first_turn}回合纪事"
        else:
            return f"第{first_turn}-{last_turn}回合纪事"

    def _calculate_quality_score(self, events: List[Any]) -> float:
        """计算章节质量评分"""
        if not events:
            return 0.0

        scores = [getattr(e, 'score', 0) or 0 for e in events]
        avg_score = sum(scores) / len(scores) if scores else 0

        interaction_ratio = sum(
            1 for e in events
            if getattr(e, 'action_type', '') == 'interaction'
        ) / len(events)

        return min(1.0, avg_score * 0.7 + interaction_ratio * 0.3)

    async def _generate_with_llm(
        self,
        events: List[Dict],
        llm_client: "BaseLLMClient",
    ) -> List[StorySection]:
        """使用LLM生成叙事段落"""
        # 构建事件上下文
        events_context = self._build_events_context(events)

        # 构建prompt
        system_prompt = NARRATIVE_SYSTEM_PROMPT
        user_prompt = NARRATIVE_USER_PROMPT_TEMPLATE.format(
            events_context=events_context
        )

        # 调用LLM
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        response = await llm_client.generate(
            messages,
            temperature=0.7,
            max_tokens=2000,
        )

        # 解析响应
        return self._parse_llm_response(response, events)

    def _build_events_context(self, events: List[Dict]) -> str:
        """构建事件上下文文本"""
        lines = []
        current_section = []

        for event in events:
            turn = event.get('turn', 0)
            day = event.get('day', 1)
            actor = event.get('actor', '未知')
            target = event.get('target', '')
            action = event.get('action', '')
            action_type = event.get('action_type', 'normal')
            location = event.get('location', '')
            score = event.get('score', 0)

            # 构建事件行
            event_line = f"[回合{turn}][{action_type}] {actor}"

            if target:
                event_line += f" → {target}"

            event_line += f"：{action}"

            if location:
                event_line += f"（{location}）"

            if score and score > 3.0:
                event_line += f" [精彩]"

            lines.append(event_line)

        return "\n".join(lines)

    def _parse_llm_response(
        self,
        response: Optional[str],
        events: List[Dict],
    ) -> List[StorySection]:
        """解析LLM响应为结构化段落"""
        if not response:
            return self._create_fallback_sections(events)

        sections = []
        phase_pattern = re.compile(r'【(起|承|转|合)】')

        # 尝试按【起】【承】【转】【合】分割
        parts = phase_pattern.split(response)

        # parts[0]可能是空或序言，parts[1]起, parts[2]起的内容, ...
        phase_names = ["setup", "development", "climax", "resolution"]

        # 简化解析：如果响应中包含【起】【承】【转】【合】
        if '【起】' in response and '【承】' in response:
            # 按段落分割
            current_phase = None
            current_content = ""

            for line in response.split('\n'):
                phase_match = phase_pattern.search(line)
                if phase_match:
                    # 保存上一个段落
                    if current_phase and current_content:
                        sections.append(StorySection(
                            phase=current_phase,
                            turn_range="",
                            content=current_content.strip(),
                            key_event=self._extract_key_event(current_content),
                        ))

                    # 开始新段落
                    phase_char = phase_match.group(1)
                    phase_map = {"起": "setup", "承": "development",
                                 "转": "climax", "合": "resolution"}
                    current_phase = phase_map.get(phase_char, "development")
                    current_content = line.split('】', 1)[-1] if '】' in line else line
                else:
                    current_content += "\n" + line

            # 保存最后一个段落
            if current_phase and current_content:
                sections.append(StorySection(
                    phase=current_phase,
                    turn_range="",
                    content=current_content.strip(),
                    key_event=self._extract_key_event(current_content),
                ))

        # 如果解析失败，使用fallback
        if not sections:
            return self._create_fallback_sections(events)

        return sections

    def _extract_key_event(self, text: str) -> str:
        """从文本中提取关键事件"""
        # 简化：取前30字作为关键事件描述
        clean = text.strip().replace('\n', ' ')
        return clean[:30] + "..." if len(clean) > 30 else clean

    def _create_fallback_chapter(
        self,
        events: List[Any],
        chapter_title: str = "",
        characters: Optional[List[str]] = None,
        locations: Optional[List[str]] = None,
        theme: str = "",
    ) -> NarrativeChapter:
        """创建降级章节（无LLM时）"""
        sections = self._create_fallback_sections(events)

        if not chapter_title:
            chapter_title = f"第1-{len(events)}回合纪事"

        return NarrativeChapter(
            chapter_title=chapter_title,
            total_turns=len(events),
            sections=sections,
            characters=characters or [],
            locations=locations or [],
            theme=theme or "自动生成",
            quality_score=0.3,
        )

    def _create_fallback_sections(
        self,
        events: List[Any],
    ) -> List[StorySection]:
        """创建降级段落"""
        if not events:
            return []

        total = len(events)
        q1_end = max(1, total // 4)
        q2_end = max(q1_end + 1, total // 2)
        q3_end = max(q2_end + 1, total * 3 // 4)

        sections = []

        # 【起】
        setup_events = events[:q1_end]
        setup_content = self._summarize_events(setup_events, "起")
        sections.append(StorySection(
            phase="setup",
            turn_range=f"第{getattr(events[0], 'turn', 1)}-{getattr(setup_events[-1], 'turn', q1_end)}回合",
            content=setup_content,
            key_event="开篇情境",
        ))

        # 【承】
        dev_events = events[q1_end:q2_end]
        if dev_events:
            sections.append(StorySection(
                phase="development",
                turn_range=f"第{getattr(dev_events[0], 'turn', q1_end+1)}-{getattr(dev_events[-1], 'turn', q2_end)}回合",
                content=self._summarize_events(dev_events, "承"),
                key_event="冲突发展",
            ))

        # 【转】
        climax_events = events[q2_end:q3_end]
        if climax_events:
            sections.append(StorySection(
                phase="climax",
                turn_range=f"第{getattr(climax_events[0], 'turn', q2_end+1)}-{getattr(climax_events[-1], 'turn', q3_end)}回合",
                content=self._summarize_events(climax_events, "转"),
                key_event="高潮转折",
            ))

        # 【合】
        final_events = events[q3_end:]
        if final_events:
            sections.append(StorySection(
                phase="resolution",
                turn_range=f"第{getattr(final_events[0], 'turn', q3_end+1)}-{getattr(final_events[-1], 'turn', total)}回合",
                content=self._summarize_events(final_events, "合"),
                key_event="余韵收尾",
            ))

        return sections

    def _summarize_events(
        self,
        events: List[Any],
        phase: str,
    ) -> str:
        """将事件列表总结为一个段落（无LLM时）"""
        if not events:
            return f"【{phase}】内容待补充"

        lines = []
        phase_labels = {"起": "这一日", "承": "与此同时", "转": "然而就在这时", "合": "待一切归于平静"}
        label = phase_labels.get(phase, "")

        for event in events[:5]:  # 最多取5个事件
            actor = getattr(event, 'actor_name', '某人')
            action = getattr(event, 'action', '做了一件事')
            target = getattr(event, 'target_name', '')
            location = getattr(event, 'location', '')

            line = f"{actor}"
            if target:
                line += f"与{target}"
            line += f"：{action}"
            if location:
                line += f"（{location}）"
            line += "。"

            lines.append(line)

        summary = label + "，" + "".join(lines)

        if len(events) > 5:
            summary += f"此外还有{len(events) - 5}起事件发生。"

        return summary

    def to_dict(self, chapter: NarrativeChapter) -> Dict[str, Any]:
        """将章节转换为API响应格式"""
        return {
            "chapter_title": chapter.chapter_title,
            "total_turns": chapter.total_turns,
            "theme": chapter.theme,
            "quality_score": round(chapter.quality_score, 2),
            "sections": [
                {
                    "phase": s.phase,
                    "phase_name": {
                        "setup": "起",
                        "development": "承",
                        "climax": "转",
                        "resolution": "合",
                    }.get(s.phase, s.phase),
                    "turn_range": s.turn_range,
                    "content": s.content,
                    "key_event": s.key_event,
                }
                for s in chapter.sections
            ],
            "characters": chapter.characters,
            "locations": chapter.locations,
            "generated_at": datetime.now().isoformat(),
        }