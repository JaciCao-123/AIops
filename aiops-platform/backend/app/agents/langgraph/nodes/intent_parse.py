from ..state import AIOpsState
from app.agents.intent_parse import IntentParseAgent

_intent_agent = IntentParseAgent()


async def intent_parse_node(state: AIOpsState) -> dict:
    intent_result = await _intent_agent.parse(state["user_query"])
    entities_result = await _intent_agent.extract_entities(state["user_query"])

    entities_dict = (
        entities_result.model_dump()
        if hasattr(entities_result, "model_dump")
        else entities_result
    )

    ner_entities = []
    for e in intent_result.ner_entities:
        ner_entities.append(e.model_dump() if hasattr(e, "model_dump") else e)

    return {
        "intent_data": {
            "intent": intent_result.intent,
            "confidence": intent_result.confidence,
            "entities": entities_dict,
            "normalized_query": intent_result.normalized_query,
            "ner_entities": ner_entities,
            "keywords": intent_result.keywords,
        },
        "entities": entities_dict,
        "intent_type": intent_result.intent,
        "messages": [
            {
                "role": "system",
                "content": (
                    f"意图识别完成: {intent_result.intent}, "
                    f"置信度: {intent_result.confidence}"
                ),
            }
        ],
    }
