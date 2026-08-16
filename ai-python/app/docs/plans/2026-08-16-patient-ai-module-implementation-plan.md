# 患者端 AI 模块 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现一个由意图路由 Agent、谈心 Agent、医院 Agent 和医疗知识 Agent 组成的患者端 LangGraph，并打通可追溯 RAG、会话记忆、Java Tool、挂号 HITL 与前端 SSE 交互。

**Architecture:** FastAPI 承载 LangGraph、RAG、checkpoint 和 SSE；医院业务数据始终通过 Spring Boot 内部 AI Tool API 访问。Java 保留现有 UUID 登录令牌，在认证患者后签发短期委托 JWT；前端只访问 Java，并通过结构化 SSE 完成引用展示和 interrupt 恢复。

**Tech Stack:** Python 3.11、FastAPI、LangGraph、LangChain、DashScope OpenAI-compatible API、Qdrant、SQLite checkpoint、pytest；Java 17、Spring Boot 3.5、MyBatis、Nimbus JOSE JWT、JUnit 5；Vue 3、Vite、Node test。

## Global Constraints

- Python 不直接访问医院业务数据库。
- 保留当前 `AuthTokenStore` UUID 登录机制，不把全站认证迁移为 JWT。
- Java → Python 使用 `X-Api-Key`；Python → Java AI Tool 使用短期委托 JWT。
- 初始委托令牌只有 `dept:read`、`doctor:read`、`schedule:read`；患者确认后才签发 `registration:create`。
- 委托令牌只通过请求头和 LangGraph 运行配置传递，不进入 State、checkpoint、日志、聊天记录或 Qdrant。
- 意图值统一为 `chat | hospital | medical`。
- 医院、医疗、会话记忆分别使用 `wenrun_hospital_custom`、`wenrun_medical_general`、`wenrun_conversation_memory`。
- 医疗 Agent 不诊断、不开药、不提供具体处方剂量；越界请求自然说明权限边界。
- 查询 Tool 可直接执行；创建挂号必须经过 LangGraph `interrupt`。
- RAG 事实必须带引用，Tool 事实必须带工具名和查询时间；证据不足时不得编造。
- 首期记忆仅限当前 `conversationId`。
- 所有写操作必须具有幂等保护，并由 Java 做最终业务校验。
- 本计划中的 Git commit 步骤仅在用户明确授权提交时执行。

---

## File Structure

### Python：新建

- `ai-python/app/core/config.py`：集中读取环境配置。
- `ai-python/app/core/llm.py`：创建可注入的聊天模型和 embedding。
- `ai-python/app/api/dependencies/auth.py`：校验 Java 调 Python 的内部 API Key。
- `ai-python/app/api/dependencies/runtime.py`：读取请求级委托令牌。
- `ai-python/app/api/routes/health.py`：健康检查。
- `ai-python/app/api/routes/knowledge.py`：Word/PDF 入库与删除。
- `ai-python/app/models/sse.py`：六类 SSE 事件。
- `ai-python/app/models/source.py`：RAG/Tool 来源模型。
- `ai-python/app/models/knowledge.py`：知识库接口模型。
- `ai-python/app/services/chat_service.py`：invoke、stream 和 resume 门面。
- `ai-python/app/services/sse.py`：SSE 编码。
- `ai-python/app/services/java_tools/`：Java Tool HTTP client 与四个 Tool。
- `ai-python/app/services/memory/window.py`：短期窗口。
- `ai-python/app/services/memory/vector.py`：当前会话向量记忆。
- `ai-python/app/rag/collections.py`：collection 常量。
- `ai-python/app/rag/ingest.py`：文档解析、切片和幂等入库。
- `ai-python/app/graphs/hospital/checkpoint.py`：SQLite checkpointer。
- `ai-python/app/graphs/hospital/nodes/clarify_node.py`：含糊意图澄清。
- `ai-python/app/graphs/hospital/nodes/hospital_node.py`：医院 Agent。
- `ai-python/app/graphs/hospital/nodes/medical_node.py`：医疗知识 Agent。
- `ai-python/app/graphs/hospital/nodes/citation_validate_node.py`：引用与安全校验。
- `ai-python/app/graphs/hospital/nodes/registration_interrupt_node.py`：挂号暂停、恢复与执行。
- `ai-python/app/graphs/hospital/prompts/*.py`：四个 Agent 的 Prompt。
- `ai-python/tests/`：unit、integration、contract 测试。

### Python：修改

- `ai-python/pyproject.toml`、`requirements.txt`、`Dockerfile`、`README.md`
- `ai-python/app/main.py`
- `ai-python/app/api/routes/chat.py`
- `ai-python/app/models/chat.py`
- `ai-python/app/models/intent_result.py`
- `ai-python/app/graphs/hospital/state.py`
- `ai-python/app/graphs/hospital/graph.py`
- `ai-python/app/graphs/hospital/nodes/chat_node.py`
- `ai-python/app/graphs/hospital/nodes/intent_judgment_node.py`
- `ai-python/app/graphs/hospital/nodes/memory_node.py`
- `ai-python/app/rag/qdrant.py`
- `ai-python/app/rag/rag.py`

删除演示实现：

- `ai-python/app/graphs/hospital/tools/test_tool.py`
- `ai-python/app/graphs/hospital/nodes/tool_node.py`
- `ai-python/app/graphs/hospital/nodes/knowledge_node.py`

### Java：新建

- `backend-java/src/main/java/com/wenrun/ai/delegation/AiDelegationProperties.java`
- `backend-java/src/main/java/com/wenrun/ai/delegation/AiDelegationClaims.java`
- `backend-java/src/main/java/com/wenrun/ai/delegation/AiDelegationTokenService.java`
- `backend-java/src/main/java/com/wenrun/ai/tools/interceptor/DelegatedJwtInterceptor.java`
- `backend-java/src/main/java/com/wenrun/ai/tools/controller/AiToolsInternalController.java`
- `backend-java/src/main/java/com/wenrun/ai/tools/service/AiToolsRegistrationService.java`
- `backend-java/src/main/java/com/wenrun/ai/tools/dto/AiToolRegistrationCreateDTO.java`
- `backend-java/src/main/java/com/wenrun/ai/tools/vo/AiToolErrorVO.java`
- `backend-java/src/main/java/com/wenrun/ai/dto/ChatResumeRequestDTO.java`
- `backend-java/src/main/java/com/wenrun/ai/dto/PythonChatRequestDTO.java`
- `backend-java/src/main/java/com/wenrun/ai/dto/AiUserContextDTO.java`
- `backend-java/src/main/java/com/wenrun/ai/vo/ChatCitationVO.java`
- `backend-java/src/main/java/com/wenrun/ai/vo/ChatInterruptVO.java`
- `backend-java/src/main/java/com/wenrun/ai/service/ConversationOwnershipService.java`
- `docs/SQL/migrations/2026-08-16-registration-idempotency.sql`
- 对应的 Java 测试类。

### Java：修改

- `backend-java/src/main/java/com/wenrun/config/AuthInterceptor.java`
- `backend-java/src/main/java/com/wenrun/config/WebMvcConfig.java`
- `backend-java/src/main/java/com/wenrun/ai/config/AiServiceProperties.java`
- `backend-java/src/main/java/com/wenrun/ai/config/AiHttpClientConfig.java`
- `backend-java/src/main/java/com/wenrun/ai/client/AiServiceClient.java`
- `backend-java/src/main/java/com/wenrun/ai/controller/AiChatController.java`
- `backend-java/src/main/java/com/wenrun/ai/service/AiChatService.java`
- `backend-java/src/main/java/com/wenrun/ai/service/serviceImpl/AiChatServiceImpl.java`
- `backend-java/src/main/java/com/wenrun/ai/dto/ChatRequestDTO.java`
- `backend-java/src/main/java/com/wenrun/ai/vo/ChatStreamEventVO.java`
- `backend-java/src/main/java/com/wenrun/entity/Registration.java`
- `backend-java/src/main/java/com/wenrun/repository/RegistrationRepository.java`
- `backend-java/src/main/java/com/wenrun/repository/ChatMessageRepository.java`
- `backend-java/src/main/resources/mapper/RegistrationRepository.xml`
- `backend-java/src/main/resources/mapper/ChatMessageRepository.xml`
- `backend-java/src/main/resources/application.yml`
- `docs/SQL/schema.sql`

