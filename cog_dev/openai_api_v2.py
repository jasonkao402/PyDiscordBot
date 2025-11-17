from time import strftime
from cog_dev.database_test import PersonaDatabase, Persona
from cog.utilFunc import replyDict
import asyncio
import openai
from collections import deque
from config_loader import configToml

N = 16
oai_client = openai.AsyncClient(
    base_url = "http://127.0.0.1:7861/v1",
    api_key = configToml['apiToken']['gcli2api'],
)

async def llm_chat_v3(messages):
    try:
        completion = await oai_client.chat.completions.create(
            model="gemini-2.5-pro",
            messages=messages,
            temperature=0.7,
            max_tokens=4096,
            # n=1,
            # stop=None,
        )
    except openai.APIError as e:
        print(f"OpenAI API error: {e}")
        return replyDict(role='error', content=e)
    print(completion.usage)
    return replyDict(role = completion.choices[0].message.role, content = completion.choices[0].message.content)

async def main():
    db = PersonaDatabase("llm_character_cards.db")
    _persona = db.get_persona_no_check(3)
    userName = 'jason'
    persona_session_memory = deque(maxlen=N)
    while True:
        content = input('You: ')
        if content.lower() in ['exit', 'quit']:
            break
        try:
            # prompt = replyDict('user'  , f'jasonZzz said {prompt}', 'jasonZzz')
            prompt = replyDict('user', f'{userName} said {content}', userName)
            setupmsg = replyDict('system', f'{_persona.content} 現在是{strftime("%Y-%m-%d %H:%M %a")}', 'system')
            
            reply  = await llm_chat_v3([*persona_session_memory, setupmsg.asdict, prompt.asdict])
            assert reply.role != 'error'
            
            print(f'{_persona.persona}: {reply.content}')
        except TimeoutError:
            print('timeout')
        except AssertionError:
            # if embed.vector[0] == 0:
                # print(f'Embed error:\n{embed.text}')
            if reply.role == 'error':
                # reply2 = '\n'.join((f'{k}: {v}' for k, v in reply.content.items()))
                print(f'Reply error:\n{reply.content}')
        else:
            persona_session_memory.append(prompt.asdict)
            persona_session_memory.append(reply.asdict)

asyncio.run(main())