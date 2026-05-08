"""
AI 助手 API

提供多轮对话和会话管理功能。
"""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from openai import AsyncOpenAI
import json
import asyncio

from app.core.config import settings
from app.services.session_manager import session_manager, Session, ChatMessage
from app.utils.rate_limiter import chat_rate_limiter

router = APIRouter(prefix="/api/ai-chat", tags=["ai-chat"])


# ==================== 请求/响应模型 ====================

class ChatMessageModel(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str


class ChatResponse(BaseModel):
    session_id: str
    response: str
    message_count: int


class SessionCreateRequest(BaseModel):
    title: Optional[str] = None


class SessionUpdateRequest(BaseModel):
    title: str


class SessionResponse(BaseModel):
    session_id: str
    title: str
    message_count: int
    created_at: datetime
    updated_at: datetime


class SessionDetailResponse(BaseModel):
    session_id: str
    title: str
    messages: List[ChatMessageModel]
    message_count: int
    created_at: datetime
    updated_at: datetime


class StatsResponse(BaseModel):
    total_sessions: int
    total_messages: int
    max_sessions: int
    max_messages_per_session: int


# ==================== 系统提示词 ====================

SYSTEM_PROMPT = """你是一个专业的 AIOps 智能运维助手。

## 核心原则

### 1. 诚实原则
- 如果你不确定某个操作的效果或安全性，**直接承认，不要猜测**。
- 不要编造不存在的命令、参数或配置文件路径。
- 如果问题超出你的知识范围，明确告知用户并建议寻求人工专家支持。
- 不要为了给出答案而虚构信息——"我不知道"比"错误建议"安全得多。

### 2. 风险标注原则
对任何可能影响生产服务的建议，**必须标注风险等级**：
- **[低风险]**：只读操作（查看日志、查询状态），不会影响服务运行
- **[中风险]**：可能短暂影响服务性能的操作（重启单个非核心服务、清理临时文件）
- **[高风险]**：可能导致服务中断的操作（重启核心服务、修改配置、数据库操作）

### 3. 命令验证原则
- 提供的任何运维命令，**必须是经过验证的真实命令**。
- 推荐在测试环境先验证再应用于生产。
- 对于危险命令（rm、kill、reboot、systemctl stop 等），必须明确警告。

### 4. 回滚方案原则
- 对于变更类建议，**必须同时提供回滚方案**。
- 说明如何撤销操作、恢复到变更前的状态。

### 5. 来源引用原则
- 如果建议基于特定文档或最佳实践，请注明来源。
- 经验性建议标注为"常见做法"，不要冒充权威结论。

---

## 职责范围

1. 帮助用户排查和诊断系统故障
2. 解答运维相关问题，包括但不限于：
   - 服务器性能问题排查（CPU、内存、磁盘、网络）
   - 数据库问题诊断（MySQL、PostgreSQL、Redis 等）
   - 容器和 Kubernetes 相关问题
   - 微服务架构和分布式系统问题
   - 日志分析和监控告警
   - 自动化运维脚本编写
3. 提供最佳实践建议和解决方案

---

## 回答规范

- 请用专业但易懂的语言回答用户的问题
- 回答时尽量结构化，使用要点列表等方式让内容更清晰
- 涉及操作步骤时，明确标注风险等级
- 涉及命令时，添加注释说明每个参数的作用
- 提供变更建议时，附带回滚方案
- 如果需要更多上下文信息，请主动询问

注意：你正在与用户进行多轮对话，请记住之前的对话内容，保持上下文连贯。"""


# ==================== OpenAI 客户端 ====================

async def get_openai_client():
    if not settings.OPENAI_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="OpenAI API Key 未配置，请在 .env 中设置 OPENAI_API_KEY"
        )
    
    return AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL if settings.OPENAI_BASE_URL else None,
    )


# ==================== 会话管理接口 ====================

@router.post("/sessions", response_model=SessionResponse)
async def create_session(request: SessionCreateRequest = None):
    """创建新会话"""
    title = request.title if request else None
    session = await session_manager.create_session(title)
    return SessionResponse(
        session_id=session.session_id,
        title=session.title,
        message_count=session.message_count,
        created_at=session.created_at,
        updated_at=session.updated_at
    )