### Frontend

- 修改 `frontend/src/api/modules/ai.js`
- 修改 `frontend/src/composables/useAssistant.js`
- 修改 `frontend/src/features/assistant/session.js`
- 修改 `frontend/src/views/Assistant.vue`
- 修改 `frontend/src/views/shared/views.css`
- 修改 `frontend/src/api/index.js`
- 修改 `frontend/package.json`
- 新建 `frontend/src/features/assistant/citation.js`
- 新建 `frontend/src/features/assistant/interrupt.js`
- 新建 `frontend/src/components/CitationList.vue`
- 新建 `frontend/src/components/InterruptConfirm.vue`
- 修改 `frontend/test/ai.test.js`

---

### Task 1: 修复 Python 工程基线与配置

**Files:**
- Modify: `ai-python/pyproject.toml`
- Modify: `ai-python/requirements.txt`
- Modify: `ai-python/Dockerfile`
- Modify: `ai-python/README.md`
- Create: `ai-python/app/core/config.py`
- Create: `ai-python/app/core/llm.py`
- Create: `ai-python/tests/unit/test_config.py`

**Interfaces:**
- Produces: `get_settings() -> Settings`
- Produces: `create_chat_model(settings: Settings) -> BaseChatModel`
- Produces: `create_embeddings(settings: Settings) -> Embeddings`

- [ ] **Step 1: 写配置失败测试**

```python
# ai-python/tests/unit/test_config.py
from app.core.config import Settings


def test_settings_define_isolated_collections():
    settings = Settings(
        dashscope_api_key="test",
        dashscope_base_url="https://example.invalid/v1",
        dashscope_chat_model="test-model",
        embedding_model="test-embedding",
        internal_api_key="internal",
    )
    assert settings.hospital_collection == "wenrun_hospital_custom"
    assert settings.medical_collection == "wenrun_medical_general"
    assert settings.memory_collection == "wenrun_conversation_memory"
    assert settings.checkpoint_path.endswith(".sqlite")
```

- [ ] **Step 2: 验证测试因配置模块不存在而失败**

Run:

```powershell
cd "D:\刘畅\WebAI\Online hospitals\ai-python"
python -m pytest tests/unit/test_config.py -v
```

Expected: FAIL，提示 `app.core.config` 不存在。

- [ ] **Step 3: 统一依赖与打包**

`pyproject.toml` 以 `app` 为实际包，声明运行所需依赖：

```toml
[project]
name = "wenrun-ai"
requires-python = ">=3.11"
dependencies = [
  "python-dotenv",
  "fastapi",
  "uvicorn[standard]",
  "httpx",
  "pydantic-settings",
  "langgraph",
  "langgraph-checkpoint-sqlite",
  "langchain",
  "langchain-openai",
  "langchain-qdrant",
  "qdrant-client",
  "pypdf",
  "python-docx",
  "python-multipart",
  "loguru",
]

[project.optional-dependencies]
test = ["pytest", "pytest-asyncio"]

[tool.hatch.build.targets.wheel]
packages = ["app"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

`requirements.txt` 只引用项目依赖，避免双轨版本：

```text
-e .[test]
```

Docker 使用项目声明安装，不再手写依赖清单：

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY app app
RUN pip install --no-cache-dir .
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 4: 实现 Settings 与可注入模型工厂**

```python
# ai-python/app/core/config.py
from functools import lru_cache
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        populate_by_name=True,
    )
    dashscope_api_key: str
    dashscope_base_url: str
    dashscope_chat_model: str
    embedding_model: str
    qdrant_url: str = "http://localhost:6333"
    hospital_collection: str = Field(
        "wenrun_hospital_custom",
        validation_alias="QDRANT_HOSPITAL_COLLECTION",
    )
    medical_collection: str = Field(
        "wenrun_medical_general",
        validation_alias="QDRANT_MEDICAL_COLLECTION",
    )
    memory_collection: str = Field(
        "wenrun_conversation_memory",
        validation_alias="QDRANT_MEMORY_COLLECTION",
    )
    checkpoint_path: str = Field(
        "./data/checkpoints.sqlite",
        validation_alias="AI_CHECKPOINT_PATH",
    )
    java_base_url: str = Field(
        "http://localhost:8080",
        validation_alias="AI_JAVA_BASE_URL",
    )
    internal_api_key: str = Field(
        validation_alias=AliasChoices("AI_INTERNAL_API_KEY", "AI_SERVICE_API_KEY"),
    )
    short_term_token_budget: int = 6000
    agent_max_steps: int = 8


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

```python
# ai-python/app/core/llm.py
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from app.core.config import Settings


def create_chat_model(settings: Settings) -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.dashscope_chat_model,
        base_url=settings.dashscope_base_url,
        api_key=settings.dashscope_api_key,
    )


def create_embeddings(settings: Settings) -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        base_url=settings.dashscope_base_url,
        api_key=settings.dashscope_api_key,
    )
```

- [ ] **Step 5: 安装并验证基线**

Run:

```powershell
cd "D:\刘畅\WebAI\Online hospitals\ai-python"
python -m pip install -e ".[test]"
python -m pytest tests/unit/test_config.py -v
python -c "import app; import langgraph; import langchain_qdrant"
```

Expected: 测试 PASS，imports 退出码为 0。

- [ ] **Step 6: 提交检查点（仅在用户明确授权后）**

```powershell
git add ai-python/pyproject.toml ai-python/requirements.txt ai-python/Dockerfile ai-python/README.md ai-python/app/core ai-python/tests/unit/test_config.py
git commit -m "build: align Python AI dependencies and configuration"
```

---

### Task 2: 固化 FastAPI、请求模型与 SSE 契约

**Files:**
- Modify: `ai-python/app/models/chat.py`
- Create: `ai-python/app/models/source.py`
- Create: `ai-python/app/models/sse.py`
- Create: `ai-python/app/api/dependencies/auth.py`
- Create: `ai-python/app/api/dependencies/runtime.py`
- Create: `ai-python/app/services/sse.py`
- Create: `ai-python/app/api/routes/health.py`
- Modify: `ai-python/app/api/routes/chat.py`
- Modify: `ai-python/app/main.py`
- Create: `ai-python/tests/contract/test_api_sse.py`

**Interfaces:**
- Produces: `ChatRequest`, `ChatResponse`, `ResumeRequest`, `UserContext`
- Produces: `ChatStreamEvent`
- Produces: `ToolRuntimeContext(delegation_token: str)`
- Produces: `encode_sse(event: ChatStreamEvent) -> str`
- Produces: `DELETE /v1/chat/conversations/{conversation_id}`

- [ ] **Step 1: 写 API 契约测试**

```python
# ai-python/tests/contract/test_api_sse.py
from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


def test_health_is_available_without_api_key():
    assert client.get("/health").json() == {"status": "ok"}


def test_chat_requires_internal_api_key():
    response = client.post(
        "/v1/chat",
        json={"message": "你好", "conversationId": "c-1"},
    )
    assert response.status_code == 401


def test_sse_encoder_uses_data_frame():
    from app.models.sse import ChatStreamEvent
    from app.services.sse import encode_sse
    frame = encode_sse(ChatStreamEvent(type="status", content="routing"))
    assert frame.startswith("data: ")
    assert frame.endswith("\n\n")
```

- [ ] **Step 2: 运行并确认契约测试失败**

Run:

```powershell
python -m pytest tests/contract/test_api_sse.py -v
```

Expected: FAIL，缺少 health、认证依赖或 SSE 模型。

