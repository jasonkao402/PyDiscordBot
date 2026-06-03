from collections import deque, defaultdict
from cog.utilFunc import UserDict
from cog_dev.responseParsing import parse_response
from cog_dev.moderation import PendingMessage, TrimedResponse
from persona_db.PersonaDatabase import Persona
from persona_db.DatabaseModels import ChatInteraction
from persona_db.helper_func import _now_iso
import cog_dev.web_api as web_api
from config_loader import configToml

from openai import AsyncOpenAI
# from google import genai
from google.genai import types as gtypes, errors
from typing import Optional
from uuid import uuid4
from time import strftime, time_ns
from cog.utilFunc import wcformat

chat_config: dict[str, str] = configToml.get("llmChat", "")
link_config: dict[str, str] = configToml.get("llmLink", "")
llm_base_url = link_config.get("link_openrouter", "")

FULL_MEMORY_RANGE = 10
SUM_MEMORY_RANGE = 10
VECTOR_MEMORY_RANGE = 3

class LLMAPI:
    def __init__(self, _main_model: Optional[str] = None, _debug_mode: bool = False):
        self.main_model = _main_model if _main_model is not None else chat_config["modelChat"]
        self.round_robin_api_index = 0
        self.api_call_count = 0  # Counter to track the number of API calls
        self.api_switch_threshold = 5  # Number of calls before switching to the next API
        self.round_robin_api_collection = configToml['apiToken'].get('openrouter_llm', [])
        self.debug_mode = _debug_mode
        # self.llm_apis = [genai.Client(
        #     api_key=api_key, http_options=http_options,
        # ) for api_key in self.round_robin_api_collection]
        self.llm_apis = [AsyncOpenAI(api_key = api_key, base_url = llm_base_url) for api_key in self.round_robin_api_collection]
        self.persona_session_memory: defaultdict[int, deque[ChatInteraction]] = defaultdict(lambda: deque(maxlen=FULL_MEMORY_RANGE))
        print(f'Loaded LLM API with model = {self.main_model}, created {len(self.llm_apis)} clients @ {llm_base_url}.')
    
    async def cleanup(self):
        for llm_api in self.llm_apis:
            await llm_api.close()
    
    def inspect_memory(self, persona_id: int) -> list[ChatInteraction]:
        return list(self.persona_session_memory[persona_id])
    
    def reset_memory(self, persona_id: int):
        self.persona_session_memory.pop(persona_id, None)
    
    def _expand_ChatInteraction_to_messages(self, chat_interactions: deque[ChatInteraction], skip_memorized: bool = False) -> list[dict]:
        messages = []
        for interaction in chat_interactions:
            # skip messages that are already marked as memorized if skip_memorized is True 
            if skip_memorized and interaction.is_memorized:
                continue

            if interaction.user_prompt and interaction.main_content:
                messages.append({"role": "user", "content": interaction.user_prompt})
                messages.append({"role": "assistant", "content": interaction.main_content})

        return messages

    def get_msg_uids_from_memory(self, persona_id: int, skip_memorized: bool = False) -> list[int]:
        chat_interactions = self.persona_session_memory[persona_id]
        return [interaction.msg_uid for interaction in chat_interactions if not (skip_memorized and interaction.is_memorized)]
    
    def _debug_response(self, message: str, timestamp: int) -> TrimedResponse:
        return TrimedResponse(
            response_text=f"[Debug] {_now_iso()} {message}",
            thinking_content="",
            timestamp=timestamp,
            token_usage={}
        )
        
    async def llm_chat_v6(self, messages: list[dict], system: str, user_dict: UserDict, image: Optional[gtypes.Part | dict] = None) -> TrimedResponse:
        """
        messages: list of strings (model / user messages)
        system: system instruction string
        user_dict: dictionary containing user information
        image: optional image part for the last user message
        """
        _timestamp = time_ns()
        try:
            message_list=[
                    {"role": "system", "content": system},
                    *[
                        {
                            "role": msg["role"],
                            "content": msg["content"]
                        } for msg in messages
                    ]
                ]
            
            if image:
                message_list[-1]["content"] = [image, {"type": "text", "text": message_list[-1]["content"]}]
            
            if self.debug_mode:
                return self._debug_response("This is a debug response. No actual API call was made.", _timestamp)

            else:
                response = await self.llm_apis[self.round_robin_api_index].chat.completions.create(
                    model=self.main_model,
                    messages=message_list,
                    max_tokens=4096,
                    extra_body={"reasoning": {"enabled": True}},
                )
        except errors.APIError as e:
            api_error = f"[{e.code}]{e.message}"
            print(f"API Error: {api_error}\n---")
            return TrimedResponse(response_text=f"API Error: {api_error}", thinking_content="", timestamp=_timestamp, token_usage={}, _code=-1)
        
        response_text = str(response.choices[0].message.content)
        thinking_content = str(getattr(response.choices[0].message, 'reasoning', ""))
        token_usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
            "cost": getattr(response.usage, 'cost', 0)  # Some APIs might provide estimated cost
        } if response.usage else {}
        response_code = 200 if response else -1

        final_msg = await web_api.pending_manager.moderate(
            PendingMessage(
                uid=str(uuid4()),
                user_id=user_dict.uid,
                user_display_name=user_dict.effective_name,
                input_msg=messages[-1]["content"] if messages else "",
                content=response_text,
            )
        )
        
        return TrimedResponse(
            response_text=final_msg.content,
            thinking_content=thinking_content,
            timestamp=_timestamp,
            token_usage=token_usage,
            _code=response_code
        )
    
    async def persona_chat_oneshot(self, prompt_str: str, _persona: Persona, _user_dict: UserDict, encoded_image: Optional[str]) -> TrimedResponse:
        """Handle the logic for interacting with the LLM agent."""
        persona_name = _persona.persona_name if _persona.persona_name else "UnknownPersona"
        user_persona_pair = f'{wcformat(_user_dict.name)}@{persona_name}'
        # Filter out mention bot part
        print(f'{user_persona_pair}: {prompt_str}')

        system_instruction = f'{_persona.content}\n最新對話發生在:{strftime("%Y/%m/%d %H:%M %a")}'
        latest_prompt = {'role': 'user', 'content': f'{_user_dict.display_name} said {prompt_str}'}

        chatMem = self.persona_session_memory[_persona.uid]
        _timestamp = time_ns()
        try:
            image_part = dict()
            if encoded_image:
                # OpenAI
                image_part = {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{encoded_image}",
                        "detail": "low",
                    }
                }
            tResponse = await self.llm_chat_v6([*self._expand_ChatInteraction_to_messages(chatMem), latest_prompt], system_instruction, user_dict=_user_dict, image=image_part)

            # print(f'{user_persona_pair} Response:\n{tResponse}')

        except TimeoutError as e:
            print(f'{user_persona_pair} API request timed out. Error: {e}')
            return TrimedResponse(
                response_text = f'{user_persona_pair} API request timed out. Please try again later.\n{e}',
                thinking_content="",
                timestamp=_timestamp,
                token_usage={},
                _code=-1
            )
            
        except Exception as e:
            print(f'{user_persona_pair} Reply error:\n{e}')
            return TrimedResponse(
                response_text = f'{user_persona_pair} 發生錯誤，請聯繫主人\n{e}',
                thinking_content="",
                timestamp=_timestamp,
                token_usage={},
                _code=-1
            )
            
        else:
            # Only append to memory if no exception
            chatMem.append(ChatInteraction(
                msg_uid=_timestamp,
                user_uid=_user_dict.uid,
                persona_uid=_persona.uid,
                main_content=tResponse.response_text,
                user_prompt=latest_prompt["content"],
            ))
            # For debugging: print the current memory
            if self.debug_mode:
                print(f"Current session memory for persona {persona_name}:")
                for idx, mem in enumerate(chatMem):
                    print(f"{idx+1:2d}. User Prompt: {mem.user_prompt} | Assistant Reply: {mem.main_content} | Memorized: {mem.is_memorized}")
                
            # chatMem.append(prompt)
            # chatMem.append({'role': 'assistant', 'content': reply_content})
            
            return tResponse
    
    async def persona_memory_summarize(self, _persona: Persona) -> TrimedResponse:
        """Summarize the recent memory for a given persona."""
        chatMem = self.persona_session_memory[_persona.uid]
        _timestamp = time_ns()
        if not chatMem:
            return TrimedResponse(
                response_text="No recent interactions to summarize.",
                thinking_content="",
                timestamp=_timestamp,
                token_usage={},
                _code=-1
            )
            
        system_instruction = f'{_persona.content}\n最新對話發生在:{strftime("%Y/%m/%d %H:%M %a")}\n{chat_config["promptMemoryFormat"]}'
        expand_messages = self._expand_ChatInteraction_to_messages(chatMem, skip_memorized=True)
        tResponse : TrimedResponse
        try:
            if not expand_messages:
                return TrimedResponse(
                    response_text="No new interactions to summarize since the last summarization.",
                    thinking_content="",
                    timestamp=_timestamp,
                    token_usage={},
                    _code=-1
                )
            if self.debug_mode:
                print(f"Summarizing memory with system instruction:\n{system_instruction}\nChatMem len() = {len(expand_messages)}:")
                for idx, mem in enumerate(expand_messages):
                    print(f"{idx+1:2d} {mem['role'][0]}: {mem['content']}")
                tResponse = self._debug_response("This is a debug response for memory summarization. No actual API call was made.", _timestamp)
            else:
                tResponse = await self.llm_chat_v6(expand_messages, system_instruction, user_dict=UserDict(uid=0, name="System", display_name="System"))

        except Exception as e:
            print(f'Memory summarization error:\n{e}')
            return TrimedResponse(
                response_text = f'Memory summarization error:\n{e}',
                thinking_content="",
                timestamp=_timestamp,
                token_usage={},
                _code=-1
            )
        else:
            # only mark as memorized if summarization succeeded
            for message in chatMem:
                message.is_memorized = True

        return tResponse