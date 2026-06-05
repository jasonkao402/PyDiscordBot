import uvicorn
from cog.llmAgentAPI import LLMAPI
from cog.utilFunc import UserDict
from cog_dev.moderation import PendingMessage, PendingMessageManager, TrimedResponse
from persona_db.PersonaDatabase import PersonaDatabase, Persona, DiscordUser
import cog_dev.web_api as web_api
import asyncio
from config_loader import configToml

chat_config: dict[str, str] = configToml.get("llmChat", "")
link_config: dict[str, str] = configToml.get("llmLink", "")
llm_base_url = link_config.get("link_openrouter", "")
debugModel = chat_config["modelDebug"]
debug_persona_id = 21
debug_user_id = configToml.get("auth", {}).get("adminList", [])[0]


class ChatCog:
    def __init__(self):
        self.llm_api = LLMAPI(_main_model=debugModel, _debug_mode=True)

    async def close(self):
        await self.llm_api.cleanup()


async def cog_chatbot():
    # print(http_options)
    db = PersonaDatabase("llm_character_cards.db")
    api = ChatCog()
    # print(api.list_models())

    _persona = db.get_persona_no_check(debug_persona_id)
    assert isinstance(_persona, Persona)
    print(f"Using persona: {_persona.persona_name}")
    
    _user = db.get_discord_user(debug_user_id)
    assert isinstance(_user, DiscordUser)
    user_dict = UserDict(uid=_user.user_uid, name=_user.preferred_name or "User")
    print(f"Using user: {user_dict.effective_name} (UID: {user_dict.uid})")

    while True:
        # example message: 哈基亞，你今天的日程計劃如何?
        userPrompt = await asyncio.to_thread(input, f"{user_dict.effective_name}: ")
        if userPrompt.lower() in ["exit", "quit"]:
            break

        print("Processing...")

        try:
            if userPrompt.lower() in ["memo"]:
                source_msg_uids = api.llm_api.get_msg_uids_from_memory(
                    debug_persona_id, skip_memorized=True
                )
                tResponse = await api.llm_api.persona_memory_summarize(
                    _persona=_persona
                )
                if tResponse._code == -1:
                    print(f"Summarization failed: {tResponse.response_text}")
                    continue
                db.increment_interaction_count(debug_persona_id, user_dict.uid)
                print(f"Memorized msg_uids: {source_msg_uids}")
                db.create_persona_memory(
                    memory_content=tResponse.response_text,
                    persona_uid=debug_persona_id,
                    source_msg_uids=source_msg_uids,
                )
            else:
                tResponse = await api.llm_api.persona_chat_oneshot(
                    prompt_str=userPrompt,
                    _persona=_persona,
                    _user_dict=user_dict,
                    encoded_image=None,
                )
                db.increment_interaction_count(debug_persona_id, user_dict.uid)
                if tResponse._code == -1:
                    print(f"Chat failed: {tResponse.response_text}")
                    continue
                res = db.create_chat_interaction(
                    msg_uid=tResponse.timestamp,
                    user_uid=user_dict.uid,
                    persona_uid=debug_persona_id,
                    main_content=tResponse.response_text,
                    user_prompt=userPrompt,
                )
                assert res, "Failed to create chat interaction in database"
            print(str(tResponse))

        except Exception as e:
            print(f"Error during chat: {e}")

    await api.close()


async def main():
    pending_manager = PendingMessageManager(update_callback=web_api.push_update)
    web_api.pending_manager = pending_manager

    bot_task = asyncio.create_task(cog_chatbot())

    # Run web API in background
    uvicorn_config = uvicorn.Config(
        "cog_dev.web_api:app", host="localhost", port=8070, log_level="info"
    )
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
