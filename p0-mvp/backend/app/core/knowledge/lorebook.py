"""
B01 Lorebook式动态词典
按关键字触发注入世界设定到LLM上下文
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from pathlib import Path
import yaml


@dataclass
class LoreEntry:
    """词条"""
    key: str
    content: str
    aliases: List[str] = field(default_factory=list)
    priority: int = 0  # 优先级，数字越大越优先
    context_limit: int = 500  # 最大注入token


class Lorebook:
    """
    Lorebook式动态词典
    
    当检测到关键词时，自动将对应词条注入到LLM上下文
    支持上下文预算管理（单次不超过30%）
    """
    
    def __init__(
        self,
        max_context_ratio: float = 0.3,
        max_total_chars: int = 2000
    ):
        self.entries: Dict[str, LoreEntry] = {}
        self._keyword_index: Dict[str, Set[str]] = {}  # keyword -> entry_keys
        
        self.max_context_ratio = max_context_ratio
        self.max_total_chars = max_total_chars
    
    def add_entry(self, entry: LoreEntry):
        """添加词条"""
        self.entries[entry.key] = entry
        
        # 建立关键词索引
        keywords = [entry.key] + entry.aliases
        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower not in self._keyword_index:
                self._keyword_index[kw_lower] = set()
            self._keyword_index[kw_lower].add(entry.key)
    
    def add_entries_from_yaml(self, yaml_path: Path):
        """从YAML文件加载词条"""
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        if not data or "entries" not in data:
            return
        
        for entry_data in data["entries"]:
            entry = LoreEntry(
                key=entry_data["key"],
                content=entry_data["content"],
                aliases=entry_data.get("aliases", []),
                priority=entry_data.get("priority", 0),
                context_limit=entry_data.get("context_limit", 500)
            )
            self.add_entry(entry)
    
    def add_entries_from_dict(self, entries_data: List[Dict]):
        """从字典列表加载词条"""
        for entry_data in entries_data:
            entry = LoreEntry(
                key=entry_data["key"],
                content=entry_data["content"],
                aliases=entry_data.get("aliases", []),
                priority=entry_data.get("priority", 0),
                context_limit=entry_data.get("context_limit", 500)
            )
            self.add_entry(entry)
    
    def lookup(self, text: str) -> List[LoreEntry]:
        """
        在文本中查找匹配的词条
        
        Returns:
            按优先级排序的匹配词条列表
        """
        text_lower = text.lower()
        matched_keys: Set[str] = set()
        matched_entries: List[LoreEntry] = []
        
        # 查找所有匹配关键词
        for keyword, keys in self._keyword_index.items():
            if keyword in text_lower:
                matched_keys.update(keys)
        
        # 获取词条并排序
        for key in matched_keys:
            entry = self.entries[key]
            # 检查文本是否真正包含关键词
            keywords = [entry.key] + entry.aliases
            if any(kw.lower() in text_lower for kw in keywords):
                matched_entries.append(entry)
        
        # 按优先级排序
        matched_entries.sort(key=lambda e: e.priority, reverse=True)
        
        return matched_entries
    
    def inject_context(self, text: str, max_chars: Optional[int] = None) -> str:
        """
        注入匹配的Lore上下文到文本
        
        Args:
            text: 原始文本
            max_chars: 最大注入字符数，默认使用 max_total_chars * ratio
            
        Returns:
            带注入上下文的文本
        """
        if max_chars is None:
            max_chars = int(self.max_total_chars * self.max_context_ratio)
        
        matched = self.lookup(text)
        
        if not matched:
            return text
        
        # 构建注入内容
        injection_parts = []
        current_chars = 0
        
        for entry in matched:
            entry_text = f"\n【{entry.key}】{entry.content}"
            if current_chars + len(entry_text) > max_chars:
                # 截断
                remaining = max_chars - current_chars
                if remaining > 50:  # 至少50字符
                    injection_parts.append(entry_text[:remaining] + "...")
                break
            
            injection_parts.append(entry_text)
            current_chars += len(entry_text)
        
        if injection_parts:
            return text + "\n\n[世界设定注入]" + "".join(injection_parts)
        
        return text
    
    def inject_to_prompt(
        self,
        system_prompt: str,
        user_prompt: str,
        max_chars: Optional[int] = None
    ) -> tuple[str, str]:
        """
        注入Lore上下文到提示词
        
        Returns:
            (modified_system_prompt, modified_user_prompt)
        """
        # 在用户提示词中查找关键词
        combined_text = system_prompt + " " + user_prompt
        injected_user = self.inject_context(user_prompt, max_chars)
        
        return system_prompt, injected_user
    
    def clear(self):
        """清空所有词条"""
        self.entries.clear()
        self._keyword_index.clear()
    
    def to_dict(self) -> Dict:
        """序列化为字典"""
        return {
            "entries": [
                {
                    "key": e.key,
                    "content": e.content,
                    "aliases": e.aliases,
                    "priority": e.priority,
                    "context_limit": e.context_limit
                }
                for e in self.entries.values()
            ],
            "max_context_ratio": self.max_context_ratio,
            "max_total_chars": self.max_total_chars
        }
