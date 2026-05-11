# P0 MVP - 沉浸式AI小说创作平台

## 项目结构

```
p0-mvp/
├── backend/
│   ├── app/
│   │   ├── core/
│   │   │   ├── sandbox/     # A01 沙盒模拟核心
│   │   │   ├── events/      # A02 事件日志系统
│   │   │   ├── knowledge/   # B01+B02 知识图谱
│   │   │   ├── agent/       # C01 智能体架构
│   │   │   └── scoring/     # G01 审美评分
│   │   ├── api/             # FastAPI 路由
│   │   └── main.py          # 主入口
│   └── requirements.txt
└── frontend/
    ├── src/
    │   └── components/      # F01 可视化图谱
    └── package.json
```

## 开发进度

- [x] A01 沙盒模拟核心
- [ ] A02 事件日志系统（SQLite）
- [ ] B01+B02 世界信息注入 + 知识图谱
- [ ] C01 智能体核心架构
- [ ] F01 可视化世界观图谱
- [ ] G01 基础审美评分

## 快速开始

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## API 端点

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | /api/worlds | 列出世界 |
| GET | /api/worlds/{id} | 获取世界详情 |
| GET | /api/worlds/{id}/events | 获取事件日志 |
| POST | /api/simulate/start | 开始模拟 |
| GET | /api/simulate/status | 模拟状态 |

## 验收标准

| 条件 | 阈值 | 状态 |
|------|------|------|
| 10个NPC存活100回合 | 必须 | ✅ |
| 非预设互动 ≥3 | ≥3 | ✅ |
| 故事感时刻 ≥1 | ≥1 | ✅ |
| 单回合延迟 <15s | <15s | ✅ |
