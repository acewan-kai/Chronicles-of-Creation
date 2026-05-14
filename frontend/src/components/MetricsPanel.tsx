import React from 'react';

interface MetricsPanelProps {
  metrics: any;
}

export const MetricsPanel: React.FC<MetricsPanelProps> = ({ metrics }) => {
  if (!metrics) {
    return (
      <div className="metrics-panel">
        <h3>运行指标</h3>
        <p className="empty-message">暂无数据</p>
      </div>
    );
  }

  const moodEmoji: Record<string, string> = {
    "平静": "😌", "暗流涌动": "🌊", "紧张": "😰", "危机四伏": "⚠️",
    "风雨欲来": "🌧️", "动荡": "🔥", "混乱": "💥", "希望萌芽": "🌱",
    "重整旗鼓": "⚔️", "新秩序": "🏛️",
  };

  const getStatusClass = (value: number, threshold: number) => {
    if (value >= threshold) return 'status-good';
    if (value >= threshold * 0.7) return 'status-warning';
    return 'status-bad';
  };

  return (
    <div className="metrics-panel">
      <h3>运行指标</h3>
      
      {metrics.world_mood && (
        <div className="world-mood-indicator">
          {moodEmoji[metrics.world_mood] || '🎭'} 世界氛围: {metrics.world_mood}
          {metrics.current_turn && ` · 第${metrics.current_turn}回合`}
        </div>
      )}

      <div className="metrics-grid">
        <div className="metric-card">
          <div className="metric-value">{metrics.total_events || 0}</div>
          <div className="metric-label">总事件</div>
        </div>
        
        <div className="metric-card">
          <div className="metric-value">
            {metrics.success_rate || '0%'}
          </div>
          <div className="metric-label">成功率</div>
        </div>
        
        <div className="metric-card">
          <div className="metric-value">
            {metrics.interactions || 0}
          </div>
          <div className="metric-label">跨角色互动</div>
        </div>
        
        <div className="metric-card highlight">
          <div className="metric-value">
            {metrics.story_moments || 0}
          </div>
          <div className="metric-label">故事时刻</div>
        </div>
      </div>

      <div className="metrics-details">
        <h4>验收标准</h4>
        <ul className="criteria-list">
          <li className={getStatusClass(metrics.total_npcs_alive || 0, 10)}>
            <span className="criteria-icon">
              {metrics.total_npcs_alive >= 10 ? '✓' : '✗'}
            </span>
            <span>10个NPC存活100回合</span>
            <span className="criteria-value">
              {metrics.total_npcs_alive || 0}/10
            </span>
          </li>
          <li className={getStatusClass(metrics.interactions || 0, 3)}>
            <span className="criteria-icon">
              {metrics.interactions >= 3 ? '✓' : '✗'}
            </span>
            <span>非预设互动≥3</span>
            <span className="criteria-value">
              {metrics.interactions || 0}
            </span>
          </li>
          <li className={getStatusClass(metrics.story_moments || 0, 1)}>
            <span className="criteria-icon">
              {metrics.story_moments >= 1 ? '✓' : '✗'}
            </span>
            <span>故事感时刻≥1</span>
            <span className="criteria-value">
              {metrics.story_moments || 0}
            </span>
          </li>
          <li className={getStatusClass(15 - (metrics.avg_delay || 0), 15)}>
            <span className="criteria-icon">
              {(metrics.avg_delay || 999) < 15 ? '✓' : '✗'}
            </span>
            <span>单回合延迟&lt;15s</span>
            <span className="criteria-value">
              {(metrics.avg_delay || 0).toFixed(2)}s
            </span>
          </li>
        </ul>
      </div>

      <div className="metrics-status">
        <div className={`status-badge ${metrics.go_status ? 'go' : 'no-go'}`}>
          {metrics.go_status ? 'GO' : 'NO-GO'}
        </div>
        <span className="status-text">
          {metrics.go_status ? '通过验收标准' : '未通过验收标准'}
        </span>
      </div>

      {metrics.budget && (
        <div className="budget-panel">
          <h4>Lorebook 预算</h4>
          <div className="budget-bar-wrapper">
            <div className="budget-bar-label">
              {metrics.budget.total_used}/{metrics.budget.total_budget} 字符
            </div>
            <div className="budget-bar">
              <div
                className="budget-bar-fill"
                style={{ width: `${Math.min(metrics.budget.usage_pct, 100)}%` }}
              />
            </div>
            <div className="budget-bar-pct">{metrics.budget.usage_pct}%</div>
          </div>
          {metrics.budget.agents && (
            <ul className="budget-agent-list">
              {metrics.budget.agents.slice(0, 5).map((a: any) => (
                <li key={a.agent_id} className="budget-agent-item">
                  <span className="budget-agent-name">{a.name}</span>
                  <span className="budget-agent-bar">
                    <span
                      className="budget-agent-fill"
                      style={{ width: `${Math.min(a.usage_pct, 100)}%` }}
                    />
                  </span>
                  <span className="budget-agent-pct">{a.usage_pct}%</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {metrics.behavior && metrics.behavior.total_evaluations > 0 && (
        <div className="budget-panel">
          <h4>行为一致性</h4>
          <div className="budget-bar-wrapper">
            <div className="budget-bar-label">
              综合 {metrics.behavior.avg_score?.toFixed(2)}
            </div>
            <div className="budget-bar">
              <div
                className="budget-bar-fill"
                style={{ width: `${(metrics.behavior.avg_score || 0) * 100}%` }}
              />
            </div>
            <div className="budget-bar-pct">
              评测{metrics.behavior.total_evaluations}次
            </div>
          </div>
          <div className="behavior-breakdown">
            <span className="behavior-tag consistent">
              一致 {metrics.behavior.consistent_pct}%
            </span>
            <span className="behavior-tag divergent">
              偏离 {metrics.behavior.divergent_pct}%
            </span>
          </div>
          {metrics.behavior.agents && (
            <ul className="budget-agent-list">
              {metrics.behavior.agents
                .sort((a: any, b: any) => b.avg_score - a.avg_score)
                .slice(0, 5)
                .map((a: any) => (
                  <li key={a.agent_id} className="budget-agent-item">
                    <span className="budget-agent-name">{a.agent_id}</span>
                    <span className="budget-agent-bar">
                      <span
                        className="budget-agent-fill"
                        style={{ width: `${a.avg_score * 100}%` }}
                      />
                    </span>
                    <span className="budget-agent-pct">
                      {a.avg_score?.toFixed(2)}
                      {a.recent_trend === 'up' ? ' ↑' : a.recent_trend === 'down' ? ' ↓' : ''}
                    </span>
                  </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
};
