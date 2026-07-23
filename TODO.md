# 患者端多 Agent Graph 设计（TODO）

## 总览

三个专科 Agent：

| Agent | 意图标签 | 职责 |
|------|---------|------|
| 知识问答 | `knowledge` | 医疗知识 / 就诊须知 / 科普（RAG） |
| 院内信息 | `hospital_info` | 地址导航、科室位置、师资与医生介绍 |
| Tool | `tool` | 挂载业务工具（查号源、挂号等），写操作需确认 |

拓扑：`Router`（起步）→ 后续可加 Handoffs。

---

## 详细流程图

```mermaid
flowchart TD
  START([用户消息进入<br/>POST /chat]) --> auth[鉴权 / 注入上下文<br/>user_id · patient_id · token]

  auth --> guard{安全护栏}

  %% —— 安全护栏分支 ——
  guard -->|危急症状关键词<br/>胸痛/大出血/意识不清等| emergency[急诊引导节点<br/>固定话术 + 建议立即就医/人工]
  guard -->|违规/越权请求| reject[拒绝节点<br/>说明原因后结束]
  guard -->|通过| load_mem[加载会话状态<br/>messages · active_agent · slots]

  load_mem --> router[意图路由节点<br/>规则优先 + LLM 兜底]

  %% —— 路由出口 ——
  router -->|knowledge| kb_prep[知识问答 · 准备<br/>改写查询 / 构造检索 query]
  router -->|hospital_info| info_prep[院内信息 · 准备<br/>解析院区/科室/医生实体]
  router -->|tool| tool_prep[Tool · 准备<br/>解析办事意图与槽位]
  router -->|clarify / 低置信| clarify[追问澄清节点<br/>问清意图后回到路由]
  router -->|跨域复合意图<br/>如科普+挂号| multi[多跳编排<br/>按顺序调用多个 Agent]

  %% —— 知识问答 Agent ——
  kb_prep --> kb_retrieve[知识库检索 RAG<br/>向量检索 + 可选重排]
  kb_retrieve --> kb_gen[知识问答 Agent<br/>基于检索结果生成回答<br/>附免责声明]
  kb_gen --> reply

  %% —— 院内信息 Agent ——
  info_prep --> info_retrieve[结构化检索<br/>科室/医生/地址/师资目录]
  info_retrieve --> info_gen[院内信息 Agent<br/>整理地址/导航/简介]
  info_gen --> reply

  %% —— Tool Agent ——
  tool_prep --> tool_agent[Tool Agent<br/>create_agent + tools]
  tool_agent --> tool_loop{是否还有 tool_calls?}
  tool_loop -->|是 · 只读工具| exec_read[执行只读工具<br/>查号源/查医生/查账单等]
  exec_read --> tool_agent
  tool_loop -->|是 · 写操作工具<br/>挂号/取消/支付| hitl{写操作需用户确认?}
  tool_loop -->|否 · 已得到最终答案| reply

  hitl -->|需要确认<br/>pending_action 未确认| confirm[待确认卡片<br/>返回前端展示摘要]
  hitl -->|已确认 / 或配置为免确认| exec_write[执行写工具<br/>调用 Java 业务 API]
  exec_write --> tool_agent

  confirm --> WAIT([等待用户下一轮确认<br/>checkpointer 保留状态])
  WAIT -->|用户确认| exec_write
  WAIT -->|用户取消| cancel_act[取消待办<br/>清理 pending_action]
  cancel_act --> reply

  %% —— 多跳 ——
  multi --> kb_prep
  multi --> info_prep
  multi --> tool_prep

  %% —— 统一出口 ——
  clarify --> router
  emergency --> END([结束本轮])
  reject --> END
  reply[统一回复节点<br/>拼装 reply · citations · actions] --> persist[落库/更新 checkpointer<br/>写回 messages]
  persist --> END
```

---

## 节点职责清单

### 1. `auth` — 鉴权与上下文注入
- [ ] 从 Header / Java 网关解析用户身份
- [ ] 注入 `user_id`、`patient_id`（无档案则后续 Tool 引导建档）
- [ ] 失败则直接 401，不进入 Graph

### 2. `guard` — 安全护栏
- [ ] 危急症状词表拦截 → `emergency`
- [ ] 越权/敏感操作拦截 → `reject`
- [ ] 医疗免责：知识问答路径强制 disclaimer

### 3. `router` — 意图路由
- [ ] 输出：`knowledge` | `hospital_info` | `tool` | `clarify`
- [ ] 规则优先（关键词），低置信再用 LLM 分类
- [ ] 复合意图可走 `multi`（第一版可降级为追问主意图）

### 4. `kb_*` — 知识问答 Agent
- [ ] 检索医疗知识库（Qdrant 等）
- [ ] 仅基于检索片段回答，拒绝对无依据的确诊表述
- [ ] 返回：`reply` + 可选 `citations`

### 5. `info_*` — 院内信息 Agent
- [ ] 查院区地址、楼层导航、科室简介、医生/师资介绍
- [ ] 数据源：结构化目录 API 或专用知识集合
- [ ] 不做挂号/缴费等写操作

### 6. `tool_*` — Tool Agent
- [ ] 使用 `create_agent(model, tools=[...])`
- [ ] 只读工具可直接执行
- [ ] 写操作进入 HITL：`pending_action` → 前端确认卡片 → 再执行
- [ ] 工具结果回灌 messages，直到无 tool_calls

### 7. `clarify` / `reply` / `persist`
- [ ] `clarify`：一次只问一个关键缺失信息，然后回到 `router`
- [ ] `reply`：统一对外结构 `{ reply, intent, actions?, citations? }`
- [ ] `persist`：会话与 `pending_action` 写入 checkpointer

---

## State 字段（对应 `agent/graph/states.py`）

```text
messages          # 对话历史
user_id           # 登录用户
patient_id        # 就诊人（可空）
intent            # knowledge | hospital_info | tool | clarify | emergency
active_agent      # 当前专科
slots             # 办事槽位：科室/日期/医生等
rag_docs          # 知识库命中
hospital_facts    # 院内信息命中
pending_action    # 待确认写操作 {tool, args, summary}
tool_results      # 最近工具返回
safe_flags        # 护栏命中标记
```

---

## 文件落地（对应现有目录）

```text
AI/app/agent/graph/
  states.py      # State 定义
  nodes.py       # auth / guard / router / kb / info / tool / hitl / reply
  workflow.py    # StateGraph 组装与条件边
AI/app/chain/qa.py   # 可先作为知识问答核心，再拆出 info / tool
AI/app/router/chat.py  # 入口改为调用 workflow.invoke / astream
```

---

## 实现顺序建议

1. [ ] 定义 `states.py` + 空壳 `workflow`（router 先写死规则）
2. [ ] 接通知识问答（现有 `qa.py` + RAG 可后补）
3. [ ] 接通院内信息检索（mock 数据亦可）
4. [ ] Tool Agent：先挂只读工具
5. [ ] HITL：写操作确认卡片
6. [ ] checkpointer 多轮会话
7. [ ] 危急护栏与免责声明打磨
```
