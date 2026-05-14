import React, { useState, useMemo } from 'react';
import dayjs from 'dayjs';

interface EventTimelineProps {
  events: any[];
}

const PAGE_SIZE = 20;

export const EventTimeline: React.FC<EventTimelineProps> = ({ events }) => {
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [actorFilter, setActorFilter] = useState('');
  const [minTurn, setMinTurn] = useState('');
  const [maxTurn, setMaxTurn] = useState('');
  const [page, setPage] = useState(1);
  const [expandedEvent, setExpandedEvent] = useState<number | null>(null);

  // 提取所有actor用于下拉筛选
  const actors = useMemo(() => {
    const names = new Set<string>();
    events.forEach(e => { if (e.actor) names.add(e.actor); });
    return Array.from(names).sort();
  }, [events]);

  // 筛选
  const filteredEvents = useMemo(() => {
    let result = events;

    if (typeFilter !== 'all') {
      result = result.filter(e => e.action_type === typeFilter);
    }
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      result = result.filter(e =>
        (e.actor && e.actor.toLowerCase().includes(q)) ||
        (e.target && e.target.toLowerCase().includes(q)) ||
        (e.action && e.action.toLowerCase().includes(q)) ||
        (e.location && e.location.toLowerCase().includes(q))
      );
    }
    if (actorFilter) {
      result = result.filter(e => e.actor === actorFilter);
    }
    if (minTurn) {
      result = result.filter(e => e.turn >= parseInt(minTurn));
    }
    if (maxTurn) {
      result = result.filter(e => e.turn <= parseInt(maxTurn));
    }

    return result;
  }, [events, typeFilter, searchQuery, actorFilter, minTurn, maxTurn]);

  // 分页
  const totalPages = Math.max(1, Math.ceil(filteredEvents.length / PAGE_SIZE));
  const pagedEvents = filteredEvents.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  // Reset page on filter change
  React.useEffect(() => { setPage(1); }, [typeFilter, searchQuery, actorFilter, minTurn, maxTurn]);

  const resetFilters = () => {
    setTypeFilter('all');
    setSearchQuery('');
    setActorFilter('');
    setMinTurn('');
    setMaxTurn('');
    setPage(1);
  };

  const hasActiveFilters = typeFilter !== 'all' || searchQuery || actorFilter || minTurn || maxTurn;

  const formatTime = (turn: number) => {
    const day = Math.floor(turn / 8) + 1;
    const hour = (turn % 8) * 3;
    return `第${day}天 ${hour.toString().padStart(2, '0')}:00`;
  };

  const highlightMatch = (text: string) => {
    if (!searchQuery || !text) return text;
    const idx = text.toLowerCase().indexOf(searchQuery.toLowerCase());
    if (idx < 0) return text;
    return (
      <>
        {text.slice(0, idx)}
        <mark className="search-highlight">{text.slice(idx, idx + searchQuery.length)}</mark>
        {text.slice(idx + searchQuery.length)}
      </>
    );
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
        <div className="timeline-controls">
          {/* 搜索框 */}
          <input
            type="text"
            className="search-input"
            placeholder="搜索角色/动作/地点..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
          />

          {/* 类型筛选 */}
          <div className="filter-buttons">
            <button className={`filter-btn ${typeFilter === 'all' ? 'active' : ''}`} onClick={() => setTypeFilter('all')}>
              全部
            </button>
            <button className={`filter-btn ${typeFilter === 'interaction' ? 'active' : ''}`} onClick={() => setTypeFilter('interaction')}>
              互动
            </button>
            <button className={`filter-btn ${typeFilter === 'story_moment' ? 'active' : ''}`} onClick={() => setTypeFilter('story_moment')}>
              故事
            </button>
            <button className={`filter-btn ${typeFilter === 'normal' ? 'active' : ''}`} onClick={() => setTypeFilter('normal')}>
              普通
            </button>
          </div>

          {/* 角色筛选 */}
          <select
            className="filter-select"
            value={actorFilter}
            onChange={e => setActorFilter(e.target.value)}
          >
            <option value="">全部角色</option>
            {actors.map(name => (
              <option key={name} value={name}>{name}</option>
            ))}
          </select>

          {/* 回合范围 */}
          <div className="turn-range">
            <input
              type="number"
              className="turn-input"
              placeholder="起始回合"
              value={minTurn}
              onChange={e => setMinTurn(e.target.value)}
              min={1}
            />
            <span>–</span>
            <input
              type="number"
              className="turn-input"
              placeholder="结束回合"
              value={maxTurn}
              onChange={e => setMaxTurn(e.target.value)}
              min={1}
            />
          </div>

          {hasActiveFilters && (
            <button className="reset-btn" onClick={resetFilters}>× 重置</button>
          )}
        </div>

        <div className="timeline-count">
          显示 {pagedEvents.length} / {filteredEvents.length} 条
          {filteredEvents.length !== events.length && ` (总计 ${events.length} 条)`}
        </div>
      </div>

      <div className="timeline-list">
        {pagedEvents.length === 0 ? (
          <div className="timeline-empty">
            <p>{events.length === 0 ? '暂无事件，启动模拟后将自动生成' : '无匹配事件'}</p>
          </div>
        ) : (
          pagedEvents.map((event, index) => (
            <div
              key={`${event.turn}_${(page - 1) * PAGE_SIZE + index}`}
              className={`timeline-item ${event.action_type === 'story_moment' ? 'highlight' : ''}`}
              onClick={() => setExpandedEvent(expandedEvent === index ? null : index)}
            >
              <div className="timeline-marker">
                <span className="marker-dot" />
                {index < pagedEvents.length - 1 && <span className="marker-line" />}
              </div>

              <div className="timeline-content">
                <div className="timeline-meta">
                  <span className="timeline-time">{formatTime(event.turn)}</span>
                  <span className="timeline-turn">(T{event.turn})</span>
                  <span className="timeline-location">{event.location}</span>
                  {getTypeBadge(event.action_type)}
                </div>

                <div className="timeline-actor">
                  <strong>{highlightMatch(event.actor || '?')}</strong>
                  {event.target && (
                    <span className="timeline-target"> → {highlightMatch(event.target)}</span>
                  )}
                </div>

                <div className="timeline-action">
                  {expandedEvent === index ? (
                    <p className="action-full">{highlightMatch(event.action || '')}</p>
                  ) : (
                    <p className="action-preview">
                      {event.action && event.action.length > 100
                        ? highlightMatch(event.action.slice(0, 100)) + '...'
                        : highlightMatch(event.action || '')}
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

      {/* 分页 */}
      {totalPages > 1 && (
        <div className="timeline-pagination">
          <button disabled={page <= 1} onClick={() => setPage(p => Math.max(1, p - 1))}>
            上一页
          </button>
          <span className="page-info">第 {page} / {totalPages} 页</span>
          <button disabled={page >= totalPages} onClick={() => setPage(p => Math.min(totalPages, p + 1))}>
            下一页
          </button>
        </div>
      )}
    </div>
  );
};
