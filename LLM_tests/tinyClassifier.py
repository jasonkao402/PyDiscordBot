import ollama_api

model = "TinyLlama:latest"
txtpath = "subsystem_tests/chat_history/deepseek.txt"

configToml = ollama_api.configToml
# configToml["modelChat"] = model

system = {"role": "system", "content": 
    "please give a summary and determine how much awareness you should raise for the following text, output a number from 0 to 10, in json format, inside a dict with the key 'summary' with summary text, and key 'awareness' with a number, for example: {'summary':'user is walking towards me', 'awareness': 5}, if the text is not related to the user, please output {'summary':'', 'awareness': 0}"}

async def main():
    with open(txtpath, "r", encoding='utf8') as file:
        text = file.readlines()
        
    api = ollama_api.Ollama_API_Handler()
    
    for lines in text:
        lines = lines.strip()
        if lines:
            response = await api.chat(messages=[system, {"role": "user", "content": lines}], token_limit=200)
            print(response.content)
            print("\n")
        else:
            continue

if __name__ == "__main__":
    import asyncio

    asyncio.run(main())