- [ ] **Step 3: 实现 camelCase 兼容模型**

```python
# ai-python/app/models/chat.py
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class UserContext(ApiModel):
    user_id: int | None = Field(None, alias="userId")
    patient_id: int | None = Field(None, alias="patientId")


class ChatRequest(ApiModel):
    message: str = Field(min_length=1)
    conversation_id: str = Field(alias="conversationId", min_length=1)
    memory_enabled: bool = Field(True, alias="memoryEnabled")
    user_context: UserContext = Field(default_factory=UserContext, alias="userContext")


class ResumeRequest(ApiModel):
    conversation_id: str = Field(alias="conversationId", min_length=1)
    interrupt_id: str = Field(alias="interruptId", min_length=1)
    approved: bool
    params: dict[str, Any] | None = None


class ChatResponse(ApiModel):
    reply: str | None = None
    status: Literal["completed", "pending"]
    conversation_id: str = Field(alias="conversationId")
    intent: Literal["chat", "hospital", "medical"] | None = None
    interrupts: list[dict[str, Any]] = Field(default_factory=list)
```

`source.py` 定义 `CitationSource` 和 `ToolSource`；`sse.py` 使用判别字段 `type` 覆盖 `status/token/citation/interrupt/done/error`，并包含 `code`、`message`、`sources`、`interrupt`。

- [ ] **Step 4: 实现认证、运行时上下文和 SSE 编码**

```python
# ai-python/app/api/dependencies/auth.py
from fastapi import Depends, Header, HTTPException
from app.core.config import Settings, get_settings


def verify_api_key(
    x_api_key: str | None = Header(None, alias="X-Api-Key"),
    settings: Settings = Depends(get_settings),
) -> None:
    if not x_api_key or x_api_key != settings.internal_api_key:
        raise HTTPException(status_code=401, detail="invalid internal api key")
```

```python
# ai-python/app/api/dependencies/runtime.py
from dataclasses import dataclass
from fastapi import Header


@dataclass(frozen=True)
class ToolRuntimeContext:
    delegation_token: str | None


def get_tool_context(
    token: str | None = Header(None, alias="X-Delegated-Token"),
) -> ToolRuntimeContext:
    return ToolRuntimeContext(delegation_token=token)
```

```python
# ai-python/app/services/sse.py
from app.models.sse import ChatStreamEvent


def encode_sse(event: ChatStreamEvent) -> str:
    return f"data: {event.model_dump_json(by_alias=True, exclude_none=True)}\n\n"
```

- [ ] **Step 5: 注册路由并通过依赖注入调用 ChatService**

`GET /health` 不校验 Key；`/v1/chat*` 使用 `Depends(verify_api_key)`。流式路由返回：

```python
return StreamingResponse(
    (encode_sse(event) async for event in service.stream_chat(request, runtime)),
    media_type="text/event-stream",
)
```

恢复路由调用 `service.resume_stream(request, runtime)`。在 Task 3 完成前，测试 fixture 用 fake service 覆盖依赖，禁止路由直接 import 全局模型。

删除会话路由调用 `service.delete_conversation(conversation_id)`，同时删除该 thread 的 checkpoint 和当前会话向量记忆；不存在时保持幂等并返回 204。

- [ ] **Step 6: 运行契约测试**

Run:

```powershell
python -m pytest tests/contract/test_api_sse.py -v
```

Expected: PASS。

- [ ] **Step 7: 提交检查点（仅在用户明确授权后）**

```powershell
git add ai-python/app/models ai-python/app/api ai-python/app/services/sse.py ai-python/app/main.py ai-python/tests/contract/test_api_sse.py
git commit -m "feat: define authenticated AI chat and SSE contracts"
```

---

### Task 3: 重构 LangGraph 为三业务 Agent 路由图

**Files:**
- Modify: `ai-python/app/models/intent_result.py`
- Modify: `ai-python/app/graphs/hospital/state.py`
- Modify: `ai-python/app/graphs/hospital/graph.py`
- Modify: `ai-python/app/graphs/hospital/nodes/intent_judgment_node.py`
- Modify: `ai-python/app/graphs/hospital/nodes/chat_node.py`
- Create: `ai-python/app/graphs/hospital/nodes/hospital_node.py`
- Create: `ai-python/app/graphs/hospital/nodes/medical_node.py`
- Create: `ai-python/app/graphs/hospital/nodes/clarify_node.py`
- Create: `ai-python/app/graphs/hospital/nodes/citation_validate_node.py`
- Create: `ai-python/app/graphs/hospital/prompts/intent.py`
- Create: `ai-python/app/graphs/hospital/prompts/chat.py`
- Create: `ai-python/app/graphs/hospital/prompts/hospital.py`
- Create: `ai-python/app/graphs/hospital/prompts/medical.py`
- Create: `ai-python/tests/unit/test_intent_routing.py`
- Create: `ai-python/tests/integration/test_graph_flows.py`
- Delete: `ai-python/app/graphs/hospital/nodes/tool_node.py`
- Delete: `ai-python/app/graphs/hospital/nodes/knowledge_node.py`
- Delete: `ai-python/app/graphs/hospital/tools/test_tool.py`

**Interfaces:**
- Produces: `build_graph(deps: GraphDependencies, checkpointer=None)`
- Produces: `route_by_intent(state: State) -> str`
- Produces: `GraphDependencies`，测试可注入 fake agents/retrievers/tools

- [ ] **Step 1: 写路由与医疗边界测试**

```python
def test_route_maps_only_three_business_intents():
    from app.graphs.hospital.graph import route_by_intent
    assert route_by_intent({"intent": "chat"}) == "chat"
    assert route_by_intent({"intent": "hospital"}) == "hospital"
    assert route_by_intent({"intent": "medical"}) == "medical"


def test_ambiguous_intent_routes_to_clarification():
    from app.graphs.hospital.graph import route_by_intent
    assert route_by_intent({"intent": None}) == "clarify"


def test_medical_agent_escalates_danger_signals(fake_medical_agent):
    answer = fake_medical_agent.invoke("胸痛并且呼吸困难")
    assert "急诊" in answer or "急救" in answer
    assert "确诊" not in answer
```

集成测试用 fake node 返回确定消息，断言三条边均到 `citation_validate`，而不是直接 END。

- [ ] **Step 2: 运行并确认旧枚举导致失败**

Run:

```powershell
python -m pytest tests/unit/test_intent_routing.py tests/integration/test_graph_flows.py -v
```

Expected: FAIL，旧值为 `tool/knowledge`，且无 clarify。

- [ ] **Step 3: 扩展 State 并移除 import-time Agent 单例**

```python
class State(MessagesState):
    conversation_id: str
    user_id: int | None
    patient_id: int | None
    intent: Literal["chat", "hospital", "medical"] | None
    memory_enabled: bool
    task_plan: list[dict]
    tool_context: dict
    sources: list[dict]
    pending_action: dict | None
    error: dict | None
    retry_count: int
```

所有 Agent 从 `GraphDependencies` 注入；测试不得触发真实 DashScope 或 Qdrant。

- [ ] **Step 4: 实现主图拓扑**

```python
builder.add_edge(START, "load_memory")
builder.add_edge("load_memory", "intent_judgment")
builder.add_conditional_edges(
    "intent_judgment",
    route_by_intent,
    {
        "chat": "chat",
        "hospital": "hospital",
        "medical": "medical",
        "clarify": "clarify",
    },
)
for node in ("chat", "hospital", "medical", "clarify"):
    builder.add_edge(node, "citation_validate")
builder.add_edge("citation_validate", "save_memory")
builder.add_edge("save_memory", END)
```

意图 Agent 使用结构化输出，Prompt 明确混合“医院信息 + 办事”属于 `hospital`。医疗 Prompt 写入能力边界，但只在诊断/开药请求时自然说明。

- [ ] **Step 5: 运行图测试**

Run:

