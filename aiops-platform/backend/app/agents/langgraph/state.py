from typing import TypedDict, Annotated, List, Dict, Any, Optional
from langgraph.graph.message import add_messages


class AIOpsState(TypedDict):
    messages: Annotated[list, add_messages]
    user_query: str
    intent_data: Optional[Dict[str, Any]]
    entities: Optional[Dict[str, Any]]
    intent_type: Optional[str]
    need_ssh_login: bool
    ssh_confirmed: bool
    ssh_user: Optional[str]
    matched_skills: List[str]
    skills_content: str
    knowledge_context: Optional[Dict[str, Any]]
    observability_report: Optional[Dict[str, Any]]
    execution_history: List[Dict[str, Any]]
    diagnosis_result: Optional[Dict[str, Any]]
    confirmation_request: Optional[Dict[str, Any]]
    approval_status: Optional[str]
    iteration_count: int
    error: Optional[str]
    warning_cleared: bool