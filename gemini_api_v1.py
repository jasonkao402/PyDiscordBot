from time import strftime, time, monotonic
from uuid import uuid4
import uvicorn
# from cog.askAI import 
from cog_dev.moderation import PendingMessage, PendingMessageManager, TrimedResponse
from cog_dev.database_test import PersonaDatabase, Persona
import cog_dev.web_api as web_api
import asyncio
from openai import AsyncOpenAI
from google import genai
from google.genai import types as gtypes, errors
from collections import deque
from config_loader import configToml

N = 16

chat_config: dict[str, str] = configToml.get("llmChat", "")
link_config: dict[str, str] = configToml.get("llmLink", "")
llm_base_url = link_config.get("link_openrouter", "")
mainModel = chat_config["modelDebug"]
# Typed http_options to satisfy Client's expected HttpOptionsDict
# http_options = gtypes.HttpOptions(
#     # base_url=f"{configToml['llmLink']['link_gcli2api']}?key={configToml['apiToken']['gemini_llm'][0]}", timeout=60,
#     base_url=str(configToml["llmLink"]["link_gcli2api"]), timeout=60,
#     headers={"x-goog-api-key" : configToml["apiToken"]["gemini_llm"][0]},
# )

class ChatCog:
    def __init__(self):
        # self.client = genai.Client(
        #     api_key=configToml["apiToken"]["gemini_llm"][0],
        #     http_options=http_options,
        #     )
        
        self.llm_api = AsyncOpenAI(api_key = configToml["apiToken"]["openrouter_llm"][0], base_url = llm_base_url)
        print(f'Loaded askAI cog with model = {mainModel}, LLM API client = {llm_base_url}.')
        
    # def list_models(self) -> str:
    #     models = self.client.models.list()
    #     model_names = [str(model.name) for model in models]
    #     model_names = "\n".join(model_names)
    #     return model_names

    async def llm_chat_v6(self, messages: list[dict], system: str, username: str) -> TrimedResponse:
        """
        messages: list of strings (system + user messages)
        """
        try:
            message_list = [
                {"role": "system", "content": system},
                *[
                    {
                        "role": msg["role"],
                        "content": msg["content"]
                    } for msg in messages
                ]
            ]
            
            response = await self.llm_api.chat.completions.create(
                model=mainModel,
                messages=message_list,
                max_tokens=1024,
                # extra_body={"thinking": {"type": "enabled"}},
                extra_body={"reasoning": {"enabled": False}},
            )
            # json_response = response.model_dump()
            # print(f"LLM API response: {json.dumps(json_response, indent=2)}\n---")
        
        except errors.APIError as e:
            api_error = f"[{e.code}]{e.message}"
            print(f"API Error: {api_error}\n---")
            return TrimedResponse(response_text=f"API Error: {api_error}", thinking_content="", token_usage={})
        
        response_text = str(response.choices[0].message.content)
        thinking_content = str(response.choices[0].message.reasoning) if hasattr(response.choices[0].message, 'reasoning') else "" # pyright: ignore[reportAttributeAccessIssue]
        token_usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens
        } if response.usage else {}
        
        final_msg = await web_api.pending_manager.moderate(
            PendingMessage(
                uid=str(uuid4()),
                user_id=0,  # Replace with actual user ID if available
                user_display_name=username,
                input_msg=messages[-1]["content"] if messages else "",
                content=response_text,
            )
        )
            
        return TrimedResponse(
            response_text=final_msg.content,
            thinking_content=thinking_content,
            token_usage=token_usage
        )

async def cog_chatbot():
    # print(http_options)
    db = PersonaDatabase("llm_character_cards.db")
    api = ChatCog()
    # print(api.list_models())
    debug_persona_id = 21
    _persona = db.get_persona_no_check(debug_persona_id)
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
        # example message: 哈基亞，你今天的日程計劃如何?
        userPrompt = await asyncio.to_thread(input, f"{userName}: ")
        print("Processing...")
        if userPrompt.lower() in ["exit", "quit"]:
            break

        try:
            # reply = await async_chat.send_message(f"{userName} said {userPrompt}")
            userPrompt_formatted = {"role": "user", "content": f"{userName} said {userPrompt}"}
            reply = await api.llm_chat_v6(
                messages=[*persona_session_memory, userPrompt_formatted],
                system=f'{_persona.content} 最新對話發生在{strftime("%Y-%m-%d %H:%M %a")}',
                username=userName
            )
            # print(f"[Peek]Thinking:\n{reply.thinking_content}")
            # print(f"[Peek]Response:\n{reply.response_text}")
            
            # print(reply)
            print(f"[{_persona.persona}]:")
            print(f"Thinking:\n{reply.thinking_content}")
            print(f"Response:\n{reply.response_text}")
            print(f"Token usage:\n{" ".join(f'{k}: {v}' for k, v in reply.token_usage.items())}")

        except Exception as e:
            print(f"Error during chat: {e}")
        else:
            persona_session_memory.append(userPrompt_formatted)
            persona_session_memory.append({"role": "assistant", "content": reply.response_text})
            
    await api.llm_api.close()
    
async def main():
    pending_manager = PendingMessageManager(update_callback=web_api.push_update)
    web_api.pending_manager = pending_manager
    
    bot_task = asyncio.create_task(cog_chatbot())
    
    # Run web API in background
    uvicorn_config = uvicorn.Config("cog_dev.web_api:app", host="localhost", port=8070, log_level="info")
    server = uvicorn.Server(uvicorn_config)
    api_task = asyncio.create_task(server.serve())
    
    try:
        # Wait until the user quits the chatbot
        await bot_task
    except asyncio.CancelledError:
        pass
    finally:
        # Gracefully shut down the web server
        print("\nShutting down web server...")
        server.should_exit = True
        await api_task

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram properly terminated.")
    
