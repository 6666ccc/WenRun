# 快速模式去掉院内 RAG

日期：2026-09-03  
状态：已确认，按方案 A 实施

## 背景

快速模式最初挂了 `search_hospital_knowledge`（Qdrant）和 `web_search`（Tavily）。院内检索会多一轮 Embedding + 向量查询，且提示词要求「用药必须先查院内库」。产品意图是：快速模式只有闲聊、联网和会话记忆，不引入 RAG。

## 决策

- 快速模式只挂 `web_search`。
- 记忆不变：`conversationId` 作为 `thread_id`，与正常模式共用 checkpoint。
- 正常模式的 `knowledge_node` / Qdrant 不动。
- `search_hospital_knowledge` 工具模块保留，供正常模式或测试使用，但不得出现在 `FAST_TOOLS` 里。

## 回答边界

| 患者问 | 快速模式 |
| --- | --- |
| 你好、谢谢、陪聊 | 不调工具，直接短答 |
| 感冒吃什么药、护理、要不要就医 | 可调用 `web_search`；文末「参考来源」；声明不能代替面诊 |
| 儿科几楼、就诊须知、号源排班、科室医生、我的预约 | 拒答，请关闭快速模式 |
| 挂号 / 退号 / 缴费 | 不代办，引导到页面 |

关闭快速模式后：号源排班走只读 Tool；楼层 / 须知走院内 RAG。

## 非目标

- 不为寒暄单独做无工具短路径（方案 B）。
- 不删除院内知识库工具或 `knowledge_node`。
- 不改 Java 网关字段或前端 `fastMode` 开关形态。
