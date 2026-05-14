"""
小说导出模块
将模拟世界的事件和对话导出为可读的小说格式
"""

import os
import re
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..sandbox.narrative_extractor import NarrativeExtractor
    from .agent.dialogue import DialogueManager


@dataclass
class NovelChapter:
    """小说章节"""
    chapter_num: int
    title: str
    content: str
    turns_covered: tuple[int, int]


@dataclass
class NovelExportResult:
    """导出结果"""
    title: str
    world_name: str
    template: str
    chapters: List[NovelChapter]
    total_events: int
    total_dialogues: int

    def to_markdown(self) -> str:
        """导出为Markdown格式"""
        lines = [
            f"# {self.title}",
            "",
            f"**世界**: {self.world_name} | **模板**: {self.template}",
            f"**事件数**: {self.total_events} | **对话数**: {self.total_dialogues}",
            "",
            "---",
            ""
        ]

        for ch in self.chapters:
            lines.append(f"## 第{ch.chapter_num}章 {ch.title}")
            lines.append("")
            lines.append(ch.content)
            lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    def to_html(self) -> str:
        """导出为HTML格式"""
        import html
        content = html.escape(self.to_markdown())
        return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{html.escape(self.title)}</title></head>
<body>
{content.replace('\n', '<br>')}
</body>
</html>"""


class NovelExporter:
    """小说导出器"""

    def __init__(self, events: List[Dict], dialogues: List[Dict], world_info: Dict):
        self.events = events
        self.dialogues = dialogues
        self.world_info = world_info

    def export(
        self,
        narrative_text: Optional[str] = None,
        format: str = "markdown"
    ) -> NovelExportResult:
        """
        导出小说

        Args:
            narrative_text: 叙事提取的章节文本（起承转合结构）
            format: 导出格式 (markdown/html)

        Returns:
            NovelExportResult: 包含章节和元数据
        """
        chapters = self._build_chapters(narrative_text)

        return NovelExportResult(
            title=self.world_info.get("name", "未命名世界"),
            world_name=self.world_info.get("name", ""),
            template=self.world_info.get("template", ""),
            chapters=chapters,
            total_events=len(self.events),
            total_dialogues=len(self.dialogues),
        )

    def _build_chapters(self, narrative_text: Optional[str]) -> List[NovelChapter]:
        """构建章节"""
        chapters = []

        if narrative_text:
            # 使用叙事提取的章节结构
            chapter = NovelChapter(
                chapter_num=1,
                title=self._extract_title(narrative_text) or "序章",
                content=narrative_text,
                turns_covered=(1, len(self.events))
            )
            chapters.append(chapter)
        else:
            # 从事件流构建章节
            chapters = self._build_chapters_from_events()

        return chapters

    def _extract_title(self, text: str) -> Optional[str]:
        """提取章节标题"""
        # 尝试匹配常见的章节标题模式
        patterns = [
            r'第[一二三四五六七八九十百0-9]+章\s*(.+)',
            r'【(.+)】',
            r'^(.+)$',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()[:50]
        return None

    def _build_chapters_from_events(self) -> List[NovelChapter]:
        """从事件流构建章节"""
        chapters = []

        if not self.events:
            return [NovelChapter(
                chapter_num=1,
                title="楔子",
                content="这个世界尚未开始它的故事。",
                turns_covered=(0, 0)
            )]

        # 按段落/场景分组
        scenes = self._group_events_by_scene()

        for i, scene in enumerate(scenes, 1):
            chapter = NovelChapter(
                chapter_num=i,
                title=scene.get("title", f"第{i}章"),
                content=scene.get("content", ""),
                turns_covered=scene.get("turns", (0, 0))
            )
            chapters.append(chapter)

        return chapters

    def _group_events_by_scene(self) -> List[Dict]:
        """将事件按场景分组"""
        scenes = []
        current_scene = {"events": [], "turns": (0, 0)}

        for event in self.events:
            turn = event.get("turn", 0)
            event_type = event.get("type", "normal")
            content = event.get("content", event.get("description", ""))
            actor = event.get("actor", "未知")

            # 对话类型事件单独处理
            if event_type == "interaction" and self._is_dialogue_event(event):
                # 完成当前场景
                if current_scene["events"]:
                    scenes.append(self._finalize_scene(current_scene, len(scenes) + 1))
                    current_scene = {"events": [], "turns": (0, 0)}

                # 添加对话场景
                dialogue_text = self._format_dialogue(event)
                scenes.append({
                    "title": f"场景 {len(scenes) + 1}",
                    "content": dialogue_text,
                    "turns": (turn, turn)
                })
            else:
                # 普通事件加入当前场景
                if not current_scene["events"]:
                    current_scene["turns"] = (turn, turn)
                else:
                    current_scene["turns"] = (current_scene["turns"][0], turn)

                formatted = self._format_event(content, actor, event_type)
                current_scene["events"].append(formatted)

        # 处理最后一个场景
        if current_scene["events"]:
            scenes.append(self._finalize_scene(current_scene, len(scenes) + 1))

        return scenes

    def _is_dialogue_event(self, event: Dict) -> bool:
        """判断是否为对话事件"""
        content = event.get("content", "")
        return "说" in content or "：" in content or "「" in content

    def _format_event(self, content: str, actor: str, event_type: str) -> str:
        """格式化事件内容"""
        type_map = {
            "interaction": "【互动】",
            "story_moment": "【故事时刻】",
            "normal": "【行动】"
        }
        prefix = type_map.get(event_type, "")
        return f"{prefix}{actor}：{content}"

    def _format_dialogue(self, event: Dict) -> str:
        """格式化对话"""
        content = event.get("content", "")
        actor = event.get("actor", "未知")
        return f"「{actor}」{content}"

    def _finalize_scene(self, scene: Dict, num: int) -> Dict:
        """完成场景构建"""
        events = scene.get("events", [])
        if not events:
            return {"title": f"第{num}章", "content": "", "turns": scene.get("turns", (0, 0))}

        content = "\n\n".join(events)
        return {
            "title": f"第{num}章",
            "content": content,
            "turns": scene.get("turns", (0, 0))
        }