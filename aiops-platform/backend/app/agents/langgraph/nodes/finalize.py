from datetime import datetime
from ..state import AIOpsState


async def finalize_node(state: AIOpsState) -> dict:
    diagnosis = state.get("diagnosis_result") or {}
    decision = diagnosis.get("decision", "UNKNOWN")

    summary_parts = []
    if diagnosis.get("root_cause"):
        summary_parts.append(f"根因: {diagnosis['root_cause']}")
    if diagnosis.get("recommendation"):
        summary_parts.append(f"建议: {diagnosis['recommendation']}")

    summary = " | ".join(summary_parts) if summary_parts else "诊断流程已完成"

    return {
        "messages": [
            {
                "role": "assistant",
                "content": f"【诊断完成】{summary}",
            }
        ],
    }