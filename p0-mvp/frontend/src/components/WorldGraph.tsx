import React, { useEffect, useRef } from 'react';
import Cytoscape from 'cytoscape';

interface WorldGraphProps {
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

export const WorldGraph: React.FC<WorldGraphProps> = ({ events, isSimulating }) => {
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
    if (!cyRef.current || events.length === 0) return;

    const { nodes, edges } = buildGraphData(events);
    
    cyRef.current.elements().remove();
    cyRef.current.add(nodes);
    cyRef.current.add(edges);
    
    cyRef.current.layout({
      name: 'cose',
      animate: true,
      animationDuration: 500,
    }).run();
  }, [events]);

  const buildGraphData = (events: any[]) => {
    const nodes: any[] = [];
    const edges: any[] = [];
    const nodeSet = new Set<string>();

    // 添加基础节点
    const baseNodes = [
      { id: 'village', name: '雾隐村', type: 'location' },
      { id: 'teahouse', name: '茶馆', type: 'location' },
      { id: 'dock', name: '码头', type: 'location' },
      { id: 'temple', name: '祠堂', type: 'location' },
      { id: 'mayor', name: '李沉渊', type: 'character' },
      { id: 'blacksmith', name: '张铁柱', type: 'character' },
      { id: 'doctor', name: '沈墨白', type: 'character' },
    ];

    baseNodes.forEach(node => {
      if (!nodeSet.has(node.id)) {
        nodes.push(node);
        nodeSet.add(node.id);
      }
    });

    // 从事件中提取关系
    const interactions: Map<string, { count: number; type: string }> = new Map();

    events.slice(-50).forEach((event: any) => {
      if (event.target) {
        const key = `${event.actor}_${event.target}`;
        const existing = interactions.get(key) || { count: 0, type: 'interaction' };
        existing.count++;
        interactions.set(key, existing);
      }
    });

    // 添加边
    interactions.forEach((data, key) => {
      const [source, target] = key.split('_');
      if (nodeSet.has(source) && nodeSet.has(target)) {
        edges.push({
          data: {
            id: `edge_${key}`,
            source,
            target,
            type: 'interaction',
            label: `${data.count}次互动`,
          },
        });
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
