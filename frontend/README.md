# 沉浸式AI小说创作平台 - 前端

## 项目简介

这是一个基于 React + TypeScript 的前端应用，用于与沉浸式AI小说创作平台的后端服务交互，提供世界图谱可视化和事件时间线展示。

## 技术栈

- **框架**: React 18 + TypeScript
- **构建工具**: Vite 5
- **路由**: React Router 6
- **状态管理**: Zustand
- **HTTP客户端**: Axios
- **可视化**: Cytoscape.js + D3.js
- **样式**: CSS3 (自定义)

## 功能特性

- 🌍 世界图谱可视化 (基于 Cytoscape.js)
- 📜 事件时间线展示
- 📊 模拟指标面板
- 🎭 AI角色状态追踪
- ⚡ 实时模拟更新

## 快速开始

### 安装依赖

```bash
cd frontend
npm install
```

### 开发模式

```bash
npm run dev
```

访问 http://localhost:3000

### 构建生产版本

```bash
npm run build
```

### 预览生产构建

```bash
npm run preview
```

## 项目结构

```
frontend/
├── src/
│   ├── components/       # React 组件
│   │   ├── WorldGraph.tsx       # 世界图谱组件
│   │   ├── EventTimeline.tsx    # 事件时间线
│   │   ├── MetricsPanel.tsx     # 指标面板
│   │   ├── AgentList.tsx       # 角色列表
│   │   └── OnboardingGuide.tsx # 引导页
│   ├── App.tsx           # 主应用组件
│   ├── api.ts            # API 服务层
│   ├── main.tsx          # 入口文件
│   └── index.css         # 全局样式
├── package.json
├── vite.config.ts
└── tsconfig.json
```

## API 配置

前端默认通过 Vite 代理连接后端服务：

- 开发模式: `http://localhost:8000`
- 生产模式: `http://170.106.194.111:8000`

如需修改，在 `vite.config.ts` 中更新 `API_BASE`。

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| VITE_API_URL | API 地址 | /api (开发) |

## 组件说明

### WorldGraph

使用 Cytoscape.js 渲染世界关系图谱，支持：
- 节点类型: 角色、地点、势力
- 边类型: 友好、敌对、互动
- 缩放、拖拽、点击交互

### EventTimeline

事件时间线组件，支持：
- 按类型筛选事件
- 高亮故事时刻
- 实时更新

### MetricsPanel

模拟指标展示面板，包括：
- 回合数、事件数
- 角色存活率
- 验收标准状态

### AgentList

AI角色状态列表，显示：
- 角色名称和头像
- 健康值、心情值
- 位置和关系

## 许可证

MIT