```powershell
python -m pytest tests/unit/test_intent_routing.py tests/integration/test_graph_flows.py -v
```

Expected: PASS，且测试期间没有外部网络请求。

- [ ] **Step 6: 提交检查点（仅在用户明确授权后）**

```powershell
git add ai-python/app/graphs ai-python/app/models/intent_result.py ai-python/tests
git commit -m "feat: route patient requests across three specialist agents"
```

---

### Task 4: 实现隔离的 RAG 入库、检索和引用校验

**Files:**
- Modify: `ai-python/app/rag/qdrant.py`
- Modify: `ai-python/app/rag/rag.py`
- Create: `ai-python/app/rag/collections.py`
- Create: `ai-python/app/rag/ingest.py`
- Create: `ai-python/app/models/knowledge.py`
- Create: `ai-python/app/api/routes/knowledge.py`
- Modify: `ai-python/app/main.py`
- Modify: `ai-python/app/graphs/hospital/nodes/hospital_node.py`
- Modify: `ai-python/app/graphs/hospital/nodes/medical_node.py`
- Modify: `ai-python/app/graphs/hospital/nodes/citation_validate_node.py`
- Create: `ai-python/tests/unit/test_rag_filter.py`
- Create: `ai-python/tests/unit/test_citation_validate.py`
- Create: `ai-python/tests/contract/test_knowledge_api.py`

**Interfaces:**
- Produces: `KnowledgeBase` enum
- Produces: `retrieve(base, query, filters=None) -> list[ScoredChunk]`
- Produces: `ingest_document(file, document_id, base, original_name) -> IngestResponse`
- Produces: `delete_document(base, document_id) -> None`

- [ ] **Step 1: 写 collection 隔离与引用失败测试**

```python
def test_medical_retrieval_never_uses_hospital_collection(fake_vector_stores):
    result = retrieve(KnowledgeBase.MEDICAL, "口腔溃疡原因")
    assert fake_vector_stores.last_collection == "wenrun_medical_general"


def test_unsupported_claim_is_rejected():
    state = {
        "messages": [{"role": "assistant", "content": "本院每天七点挂号 [S1]"}],
        "sources": [{"id": "S1", "excerpt": "门诊八点开始挂号"}],
        "retry_count": 1,
    }
    result = citation_validate_node(state)
    assert result["error"]["code"] == "UNSUPPORTED_CITATION"
```

- [ ] **Step 2: 运行并确认 RAG 尚未实现**

Run:

```powershell
python -m pytest tests/unit/test_rag_filter.py tests/unit/test_citation_validate.py -v
```

Expected: FAIL。

- [ ] **Step 3: 实现显式 collection 工厂**

```python
class KnowledgeBase(str, Enum):
    HOSPITAL = "hospital-custom"
    MEDICAL = "medical-general"
    MEMORY = "conversation-memory"


COLLECTIONS = {
    KnowledgeBase.HOSPITAL: "wenrun_hospital_custom",
    KnowledgeBase.MEDICAL: "wenrun_medical_general",
    KnowledgeBase.MEMORY: "wenrun_conversation_memory",
}
```

`qdrant.py` 只提供 client/store 工厂，不在 import 时建立外部连接。`retrieve` 必须由 `KnowledgeBase` 选择 collection，不接受任意 collection 字符串。

- [ ] **Step 4: 实现 Word/PDF 解析与幂等替换**

`ingest_document`：

1. 只接受 `.pdf`、`.docx`；
2. PDF 保存页码，Word 保存标题或段落位置；
3. 生成带 `documentId/knowledgeBase/originalName/pageNumber/section/chunkIndex/documentVersion/ingestedAt` 的 Document；
4. 写入临时版本标记；
5. 全部成功后删除旧版本并激活新版本；
6. 异常时删除临时版本。

知识路由保持 Java 已有字段名 `documentId`、`knowledgeBase`、`originalName`，响应：

```json
{"documentId":"doc-1","knowledgeBase":"medical-general","chunkCount":12}
```

- [ ] **Step 5: 实现生成与引用校验**

医院与医疗 Agent 将检索片段编号为 `[S1]`。引用节点验证 ID 存在、知识库正确、回答事实被 excerpt 支持；首次失败返回重写指令，第二次失败返回保守回答和稳定错误码。

- [ ] **Step 6: 运行 RAG 和知识 API 测试**

Run:

```powershell
python -m pytest tests/unit/test_rag_filter.py tests/unit/test_citation_validate.py tests/contract/test_knowledge_api.py -v
```

Expected: PASS。

- [ ] **Step 7: 提交检查点（仅在用户明确授权后）**

```powershell
git add ai-python/app/rag ai-python/app/api/routes/knowledge.py ai-python/app/models/knowledge.py ai-python/app/graphs/hospital/nodes ai-python/tests
git commit -m "feat: add isolated traceable hospital and medical RAG"
```

---

### Task 5: 实现当前会话记忆与 SQLite checkpoint

**Files:**
- Create: `ai-python/app/services/memory/window.py`
- Create: `ai-python/app/services/memory/vector.py`
- Modify: `ai-python/app/graphs/hospital/nodes/memory_node.py`
- Create: `ai-python/app/graphs/hospital/checkpoint.py`
- Modify: `ai-python/app/graphs/hospital/graph.py`
- Modify: `ai-python/app/services/chat_service.py`
- Create: `ai-python/tests/unit/test_memory.py`
- Create: `ai-python/tests/integration/test_checkpoint.py`

**Interfaces:**
- Produces: `trim_messages(messages, token_budget) -> WindowResult`
- Produces: `load_memory(conversation_id)`, `save_memory(conversation_id, facts)`, `delete_memory(conversation_id)`
- Produces: `get_checkpointer(settings)`
- Produces: `delete_conversation(conversation_id) -> None`

- [ ] **Step 1: 写会话隔离和关闭记忆测试**

```python
async def test_memory_is_filtered_by_conversation(vector_memory):
    await vector_memory.save_memory("c-1", ["偏好上午就诊"])
    await vector_memory.save_memory("c-2", ["对青霉素过敏"])
    assert await vector_memory.load_memory("c-1", "就诊") == ["偏好上午就诊"]


async def test_memory_disabled_skips_vector_store(memory_node, spy_store):
    await memory_node({"conversation_id": "c-1", "memory_enabled": False})
    assert spy_store.calls == []
```

- [ ] **Step 2: 运行并确认测试失败**

Run:

```powershell
python -m pytest tests/unit/test_memory.py tests/integration/test_checkpoint.py -v
```

Expected: FAIL。

- [ ] **Step 3: 实现短期窗口与向量记忆**

`trim_messages` 按配置的 token 预算保留最新消息，把淘汰部分交给摘要器；向量记忆每次读写都附加 Qdrant filter：

```python
models.FieldCondition(
    key="metadata.conversationId",
    match=models.MatchValue(value=conversation_id),
)
```

`memory_enabled=False` 时加载和保存节点直接返回空更新。

`delete_conversation` 同时按 `thread_id` 删除 SQLite checkpoint，并调用 `delete_memory(conversation_id)`；该操作幂等。

- [ ] **Step 4: 接入 checkpoint 和 thread_id**

```python
def graph_config(conversation_id: str, delegation_token: str | None) -> dict:
    return {
        "configurable": {
            "thread_id": conversation_id,
            "delegation_token": delegation_token,
        }
    }
```

SQLite 文件父目录在启动时创建。首期单进程使用 SQLite；Docker 将 `./data` 挂载为持久卷。

- [ ] **Step 5: 验证恢复与跨会话隔离**

Run:

```powershell
python -m pytest tests/unit/test_memory.py tests/integration/test_checkpoint.py -v
```

Expected: PASS；`c-1` 的 checkpoint 和记忆不能被 `c-2` 获取。

- [ ] **Step 6: 提交检查点（仅在用户明确授权后）**

```powershell
git add ai-python/app/services/memory ai-python/app/graphs/hospital ai-python/tests
git commit -m "feat: add conversation-scoped memory and checkpoints"
```

