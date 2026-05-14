import React, { useEffect, useRef } from 'react';
import Cytoscape from 'cytoscape';
import { World, Agent, Location, GraphEdge } from '../api';

interface WorldGraphProps {
  worldData: World | null;
  events: any[];
  isSimulating: boolean;
}

// 预设节点样式
const nodeStyles = {
  character: {
    backgroundColor: '#4CAF50',
    label: 'data(name)',
    shape: 'ellipse',
  },
  location: {
    backgroundColor: '#2196F3',
    label: 'data(name)',
    shape: 'rectangle',
  },
  faction: {
    backgroundColor: '#FF9800',
    label: 'data(name)',
    shape: 'diamond',
  },
};

export const WorldGraph: React.FC<WorldGraphProps> = ({ worldData, events, isSimulating }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Cytoscape.Core | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // 初始化 Cytoscape
    cyRef.current = Cytoscape({
      container: containerRef.current,
      style: [
        {
          selector: 'node',
          style: {
            'label': 'data(name)',
            'text-valign': 'bottom',
            'text-margin-y': 8,
            'font-size': 12,
            'background-color': '#666',
            'border-width': 2,
            'border-color': '#fff',
          },
        },
        {
          selector: 'node[type="character"]',
          style: {
            'background-color': '#4CAF50',
            'shape': 'ellipse',
          },
        },
        {
          selector: 'node[type="location"]',
          style: {
            'background-color': '#2196F3',
            'shape': 'rectangle',
          },
        },
        {
          selector: 'node[type="faction"]',
          style: {
            'background-color': '#FF9800',
            'shape': 'diamond',
          },
        },
        {
          selector: 'edge',
          style: {
            'width': 2,
            'line-color': '#aaa',
            'target-arrow-color': '#aaa',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
          },
        },
        {
          selector: 'edge[type="friend"]',
          style: {
            'line-color': '#4CAF50',
            'target-arrow-color': '#4CAF50',
          },
        },
        {
          selector: 'edge[type="enemy"]',
          style: {
            'line-color': '#f44336',
            'target-arrow-color': '#f44336',
            'line-style': 'dashed',
          },
        },
        {
          selector: 'edge[type="interaction"]',
          style: {
            'line-color': '#9C27B0',
            'target-arrow-color': '#9C27B0',
            'width': 3,
          },
        },
        {
          selector: '.highlighted',
          style: {
            'border-width': 4,
            'border-color': '#FFD700',
          },
        },
      ],
      layout: {
        name: 'cose',
        animate: isSimulating,
        animationDuration: 500,
      },
      wheelSensitivity: 0.3,
      minZoom: 0.3,
      maxZoom: 3,
    });

    // 点击节点事件
    cyRef.current.on('tap', 'node', (evt) => {
      const node = evt.target;
      console.log('Node clicked:', node.data());
    });

    return () => {
      if (cyRef.current) {
        cyRef.current.destroy();
      }
    };
  }, []);

  // 更新图谱数据
  useEffect(() => {
    if (!cyRef.current) return;

    const { nodes, edges } = buildGraphData(events);

    if (nodes.length === 0) return;

    cyRef.current.elements().remove();
    cyRef.current.add(nodes);
    cyRef.current.add(edges);

    cyRef.current.layout({
      name: 'cose',
      animate: true,
      animationDuration: 500,
    }).run();
  }, [worldData, events]);

  const buildGraphData = (events: any[]) => {
    const nodes: any[] = [];
    const edges: any[] = [];
    const nodeSet = new Set<string>();
    const nodeNameMap = new Map<string, string>(); // id -> name mapping for event matching

    // 从 worldData 动态构建节点
    if (worldData) {
      // 添加地点节点
      (worldData.locations || []).forEach((loc: Location) => {
        if (!nodeSet.has(loc.id)) {
          nodes.push({ data: { id: loc.id, name: loc.name, type: 'location' } });
          nodeSet.add(loc.id);
          nodeNameMap.set(loc.id, loc.name);
          nodeNameMap.set(loc.name, loc.id);
        }
      });

      // 添加角色节点
      (worldData.agents || []).forEach((agent: Agent) => {
        const agentId = agent.agent_id;
        if (!nodeSet.has(agentId)) {
          nodes.push({ data: { id: agentId, name: agent.name || agent.config?.name, type: 'character' } });
          nodeSet.add(agentId);
          nodeNameMap.set(agentId, agent.name || agent.config?.name);
          nodeNameMap.set(agent.name || agent.config?.name, agentId);
        }
      });
    }

    // 从事件中提取关系
    const interactions: Map<string, { count: number; type: string }> = new Map();

    events.slice(-50).forEach((event: any) => {
      if (event.target) {
        const sourceId = nodeNameMap.get(event.actor) || event.actor;
        const targetId = nodeNameMap.get(event.target) || event.target;
        const key = `${sourceId}_${targetId}`;
        const existing = interactions.get(key) || { count: 0, type: 'interaction' };
        existing.count++;
        interactions.set(key, existing);
      }
    });

    // 添加事件互动边
    interactions.forEach((data, key) => {
      const [source, target] = key.split('_');
      if (nodeSet.has(source) && nodeSet.has(target)) {
        edges.push({
          data: {
            id: `evt_${key}`,
            source,
            target,
            type: 'interaction',
            label: `${data.count}次互动`,
          },
        });
      }
    });

    // 添加知识图谱关系边（friend/enemy/knows）
    (worldData.graph_edges || []).forEach((ge: GraphEdge) => {
      if (nodeSet.has(ge.source) && nodeSet.has(ge.target)) {
        const edgeId = `kg_${ge.source}_${ge.target}_${ge.type}`;
        // 避免与事件边重复
        if (!edges.some(e => e.data.id === edgeId)) {
          edges.push({
            data: {
              id: edgeId,
              source: ge.source,
              target: ge.target,
              type: ge.type,
              weight: ge.weight,
              label: `${ge.type} (${(ge.weight * 100).toFixed(0)}%)`,
            },
          });
        }
      }
    });

    return { nodes, edges };
  };

  return (
    <div className="world-graph">
      <div className="graph-toolbar">
        <button onClick={() => cyRef.current?.fit()} className="btn btn-sm">
          适应屏幕
        </button>
        <button onClick={() => cyRef.current?.zoom(1.2)} className="btn btn-sm">
          放大
        </button>
        <button onClick={() => cyRef.current?.zoom(0.8)} className="btn btn-sm">
          缩小
        </button>
      </div>
      <div ref={containerRef} className="graph-container" />
      <div className="graph-legend">
        <div className="legend-item">
          <span className="legend-dot" style={{ background: '#4CAF50' }} />
          <span>角色</span>
        </div>
        <div className="legend-item">
          <span className="legend-dot" style={{ background: '#2196F3' }} />
          <span>地点</span>
        </div>
        <div className="legend-item">
          <span className="legend-line" style={{ borderColor: '#4CAF50' }} />
          <span>友好</span>
        </div>
        <div className="legend-item">
          <span className="legend-line" style={{ borderColor: '#f44336', borderStyle: 'dashed' }} />
          <span>敌对</span>
        </div>
        <div className="legend-item">
          <span className="legend-line" style={{ borderColor: '#9C27B0', borderTopWidth: 3 }} />
          <span>互动</span>
        </div>
      </div>
    </div>
  );
};
