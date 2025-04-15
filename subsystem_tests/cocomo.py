import heapq
import random

# 任務模型
class Task:
    def __init__(self, name, reward, energy):
        self.name = name
        self.reward = reward  # 由 RL 或使用者評價給出
        self.energy = energy  # 決定 fade out 速度
        self.level = 2        # 初始在低優先潛意識 queue (2: unconscious)
        self.time = 0         # 用來模擬 aging

    def __lt__(self, other):
        return self.reward > other.reward  # 高 reward 排前面

    def __repr__(self):
        return f"{self.name}(L{self.level}, R{self.reward:.2f}, E{self.energy:.2f})"

# CoCoMo MFQ 調度器
class CoCoMoMFQ:
    def __init__(self, levels=3):
        self.queues = [[] for _ in range(levels)]  # Q0: high, Q1: mid, Q2: low
        self.max_level = levels - 1

    def add_task(self, task: Task):
        self.queues[task.level].append(task)

    def interrupt(self, task: Task):
        print(f"\U0001f514 Interrupt! {task.name} promoted to conscious (Q0)")
        # 確保從原先 queue 中移除
        self.queues[task.level].remove(task)
        task.level = 0
        self.queues[0].append(task)

    def decay_energy(self):
        for lvl in range(len(self.queues)):
            for task in list(self.queues[lvl]):
                task.energy -= random.uniform(0.1, 0.3)
                if task.energy <= 0 and task.level < self.max_level:
                    print(f"\U0001f634 {task.name} faded to Q{task.level + 1}")
                    self.queues[lvl].remove(task)
                    task.level += 1
                    self.queues[task.level].append(task)

    def run_cycle(self):
        for lvl in range(len(self.queues)):
            if self.queues[lvl]:
                task = max(self.queues[lvl], key=lambda t: t.reward)
                self.queues[lvl].remove(task)
                print(f"\U0001f9e0 Running: {task}")
                task.energy -= 0.5
                if task.energy > 0:
                    task.time += 1
                    if task.time > 2 and task.level < self.max_level:
                        print(f"\U0001f53b Demote {task.name} to Q{task.level+1}")
                        task.level += 1
                    self.queues[task.level].append(task)
                return
        print("\U0001f610 No tasks to run.")

# 範例任務模擬
def simulate_mfq():
    mfq = CoCoMoMFQ()

    tasks = [
        Task("Check Email", reward=0.3, energy=1.5),
        Task("Sense Emergency", reward=0.9, energy=1.0),
        Task("Daydream", reward=0.1, energy=1.2),
        Task("Help User Emotionally", reward=0.8, energy=1.5),
        Task("Yawn", reward=0.2, energy=1.1),
        Task("Take a Break", reward=0.4, energy=1.7),
    ]

    for t in tasks:
        mfq.add_task(t)

    print("\n--- Initial Cycle ---")
    for i in range(len(tasks)):
        if random.random() < 0.5:
            mfq.interrupt(random.choice(tasks))
        mfq.run_cycle()
        mfq.decay_energy()
        print("Queues:", *mfq.queues, sep='\n')
        print()

simulate_mfq()
