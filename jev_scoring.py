from helper_func.llmAgentAPI import LLMAPI
from helper_func.chat_context_manager import ChatContextManager
from persona_db.PersonaDatabase import ChatInteraction
from config_loader import configToml
class JevScoringCog():
    def __init__(self):
        self.state = ChatContextManager()
        self.db = self.state.db
        self.llm_api: LLMAPI = self.state.llm_api

    def get_user_chat(self, user_id: int):
        """Get the chat history for a specific user"""
        return self.db.get_discord_user_chat_history(user_id)

if __name__ == "__main__":
    # Example usage
    cog = JevScoringCog()
    user_id = configToml["auth"]["admin_list"][0]
    chat_history = cog.get_user_chat(user_id)  # Get the last 10 chat interactions
    print("length of chat history:", len(chat_history))

    print(f"Chat history for user {user_id}:\n")
    for i, interaction in enumerate(chat_history[:10]):
        print(f"{i+1}. [{interaction.created_at}] {interaction.user_prompt} -> {interaction.main_content}")