import React, { useState, useEffect } from 'react';
import { api, Template } from '../api';

interface CreateWorldModalProps {
  onCreated: (worldId: string) => void;
  onClose: () => void;
}

interface GeneratedWorld {
  era: string;
  locations: Array<{ id: string; name: string; desc: string; lat: number; lng: number }>;
  agents: Array<{ id: string; name: string; identity: string; personality: string }>;
  initial_relationships: Array<{ a: string; b: string; type: string; weight: number }>;
  active_events: string[];
}

const TEMPLATE_INFO: Record<string, { name: string; genre: string; desc: string; icon: string }> = {
  cultivation: { name: '青云仙门', genre: '修仙', desc: '灵气浓郁，宗门林立，剑道通神', icon: '🏔️' },
  wuxia: { name: '江湖风云录', genre: '武侠', desc: '明末乱世，武林争霸，侠义与阴谋', icon: '⚔️' },
  urban: { name: '深夜事务所', genre: '都市奇幻', desc: '现代都市，超自然事件，阴阳两界', icon: '🌃' },
  generate: { name: '✨ 智能生成', genre: 'AI定制', desc: '输入你的世界观描述，AI自动生成专属世界', icon: '🤖' },
};

// 根据agent id查找名字
function agentName(agents: GeneratedWorld['agents'], id: string): string {
  const found = agents.find(a => a.id === id);
  return found ? found.name : id;
}

export const CreateWorldModal: React.FC<CreateWorldModalProps> = ({ onCreated, onClose }) => {
  const [worldName, setWorldName] = useState('');
  const [worldDesc, setWorldDesc] = useState('');
  const [template, setTemplate] = useState('generate');
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 智能生成预览
  const [generated, setGenerated] = useState<GeneratedWorld | null>(null);
  const [showPreview, setShowPreview] = useState(false);

  useEffect(() => {
    api.getTemplates().then(data => setTemplates(data)).catch(() => {});
  }, []);

  // 智能生成
  const handleGenerate = async () => {
    const name = worldName.trim();
    if (!name) {
      setError('请输入世界名称');
      return;
    }
    if (!worldDesc.trim()) {
      setError('请输入世界描述，AI需要知道你想要什么样的世界');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await api.generateWorld(name, worldDesc.trim());
      setGenerated(data.generated);
      setShowPreview(true);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || '智能生成失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  // 确认创建
  const handleCreate = async () => {
    const name = worldName.trim();
    if (!name) {
      setError('请输入世界名称');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await api.createWorld(
        name,
        generated ? 'custom' : template,
        worldDesc.trim() || undefined,
        generated || undefined,
      );
      onCreated(data.world?.id || data.id);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || '创建失败');
    } finally {
      setLoading(false);
    }
  };

  const selectedInfo = TEMPLATE_INFO[template];

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content modal-wide" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>创建新世界</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <div className="modal-body">
          {/* 世界名称 */}
          <div className="form-group">
            <label>世界名称</label>
            <input
              type="text"
              value={worldName}
              onChange={e => setWorldName(e.target.value)}
              placeholder="给你的世界起个名字，如「都市异能世界」"
              className="form-input"
              autoFocus
            />
          </div>

          {/* 创建方式选择 */}
          <div className="form-group">
            <label>创建方式</label>
            <div className="template-grid template-grid-4">
              {['generate', 'cultivation', 'wuxia', 'urban'].map(key => {
                const info = TEMPLATE_INFO[key];
                const isSelected = template === key;
                return (
                  <div
                    key={key}
                    className={`template-card ${isSelected ? 'selected' : ''}`}
                    onClick={() => { setTemplate(key); setGenerated(null); setShowPreview(false); }}
                  >
                    <span className="template-icon">{info.icon}</span>
                    <div className="template-info">
                      <div className="template-name">{info.name}</div>
                      <div className="template-genre">{info.genre}</div>
                      <div className="template-desc">{info.desc}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* 智能生成：描述输入 */}
          {template === 'generate' && !showPreview && (
            <div className="form-group">
              <label>世界描述（告诉AI你想要什么样的世界）</label>
              <textarea
                value={worldDesc}
                onChange={e => setWorldDesc(e.target.value)}
                placeholder={'描述你的世界设定，越详细越好。例如：\n\n"2025年的上海，表面上繁华如常，暗地里异能者和妖怪组织维持着脆弱平衡。主角经营一家表面是古董店、实为灵异事件处理所的小店。东西方超自然力量在城市暗处碰撞..."'}
                className="form-textarea"
                rows={5}
              />
              <div className="form-hint">
                提示：描述越详细，AI生成的世界越贴合你的想象。可以包含时代背景、核心设定、势力关系等。
              </div>
            </div>
          )}

          {/* 智能生成预览 */}
          {showPreview && generated && (
            <div className="generate-preview">
              <h4>🤖 AI已为你生成世界「{worldName}」</h4>
              <div className="preview-era">时代背景：{generated.era}</div>

              <div className="preview-section">
                <h5>📍 地点 ({generated.locations?.length || 0}个)</h5>
                <div className="preview-grid">
                  {(generated.locations || []).map(loc => (
                    <div key={loc.id} className="preview-item">
                      <strong>{loc.name}</strong>
                      <span>{loc.desc}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="preview-section">
                <h5>👤 角色 ({generated.agents?.length || 0}个)</h5>
                <div className="preview-grid">
                  {(generated.agents || []).map(agent => (
                    <div key={agent.id} className="preview-item">
                      <strong>{agent.name}</strong>
                      <span className="agent-identity">{agent.identity}</span>
                      <span className="agent-personality">{agent.personality}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="preview-section">
                <h5>🔗 初始关系</h5>
                <div className="preview-grid">
                  {(generated.initial_relationships || []).map((rel, i) => (
                    <div key={i} className="preview-item preview-rel">
                      <strong>{agentName(generated.agents, rel.a)}</strong>
                      <span className="rel-type">{rel.type}</span>
                      <strong>{agentName(generated.agents, rel.b)}</strong>
                    </div>
                  ))}
                </div>
              </div>

              {generated.active_events?.length > 0 && (
                <div className="preview-section">
                  <h5>⚡ 活跃事件</h5>
                  <ul className="preview-events">
                    {generated.active_events.map((ev, i) => (
                      <li key={i}>{ev}</li>
                    ))}
                  </ul>
                </div>
              )}

              <button
                className="btn btn-secondary"
                onClick={() => { setShowPreview(false); setGenerated(null); }}
                style={{ marginTop: 12 }}
              >
                重新生成
              </button>
            </div>
          )}

          {error && <div className="form-error">{error}</div>}
        </div>

        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>取消</button>

          {template === 'generate' && !showPreview && (
            <button
              className="btn btn-accent"
              onClick={handleGenerate}
              disabled={loading || !worldName.trim() || !worldDesc.trim()}
            >
              {loading ? 'AI生成中...' : '🤖 智能生成'}
            </button>
          )}

          {(template !== 'generate' || showPreview) && (
            <button
              className="btn btn-primary"
              onClick={handleCreate}
              disabled={loading}
            >
              {loading ? '创建中...' : `创建世界「${worldName.trim() || selectedInfo.name}」`}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
