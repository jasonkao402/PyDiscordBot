# helper_func/jev_gate.py
from typesafe_sdk import AsyncTypeSafeClient, Choice, Noul, Score
from config_loader import configToml

JEV_URL = configToml["api_token"].get("url", "")
JEV_MODEL = configToml["api"]

async def gate_message(
    client: AsyncTypeSafeClient,
    message: str,
    recent_context: list[str],
    persona_name: str,
    subject_name: str,
) -> dict:
    result = dict()
    async with AsyncTypeSafeClient() as client:
        response = await client.system_one(
            state={
                "persona": persona_name,
                "speaker": subject_name,
                "recent_context": recent_context[-3:],
                "message": message,
            },
            questions={
                "memorable": Noul(instructions="Is this message a non-repeatable, memory-worthy fact "
                                    "about the speaker or the ongoing topic? "
                                    "Ignore small talk, emoji-only, repetition, and "
                                    "information already present in recent_context."),
                # "tone": Choice(
                #     instructions="What is the customer's tone?",
                #     criteria={"calm": None, "frustrated": None, "angry": None},
                # ),
                "decision_impact": Score(
                    instructions="If this knowledge did not exist, how likely is the agent "
                                "to make a different or incorrect decision in a future interaction?",
                    criteria=["No impact — generic knowledge the LLM already has",
                                        "Minor — slightly better phrasing only",
                                        "Moderate — would get a preference or detail wrong",
                                        "High — would give a factually wrong answer about this person",],
                ),
            },
            model=JEV_MODEL,
        )
    result["memorable"] = response.nouls["memorable"].noul
    result["decision_impact"] = response.scores["decision_impact"].score
    return result