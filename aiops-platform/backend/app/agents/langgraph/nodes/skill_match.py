from ..state import AIOpsState
from app.agents.skill_manager import SkillManager
import logging

_skill_manager = SkillManager()
logger = logging.getLogger(__name__)


async def skill_match_node(state: AIOpsState) -> dict:
    query = state["user_query"]
    intent_data = state.get("intent_data", {})

    logger.warning(f"[DEBUG skill_match] query={query}")
    logger.warning(f"[DEBUG skill_match] intent_data={intent_data}")

    matched_skills = _skill_manager.search_relevant_skills(
        query,
        intent_data,
    )

    logger.warning(f"[DEBUG skill_match] result={matched_skills}")

    skills_content = _skill_manager.get_relevant_skills_content(matched_skills)

    return {
        "matched_skills": matched_skills,
        "skills_content": skills_content,
        "messages": [
            {
                "role": "system",
                "content": (
                    f"匹配到 {len(matched_skills)} 个 Skill: "
                    f"{', '.join(matched_skills)}"
                ),
            }
        ],
    }
