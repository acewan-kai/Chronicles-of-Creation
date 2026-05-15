import React, { useState, useEffect, useCallback } from 'react';
import { api, Agent } from '../api';

interface DescendContext {
  agent_id: string;
  agent_name: string;
  identity: string;
  personality: string;
  current_location: string;
  location_name: string;
  memory_snapshot: Array<{ type: string; content: string; importance: number }>;
  relationship_snapshot: Record<string, { type: string; weight: number }>;
  world_mood: string;
  active_goals: string[];
  entered_at: string;
  entered_turn: number;
}

interface DescendAction {
  action_id: string;
  action_type: string;
  content: string;
  target?: string;
  impact: string;
  options_available: number;
  turn: number;
}

interface DescendOption {
  id: string;
  icon?: string;
  label: string;
  type: string;
  description: string;
}

interface DescentModeProps {
  worldId: string;
  agents: Agent[];
  isSimulating: boolean;
}

export const DescentMode: React.FC<DescentModeProps> = ({ worldId, agents, isSimulating }) => {
  const [selectedAgentId, setSelectedAgentId] = useState<string>('');
  const [isActive, setIsActive] = useState(false);
  const [context, setContext] = useState<DescendContext | null>(null);
  const [options, setOptions] = useState<DescendOption[]>([]);
  const [actions, setActions] = useState<DescendAction[]>([]);
  const [actionContent, setActionContent] = useState('');
  const [situation, setSituation] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'actions' | 'memory' | 'relations'>('actions');

  // 加载降临状态
  const loadStatus = useCallback(async () => {
    if (!selectedAgentId) return;
    try {
      const data = await api.getDescendStatus(worldId, selectedAgentId);
      if (data.status === 'active' && data.context) {
        setIsActive(true);
        setContext(data.context);
        setActions(data.recent_actions || []);
      } else {
        setIsActive(false);
        setContext(null);
        setActions([]);
      }
    } catch {
      setIsActive(false);
    }
  }, [worldId, selectedAgentId]);

  useEffect(() => {
    if (selectedAgentId) {
      loadStatus();
    }
  }, [selectedAgentId, loadStatus]);

  // 加载选项
  const loadOptions = async (sit?: string) => {
    if (!selectedAgentId) return;
    try {
      const data = await api.getDescendOptions(worldId, selectedAgentId, sit || situation);
      setOptions(data.options || []);
    } catch (err: any) {
      setError(err.message || '加载选项失败');
    }
  };

  // 降临
  const handleDescend = async () => {
    if (!selectedAgentId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.descendToAgent(worldId, selectedAgentId);
      setIsActive(true);
      setContext(data.context);
      setActions([]);
      await loadOptions();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || '降临失败');
    } finally {
      setLoading(false);
    }
  };

  // 退出降临
  const handleExit = async () => {
    if (!selectedAgentId) return;
    setLoading(true);
    setError(null);
    try {
      await api.exitDescend(worldId, selectedAgentId);
      setIsActive(false);
      setContext(null);
      setOptions([]);
      setActions([]);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || '退出失败');
    } finally {
      setLoading(false);
    }
  };

  // 执行行动
  const handleAct = async (option: DescendOption) => {
    if (!selectedAgentId) return;
    setError(null);
    try {
      const data = await api.descendAct(
        worldId,
        selectedAgentId,
        option.type,
        option.label,
        undefined,
      );
      setActions((prev) => [...prev, data.action].slice(-20));
      // 行动后刷新选项
      await loadOptions();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || '行动失败');
    }
  };

  // 自定义行动
  const handleCustomAct = async () => {
    if (!selectedAgentId || !actionContent.trim()) return;
    setError(null);
    try {
      const data = await api.descendAct(
        worldId,
        selectedAgentId,
        'interact',
        actionContent.trim(),
        undefined,
      );
      setActions((prev) => [...prev, data.action].slice(-20));
      setActionContent('');
      await loadOptions();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || '行动失败');
    }
  };

  // 获取关系列表
  const getRelations = (): Array<{ name: string; type: string; weight: number }> => {
    if (!context?.relationship_snapshot) return [];
    return Object.entries(context.relationship_snapshot).map(([name, info]) => ({
      name,
      type: info.type,
      weight: info.weight,
    }));
  };

  // 关系类型颜色
  const relationColor = (type: string) => {
    switch (type) {
      case 'friend':
      case 'ally':
      case '好友':
      case '盟友':
        return '#22c55e';
      case 'enemy':
      case '敌对':
        return '#ef4444';
      case 'knows':
        return '#3b82f6';
      default:
        return '#94a3b8';
    }
  };

  const relationLabel = (type: string) => {
    switch (type) {
      case 'friend':
        return '好友';
      case 'ally':
        return '盟友';
      case 'enemy':
        return '敌对';
      case 'knows':
        return '相识';
      default:
        return type;
    }
  };

  if (!worldId) {
    return <div className="descent-mode"><p className="text-muted">请先选择世界</p></div>;
  }

  return (
    <div className="descent-mode">
      {/* NPC 选择器 */}
      <div className="descent-header">
        <select
          value={selectedAgentId}
          onChange={(e) => setSelectedAgentId(e.target.value)}
          className="agent-select"
          disabled={isActive}
        >
          <option value="">-- 选择降临角色 --</option>
          {agents
            .filter((a) => a.is_alive !== false)
            .map((agent) => (
              <option key={agent.agent_id} value={agent.agent_id}>
                {agent.config.name} — {agent.config.identity}
              </option>
            ))}
        </select>

        {isActive ? (
          <button onClick={handleExit} className="btn btn-danger" disabled={loading}>
            {loading ? '退出中...' : '退出降临'}
          </button>
        ) : (
          <button
            onClick={handleDescend}
            className="btn btn-primary"
            disabled={!selectedAgentId || loading || !isSimulating}
          >
            {loading ? '降临中...' : '降临'}
          </button>
        )}
      </div>

      {error && <div className="descent-error">{error}</div>}

      {!isSimulating && (
        <div className="descent-hint">启动模拟后可降临到NPC视角</div>
      )}

      {/* 降临上下文面板 */}
      {isActive && context && (
        <div className="descent-context">
          <div className="context-header">
            <div className="context-identity">
              <h3>{context.agent_name}</h3>
              <span className="identity-tag">{context.identity}</span>
              <span className="personality-tag">{context.personality}</span>
            </div>
            <div className="context-location">
              📍 {context.location_name}
              {context.world_mood && (
                <span className="world-mood"> | 世界氛围: {context.world_mood}</span>
              )}
            </div>
            {context.active_goals.length > 0 && (
              <div className="context-goals">
                🎯 目标: {context.active_goals.join(' / ')}
              </div>
            )}
          </div>

          {/* 子标签切换 */}
          <div className="descent-tabs">
            <button
              className={`tab-btn-sm ${activeTab === 'actions' ? 'active' : ''}`}
              onClick={() => setActiveTab('actions')}
            >
              行动 ({actions.length})
            </button>
            <button
              className={`tab-btn-sm ${activeTab === 'memory' ? 'active' : ''}`}
              onClick={() => setActiveTab('memory')}
            >
              记忆 ({context.memory_snapshot?.length || 0})
            </button>
            <button
              className={`tab-btn-sm ${activeTab === 'relations' ? 'active' : ''}`}
              onClick={() => setActiveTab('relations')}
            >
              关系 ({Object.keys(context.relationship_snapshot || {}).length})
            </button>
          </div>

          <div className="descent-panel">
            {activeTab === 'actions' && (
              <div className="action-history">
                {actions.length === 0 ? (
                  <p className="text-muted">暂无行动记录</p>
                ) : (
                  actions.map((act) => (
                    <div key={act.action_id} className="action-item">
                      <span className={`action-type-badge ${act.action_type}`}>
                        {act.action_type === 'dialogue' ? '💬' : act.action_type === 'observe' ? '👁' : '⚡'}
                      </span>
                      <span className="action-content">{act.content}</span>
                      {act.target && <span className="action-target">→ {act.target}</span>}
                      <span className="action-impact">{act.impact}</span>
                    </div>
                  ))
                )}
              </div>
            )}

            {activeTab === 'memory' && (
              <div className="memory-list">
                {(!context.memory_snapshot || context.memory_snapshot.length === 0) ? (
                  <p className="text-muted">无记忆数据</p>
                ) : (
                  context.memory_snapshot.map((mem, i) => (
                    <div key={i} className="memory-item">
                      <span className="mem-type">{mem.type}</span>
                      <span className="mem-content">{mem.content}</span>
                      <span className="mem-importance" title="重要性">
                        {'★'.repeat(Math.ceil(mem.importance * 5))}
                      </span>
                    </div>
                  ))
                )}
              </div>
            )}

            {activeTab === 'relations' && (
              <div className="relation-list">
                {getRelations().length === 0 ? (
                  <p className="text-muted">无关系数据</p>
                ) : (
                  getRelations().map((rel, i) => (
                    <div key={i} className="relation-item">
                      <span
                        className="relation-dot"
                        style={{ backgroundColor: relationColor(rel.type) }}
                      />
                      <span className="relation-name">{rel.name}</span>
                      <span
                        className="relation-type"
                        style={{ color: relationColor(rel.type) }}
                      >
                        {relationLabel(rel.type)}
                      </span>
                      <span className="relation-weight">
                        亲密度: {Math.round(rel.weight * 100)}%
                      </span>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* 对话选项树 */}
      {isActive && (
        <div className="descent-options">
          <h4>可选行动</h4>

          {/* 情境描述 */}
          <div className="situation-input">
            <input
              type="text"
              value={situation}
              onChange={(e) => setSituation(e.target.value)}
              placeholder="描述当前情境（可选）..."
              className="input-text"
            />
            <button
              onClick={() => loadOptions()}
              className="btn btn-sm btn-secondary"
              disabled={loading}
            >
              刷新选项
            </button>
          </div>

          <div className="options-grid">
            {options.map((opt) => (
              <button
                key={opt.id}
                className="option-card"
                onClick={() => handleAct(opt)}
                disabled={loading}
              >
                <span className="option-icon">{opt.icon || '💬'}</span>
                <span className="option-label">{opt.label}</span>
                <span className="option-type">{opt.type}</span>
              </button>
            ))}
          </div>

          {/* 自定义行动 */}
          <div className="custom-action">
            <input
              type="text"
              value={actionContent}
              onChange={(e) => setActionContent(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleCustomAct()}
              placeholder="输入自定义行动..."
              className="input-text"
            />
            <button
              onClick={handleCustomAct}
              className="btn btn-sm btn-primary"
              disabled={!actionContent.trim() || loading}
            >
              执行
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default DescentMode;
