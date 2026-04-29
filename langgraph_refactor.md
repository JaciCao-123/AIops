# Multi-Agent 基于 LangGraph 框架的重构方案

## 一、当前架构分析

### 1.1 现有架构

```
┌──────────────────────────────────────────────────────────────────┐
│                    MultiAgentOrchestrator                        │
│                                                                  │
│  process_query(user_query)                                       │
│      │                                                           │
│      ▼                                                           │
│  IntentParseAgent.parse()        ← 固定步骤                      │
│      │                                                           │
│      ▼                                                           │
│  SkillManager.search_relevant_skills()                           │
│      │                                                           │
│      ▼                                                           │
│  MasterAgent.plan_and_execute()  ← ReAct 循环 (手动实现)         │
│      │  ┌─────────────────────────────────────┐                  │
│      │  │ while iteration < max_iterations:   │                  │
│      │  │   LLM call → tool_calls → execute   │                  │
│      │  │   → append result → repeat          │                  │
│      │  └─────────────────────────────────────┘                  │
│      │                                                           │
│      ▼                                                           │
│  返回诊断结果                                                     │
└──────────────────────────────────────────────────────────────────┘
```

### 1.2 现有组件职责

| 组件 | 文件 | 职责 |
|------|------|------|
| `IntentParseAgent` | intent_parse.py | NER 实体识别、意图分类、关键词提取 |
| `KnowledgeExpertAgent` | knowledge.py | Neo4j 拓扑查询、RAG 检索、历史案例匹配 |
| `ObservabilityAnalystAgent` | observability.py | 收集指标/日志/链路、异常检测 |
| `MasterAgent` | master.py | ReAct 循环控制、Function Calling、动态规划 |
| `ActionExecuteAgent` | action_execute.py | 生成安全执行命令、风险评估 |
| `ToolRegistry` | tool_registry.py | 25+ 工具注册与执行、7 层安全检查 |
| `SkillManager` | skill_manager.py | 40+ Skill 文件管理与匹配 |
| `MultiAgentOrchestrator` | orchestrator.py | 整体流程编排 |

### 1.3 现有架构痛点

| 痛点 | 描述 |
|------|------|
| **ReAct 循环手动实现** | MasterAgent 中 while 循环 + OpenAI API 调用，无状态持久化 |
| **无断点续跑** | 诊断过程中断后无法恢复，需要从头开始 |
| **调试困难** | 中间状态散落在 messages 列表中，难以追踪和回放 |
| **流程硬编码** | SSH 登录检查、Skill 匹配等逻辑耦合在 orchestrator 中 |
| **无图级别条件分支** | 路由决策依赖 LLM 输出，而非图结构 |
| **人机协同仅限工具层** | 审批通过 `ask_user_confirmation` 工具实现，非图级别中断 |
| **流式输出粗糙** | SSE 仅在 orchestrator 层实现，无法按节点粒度推送 |

---

## 二、LangGraph 核心概念映射

### 2.1 LangGraph → 项目概念映射

| LangGraph 概念 | 项目对应 | 说明 |
|----------------|----------|------|
| `StateGraph` | `MultiAgentOrchestrator` | 有向图编排器 |
| `State (TypedDict)` | 各阶段结果字典 | 全局共享状态 |
| `Node (function)` | 各 Agent 的核心方法 | 图中的计算节点 |
| `Edge (conditional)` | orchestrator 中的 if/else | 节点间转移条件 |
| `Checkpoint` | 无（新增） | 状态持久化与断点续跑 |
| `Human-in-the-loop` | `ask_user_confirmation` 工具 | 图级别人工审批 |
| `ToolNode` | `ToolRegistry` | 工具执行节点 |
| `Streaming` | SSE 流式输出 | 按节点粒度流式推送 |

### 2.2 LangGraph 安装

```bash
pip install langgraph langchain-core langchain-openai
```

---

## 三、重构后的 LangGraph 架构设计

### 3.1 状态图设计

