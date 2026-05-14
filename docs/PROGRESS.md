# 项目进度文档

> 最后更新: 2026-05-14 12:00 (目录结构重构完成 + 部署脚本更新)

## 快速恢复指南（下次开工读这里）

```
服务器: ssh -i C:/Users/18380/.ssh/claw.pem ubuntu@170.106.194.111
后端重启: ssh -i C:/Users/18380/.ssh/claw.pem ubuntu@170.106.194.111 "cd ~/p0-mvp-backend && nohup ~/p0-mvp-venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/uvicorn.log 2>&1 &"
前端部署: cd frontend && npx vite build && scp -i C:/Users/18380/.ssh/claw.pem -r dist/* ubuntu@170.106.194.111:~/p0-mvp-frontend/
代码已提交: ✅ git commit完成 (2026-05-14)
当前状态: P0 MVP部署验收完成，Sprint 1 90% + Sprint 2 95% + Sprint 3 75%
下一优先: S2-6 World Info预算管理 + S2-7 行为一致性评测 + S3-5 WebSocket实时推送
项目结构: 标准布局 (backend/ + frontend/ + tools/ + docs/ + archive/)
```

---

## 一、项目概述

**项目名称**: 沉浸式AI小说创作平台  
**项目阶段**: P0 MVP — Sprint 1收尾 / Sprint 2起步  
**目标**: 基于LLM的沉浸式小说创作引擎

## 二、访问地址

| 地址 | 说明 |
|------|------|
| **http://170.106.194.111/** | 前端界面（nginx → 直连后端API） |
| http://170.106.194.111:8000 | API直连 |
| http://170.106.194.111:8000/docs | Swagger中文文档 |

## 三、Sprint完成度总览

### Sprint 1: 沙盒引擎 + 事件日志 — ✅ 90%

| # | 任务 | 状态 |
|---|------|------|
| S1-1 | WorldState与模板世界集成 | ✅ 3模板×10角色×8地点 |
| S1-2 | TurnScheduler并发 | ✅ 10NPC并行运行 |
| S1-3 | SQLite+JSONL双写 | ✅ EventStore实现 |
| S1-4 | 事件查询引擎API | ✅ 5种查询模式 |
| S1-5 | LLM适配层(DeepSeek/OpenAI/Mock) | ✅ 三模式可切换 |
| S1-6 | 端到端测试 | ✅ 创建→启动→事件→停止 |

### Sprint 2: 智能体 + 知识图谱 — ✅ 95%

| # | 任务 | 状态 |
|---|------|------|
| S2-1 | MemoryStream遗忘曲线 | ✅ 艾宾浩斯公式, avg_retention=80.7% |
| S2-2 | Planner LLM集成 | ✅ LLM生成3步计划, 角色化Mock fallback |
| S2-3 | Reflector周期性反思 | ✅ LLM驱动角色化反思, 三级fallback链, agent存储 |
| S2-4 | KnowledgeGraph动态更新 | ✅ 互动事件驱动关系边创建/权重变化/类型升级 |
| S2-5 | Lorebook上下文注入 | ✅ 模板自动构建词条, NPC prompt注入(600字限制) |
| S2-6 | World Info预算管理 | ❌ |
| S2-7 | 行为一致性评测 | ❌ |

### Sprint 3: 前端仪表盘 — ✅ 75%

| # | 任务 | 状态 |
|---|------|------|
| S3-1 | WorldGraph动态数据源 | ✅ **本次完成** |
| S3-2 | MetricsPanel实时数据 | ⚠️ 组件已有 |
| S3-3 | AgentList详情面板 | ✅ **本次完成** |
| S3-4 | EventTimeline筛选 | ✅ 搜索框+角色下拉+回合范围+分页+高亮 |
| S3-5 | WebSocket实时推送 | ❌ |
| S3-6 | **创建世界UI** | ✅ **本次完成** |
| S3-7 | 端到端UI验收 | ❌ |

## 四、后端实际完成清单

### 路由 (38条，/api前缀 + 无前缀两套)

| 分组 | 路由 | 方法 |
|------|------|------|
| 基础 | `/`, `/health`, `/info` | GET |
| 模板 | `/templates` | GET |
| 小说 | `/books`, `/books/{id}` | GET/POST |
| 世界 | `/worlds`, `/worlds/{id}`, `/worlds/{id}/events`, `/worlds/{id}/metrics` | GET/POST |
| 模拟 | `/simulate/start`, `/simulate/stop`, `/simulate/status` | POST/GET |