---

### Task 6: 新增 Java 委托 JWT 并收窄认证边界

**Files:**
- Create: `backend-java/src/main/java/com/wenrun/ai/delegation/AiDelegationProperties.java`
- Create: `backend-java/src/main/java/com/wenrun/ai/delegation/AiDelegationClaims.java`
- Create: `backend-java/src/main/java/com/wenrun/ai/delegation/AiDelegationTokenService.java`
- Create: `backend-java/src/main/java/com/wenrun/ai/tools/interceptor/DelegatedJwtInterceptor.java`
- Modify: `backend-java/src/main/java/com/wenrun/config/AuthInterceptor.java`
- Modify: `backend-java/src/main/java/com/wenrun/config/WebMvcConfig.java`
- Modify: `backend-java/src/main/resources/application.yml`
- Create: `backend-java/src/test/java/com/wenrun/ai/delegation/AiDelegationTokenServiceTest.java`
- Create: `backend-java/src/test/java/com/wenrun/ai/tools/interceptor/DelegatedJwtInterceptorTest.java`
- Modify: `backend-java/src/test/java/com/wenrun/config/AuthInterceptorTest.java`

**Interfaces:**
- Produces: `issueReadToken(userId, patientId, conversationId)`
- Produces: `issueWriteToken(userId, patientId, conversationId, interruptId)`
- Produces: `verify(token, requiredScope) -> AiDelegationClaims`

- [ ] **Step 1: 写 scope、audience、过期和 interrupt 绑定测试**

```java
@Test
void readTokenCannotCreateRegistration() {
    String token = service.issueReadToken(1L, 10L, "c-1");
    assertThrows(AiDelegationException.class,
            () -> service.verify(token, "registration:create"));
}

@Test
void writeTokenBindsInterruptAndPatient() {
    String token = service.issueWriteToken(1L, 10L, "c-1", "i-1");
    AiDelegationClaims claims = service.verify(token, "registration:create");
    assertEquals(10L, claims.patientId());
    assertEquals("i-1", claims.interruptId());
}
```

- [ ] **Step 2: 运行并确认测试失败**

Run:

```powershell
cd "D:\刘畅\WebAI\Online hospitals\backend-java"
mvn -Dtest=AiDelegationTokenServiceTest,DelegatedJwtInterceptorTest,AuthInterceptorTest test
```

Expected: FAIL，委托服务和拦截器不存在。

- [ ] **Step 3: 实现独立委托 JWT**

委托令牌使用 Nimbus HS256，claims 为：

```java
new JWTClaimsSet.Builder()
    .subject(userId.toString())
    .audience("ai-tools")
    .claim("patient_id", patientId)
    .claim("conversation_id", conversationId)
    .claim("scope", scopes)
    .claim("interrupt_id", interruptId)
    .jwtID(UUID.randomUUID().toString())
    .issueTime(now)
    .expirationTime(Date.from(now.toInstant().plusSeconds(expirySeconds)))
    .build();
```

配置使用环境变量，不在 yml 写真实 secret：

```yaml
ai:
  delegation:
    secret: ${AI_DELEGATION_SECRET}
    expiry-seconds: ${AI_DELEGATION_EXPIRY_SECONDS:300}
```

`AiDelegationProperties` 使用 `@Validated` 和 `@NotBlank`，缺少 secret 时启动失败；测试通过专用 properties 注入固定测试密钥。

- [ ] **Step 4: 收窄原 AuthInterceptor**

移除 `X-Api-Key` 对全部 `/api/**` 的放行。现有患者请求继续由 `AuthTokenStore` 校验 UUID Token；`/api/internal/ai-tools/**` 从原拦截器排除，只由 `DelegatedJwtInterceptor` 保护。

```java
registry.addInterceptor(authInterceptor)
    .addPathPatterns("/api/**")
    .excludePathPatterns(
        "/api/health",
        "/api/auth/login",
        "/api/auth/register",
        "/api/internal/ai-tools/**");
registry.addInterceptor(delegatedJwtInterceptor)
    .addPathPatterns("/api/internal/ai-tools/**");
```

- [ ] **Step 5: 运行认证测试**

Run:

```powershell
mvn -Dtest=AiDelegationTokenServiceTest,DelegatedJwtInterceptorTest,AuthInterceptorTest test
```

Expected: PASS；普通 API Key 不再能绕过患者 API。

- [ ] **Step 6: 提交检查点（仅在用户明确授权后）**

```powershell
git add backend-java/src/main/java/com/wenrun/ai/delegation backend-java/src/main/java/com/wenrun/ai/tools/interceptor backend-java/src/main/java/com/wenrun/config backend-java/src/main/resources/application.yml backend-java/src/test
git commit -m "feat: add scoped delegation tokens for AI tools"
```

---

### Task 7: 实现 Java AI Tool 白名单和安全挂号

**Files:**
- Create: `backend-java/src/main/java/com/wenrun/ai/tools/controller/AiToolsInternalController.java`
- Create: `backend-java/src/main/java/com/wenrun/ai/tools/service/AiToolsRegistrationService.java`
- Create: `backend-java/src/main/java/com/wenrun/ai/tools/dto/AiToolRegistrationCreateDTO.java`
- Create: `backend-java/src/main/java/com/wenrun/ai/tools/vo/AiToolErrorVO.java`
- Modify: `backend-java/src/main/java/com/wenrun/entity/Registration.java`
- Modify: `backend-java/src/main/java/com/wenrun/repository/RegistrationRepository.java`
- Modify: `backend-java/src/main/resources/mapper/RegistrationRepository.xml`
- Modify: `docs/SQL/schema.sql`
- Create: `docs/SQL/migrations/2026-08-16-registration-idempotency.sql`
- Create: `backend-java/src/test/java/com/wenrun/ai/tools/controller/AiToolsInternalControllerTest.java`
- Create: `backend-java/src/test/java/com/wenrun/ai/tools/service/AiToolsRegistrationServiceTest.java`

**Interfaces:**
- Produces: `/api/internal/ai-tools/depts`
- Produces: `/api/internal/ai-tools/staff`
- Produces: `/api/internal/ai-tools/schedules`
- Produces: `/api/internal/ai-tools/registrations`

- [ ] **Step 1: 写患者归属、scope、重复提交和号源变化测试**

```java
@Test
void ignoresBodyPatientAndUsesDelegatedPatient() {
    var dto = new AiToolRegistrationCreateDTO(999L, 20L, "idem-1", "i-1");
    assertThrows(AiToolException.class,
            () -> service.register(dto, claimsForPatient(10L)));
}

@Test
void sameIdempotencyKeyReturnsSameRegistration() {
    Long first = service.register(validRequest("idem-1"), writeClaims());
    Long second = service.register(validRequest("idem-1"), writeClaims());
    assertEquals(first, second);
    verify(scheduleRepository, times(1)).decrementRemaining(anyLong());
}
```

- [ ] **Step 2: 运行并确认测试失败**

Run:

```powershell
mvn -Dtest=AiToolsInternalControllerTest,AiToolsRegistrationServiceTest test
```

Expected: FAIL。

- [ ] **Step 3: 增加数据库幂等字段**

迁移和权威 schema 都增加：

```sql
ALTER TABLE registration
  ADD COLUMN idempotency_key VARCHAR(128) DEFAULT NULL COMMENT 'AI挂号幂等键',
  ADD UNIQUE KEY uk_registration_idempotency_key (idempotency_key);
```

Entity 和 Mapper 增加 `idempotencyKey`，Repository 增加：

```java
Registration selectByIdempotencyKey(String idempotencyKey);
int countActiveByPatientAndSchedule(Long patientId, Long scheduleId);
```

- [ ] **Step 4: 实现白名单 Controller**

Controller 只调用现有 `DeptService`、`StaffService`、`ScheduleService` 和新的 `AiToolsRegistrationService`。每个方法读取拦截器写入的 `AiDelegationClaims`，并验证对应 scope。

