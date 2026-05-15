---
task: Sprint 2 收尾 — WebSocket NPC位置 + 集成修补
slug: 20260515-integration-sprint
effort: Standard
phase: complete
progress: 8/8
mode: ALGORITHM
started: 2026-05-15T17:30:00
updated: 2026-05-15T17:30:00
---

## Context

前一轮分析发现大部分代码已就绪：
- leaflet/react-leaflet已安装，前端build通过(0错误)
- auth/db已集成到main.py
- 模板location已有真实lat/lng坐标
- NPC位置API已返回坐标
- TURN_COMPLETE WebSocket已包含npc_positions

实际缺口：
1. 缺少专用NPC_POSITION WebSocket事件类型（api.ts已声明但后端未发）
2. WorldMap使用5s轮询，可优化为WebSocket实时推送
3. Sprint 2的20条ISC中后端7条已满足6条（缺ISC-6: NPC_POSITION事件）

## Criteria

- [x] ISC-1: WebSocket新增NPC_POSITION专用事件广播
- [x] ISC-2: 模拟循环在NPC位置变更时推送NPC_POSITION事件
- [x] ISC-3: WorldMap订阅WebSocket实时更新NPC位置
- [x] ISC-4: 移除WorldMap的5s轮询，改为WebSocket驱动
- [x] ISC-5: 前端build 0错误
- [x] ISC-6: 更新Sprint 2 PRD标记ISC-6完成
- [x] ISC-7: git commit所有变更
- [x] ISC-8: 输出变更摘要

## Decisions

- NPC_POSITION在每回合完成时广播（与TURN_COMPLETE同时），避免额外开销
- WorldMap保留初始加载的HTTP请求，后续更新走WebSocket
