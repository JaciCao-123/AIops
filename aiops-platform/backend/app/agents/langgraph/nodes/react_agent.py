import json
from typing import Dict, Any, List

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool as lc_tool
from pydantic import BaseModel as LCBaseModel, create_model, Field
from langgraph.prebuilt import create_react_agent

from ..state import AIOpsState
from app.agents.tool_registry import ToolRegistry
from app.core.config import settings
from app.utils.file_manager import IntermediateFileManager

_tool_registry = ToolRegistry(IntermediateFileManager())


def _build_param_model(name: str, params_schema: dict):
    fields = {}
    properties = params_schema.get("properties", {})
    required = set(params_schema.get("required", []))

    for field_name, field_info in properties.items():
        field_type = field_info.get("type", "string")

        type_map = {
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        python_type = type_map.get(field_type, str)

        if field_name not in required:
            fields[field_name] = (python_type, Field(default=None))
        else:
            fields[field_name] = (python_type, ...)

    if not fields:
        fields["_placeholder"] = (str, Field(default=None))

    return create_model(f"{name}Schema", **fields)


def _convert_tool_registry_to_langchain(registry: ToolRegistry) -> list:
    lc_tools = []

    for tool_def in registry.get_tools_for_llm():
        func_info = tool_def["function"]
        tool_name = func_info["name"]
        description = func_info["description"]
        params_schema = func_info.get("parameters", {})

        try:
            args_schema = _build_param_model(tool_name, params_schema)
        except Exception:
            args_schema = None

        def make_tool_func(tn: str, desc: str, schema):
            if schema is not None:
                @lc_tool(args_schema=schema)
                async def tool_func(**kwargs) -> str:
                    """execute tool"""
                    result = await registry.execute(tn, **kwargs)
                    return json.dumps(result, ensure_ascii=False, default=str)
            else:
                @lc_tool
                async def tool_func(**kwargs) -> str:
                    """execute tool"""
                    result = await registry.execute(tn, **kwargs)
                    return json.dumps(result, ensure_ascii=False, default=str)

            tool_func.name = tn
            tool_func.description = desc
            return tool_func

        lc_tools.append(make_tool_func(tool_name, description, args_schema))

    return lc_tools


SYSTEM_PROMPT = """你是一个智能运维诊断专家。你需要根据用户的问题和 skill 文件中的方法，动态规划并执行诊断流程。

## ReAct 诊断工作流程

### 0. 规划阶段（必须首先执行）
在开始执行任何诊断命令之前，你必须：
1. 根据匹配的 skill 文件内容，制定诊断计划
2. 调用 `save_diagnosis_plan` 工具保存诊断计划
3. 然后按计划逐步执行诊断步骤

### 1. 思考 (Thought)
在每次行动前，你必须先思考：
- 当前已有哪些信息？
- 还需要哪些信息？
- 下一步应该做什么？
- 这个操作是否安全？

### 2. 行动 (Action)
根据思考结果，选择合适的工具执行。

### 3. 观察 (Observation)
分析工具返回的结果，决定是否需要进一步行动。

### 4. 终止条件
必须调用 `submit_diagnosis_result` 工具提交诊断结果。这是唯一正确的结束方式。

## 安全规则
- 危险命令绝对禁止执行 (rm -rf, shutdown, reboot, dd, mkfs 等)
- 中风险操作需要调用 `ask_user_confirmation` 获取用户确认（会自动发送审批邮件）
- 执行命令后如果返回 requires_confirmation=true 或 risk_level=L2/L3，必须调用 `ask_user_confirmation` 工具，**并传递原始的 `command` 参数和 `target_host`**
- 调用 `ask_user_confirmation` 后会获得 `approval_id`，然后调用 `wait_for_approval` 等待邮件审批（timeout_seconds=60）
- **审批通过前不要调用 submit_diagnosis_result**，必须先完成 `wait_for_approval` → `execute_approved_command` 流程
- 审批通过后使用 `execute_approved_command(approval_id)` 执行已批准的命令
- 只读操作可以安全执行

## SSH 连接
- 如果需要远程连接服务器，使用 `execute_command` 工具并设置 `target_host` 参数
- 如果用户查询中提到了用户名，使用 `ssh_user` 参数传递
- 如果用户名未知，在查询中包含 SSH 用户名后重试
"""


def _build_user_message(state: AIOpsState) -> str:
    intent_data = state.get("intent_data", {})
    skills_content = state.get("skills_content", "")
    ssh_user = state.get("ssh_user")

    user_msg = f"""## 用户查询
{state["user_query"]}

## 意图识别结果
{json.dumps(intent_data, ensure_ascii=False, indent=2)}

## 可用的 Skill 文件
{skills_content}
"""

    if ssh_user:
        user_msg += f"\n## SSH 用户名\n{ssh_user}\n"

    user_msg += "\n请根据 skill 文件中的方法，开始诊断流程。"

    return user_msg


_react_agent = None


def _get_react_agent():
    global _react_agent
    if _react_agent is not None:
        return _react_agent

    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
        temperature=0.2,
    )

    lc_tools = _convert_tool_registry_to_langchain(_tool_registry)

    _react_agent = create_react_agent(
        llm,
        lc_tools,
        prompt=SYSTEM_PROMPT,
    )

    return _react_agent


