import React, { useState, useEffect } from 'react';
import { WorldGraph } from './components/WorldGraph';
import { EventTimeline } from './components/EventTimeline';
import { AgentList } from './components/AgentList';
import { MetricsPanel } from './components/MetricsPanel';
import { api } from './api';

function App() {
  const [worldId, setWorldId] = useState<string>('foggy-village');
  const [activeTab, setActiveTab] = useState<'graph' | 'timeline' | 'agents'>('graph');
  const [isSimulating, setIsSimulating] = useState(false);
  const [events, setEvents] = useState<any[]>([]);
  const [metrics, setMetrics] = useState<any>(null);

  useEffect(() => {
    // 加载初始数据
    loadData();
    
    // 轮询更新
    const interval = setInterval(() => {
      if (isSimulating) {
        loadData();
      }
    }, 5000);
    
    return () => clearInterval(interval);
  }, [worldId, isSimulating]);

  const loadData = async () => {
    try {
      const [eventsData, metricsData] = await Promise.all([
        api.getEvents(worldId),
        api.getMetrics(worldId)
      ]);
      setEvents(eventsData);
      setMetrics(metricsData);
    } catch (error) {
      console.error('Failed to load data:', error);
    }
  };

  const startSimulation = async () => {
    setIsSimulating(true);
    try {
      await api.startSimulation(worldId);
    } catch (error) {
      console.error('Failed to start simulation:', error);
      setIsSimulating(false);
    }
  };

  const stopSimulation = async () => {
    setIsSimulating(false);
    try {
      await api.stopSimulation(worldId);
    } catch (error) {
      console.error('Failed to stop simulation:', error);
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>沉浸式AI小说创作平台</h1>
        <div className="header-actions">
          <select 
            value={worldId} 
            onChange={(e) => setWorldId(e.target.value)}
            className="world-select"
          >
            <option value="foggy-village">雾隐村</option>
            <option value="martial-world">武侠世界</option>
            <option value="cultivation-realm">修仙界</option>
          </select>
          
          {isSimulating ? (
            <button onClick={stopSimulation} className="btn btn-danger">
              停止模拟
            </button>
          ) : (
            <button onClick={startSimulation} className="btn btn-primary">
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
            {activeTab === 'graph' && (
              <WorldGraph 
                events={events} 
                isSimulating={isSimulating}
              />
            )}
            {activeTab === 'timeline' && (
              <EventTimeline events={events} />
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
