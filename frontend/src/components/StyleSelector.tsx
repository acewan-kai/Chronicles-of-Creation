import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../api';

interface StylePreset {
  id: string;
  name: string;
  description: string;
  vector: Record<string, number>;
}

interface StyleSelectorProps {
  worldId: string;
  onGenerate?: (chapter: any) => void;
}

const DIM_LABELS: Record<string, string> = {
  pace: '节奏',
  density: '密度',
  tension: '张力',
  emotion_depth: '情感深度',
  description_richness: '描写丰富度',
  dialogue_ratio: '对话占比',
  inner_monologue: '内心独白',
  humor: '幽默',
  darkness: '暗黑',
  poetry: '诗意',
  action_ratio: '动作占比',
  world_detail: '世界观细节',
};

export const StyleSelector: React.FC<StyleSelectorProps> = ({ worldId, onGenerate }) => {
  const [presets, setPresets] = useState<StylePreset[]>([]);
  const [selected, setSelected] = useState<string>('shuangwen');
  const [intensity, setIntensity] = useState(50);
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getStylePresets().then(setPresets).catch(() => {});
  }, []);

  const active = presets.find(p => p.id === selected);

  const handleGenerate = useCallback(async () => {
    if (!worldId || generating) return;
    setGenerating(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.generateStyledChapter(worldId, selected, intensity);
      setResult(res.chapter.chapter_text);
      onGenerate?.(res.chapter);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e.message || '生成失败');
    }
    setGenerating(false);
  }, [worldId, selected, intensity, generating, onGenerate]);

  return (
    <div className="style-selector">
      <h3>风格选择器</h3>

      {/* 风格预设 */}
      <div className="style-preset-grid">
        {presets.map(p => (
          <div
            key={p.id}
            className={`style-preset-card ${selected === p.id ? 'active' : ''}`}
            onClick={() => setSelected(p.id)}
          >
            <strong>{p.name}</strong>
            <p>{p.description}</p>
          </div>
        ))}
      </div>

      {/* 向量雷达预览 */}
      {active && (
        <div className="style-vector-preview">
          <strong>{active.name} — 风格向量</strong>
          <div className="vector-bars">
            {Object.entries(active.vector).map(([dim, val]) => (
              <div key={dim} className="vector-bar-row">
                <span className="vector-dim-label">{DIM_LABELS[dim] || dim}</span>
                <div className="vector-bar-track">
                  <div
                    className="vector-bar-fill"
                    style={{ width: `${(val as number) * 100}%` }}
                  />
                </div>
                <span className="vector-dim-value">{((val as number) * 100).toFixed(0)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 强度滑块 */}
      <div className="style-intensity">
        <label>
          风格强度: <strong>{intensity}%</strong>
        </label>
        <input
          type="range"
          min={0}
          max={100}
          value={intensity}
          onChange={e => setIntensity(Number(e.target.value))}
        />
        <div className="intensity-labels">
          <span>自然</span>
          <span>适中</span>
          <span>极致</span>
        </div>
      </div>

      {/* 生成按钮 */}
      <button
        className="btn btn-primary"
        onClick={handleGenerate}
        disabled={!worldId || generating}
      >
        {generating ? '生成中...' : '🎨 生成风格化章节'}
      </button>

      {error && <div className="error-msg">{error}</div>}

      {/* 生成结果 */}
      {result && (
        <div className="style-result">
          <strong>生成结果:</strong>
          <div className="chapter-text">{result}</div>
        </div>
      )}
    </div>
  );
};
