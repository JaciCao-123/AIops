from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from openai import AsyncOpenAI

from app.core.config import settings

router = APIRouter(prefix="/api/ai-chat", tags=["ai-chat"])

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]

class ChatResponse(BaseModel):
    response: str

SYSTEM_PROMPT = """你是一个专业的 AIOps 智能运维助手。你的职责是：

1. 帮助用户排查和诊断系统故障
2. 解答运维相关的问题，包括但不限于：
   - 服务器性能问题排查（CPU、内存、磁盘、网络）
   - 数据库问题诊断（MySQL、PostgreSQL、Redis 等）
   - 容器和 Kubernetes 相关问题
   - 微服务架构和分布式系统问题
   - 日志分析和监控告警
   - 自动化运维脚本编写

3. 提供最佳实践建议和解决方案

请用专业但易懂的语言回答用户的问题。如果需要更多上下文信息，请主动询问。
回答时请尽量结构化，使用要点列表等方式让内容更清晰。"""

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

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
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
        
        return ChatResponse(response=response.choices[0].message.content)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"对话失败: {str(e)}"
        )

@router.delete("/history")
async def clear_history():
    return {"message": "对话历史已清空"}

@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "ai-chat",
        "model": settings.OPENAI_MODEL,
        "configured": bool(settings.OPENAI_API_KEY)
    }
