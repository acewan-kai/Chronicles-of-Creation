import React, { useState, useEffect } from 'react';
import { WorldGraph } from './components/WorldGraph';
import { EventTimeline } from './components/EventTimeline';
import { AgentList } from './components/AgentList';
import { MetricsPanel } from './components/MetricsPanel';
import { OnboardingGuide } from './components/OnboardingGuide';
import { api, World, Event } from './api';

function App() {
  const [worldId, setWorldId] = useState<string>('foggy-village');
  const [worlds, setWorlds] = useState<World[]>([]);
  const [activeTab, setActiveTab] = useState<'graph' | 'timeline'>('graph');
  const [isSimulating, setIsSimulating] = useState(false);
  const [events, setEvents] = useState<Event[]>([]);
  const [metrics, setMetrics] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [apiVersion, setApiVersion] = useState<string>('');

  // 加载世界列表
  useEffect(() => {
    loadWorlds();
  }, []);

  // 加载数据
  useEffect(() => {
    loadData();
    
    // 轮询更新
    const interval = setInterval(() => {
      if (isSimulating) {
        loadData();
      }
    }, 5000);
    
    return () => clearInterval(interval);
  }, [worldId, isSimulating]);

  const loadWorlds = async () => {
    try {
      const data = await api.getInfo();
      setApiVersion(data.version || '0.1.0');
      
      // 尝试获取世界列表
      try {
        const worldsData = await api.getWorlds();
        setWorlds(worldsData);
        if (worldsData.length > 0 && !worldsData.find((w: World) => w.id === worldId)) {
          setWorldId(worldsData[0].id);
        }
      } catch {
        // API尚未实现，使用默认世界
        setWorlds([
          { id: 'foggy-village', name: '雾隐村', description: '一个被迷雾笼罩的神秘村落' }
        ]);
      }
      setLoading(false);
    } catch (err) {
      setError('无法连接到服务器');
      setLoading(false);
    }
  };

  const loadData = async () => {
    try {
      const [eventsData, metricsData] = await Promise.all([
        api.getEvents(worldId).catch(() => []),
        api.getMetrics(worldId).catch(() => null)
      ]);
      setEvents(eventsData);
      setMetrics(metricsData);
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
        <p className="error-hint">请确保后端服务正在运行</p>
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
          <AgentList agents={events} />
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
              className={`tab-btn ${activeTab === 'timeline' ? 'active' : ''}`}
              onClick={() => setActiveTab('timeline')}
            >
              事件时间线
            </button>
          </nav>

          <div className="tab-content">
            {events.length === 0 && !isSimulating ? (
              <OnboardingGuide onStart={startSimulation} />
            ) : activeTab === 'graph' ? (
              <WorldGraph 
                events={events} 
                isSimulating={isSimulating}
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
    </div>
  );
}

export default App;
