---
task: Sprint 2 - F03时间线控件 + F02世界地图
slug: 20260515-sprint2-timeline-map
effort: Extended
phase: build
progress: 1/20
mode: algorithm
started: 2026-05-15T15:50:00+08:00
updated: 2026-05-15T15:50:00+08:00
---

## Context

Sprint 2 of P1 development: 时间线控件 (F03) + 世界地图 (F02).

**F03 时间线控件**: 可拖拽的时间轴组件，支持多速度回放(1x/10x/100x/1000x)、事件标记、快照保存/加载。需要后端快照API支持。

**F02 世界地图**: 基于Leaflet的交互式地图，≥3种图层(地理/势力/事件热力)，NPC位置实时可见，地图图标可点击查看NPC详情。需要WebSocket扩展推送NPC位置变更。

**现有基础**: 
- 前端无路由，扁平组件树，状态在App.tsx管理
- 已有WebSocket连接(NEW_EVENT/TURN_COMPLETE/STATUS_CHANGE)
- 已有EventTimeline组件(垂直列表)但无时间轴控件
- 无Leaflet/地图库
- 后端模拟循环已有NPC位置数据

### 交付物
- `src/components/TimelineControls.tsx` — 可拖拽时间轴，速度控制，事件标记
- `src/components/WorldMap.tsx` — Leaflet地图，多层，NPC实时位置
- `src/api.ts` — 增加快照/地图相关API调用
- `src/App.tsx` — 增加新标签和路由
- `app/main.py` — 新增快照API + NPC位置API
- WebSocket扩展：NPC位置变更事件

### Decisions

无第三方时间线库，自建轻量组件(L206)。Leaflet使用react-leaflet v4。

### Plan

**后端 (20min)**: 快照CRUD API → NPC位置查询API → WebSocket NPC位置推送
**前端 (60min)**: 安装leaflet → 创建TimelineControls → 创建WorldMap → 集成到App → 扩展api.ts/WebSocket

## Criteria

### 后端
- [ ] ISC-1: POST /api/worlds/{id}/snapshots 保存世界快照
- [ ] ISC-2: GET /api/worlds/{id}/snapshots 返回快照列表
- [ ] ISC-3: 快照包含时间点/事件摘要/NPC位置/世界状态
- [ ] ISC-4: GET /api/worlds/{id}/npc-locations 返回所有NPC当前位置
- [ ] ISC-5: WebSocket TURN_COMPLETE 消息包含NPC位置更新数据
- [x] ISC-6: WebSocket 新增 NPC_POSITION 事件类型
- [ ] ISC-7: 快照存储在 event_store SQLite 中持久化

### F03 时间线控件
- [ ] ISC-8: 时间轴支持拖拽滑动选择时间点
- [ ] ISC-9: 速度控制按钮 (1x/10x/100x/1000x)
- [ ] ISC-10: 事件在时间轴上以标记点显示
- [ ] ISC-11: 点击标记点显示事件详情
- [ ] ISC-12: 时间轴根据已选速度自动播放
- [ ] ISC-13: 快照保存/加载按钮
- [ ] ISC-14: 时间线集成到世界详情页的tab切换

### F02 世界地图
- [ ] ISC-15: Leaflet地图加载世界地点标记
- [ ] ISC-16: NPC位置实时显示（随WebSocket更新）
- [ ] ISC-17: ≥3种图层切换（地理/势力/事件热力）
- [ ] ISC-18: 点击NPC图标显示详情弹窗
- [ ] ISC-19: 地图集成到世界详情页的tab切换
- [ ] ISC-20: WebSocket NPC位置变更自动更新地图标记

## Verification

由后续VERIFY阶段填充。
