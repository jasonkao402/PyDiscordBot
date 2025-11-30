from time import strftime

from flask import g
from cog_dev.database_test import PersonaDatabase, Persona
import asyncio
from google import genai
from google.genai import types as gtypes, errors
from collections import deque
from config_loader import configToml
import json

N = 16

# Typed http_options to satisfy Client's expected HttpOptionsDict
http_options = gtypes.HttpOptions(
    # base_url=f"{configToml['llmLink']['link_gcli2api']}?key={configToml['apiToken']['gemini_llm'][0]}", timeout=60,
    base_url=str(configToml["llmLink"]["link_gcli2api"]), timeout=60,
    headers={"x-goog-api-key" : configToml["apiToken"]["gemini_llm"][0]},
)

class ChatCog:
    def __init__(self):
        self.client = genai.Client(
            api_key=configToml["apiToken"]["gemini_llm"][0],
            http_options=http_options,
            )
        
    def list_models(self) -> str:
        models = self.client.models.list()
        model_names = [str(model.name) for model in models]
        model_names = "\n".join(model_names)
        return model_names

    async def llm_chat_v5(self, messages: list[dict], system: str) -> str:
        """
        messages: list of strings (system + user messages)
        """
        try:
            # 將 messages 轉成 Google GenAI 的 contents
            # (type) ContentListUnion = Content | str | Image | File | Part | list[str | Image | File | Part] | list[Content | str | Image | File | Part | list[str | Image | File | Part]]
            message_contents = [
                gtypes.Content(parts=list([gtypes.Part(text=msg['content'])]), role=msg["role"]) for msg in messages
            ]
            
            response = await self.client.aio.models.generate_content(
                model=configToml["llmChat"]["modelChat"],
                contents=list(message_contents),
                config=gtypes.GenerateContentConfig(
                    http_options=http_options,
                    system_instruction=system,
                    temperature=1.0,
                    max_output_tokens=4096,
                    thinking_config=gtypes.ThinkingConfig(
                        thinking_level=gtypes.ThinkingLevel.LOW
                    ),
                ),
            )
        except errors.APIError as e:
            api_error = f"[{e.code}]{e.message}"
            print(f"GenAI Error: {api_error}")
            return api_error

        response_text = str(response.text)
        if response.usage_metadata:
            print(response.usage_metadata.total_token_count)
        return response_text

async def main():
    print(http_options)
    db = PersonaDatabase("llm_character_cards.db")
    api = ChatCog()
    # print(api.list_models())
    _persona = db.get_persona_no_check(3)
    assert isinstance(_persona, Persona)
    print(f"Using persona: {_persona.persona}")
    userName = "USER"
    persona_session_memory = deque(maxlen=N)
    # chat_config = types.GenerateContentConfig(
    #     http_options=http_options,
    #     system_instruction=f'{_persona.content} 現在是{strftime("%Y-%m-%d %H:%M %a")}',
    #     temperature=1.0,
    #     max_output_tokens=4096,
    #     thinking_config=types.ThinkingConfig(thinking_level="low"),
    # )

    # async_chat = client.aio.chats.create(
    # model=configToml["llmChat"]["modelChat"],
    # config=chat_config,
    # )
    while True:
        userPrompt = input(f"{userName}: ")
        if userPrompt.lower() in ["exit", "quit"]:
            break

        try:
            # reply = await async_chat.send_message(f"{userName} said {userPrompt}")
            reply = await api.llm_chat_v5(
                messages=[{"role": "user", "content": f"{userName} said {userPrompt}"}],
                system=f'{_persona.content} 現在是{strftime("%Y-%m-%d %H:%M %a")}',
            )
            # print(reply)
            print(f"\n{_persona.persona}: {reply}")

        except Exception as e:
            print(f"Error during chat: {e}")
        else:
            persona_session_memory.append(userPrompt)
            persona_session_memory.append({"role": "model", "content": reply})
            
    api.client.close()

if __name__ == "__main__":
    asyncio.run(main())