```
                          ┌─────────────┐
                          │  START       │
                          └──────┬──────┘
                                 │
                                 ▼
                      ┌─────────────────────┐
                      │  intent_parse_node  │  意图识别 + NER
                      └──────────┬──────────┘
                                 │
                                 ▼
                      ┌─────────────────────┐
                      │  route_intent_node  │  条件路由
                      └──────────┬──────────┘
                                 │
                    ┌────────────┼────────────┐
                    │            │            │
                    ▼            ▼            ▼
             ┌──────────┐ ┌──────────┐ ┌──────────┐
             │ diagnose │ │  query   │ │  qa      │
             │  path    │ │  path    │ │  path    │
             └─────┬────┘ └────┬─────┘ └────┬─────┘
                   │           │            │
                   ▼           │            ▼
          ┌───────────────┐    │     ┌───────────┐
          │ ssh_check_    │    │     │ knowledge │
          │ node          │    │     │ _qa_node  │
          └───────┬───────┘    │     └─────┬─────┘
                  │            │           │
           ┌──────┼──────┐     │           │
           ▼             ▼     │           │
    ┌────────────┐ ┌─────────┐ │           │
    │ need_ssh_  │ │ continue│ │           │
    │ confirm    │ │ _diag   │ │           │
    └─────┬──────┘ └────┬────┘ │           │
          │              │      │           │
          ▼              ▼      │           │
    ┌───────────┐ ┌────────────┐│           │
    │ human_    │ │ skill_     ││           │
    │ review    │ │ match_node ││           │
    └─────┬─────┘ └──────┬─────┘│           │
          │              │      │           │
          ▼              ▼      │           │
    ┌───────────┐ ┌────────────┐│           │
    │ ssh_login │ │ react_     ││           │
    │ _node     │ │ agent_node ││           │
    └─────┬─────┘ │(ReAct循环) ││           │
          │       └──────┬─────┘│           │
          │              │      │           │
          │       ┌──────┼──────┐           │
          │       ▼             ▼           │
          │ ┌───────────┐ ┌──────────┐      │
          │ │ completed │ │ needs_   │      │
          │ │           │ │ confirm  │      │
          │ └─────┬─────┘ └────┬─────┘      │
          │       │            │            │
          │       │            ▼            │
          │       │     ┌───────────┐       │
          │       │     │ approval_ │       │
          │       │     │ node      │       │
          │       │     └─────┬─────┘       │
          │       │           │             │
          ▼       ▼           ▼             ▼
          └───────────────┬────┘─────────────┘
                          │
                          ▼
                   ┌───────────┐
                   │  END       │
                   └───────────┘
```

### 3.2 全局状态定义

```python
from typing import TypedDict, Annotated, List, Dict, Any, Optional
from langgraph.graph.message import add_messages


class AIOpsState(TypedDict):
    messages: Annotated[list, add_messages]
    user_query: str
    intent_data: Optional[Dict[str, Any]]
    entities: Optional[Dict[str, Any]]
    intent_type: Optional[str]
    need_ssh_login: bool
    ssh_confirmed: bool
    ssh_user: Optional[str]
    matched_skills: List[str]
    skills_content: str
    knowledge_context: Optional[Dict[str, Any]]
    observability_report: Optional[Dict[str, Any]]
    execution_history: List[Dict[str, Any]]
    diagnosis_result: Optional[Dict[str, Any]]
    confirmation_request: Optional[Dict[str, Any]]
    approval_status: Optional[str]
    iteration_count: int
    error: Optional[str]
    warning_cleared: bool
```

---

## 四、核心代码实现

### 4.1 图构建

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode

from app.agents.langgraph.nodes import (
    intent_parse_node,
    route_intent_node,
    diagnose_entry_node,
    ssh_check_node,
    skill_match_node,
    react_agent_node,
    knowledge_qa_node,
    approval_node,
    human_review_node,
    finalize_node,
)
from app.agents.langgraph.routers import (
    route_after_intent,
    route_after_ssh_check,
    route_after_react,
)


