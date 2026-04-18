import os
import sys
import json
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent))

from base.logger import get_logger

app = FastAPI(
    title="Time Sequence Prediction API",
    description="安全审计与时序预测服务",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = get_logger("API")

AUDIT_STATUS = {
    "running": False,
    "last_run": None,
    "incidents": [],
    "error": None
}

class AuditResponse(BaseModel):
    status: str
    message: str
    incidents_count: int = 0
    last_run: Optional[str] = None

class Incident(BaseModel):
    incident_type: str
    severity: str
    start_time: str
    end_time: str
    summary: str
    recommendations: List[str]
    correlated_events: List[Dict[str, Any]]

class HealthResponse(BaseModel):
    status: str
    service: str
    timestamp: str

@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="healthy",
        service="time-sequence-prediction-api",
        timestamp=datetime.now().isoformat()
    )

@app.get("/", response_model=HealthResponse)
async def root():
    return await health_check()

def run_security_audit_task():
    global AUDIT_STATUS
    
    try:
        AUDIT_STATUS["running"] = True
        AUDIT_STATUS["error"] = None
        
        from run_security_audit import SecurityAuditRunner
        runner = SecurityAuditRunner()
        success = runner.run()
        
        incidents_file = Path(__file__).parent / "correlation_engine" / "incidents.json"
        incidents = []
        if incidents_file.exists():
            with open(incidents_file, 'r', encoding='utf-8') as f:
                incidents = json.load(f)
        
        AUDIT_STATUS["running"] = False
        AUDIT_STATUS["last_run"] = datetime.now().isoformat()
        AUDIT_STATUS["incidents"] = incidents
        
        if not success:
            AUDIT_STATUS["error"] = "审计流程执行完成但存在失败步骤"
            
    except Exception as e:
        AUDIT_STATUS["running"] = False
        AUDIT_STATUS["error"] = str(e)
        logger.exception(f"安全审计执行失败: {e}")

@app.post("/api/audit/run", response_model=AuditResponse)
async def run_audit(background_tasks: BackgroundTasks):
    if AUDIT_STATUS["running"]:
        return AuditResponse(
            status="already_running",
            message="安全审计正在运行中，请稍后查询结果",
            last_run=AUDIT_STATUS["last_run"]
        )
    
    background_tasks.add_task(run_security_audit_task)
    
    return AuditResponse(
        status="started",
        message="安全审计已启动，请稍后查询结果",
        last_run=AUDIT_STATUS["last_run"]
    )

@app.get("/api/audit/status", response_model=AuditResponse)
async def get_audit_status():
    incidents_count = len(AUDIT_STATUS.get("incidents", []))
    
    status = "idle"
    if AUDIT_STATUS["running"]:
        status = "running"
    elif AUDIT_STATUS["error"]:
        status = "error"
    elif AUDIT_STATUS["last_run"]:
        status = "completed"
    
    return AuditResponse(
        status=status,
        message=AUDIT_STATUS["error"] or "安全审计状态",
        incidents_count=incidents_count,
        last_run=AUDIT_STATUS["last_run"]
    )

@app.get("/api/audit/incidents", response_model=List[Incident])
async def get_incidents():
    if AUDIT_STATUS["running"]:
        raise HTTPException(status_code=409, detail="审计正在运行中，请稍后查询")
    
    return AUDIT_STATUS.get("incidents", [])

@app.get("/api/audit/incidents/{incident_id}")
async def get_incident(incident_id: int):
    incidents = AUDIT_STATUS.get("incidents", [])
    
    if incident_id < 0 or incident_id >= len(incidents):
        raise HTTPException(status_code=404, detail="事件不存在")
    
    return incidents[incident_id]

@app.get("/api/events")
async def list_events():
    events_dir = Path(__file__).parent / "correlation_engine" / "events"
    
    if not events_dir.exists():
        return {"events": [], "count": 0}
    
    events = []
    for event_file in sorted(events_dir.glob("*.json")):
        try:
            with open(event_file, 'r', encoding='utf-8') as f:
                event = json.load(f)
                event["filename"] = event_file.name
                events.append(event)
        except Exception as e:
            logger.error(f"读取事件文件失败 {event_file}: {e}")
    
    return {"events": events, "count": len(events)}

@app.get("/api/models")
async def list_models():
    models_dir = Path(__file__).parent / "base" / "models"
    
    if not models_dir.exists():
        return {"models": [], "count": 0}
    
    models = []
    for model_file in sorted(models_dir.glob("*.pkl")):
        stat = model_file.stat()
        models.append({
            "name": model_file.name,
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
        })
    
    return {"models": models, "count": len(models)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
