import React from 'react';

interface AgentListProps {
  agents: any[];
}

export const AgentList: React.FC<AgentListProps> = ({ agents }) => {
  // 统计每个角色的事件数
  const agentStats = agents.reduce((acc, event) => {
    if (!acc[event.actor]) {
      acc[event.actor] = { count: 0, interactions: 0, storyMoments: 0 };
    }
    acc[event.actor].count++;
    if (event.action_type === 'interaction') acc[event.actor].interactions++;
    if (event.action_type === 'story_moment') acc[event.actor].storyMoments++;
    return acc;
  }, {} as Record<string, { count: number; interactions: number; storyMoments: number }>);

  const sortedAgents = Object.entries(agentStats)
    .sort((a, b) => b[1].count - a[1].count);

  return (
    <div className="agent-list">
      <h3>角色活跃度</h3>
      
      {sortedAgents.length === 0 ? (
        <p className="empty-message">暂无数据</p>
      ) : (
        <div className="agent-items">
          {sortedAgents.map(([name, stats]) => (
            <div key={name} className="agent-item">
              <div className="agent-name">
                <span className="agent-avatar">{name[0]}</span>
                <span>{name}</span>
              </div>
              <div className="agent-stats">
                <span className="stat">
                  <span className="stat-value">{stats.count}</span>
                  <span className="stat-label">事件</span>
                </span>
                <span className="stat interaction">
                  <span className="stat-value">{stats.interactions}</span>
                  <span className="stat-label">互动</span>
                </span>
                <span className="stat story">
                  <span className="stat-value">{stats.storyMoments}</span>
                  <span className="stat-label">故事</span>
                </span>
              </div>
              <div className="agent-bar">
                <div 
                  className="bar-fill"
                  style={{ 
                    width: `${(stats.count / Math.max(...sortedAgents.map(a => a[1].count))) * 100}%` 
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