创建挂号 DTO：

```java
public record AiToolRegistrationCreateDTO(
        Long patientId,
        Long scheduleId,
        String idempotencyKey,
        String interruptId) {}
```

写服务依次校验：claim patient、interruptId、幂等记录、患者存在、重复活跃挂号、锁定排班、剩余号源、扣减、插入。异常映射为稳定码。

- [ ] **Step 5: 运行 Tool 测试**

Run:

```powershell
mvn -Dtest=AiToolsInternalControllerTest,AiToolsRegistrationServiceTest test
```

Expected: PASS。

- [ ] **Step 6: 提交检查点（仅在用户明确授权后）**

```powershell
git add backend-java/src/main/java/com/wenrun/ai/tools backend-java/src/main/java/com/wenrun/entity/Registration.java backend-java/src/main/java/com/wenrun/repository/RegistrationRepository.java backend-java/src/main/resources/mapper/RegistrationRepository.xml backend-java/src/test docs/SQL
git commit -m "feat: expose safe idempotent AI registration tools"
```

---

### Task 8: 接通 Python Java Tools、医院 Agent 与 HITL

**Files:**
- Create: `ai-python/app/services/java_tools/client.py`
- Create: `ai-python/app/services/java_tools/models.py`
- Create: `ai-python/app/services/java_tools/dept.py`
- Create: `ai-python/app/services/java_tools/doctor.py`
- Create: `ai-python/app/services/java_tools/schedule.py`
- Create: `ai-python/app/services/java_tools/registration.py`
- Modify: `ai-python/app/graphs/hospital/nodes/hospital_node.py`
- Create: `ai-python/app/graphs/hospital/nodes/registration_interrupt_node.py`
- Modify: `ai-python/app/graphs/hospital/graph.py`
- Modify: `ai-python/app/services/chat_service.py`
- Create: `ai-python/tests/unit/test_tool_errors.py`
- Create: `ai-python/tests/integration/test_hospital_hitl.py`

**Interfaces:**
- Produces: `JavaToolsClient`
- Produces: `registration_interrupt_node(state, config)`
- Consumes: Java `/api/internal/ai-tools/**`

- [ ] **Step 1: 写复合请求、拒绝、确认和重复恢复测试**

```python
async def test_hospital_agent_combines_rag_and_schedule_tool(graph):
    result = await graph.ainvoke(
        patient_input("外科在哪里，明天下午有哪些医生"),
        config_for("c-1", "read-token"),
    )
    assert any(s["kind"] == "rag" for s in result["sources"])
    assert any(s["kind"] == "tool" for s in result["sources"])


async def test_registration_stops_at_interrupt(graph):
    result = await graph.ainvoke(
        patient_input("挂第一个号源"),
        config_for("c-1", "read-token"),
    )
    assert result["__interrupt__"]
    assert fake_java.create_calls == 0
```

- [ ] **Step 2: 运行并确认测试失败**

Run:

```powershell
python -m pytest tests/unit/test_tool_errors.py tests/integration/test_hospital_hitl.py -v
```

Expected: FAIL。

- [ ] **Step 3: 实现 JavaToolsClient**

所有请求携带：

```python
headers = {
    "Authorization": f"Bearer {delegation_token}",
    "X-Request-Id": request_id,
}
```

对 Java 稳定错误码映射为结构化 `ToolFailure(code, safe_message, retryable)`；日志不得输出 Authorization。

- [ ] **Step 4: 实现医院计划与 interrupt**

医院 Agent 只能输出受控计划：`hospital_rag`、`query_depts`、`query_doctors`、`query_schedules`、`prepare_registration`。写节点：

```python
confirmation = interrupt({
    "interruptId": interrupt_id,
    "action": "registration:create",
    "params": pending_action,
    "summary": summary,
})
if not confirmation.get("approved"):
    return {"pending_action": None, "messages": [AIMessage(content="已取消挂号操作。")]}
```

恢复后从新的 `configurable.delegation_token` 获取写令牌，重新查询号源，再调用 `create_registration`。幂等键使用 `conversationId + interruptId` 的稳定哈希。

- [ ] **Step 5: 实现 ChatService resume**

```python
async for event in graph.astream_events(
    Command(resume={
        "interruptId": request.interrupt_id,
        "approved": request.approved,
        "params": request.params,
    }),
    config=graph_config(request.conversation_id, runtime.delegation_token),
):
    yield map_graph_event(event)
```

校验 checkpoint 中 interruptId 与请求一致；已消费 interrupt 再次恢复返回 `INTERRUPT_ALREADY_RESOLVED`。

- [ ] **Step 6: 运行 HITL 测试**

Run:

```powershell
python -m pytest tests/unit/test_tool_errors.py tests/integration/test_hospital_hitl.py -v
```

Expected: PASS；确认前 `create_calls == 0`，确认后只调用一次。

- [ ] **Step 7: 提交检查点（仅在用户明确授权后）**

```powershell
git add ai-python/app/services/java_tools ai-python/app/graphs/hospital ai-python/app/services/chat_service.py ai-python/tests
git commit -m "feat: add hospital tools and interrupt-driven registration"
```

---

### Task 9: Java 转发 API Key、委托令牌、完整 SSE 与 resume

**Files:**
- Modify: `backend-java/src/main/java/com/wenrun/ai/config/AiServiceProperties.java`
- Modify: `backend-java/src/main/java/com/wenrun/ai/config/AiHttpClientConfig.java`
- Modify: `backend-java/src/main/java/com/wenrun/ai/client/AiServiceClient.java`
- Modify: `backend-java/src/main/java/com/wenrun/ai/controller/AiChatController.java`
- Modify: `backend-java/src/main/java/com/wenrun/ai/service/AiChatService.java`
- Modify: `backend-java/src/main/java/com/wenrun/ai/service/serviceImpl/AiChatServiceImpl.java`
- Modify: `backend-java/src/main/java/com/wenrun/ai/dto/ChatRequestDTO.java`
- Create: `backend-java/src/main/java/com/wenrun/ai/dto/ChatResumeRequestDTO.java`
- Create: `backend-java/src/main/java/com/wenrun/ai/dto/PythonChatRequestDTO.java`
- Create: `backend-java/src/main/java/com/wenrun/ai/dto/AiUserContextDTO.java`
- Modify: `backend-java/src/main/java/com/wenrun/ai/vo/ChatStreamEventVO.java`
- Create: `backend-java/src/main/java/com/wenrun/ai/vo/ChatCitationVO.java`
- Create: `backend-java/src/main/java/com/wenrun/ai/vo/ChatInterruptVO.java`
- Create: `backend-java/src/main/java/com/wenrun/ai/service/ConversationOwnershipService.java`
- Modify: `backend-java/src/main/java/com/wenrun/repository/ChatMessageRepository.java`
- Modify: `backend-java/src/main/resources/mapper/ChatMessageRepository.xml`
- Modify: `backend-java/src/main/resources/application.yml`
- Create: `backend-java/src/test/java/com/wenrun/ai/client/AiServiceClientTest.java`
- Create: `backend-java/src/test/java/com/wenrun/ai/controller/AiChatControllerTest.java`

**Interfaces:**
- Produces: `POST /api/ai/chat/stream`
- Produces: `POST /api/ai/chat/resume/stream`
- Produces: `DELETE /api/ai/conversations/{conversationId}`
- Consumes: Python chat、stream、resume API

- [ ] **Step 1: 写出站 Header 和 SSE 转发测试**

```java
server.expect(requestTo("http://localhost:8000/v1/chat/stream"))
    .andExpect(header("X-Api-Key", "internal"))
    .andExpect(header("X-Delegated-Token", readToken))
    .andRespond(withSuccess(
        "data: {\"type\":\"interrupt\",\"interrupt\":{\"interruptId\":\"i-1\"}}\n\n",
        MediaType.TEXT_EVENT_STREAM));
```

