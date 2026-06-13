import os
import json
from datetime import datetime
from ..state import AIOpsState
from app.utils.file_manager import IntermediateFileManager
from app.utils.logger import get_logger

logger = get_logger("langgraph.finalize")

_file_manager = IntermediateFileManager(
    base_dir=os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", "data")
)


def _serialize_state(state: AIOpsState) -> dict:
    result = {
        "user_query": state.get("user_query", ""),
        "start_time": datetime.now().isoformat(),
        "intent_data": state.get("intent_data"),
        "intent_type": state.get("intent_type"),
        "entities": state.get("entities"),
        "matched_skills": state.get("matched_skills", []),
        "skills_content": state.get("skills_content", ""),
        "ssh_user": state.get("ssh_user"),
        "need_ssh_login": state.get("need_ssh_login", False),
        "ssh_confirmed": state.get("ssh_confirmed", False),
        "iteration_count": state.get("iteration_count", 0),
        "approval_status": state.get("approval_status"),
        "confirmation_request": state.get("confirmation_request"),
        "diagnosis_result": state.get("diagnosis_result"),
        "execution_history": state.get("execution_history", []),
        "warning_cleared": state.get("warning_cleared", False),
    }
    return result


async def finalize_node(state: AIOpsState) -> dict:
    diagnosis = state.get("diagnosis_result") or {}
    execution_history = state.get("execution_history", [])

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    try:
        full_result = _serialize_state(state)

        for i, entry in enumerate(execution_history):
            if entry.get("tool") == "execute_command":
                result_raw = entry.get("result", {})
                if isinstance(result_raw, dict):
                    output_str = result_raw.get("output", "")
                    if isinstance(output_str, str) and output_str.strip():
                        try:
                            parsed = json.loads(output_str)
                            host = parsed.get("target_host", "local")
                            cmd_output = parsed.get("output", output_str)
                        except (json.JSONDecodeError, TypeError):
                            host = "local"
                            cmd_output = output_str

                        _file_manager.save_execution_output(
                            output=cmd_output,
                            target_host=host,
                            query_id=f"{timestamp}_{i}"
                        )

        full_result_path = _file_manager.save_full_result(full_result, query_id=timestamp)
        logger.info(f"Full result saved to: {full_result_path}")

    except Exception as e:
        logger.error(f"Failed to save intermediate files: {e}")
        full_result_path = None

    summary_parts = []
    if diagnosis.get("root_cause"):
        summary_parts.append(f"根因: {diagnosis['root_cause']}")
    if diagnosis.get("recommendation"):
        summary_parts.append(f"建议: {diagnosis['recommendation']}")

    summary = " | ".join(summary_parts) if summary_parts else "诊断流程已完成"
    if full_result_path:
        summary += f"\n[中间文件] 完整结果: {full_result_path}"

    return {
        "messages": [
            {
                "role": "assistant",
                "content": f"【诊断完成】{summary}",
            }
        ],
        "full_result_path": full_result_path,
    }
