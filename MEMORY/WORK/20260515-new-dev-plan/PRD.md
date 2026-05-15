---
task: 根据PRD需求重新制定完整研发计划
slug: 20260515-new-dev-plan
effort: Extended
phase: complete
progress: 16/16
mode: ALGORITHM
started: 2026-05-15T10:10:00
updated: 2026-05-15T10:10:00
---

## Context

用户要求基于完整PRD（28项需求，7大模块）和当前代码现状，重新制定详细研发计划。
当前：Phase 2 P0全部完成，部分P1已提前实现，需要为剩余P1+P2制定有序的Sprint计划。

### 已完成（不在计划范围内）
P0全部（A01/A02/B01/B02/C01/F01/G01_basic），
P1提前完成：A03/A04（LLM化）/A05/C03/D01/E01-E03

### 需要计划的
- 基础设施：数据持久化、用户认证
- P1剩余：B03/B04/B05/C02/D02/D03/F02/F03/F04/G02/G03/G04/G05
- P2全部：B05(P1→P2)/C04/D04/E04/F05/F06/G06/G07

## Criteria

- [x] ISC-1: 当前已完成需求准确列出（按PRD编号）
- [x] ISC-2: 基础设施缺口识别并优先级明确
- [x] ISC-3: P1剩余需求按依赖关系排序
- [x] ISC-4: Sprint 1 内容和交付物明确
- [x] ISC-5: Sprint 2 内容和交付物明确
- [x] ISC-6: Sprint 3 内容和交付物明确
- [x] ISC-7: Sprint 4 内容和交付物明确
- [x] ISC-8: Sprint 5 内容和交付物明确
- [x] ISC-9: Sprint 6 内容和交付物明确
- [x] ISC-10: P2功能规划路径明确
- [x] ISC-11: 每个Sprint标注依赖关系和前置条件
- [x] ISC-12: 每个Sprint标注估算工作量
- [x] ISC-13: 北极星指标在各Sprint中的关联映射
- [x] ISC-14: Alpha/Beta测试里程碑节点明确
- [x] ISC-15: 技术风险和缓解措施列出
- [x] ISC-16: 计划文档写入 docs/ 目录

## Decisions

- 以PRD需求编号为准（非Roadmap编号）统一引用
- Sprint时长约2-3周，适合小团队/solo开发节奏
- 品味学习（G02-G05）是最高差异化价值，排在前端UI之前

## Verification

每条ISC在VERIFY阶段逐一检查计划文档内容。
