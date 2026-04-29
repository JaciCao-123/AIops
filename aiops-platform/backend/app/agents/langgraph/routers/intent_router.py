from ..state import AIOpsState


def route_after_intent(state: AIOpsState) -> str:
    intent_type = state.get("intent_type", "GENERAL_QA")

    if intent_type == "DIAGNOSE":
        return "diagnose"
    elif intent_type == "QUERY_STATUS":
        return "query"
    else:
        return "qa"