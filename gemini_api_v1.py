from time import strftime
import uvicorn
from cog.llmAgentAPI import LLMAPI
from cog.utilFunc import UserDict
from cog_dev.moderation import PendingMessage, PendingMessageManager, TrimedResponse
from cog_dev.database_test import PersonaDatabase, Persona
import cog_dev.web_api as web_api
import asyncio
from config_loader import configToml

N = 16

chat_config: dict[str, str] = configToml.get("llmChat", "")
link_config: dict[str, str] = configToml.get("llmLink", "")
llm_base_url = link_config.get("link_openrouter", "")
mainModel = chat_config["modelDebug"]

class ChatCog:
    def __init__(self):
        self.llm_api = LLMAPI()
        
    async def close(self):
        await self.llm_api.cleanup()
        
async def cog_chatbot():
    # print(http_options)
    db = PersonaDatabase("llm_character_cards.db")
    api = ChatCog()
    # print(api.list_models())
    debug_persona_id = 21
    _persona = db.get_persona_no_check(debug_persona_id)
    assert isinstance(_persona, Persona)
    print(f"Using persona: {_persona.persona}")
    
    user_dict = UserDict(
        uid=0,
        name="USER",
        display_name="USER"
    )
    
    while True:
        # example message: 哈基亞，你今天的日程計劃如何?
        userPrompt = await asyncio.to_thread(input, f"{user_dict.display_name}: ")
        print("Processing...")
        if userPrompt.lower() in ["exit", "quit"]:
            break

        try:
            tResponse = await api.llm_api.handle_llm_agent(
                content=userPrompt,
                _persona=_persona,
                _user_dict=user_dict,
                encoded_image=None,
            )
            print(str(tResponse))

        except Exception as e:
            print(f"Error during chat: {e}")
            
    await api.close()
    
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
    
