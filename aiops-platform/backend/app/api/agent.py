"""
旧版 Agent API - 已弃用 (DEPRECATED)

此模块不再维护，所有功能已迁移至 LangGraph 实现。
请使用以下替代接口：

- POST /api/multi-agent-lg/process     → LangGraph 非流式
- POST /api/multi-agent-lg/process/stream → LangGraph 流式
- POST /api/multi-agent/process        → LangGraph 后端 (兼容旧格式)

本接口保留仅供向后兼容，将在未来版本中移除。
"""

import uuid
import warnings
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from fastapi import Depends

from app.core.database import get_db, AgentTask

router = APIRouter(prefix="/api/agent", tags=["agent", "deprecated"])

warnings.warn(
    "agent.py 模块已弃用，请迁移至 LangGraph API (/api/multi-agent-lg/)",
    DeprecationWarning,
    stacklevel=2,
)


class DiagnoseRequest(BaseModel):
    user_input: str
    session_id: Optional[str] = None


class DiagnoseResponse(BaseModel):
    task_id: str
    status: str
    message: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    intent_data: Optional[dict] = None
    analysis_report: Optional[dict] = None
    knowledge_context: Optional[dict] = None
    decision: Optional[dict] = None
    action_result: Optional[dict] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


def _deprecation_headers() -> dict:
    return {
        "X-Deprecated": "true",
        "X-Sunset": "2026-09-01",
        "X-Migration-Url": "/api/multi-agent-lg/process",
        "X-Deprecation-Message": "此接口已弃用，请迁移至 LangGraph API",
    }


@router.post("/diagnose", response_model=DiagnoseResponse)
async def diagnose(
    request: DiagnoseRequest,
    req: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    return {"task_id": "deprecated", "status": "deprecated", "message": "此接口已弃用。请使用 POST /api/multi-agent-lg/process 或 POST /api/multi-agent/process"}


@router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str, req: Request, db: Session = Depends(get_db)):
    return {"task_id": task_id, "status": "deprecated"}


@router.get("/history")
async def get_history(
    req: Request,
    limit: int = 10,
    db: Session = Depends(get_db),
):
    return {
        "deprecated": True,
        "message": "此接口已弃用。历史查询功能将在新接口中提供。",
        "tasks": [],
    }
