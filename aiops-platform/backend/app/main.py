from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import init_db
from app.api import api_router
from app.api.terminal import websocket_terminal
from app.api.auth import router as auth_router, create_default_users
from app.api.approval import router as approval_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    create_default_users()
    yield

app = FastAPI(
    title=settings.APP_NAME,
    description="AIOps智能运维平台 - Multi-Agent故障诊断系统",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(auth_router)
app.include_router(approval_router)

app.add_api_websocket_route("/ws/terminal", websocket_terminal)

@app.get("/")
async def root():
    return {
        "message": "AIOps Platform API",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
