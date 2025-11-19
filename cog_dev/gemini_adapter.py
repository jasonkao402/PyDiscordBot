import asyncio
from typing import List
from google import genai
from google.genai import types

from config_loader import configToml

class GeminiAPIHandler:
    """A lightweight adapter to mimic Ollama chat interface using Gemini GenAI.

    Expected input: List[{"role": str, "content": str}]
    Returns: object with `.content` string, similar to previous API.
    """

    def __init__(self):
        # http_options = {
        #     "base_url": configToml["llmChat"]["link_build"],
        # }
        self._model = configToml["llmChat"]["modelChat"]
        self._client_collection = [genai.Client(
            api_key=configToml["apiToken"]["gemini_llm"][i],
            # http_options=http_options,
        ) for i in range(len(configToml["apiToken"]["gemini_llm"]))]
        self._rr_index = 0  # Round-robin index
        self._rr_count = 5  # Number of requests per client before switching
        self._rr_current_count = 0  # Current count for the active client
        print(f"Initialized GeminiAPIHandler with {len(self._client_collection)} clients.")

    async def generate_content_v1(self, contents: List[types.Content], system_prompt) -> types.GenerateContentResponse:
        # Wrapper to call the synchronous generate_content in an async way
        try:
            response = await self._client_collection[self._rr_index].aio.models.generate_content(
                model=configToml["llmChat"]["modelChat"],
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    max_output_tokens=2048,
                ),
            )
        except Exception as e:
            print(f"GenAI Error: {e}")
            return str(e)
        else:
            self._rr_current_count += 1
            if self._rr_current_count >= self._rr_count:
                self._rr_index = (self._rr_index + 1) % len(self._client_collection)
                self._rr_current_count = 0
        
        # Google GenAI SDK 主要輸出為 `response.text`
        # print(response)
        return response.text

async def main():
    api = GeminiAPIHandler()
    system_prompt = "You are a helpful assistant."
    # n = 12
    for i in range(3):
        n = i+3
        contents = types.Content(role="user", parts=[types.Part.from_text(text=f"Return the Fibonacci sequence up to the {n}th term as a comma-separated list.")])
        
        response = await api.generate_content_v1(contents, system_prompt)
        print("Fibonacci sequence:", response)
    
# test code
if __name__ == "__main__":
    asyncio.run(main())