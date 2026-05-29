from collections import deque
from cog_dev.responseParsing import parse_response
from cog_dev.moderation import PendingMessage, TrimedResponse
from cog_dev.database_test import Persona
import cog_dev.web_api as web_api
from config_loader import configToml
from openai import AsyncOpenAI
# from google import genai
from google.genai import types as gtypes, errors
from typing import Optional, List
from uuid import uuid4
from time import strftime
from cog.utilFunc import sepLines, wcformat

chat_config: dict[str, str] = configToml.get("llmChat", "")
link_config: dict[str, str] = configToml.get("llmLink", "")
llm_base_url = link_config.get("link_openrouter", "")
mainModel = chat_config["modelChat"]
MEMOLEN = 26

class LLMAPI:
    def __init__(self):
        self.round_robin_api_index = 0
        self.api_call_count = 0  # Counter to track the number of API calls
        self.api_switch_threshold = 5  # Number of calls before switching to the next API
        self.round_robin_api_collection = configToml['apiToken'].get('openrouter_llm', [])
        # self.llm_apis = [genai.Client(
        #     api_key=api_key,
        #     http_options=http_options,
        # ) for api_key in self.round_robin_api_collection]
        self.llm_apis = [AsyncOpenAI(api_key = api_key, base_url = llm_base_url) for api_key in self.round_robin_api_collection]
        self.persona_session_memory: dict[int, deque] = {}
        print(f'Loaded LLM API with model = {mainModel}, created {len(self.llm_apis)} clients @ {llm_base_url}.')
    
    async def cleanup(self):
        for llm_api in self.llm_apis:
            await llm_api.close()
            
    def init_memory(self, persona_id: int):
        if persona_id not in self.persona_session_memory:
            self.persona_session_memory[persona_id] = deque(maxlen=MEMOLEN) 
            
    async def llm_chat_v6(self, messages: list[dict], system: str, user_dict: dict, image: Optional[gtypes.Part | dict] = None) -> TrimedResponse:
        """
        messages: list of strings (model / user messages)
        system: system instruction string
        user_dict: dictionary containing user information
        image: optional image part for the last user message
        """
        try:
            """
            # Google API 將 messages 轉成 Google GenAI 的 contents
            message_contents = [
                gtypes.Content(parts=list([gtypes.Part(text=msg['content'])]), role=msg["role"]) for msg in messages
            ]
            
            if image:
                message_contents.append(
                    gtypes.Content(parts=[image], role="user")
                )
            content_config = gtypes.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=4096,
                thinking_config=gtypes.ThinkingConfig(
                    thinking_level=gtypes.ThinkingLevel.LOW
                ),
            )
            response = await self.llm_apis[self.round_robin_api_index].aio.models.generate_content(
                model=chat_config["modelChat"],
                contents=list(message_contents),
                config=content_config,
            )
            # """
            # Deepseek API / OpenAI API
            # """
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
            
            response = await self.llm_apis[self.round_robin_api_index].chat.completions.create(
                model=chat_config["modelChat"],
                messages=message_list,
                max_tokens=2048,
                extra_body={"reasoning": {"enabled": True}},
            )
            # """
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
        
        # if response.usage:
        #     print(f'Token usage: {response.usage.total_tokens} tokens')
        
        final_msg = await web_api.pending_manager.moderate(
            PendingMessage(
                uid=str(uuid4()),
                user_id=user_dict["id"],
                user_display_name=user_dict["display_name"] or user_dict["name"],
                input_msg=messages[-1]["content"] if messages else "",
                content=response_text,
            )
        )
        
        return TrimedResponse(
            response_text=final_msg.content,
            thinking_content=thinking_content,
            token_usage=token_usage
        )
    
    async def handle_llm_trigger(self, content: str, _persona: Persona, user_id: int, user_name: str, display_name: str, encoded_image: Optional[str]) -> TrimedResponse:
        """Handle the logic for detecting and triggering the LLM feature."""
        persona_name = _persona.persona if _persona.persona else "UnknownPersona"
        user_persona_pair = f'{wcformat(user_name)}@{persona_name}'
        # Filter out mention bot part
        print(f'{user_persona_pair}: {content}')

        system_instruction = f'{_persona.content}\n最新對話發生在:{strftime("%Y/%m/%d %H:%M %a")}'
        prompt = {'role': 'user', 'content': f'{display_name} said {content}'}

        # if _persona.uid not in self.persona_session_memory:
        #     self.persona_session_memory[_persona.uid] = deque(maxlen=MEMOLEN)
        self.init_memory(_persona.uid)
        chatMem = self.persona_session_memory[_persona.uid]
        user_dict = {
            "id": user_id,
            "name": user_name,
            "display_name": display_name,
        }
        try:
            image_part = dict()
            if encoded_image:
                # Handle image attachments
                # base64_image = base64.b64encode(await message.attachments[0].read()).decode('utf-8')
                # google AI code
                # print(f'Encoded image size: {len(base64_image)} characters')
                # image_part = gtypes.Part(
                #     inline_data=gtypes.Blob(
                #         mime_type="image/jpeg",
                #         data=base64.b64decode(base64_image),
                #     ),
                #     media_resolution=gtypes.MediaResolution.MEDIA_RESOLUTION_LOW
                # )
                # OpenAI code
                image_part = {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{encoded_image}",
                        "detail": "low",
                    }
                }
            reply_dict = await self.llm_chat_v6([*chatMem, prompt], system_instruction, user_dict=user_dict, image=image_part)

            print(f'{user_persona_pair} Response:\n{reply_dict}')

        except TimeoutError as e:
            print(f'{user_persona_pair} API request timed out. Error: {e}')
            return TrimedResponse(
                response_text = f'{user_persona_pair} API request timed out. Please try again later.\n{e}',
                thinking_content="",
                token_usage={}
            )
            
        except Exception as e:
            print(f'{user_persona_pair} Reply error:\n{e}')
            return TrimedResponse(
                response_text = f'{user_persona_pair} 發生錯誤，請聯繫主人\n{e}',
                thinking_content="",
                token_usage={}
            )
            
        else:
            # Only append to memory if no exception
            reply_content = reply_dict.response_text
            chatMem.append(prompt)
            chatMem.append({'role': 'assistant', 'content': reply_content})
            
            return reply_dict