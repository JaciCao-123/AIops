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

        intent_data = result.get("intent_data", {})
        diagnosis_result = result.get("diagnosis_result", {})
        confirmation_request = result.get("confirmation_request")
        approval_status = result.get("approval_status")
        matched_skills = result.get("matched_skills", [])
        warning_cleared = result.get("warning_cleared", False)

        entities_raw = intent_data.get("entities", {})
        services_list = entities_raw.get("services", [])
        symptoms_list = entities_raw.get("symptoms", [])
        servers_list = entities_raw.get("servers", [])

        flat_entities = {
            "service": services_list[0].get("normalized", services_list[0].get("value", "")) if services_list else "",
            "symptom": symptoms_list[0].get("normalized", symptoms_list[0].get("value", "")) if symptoms_list else "",
            "time_range": entities_raw.get("time_range", ""),
            "servers": [s.get("normalized", s.get("value", "")) if isinstance(s, dict) else s for s in servers_list],
            "services": [s.get("normalized", s.get("value", "")) if isinstance(s, dict) else s for s in services_list],
            "symptoms": [s.get("normalized", s.get("value", "")) if isinstance(s, dict) else s for s in symptoms_list],
            "_raw": entities_raw,
        }

        final_decision = None
        if confirmation_request:
            final_decision = {
                "decision": "NEEDS_CONFIRMATION",
                "is_final": False,
                "confirmation_request": confirmation_request,
                "root_cause_summary": diagnosis_result.get("root_cause", ""),
                "reasoning": diagnosis_result.get("analysis_summary", ""),
                "action_plan": diagnosis_result.get("recommendation", ""),
                "risk_level": diagnosis_result.get("risk_level", "MEDIUM"),
            }
        elif diagnosis_result:
            problem_type = diagnosis_result.get("problem_type", "unknown")
            if not problem_type or problem_type == "unknown":
                dr_decision = diagnosis_result.get("decision", "")
                if dr_decision == "KNOWLEDGE_QA":
                    problem_type = "knowledge_qa"
                elif diagnosis_result.get("knowledge_report"):
                    problem_type = "knowledge_qa"

            final_decision = {
                "decision": "RESOLVED" if problem_type in ("none", "knowledge_qa") else "MANUAL_INTERVENTION",
                "is_final": True,
                "problem_type": problem_type,
                "root_cause": diagnosis_result.get("root_cause", diagnosis_result.get("knowledge_report", "")[:200]),
                "root_cause_summary": diagnosis_result.get("root_cause", diagnosis_result.get("knowledge_report", "")[:200]),
                "impact": diagnosis_result.get("impact", "无直接影响"),
                "recommendation": diagnosis_result.get("recommendation", diagnosis_result.get("knowledge_report", "")[:300]),
                "action_plan": diagnosis_result.get("recommendation", diagnosis_result.get("knowledge_report", "")[:300]),
                "risk_level": diagnosis_result.get("risk_level", "LOW"),
                "confidence": diagnosis_result.get("confidence", "MEDIUM"),
                "reasoning": diagnosis_result.get("analysis_summary", diagnosis_result.get("knowledge_report", "")),
                "analysis_summary": diagnosis_result.get("analysis_summary", diagnosis_result.get("knowledge_report", "")),
            }
        elif approval_status == "rejected":
            final_decision = {
                "decision": "REJECTED",
                "reason": "用户拒绝了操作请求",
            }
        elif result.get("need_ssh_login") or servers_list:
            host = servers_list[0].get("normalized", servers_list[0].get("value", str(servers_list[0]))) if servers_list else "目标服务器"
            final_decision = {
                "decision": "NEEDS_CONFIRMATION",
                "is_final": False,
                "confirmation_request": {
                    "success": True,
                    "requires_confirmation": True,
                    "operation": f"确认 SSH 登录信息",
                    "risk": "低风险（仅信息收集）",
                    "impact": f"需要获取 SSH 用户名才能连接服务器 {host} 进行诊断",
                    "message": f"需要连接服务器 {host} 进行诊断，请在查询中包含 SSH 用户名（例如：用 jaci 用户 SSH 登录）",
                },
                "root_cause_summary": f"缺少 {host} 的 SSH 登录用户名",
                "reasoning": f"意图识别检测到需要连接服务器 {host}，但未提供 SSH 用户名",
                "action_plan": "在查询中补充 SSH 用户名后重新提交，例如：用 <用户名> SSH 登录 8.136.186.115",
                "risk_level": "LOW",
            }
        else:
            final_decision = {
                "decision": "MANUAL_INTERVENTION",
                "reason": "诊断流程未产出最终结论",
            }

        end_time = datetime.now()
        iteration_count = result.get("iteration_count", 0)
        execution_history = result.get("execution_history", [])

        skill_summary = ", ".join(matched_skills) if matched_skills else "未匹配到特定技能，使用通用诊断流程"
        skills_preview = result.get("skills_content", "")[:500]

        diagnosis_plan_from_history = None
        command_entries = []
        email_entry = None

        for entry in execution_history:
            tool = entry.get("tool", "")
            args = entry.get("args", {}) or {}
            res = entry.get("result", {}) or {}

            if tool == "save_diagnosis_plan":
                diagnosis_plan_from_history = {
                    "plan_name": args.get("plan_name", args.get("check_type", "")),
                    "check_type": args.get("check_type", ""),
                    "commands": args.get("commands", []) if isinstance(args.get("commands"), list) else [],
                    "reasoning": str(args.get("reasoning", ""))[:500],
                }

            if tool == "execute_command":
                output_str = ""
                if isinstance(res, dict):
                    output_str = res.get("output", "") or res.get("error", "")
                elif isinstance(res, str):
                    output_str = res

                if isinstance(output_str, str) and len(output_str) > 2000:
                    output_str = output_str[:2000] + "\n... (truncated)"

                cmd_entry = {
                    "command": args.get("command", "")[:200],
                    "target_host": args.get("target_host", res.get("target_host", "") if isinstance(res, dict) else ""),
                    "success": True if (isinstance(res, dict) and res.get("success")) else False,
                    "output": output_str,
                }
                command_entries.append(cmd_entry)

            if tool == "ask_user_confirmation" and isinstance(res, dict) and res.get("email_sent"):
                email_entry = {
                    "email_sent": True,
                    "approval_id": res.get("approval_id", ""),
                    "to_email": res.get("to_email", ""),
                    "operation": res.get("operation", ""),
                    "risk": res.get("risk", ""),
                    "message": res.get("message", ""),
                    "status": "pending",
                }

        dynamic_status = "completed"
        if confirmation_request or result.get("need_ssh_login"):
            dynamic_status = "needs_confirmation"
        if email_entry:
            dynamic_status = "waiting_approval"

        analysis_report = diagnosis_result.get("analysis_summary", "")
        if not analysis_report:
            km = result.get("knowledge_context", {})
            if isinstance(km, dict):
                analysis_report = km.get("knowledge_report", str(km)[:500])

        knowledge_report = ""
        if diagnosis_result.get("root_cause"):
            knowledge_report += f"根本原因: {diagnosis_result['root_cause']}\n\n"
        if analysis_report:
            knowledge_report += analysis_report
        if not knowledge_report:
            knowledge_report = "诊断分析进行中..."

        stages = {
            "intent_parsing": {
                "intent": intent_data.get("intent", "GENERAL_QA"),
                "confidence": intent_data.get("confidence", "LOW"),
                "entities": flat_entities,
                "keywords": intent_data.get("keywords", []),
                "normalized_query": intent_data.get("normalized_query", "") or request.query,
            },
            "skill_matching": {
                "matched_skills": matched_skills,
                "skill_summary": skill_summary,
                "skills_content_length": len(result.get("skills_content", "")),
                "skills_preview": skills_preview,
            },
            "observability_analysis": {
                "analysis_report": analysis_report or "待分析",
                "diagnosis_plan": diagnosis_plan_from_history,
            },
            "knowledge_query": {
                "knowledge_report": knowledge_report,
                "service": flat_entities.get("service", ""),
            },
            "dynamic_execution": {
                "status": dynamic_status,
                "iterations": iteration_count,
                "command_entries": command_entries,
                "email_approval": email_entry,
            },
        }

        display_execution_result = {
            "tool_name": "ReAct Agent (LangGraph)",
            "template_name": "LangGraph StateGraph",
            "risk_assessment": diagnosis_result.get("risk_level", "MEDIUM"),
            "requires_approval": bool(email_entry),
            "execution_note": diagnosis_result.get("recommendation", "诊断完成，详见上方报告"),
        }

        return JSONResponse(
            content={
                "query": request.query,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": (end_time - start_time).total_seconds(),
                "stages": stages,
                "final_decision": final_decision,
                "execution_result": display_execution_result,
                "warning_cleared": warning_cleared,
                "mode": "langgraph",
                "iteration_count": iteration_count,
                "diagnosis_result": diagnosis_result,
                "raw_response": analysis_report or knowledge_report,
                "execution_history": execution_history,
                "saved_to": result.get("full_result_path"),
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


@router.post("/approve/{approval_id}")
async def approve_operation(approval_id: str):
    """
    手动批准审批请求
    """
    from app.utils.email_sender import email_sender as _es
    
    approval = _es.approval_manager.get_approval(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail=f"未找到审批ID: {approval_id}")
    
    if approval.get("status") != "pending":
        return {
            "success": True,
            "approval_id": approval_id,
            "status": approval.get("status"),
            "message": f"审批已处理，当前状态: {approval.get('status')}"
        }
    
    result = _es.approval_manager.approve(approval_id, "api_manual")
    if not result:
        raise HTTPException(status_code=500, detail="审批操作失败")
    
    return {
        "success": True,
        "approval_id": approval_id,
        "status": "approved",
        "message": "审批已通过",
        "commands": result.get("commands", []),
        "target_host": result.get("target_host", ""),
    }


@router.post("/reject/{approval_id}")
async def reject_operation(approval_id: str):
    """
    手动拒绝审批请求
    """
    from app.utils.email_sender import email_sender as _es
    
    approval = _es.approval_manager.get_approval(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail=f"未找到审批ID: {approval_id}")
    
    if approval.get("status") != "pending":
        return {
            "success": True,
            "approval_id": approval_id,
            "status": approval.get("status"),
            "message": f"审批已处理，当前状态: {approval.get('status')}"
        }
    
    _es.approval_manager.reject(approval_id, "api_manual")
    
    return {
        "success": True,
        "approval_id": approval_id,
        "status": "rejected",
        "message": "审批已拒绝"
    }


@router.get("/approvals/pending")
async def list_pending_approvals():
    """
    列出所有待审批的操作
    """
    from app.utils.email_sender import email_sender as _es
    from pathlib import Path
    
    data_dir = Path("data/approvals")
    pending = []
    for fp in data_dir.glob("*.json"):
        try:
            with open(fp) as f:
                d = json.load(f)
                if d.get("status") == "pending":
                    pending.append(d)
        except Exception:
            pass
    
    return {
        "success": True,
        "count": len(pending),
        "pending": pending
    }


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "multi-agent",
        "backend": "LangGraph",
        "deprecated": False,
        "note": "后端已迁移至 LangGraph 实现。旧版 Orchestrator 模式不再维护。",
    }
