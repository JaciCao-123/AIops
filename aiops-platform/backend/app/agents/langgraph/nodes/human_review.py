from ..state import AIOpsState


async def human_review_node(state: AIOpsState) -> dict:
    entities = state.get("entities", {})
    servers = entities.get("servers", [])
    server_ip = servers[0].get("value", "") if servers else ""

    return {
        "confirmation_request": {
            "operation": "确认 SSH 登录信息",
            "risk": "低风险（仅信息收集）",
            "impact": f"需要获取 SSH 用户名才能连接服务器 {server_ip}",
            "message": f"需要连接服务器 {server_ip} 进行诊断，请提供 SSH 登录用户名",
        },
    }