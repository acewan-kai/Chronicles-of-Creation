import React, { useRef, useCallback, useEffect, useState } from 'react';
import { api, Event, Snapshot } from '../api';

interface TimelineControlsProps {
  events: Event[];
  currentTurn: number;
  worldId: string;
  isSimulating: boolean;
  onSeek?: (turn: number) => void;
}

const SPEEDS = [1, 10, 100, 1000];

export const TimelineControls: React.FC<TimelineControlsProps> = ({
  events,
  currentTurn,
  worldId,
  isSimulating,
  onSeek,
}) => {
  const timelineRef = useRef<HTMLDivElement>(null);
  const [playSpeed, setPlaySpeed] = useState(1);
  const [isPlaying, setIsPlaying] = useState(false);
  const [selectedTurn, setSelectedTurn] = useState<number | null>(null);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [saving, setSaving] = useState(false);
  const [showSnapshotList, setShowSnapshotList] = useState(false);

  // 从事件中提取所有回合数
  const turnsWithEvents = React.useMemo(() => {
    const turnSet = new Set<number>();
    events.forEach(e => turnSet.add(e.turn));
    return Array.from(turnSet).sort((a, b) => a - b);
  }, [events]);

  const maxTurn = Math.max(currentTurn, ...turnsWithEvents, 1);

  // 点击时间轴跳转
  const handleTimelineClick = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!timelineRef.current) return;
    const rect = timelineRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const pct = x / rect.width;
    const turn = Math.max(1, Math.round(pct * maxTurn));
    setSelectedTurn(turn);
    onSeek?.(turn);
  }, [maxTurn, onSeek]);

  // 播放/暂停
  const togglePlay = useCallback(() => {
    if (isSimulating) return;
    setIsPlaying(p => !p);
  }, [isSimulating]);

  // 保存快照
  const handleSaveSnapshot = useCallback(async () => {
    if (saving) return;
    setSaving(true);
    try {
      const snap = await api.saveSnapshot(worldId);
      setSnapshots(prev => [snap, ...prev].slice(0, 50));
    } catch (err) {
      console.error('保存快照失败:', err);
    }
    setSaving(false);
  }, [worldId, saving]);

  // 加载快照列表
  const loadSnapshots = useCallback(async () => {
    try {
      const snaps = await api.getSnapshots(worldId);
      setSnapshots(snaps);
    } catch { /* ignore */ }
  }, [worldId]);

  // 加载快照时跳转
  const handleLoadSnapshot = useCallback((snap: Snapshot) => {
    setSelectedTurn(snap.turn);
    onSeek?.(snap.turn);
    setShowSnapshotList(false);
  }, [onSeek]);

  // 播放推进
  useEffect(() => {
    if (!isPlaying || isSimulating) return;
    const interval = 1000 / playSpeed;
    const timer = setInterval(() => {
      setSelectedTurn(prev => {
        const next = (prev ?? 0) + 1;
        if (next > maxTurn) {
          setIsPlaying(false);
          return maxTurn;
        }
        onSeek?.(next);
        return next;
      });
    }, interval);
    return () => clearInterval(timer);
  }, [isPlaying, playSpeed, maxTurn, onSeek, isSimulating]);

  // 加载快照
  useEffect(() => {
    if (worldId) loadSnapshots();
  }, [worldId, loadSnapshots]);

  // 当前选中回合的事件
  const selectedEvents = React.useMemo(() => {
    if (selectedTurn === null) return [];
    return events.filter(e => e.turn === selectedTurn);
  }, [events, selectedTurn]);

  // 格式化时间显示
  const formatTurnTime = (turn: number) => {
    const day = Math.floor(turn / 8) + 1;
    const hour = (turn % 8) * 3;
    return `第${day}天 ${hour.toString().padStart(2, '0')}:00`;
  };

  return (
    <div className="timeline-controls">
      <div className="timeline-header-bar">
        <h3>时间线控制</h3>
        <div className="timeline-actions">
          <button
            className="btn btn-sm"
            onClick={handleSaveSnapshot}
            disabled={saving}
            title="保存当前时间点"
          >
            {saving ? '保存中...' : '📸 保存快照'}
          </button>
          <button
            className="btn btn-sm"
            onClick={() => setShowSnapshotList(v => !v)}
            title="查看快照列表"
          >
            📋 快照 ({snapshots.length})
          </button>
        </div>
      </div>

      {/* 速度控制 */}
      <div className="speed-controls">
        <span className="speed-label">播放速度:</span>
        {SPEEDS.map(s => (
          <button
            key={s}
            className={`btn btn-xs ${playSpeed === s ? 'btn-active' : ''}`}
            onClick={() => setPlaySpeed(s)}
          >
            {s}x
          </button>
        ))}
        <button
          className={`btn btn-xs ${isPlaying ? 'btn-danger' : 'btn-primary'}`}
          onClick={togglePlay}
          disabled={isSimulating}
        >
          {isPlaying ? '⏸ 暂停' : '▶ 播放'}
        </button>
      </div>

      {/* 时间轴滑块 */}
      <div
        ref={timelineRef}
        className="timeline-slider"
        onClick={handleTimelineClick}
      >
        <div className="timeline-track">
          {/* 进度条 */}
          <div
            className="timeline-progress"
            style={{ width: `${((selectedTurn ?? currentTurn) / maxTurn) * 100}%` }}
          />
          {/* 事件标记点 */}
          {turnsWithEvents.filter(t => t % Math.max(1, Math.floor(maxTurn / 30)) === 0 || t === 1).map(turn => (
            <div
              key={turn}
              className="timeline-event-marker"
              style={{ left: `${(turn / maxTurn) * 100}%` }}
              title={`T${turn}: ${events.find(e => e.turn === turn)?.actor ?? ''}`}
            />
          ))}
          {/* 拖拽头部 */}
          <div
            className="timeline-playhead"
            style={{ left: `${((selectedTurn ?? currentTurn) / maxTurn) * 100}%` }}
          >
            <div className="playhead-dot" />
          </div>
        </div>
        <div className="timeline-labels">
          <span>T1 {formatTurnTime(1)}</span>
          <span>T{maxTurn} {formatTurnTime(maxTurn)}</span>
        </div>
      </div>

      {/* 当前事件详情 */}
      {selectedTurn !== null && selectedEvents.length > 0 && (
        <div className="timeline-event-detail">
          <div className="detail-header">
            <strong>回合 T{selectedTurn} — {formatTurnTime(selectedTurn)}</strong>
            <span className="detail-count">{selectedEvents.length} 个事件</span>
          </div>
          <div className="detail-list">
            {selectedEvents.slice(0, 5).map((ev, i) => (
              <div key={i} className="detail-item">
                <span className="detail-actor">{ev.actor}</span>
                <span className="detail-action">{ev.action?.slice(0, 60)}</span>
                {ev.target && <span className="detail-target">→ {ev.target}</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 快照列表弹出 */}
      {showSnapshotList && (
        <div className="snapshot-list-panel">
          <div className="snapshot-list-header">
            <strong>快照列表</strong>
            <button className="btn btn-xs" onClick={() => setShowSnapshotList(false)}>✕</button>
          </div>
          <div className="snapshot-list">
            {snapshots.length === 0 ? (
              <p className="empty-text">暂无快照</p>
            ) : (
              snapshots.slice().reverse().map(snap => (
                <div
                  key={snap.id}
                  className="snapshot-item"
                  onClick={() => handleLoadSnapshot(snap)}
                >
                  <span className="snap-turn">T{snap.turn}</span>
                  <span className="snap-time">{formatTurnTime(snap.turn)}</span>
                  <span className="snap-mood">{snap.world_mood}</span>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
};
