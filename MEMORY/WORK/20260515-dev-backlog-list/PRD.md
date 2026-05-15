---
task: 列出项目待开发清单
slug: 20260515-dev-backlog-list
effort: Standard
phase: complete
progress: 10/10
mode: ALGORITHM
started: 2026-05-15T17:00:00
updated: 2026-05-15T17:00:00
---

## Context

用户要求列出当前项目的待开发清单。项目为沉浸式AI小说创作平台，基于PRD 28项需求。
当前：Phase 2 P0全部完成，部分P1已提前实现，Pre-Sprint部分完成，Sprint 1-2的代码文件已创建但集成度不一。

## Criteria

- [x] ISC-1: 已完成需求准确列出（含状态标记）
- [x] ISC-2: 进行中需求列出（含文件状态）
- [x] ISC-3: 未开始P1需求列出（按Sprint分组）
- [x] ISC-4: P2远期需求列出
- [x] ISC-5: 基础设施缺口识别
- [x] ISC-6: 前端待开发组件列出
- [x] ISC-7: 当前未提交的代码变更说明
- [x] ISC-8: 按优先级排序的下一步建议
- [x] ISC-9: 依赖关系标注
- [x] ISC-10: 清单输出给用户

## Decisions

- 使用Standard effort，这是梳理/列表任务
- 基于git status + git log + 文件内容综合判断完成度
