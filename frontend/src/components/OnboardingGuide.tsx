import React from 'react';

interface OnboardingGuideProps {
  onStart: () => void;
}

export const OnboardingGuide: React.FC<OnboardingGuideProps> = ({ onStart }) => {
  return (
    <div className="onboarding-guide">
      <div className="onboarding-icon">📖</div>
      <h2>开始你的创作之旅</h2>
      <p>
        点击下方按钮，让AI角色在你的世界中开始他们的故事。
        <br />
        故事将从他们的行动中自然涌现。
      </p>
      
      <div className="onboarding-steps">
        <div className="onboarding-step">
          <span className="step-number">1</span>
          <span className="step-text">选择世界</span>
        </div>
        <div className="onboarding-step">
          <span className="step-number">2</span>
          <span className="step-text">启动模拟</span>
        </div>
        <div className="onboarding-step">
          <span className="step-number">3</span>
          <span className="step-text">见证故事</span>
        </div>
      </div>
      
      <button onClick={onStart} className="btn btn-primary">
        <span className="btn-icon">▶</span>
        开始模拟
      </button>
      
      <div className="onboarding-features">
        <div className="feature">
          <span className="feature-icon">🎭</span>
          <span>10+ AI角色</span>
        </div>
        <div className="feature">
          <span className="feature-icon">🌍</span>
          <span>丰富世界观</span>
        </div>
        <div className="feature">
          <span className="feature-icon">✨</span>
          <span>故事涌现</span>
        </div>
      </div>
    </div>
  );
};
