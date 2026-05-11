import React, { useState } from 'react';
import dayjs from 'dayjs';

interface EventTimelineProps {
  events: any[];
}

export const EventTimeline: React.FC<EventTimelineProps> = ({ events }) => {
  const [filter, setFilter] = useState<string>('all');
  const [expandedEvent, setExpandedEvent] = useState<number | null>(null);

  const filteredEvents = events.filter((event) => {
    if (filter === 'all') return true;
    return event.action_type === filter;
  });

  const formatTime = (turn: number) => {
    const day = Math.floor(turn / 8) + 1;
    const hour = (turn % 8) * 3;
    return `第${day}天 ${hour.toString().padStart(2, '0')}:00`;
  };

  const getTypeBadge = (type: string) => {
    const badges: Record<string, { label: string; className: string }> = {
      normal: { label: '普通', className: 'badge-default' },
      interaction: { label: '互动', className: 'badge-interaction' },
      story_moment: { label: '故事', className: 'badge-story' },
    };
    const badge = badges[type] || badges.normal;
    return <span className={`badge ${badge.className}`}>{badge.label}</span>;
  };

  return (
    <div className="event-timeline">
      <div className="timeline-header">
        <h3>事件时间线</h3>
        <div className="timeline-filters">
          <button
            className={`filter-btn ${filter === 'all' ? 'active' : ''}`}
            onClick={() => setFilter('all')}
          >
            全部 ({events.length})
          </button>
          <button
            className={`filter-btn ${filter === 'interaction' ? 'active' : ''}`}
            onClick={() => setFilter('interaction')}
          >
            互动 ({events.filter(e => e.action_type === 'interaction').length})
          </button>
          <button
            className={`filter-btn ${filter === 'story_moment' ? 'active' : ''}`}
            onClick={() => setFilter('story_moment')}
          >
            故事 ({events.filter(e => e.action_type === 'story_moment').length})
          </button>
        </div>
      </div>

      <div className="timeline-list">
        {filteredEvents.length === 0 ? (
          <div className="timeline-empty">
            <p>暂无事件</p>
          </div>
        ) : (
          filteredEvents.map((event, index) => (
            <div
              key={index}
              className={`timeline-item ${event.action_type === 'story_moment' ? 'highlight' : ''}`}
              onClick={() => setExpandedEvent(expandedEvent === index ? null : index)}
            >
              <div className="timeline-marker">
                <span className="marker-dot" />
                {index < filteredEvents.length - 1 && <span className="marker-line" />}
              </div>
              
              <div className="timeline-content">
                <div className="timeline-meta">
                  <span className="timeline-time">
                    {formatTime(event.turn)}
                  </span>
                  <span className="timeline-location">{event.location}</span>
                  {getTypeBadge(event.action_type)}
                </div>
                
                <div className="timeline-actor">
                  <strong>{event.actor}</strong>
                  {event.target && (
                    <span className="timeline-target"> → {event.target}</span>
                  )}
                </div>
                
                <div className="timeline-action">
                  {expandedEvent === index ? (
                    <p className="action-full">{event.action}</p>
                  ) : (
                    <p className="action-preview">
                      {event.action.length > 100
                        ? event.action.slice(0, 100) + '...'
                        : event.action}
                    </p>
                  )}
                </div>

                {event.score && (
                  <div className="timeline-score">
                    审美评分: {event.score.toFixed(1)} / 5.0
                  </div>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