def build_aiops_graph():
    graph = StateGraph(AIOpsState)

    graph.add_node("intent_parse", intent_parse_node)
    graph.add_node("route_intent", route_intent_node)
    graph.add_node("diagnose_entry", diagnose_entry_node)
    graph.add_node("ssh_check", ssh_check_node)
    graph.add_node("skill_match", skill_match_node)
    graph.add_node("react_agent", react_agent_node)
    graph.add_node("knowledge_qa", knowledge_qa_node)
    graph.add_node("approval", approval_node)
    graph.add_node("human_review", human_review_node)
    graph.add_node("finalize", finalize_node)

    graph.set_entry_point("intent_parse")

    graph.add_edge("intent_parse", "route_intent")

    graph.add_conditional_edges(
        "route_intent",
        route_after_intent,
        {
            "diagnose": "diagnose_entry",
            "query": "knowledge_qa",
            "qa": "knowledge_qa",
        },
    )

    graph.add_edge("diagnose_entry", "ssh_check")

    graph.add_conditional_edges(
        "ssh_check",
        route_after_ssh_check,
        {
            "need_confirm": "human_review",
            "continue": "skill_match",
        },
    )

    graph.add_edge("human_review", "skill_match")
    graph.add_edge("skill_match", "react_agent")

    graph.add_conditional_edges(
        "react_agent",
        route_after_react,
        {
            "completed": "finalize",
            "needs_confirmation": "approval",
            "continue": "react_agent",
        },
    )

    graph.add_conditional_edges(
        "approval",
        lambda state: "approved" if state.get("approval_status") == "approved" else "rejected",
        {
            "approved": "react_agent",
            "rejected": "finalize",
        },
    )

    graph.add_edge("knowledge_qa", "finalize")
    graph.add_edge("finalize", END)

    memory = MemorySaver()

    return graph.compile(
        checkpointer=memory,
        interrupt_before=["human_review", "approval"],
    )
```

### 4.2 节点实现

#### 意图解析节点

```python
from app.agents.intent_parse import IntentParseAgent

_intent_agent = IntentParseAgent()


async def intent_parse_node(state: AIOpsState) -> dict:
    intent_result = await _intent_agent.parse(state["user_query"])
    entities_result = await _intent_agent.extract_entities(state["user_query"])

    entities_dict = entities_result.model_dump() if hasattr(entities_result, "model_dump") else entities_result

    return {
        "intent_data": {
            "intent": intent_result.intent,
            "confidence": intent_result.confidence,
            "entities": entities_dict,
            "normalized_query": intent_result.normalized_query,
            "ner_entities": [e.model_dump() if hasattr(e, "model_dump") else e for e in intent_result.ner_entities],
            "keywords": intent_result.keywords,
        },
        "entities": entities_dict,
        "intent_type": intent_result.intent,
        "messages": [{"role": "system", "content": f"意图识别完成: {intent_result.intent}, 置信度: {intent_result.confidence}"}],
    }
```

#### 条件路由节点

```python
def route_after_intent(state: AIOpsState) -> str:
    intent_type = state.get("intent_type", "GENERAL_QA")

    if intent_type == "DIAGNOSE":
        return "diagnose"
    elif intent_type == "QUERY_STATUS":
        return "query"
    else:
        return "qa"
```

#### SSH 检查节点

```python
async def ssh_check_node(state: AIOpsState) -> dict:
    entities = state.get("entities", {})
    ssh_users = entities.get("ssh_users", [])
    servers = entities.get("servers", [])

    need_ssh = bool(servers) and not ssh_users

    if need_ssh:
        return {
            "need_ssh_login": True,
            "ssh_confirmed": False,
            "messages": [{"role": "assistant", "content": f"需要连接服务器 {servers}，请提供 SSH 登录用户名"}],
        }

    return {
        "need_ssh_login": False,
        "ssh_confirmed": True,
        "messages": [{"role": "assistant", "content": "SSH 信息完整，继续诊断"}],
    }


def route_after_ssh_check(state: AIOpsState) -> str:
    if state.get("need_ssh_login") and not state.get("ssh_confirmed"):
        return "need_confirm"
    return "continue"
```

#### 人工审核节点 (Human-in-the-loop)

```python
async def human_review_node(state: AIOpsState) -> dict:
    servers = state.get("entities", {}).get("servers", [])
    server_ip = servers[0].get("value", "") if servers else ""

    return {
        "confirmation_request": {
            "operation": f"确认 SSH 登录信息",
            "risk": "低风险（仅信息收集）",
            "impact": f"需要获取 SSH 用户名才能连接服务器 {server_ip}",
            "message": f"需要连接服务器进行诊断，请提供 SSH 登录用户名",
        },
    }
```

#### Skill 匹配节点

```python
from app.agents.skill_manager import SkillManager

_skill_manager = SkillManager()


async def skill_match_node(state: AIOpsState) -> dict:
    matched_skills = _skill_manager.search_relevant_skills(
        state["user_query"],
        state.get("intent_data", {}),
    )
    skills_content = _skill_manager.get_relevant_skills_content(matched_skills)

    return {
        "matched_skills": matched_skills,
        "skills_content": skills_content,
        "messages": [{"role": "system", "content": f"匹配到 {len(matched_skills)} 个 Skill: {', '.join(matched_skills)}"}],
    }
