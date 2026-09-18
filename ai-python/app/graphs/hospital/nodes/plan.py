"""多意图回合的按需规划节点：拆子目标、判依赖，不产生面向患者的文本。

只有 begin_node 选中 ≥2 个 Agent 时才会进入本节点。它的输出 ``task_plan`` 决定：
- 每个 Agent 本轮只需处理的子目标（避免互相抢答或漏答）；
- 哪些 Agent 必须等上游结果（目前只允许 tools 依赖 knowledge，例如
  “感冒该看哪科，帮我挂那个科的号”需要先由知识助手给出科室）。

规划失败时降级为“全部并行、无子目标”，与旧行为完全一致。
"""

from typing import Any

from langchain_core.messages import BaseMessage
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.graphs.hospital.context_builder import bounded_system_message, build_context
from app.graphs.hospital.state import AgentName, State
from app.models.chat import model

# 依赖白名单：(下游, 上游)。除此之外的依赖一律丢弃，保证图里不会出现环或未知路径。
ALLOWED_DEPENDENCIES: frozenset[tuple[AgentName, AgentName]] = frozenset({("tools", "knowledge")})

PLAN_SYSTEM_PROMPT = """你是温润诊所患者端的任务规划器，不是对患者说话的助手。
患者一句话里包含多件事，系统已经选出了要启动的内部 Agent。你的工作只有两件：
1. 为每个已选 Agent 写出它本轮要处理的子目标（goal），用患者原话改写成一句话，不要补充患者没说的内容。
2. 判断 tools 是否必须等 knowledge 的结论才能开始。

Agent 说明：
- knowledge：医疗知识（症状、用药、护理、是否要就医、某类病该看哪科）。
- tools：本院实时业务（科室目录、号源、排班、我的预约、挂号、退号、记住/忘掉偏好）。
- chat：寒暄、情绪、当前时间、自我介绍、楼层/营业时间等非医疗院务。

依赖规则（只允许这一种）：
- 患者要挂号/查号源，但没说科室或医生，而是让系统根据病情决定（“帮我挂对应的科”“该看哪科就挂哪科”），
  tools 的 depends_on 填 ["knowledge"]。
- 患者已经说明了科室或医生（“帮我挂明天内科”“挂李雷医生”），tools 不依赖任何人，depends_on 填 []。
- knowledge 和 chat 永远不依赖别人。

输出要求：
- 只返回一个 JSON 对象，不要 Markdown 代码块、解释或其他文字。
- 格式：{"tasks":[{"agent":"knowledge","goal":"...","depends_on":[]},{"agent":"tools","goal":"...","depends_on":["knowledge"]}]}
- tasks 必须且只能覆盖已选 Agent：{selected_agents}
"""

REPAIR_SYSTEM_PROMPT = """你刚才的规划结果不符合要求。请基于下面的规则和患者消息重新输出。

{rules}

上一次无效输出如下：
{invalid_output}

这一次只返回一个可被 JSON 解析、且符合字段约束的 JSON 对象；不要 Markdown、解释或任何额外文字。
"""


class PlannedTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: AgentName
    goal: str = Field(default="", max_length=400)
    depends_on: list[AgentName] = Field(default_factory=list)


class TaskPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tasks: list[PlannedTask] = Field(default_factory=list)


def parallel_plan(selected_agents: list[AgentName]) -> dict[str, Any]:
    """降级计划：所有已选 Agent 并行、不带子目标。"""

    return {
        "tasks": [
            {"agent": agent, "goal": "", "depends_on": []}
            for agent in selected_agents
        ]
    }


def normalize_plan(plan: TaskPlan | None, selected_agents: list[AgentName]) -> dict[str, Any]:
    """把模型输出收敛到图能安全执行的形状。

    - 只保留 selected_agents 里的 Agent，去重；
    - 依赖只保留白名单内且上游确实被选中的项；
    - 模型漏掉的已选 Agent 用空 goal 补齐，保证每个被路由的节点都会运行。
    """

    selected: list[AgentName] = []
    for agent in selected_agents:
        if agent not in selected:
            selected.append(agent)
    if plan is None:
        return parallel_plan(selected)

    by_agent: dict[AgentName, dict[str, Any]] = {}
    for task in plan.tasks:
        if task.agent not in selected or task.agent in by_agent:
            continue
        depends_on = [
            upstream
            for upstream in task.depends_on
            if (task.agent, upstream) in ALLOWED_DEPENDENCIES and upstream in selected
        ]
        by_agent[task.agent] = {
            "agent": task.agent,
            "goal": task.goal.strip(),
            "depends_on": depends_on,
        }

    for agent in selected:
        by_agent.setdefault(agent, {"agent": agent, "goal": "", "depends_on": []})

    # 保持 selected_agents 的顺序，便于日志和测试比对。
    return {"tasks": [by_agent[agent] for agent in selected]}


