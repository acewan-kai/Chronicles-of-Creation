"""
B01+B02 世界信息注入 + 知识图谱
包含：Lorebook式动态词典、NetworkX知识图谱
"""

from .lorebook import Lorebook
from .knowledge_graph import KnowledgeGraph

__all__ = ["Lorebook", "KnowledgeGraph"]
