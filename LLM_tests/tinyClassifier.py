import ollama_api

model = "TinyLlama:latest"
txtpath = "subsystem_tests/chat_history/deepseek.txt"

with open(txtpath, "r") as file:
    text = file.readlines()

api = ollama_api.OllamaAPIHandler()
configToml = ollama_api.configToml
configToml["modelChat"] = model

system = {"role": "system", "content": "please determine how much awareness you should raise for the following text, output a number from 1 to 10, in json format"}

for lines in text:
    lines = lines.strip()
    if lines:
        response = api.chat(messages=[{"role": "user", "content": lines}])
        print(response["message"]["content"])
        print("\n")
    else:
        continue