from ..state import AIOpsState


async def ssh_check_node(state: AIOpsState) -> dict:
    entities = state.get("entities", {})
    ssh_users = entities.get("ssh_users", [])
    servers = entities.get("servers", [])

    need_ssh = bool(servers) and not ssh_users

    if need_ssh:
        server_values = [s.get("value", "") if isinstance(s, dict) else str(s) for s in servers]
        return {
            "need_ssh_login": True,
            "ssh_confirmed": False,
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        f"需要连接服务器 {server_values}，"
                        f"请提供 SSH 登录用户名"
                    ),
                }
            ],
        }

    return {
        "need_ssh_login": False,
        "ssh_confirmed": True,
        "messages": [
            {"role": "assistant", "content": "SSH 信息完整，继续诊断"}
        ],
    }