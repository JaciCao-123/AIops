from ..state import AIOpsState


def route_after_ssh_check(state: AIOpsState) -> str:
    if state.get("need_ssh_login") and not state.get("ssh_confirmed"):
        return "need_confirm"
    return "continue"