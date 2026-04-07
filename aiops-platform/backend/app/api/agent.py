import uuid
import asyncio
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
from fastapi import Depends

from app.core.database import get_db, AgentTask
from app.agents import (
    IntentParseAgent,
    ObservabilityAnalystAgent,
    KnowledgeExpertAgent,
    MasterAgent,
    ActionExecuteAgent
)

router = APIRouter(prefix="/api/agent", tags=["agent"])

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

intent_agent = IntentParseAgent()
observability_agent = ObservabilityAnalystAgent()
knowledge_agent = KnowledgeExpertAgent()
master_agent = MasterAgent()
action_agent = ActionExecuteAgent()

async def run_diagnosis_pipeline(task_id: str, user_input: str, db: Session):
    try:
        task = db.query(AgentTask).filter(AgentTask.task_id == task_id).first()
        if not task:
            return
        
        task.status = "processing"
        db.commit()
        
        intent_data = await intent_agent.parse(user_input)
        task.intent_data = str(intent_data)
        db.commit()
        
        service = intent_data.get("entities", {}).get("service", "unknown")
        symptom = intent_data.get("entities", {}).get("symptom", "unknown")
        
        analysis_report = await observability_agent.analyze(service)
        task.analysis_report = str(analysis_report)
        db.commit()
        
        knowledge_context = await knowledge_agent.query(service, symptom)
        task.knowledge_context = str(knowledge_context)
        db.commit()
        
        decision = await master_agent.decide(intent_data, analysis_report, knowledge_context)
        task.decision = str(decision)
        db.commit()
        
        if decision.get("decision") == "EXECUTE_FIX":
            target_entities = intent_data.get("entities", {})
            action_result = await action_agent.execute(
                decision.get("action_plan", ""),
                target_entities
            )
            task.action_result = str(action_result)
        
        task.status = "completed"
        task.updated_at = datetime.utcnow()
        db.commit()
        
    except Exception as e:
        task = db.query(AgentTask).filter(AgentTask.task_id == task_id).first()
        if task:
            task.status = "failed"
            task.decision = str({"error": str(e)})
            db.commit()

@router.post("/diagnose", response_model=DiagnoseResponse)
async def diagnose(request: DiagnoseRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    task_id = str(uuid.uuid4())
    
    task = AgentTask(
        task_id=task_id,
        user_input=request.user_input,
        status="pending"
    )
    db.add(task)
    db.commit()
    
    background_tasks.add_task(run_diagnosis_pipeline, task_id, request.user_input, db)
    
    return DiagnoseResponse(
        task_id=task_id,
        status="pending",
        message="诊断任务已创建，请通过 /api/agent/status/{task_id} 查询进度"
    )

@router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str, db: Session = Depends(get_db)):
    task = db.query(AgentTask).filter(AgentTask.task_id == task_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    def safe_parse(data_str):
        if not data_str:
            return None
        try:
            import json
            return json.loads(data_str.replace("'", '"'))
        except:
            return {"raw": data_str}
    
    return TaskStatusResponse(
        task_id=task.task_id,
        status=task.status,
        intent_data=safe_parse(task.intent_data),
        analysis_report=safe_parse(task.analysis_report),
        knowledge_context=safe_parse(task.knowledge_context),
        decision=safe_parse(task.decision),
        action_result=safe_parse(task.action_result),
        created_at=task.created_at,
        updated_at=task.updated_at
    )

@router.get("/history")
async def get_history(limit: int = 10, db: Session = Depends(get_db)):
    tasks = db.query(AgentTask).order_by(AgentTask.created_at.desc()).limit(limit).all()
    return {
        "tasks": [
            {
                "task_id": t.task_id,
                "user_input": t.user_input,
                "status": t.status,
                "created_at": t.created_at
            }
            for t in tasks
        ]
    }
