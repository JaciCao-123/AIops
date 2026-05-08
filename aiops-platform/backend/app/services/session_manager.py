"""
AI 助手会话管理服务

提供多轮对话的会话管理和上下文存储功能。
"""

from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field
import uuid
import asyncio
from collections import OrderedDict


@dataclass
class ChatMessage:
    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Session:
    session_id: str
    title: str
    messages: List[ChatMessage] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    message_count: int = 0


class SessionManager:
    """
    会话管理器
    
    功能:
    - 创建、获取、删除会话
    - 上下文窗口管理（限制消息数量）
    - 自动生成会话标题
    - LRU 淘汰策略（可选）
    """
    
    def __init__(
        self,
        max_sessions: int = 100,
        max_messages_per_session: int = 20,
        session_timeout_minutes: int = 60
    ):
        self.max_sessions = max_sessions
        self.max_messages_per_session = max_messages_per_session
        self.session_timeout_minutes = session_timeout_minutes
        self._sessions: OrderedDict[str, Session] = OrderedDict()
        self._lock = asyncio.Lock()
    
    async def create_session(self, title: Optional[str] = None) -> Session:
        """创建新会话"""
        async with self._lock:
            session_id = str(uuid.uuid4())[:8]
            session = Session(
                session_id=session_id,
                title=title or f"新对话 {session_id[:4]}"
            )
            
            if len(self._sessions) >= self.max_sessions:
                self._sessions.popitem(last=False)
            
            self._sessions[session_id] = session
            return session
    
    async def get_session(self, session_id: str) -> Optional[Session]:
        """获取会话"""
        async with self._lock:
            session = self._sessions.get(session_id)
            if session:
                self._sessions.move_to_end(session_id)
            return session
    
    async def get_all_sessions(self) -> List[Session]:
        """获取所有会话列表（按更新时间倒序）"""
        async with self._lock:
            sessions = list(self._sessions.values())
            return sorted(sessions, key=lambda s: s.updated_at, reverse=True)
    
    async def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        async with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False
    
    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str
    ) -> Optional[ChatMessage]:
        """向会话添加消息"""
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return None
            
            message = ChatMessage(role=role, content=content)
            session.messages.append(message)
            session.message_count += 1
            session.updated_at = datetime.now()
            
            if len(session.messages) > self.max_messages_per_session:
                removed_count = len(session.messages) - self.max_messages_per_session
                session.messages = session.messages[removed_count:]
            
            if session.message_count == 1 and role == "user":
                session.title = self._generate_title(content)
            
            self._sessions.move_to_end(session_id)
            
            return message
    
    async def get_messages(
        self,
        session_id: str,
        limit: Optional[int] = None
    ) -> List[ChatMessage]:
        """获取会话消息"""
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return []
            
            messages = session.messages
            if limit:
                messages = messages[-limit:]
            
            return messages
    
    async def clear_messages(self, session_id: str) -> bool:
        """清空会话消息"""
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return False
            
            session.messages = []
            session.updated_at = datetime.now()
            return True
    
    async def update_title(self, session_id: str, title: str) -> bool:
        """更新会话标题"""
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return False
            
            session.title = title
            session.updated_at = datetime.now()
            return True
    
    def _generate_title(self, content: str) -> str:
        """根据第一条消息生成会话标题"""
        title = content[:30]
        if len(content) > 30:
            title += "..."
        return title
    
    async def get_context_messages(
        self,
        session_id: str,
        max_tokens: int = 4000
    ) -> List[Dict[str, str]]:
        """
        获取上下文消息（用于 LLM 调用）
        
        Args:
            session_id: 会话 ID
            max_tokens: 最大 token 数（粗略估计，按 1 token ≈ 1.5 字符计算）
        
        Returns:
            适合发送给 LLM 的消息列表
        """
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return []
            
            messages = []
            total_chars = 0
            max_chars = max_tokens * 1.5
            
            for msg in reversed(session.messages):
                msg_chars = len(msg.content)
                if total_chars + msg_chars > max_chars:
                    break
                messages.insert(0, {"role": msg.role, "content": msg.content})
                total_chars += msg_chars
            
            return messages
    
    async def get_stats(self) -> Dict:
        """获取统计信息"""
        async with self._lock:
            total_messages = sum(s.message_count for s in self._sessions.values())
            return {
                "total_sessions": len(self._sessions),
                "total_messages": total_messages,
                "max_sessions": self.max_sessions,
                "max_messages_per_session": self.max_messages_per_session
            }


session_manager = SessionManager(
    max_sessions=100,
    max_messages_per_session=20
)