Controller 测试断言 `interrupt` 后正常完成 SSE，不生成错误事件；resume approved 时签发写 scope。

- [ ] **Step 2: 运行并确认测试失败**

Run:

```powershell
mvn -Dtest=AiServiceClientTest,AiChatControllerTest test
```

Expected: FAIL。

- [ ] **Step 3: 统一出站认证和 DTO**

`AiHttpClientConfig` 为两个 RestClient 默认添加 `X-Api-Key`。`AiServiceClient` 每次 chat/stream 接收 delegationToken 并添加 `X-Delegated-Token`。

不要再用 `JwtUtil.verifyAndParse()` 解析患者 UUID Token。Controller 使用已由 `AuthInterceptor` 写入的 `UserContext.getUserId()`，通过 `PatientRepository.selectByUserId()` 补全患者，再签发 read token。

浏览器入参 `ChatRequestDTO` 只保留 `message/conversationId/memoryEnabled`；Java 内部创建以下出站模型，避免信任浏览器提交的患者身份：

```java
public record AiUserContextDTO(Long userId, Long patientId) {}

public record PythonChatRequestDTO(
        String message,
        String conversationId,
        Boolean memoryEnabled,
        AiUserContextDTO userContext) {}
```

- [ ] **Step 4: 扩展 SSE VO 与 resume**

```java
@Data
public class ChatStreamEventVO {
    private String type;
    private String content;
    private String reply;
    private String conversationId;
    private String intent;
    private String code;
    private String message;
    private List<ChatCitationVO> sources;
    private ChatInterruptVO interrupt;
}
```

新增 `chatResumeStream()`，approved 时签发绑定 interruptId 的 write token；拒绝时签发无写 scope 的短期 token。所有错误均作为 JSON `error` 事件发送，不再发送无法解析的纯文本。

`ConversationOwnershipService` 使用 `ChatMessageRepository.existsByConversationIdAndUserId()` 校验 resume 和 delete；首次发送消息时由当前 `UserContext.userId` 建立归属。删除会话时 Java 先校验归属，再调用 Python 删除 checkpoint/向量记忆，最后删除或归档 Java 聊天消息。

- [ ] **Step 5: 增加配置**

```yaml
ai:
  service:
    chat-resume-stream-path: /v1/chat/resume/stream
```

真实 Key 由环境变量注入：

```yaml
api-key: ${AI_SERVICE_API_KEY:}
```

- [ ] **Step 6: 运行 Java AI 契约测试**

Run:

```powershell
mvn -Dtest=AiServiceClientTest,AiChatControllerTest test
```

Expected: PASS。

- [ ] **Step 7: 提交检查点（仅在用户明确授权后）**

```powershell
git add backend-java/src/main/java/com/wenrun/ai backend-java/src/main/resources/application.yml backend-java/src/test
git commit -m "feat: proxy authenticated AI streams and HITL resume"
```

---

### Task 10: 前端解析引用、interrupt 并恢复聊天

**Files:**
- Modify: `frontend/src/api/modules/ai.js`
- Modify: `frontend/src/api/index.js`
- Create: `frontend/src/features/assistant/citation.js`
- Create: `frontend/src/features/assistant/interrupt.js`
- Modify: `frontend/src/features/assistant/session.js`
- Modify: `frontend/src/composables/useAssistant.js`
- Create: `frontend/src/components/CitationList.vue`
- Create: `frontend/src/components/InterruptConfirm.vue`
- Modify: `frontend/src/views/Assistant.vue`
- Modify: `frontend/src/views/shared/views.css`
- Modify: `frontend/test/ai.test.js`
- Modify: `frontend/package.json`

**Interfaces:**
- Produces: `chatStream(payload, handlers)`
- Produces: `resumeStream(payload, handlers)`
- Produces: `deleteConversation(conversationId)`
- Produces: `pendingInterrupt`、`streamStatus`、`resumeInterrupt`

- [ ] **Step 1: 写 SSE interrupt 正常结束、引用聚合和 resume payload 测试**

```javascript
test('interrupt is a successful terminal stream event', async () => {
  const seen = []
  const result = await consumeChatEvents([
    { type: 'status', content: '查询号源' },
    { type: 'interrupt', interrupt: { interruptId: 'i-1', action: 'registration:create' } },
  ], { onInterrupt: (value) => seen.push(value) })
  assert.equal(result.status, 'pending')
  assert.equal(seen[0].interruptId, 'i-1')
})

test('buildResumePayload keeps the interrupt identity', () => {
  assert.deepEqual(buildResumePayload('c-1', 'i-1', true), {
    conversationId: 'c-1',
    interruptId: 'i-1',
    approved: true,
  })
})
```

- [ ] **Step 2: 运行并确认测试失败**

Run:

```powershell
cd "D:\刘畅\WebAI\Online hospitals\frontend"
node --test test/ai.test.js
```

Expected: FAIL。

- [ ] **Step 3: 扩展 SSE API**

`chatStream` handlers：

```javascript
{
  signal,
  onStatus,
  onToken,
  onCitation,
  onInterrupt,
  onDone,
  onError,
}
```

`interrupt` 是正常终止事件，返回 `{ status: 'pending', interrupt }`，不得抛“流式响应意外结束”。`done` 返回 `{ reply, intent, sources }`。`error` 优先读取 `message`，保留 `code`。

新增：

```javascript
export function resumeStream(payload, handlers = {}) {
  return streamRequest('/api/ai/chat/resume/stream', payload, handlers)
}

export function deleteConversation(conversationId) {
  return request.delete(`/api/ai/conversations/${encodeURIComponent(conversationId)}`)
}
```

- [ ] **Step 4: 扩展会话和 composable**

消息结构：

```javascript
{
  role: 'assistant',
  content: '',
  sources: [],
  meta: { intent: null },
}
```

session 保存 `pendingInterrupt`。`useAssistant` 增加：

```javascript
const streamStatus = ref(null)
const pendingInterrupt = computed(() => activeSession.value?.pendingInterrupt || null)
function updateLastAssistant(conversationId, updater) {
  updateSession(conversationId, (session) => {
    const messages = [...session.messages]
    const last = messages.at(-1)
    if (last?.role === 'assistant') {
      messages[messages.length - 1] = updater(last)
    } else {
      messages.push(updater({ role: 'assistant', content: '', sources: [], meta: {} }))
    }
    return { ...session, messages }
  })
}

function appendAssistantToken(conversationId, chunk) {
  updateLastAssistant(conversationId, (message) => ({
    ...message,
    content: message.content + chunk,
  }))
}

function appendAssistantSource(conversationId, source) {
  updateLastAssistant(conversationId, (message) => ({
    ...message,
    sources: [...(message.sources || []), source],
  }))
}

function finalizeAssistantMessage(conversationId, { reply, intent, sources }) {
  updateLastAssistant(conversationId, (message) => ({
    ...message,
    content: reply || message.content,
    sources: sources || message.sources || [],
    meta: { ...message.meta, intent },
  }))
  updateSession(conversationId, (session) => ({
    ...session,
    pendingInterrupt: null,
  }))
}

function appendAssistantError(conversationId, code, message) {
  updateLastAssistant(conversationId, (current) => ({
    ...current,
    content: message || 'AI 服务暂时不可用，请稍后重试。',
    meta: { ...current.meta, errorCode: code },
  }))
}

function createStreamHandlers(conversationId) {
  return {
    onStatus: (text) => { streamStatus.value = text },
    onToken: (chunk) => appendAssistantToken(conversationId, chunk),
    onCitation: (source) => appendAssistantSource(conversationId, source),
    onInterrupt: (interrupt) => updateSession(conversationId, (session) => ({
      ...session,
      pendingInterrupt: interrupt,
    })),
    onDone: ({ reply, intent, sources }) => finalizeAssistantMessage(
      conversationId,
      { reply, intent, sources },
    ),
    onError: ({ code, message }) => appendAssistantError(
      conversationId,
      code,
      message,
    ),
  }
}

async function resumeInterrupt(approved, params = {}) {
  const pending = pendingInterrupt.value
  const session = activeSession.value
  if (!pending || !session || replying.value) return
  replying.value = true
  try {
    await resumeStream({
      conversationId: session.id,
      interruptId: pending.interruptId,
      approved,
      params,
    }, createStreamHandlers(session.id))
  } finally {
    replying.value = false
  }
}
```

