import React, { useState, useEffect } from 'react';
import { api, Template } from '../api';

interface CreateWorldModalProps {
  onCreated: (worldId: string) => void;
  onClose: () => void;
}

const TEMPLATE_INFO: Record<string, { name: string; genre: string; desc: string; icon: string }> = {
  cultivation: { name: '青云仙门', genre: '修仙', desc: '灵气浓郁，宗门林立，剑道通神，妖兽横行', icon: '🏔️' },
  wuxia: { name: '江湖风云录', genre: '武侠', desc: '明末乱世，武林争霸，侠义与阴谋交织', icon: '⚔️' },
  urban: { name: '深夜事务所', genre: '都市奇幻', desc: '现代都市，超自然事件，阴阳两界交汇', icon: '🌃' },
};

export const CreateWorldModal: React.FC<CreateWorldModalProps> = ({ onCreated, onClose }) => {
  const [worldName, setWorldName] = useState('');
  const [template, setTemplate] = useState('cultivation');
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getTemplates().then(data => setTemplates(data)).catch(() => {});
  }, []);

  const handleCreate = async () => {
    const name = worldName.trim() || TEMPLATE_INFO[template]?.name || '新世界';
    setLoading(true);
    setError(null);
    try {
      const data = await api.createWorld(name, template);
      onCreated(data.world?.id || data.id);
    } catch (err: any) {
      setError(err.message || '创建失败，请检查后端服务');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>创建新世界</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <div className="modal-body">
          <div className="form-group">
            <label>世界名称</label>
            <input
              type="text"
              value={worldName}
              onChange={e => setWorldName(e.target.value)}
              placeholder="输入世界名称，或留空使用模板默认名"
              className="form-input"
              autoFocus
            />
          </div>

          <div className="form-group">
            <label>选择模板</label>
            <div className="template-grid">
              {['cultivation', 'wuxia', 'urban'].map(key => {
                const info = TEMPLATE_INFO[key];
                return (
                  <div
                    key={key}
                    className={`template-card ${template === key ? 'selected' : ''}`}
                    onClick={() => setTemplate(key)}
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

          {error && <div className="form-error">{error}</div>}
        </div>

        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>取消</button>
          <button
            className="btn btn-primary"
            onClick={handleCreate}
            disabled={loading}
          >
            {loading ? '创建中...' : '创建世界'}
          </button>
        </div>
      </div>
    </div>
  );
};