def _response_text(response: object) -> str:
    content = getattr(response, "content", "")
    return content.strip() if isinstance(content, str) else ""


def _parse_plan(text: str) -> TaskPlan | None:
    if not text:
        return None
    try:
        return TaskPlan.model_validate_json(text)
    except ValidationError:
        return None


def build_plan_system_prompt(selected_agents: list[AgentName]) -> str:
    # 提示词里含 JSON 花括号，不能用 str.format，否则会被当成占位符。
    return PLAN_SYSTEM_PROMPT.replace("{selected_agents}", ", ".join(selected_agents))


def _plan_with_model(messages: list[BaseMessage], selected_agents: list[AgentName]) -> str | None:
    prompt = build_plan_system_prompt(selected_agents)
    try:
        return _response_text(model.invoke([bounded_system_message(prompt), *messages]))
    except Exception:  # noqa: BLE001 - provider SDKs expose heterogeneous errors
        logger.exception("Task planning failed")
        return None


def _repair_invalid_json(
    messages: list[BaseMessage], selected_agents: list[AgentName], invalid_output: str
) -> str | None:
    repair_prompt = REPAIR_SYSTEM_PROMPT.format(
        rules=build_plan_system_prompt(selected_agents),
        invalid_output=invalid_output[:2_000],
    )
    try:
        return _response_text(model.invoke([bounded_system_message(repair_prompt), *messages]))
    except Exception:  # noqa: BLE001 - provider SDKs expose heterogeneous errors
        logger.exception("Task plan JSON repair failed")
        return None


def plan_node(state: State) -> dict:
    """为多意图回合生成 task_plan；单意图时不调用模型。"""

    selected_agents = [
        agent for agent in (state.get("selected_agents") or []) if isinstance(agent, str)
    ]
    if len(selected_agents) < 2:
        return {"task_plan": None}

    messages = build_context(state, purpose="route")
    raw = _plan_with_model(messages, selected_agents)
    plan = _parse_plan(raw or "")
    repaired = False
    if plan is None and raw is not None:
        plan = _parse_plan(_repair_invalid_json(messages, selected_agents, raw) or "")
        repaired = plan is not None
        if plan is None:
            logger.warning("Task planner returned invalid JSON after one repair attempt")

    task_plan = normalize_plan(plan, selected_agents)
    logger.info(
        "task_plan conversation_id={} degraded={} repaired={} tasks={}",
        state.get("conversation_id"),
        plan is None,
        repaired,
        [
            (task["agent"], task["depends_on"])
            for task in task_plan["tasks"]
        ],
    )
    return {"task_plan": task_plan}


# ---- 供图的条件边与各节点读取 task_plan 的纯函数 ----


def plan_tasks(state: State) -> list[dict[str, Any]]:
    plan = state.get("task_plan")
    tasks = plan.get("tasks") if isinstance(plan, dict) else None
    return [task for task in (tasks or []) if isinstance(task, dict) and task.get("agent")]


def task_for(state: State, agent: AgentName) -> dict[str, Any] | None:
    return next((task for task in plan_tasks(state) if task.get("agent") == agent), None)


def task_goal(state: State, agent: AgentName) -> str | None:
    task = task_for(state, agent)
    goal = task.get("goal") if task else None
    return goal.strip() if isinstance(goal, str) and goal.strip() else None


def depends_on(state: State, agent: AgentName, upstream: AgentName) -> bool:
    task = task_for(state, agent)
    return bool(task) and upstream in (task.get("depends_on") or [])


def ready_agents(state: State) -> list[AgentName]:
    """计划中没有任何依赖的 Agent，可以立即并行启动。"""

    return [task["agent"] for task in plan_tasks(state) if not task.get("depends_on")]
