# 沉浸式AI小说创作平台 (Chronicles of Creation)

> 让AI角色在模拟世界中自由生活、互动、产生故事 — 自动生成小说素材

## 这是什么

一个**AI多智能体模拟引擎**。你创建一个世界模板（修仙/武侠/都市），放入10个AI角色，引擎让它们在世界里自主决策、互相交流、产生事件。跑完100回合后，你得到：

- 📖 **剧情素材**：AI角色之间自然生成的对话和情节
- 🗺️ **世界观**：自动构建的角色关系图谱和地点网络
- 📊 **评测报告**：每个角色的行为一致性评分（是否符合人设）

## 核心能力

### AI角色自主模拟
10个NPC同时运行，每个都有自己的身份、性格、记忆和目标。它们会：
- 根据当前处境做决策
- 与其他角色互动（合作/对抗/谈判）
- 产生"故事时刻"（有戏剧张力的情节）
- 写日记反思自己的行为

### 多LLM驱动
支持 DeepSeek / OpenAI / Kimi / MiniMax / 智谱 等多家大模型。角色行动、对话生成、叙事重写都调用真实LLM API。

### 叙事提取
把100回合的事件流，转化为「起承转合」的小说章节结构。

### 故事淘洗
从海量事件中找出最有价值的叙事切片，按「意外性」「逻辑性」「情感强度」排序。

### NPC对话生成
让任意两个AI角色围绕特定话题展开对话，生成自然语言交互，写入双方记忆流。

### 小说导出
将模拟产生的事件和对话，导出为带章节结构的Markdown小说文本。

### 角色自定义
创建世界后，可修改任意NPC的名称、身份、性格，使其更符合你的创作需求。

### 世界重置
不必重新创建世界，直接重置到初始状态，保留你的角色配置设定，重新运行模拟。

### 模拟控制
支持暂停/恢复/单步执行模拟，更精细地控制模拟进度。

### 事件搜索
按关键词搜索历史事件，快速定位特定情节。

### 角色关系
查看所有NPC之间的关系网络和互动统计。

## 使用场景

**写小说卡文？**
让AI角色跑一遍，他们自己会产生各种情节冲突。你从中挑选灵感。

**构建世界观？**
AI会自动生成角色关系、势力纠葛、地点描写。你来定框架，AI填充细节。

**测试人设？**
把角色丢进不同情境，看它们的行为是否符合你设定的性格。

## 快速开始

```bash
# 1. 克隆项目
git clone https://github.com/acewan-kai/Chronicles-of-Creation.git
cd Chronicles-of-Creation

# 2. 配置LLM
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY

# 3. 启动后端
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 4. 打开浏览器
# 访问 http://localhost:8000/docs 查看API文档
```

## 一个完整例子

```bash
# 创建都市奇幻世界
curl -X POST http://localhost:8000/api/worlds \
  -H "Content-Type: application/json" \
  -d '{"name":"深夜事务所","template":"urban"}'

# 启动模拟（AI角色开始自主行动）
curl -X POST http://localhost:8000/api/simulate/start \
  -H "Content-Type: application/json" \
  -d '{"world_id":"刚得到的world_id"}'

# 等几秒后查询事件
curl http://localhost:8000/api/worlds/{world_id}/events?limit=10

# 让两个角色对话
curl -X POST http://localhost:8000/api/dialogue/generate \
  -H "Content-Type: application/json" \
  -d '{"world_id":"{world_id}","speaker_a_id":"boss_shen","speaker_b_id":"partner_bai","topic":"案件讨论"}'

# 自定义角色
curl -X PATCH http://localhost:8000/api/worlds/{world_id}/agents/boss_shen \
  -H "Content-Type: application/json" \
  -d '{"name":"沈夜所长","personality":"更加沉稳老练"}'

# 导出小说
curl -X POST http://localhost:8000/api/novel/export \
  -H "Content-Type: application/json" \
  -d '{"world_id":"{world_id}","start_turn":1,"end_turn":20,"format":"markdown"}'

# 重置世界（重新运行）
curl -X POST http://localhost:8000/api/worlds/{world_id}/reset \
  -H "Content-Type: application/json"

# 暂停/恢复模拟
curl -X POST http://localhost:8000/api/simulate/pause \
  -H "Content-Type: application/json" \
  -d '{"world_id":"{world_id}"}'

curl -X POST http://localhost:8000/api/simulate/resume \
  -H "Content-Type: application/json" \
  -d '{"world_id":"{world_id}"}'

# 单步执行
curl -X POST http://localhost:8000/api/simulate/step \
  -H "Content-Type: application/json" \
  -d '{"world_id":"{world_id}","turns":5}'

# 查看角色关系
curl http://localhost:8000/api/worlds/{world_id}/relationships

# 搜索事件
curl "http://localhost:8000/api/worlds/{world_id}/events/search?q=关键词"
```

## 技术栈

- **后端**：Python + FastAPI + SQLite
- **LLM**：多Provider统一接口（DeepSeek为主）
- **前端**：React + WebSocket
- **存储**：SQLite持久化 + JSONL流式记录

## 项目结构

```
backend/
├── app/
│   ├── core/
│   │   ├── sandbox/     # 模拟引擎核心
│   │   ├── agent/       # AI角色（记忆/规划/反思/对话）
│   │   ├── events/      # 事件日志
│   │   ├── knowledge/   # 知识图谱 + Lorebook
│   │   └── scoring/     # 行为一致性评分
│   └── main.py          # API入口
└── tests/               # 单元测试
```