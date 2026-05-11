"""
B02 知识图谱
使用NetworkX存储势力、地点、法则、角色之间的关联
"""

import networkx as nx
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Any
from enum import Enum
import json


class NodeType(Enum):
    """节点类型"""
    CHARACTER = "character"
    LOCATION = "location"
    FACTION = "faction"
    ITEM = "item"
    EVENT = "event"
    RULE = "rule"  # 世界法则


class RelationType(Enum):
    """关系类型"""
    KNOWS = "knows"
    FRIEND = "friend"
    ENEMY = "enemy"
    BELONGS_TO = "belongs_to"
    LOCATED_AT = "located_at"
    OWNED_BY = "owned_by"
    PARTICIPATED_IN = "participated_in"
    INFLUENCES = "influences"
    CAUSED = "caused"


@dataclass
class KnowledgeNode:
    """知识节点"""
    id: str
    node_type: NodeType
    name: str
    description: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.node_type.value,
            "name": self.name,
            "description": self.description,
            "properties": self.properties
        }


@dataclass
class KnowledgeRelation:
    """知识关系"""
    source: str
    target: str
    relation_type: RelationType
    weight: float = 1.0
    description: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "target": self.target,
            "type": self.relation_type.value,
            "weight": self.weight,
            "description": self.description,
            "properties": self.properties
        }


