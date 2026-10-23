# helper_func/llmAgentAPI.py
from __future__ import annotations

from collections import defaultdict, deque
from time import time_ns
from typing import TYPE_CHECKING
from uuid import uuid4

from google.genai import errors
from openai import AsyncOpenAI

from cog_dev import web_api
from cog_dev.moderation import PendingMessage, TrimedResponse
from config_loader import configToml
from helper_func.utilFunc import PlaceholderReplacer, UserDict, wcformat
from persona_db.DatabaseModels import ChatInteraction
from persona_db.helper_func import iso_timestamp

if TYPE_CHECKING:
    from persona_db.PersonaDatabase import Persona

model_config: dict[str, str] = configToml.get("llm_model", "")
prompt_config: dict[str, str] = configToml.get("prompt_template", "")

api_provider = configToml["llm_model"].get("provider", "NOT_FOUND")
detail_memory_range = configToml["llm_model"].get("detail_memory_range", 14)
summary_memory_range = configToml["llm_model"].get("summary_memory_range", 14)
retrieval_memory_range = configToml["llm_model"].get("retrieval_memory_range", 3)
round_robin_quota = configToml["llm_model"].get("round_robin_quota", 50)
extra_body = {
    # "provider": {
    #     "order": ["coreweave/fp8", "relace", "digitalocean", "deepinfra/fp8"],
    #     "ignore": ["fireworks", "streamlake", "phala", "venice", "moonshotai/int4", "novita", "parasail/int4"],
    #     "sort": "throughput",
    # },
    "reasoning_effort": "low",
    # "reasoning": {"enabled": True},
}