async def react_agent_node(state: AIOpsState) -> dict:
    agent = _get_react_agent()

    user_message = _build_user_message(state)
    input_messages = state.get("messages", []) + [
        {"role": "user", "content": user_message}
    ]

    result = await agent.ainvoke(
        {"messages": input_messages},
        config={"recursion_limit": 200},
    )

    last_message = result["messages"][-1]
    content = (
        last_message.content
        if hasattr(last_message, "content")
        else str(last_message)
    )

    tool_calls_in_history = []
    for msg in result["messages"]:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls_in_history.append(tc)

    diagnosis_result = None
    confirmation_request = None

    for tc in tool_calls_in_history:
        if tc.get("name") == "submit_diagnosis_result":
            try:
                args = tc.get("args", {})
                if isinstance(args, str):
                    args = json.loads(args)
                diagnosis_result = {
                    "is_final": True,
                    "problem_type": args.get("problem_type", "unknown"),
                    "root_cause": args.get("root_cause", ""),
                    "impact": args.get("impact", ""),
                    "recommendation": args.get("recommendation", ""),
                    "risk_level": args.get("risk_level", "MEDIUM"),
                    "confidence": args.get("confidence", "MEDIUM"),
                    "analysis_summary": args.get("analysis_summary", ""),
                }
            except (json.JSONDecodeError, AttributeError):
                diagnosis_result = {"is_final": True, "raw_response": content}

        if tc.get("name") == "ask_user_confirmation":
            try:
                args = tc.get("args", {})
                if isinstance(args, str):
                    args = json.loads(args)
                confirmation_request = {
                    "operation": args.get("operation", ""),
                    "risk": args.get("risk", ""),
                    "impact": args.get("impact", ""),
                    "message": args.get("operation", "需要用户确认"),
                }
            except (json.JSONDecodeError, AttributeError):
                confirmation_request = {"message": "需要用户确认"}

    execution_history = []
    pending_tool_calls = {}
    for msg in result["messages"]:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                pending_tool_calls[tc.get("id", "")] = {
                    "tool": tc.get("name", ""),
                    "args": tc.get("args", {}) if isinstance(tc.get("args"), dict) else {},
                }
        if hasattr(msg, "tool_call_id") and getattr(msg, "tool_call_id", None):
            tc_id = msg.tool_call_id
            if tc_id in pending_tool_calls:
                entry = pending_tool_calls.pop(tc_id)
                content_raw = msg.content if hasattr(msg, "content") else ""
                try:
                    parsed = json.loads(content_raw) if isinstance(content_raw, str) else content_raw
                except (json.JSONDecodeError, TypeError):
                    parsed = {"output": str(content_raw)}
                entry["result"] = parsed if isinstance(parsed, dict) else {"output": str(content_raw)}
                execution_history.append(entry)

    return {
        "diagnosis_result": diagnosis_result,
        "confirmation_request": confirmation_request,
        "messages": result["messages"],
        "iteration_count": state.get("iteration_count", 0) + 1,
        "execution_history": execution_history,
    }
