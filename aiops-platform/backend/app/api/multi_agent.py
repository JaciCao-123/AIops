import uuid
import asyncio
import json
import warnings
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from app.agents.langgraph import build_aiops_graph, AIOpsState

router = APIRouter(prefix="/api/multi-agent", tags=["multi-agent"])

_graph = build_aiops_graph()

warnings.filterwarnings("always", message=".*deprecated.*", category=DeprecationWarning)


class MultiAgentRequest(BaseModel):
    query: str
    stream: Optional[bool] = False
    session_id: Optional[str] = None


class MultiAgentResponse(BaseModel):
    query: str
    start_time: str
    stages: Dict[str, Any]
    final_decision: Optional[Dict[str, Any]]
    execution_result: Optional[Dict[str, Any]]
    duration_seconds: float


@router.post("/process")
async def process_multi_agent_query(
    request: MultiAgentRequest,
    req: Request,
):
    """
    Multi-Agent 诊断查询 (已迁移至 LangGraph 后端)

    与旧版接口兼容的响应格式，后端已切换为 LangGraph 实现。
    """

    start_time = datetime.now()
    session_id = request.session_id or str(uuid.uuid4())[:8]

    config = {
        "configurable": {
            "thread_id": session_id
        },
        "recursion_limit": 50,
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

        intent_data = result.get("intent_data", {})
        diagnosis_result = result.get("diagnosis_result", {})
        confirmation_request = result.get("confirmation_request")
        approval_status = result.get("approval_status")
        matched_skills = result.get("matched_skills", [])
        warning_cleared = result.get("warning_cleared", False)

        final_decision = None
        if confirmation_request:
            final_decision = {
                "decision": "NEEDS_CONFIRMATION",
                "confirmation_request": confirmation_request,
            }
        elif diagnosis_result:
            problem_type = diagnosis_result.get("problem_type", "unknown")
            final_decision = {
                "decision": "RESOLVED" if problem_type == "none" else "MANUAL_INTERVENTION",
                "problem_type": problem_type,
                "root_cause": diagnosis_result.get("root_cause", ""),
                "root_cause_summary": diagnosis_result.get("root_cause", ""),
                "impact": diagnosis_result.get("impact", ""),
                "recommendation": diagnosis_result.get("recommendation", ""),
                "action_plan": diagnosis_result.get("recommendation", ""),
                "risk_level": diagnosis_result.get("risk_level", "MEDIUM"),
                "confidence": diagnosis_result.get("confidence", "MEDIUM"),
                "reasoning": diagnosis_result.get("analysis_summary", ""),
                "analysis_summary": diagnosis_result.get("analysis_summary", ""),
            }
        elif approval_status == "rejected":
            final_decision = {
                "decision": "REJECTED",
                "reason": "用户拒绝了操作请求",
            }
        else:
            final_decision = {
                "decision": "MANUAL_INTERVENTION",
                "reason": "诊断流程未产出最终结论",
            }

        end_time = datetime.now()

        stages = {
            "intent_parsing": {
                "intent": intent_data.get("intent", "GENERAL_QA"),
                "confidence": intent_data.get("confidence", "LOW"),
                "entities": intent_data.get("entities", {}),
                "keywords": intent_data.get("keywords", []),
            },
            "skill_matching": {
                "matched_skills": matched_skills,
                "skills_content_length": len(result.get("skills_content", "")),
            },
        }

        return JSONResponse(
            content={
                "query": request.query,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": (end_time - start_time).total_seconds(),
                "stages": stages,
                "final_decision": final_decision,
                "execution_result": diagnosis_result,
                "warning_cleared": warning_cleared,
                "mode": "langgraph",
                "iteration_count": result.get("iteration_count", 0),
                "diagnosis_result": diagnosis_result,
                "raw_response": diagnosis_result.get("analysis_summary", ""),
            },
            headers={
                "X-Backend": "langgraph",
                "X-Deprecation-Notice": "Backend migrated to LangGraph. New API: POST /api/multi-agent-lg/process",
            },
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"处理查询时发生错误: {str(e)}",
        )


@router.post("/process/stream")
async def process_multi_agent_stream(request: MultiAgentRequest):
    """流式处理 multi-agent 查询 (LangGraph 后端)"""
    config = {
        "configurable": {
            "thread_id": request.session_id or "default"
        }
    }

    async def event_generator():
        yield f"data: {json.dumps({'type': 'info', 'message': '后端已切换至 LangGraph，事件格式可能有变化'}, ensure_ascii=False)}\n\n"
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


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "multi-agent",
        "backend": "LangGraph",
        "deprecated": False,
        "note": "后端已迁移至 LangGraph 实现。旧版 Orchestrator 模式不再维护。",
    }
