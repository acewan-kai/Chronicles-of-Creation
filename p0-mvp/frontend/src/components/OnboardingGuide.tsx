import React, { useState, useCallback } from 'react';

interface Template {
  id: string;
  name: string;
  genre: string;
  description: string;
  thumbnail: string;
  difficulty: string;
}

const TEMPLATES: Template[] = [
  {
    id: 'cultivation',
    name: '青云仙门',
    genre: '修仙',
    description: '以剑道闻名的修仙门派，弟子们为突破境界而苦修',
    thumbnail: '🗡️',
    difficulty: '入门'
  },
  {
    id: 'wuxia',
    name: '江湖风云录',
    genre: '武侠',
    description: '明末乱世，门派林立，一把传说中的绝世神兵引发争夺',
    thumbnail: '🌙',
    difficulty: '入门'
  },
  {
    id: 'urban',
    name: '深夜事务所',
    genre: '都市奇幻',
    description: '现代都市中隐藏着无数神秘存在，承接超自然委托',
    thumbnail: '🌃',
    difficulty: '入门'
  }
];

interface OnboardingGuideProps {
  onComplete: (config: { template: string; worldName: string }) => void;
  onSkip?: () => void;
}

type Step = 'welcome' | 'choose_template' | 'name_world' | 'customize' | 'ready';

export const OnboardingGuide: React.FC<OnboardingGuideProps> = ({ onComplete, onSkip }) => {
  const [step, setStep] = useState<Step>('welcome');
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null);
  const [worldName, setWorldName] = useState('');
  const [error, setError] = useState('');

  const handleStart = useCallback(() => {
    setStep('choose_template');
  }, []);

  const handleTemplateSelect = useCallback((id: string) => {
    setSelectedTemplate(id);
    setStep('name_world');
    setError('');
  }, []);

  const handleNameSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    const name = worldName.trim();
    if (name.length < 2 || name.length > 20) {
      setError('名称长度需在2-20个字符之间');
      return;
    }
    setStep('customize');
  }, [worldName]);

  const handleCustomizeSkip = useCallback(() => {
    if (selectedTemplate && worldName.trim()) {
      onComplete({ template: selectedTemplate, worldName: worldName.trim() });
    }
  }, [selectedTemplate, worldName, onComplete]);

  const handleStartSimulation = useCallback(() => {
    if (selectedTemplate && worldName.trim()) {
      onComplete({ template: selectedTemplate, worldName: worldName.trim() });
    }
  }, [selectedTemplate, worldName, onComplete]);

  const progress = {
    welcome: 0,
    choose_template: 25,
    name_world: 50,
    customize: 75,
    ready: 100
  };

  return (
    <div className="onboarding-guide">
      {/* 进度条 */}
      <div className="onboarding-progress">
        <div 
          className="onboarding-progress-bar" 
          style={{ width: `${progress[step]}%` }}
        />
      </div>

      {/* 步骤内容 */}
      <div className="onboarding-content">
        {/* 欢迎页 */}
        {step === 'welcome' && (
          <div className="onboarding-step fade-in">
            <div className="step-icon">📚</div>
            <h1>欢迎来到AI小说创作平台</h1>
            <p className="step-description">
              在这里，AI角色将在你构建的世界中自主生活、互动，
              <br />
              故事将从他们的行动中自然涌现。
            </p>
            <div className="step-features">
              <div className="feature">
                <span className="feature-icon">🎭</span>
                <span>10+ AI角色自主行动</span>
              </div>
              <div className="feature">
                <span className="feature-icon">🌍</span>
                <span>丰富的世界观设定</span>
              </div>
              <div className="feature">
                <span className="feature-icon">✨</span>
                <span>故事自然涌现</span>
              </div>
            </div>
            <button className="btn-primary" onClick={handleStart}>
              开始创作
            </button>
            {onSkip && (
              <button className="btn-secondary" onClick={onSkip}>
                跳过引导
              </button>
            )}
          </div>
        )}

        {/* 选择模板 */}
        {step === 'choose_template' && (
          <div className="onboarding-step fade-in">
            <h2>选择你的世界模板</h2>
            <p className="step-description">
              我们提供了3个精心设计的预制世界，你也可以从零开始创建。
            </p>
            <div className="template-grid">
              {TEMPLATES.map((template) => (
                <div
                  key={template.id}
                  className={`template-card ${selectedTemplate === template.id ? 'selected' : ''}`}
                  onClick={() => handleTemplateSelect(template.id)}
                >
                  <div className="template-thumbnail">{template.thumbnail}</div>
                  <div className="template-info">
                    <h3>{template.name}</h3>
                    <span className="template-genre">{template.genre}</span>
                    <p className="template-desc">{template.description}</p>
                    <span className="template-difficulty">{template.difficulty}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 命名世界 */}
        {step === 'name_world' && (
          <div className="onboarding-step fade-in">
            <h2>为你的世界命名</h2>
            <p className="step-description">
              给你的世界起一个独一无二的名字，
              <br />
              这将成为故事发生的舞台。
            </p>
            <form onSubmit={handleNameSubmit} className="name-form">
              <input
                type="text"
                value={worldName}
                onChange={(e) => {
                  setWorldName(e.target.value);
                  setError('');
                }}
                placeholder="输入世界名称..."
                className="name-input"
                maxLength={20}
                autoFocus
              />
              {error && <span className="error-message">{error}</span>}
              <div className="char-count">{worldName.length}/20</div>
              <div className="button-group">
                <button 
                  type="button" 
                  className="btn-secondary"
                  onClick={() => setStep('choose_template')}
                >
                  上一步
                </button>
                <button type="submit" className="btn-primary">
                  下一步
                </button>
              </div>
            </form>
          </div>
        )}

        {/* 自定义角色 */}
        {step === 'customize' && (
          <div className="onboarding-step fade-in">
            <h2>自定义角色（可选）</h2>
            <p className="step-description">
              你可以调整预置角色的性格、背景或关系，
              <br />
              也可以保持默认设置直接开始。
            </p>
            <div className="customize-options">
              <div className="customize-option" onClick={handleCustomizeSkip}>
                <div className="option-icon">⚡</div>
                <div className="option-text">
                  <h4>保持默认设置</h4>
                  <p>直接使用预置角色，快速开始</p>
                </div>
              </div>
              <div className="customize-option disabled">
                <div className="option-icon">🎨</div>
                <div className="option-text">
                  <h4>调整角色设定</h4>
                  <p>coming soon</p>
                </div>
              </div>
              <div className="customize-option disabled">
                <div className="option-icon">➕</div>
                <div className="option-text">
                  <h4>添加新角色</h4>
                  <p>coming soon</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 准备启动 */}
        {step === 'ready' && (
          <div className="onboarding-step fade-in">
            <div className="ready-icon">🚀</div>
            <h2>一切准备就绪！</h2>
            <div className="ready-summary">
              <div className="summary-item">
                <span className="label">世界名称</span>
                <span className="value">{worldName}</span>
              </div>
              <div className="summary-item">
                <span className="label">模板</span>
                <span className="value">
                  {TEMPLATES.find(t => t.id === selectedTemplate)?.name}
                </span>
              </div>
            </div>
            <p className="ready-hint">
              AI角色们将在你的世界中开始他们的故事
            </p>
            <button className="btn-primary btn-large" onClick={handleStartSimulation}>
              启动模拟
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default OnboardingGuide;
