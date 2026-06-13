import json
from typing import Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agents.langgraph import build_aiops_graph, AIOpsState

router = APIRouter(prefix="/api/multi-agent-lg", tags=["multi-agent-langgraph"])

_graph = build_aiops_graph()


class LangGraphRequest(BaseModel):
    query: str
    stream: Optional[bool] = False
    session_id: Optional[str] = None


class ApproveRequest(BaseModel):
    session_id: str
    approved: bool
    ssh_user: Optional[str] = None


@router.post("/process")
async def process_multi_agent_query(request: LangGraphRequest):
    config = {
        "configurable": {
            "thread_id": request.session_id or "default"
        },
        "recursion_limit": 100,
    }

    try:
        result = await _graph.ainvoke(
            {
                "user_query": request.query,
                "messages": [],
                "iteration_count": 0,
                "need_ssh_login": False,
                "ssh_confirmed": False,
                "warning_cleared": False,
                "matched_skills": [],
                "skills_content": "",
                "execution_history": [],
            },
            config=config,
        )

        return {
            "query": request.query,
            "intent_data": result.get("intent_data"),
            "matched_skills": result.get("matched_skills"),
            "diagnosis_result": result.get("diagnosis_result"),
            "confirmation_request": result.get("confirmation_request"),
            "approval_status": result.get("approval_status"),
            "warning_cleared": result.get("warning_cleared", False),
            "iteration_count": result.get("iteration_count", 0),
            "execution_history": result.get("execution_history", []),
            "saved_to": result.get("full_result_path"),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"处理查询时发生错误: {str(e)}",
        )


@router.post("/process/stream")
async def process_multi_agent_stream(request: LangGraphRequest):
    config = {
        "configurable": {
            "thread_id": request.session_id or "default"
        },
        "recursion_limit": 100,
    }

    async def event_generator():
        async for event in _graph.astream_events(
            {
                "user_query": request.query,
                "messages": [],
                "iteration_count": 0,
                "need_ssh_login": False,
                "ssh_confirmed": False,
                "warning_cleared": False,
                "matched_skills": [],
                "skills_content": "",
                "execution_history": [],
            },
            config=config,
            version="v2",
        ):
            yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


@router.post("/approve")
async def approve_operation(request: ApproveRequest):
    config = {
        "configurable": {"thread_id": request.session_id}
    }

    try:
        current_state = await _graph.aget_state(config)

        if not current_state.values:
            raise HTTPException(
                status_code=404,
                detail=f"未找到 session: {request.session_id}",
            )

        if request.approved:
            update = {"approval_status": "approved"}
            if request.ssh_user:
                update["ssh_user"] = request.ssh_user
                update["ssh_confirmed"] = True
            await _graph.aupdate_state(
                config, update, as_node="human_review"
            )
        else:
            await _graph.aupdate_state(
                config,
                {"approval_status": "rejected"},
                as_node="approval",
            )

        result = await _graph.ainvoke(None, config=config)

        return {
            "approved": request.approved,
            "diagnosis_result": result.get("diagnosis_result"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"审批操作失败: {str(e)}",
        )


@router.get("/state/{session_id}")
async def get_session_state(session_id: str):
    config = {"configurable": {"thread_id": session_id}}

    try:
        state = await _graph.aget_state(config)

        if not state.values:
            raise HTTPException(
                status_code=404,
                detail=f"未找到 session: {session_id}",
            )

        return {
            "session_id": session_id,
            "values": {
                k: v
                for k, v in state.values.items()
                if k != "messages"
            },
            "next": state.next,
            "created_at": state.created_at if hasattr(state, "created_at") else None,
            "parent_config": (
                state.parent_config if hasattr(state, "parent_config") else None
            ),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取状态失败: {str(e)}",
        )


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "multi-agent-langgraph",
        "framework": "LangGraph",
        "features": [
            "state_graph",
            "checkpoint",
            "human_in_the_loop",
            "streaming",
            "conditional_routing",
        ],
    }