### 核心模块 (19个py文件)

| 模块 | 文件 | 状态 |
|------|------|------|
| sandbox/ | world_state, turn_scheduler, action_executor, event_dispatcher | ✅ |
| events/ | event_store(SQLite+JSONL), query_engine | ✅ |
| knowledge/ | knowledge_graph, lorebook | ✅ 动态关系更新 |
| agent/ | agent(MemoryStream), planner(简化), reflector(简化) | ⚠️ 骨架 |
| scoring/ | scorer(AestheticScorer) | ✅ |
| - | onboarding, usage_tracker | ✅ |

### LLM支持
- MockLLMClient (测试用，免API Key)
- DeepSeekClient (国产低价)
- OpenAIClient (本次新增)
- 自动切换: DEEPSEEK_API_KEY → OPENAI_API_KEY → Mock降级

## 五、前端实际完成清单

| 组件 | 状态 | 说明 |
|------|------|------|
| App.tsx | ✅ | 主应用，含创建世界+世界选择+模拟控制 |
| CreateWorldModal | ✅ **本次新增** | 模板选择(3个)+名称输入+API调用 |
| WorldGraph | ✅ **本次改造** | 动态节点，从worldData.agents/locations构建 |
| EventTimeline | ⚠️ | 事件列表，缺筛选/搜索 |
| AgentList | ✅ **本次改造** | 展示真实agent数据(name/identity/location/memory) |
| MetricsPanel | ⚠️ | 指标面板，数据接入待验证 |
| OnboardingGuide | ✅ | 引导页，世界为空时显示 |
| api.ts | ✅ | DEV用/api代理，PROD直连远程 |

## 六、待办事项（按优先级）

### P0 紧急 — ✅ 全部完成 (2026-05-13)
- [x] ~~前端创建世界UI~~
- [x] ~~WorldGraph替换硬编码节点为API动态数据~~ ✅ 2026-05-12
- [x] ~~AgentList接入真实NPC数据~~ ✅ 2026-05-12
- [x] ~~部署到测试服务器验证~~ ✅ 2026-05-13 后端重启+API全量验证
- [x] ~~前端浏览器端到端走通~~ ✅ 2026-05-13 API层全流程验证通过
- [x] ~~git commit~~ ✅ 2026-05-13

### P1 重要
- [x] Planner LLM集成 ✅ S2-2
- [x] MemoryStream遗忘曲线 ✅ S2-1
- [x] EventTimeline添加筛选 ✅ S3-4

### P2 一般
- [x] KnowledgeGraph关系动态更新 ✅ S2-4
- [x] Lorebook上下文注入到模拟循环 ✅ S2-5
- [x] 前端EventTimeline搜索/分页 ✅ S3-4
- [ ] MetricsPanel接入go_status等验收指标

### P3 优化
- [ ] WebSocket实时推送
- [ ] 性能优化（单回合延迟目标<5s）
- [ ] 正式环境部署（HTTPS + 域名）

## 七、部署信息

| 项目 | 信息 |
|------|------|
| 服务器 | 腾讯云CVM 170.106.194.111 |
| SSH | `ssh -i ~/.ssh/claw.pem ubuntu@170.106.194.111` |
| 后端目录 | /home/ubuntu/p0-mvp-backend/app/ |
| 前端目录 | /home/ubuntu/p0-mvp-frontend/ |
| 虚拟环境 | /home/ubuntu/p0-mvp-venv/ |
| 后端端口 | 8000 (uvicorn) |
| 前端端口 | 80 (nginx) |
| nginx配置 | /etc/nginx/sites-enabled/default |

## 八、目录结构重构 (2026-05-14) ✅

已从阶段命名布局重构为标准项目布局，部署脚本已同步更新：

```
重构前:  p0-mvp/backend/  p0-mvp/frontend/  poc-sandbox/
重构后:  backend/         frontend/         archive/poc-sandbox/
新增:    tools/ (deploy.bat, deploy.ps1, install.sh)
```

## 九、技术选型

| 层级 | 技术 | 
|------|------|
| 后端框架 | FastAPI 0.136 |
| Python | 3.12 |
| 数据库 | SQLite (aiosqlite) + JSONL |
| 图计算 | networkx 3.6 |
| LLM | DeepSeek / OpenAI / Mock |
| 前端框架 | React 18 |
| 构建工具 | Vite 5 |
| 图可视化 | Cytoscape.js |
| HTTP客户端 | axios |