class LLMAPI:
    def __init__(self, _main_model: str | None = None, _debug_mode: bool = False) -> None:
        self.main_model = (
            _main_model if _main_model is not None else model_config["model_main"]
        )
        self.available_models: list[str] = []  # Cache for available models

        _api_key_pool = configToml["api_token"][api_provider].get("keys", [])
        _api_base_url = configToml["api_token"][api_provider].get("url", "")
        self.max_tokens = configToml["llm_model"].get("max_tokens", 5120)
        # Initialize round-robin usage counter and quota
        self.round_robin_usage = 0
        self.round_robin_quota = round_robin_quota
        self.round_robin_api_index = 0
        self.round_robin_api_total = len(_api_key_pool)

        self.debug_mode = _debug_mode
        # self.llm_apis = [genai.Client(
        #     api_key=api_key, http_options=http_options,
        # ) for api_key in _api_key_pool]
        self.llm_apis = [
            AsyncOpenAI(api_key=api_key, base_url=_api_base_url)
            for api_key in _api_key_pool
        ]
        self.persona_session_memory: defaultdict[int, deque[ChatInteraction]] = (
            defaultdict(lambda: deque(maxlen=detail_memory_range))
        )
        print(
            f"Loaded LLM API with model = {self.main_model}, created {len(self.llm_apis)} clients @ {_api_base_url}."
        )

    async def cleanup(self):
        for llm_api in self.llm_apis:
            await llm_api.close()
        print(f"Closed {len(self.llm_apis)} LLM API clients.")

    def inspect_memory(self, persona_id: int) -> list[ChatInteraction]:
        return list(self.persona_session_memory[persona_id])

    def reset_memory(self, persona_id: int):
        self.persona_session_memory.pop(persona_id, None)

    def rotate_api_index(self):
        """Rotate the API index for round-robin usage."""
        self.round_robin_usage += 1
        if self.round_robin_usage >= self.round_robin_quota:
            c, n = self.round_robin_api_index, (self.round_robin_api_index + 1) % self.round_robin_api_total
            print(f"Switching API from index {c} to {n}.")
            self.round_robin_api_index = n
            self.round_robin_usage = 0  # Reset the counter after switching

    def expand_chat_interaction_to_messages(
        self, chat_interactions: deque[ChatInteraction], skip_memorized: bool = False
    ) -> list[dict]:
        messages = []
        for interaction in chat_interactions:
            # skip messages that are already marked as memorized if skip_memorized is True
            if skip_memorized and interaction.is_memorized:
                continue

            if interaction.user_prompt and interaction.main_content:
                _user_role_name = interaction.user_internal_name or f"User{interaction.user_uid % 10000}"
                messages.extend(({"role": "user", "content": interaction.user_prompt, "name": _user_role_name},
                                 {"role": "assistant", "content": interaction.main_content}))

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

    def _debug_response(self, timestamp: int, message: str = "") -> TrimedResponse:
        return TrimedResponse(
            response_text=f"[Debug] {iso_timestamp()} {message}",
            timestamp=timestamp,
            _code=-1,
        )

    def _debug_system_instruction(self, _persona: Persona, _user_dict: UserDict) -> str:
        _pr = PlaceholderReplacer(_user_dict)
        return _pr.replace_placeholders(_persona.content)

    async def llm_api_v6(
        self,
        messages: list[dict],
        system: str,
        user_dict: UserDict,
        image: str | dict | None = None,
    ) -> TrimedResponse:
        """
        messages: list of strings (assistant / user messages)
        system: system instruction string
        user_dict: dictionary containing user information
        image: optional image part for the last user message
        """
        _timestamp = time_ns()
        if self.debug_mode:
            return self._debug_response(
                _timestamp,
                "Debug response."
            )
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
        try:
            response = await self.llm_apis[
                self.round_robin_api_index
            ].chat.completions.create(
                model=self.main_model,
                messages=message_list,
                max_tokens=self.max_tokens,
                extra_body=extra_body,
            )
            self.rotate_api_index()  # Rotate API index after a successful call

        except errors.APIError as e:
            api_error = f"[{e.code}]{e.message}"
            print(f"API Error: {api_error}\n---")
            return self._debug_response(
                _timestamp,
                f"API Error: {api_error}"
            )
        print(f"{response.choices[0].message}\n" + "=" * 20)
        response_text = str(response.choices[0].message.content)
        thinking_content = str(
            getattr(response.choices[0].message, "reasoning", None) or
            getattr(response.choices[0].message, "reasoning_content", None) or
            ""
        )
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
        encoded_image: str | None = None,
    ) -> TrimedResponse:
        """Get a response from the LLM for a given persona and user prompt (and message context from recent memory)"""
        persona_name = (
            _persona.persona_name or "UnknownPersona"
        )

        _pr = PlaceholderReplacer(_user_dict)
        system_instruction = _pr.replace_placeholders(_persona.content)
        # f'\n最新對話發生在:{strftime("%Y/%m/%d %H:%M %a")}'

        _debug_user_persona_pair = f"{wcformat(_user_dict.name)}@{persona_name}"
        print(f"{_debug_user_persona_pair}: {prompt_str}\n")

        latest_prompt = {
            "role": "user",
            "content": f"{_user_dict.effective_name} said {prompt_str}",
        }

        chat_mem = self.persona_session_memory[_persona.uid]
        _timestamp = time_ns()
        try:
            image_part = {}
            if encoded_image:
                # OpenAI
                image_part = {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{encoded_image}",
                        "detail": "low",
                    },
                }
            response = await self.llm_api_v6(
                [*self.expand_chat_interaction_to_messages(chat_mem), latest_prompt],
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
            chat_mem.append(
                ChatInteraction(
                    msg_uid=_timestamp,
                    user_uid=_user_dict.uid,
                    persona_uid=_persona.uid,
                    main_content=response.response_text,
                    user_prompt=latest_prompt["content"],
                    user_internal_name=_user_dict.role_name,
                )
            )
            # For debugging: print the current memory
            if self.debug_mode:
                print(f"Current session memory for persona {persona_name}:")
                for idx, mem in enumerate(chat_mem):
                    print(
                        f"{idx + 1:2d}. User Prompt: {mem.user_prompt} | Assistant Reply: {mem.main_content} | Memorized: {mem.is_memorized}"
                    )

            return response

    async def persona_memory_summarize(self, _persona: Persona, _user_dict: UserDict) -> TrimedResponse:
        """Summarize the recent memory for a given persona."""
        chat_mem = self.persona_session_memory[_persona.uid]
        _timestamp = time_ns()
        if not chat_mem:
            return TrimedResponse(
                response_text="No recent interactions to summarize.",
                timestamp=_timestamp,
                _code=-1,
            )

        _pr = PlaceholderReplacer(_user_dict)
        system_instruction = _pr.replace_placeholders(_persona.content)
        system_instruction += prompt_config["memory_format"]
        # system_instruction = f'{_persona.content}\n最新對話發生在:{strftime("%Y/%m/%d %H:%M %a")}\n{prompt_config["memory_format"]}'
        expand_messages = self.expand_chat_interaction_to_messages(
            chat_mem, skip_memorized=True
        )
        if not expand_messages:
            return TrimedResponse(
                response_text="No new interactions to summarize since the last summarization.",
                timestamp=_timestamp,
                _code=-1,
            )
        expand_messages.append(
            {"role": "user", "content": prompt_config["memory_request"] + prompt_config["memory_format"]}
        )
        response: TrimedResponse
        print(
            f"Summarizing memory with system instruction:\n...{system_instruction[-50:]}\nChatMem len() = {len(expand_messages)}:"
        )
        try:
            if self.debug_mode:
                for idx, mem in enumerate(expand_messages):
                    print(f"{idx + 1:2d} {mem['role'][0]}: {mem['content']}")
                response = self._debug_response(
                    _timestamp,
                    "Debug response for memory summarization."
                )
            else:
                response = await self.llm_api_v6(
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
            for message in chat_mem:
                message.is_memorized = True

        return response

    def revert_last_interaction(self, persona_id: int) -> bool:
        """Revert the last interaction for a given persona."""
        chat_mem = self.persona_session_memory[persona_id]
        if chat_mem:
            removed_interaction = chat_mem.pop()
            print(f"Reverted last interaction for persona {persona_id}: {removed_interaction}")
            return True
        print(f"No interactions to revert for persona {persona_id}.")
        return False

    async def get_available_models(self, force_refresh: bool = False) -> list[str]:
        """Return a list of available models from the current LLM API."""
        if self.available_models and not force_refresh:
            return self.available_models  # Return cached models if available

        self.available_models = []  # Clear the cache
        _list = self.llm_apis[0].models.list()
        result = [model.id async for model in _list]
        self.available_models = result
        return result
