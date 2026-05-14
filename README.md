# 沉浸式AI小说创作平台 (Chronicles of Creation)

> 基于多智能体模拟的下一代AI驱动小说创作引擎

## 核心特性

### 多LLM Provider支持
内置统一LLM接口，支持 DeepSeek、OpenAI、Kimi、MiniMax、智谱GLM、通义千问、腾讯混元、字节豆包等 providers。配置 `LLM_MODE=deepseek` 即可切换。

### P0 MVP 功能 (全部完成)

| 模块 | 状态 | 说明 |
|------|------|------|
| A01 沙盒模拟核心 | ✅ | 100回合模拟调度，10 NPC并发决策 |
| A02 事件日志系统 | ✅ | SQLite持久化+JSONL流式记录 |
| B01+B02 知识图谱 | ✅ | 角色/地点节点，关系边动态更新 |
| C01 智能体架构 | ✅ | 身份+性格+记忆流+行动决策 |
| F01 可视化图谱 | ✅ | WebSocket实时推送，前端免轮询 |
| G01 审美评分 | ✅ | 四维度行为一致性评测 |
| World Info | ✅ | Lorebook按NPC优先级预算分配 |

### P1 叙事引擎 (全部完成)

| 模块 | 状态 | 说明 |
|------|------|------|
| A03 反思模块 | ✅ | LLM驱动周期性深度反思 |
| A04 规划模块 | ✅ | LLM驱动中短期计划生成 |
| A05 叙事提取 | ✅ | 事件序列→起承转合四段结构 |
| E01 事件切片 | ✅ | 哈希分组快速筛选 |
| E02 三维评分 | ✅ | 意外性/逻辑性/情感评分 |
| E03 叙事重写 | ✅ | LLM生成可读章节文本 |
| C03 智能体对话 | ✅ | NPC间自然语言交互，写入记忆流 |

### 技术架构

```
backend/
├── app/
│   ├── core/
│   │   ├── sandbox/
│   │   │   ├── action_executor.py   # LLM Action执行器
│   │   │   ├── multi_llm_client.py  # 多Provider统一接口
│   │   │   ├── narrative_extractor.py  # A05 叙事提取
│   │   │   ├── story_sifter.py      # E01-E03 故事淘洗
│   │   │   ├── turn_scheduler.py    # 回合调度器
│   │   │   └── world_state.py       # 世界状态管理
│   │   ├── agent/
│   │   │   ├── agent.py             # 智能体核心
│   │   │   ├── dialogue.py          # C03 对话系统
│   │   │   ├── planner.py          # A04 规划模块
│   │   │   └── reflector.py        # A03 反思模块
│   │   ├── events/
│   │   │   ├── event_store.py      # 事件持久化
│   │   │   └── query_engine.py     # 事件查询
│   │   ├── knowledge/
│   │   │   ├── knowledge_graph.py # 知识图谱
│   │   │   ├── lorebook.py         # World Info
│   │   │   └── budget_manager.py   # 预算分配
│   │   └── scoring/
│   │       └── behavior_evaluator.py # 行为评分
│   └── main.py                      # FastAPI入口
└── tests/
    └── test_reflector_planner.py    # 单元测试
```

## 快速开始

### 1. 配置环境变量

```bash
# 复制配置模板
cp .env.example .env

# 编辑 .env 填入API Key
DEEPSEEK_API_KEY=your_key_here
LLM_MODE=deepseek  # 或 auto/kimi/openai
```

### 2. 启动后端

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 3. 验证服务

```bash
curl http://localhost:8000/health
```

## API 端点

### 世界管理
| 方法 | 端点 | 说明 |
|------|------|------|
| GET | /api/worlds | 列出世界 |
| POST | /api/worlds | 创建世界 (name + template: cultivation/wuxia/urban) |
| GET | /api/worlds/{id} | 获取世界详情 (含NPC列表) |
| GET | /api/worlds/{id}/events | 查询事件日志 |
| GET | /api/worlds/{id}/metrics | 运行指标 |

### 模拟控制
| 方法 | 端点 | 说明 |
|------|------|------|
| POST | /api/simulate/start | 启动模拟 (后台100回合) |
| POST | /api/simulate/stop | 停止模拟 |
| GET | /api/simulate/status | 查询状态 |
| WS | /ws/{world_id} | WebSocket实时事件流 |

### P1 叙事引擎
| 方法 | 端点 | 说明 |
|------|------|------|
| POST | /api/narrative/extract | A05 叙事提取 (起承转合) |
| POST | /api/story/sift | E01-E03 故事淘洗 (切片+评分) |
| POST | /api/story/rewrite | E03 叙事重写 (LLM章节) |
| POST | /api/dialogue/generate | C03 NPC对话生成 |
| POST | /api/dialogue/history | 获取对话历史 |

### P1 评测分析
| 方法 | 端点 | 说明 |
|------|------|------|
| GET | /api/worlds/{id}/behavior | 行为一致性评测 |
| GET | /api/worlds/{id}/budget | Lorebook预算使用 |

## 验收标准

| 条件 | 阈值 | 状态 |
|------|------|------|
| 10个NPC存活100回合 | 必须 | ✅ |
| 非预设互动 ≥3 | ≥3 | ✅ |
| 故事感时刻 ≥1 | ≥1 | ✅ |
| 单回合延迟 <15s | <15s | ✅ |

## 端到端测试

```bash
# 创建世界
curl -X POST http://localhost:8000/api/worlds \
  -H "Content-Type: application/json" \
  -d '{"name":"测试世界","template":"urban"}'

# 启动模拟
curl -X POST http://localhost:8000/api/simulate/start \
  -H "Content-Type: application/json" \
  -d '{"world_id":"your_world_id"}'

# 等待几秒后查询事件
curl "http://localhost:8000/api/worlds/your_world_id/events?limit=10"

# 叙事提取
curl -X POST http://localhost:8000/api/narrative/extract \
  -H "Content-Type: application/json" \
  -d '{"world_id":"your_world_id","min_turn":1,"max_turn":5}'

# NPC对话
curl -X POST http://localhost:8000/api/dialogue/generate \
  -H "Content-Type: application/json" \
  -d '{"world_id":"your_world_id","speaker_a_id":"boss_shen","speaker_b_id":"partner_bai","topic":"案件讨论"}'
```

## 技术栈

- **后端**: FastAPI + uvicorn + SQLAlchemy + aiosqlite
- **LLM**: 多Provider统一接口 (DeepSeek/OpenAI/Kimi/MiniMax/GLM/Qwen/Hunyuan/Doubao)
- **前端**: React + WebSocket实时推送
- **存储**: SQLite + JSONL双轨持久化
- **测试**: pytest + asyncio

## 项目状态

- **P0 MVP**: ✅ 全部完成 (7/7 验收标准达标)
- **P1 叙事引擎**: ✅ 全部完成 (A03/A04/A05 + E01/E02/E03 + C03)
- **P2 协作编辑**: 规划中
- **P3 多模态输出**: 规划中