```

#### ReAct Agent 节点 (核心)

```python
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool as lc_tool
from langgraph.prebuilt import create_react_agent
from app.core.config import settings


def _convert_tool_registry_to_langchain(tool_registry: ToolRegistry) -> list:
    """将现有 ToolRegistry 转换为 LangChain Tool 格式"""
    lc_tools = []

    for tool_def in tool_registry.get_tools_for_llm():
        func_info = tool_def["function"]
        name = func_info["name"]
        description = func_info["description"]
        params_schema = func_info["parameters"]

        async def make_tool_func(tool_name: str):
            async def tool_func(**kwargs):
                return await tool_registry.execute(tool_name, **kwargs)
            return tool_func

        lc_tool_instance = lc_tool(
            name=name,
            description=description,
            args_schema=params_schema,
        )(await make_tool_func(name))

        lc_tools.append(lc_tool_instance)

    return lc_tools


def create_react_agent_node(tool_registry: ToolRegistry):
    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
        temperature=0.2,
    )

    lc_tools = _convert_tool_registry_to_langchain(tool_registry)

    react_agent = create_react_agent(
        llm,
        lc_tools,
        state_modifier=_build_system_prompt(),
    )

    return react_agent


async def react_agent_node(state: AIOpsState) -> dict:
    react_agent = create_react_agent_node(_get_tool_registry())

    user_message = _build_user_message(state)
    input_messages = state.get("messages", []) + [{"role": "user", "content": user_message}]

    result = await react_agent.ainvoke({"messages": input_messages})

    last_message = result["messages"][-1]

    if _is_submit_result(last_message):
        return {
            "diagnosis_result": _extract_diagnosis(last_message),
            "messages": result["messages"],
            "iteration_count": state.get("iteration_count", 0) + 1,
        }

    if _is_ask_confirmation(last_message):
        return {
            "confirmation_request": _extract_confirmation(last_message),
            "messages": result["messages"],
            "iteration_count": state.get("iteration_count", 0) + 1,
        }

    return {
        "messages": result["messages"],
        "iteration_count": state.get("iteration_count", 0) + 1,
    }


def route_after_react(state: AIOpsState) -> str:
    if state.get("diagnosis_result"):
        return "completed"
    if state.get("confirmation_request") and not state.get("approval_status"):
        return "needs_confirmation"
    return "continue"
```

#### 审批节点

```python
async def approval_node(state: AIOpsState) -> dict:
    confirmation = state.get("confirmation_request", {})

    return {
        "approval_status": "pending",
        "messages": [{"role": "system", "content": f"等待用户审批: {confirmation.get('operation', '')}"}],
    }
```

#### 知识问答节点

```python
from app.agents.knowledge import KnowledgeExpertAgent

_knowledge_agent = KnowledgeExpertAgent()


async def knowledge_qa_node(state: AIOpsState) -> dict:
    entities = state.get("entities", {})
    services = entities.get("services", [])
    service = services[0].get("normalized", "unknown") if services else "unknown"
    symptoms = entities.get("symptoms", [])
    symptom_str = ", ".join([s.get("value", "") if isinstance(s, dict) else s for s in symptoms])

    knowledge_result = await _knowledge_agent.query(service=service, symptom=symptom_str)

    return {
        "knowledge_context": knowledge_result.model_dump() if hasattr(knowledge_result, "model_dump") else knowledge_result,
        "diagnosis_result": {
            "decision": "KNOWLEDGE_QA",
            "knowledge_report": knowledge_result.knowledge_report,
            "topology_info": knowledge_result.topology_info.model_dump() if hasattr(knowledge_result.topology_info, "model_dump") else knowledge_result.topology_info,
        },
    }
```

#### 结果汇总节点

```python
async def finalize_node(state: AIOpsState) -> dict:
    from datetime import datetime

    return {
        "messages": [{"role": "assistant", "content": "诊断流程已完成"}],
    }
```

### 4.3 API 集成

```python
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/multi-agent", tags=["multi-agent"])


class MultiAgentRequest(BaseModel):
    query: str
    stream: Optional[bool] = False
    session_id: Optional[str] = None


_graph = build_aiops_graph()


