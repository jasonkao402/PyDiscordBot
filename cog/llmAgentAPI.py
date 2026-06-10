from collections import deque, defaultdict
from cog.utilFunc import UserDict, PlaceholderReplacer
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
extra_body = {
    "provider": {
        "order": [],
        "ignore": ["fireworks", "streamlake", "phala", "venice", "moonshotai/int4", "novita", "parasail/int4"],
        "sort": "throughput",
    },
    "reasoning": {"enabled": True},
}

class LLMAPI:
    def __init__(self, _main_model: Optional[str] = None, _debug_mode: bool = False):
        self.main_model = (
            _main_model if _main_model is not None else chat_config["modelChat"]
        )
        self.round_robin_api_index = 0
        self.api_call_count = 0  # Counter to track the number of API calls
        self.api_switch_threshold = (
            5  # Number of calls before switching to the next API
        )
        self.round_robin_api_collection = configToml["apiToken"].get(
            "openrouter_llm", []
        )
        self.debug_mode = _debug_mode
        # self.llm_apis = [genai.Client(
        #     api_key=api_key, http_options=http_options,
        # ) for api_key in self.round_robin_api_collection]
        self.llm_apis = [
            AsyncOpenAI(api_key=api_key, base_url=llm_base_url)
            for api_key in self.round_robin_api_collection
        ]
        self.persona_session_memory: defaultdict[int, deque[ChatInteraction]] = (
            defaultdict(lambda: deque(maxlen=FULL_MEMORY_RANGE))
        )
        print(
            f"Loaded LLM API with model = {self.main_model}, created {len(self.llm_apis)} clients @ {llm_base_url}."
        )

    async def cleanup(self):
        for llm_api in self.llm_apis:
            await llm_api.close()

    def inspect_memory(self, persona_id: int) -> list[ChatInteraction]:
        return list(self.persona_session_memory[persona_id])

    def reset_memory(self, persona_id: int):
        self.persona_session_memory.pop(persona_id, None)

    def _expand_ChatInteraction_to_messages(
        self, chat_interactions: deque[ChatInteraction], skip_memorized: bool = False
    ) -> list[dict]:
        messages = []
        for interaction in chat_interactions:
            # skip messages that are already marked as memorized if skip_memorized is True
            if skip_memorized and interaction.is_memorized:
                continue

            if interaction.user_prompt and interaction.main_content:
                _user_role_name = interaction.__getattribute__("user_internal_name") or f"User{interaction.user_uid%10000}"
                messages.append({"role": "user", "content": interaction.user_prompt, "name": _user_role_name})
                messages.append(
                    {"role": "assistant", "content": interaction.main_content}
                )

        return messages

    def get_msg_uids_from_memory(
        self, persona_id: int, skip_memorized: bool = False
    ) -> list[int]:
        chat_interactions = self.persona_session_memory[persona_id]
        return [
            interaction.msg_uid
            for interaction in chat_interactions
            if not (skip_memorized and interaction.is_memorized)
        ]

    def _debug_response(self,  timestamp: int, message: str="") -> TrimedResponse:
        return TrimedResponse(
            response_text=f"[Debug] {_now_iso()} {message}",
            timestamp=timestamp,
            _code=-1,
        )

    async def llm_api_v6(
        self,
        messages: list[dict],
        system: str,
        user_dict: UserDict,
        image: Optional[gtypes.Part | dict] = None,
    ) -> TrimedResponse:
        """
        messages: list of strings (assistant / user messages)
        system: system instruction string
        user_dict: dictionary containing user information
        image: optional image part for the last user message
        """
        _timestamp = time_ns()
        try:
            message_list = [
                {"role": "system", "content": system},
                *messages,
            ]
            _temp = message_list[-1].get("content", "")
            if image and isinstance(_temp, str):
                message_list[-1]["content"] = [
                    image,
                    {"type": "text", "text": _temp},
                ]

            if self.debug_mode:
                return self._debug_response(
                    _timestamp,
                    "Debug response."
                )

            else:
                response = await self.llm_apis[
                    self.round_robin_api_index
                ].chat.completions.create(
                    model=self.main_model,
                    messages=message_list,
                    max_tokens=5120,
                    extra_body=extra_body,
                )

        except errors.APIError as e:
            api_error = f"[{e.code}]{e.message}"
            print(f"API Error: {api_error}\n---")
            return self._debug_response(
                _timestamp,
                f"API Error: {api_error}"
            )

        response_text = str(response.choices[0].message.content)
        thinking_content = str(getattr(response.choices[0].message, "reasoning", ""))
        token_usage = (
            {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
                "cost": getattr(
                    response.usage, "cost", 0
                ),  # Some APIs might provide estimated cost
            }
            if response.usage
            else {}
        )
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
            _code=response_code,
        )

    async def persona_chat_oneshot(
        self,
        prompt_str: str,
        _persona: Persona,
        _user_dict: UserDict,
        encoded_image: Optional[str],
    ) -> TrimedResponse:
        """Get a response from the LLM for a given persona and user prompt (and message context from recent memory)"""
        persona_name = (
            _persona.persona_name if _persona.persona_name else "UnknownPersona"
        )

        _pr = PlaceholderReplacer(_user_dict)
        system_instruction = _pr.replace_placeholders(_persona.content)
        # f'\n最新對話發生在:{strftime("%Y/%m/%d %H:%M %a")}'
        
        _debug_user_persona_pair = f"{wcformat(_user_dict.name)}@{persona_name}"
        print(f"{_debug_user_persona_pair}: {prompt_str}\n")
        if self.debug_mode:
            print(f"[System]:\n{system_instruction}\n")
            
        latest_prompt = {
            "role": "user",
            "content": f"{_user_dict.effective_name} said {prompt_str}",
        }

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
                    },
                }
            tResponse = await self.llm_api_v6(
                [*self._expand_ChatInteraction_to_messages(chatMem), latest_prompt],
                system_instruction,
                user_dict=_user_dict,
                image=image_part,
            )

            # print(f'{user_persona_pair} Response:\n{tResponse}')

        except TimeoutError as e:
            print(f"{_debug_user_persona_pair} API request timed out. Error: {e}")
            return self._debug_response(
                _timestamp,
                f"{_debug_user_persona_pair} API request timed out. Please try again later.\n{e}"
            )

        except Exception as e:
            print(f"{_debug_user_persona_pair} Reply error:\n{e}")
            return self._debug_response(
                _timestamp,
                f"{_debug_user_persona_pair} Caught an exception:\n{e}"
            )

        else:
            # Only append to memory if no exception
            chatMem.append(
                ChatInteraction(
                    msg_uid=_timestamp,
                    user_uid=_user_dict.uid,
                    persona_uid=_persona.uid,
                    main_content=tResponse.response_text,
                    user_prompt=latest_prompt["content"],
                    user_internal_name=_user_dict.role_name,
                )
            )
            # For debugging: print the current memory
            if self.debug_mode:
                print(f"Current session memory for persona {persona_name}:")
                for idx, mem in enumerate(chatMem):
                    print(
                        f"{idx+1:2d}. User Prompt: {mem.user_prompt} | Assistant Reply: {mem.main_content} | Memorized: {mem.is_memorized}"
                    )

            return tResponse

    async def persona_memory_summarize(self, _persona: Persona, _user_dict: UserDict) -> TrimedResponse:
        """Summarize the recent memory for a given persona."""
        chatMem = self.persona_session_memory[_persona.uid]
        _timestamp = time_ns()
        if not chatMem:
            return TrimedResponse(
                response_text="No recent interactions to summarize.",
                timestamp=_timestamp,
                _code=-1,
            )
        
        _pr = PlaceholderReplacer(_user_dict)
        system_instruction = _pr.replace_placeholders(_persona.content)
        system_instruction += chat_config["promptMemoryFormat"]
        # system_instruction = f'{_persona.content}\n最新對話發生在:{strftime("%Y/%m/%d %H:%M %a")}\n{chat_config["promptMemoryFormat"]}'
        expand_messages = self._expand_ChatInteraction_to_messages(
            chatMem, skip_memorized=True
        )
        if not expand_messages:
            return TrimedResponse(
                response_text="No new interactions to summarize since the last summarization.",
                timestamp=_timestamp,
                _code=-1,
            )
        expand_messages.append(
            {"role": "user", "content": chat_config["promptMemoryTrigger"]+chat_config["promptMemoryFormat"]}
        )
        tResponse: TrimedResponse
        print(
            f"Summarizing memory with system instruction:\n...{system_instruction[-50:]}\nChatMem len() = {len(expand_messages)}:"
        )
        try:
            if self.debug_mode:
                for idx, mem in enumerate(expand_messages):
                    print(f"{idx+1:2d} {mem['role'][0]}: {mem['content']}")
                tResponse = self._debug_response(
                    _timestamp,
                    "Debug response for memory summarization."
                )
            else:
                tResponse = await self.llm_api_v6(
                    expand_messages,
                    system_instruction,
                    user_dict=UserDict(uid=0, name="System"),
                )

        except Exception as e:
            print(f"Memory summarization error:\n{e}")
            return self._debug_response(
                _timestamp,
                f"Memory summarization error:\n{e}"
            )
        else:
            # only mark as memorized if summarization succeeded
            for message in chatMem:
                message.is_memorized = True

        return tResponse
