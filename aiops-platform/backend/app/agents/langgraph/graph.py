from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .state import AIOpsState
from .nodes import (
    intent_parse_node,
    ssh_check_node,
    skill_match_node,
    react_agent_node,
    knowledge_qa_node,
    approval_node,
    human_review_node,
    finalize_node,
)
from .routers import (
    route_after_intent,
    route_after_ssh_check,
    route_after_react,
)


def _route_approval(state: AIOpsState) -> str:
    if state.get("approval_status") == "approved":
        return "approved"
    return "rejected"


def build_aiops_graph():
    graph = StateGraph(AIOpsState)

    graph.add_node("intent_parse", intent_parse_node)
    graph.add_node("ssh_check", ssh_check_node)
    graph.add_node("skill_match", skill_match_node)
    graph.add_node("react_agent", react_agent_node)
    graph.add_node("knowledge_qa", knowledge_qa_node)
    graph.add_node("approval", approval_node)
    graph.add_node("human_review", human_review_node)
    graph.add_node("finalize", finalize_node)

    graph.set_entry_point("intent_parse")

    graph.add_conditional_edges(
        "intent_parse",
        route_after_intent,
        {
            "diagnose": "ssh_check",
            "query": "knowledge_qa",
            "qa": "knowledge_qa",
        },
    )

    graph.add_conditional_edges(
        "ssh_check",
        route_after_ssh_check,
        {
            "need_confirm": "human_review",
            "continue": "skill_match",
        },
    )

    graph.add_edge("human_review", "skill_match")
    graph.add_edge("skill_match", "react_agent")

    graph.add_conditional_edges(
        "react_agent",
        route_after_react,
        {
            "completed": "finalize",
            "needs_confirmation": "approval",
            "continue": "react_agent",
        },
    )

    graph.add_conditional_edges(
        "approval",
        _route_approval,
        {
            "approved": "react_agent",
            "rejected": "finalize",
        },
    )

    graph.add_edge("knowledge_qa", "finalize")
    graph.add_edge("finalize", END)

    memory = MemorySaver()

    return graph.compile(
        checkpointer=memory,
        interrupt_before=["human_review", "approval"],
    )