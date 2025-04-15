import json
import re
import tqdm
import jieba
import numpy as np
from keybert import KeyBERT
from sentence_transformers import SentenceTransformer
from sklearn.cluster import DBSCAN
from sklearn.feature_extraction.text import CountVectorizer

hist_path = "subsystem_tests/chat_history/華山論劍.json"
# hist_path = "subsystem_tests/chat_history/deepseek.txt"
# model_name = "distiluse-base-multilingual-cased-v1"
embedder = "paraphrase-multilingual-MiniLM-L12-v2"

embedder = SentenceTransformer(embedder, device="cuda:0")
kw_model = KeyBERT(model=embedder)

ban_msgs_regex = [
    r"https?://[^\s]+",  # Match https links
    r"(<a?)?:\w+:(\d{18}>)?"  # Match Discord emojis
    # "\\d{4}-\\d{2}-\\d{2}", # Match dates
]

def filter_msg(msg):
    # Filter messages (raw messages)
    if msg == "":
        return msg
    msg = re.sub(r"\n+", " ", msg)  # Replace newlines with spaces
    for regex in ban_msgs_regex:
        msg = re.sub(regex, "", msg)
    msg = re.sub(r" +", " ", msg)  # Replace multiple spaces with a single space
    return msg.strip()

# Read JSON file
with open(hist_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

authors = set()
messages = []
for i in data['messages']:
    content = i['content']
    author = int(i['author']['id'])
    content = filter_msg(content)
    authors.add(author)
    if content == "":
        continue
    messages.append(content)
# messages = []
# with open(hist_path, 'r', encoding='utf-8') as f:
#     # data = json.load(f)
#     lines = f.readlines()

# for line in lines:
#     line = line.strip()
#     content = filter_msg(line)
#     if content == "":
#         continue
#     messages.append(content)

# ✦ 對話轉向量
embeddings = embedder.encode(messages, show_progress_bar=True, convert_to_tensor=True)
embeddings = np.array(embeddings.cpu())  # Convert to numpy array
# ✦ DBSCAN 分群參數
# eps: 範圍半徑（越大群越粗）
# min_samples: 每群最少點數（建議 2~3）
clustering = DBSCAN(eps=0.3, min_samples=2, metric='cosine')
labels = clustering.fit_predict(embeddings)

# ✦ 整理分群結果
n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
clusters = [[] for _ in range(n_clusters)]
noise = []

for sentence, label in zip(messages, labels):
    if label == -1:
        noise.append(sentence)
    else:
        clusters[label].append(sentence)
        
print(f"分群數量：{n_clusters}")
print(f"離群數量：{len(noise)}")
# ✦ 顯示分群結果
for i, group in enumerate(clusters):
    print(f"\n--- 🗂️ 主題段落 {i+1} ---")
    print(f"對話：{len(group)}")
    for line in group[:5]:
        print(f"  ➤ {line}")

    summary = " / ".join(group[:2]) + ("..." if len(group) > 2 else "")
    print(f"✦ 總結：{summary}")

    tokens = jieba.cut(" ".join(group), cut_all=False)
    tokens = list(set(tokens))  # Remove duplicates
    if tokens:
        keywords = kw_model.extract_keywords(" ".join(tokens), top_n=5)
        print(f"✦ 關鍵字：{', '.join([k for k, _ in keywords])}")
    else:
        print("✦ 關鍵字：無法提取關鍵字（無有效文本）")
    # print(f"✦ 關鍵字：{', '.join([k for k, _ in keywords])}")

# ✦ 顯示離群點（optional）
# if noise:
#     print(f"\n--- ❗ 離群句（未歸類） ---")
#     for sentence in noise:
#         print(f"  ➤ {sentence}")