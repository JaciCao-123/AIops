from ..state import AIOpsState
from app.agents.knowledge import KnowledgeExpertAgent

_knowledge_agent = KnowledgeExpertAgent()


async def knowledge_qa_node(state: AIOpsState) -> dict:
    entities = state.get("entities", {})
    services = entities.get("services", [])
    service = (
        services[0].get("normalized", "unknown") if services else "unknown"
    )
    symptoms = entities.get("symptoms", [])
    symptom_str = ", ".join(
        [s.get("value", "") if isinstance(s, dict) else s for s in symptoms]
    )

    knowledge_result = await _knowledge_agent.query(
        service=service, symptom=symptom_str
    )

    knowledge_dict = (
        knowledge_result.model_dump()
        if hasattr(knowledge_result, "model_dump")
        else knowledge_result
    )

    return {
        "knowledge_context": knowledge_dict,
        "diagnosis_result": {
            "decision": "KNOWLEDGE_QA",
            "knowledge_report": knowledge_result.knowledge_report,
            "topology_info": (
                knowledge_result.topology_info.model_dump()
                if hasattr(knowledge_result.topology_info, "model_dump")
                else knowledge_result.topology_info
            ),
        },
        "messages": [
            {
                "role": "assistant",
                "content": knowledge_result.knowledge_report[:500],
            }
        ],
    }
