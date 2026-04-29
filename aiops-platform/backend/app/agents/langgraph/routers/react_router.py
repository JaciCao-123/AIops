from ..state import AIOpsState


def route_after_react(state: AIOpsState) -> str:
    if state.get("diagnosis_result"):
        return "completed"
    if state.get("confirmation_request") and not state.get("approval_status"):
        return "needs_confirmation"
    if state.get("iteration_count", 0) >= 40:
        return "completed"
    return "continue"