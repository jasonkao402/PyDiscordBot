# jev_API.py
from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from typesafe_sdk import AsyncTypeSafeClient, Choice, Noul, Score

from config_loader import config_toml

if TYPE_CHECKING:
    from persona_db.PersonaDatabase import ChatInteraction

provider_jev = config_toml["llm_model"].get("provider_jev", "local_jev")  # Default to "local_jev" if not specified
class JevAPI:
    criteria_intent: ClassVar[dict[str, str]] = {
        "directive": "Setting rules, persona constraints, or correcting the AI's previous mistake.",
        "disclosure": "Sharing concrete personal facts, ongoing statuses, preferences, or specific life events.",
        "expressive": "Venting emotions, reacting, joking, flirting, or pure subjective bantering without new factual info.",
        "phatic": "Short greetings, acknowledgments (e.g., 'ok', 'lol'), or empty filler to keep conversation flowing.",
    }
    criteria_topic: ClassVar[dict[str, str]] = {
        "tech_work": "Coding, AI, engineering, work projects, or technical troubleshooting.",
        "entertainment": "Gaming, anime, media, streams, or recreational hobbies.",
        "life_routine": "Food, travel, physical surroundings, daily schedule, or real-world errands.",
        "venting_care": "Personal struggles, negative emotions, health/fatigue, or seeking emotional support.",
        "intimacy": "Romance, affection, relationship dynamics, or NSFW/sensual teasing.",
    }

    def __init__(self) -> None:
        self.jev_model = config_toml["llm_model"].get("model_jev", "")
        self.jev_url = config_toml["api_token"][provider_jev].get("url", "")
        self.jev_key = config_toml["api_token"][provider_jev].get("keys", "")[0]
        self.client = AsyncTypeSafeClient(api_key=self.jev_key, model=self.jev_model, base_url=self.jev_url)

    async def cleanup(self):
        if self.client:
            await self.client.aclose()

    async def gate_message(self, recent_context: dict, persona_name: str, subject_name: str) -> dict:
        response = await self.client.system_one(
            state={
                "AI companion": persona_name,
                "user": subject_name,
                "user_prompt": recent_context["u"],
                "persona_response": recent_context["a"][:150],
            },
            questions={
                "memorable": Noul(
                    instructions=f"From {persona_name}'s perspective, is this message a non-repeatable, memory-worthy fact about {subject_name} or the ongoing topic?"
                    "Ignore small talk, spam-like content, repetition and perishable information."
                ),
                "topic": Choice(
                    instructions="Which topical domain best describes the subject matter of the message?",
                    criteria=self.criteria_topic,
                ),
                "decision_impact": Score(
                    instructions=f"From {persona_name}'s perspective, if this knowledge about {subject_name} did not exist, "
                    "how likely is a different or incorrect decision to be made in a future interaction?",
                    criteria=[
                        "No impact — generic knowledge the LLM already has",
                        "Moderate — would get a preference or detail wrong",
                        "High — would give a factually wrong answer about this person",
                    ],
                ),
            },
        )

        return {
            "memorable": response.nouls["memorable"].noul,
            "topic": response.choices["topic"].choice,
            "decision_impact": response.scores["decision_impact"].score,
        }

    async def message_intent(self, recent_context: dict, persona_name: str, subject_name: str) -> dict:
        """Determine the intent of a message using the Jev model."""
        response = await self.client.system_one(
            state={"AI companion": persona_name, "user": subject_name, "user_prompt": recent_context["u"]},
            questions={
                "intent": Choice(
                    instructions="What is the primary communicative function of the user's message?",
                    criteria=self.criteria_intent,
                ),
            },
        )
        return {"intent": response.choices["intent"].choice}


def chat_formatting(interaction: ChatInteraction) -> dict:
    """Format a chat interaction for jev scoring."""
    return {"u": interaction.user_prompt, "a": interaction.main_content}
