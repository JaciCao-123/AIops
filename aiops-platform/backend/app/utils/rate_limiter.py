"""
Rate Limiter - 基于滑动窗口的请求频率限制

无需额外依赖，纯 Python 标准库实现。
支持通过 Settings 配置限流参数。
"""

import time
import asyncio
from collections import defaultdict
from typing import Dict, Tuple, Optional
from dataclasses import dataclass, field

from fastapi import Request, HTTPException

from .logger import get_logger

logger = get_logger("rate_limiter")

try:
    from ..core.config import settings
    SETTINGS_AVAILABLE = True
except ImportError:
    SETTINGS_AVAILABLE = False


@dataclass
class WindowEntry:
    timestamps: list = field(default_factory=list)
    blocked_until: float = 0.0


class RateLimiter:
    """
    滑动窗口频率限制器

    支持：
    - 按 key 限流
    - 滑动窗口计数
    - 超限后的封禁期 (block duration)
    """

    def __init__(
        self,
        max_requests: int = 30,
        window_seconds: int = 60,
        block_seconds: int = 300,
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.block_seconds = block_seconds
        self._windows: Dict[str, WindowEntry] = defaultdict(WindowEntry)
        self._lock = asyncio.Lock()

    async def check(self, key: str) -> Tuple[bool, Optional[int]]:
        """
        检查请求是否被允许

        Args:
            key: 限流键（通常是 IP 地址）

        Returns:
            (allowed, retry_after_seconds)
            - allowed=True: 请求放行
            - allowed=False: 被限流，retry_after_seconds 为建议重试秒数
        """
        async with self._lock:
            entry = self._windows[key]
            now = time.time()

            if entry.blocked_until > now:
                retry_after = int(entry.blocked_until - now)
                return False, retry_after

            expiry = now - self.window_seconds
            while entry.timestamps and entry.timestamps[0] <= expiry:
                entry.timestamps.pop(0)

            if len(entry.timestamps) >= self.max_requests:
                entry.blocked_until = now + self.block_seconds
                retry_after = self.block_seconds
                logger.warning(
                    f"Rate limit triggered for key={key}, "
                    f"{len(entry.timestamps)} requests in {self.window_seconds}s, "
                    f"blocked for {self.block_seconds}s"
                )
                return False, retry_after

            entry.timestamps.append(now)
            return True, None

    async def get_remaining(self, key: str) -> int:
        """获取剩余可用请求数"""
        async with self._lock:
            entry = self._windows[key]
            now = time.time()
            expiry = now - self.window_seconds
            while entry.timestamps and entry.timestamps[0] <= expiry:
                entry.timestamps.pop(0)
            return max(0, self.max_requests - len(entry.timestamps))


class ChatRateLimiter:
    """
    AI 对话接口专用的频率限制器

    策略：
    - 滑动窗口：30 请求 / 60 秒（可通过 Settings 配置）
    - 超限封禁：300 秒 / 5 分钟（可通过 Settings 配置）
    - 区分 /chat、/chat/stream、/chat/legacy 端点
    - 启用状态可通过 RATE_LIMIT_CHAT_ENABLED 控制
    """

    _instance: Optional["ChatRateLimiter"] = None
    _lock = asyncio.Lock()

    def __init__(
        self,
        chat_max: int = 30,
        chat_window: int = 60,
        chat_block: int = 300,
    ):
        self.limiter = RateLimiter(
            max_requests=chat_max,
            window_seconds=chat_window,
            block_seconds=chat_block,
        )

    @classmethod
    async def get_instance(cls) -> "ChatRateLimiter":
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    if SETTINGS_AVAILABLE:
                        cls._instance = cls(
                            chat_max=settings.RATE_LIMIT_CHAT_MAX_REQUESTS,
                            chat_window=settings.RATE_LIMIT_CHAT_WINDOW_SECONDS,
                            chat_block=settings.RATE_LIMIT_CHAT_BLOCK_SECONDS,
                        )
                    else:
                        cls._instance = cls()
        return cls._instance

    def _is_enabled(self) -> bool:
        if SETTINGS_AVAILABLE:
            return settings.RATE_LIMIT_CHAT_ENABLED
        return True

    def _get_client_key(self, request: Request) -> str:
        """从请求中提取客户端标识"""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"
        return f"ai-chat:{client_ip}"

    async def __call__(self, request: Request):
        """
        作为 FastAPI 依赖使用
        """
        if not self._is_enabled():
            return

        key = self._get_client_key(request)
        allowed, retry_after = await self.limiter.check(key)

        if not allowed:
            remaining = await self.limiter.get_remaining(key)
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "请求过于频繁，请稍后再试",
                    "retry_after_seconds": retry_after,
                    "remaining": remaining,
                    "limit": self.limiter.max_requests,
                    "window_seconds": self.limiter.window_seconds,
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(self.limiter.max_requests),
                    "X-RateLimit-Remaining": str(remaining),
                    "X-RateLimit-Reset": str(int(time.time() + (retry_after or 0))),
                },
            )


chat_rate_limiter = ChatRateLimiter()
