from ..state import AIOpsState
from app.agents.skill_manager import SkillManager

_skill_manager = SkillManager()


async def skill_match_node(state: AIOpsState) -> dict:
    matched_skills = _skill_manager.search_relevant_skills(
        state["user_query"],
        state.get("intent_data", {}),
    )
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
