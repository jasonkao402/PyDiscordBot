import discord

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

import openai
import time
#from openai.embeddings_utils import cosine_similarity
import PyPDF2
import numpy as np

openai.api_key = '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'
messages = []
a = []
settings = []

pdf_file = open("trpg/GreatMind.pdf", "rb")
pdf_reader = PyPDF2.PdfFileReader(pdf_file)

# Extract paragraphs from PDF file
pdf_content = ''
for page in range(pdf_reader.getNumPages()):
    pdf_content += pdf_reader.getPage(page).extractText()

paragraphs = pdf_content.split('。')

chunk_size = 6
paragraphs_chunks = [paragraphs[i:i+chunk_size] for i in range(0, len(paragraphs), chunk_size)]

# Vectorize paragraphs
embeddings = []
for chunk in paragraphs_chunks:
    text = "。".join(chunk)
    embedding = openai.Embedding.create(
        model = "text-embedding-ada-002",
        input = text.strip()
    )
    embeddings.append(embedding['data'][0]["embedding"])
    time.sleep(1)

async def openai_message(a):
    try:
        completion = openai.ChatCompletion.create(
            model='gpt-3.5-turbo',
            messages=a,
            temperature = 0.5,
        )
        print("Real", a)
        return completion['choices'][0]['message']['content']  # remove leading/trailing whitespaces
    except openai.error.OpenAIError as error:
        print(error)
        return f"Sorry, I encountered an error with status {error.status} - {error.message}. I don't know how to respond."

@client.event
async def on_ready():
    print(f'Logged in as {client.user.name}')


@client.event
async def on_message(message):
    global messages
    print(1)
    print(message.content)
    if message.content =='test':
        print(2)
        await message.channel.send('你的BOT已上線')
    if message.content =='':
        print('e04')
    if message.content == '!shutdown' and message.author.id == 316141566173642752:
        print(888)
        await message.channel.send('退休啦!')
        await client.close()
    if message.author.bot or not message.content.startswith('助手'): 
        print(2.5)
        return
    print('3')
    prompt = message.content[3:].strip()
    messages.append({
        'role': 'user',
        'content': prompt
    })

    prompt_embedding = openai.Embedding.create(model = 'text-embedding-ada-002', input = prompt)['data'][0]['embedding']
    
    similarities = []
    for embedding in embeddings:
        similarity = np.dot(embedding, prompt_embedding) / (np.linalg.norm(embedding) * np.linalg.norm(prompt_embedding))
        similarities.append(similarity)

    # Get indices of top n most similar paragraphs
    n = 3  # Number of top similar paragraphs to return
    top_indices = np.argsort(similarities)[-n:]

    # Get the corresponding paragraphs and concatenate them into a single string
    relevant_text = ""
    for i in top_indices:
        relevant_text = relevant_text + '。'.join(paragraphs_chunks[i])

    
    settings = {
            'role': 'system',
            'content': '"你是一個描述故事的旁白，請根據下方文本，回答使用者的問題"' + relevant_text
        }
    
    messages= [settings] + messages

    response = await openai_message(messages)
    print('6')
    #刪除設定，回到原本的訊息紀錄
    messages.pop(0)

    messages.append({
        'role': 'assistant',
        'content': response
    })
    while len(messages) > 10:
        messages.pop(0)
    
    if not response:
        await message.channel.send("empty response")
        return
    await message.channel.send(response)

client.run('...')

