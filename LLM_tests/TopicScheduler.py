import heapq
import random
import numpy as np
from typing import List, Optional
import ollama_api as ollama_api
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')
EMBEDDING_DIM = model.get_sentence_embedding_dimension()

# 話題任務模型
class Topic:
    def __init__(self, name: str, mood: float, engagement: float, awareness: float):
        self.name = name
        self.mood = mood
        self.engagement = engagement
        self.awareness = awareness
        # self.total_score = mood + engagement + awareness
        # self.keywords = keywords
        self.energy = 1.0
        self.level = 1  # 0: High priority (focus), 1: Low priority (background)
        self.embeddings = np.zeros((1, EMBEDDING_DIM), dtype=np.float32)
        
    @property
    def total_score(self):
        return self.mood + self.engagement + self.awareness
    
    def __lt__(self, other):
        return self.total_score > other.total_score

    def __repr__(self):
        return f"{self.name}(S={self.total_score:.2f}, E={self.energy:.2f}, L{self.level})"


class TopicScheduler:
    def __init__(self):
        self.high_priority: List[Topic] = []
        self.low_priority: List[Topic] = []
        self.last_focus: Optional[Topic] = None

    def add_topic(self, topic: Topic):
        topic.embeddings = model.encode(topic.name)
        if topic.total_score >= 2.0:
            self.high_priority.append(topic)
        else:
            self.low_priority.append(topic)

    def reply_to_topic(self):
        if not self.high_priority:
            print("😐 No topic in focus. Waiting...")
            return

        topic = self.high_priority.pop(0)
        self.last_focus = topic
        print(f"🧠 Agent replies to: {topic.name} with score {topic.total_score:.2f}")
        topic.energy -= 0.5
        topic.level = 1  # demote to low priority after speaking
        self.low_priority.append(topic)

    def roulette_promote(self):
        if not self.low_priority:
            return

        weights = [t.total_score for t in self.low_priority]
        chosen = random.choices(self.low_priority, weights=weights, k=1)[0]
        self.low_priority.remove(chosen)
        chosen.level = 0
        self.high_priority.append(chosen)
        print(f"🎲 Promoted topic: {chosen.name} to high priority")

    def semantic_promote(self, incoming_msg: str, threshold: float = 0.5):
        # for topic in list(self.low_priority):
        #     if any(kw in incoming_msg for kw in topic.keywords):
        #         self.low_priority.remove(topic)
        #         topic.level = 0
        #         self.high_priority.append(topic)
        #         print(f"🔁 Keyword reactivation: {topic.name} promoted due to message context")
        
        incoming_embedding = model.encode(incoming_msg)
        similarities = model.similarity(incoming_embedding, np.array([t.embeddings for t in self.low_priority]))[0]
        similarities = [(similarity, topic) for similarity, topic in zip(similarities, self.low_priority) if similarity > threshold]
        
        if similarities:
            similarities.sort(reverse=True, key=lambda x: x[0])
            
            top_similarity, top_topic = similarities[0]
            top_topic.level = 0
            self.high_priority.append(top_topic)
            print(f"🔁 Semantic reactivation: {top_topic.name} promoted due to message similarity ({top_similarity:.2f})")
            self.low_priority.remove(top_topic)


def simulate_willingness():
    scheduler = TopicScheduler()

    # 初始話題：可用 LLM 生成 & 評分
    topics = [
        Topic("Work Stress", mood=0.6, engagement=0.7, awareness=0.8),
        Topic("Favorite Anime", mood=0.9, engagement=0.6, awareness=0.5),
        Topic("Health", mood=0.3, engagement=0.2, awareness=0.6),
    ]

    for t in topics:
        scheduler.add_topic(t)

    print("\n--- Simulating Agent Willingness to Talk ---")
    for i in range(5):
        message = input(f"User message {i+1}: ")
        if not message:
            message = random.choice(["I'm tired today", "Did you watch the anime?", "This job is killing me"])
        scheduler.semantic_promote(message)
        if len(scheduler.high_priority) == 0:
            print("😐 No topic in focus.")
            scheduler.roulette_promote()
        
        scheduler.reply_to_topic()
        print("\nQueues:")
        print("High Priority:", scheduler.high_priority)
        print("Low  Priority:", scheduler.low_priority)
        print("\n---")

simulate_willingness()