@router.get("/sessions", response_model=List[SessionResponse])
async def list_sessions():
    """获取所有会话列表"""
    sessions = await session_manager.get_all_sessions()
    return [
        SessionResponse(
            session_id=s.session_id,
            title=s.title,
            message_count=s.message_count,
            created_at=s.created_at,
            updated_at=s.updated_at
        )
        for s in sessions
    ]


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session(session_id: str):
    """获取会话详情"""
    session = await session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    return SessionDetailResponse(
        session_id=session.session_id,
        title=session.title,
        messages=[
            ChatMessageModel(role=m.role, content=m.content)
            for m in session.messages
        ],
        message_count=session.message_count,
        created_at=session.created_at,
        updated_at=session.updated_at
    )


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除会话"""
    success = await session_manager.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"message": "会话已删除", "session_id": session_id}


@router.put("/sessions/{session_id}/title")
async def update_session_title(session_id: str, request: SessionUpdateRequest):
    """更新会话标题"""
    success = await session_manager.update_title(session_id, request.title)
    if not success:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"message": "标题已更新", "session_id": session_id}


@router.delete("/sessions/{session_id}/messages")
async def clear_session_messages(session_id: str):
    """清空会话消息"""
    success = await session_manager.clear_messages(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"message": "消息已清空", "session_id": session_id}


# ==================== 对话接口 ====================

@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    req: Request,
    _rate_limit: None = Depends(chat_rate_limiter),
):
    """
    发送消息并获取 AI 回复
    
    - 如果 session_id 为空，将自动创建新会话
    - 支持多轮对话，自动管理上下文
    """
    try:
        if request.session_id:
            session = await session_manager.get_session(request.session_id)
            if not session:
                raise HTTPException(status_code=404, detail="会话不存在")
            session_id = request.session_id
        else:
            session = await session_manager.create_session()
            session_id = session.session_id
        
        await session_manager.add_message(session_id, "user", request.message)
        
        context_messages = await session_manager.get_context_messages(
            session_id, max_tokens=4000
        )
        
        client = await get_openai_client()
        
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(context_messages)
        
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=4000,
        )
        
        assistant_content = response.choices[0].message.content
        
        await session_manager.add_message(session_id, "assistant", assistant_content)
        
        session = await session_manager.get_session(session_id)
        
        return ChatResponse(
            session_id=session_id,
            response=assistant_content,
            message_count=session.message_count if session else 0
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"对话失败: {str(e)}"
        )


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    req: Request,
    _rate_limit: None = Depends(chat_rate_limiter),
):
    """
    流式对话接口 (SSE)
    
    - 如果 session_id 为空，将自动创建新会话
    - 支持多轮对话，自动管理上下文
    - 使用 Server-Sent Events 流式返回响应
    """
    async def generate():
        try:
            if request.session_id:
                session = await session_manager.get_session(request.session_id)
                if not session:
                    yield f"data: {json.dumps({'error': '会话不存在'})}\n\n"
                    return
                session_id = request.session_id
            else:
                session = await session_manager.create_session()
                session_id = session.session_id
            
            yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"
            
            await session_manager.add_message(session_id, "user", request.message)
            
            context_messages = await session_manager.get_context_messages(
                session_id, max_tokens=4000
            )
            
            client = await get_openai_client()
            
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            messages.extend(context_messages)
            
            response = await client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=messages,
                temperature=0.7,
                max_tokens=4000,
                stream=True
            )
            
            full_content = ""
            async for chunk in response:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_content += content
                    yield f"data: {json.dumps({'type': 'content', 'content': content})}\n\n"
            
            await session_manager.add_message(session_id, "assistant", full_content)
            
            session = await session_manager.get_session(session_id)
            
            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id, 'message_count': session.message_count if session else 0})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# ==================== 兼容旧接口 ====================

class LegacyChatRequest(BaseModel):
    messages: List[ChatMessageModel]


class LegacyChatResponse(BaseModel):
    response: str


@router.post("/chat/legacy", response_model=LegacyChatResponse)
async def legacy_chat(
    request: LegacyChatRequest,
    req: Request,
    _rate_limit: None = Depends(chat_rate_limiter),
):
    """
    兼容旧版对话接口（无会话管理）
    
    保留此接口以兼容旧版前端
    """
    try:
        client = await get_openai_client()
        
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for msg in request.messages:
            messages.append({"role": msg.role, "content": msg.content})
        
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=2000,
        )
        
        return LegacyChatResponse(response=response.choices[0].message.content)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"对话失败: {str(e)}"
        )


# ==================== 其他接口 ====================

@router.delete("/history")
async def clear_history():
    """清空所有会话历史（兼容旧接口）"""
    sessions = await session_manager.get_all_sessions()
    for session in sessions:
        await session_manager.delete_session(session.session_id)
    return {"message": "所有对话历史已清空"}


@router.get("/stats", response_model=StatsResponse)
async def get_stats():
    """获取会话统计信息"""
    return await session_manager.get_stats()


@router.get("/health")
async def health_check():
    """健康检查"""
    stats = await session_manager.get_stats()
    return {
        "status": "healthy",
        "service": "ai-chat",
        "model": settings.OPENAI_MODEL,
        "configured": bool(settings.OPENAI_API_KEY),
        "stats": stats
    }