@router.post("/process")
async def process_multi_agent_query(request: MultiAgentRequest):
    config = {"configurable": {"thread_id": request.session_id or "default"}}

    result = await _graph.ainvoke(
        {
            "user_query": request.query,
            "messages": [],
            "iteration_count": 0,
            "need_ssh_login": False,
            "ssh_confirmed": False,
            "warning_cleared": False,
        },
        config=config,
    )

    return {
        "query": request.query,
        "intent_data": result.get("intent_data"),
        "matched_skills": result.get("matched_skills"),
        "diagnosis_result": result.get("diagnosis_result"),
        "confirmation_request": result.get("confirmation_request"),
        "warning_cleared": result.get("warning_cleared", False),
    }


@router.post("/process/stream")
async def process_multi_agent_stream(request: MultiAgentRequest):
    from starlette.responses import StreamingResponse
    import json

    config = {"configurable": {"thread_id": request.session_id or "default"}}

    async def event_generator():
        async for event in _graph.astream_events(
            {
                "user_query": request.query,
                "messages": [],
                "iteration_count": 0,
                "need_ssh_login": False,
                "ssh_confirmed": False,
                "warning_cleared": False,
            },
            config=config,
            version="v2",
        ):
            yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/approve")
async def approve_operation(session_id: str, approved: bool, ssh_user: str = None):
    config = {"configurable": {"thread_id": session_id}}

    current_state = await _graph.aget_state(config)

    if approved:
        update = {"approval_status": "approved"}
        if ssh_user:
            update["ssh_user"] = ssh_user
            update["ssh_confirmed"] = True
        await _graph.aupdate_state(config, update, as_node="human_review")
    else:
        await _graph.aupdate_state(config, {"approval_status": "rejected"}, as_node="approval")

    result = await _graph.ainvoke(None, config=config)

    return {
        "approved": approved,
        "diagnosis_result": result.get("diagnosis_result"),
    }
```

---

## 五、重构前后对比

### 5.1 架构对比

| 维度 | 重构前 | 重构后 (LangGraph) |
|------|--------|-------------------|
| **编排方式** | 手动 while 循环 | 声明式状态图 |
| **状态管理** | 字典传递，无持久化 | TypedDict + Checkpoint |
| **流程控制** | if/else 硬编码 | 条件边 (conditional_edges) |
| **断点续跑** | 不支持 | Checkpoint 自动保存 |
| **人工审批** | 工具层 (ask_user_confirmation) | 图级别 (interrupt_before) |
| **流式输出** | SSE 粗粒度 | astream_events 按节点粒度 |
| **调试** | print 日志 | LangSmith 集成 |
| **可观测性** | 手动记录 execution_history | 自动追踪每个节点 |

### 5.2 代码量对比

| 模块 | 重构前 | 重构后 |
|------|--------|--------|
| Orchestrator | ~515 行 | ~60 行 (图定义) |
| MasterAgent | ~544 行 | ~80 行 (ReAct 节点) |
| 流程控制逻辑 | 散布在多个文件 | 集中在图定义 |
| 审批流程 | 工具层实现 | 图级别中断 |

---

## 六、重构步骤

### Phase 1: 基础设施 (1-2 天)

1. 安装 LangGraph 依赖
2. 定义 `AIOpsState` 状态结构
3. 创建 `app/agents/langgraph/` 目录结构

```
app/agents/langgraph/
├── __init__.py
├── state.py          # 状态定义
├── graph.py          # 图构建
├── nodes/
│   ├── __init__.py
│   ├── intent_parse.py
│   ├── ssh_check.py
│   ├── skill_match.py
│   ├── react_agent.py
│   ├── knowledge_qa.py
│   ├── approval.py
│   ├── human_review.py
│   └── finalize.py
├── routers/
│   ├── __init__.py
│   ├── intent_router.py
│   ├── ssh_router.py
│   └── react_router.py
└── tools/
    ├── __init__.py
    └── adapter.py     # ToolRegistry → LangChain Tool 适配器