移除 AI 挂号对 `createRegistration()` 的直接调用；普通页面挂号保持原 API，不受影响。`deleteSession` 先调用 `deleteConversation(id)`，成功后再移除本地 session；失败时保留会话并展示可重试错误。

- [ ] **Step 5: 实现引用和确认 UI**

`CitationList.vue` 展示文档名、页码/章节、摘要或 Tool 查询时间。`InterruptConfirm.vue` 展示患者、科室、医生、日期、时段、费用，并提供确认、拒绝按钮。按钮提交期间禁用，避免重复恢复。

- [ ] **Step 6: 增加测试脚本并运行**

```json
{
  "scripts": {
    "test": "node --test test/*.test.js"
  }
}
```

Run:

```powershell
npm test
npm run lint
npm run build
```

Expected: tests PASS、lint 退出码 0、Vite build 成功。

- [ ] **Step 7: 提交检查点（仅在用户明确授权后）**

```powershell
git add frontend/src frontend/test/ai.test.js frontend/package.json
git commit -m "feat: add traceable AI responses and HITL controls"
```

---

### Task 11: 完成端到端安全、错误和可观测性验证

**Files:**
- Modify: `ai-python/app/main.py`
- Create: `ai-python/app/core/logging.py`
- Modify: `ai-python/app/services/java_tools/client.py`
- Modify: `ai-python/app/services/chat_service.py`
- Modify: `backend-java/src/main/java/com/wenrun/ai/controller/AiChatController.java`
- Modify: `backend-java/src/main/java/com/wenrun/ai/exception/AiExceptionHandler.java`
- Modify: `.env.example`
- Modify: `docker-compose.yml`
- Create: `ai-python/tests/integration/test_security.py`
- Create: `ai-python/tests/integration/test_end_to_end.py`

**Interfaces:**
- Produces: 稳定错误码、脱敏日志、可启动的五服务联调环境。

- [ ] **Step 1: 写安全回归测试**

覆盖：

```python
async def test_delegation_token_never_enters_checkpoint(chat_service, checkpoint_spy):
    stream = chat_service.stream_chat(
        chat_request("查询明天号源", "c-1"),
        ToolRuntimeContext("secret-delegation-token"),
    )
    async for event in stream:
        if event.type in {"done", "interrupt", "error"}:
            break
    await stream.aclose()
    assert "secret-delegation-token" not in checkpoint_spy.serialized_content()


async def test_other_conversation_cannot_resume_interrupt(chat_service):
    with pytest.raises(ChatServiceError) as error:
        await collect(chat_service.resume_stream(
            resume_request("c-2", "interrupt-from-c-1", True),
            ToolRuntimeContext("write-token"),
        ))
    assert error.value.code == "INTERRUPT_CONVERSATION_MISMATCH"


async def test_tool_timeout_does_not_claim_success(hospital_graph, fake_java):
    fake_java.raise_timeout = True
    result = await hospital_graph.ainvoke(
        patient_input("查询明天内科号源"),
        config_for("c-1", "read-token"),
    )
    assert result["error"]["code"] == "JAVA_TOOL_TIMEOUT"
    assert "挂号成功" not in result["messages"][-1].content


async def test_medical_answer_without_evidence_is_conservative(medical_graph):
    result = await medical_graph.ainvoke(
        patient_input("解释一种知识库中没有的疾病"),
        config_for("c-1", None),
    )
    assert result["sources"] == []
    assert "没有足够依据" in result["messages"][-1].content


async def test_expired_interrupt_cannot_create_registration(chat_service, fake_java):
    with pytest.raises(ChatServiceError) as error:
        await collect(chat_service.resume_stream(
            resume_request("c-1", "expired-interrupt", True),
            ToolRuntimeContext("write-token"),
        ))
    assert error.value.code == "INTERRUPT_EXPIRED"
    assert fake_java.create_calls == 0


async def test_delete_conversation_removes_checkpoint_and_vector_memory(
    chat_service, checkpoint_spy, vector_memory,
):
    await chat_service.delete_conversation("c-1")
    assert not checkpoint_spy.exists("c-1")
    assert await vector_memory.load_memory("c-1", "任意查询") == []
```

Java 覆盖错误 SSE 必须为 JSON，患者不能恢复他人会话。

- [ ] **Step 2: 实现脱敏日志和超时**

日志只绑定 `requestId`、`conversationId`、节点、Tool、耗时和错误码；过滤 `Authorization`、`X-Delegated-Token`、`X-Api-Key`。查询 Tool 只对连接失败和 5xx 做有限重试；创建挂号依靠幂等键，不做不受控重试。

- [ ] **Step 3: 对齐环境配置**

`.env.example` 增加：

```text
AI_DELEGATION_SECRET=
AI_DELEGATION_EXPIRY_SECONDS=300
AI_INTERNAL_API_KEY=
AI_JAVA_BASE_URL=http://localhost:8080
AI_CHECKPOINT_PATH=./data/checkpoints.sqlite
QDRANT_HOSPITAL_COLLECTION=wenrun_hospital_custom
QDRANT_MEDICAL_COLLECTION=wenrun_medical_general
QDRANT_MEMORY_COLLECTION=wenrun_conversation_memory
```

Compose 为 `ai-python` 挂载 checkpoint 数据卷，并用服务名 `backend-java`、`qdrant`。

- [ ] **Step 4: 运行三端自动测试**

Run:

```powershell
cd "D:\刘畅\WebAI\Online hospitals\ai-python"
python -m pytest tests -v

cd "D:\刘畅\WebAI\Online hospitals\backend-java"
mvn test

cd "D:\刘畅\WebAI\Online hospitals\frontend"
npm test
npm run lint
npm run build
```

Expected: 全部退出码 0。若 `WenRunApplicationTests` 依赖本地 MySQL，先通过 Compose 启动 MySQL，再重跑，不跳过测试。

- [ ] **Step 5: 执行端到端验收**

使用受审核的两份小型测试文档，依次验证：

1. 谈心请求不调用 RAG/Tool；
2. 医院位置回答带医院资料引用；
3. “外科在哪里并挂明天下午号”同时产生 RAG 与 Tool 来源；
4. interrupt 前数据库无新增挂号；
5. 拒绝后数据库无新增挂号；
6. 确认后重新校验号源且仅新增一条挂号；
7. 重复 resume 返回已处理错误且不重复扣号；
8. 口腔溃疡科普带医疗资料引用；
9. 要求诊断或开药时自然说明权限边界；
10. 新会话无法召回旧会话记忆。

- [ ] **Step 6: 提交最终检查点（仅在用户明确授权后）**

```powershell
git add ai-python backend-java frontend .env.example docker-compose.yml docs/SQL
git commit -m "feat: complete patient AI assistant integration"
```

---

## Execution Order and Review Gates

1. Tasks 1–3：Python 工程、契约和主图骨架。Gate：无外部依赖的测试可运行。
2. Tasks 4–5：RAG、引用、记忆和 checkpoint。Gate：三类存储隔离。
3. Tasks 6–7：Java 委托 JWT 与 Tool API。Gate：权限、患者归属、幂等测试通过。
4. Tasks 8–9：Python HITL 与 Java SSE/resume。Gate：确认前零写入，确认后一次写入。
5. Task 10：患者端 UI。Gate：引用可见，interrupt 可确认/拒绝。
6. Task 11：全链路回归。Gate：三端测试与十项端到端验收通过。

每个 Gate 通过后再进入下一阶段；不要把未通过的底层契约问题带入前端联调。
