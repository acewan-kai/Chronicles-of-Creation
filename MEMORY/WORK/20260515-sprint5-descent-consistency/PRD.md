---
task: Sprint 5 — 降临模式(F04) + 角色一致性守护(C02)
slug: 20260515-sprint5-descent-consistency
effort: Advanced
phase: execute
progress: 25/26
mode: ALGORITHM
started: 2026-05-15T18:10:00
updated: 2026-05-15T18:10:00
---

## Context

Sprint 5: F04降临模式（创作者化身进入世界）+ C02角色一致性守护（持续监测NPC行为偏离）。

**F04 降临模式**: 用户选择NPC降临，以该角色视角体验世界。降临延迟≤3s，不破坏NPC设定，自动记录日志，支持≥4个对话选项。

**C02 角色一致性守护**: 3类检测（行为/语言风格/关系逻辑），偏离检测≤1s，干预后恢复率≥85%。

### 交付物
- `consistency_guardian.py` — C02 行为/语言/关系三维监测
- `descend_manager.py` — F04 降临状态机+选项生成
- `DescentMode.tsx` — 降临UI（视角/记忆/关系/选项树）
- sandbox/__init__.py 更新导出
- main.py 新增API路由

## Criteria

### C02 角色一致性守护
- [x] ISC-1: consistency_guardian.py 定义3类检测维度
- [x] ISC-2: 行为一致性检测（动作是否匹配性格/身份/目标）
- [x] ISC-3: 语言风格检测（对话是否匹配角色设定语言风格）
- [x] ISC-4: 关系逻辑检测（互动是否符合已建立关系网络）
- [x] ISC-5: 偏离评分0-1，超阈值触发干预
- [x] ISC-6: LLM辅助修复prompt生成
- [x] ISC-7: 与模拟循环集成（每N回合检测）
- [x] ISC-8: API: GET /api/worlds/{id}/consistency/guardian

### F04 降临模式
- [x] ISC-9: descend_manager.py 状态机（idle/descending/active/exiting）
- [x] ISC-10: 降临/退出延迟≤3s
- [x] ISC-11: 降临后玩家行动不破坏NPC设定
- [x] ISC-12: ≥4个对话选项动态生成
- [x] ISC-13: 降临日志自动记录（时间/NPC/行动/影响）
- [x] ISC-14: API: POST /api/worlds/{id}/agents/{aid}/descend
- [x] ISC-15: API: DELETE /api/worlds/{id}/agents/{aid}/descend
- [x] ISC-16: API: POST /api/worlds/{id}/agents/{aid}/descend/act
- [x] ISC-17: API: GET /api/worlds/{id}/agents/{aid}/descend/status

### 前端
- [x] ISC-18: DescentMode.tsx NPC视角面板
- [x] ISC-19: NPC记忆快照展示
- [x] ISC-20: 关系状态可视化
- [x] ISC-21: 对话选项树（≥4选项）
- [x] ISC-22: 降临/退出按钮
- [x] ISC-23: 集成到App.tsx标签页

### 质量
- [x] ISC-24: 前端build 0错误
- [x] ISC-25: sandbox/__init__.py更新导出
- [ ] ISC-26: git commit
