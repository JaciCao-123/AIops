from ..state import AIOpsState


def route_after_intent(state: AIOpsState) -> str:
    intent_type = state.get("intent_type", "GENERAL_QA")

    # DIAGNOSE / EXECUTE_FIX / QUERY_STATUS 都需要经过完整的诊断流程
    # QUERY_STATUS 也走 diagnose 路径以触发 SSH 登录和 skill 匹配
    if intent_type in ("DIAGNOSE", "EXECUTE_FIX", "QUERY_STATUS"):
        return "diagnose"
    elif intent_type == "QUERY_STATUS_LEGACY":
        return "query"
    else:
        return "qa"