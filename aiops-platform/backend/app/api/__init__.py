from fastapi import APIRouter
from app.api import agent, logs, knowledge, multi_agent

api_router = APIRouter()

api_router.include_router(agent.router)
api_router.include_router(logs.router)
api_router.include_router(knowledge.router)
api_router.include_router(multi_agent.router)
