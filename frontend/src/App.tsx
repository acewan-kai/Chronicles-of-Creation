import React, { useState, useEffect } from 'react';
import { WorldGraph } from './components/WorldGraph';
import { EventTimeline } from './components/EventTimeline';
import { TimelineControls } from './components/TimelineControls';
import { WorldMap } from './components/WorldMap';
import { AgentList } from './components/AgentList';
import { MetricsPanel } from './components/MetricsPanel';
import { OnboardingGuide } from './components/OnboardingGuide';
import { CreateWorldModal } from './components/CreateWorldModal';
import { api, connectWebSocket, World, Event, Agent, Location, NpcPosition, WsMessage } from './api';

function App() {
  const [worldId, setWorldId] = useState<string>('');
  const [worlds, setWorlds] = useState<World[]>([]);
  const [activeTab, setActiveTab] = useState<'graph' | 'timeline' | 'map' | 'timeline-controls'>('graph');
  const [isSimulating, setIsSimulating] = useState(false);
  const [events, setEvents] = useState<Event[]>([]);
  const [metrics, setMetrics] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [apiVersion, setApiVersion] = useState<string>('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [worldData, setWorldData] = useState<World | null>(null);
  const [npcPositions, setNpcPositions] = useState<NpcPosition[]>([]);

  // 加载世界列表
  useEffect(() => {
    loadWorlds();
  }, []);

  // 加载初始数据（非模拟时）
  useEffect(() => {
    if (worldId && !isSimulating) {
      loadData();
    }
  }, [worldId]);

  // WebSocket 实时连接（模拟运行时）
  useEffect(() => {
    if (!isSimulating || !worldId) return;

    let wsRef: WebSocket | null = null;
    let eventSeq = 0;

    const onMessage = (msg: WsMessage) => {
      switch (msg.type) {
        case 'NEW_EVENT': {
          const ev: Event = {
            id: ++eventSeq,
            turn: msg.data.turn,
            actor: msg.data.actor,
            action: msg.data.action,
            target: msg.data.target,
            location: msg.data.location,
            action_type: msg.data.action_type,
            score: msg.data.score,
            world_mood: msg.data.world_mood,
            timestamp: new Date().toISOString(),
          };
          setEvents((prev: Event[]) => [...prev.slice(-299), ev]);
          break;
        }
        case 'TURN_COMPLETE': {
          setMetrics({
            current_turn: msg.data.turn,
            total_events: msg.data.event_count,
            success_rate: `${msg.data.success_rate || 0}%`,
            success_count: msg.data.success_count,
            npc_count: msg.data.npc_count,
            total_npcs_alive: msg.data.total_npcs_alive,
            interactions: msg.data.interactions,
            story_moments: msg.data.story_moments,
            avg_delay: msg.data.avg_delay,
            go_status: msg.data.go_status,
            world_mood: msg.data.world_mood,
            budget: msg.data.budget,
            behavior: msg.data.behavior,
          });
          setWorldData((prev: World | null) => ({
            ...prev,
            agents: msg.data.agents,
            graph_edges: msg.data.graph_edges,
          }));
          break;
        }
        case 'NPC_POSITION': {
          setNpcPositions(msg.data.npcs || []);
          break;
        }
        case 'STATUS_CHANGE': {
          if (msg.data.status === 'stopped') {
            setIsSimulating(false);
          }
          break;
        }
      }
    };

    wsRef = connectWebSocket(worldId, onMessage);

    return () => {
      if (wsRef && wsRef.readyState === WebSocket.OPEN) {
        wsRef.close();
      }
    };
  }, [isSimulating, worldId]);

  const loadWorlds = async () => {
    try {
      const data = await api.getInfo();
      setApiVersion(data.version || '0.1.0');

      // 尝试获取世界列表
      let worldsData: World[] = [];
      try {
        worldsData = await api.getWorlds();
        setWorlds(worldsData);
        if (worldsData.length > 0) {
          setWorldId(worldsData[0].id);
        }
      } catch {
        console.warn('Worlds API not implemented');
      }
      // 无世界时自动弹出创建弹窗
      if (worldsData.length === 0) {
        setShowCreateModal(true);
      }
      setLoading(false);
    } catch (err: any) {
      setError(err.message || '无法连接到服务器');
      setLoading(false);
    }
  };

  const handleWorldCreated = (newWorldId: string) => {
    setShowCreateModal(false);
    setWorldId(newWorldId);
    // 重新加载世界列表以获取新世界
    api.getWorlds().then(data => {
      setWorlds(data);
    }).catch(() => {});
  };

  const loadData = async () => {
    try {
      const [eventsData, metricsData, worldDetail] = await Promise.all([
        api.getEvents(worldId).catch(() => []),
        api.getMetrics(worldId).catch(() => null),
        api.getWorld(worldId).catch(() => null)
      ]);
      setEvents(eventsData);
      setMetrics(metricsData);
      setWorldData(worldDetail);
    } catch (err) {
      console.error('Failed to load data:', err);
    }
  };

  const startSimulation = async () => {
    setIsSimulating(true);
    try {
      await api.startSimulation(worldId);
    } catch (err) {
      console.error('Failed to start simulation:', err);
      setIsSimulating(false);
    }
  };

  const stopSimulation = async () => {
    setIsSimulating(false);
    try {
      await api.stopSimulation(worldId);
    } catch (err) {
      console.error('Failed to stop simulation:', err);
    }
  };

  // 加载状态
  if (loading) {
    return (
      <div className="app-loading">
        <div className="loading-spinner"></div>
        <p>正在连接服务器...</p>
      </div>
    );
  }

  // 错误状态
  if (error) {
    return (
      <div className="app-error">
        <h2>连接失败</h2>
        <p>{error}</p>
        <p className="error-hint">请确保后端服务正在运行（端口 8000）</p>
        <button onClick={loadWorlds} className="btn btn-primary">
          重试连接
        </button>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-title">
          <h1>沉浸式AI小说创作平台</h1>
          <span className="api-version">API v{apiVersion}</span>
        </div>
        <div className="header-actions">
          <select
            value={worldId}
            onChange={(e) => setWorldId(e.target.value)}
            className="world-select"
          >
            {worlds.map(world => (
              <option key={world.id} value={world.id}>
                {world.name}
              </option>
            ))}
          </select>

          <button
            onClick={() => setShowCreateModal(true)}
            className="btn btn-secondary"
            title="创建新世界"
          >
            + 创建世界
          </button>

          {isSimulating ? (
            <button onClick={stopSimulation} className="btn btn-danger">
              <span className="btn-icon">⏹</span>
              停止模拟
            </button>
          ) : (
            <button onClick={startSimulation} className="btn btn-primary">
              <span className="btn-icon">▶</span>
              开始模拟
            </button>
          )}
        </div>
      </header>

      <main className="app-main">
        <aside className="sidebar">
          <MetricsPanel metrics={metrics} />
          <AgentList agents={worldData?.agents || []} events={events} />
        </aside>

        <div className="content">
          <nav className="tab-nav">
            <button
              className={`tab-btn ${activeTab === 'graph' ? 'active' : ''}`}
              onClick={() => setActiveTab('graph')}
            >
              世界图谱
            </button>
            <button
              className={`tab-btn ${activeTab === 'timeline-controls' ? 'active' : ''}`}
              onClick={() => setActiveTab('timeline-controls')}
            >
              时间线
            </button>
            <button
              className={`tab-btn ${activeTab === 'timeline' ? 'active' : ''}`}
              onClick={() => setActiveTab('timeline')}
            >
              事件列表
            </button>
            <button
              className={`tab-btn ${activeTab === 'map' ? 'active' : ''}`}
              onClick={() => setActiveTab('map')}
            >
              世界地图
            </button>
          </nav>

          <div className="tab-content">
            {events.length === 0 && !isSimulating && activeTab !== 'map' ? (
              <OnboardingGuide onStart={startSimulation} />
            ) : activeTab === 'graph' ? (
              <WorldGraph
                worldData={worldData}
                events={events}
                isSimulating={isSimulating}
              />
            ) : activeTab === 'timeline-controls' ? (
              <TimelineControls
                events={events}
                currentTurn={metrics?.current_turn ?? 0}
                worldId={worldId}
                isSimulating={isSimulating}
              />
            ) : activeTab === 'map' ? (
              <WorldMap
                worldId={worldId}
                locations={worldData?.locations || []}
                events={events}
                isSimulating={isSimulating}
                npcPositions={npcPositions}
              />
            ) : (
              <EventTimeline events={events} />
            )}
          </div>
        </div>
      </main>

      {isSimulating && (
        <div className="simulation-indicator">
          <span className="pulse"></span>
          模拟运行中
        </div>
      )}

      {showCreateModal && (
        <CreateWorldModal
          onCreated={handleWorldCreated}
          onClose={() => setShowCreateModal(false)}
        />
      )}
    </div>
  );
}

export default App;
