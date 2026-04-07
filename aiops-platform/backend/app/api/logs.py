import json
import asyncio
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.orm import Session
from fastapi import Depends

from app.core.database import get_db, Log, Feedback
from algorithm.anomaly_detector import AnomalyDetector

router = APIRouter(prefix="/api/logs", tags=["logs"])

detector = AnomalyDetector()

class LogCreate(BaseModel):
    level: str
    content: str
    source: str = "api"

class LogResponse(BaseModel):
    id: int
    timestamp: datetime
    level: str
    content: str
    source: str
    is_anomaly: bool
    anomaly_score: Optional[float]
    user_feedback: Optional[bool]

class FeedbackRequest(BaseModel):
    feedback_type: bool

class StatsResponse(BaseModel):
    total_logs: int
    anomaly_count: int
    anomaly_rate: float
    level_distribution: dict
    top_patterns: List[dict]

@router.post("/upload")
async def upload_log_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith(('.log', '.txt')):
        raise HTTPException(status_code=400, detail="只支持 .log 和 .txt 文件")
    
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件大小不能超过 10MB")
    
    lines = content.decode('utf-8', errors='ignore').split('\n')
    logs_created = 0
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        level = "INFO"
        if "ERROR" in line or "error" in line:
            level = "ERROR"
        elif "WARN" in line or "warn" in line:
            level = "WARN"
        elif "DEBUG" in line:
            level = "DEBUG"
        
        is_anomaly, score = detector.detect(line)
        
        log = Log(
            level=level,
            content=line[:1000],
            source="file",
            is_anomaly=is_anomaly,
            anomaly_score=score
        )
        db.add(log)
        logs_created += 1
    
    db.commit()
    
    return {
        "message": f"成功上传 {logs_created} 条日志",
        "filename": file.filename
    }

@router.post("/ingest", response_model=LogResponse)
async def ingest_log(log_data: LogCreate, db: Session = Depends(get_db)):
    is_anomaly, score = detector.detect(log_data.content)
    
    log = Log(
        level=log_data.level,
        content=log_data.content,
        source=log_data.source,
        is_anomaly=is_anomaly,
        anomaly_score=score
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    
    return LogResponse(
        id=log.id,
        timestamp=log.timestamp,
        level=log.level,
        content=log.content,
        source=log.source,
        is_anomaly=log.is_anomaly,
        anomaly_score=log.anomaly_score,
        user_feedback=log.user_feedback
    )

@router.get("", response_model=List[LogResponse])
async def get_logs(
    level: Optional[str] = None,
    is_anomaly: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    query = db.query(Log)
    
    if level:
        query = query.filter(Log.level == level)
    if is_anomaly is not None:
        query = query.filter(Log.is_anomaly == is_anomaly)
    
    logs = query.order_by(Log.timestamp.desc()).offset(offset).limit(limit).all()
    
    return [
        LogResponse(
            id=log.id,
            timestamp=log.timestamp,
            level=log.level,
            content=log.content,
            source=log.source,
            is_anomaly=log.is_anomaly,
            anomaly_score=log.anomaly_score,
            user_feedback=log.user_feedback
        )
        for log in logs
    ]

@router.post("/{log_id}/feedback")
async def submit_feedback(log_id: int, feedback: FeedbackRequest, db: Session = Depends(get_db)):
    log = db.query(Log).filter(Log.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="日志不存在")
    
    log.user_feedback = feedback.feedback_type
    
    feedback_record = Feedback(
        log_id=log_id,
        feedback_type=feedback.feedback_type
    )
    db.add(feedback_record)
    db.commit()
    
    return {"message": "反馈已记录", "log_id": log_id}

@router.get("/stats", response_model=StatsResponse)
async def get_stats(db: Session = Depends(get_db)):
    total = db.query(Log).count()
    anomaly_count = db.query(Log).filter(Log.is_anomaly == True).count()
    
    level_counts = {}
    for level in ["ERROR", "WARN", "INFO", "DEBUG"]:
        count = db.query(Log).filter(Log.level == level).count()
        level_counts[level] = count
    
    anomaly_logs = db.query(Log).filter(Log.is_anomaly == True).limit(5).all()
    top_patterns = [
        {"content": log.content[:50], "score": log.anomaly_score}
        for log in anomaly_logs
    ]
    
    return StatsResponse(
        total_logs=total,
        anomaly_count=anomaly_count,
        anomaly_rate=anomaly_count / total if total > 0 else 0,
        level_distribution=level_counts,
        top_patterns=top_patterns
    )

active_connections = []

@router.websocket("/ws/simulate")
async def websocket_simulate_logs(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    
    try:
        while True:
            data = await websocket.receive_text()
            
            if data == "start":
                import random
                levels = ["INFO", "WARN", "ERROR", "DEBUG"]
                templates = [
                    "Request processed in {time}ms",
                    "Connection established to {service}",
                    "Cache hit ratio: {ratio}%",
                    "Database query executed: {query}",
                    "ERROR: Connection timeout to {service}",
                    "WARN: High memory usage: {mem}%",
                    "ERROR: Failed to process request: {error}"
                ]
                
                while True:
                    try:
                        level = random.choice(levels)
                        template = random.choice(templates)
                        content = template.format(
                            time=random.randint(10, 500),
                            service=random.choice(["redis", "mysql", "kafka"]),
                            ratio=random.randint(70, 99),
                            query=f"SELECT * FROM table_{random.randint(1,10)}",
                            mem=random.randint(60, 95),
                            error=random.choice(["timeout", "connection refused", "OOM"])
                        )
                        
                        is_anomaly, score = detector.detect(content)
                        
                        log_entry = {
                            "timestamp": datetime.utcnow().isoformat(),
                            "level": level,
                            "content": content,
                            "is_anomaly": is_anomaly,
                            "anomaly_score": score
                        }
                        
                        await websocket.send_json(log_entry)
                        await asyncio.sleep(1)
                        
                    except Exception:
                        break
            
            elif data == "stop":
                break
                
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in active_connections:
            active_connections.remove(websocket)