class KnowledgeGraph:
    """
    知识图谱
    
    使用NetworkX存储和管理世界知识
    支持节点、关系查询和路径发现
    """
    
    def __init__(self):
        self.graph = nx.MultiDiGraph()
        self.nodes: Dict[str, KnowledgeNode] = {}
        self._node_types_index: Dict[NodeType, Set[str]] = {
            nt: set() for nt in NodeType
        }
    
    # ========== 节点操作 ==========
    
    def add_node(self, node: KnowledgeNode):
        """添加节点"""
        self.nodes[node.id] = node
        self.graph.add_node(node.id)
        self._node_types_index[node.node_type].add(node.id)
    
    def get_node(self, node_id: str) -> Optional[KnowledgeNode]:
        """获取节点"""
        return self.nodes.get(node_id)
    
    def get_nodes_by_type(self, node_type: NodeType) -> List[KnowledgeNode]:
        """按类型获取节点"""
        return [
            self.nodes[nid] 
            for nid in self._node_types_index[node_type]
            if nid in self.nodes
        ]
    
    def remove_node(self, node_id: str):
        """删除节点"""
        if node_id in self.nodes:
            node = self.nodes[node_id]
            self._node_types_index[node.node_type].remove(node_id)
            del self.nodes[node_id]
            self.graph.remove_node(node_id)
    
    # ========== 关系操作 ==========
    
    def add_relation(self, relation: KnowledgeRelation):
        """添加关系"""
        self.graph.add_edge(
            relation.source,
            relation.target,
            key=relation.relation_type.value,
            **relation.to_dict()
        )
    
    def get_relations(
        self,
        node_id: str,
        relation_type: Optional[RelationType] = None,
        direction: str = "out"  # "out", "in", "both"
    ) -> List[KnowledgeRelation]:
        """获取节点的关系"""
        relations = []
        
        if direction in ("out", "both"):
            for _, target, data in self.graph.out_edges(node_id, data=True):
                if relation_type is None or data.get("type") == relation_type.value:
                    relations.append(KnowledgeRelation(**{
                        k: v for k, v in data.items()
                        if k != "type"
                    }, relation_type=RelationType(data.get("type", "knows"))))
        
        if direction in ("in", "both"):
            for source, _, data in self.graph.in_edges(node_id, data=True):
                if relation_type is None or data.get("type") == relation_type.value:
                    relations.append(KnowledgeRelation(**{
                        k: v for k, v in data.items()
                        if k != "type"
                    }, relation_type=RelationType(data.get("type", "knows"))))
        
        return relations
    
    def get_neighbors(
        self,
        node_id: str,
        node_types: Optional[List[NodeType]] = None,
        relation_types: Optional[List[RelationType]] = None
    ) -> List[Tuple[KnowledgeNode, RelationType]]:
        """获取邻居节点"""
        neighbors = []
        
        for _, target, data in self.graph.out_edges(node_id, data=True):
            if target in self.nodes:
                neighbor = self.nodes[target]
                rel_type = RelationType(data.get("type", "knows"))
                
                # 过滤
                if node_types and neighbor.node_type not in node_types:
                    continue
                if relation_types and rel_type not in relation_types:
                    continue
                
                neighbors.append((neighbor, rel_type))
        
        return neighbors
    
    # ========== 查询操作 ==========
    
    def find_path(
        self,
        source_id: str,
        target_id: str,
        max_length: int = 3
    ) -> List[List[str]]:
        """查找两个节点之间的路径"""
        try:
            return list(nx.all_simple_paths(
                self.graph, source_id, target_id, cutoff=max_length
            ))
        except nx.NetworkXNoPath:
            return []
    
    def find_shortest_path(self, source_id: str, target_id: str) -> Optional[List[str]]:
        """查找最短路径"""
        try:
            return nx.shortest_path(self.graph, source_id, target_id)
        except nx.NetworkXNoPath:
            return None
    
    def get_subgraph(
        self,
        node_ids: List[str],
        include_relations: bool = True
    ) -> nx.MultiDiGraph:
        """获取子图"""
        return self.graph.subgraph(node_ids).copy()
    
    def query_by_keyword(self, keyword: str) -> List[KnowledgeNode]:
        """按关键词搜索节点"""
        keyword_lower = keyword.lower()
        results = []
        
        for node in self.nodes.values():
            if (keyword_lower in node.name.lower() or
                keyword_lower in node.description.lower()):
                results.append(node)
        
        return results
    
    # ========== 分析操作 ==========
    
    def get_centrality(self) -> Dict[str, float]:
        """计算节点中心性"""
        return nx.degree_centrality(self.graph)
    
    def get_communities(self) -> List[List[str]]:
        """检测社区/派系"""
        try:
            # 无向图版本用于社区检测
            undirected = self.graph.to_undirected()
            communities = nx.community.louvain_communities(undirected)
            return [list(c) for c in communities]
        except:
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取图谱统计"""
        return {
            "node_count": self.graph.number_of_nodes(),
            "edge_count": self.graph.number_of_edges(),
            "node_types": {
                nt.value: len(nodes) 
                for nt, nodes in self._node_types_index.items()
            },
            "avg_degree": sum(dict(self.graph.degree()).values()) / max(1, self.graph.number_of_nodes())
        }
    
    # ========== 序列化 ==========
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "nodes": {
                nid: node.to_dict() 
                for nid, node in self.nodes.items()
            },
            "edges": [
                {"source": u, "target": v, **data}
                for u, v, data in self.graph.edges(data=True)
            ]
        }
    
    def to_json(self) -> str:
        """序列化为JSON"""
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    def save(self, path: Path):
        """保存到文件"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())
    
    @classmethod
    def load(cls, path: Path) -> "KnowledgeGraph":
        """从文件加载"""
        kg = cls()
        
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # 加载节点
        for nid, node_data in data.get("nodes", {}).items():
            node = KnowledgeNode(
                id=nid,
                node_type=NodeType(node_data["type"]),
                name=node_data["name"],
                description=node_data.get("description", ""),
                properties=node_data.get("properties", {})
            )
            kg.add_node(node)
        
        # 加载边
        for edge_data in data.get("edges", []):
            rel = KnowledgeRelation(
                source=edge_data["source"],
                target=edge_data["target"],
                relation_type=RelationType(edge_data.get("type", "knows")),
                weight=edge_data.get("weight", 1.0),
                description=edge_data.get("description", ""),
                properties=edge_data.get("properties", {})
            )
            kg.add_relation(rel)
        
        return kg