```

### Phase 2: 节点迁移 (2-3 天)

1. 将 `IntentParseAgent.parse()` 封装为 `intent_parse_node`
2. 将 SSH 检查逻辑封装为 `ssh_check_node`
3. 将 `SkillManager` 封装为 `skill_match_node`
4. 将 `MasterAgent.plan_and_execute()` 替换为 `react_agent_node`
5. 将 `KnowledgeExpertAgent` 封装为 `knowledge_qa_node`

### Phase 3: 图构建与路由 (1-2 天)

1. 构建 `StateGraph`
2. 实现条件路由函数
3. 配置 Checkpoint
4. 配置 `interrupt_before` 人工审批点

### Phase 4: API 集成 (1 天)

1. 替换 `/api/multi-agent/process` 实现
2. 替换 `/api/multi-agent/process/stream` 实现
3. 新增 `/api/multi-agent/approve` 审批接口
4. 新增 `/api/multi-agent/state` 状态查询接口

### Phase 5: 测试与优化 (1-2 天)

1. 单元测试各节点
2. 集成测试完整流程
3. 性能测试与优化
4. LangSmith 集成调试

---

## 七、面试问答指南

### Q1: 为什么要用 LangGraph 重构？

> 原有架构中 ReAct 循环是手动实现的 while 循环，存在三个核心问题：
>
> **1. 无状态持久化**：诊断过程中断后无法恢复，需要从头开始。LangGraph 的 Checkpoint 机制自动保存每个节点执行后的状态，支持断点续跑。
>
> **2. 人机协同粒度粗**：原方案通过 `ask_user_confirmation` 工具在 ReAct 循环内部实现审批，LLM 需要额外调用工具才能暂停。LangGraph 的 `interrupt_before` 在图级别中断执行，人工审批后再继续，更符合生产场景。
>
> **3. 流程不透明**：原方案的流程控制散布在 orchestrator 和 master agent 中，调试困难。LangGraph 的声明式状态图让流程一目了然，配合 LangSmith 可以追踪每个节点的输入输出。

### Q2: LangGraph 的 Checkpoint 机制如何工作？

> LangGraph 使用 Checkpointer 在每个节点执行后自动保存状态快照。当执行中断（如人工审批、网络超时），可以从最近的 Checkpoint 恢复执行，而不需要从头开始。
>
> 在我们的场景中，一个完整的诊断流程可能涉及 10+ 次工具调用，耗时数分钟。如果在中途需要人工审批，Checkpoint 保存当前所有状态（包括 messages、execution_history、matched_skills 等），审批通过后直接从断点继续。
>
> 支持 MemorySaver（内存）和 SqliteSaver / AsyncPostgresSaver（持久化）。

### Q3: 你是如何处理 ToolRegistry 与 LangGraph 的集成的？

> 原有项目有 25+ 个工具注册在 `ToolRegistry` 中，使用 OpenAI function calling 格式。LangGraph 的 ReAct Agent 需要 LangChain Tool 格式。
>
> 我编写了一个适配器 `_convert_tool_registry_to_langchain()`，将 ToolRegistry 中的工具定义转换为 LangChain `@tool` 装饰器格式，同时保持底层执行逻辑不变。这样既复用了现有的安全检查（7 层防护）和工具实现，又能无缝接入 LangGraph 的 ReAct Agent。

### Q4: 重构后如何实现流式输出？

> 原方案使用 SSE 在 orchestrator 层实现流式输出，粒度较粗。
>
> LangGraph 提供 `astream_events()` 方法，可以按节点粒度流式推送事件。前端可以实时看到当前执行到哪个节点、每个节点的输入输出。例如：
> - `intent_parse` 节点完成 → 推送意图识别结果
> - `skill_match` 节点完成 → 推送匹配到的 Skill
> - `react_agent` 节点每次工具调用 → 推送工具执行结果
>
> 这比原方案的流式输出更细粒度，用户体验更好。

### Q5: 重构中遇到的最大挑战是什么？

> 最大的挑战是 **ReAct 循环的终止条件迁移**。
>
> 原方案中，MasterAgent 的 ReAct 循环通过 `submit_diagnosis_result` 和 `ask_user_confirmation` 两个工具来终止。在 LangGraph 中，ReAct Agent 是预构建的，终止条件由 LLM 自行决定。
>
> 我的解决方案是：
> 1. 保留 `submit_diagnosis_result` 作为终止工具，在 system prompt 中强调必须调用此工具结束
> 2. `ask_user_confirmation` 不再作为工具，而是通过图级别的 `interrupt_before` 实现
> 3. 在 `route_after_react` 路由函数中检查状态，决定是继续循环还是跳转到审批节点
> 4. 设置 `max_iterations` 防止无限循环