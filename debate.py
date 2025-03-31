import logging
from abc import ABC, abstractmethod
from typing import List, Tuple
import asyncio
import ollama_api
# 設置 Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

pro_logger = logging.getLogger("ProDebater")
con_logger = logging.getLogger("ConDebater")
judge_logger = logging.getLogger("Judge")

pro_handler = logging.FileHandler("debate_output/debater_pro.log")
con_handler = logging.FileHandler("debate_output/debater_con.log")
judge_handler = logging.FileHandler("debate_output/judge.log")

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
pro_handler.setFormatter(formatter)
con_handler.setFormatter(formatter)
judge_handler.setFormatter(formatter)

pro_logger.addHandler(pro_handler)
con_logger.addHandler(con_handler)
judge_logger.addHandler(judge_handler)

class Debater(ABC):
    """ 抽象基底類別，代表辯論者 """
    def __init__(self, name: str, api: ollama_api.OllamaAPIHandler, logger: logging.Logger):
        self.name = name
        self.logger = logger
        self.arguments = []
        self.memory = []
        self.api = api
    
    @abstractmethod
    async def prepare_arguments(self, topic: str):
        """ 準備有利自己的論點 """
        pass
    
    @abstractmethod
    async def rebut(self, opponent_arguments: List[str], T: float):
        """ 反駁對手的論點，並提出新的證據，T 控制反駁強度 """
        pass

class ProDebater(Debater):
    """ 正方辯論者 """
    def __init__(self, name: str, api: ollama_api.OllamaAPIHandler):
        super().__init__(name, api, pro_logger)
        
    async def prepare_arguments(self, topic: str):
        messages = [{"role": "user", "content": f"請提供5個支持'{topic}'的論點"}]
        response = await self.api.chat(messages)
        response = response["message"]["content"]
        self.arguments = response.split("\n\n")
        self.logger.info(f"{self.name} 準備論點: {self.arguments}")
    
    async def rebut(self, opponent_arguments: List[str], T: float):
        for arg in opponent_arguments:
            messages = [{"role": "user", "content": f"請反駁以下論點，強度 {T} ({'-1: 無所不用其極地反駁對方，0: 平衡辯論，1: 尋找共識'}): {arg}"}]
            response = await self.api.chat(messages)
            response = response["message"]["content"]
            self.logger.info(f"{self.name} 反駁 (T={T}): {response}")

class ConDebater(Debater):
    """ 反方辯論者 """
    def __init__(self, name: str, api: ollama_api.OllamaAPIHandler):
        super().__init__(name, api, con_logger)
        
    async def prepare_arguments(self, topic: str):
        messages = [{"role": "user", "content": f"請提供5個反對'{topic}'的論點"}]
        response = await self.api.chat(messages)
        response = response["message"]["content"]
        self.arguments = response.split("\n\n")
        self.logger.info(f"{self.name} 準備論點: {self.arguments}")
    
    async def rebut(self, opponent_arguments: List[str], T: float):
        for arg in opponent_arguments:
            messages = [{"role": "user", "content": f"請反駁以下論點，強度 {T} ({'-1: 無所不用其極地反駁對方，0: 平衡辯論，1: 尋找共識'}): {arg}"}]
            response = await self.api.chat(messages)
            response = response["message"]["content"]
            self.logger.info(f"{self.name} 反駁 (T={T}): {response}")

class Judge:
    """ 裁判評分系統 """
    def __init__(self, api: ollama_api.OllamaAPIHandler):
        self.api = api
        
    def evaluate(self, pro_args: List[str], con_args: List[str]) -> Tuple[int, int]:
        """ 根據可靠度和合理程度計算得分 """
        pro_score = sum(len(arg) for arg in pro_args) * 1.0
        con_score = sum(len(arg) for arg in con_args) * 1.0
        judge_logger.info(f"裁判評分: 正方 {pro_score}, 反方 {con_score}")
        return pro_score, con_score

class DebateController:
    """ 控制辯論過程 """
    def __init__(self, topic: str, rounds: int):
        self.topic = topic
        self.rounds = rounds
        
        
    async def start_debate(self):
        logging.info(f"辯論主題: {self.topic}")
        self.api = ollama_api.OllamaAPIHandler()
        self.pro = ProDebater("正方", self.api)
        self.con = ConDebater("反方", self.api)
        self.judge = Judge(self.api)
        await self.pro.prepare_arguments(self.topic)
        await self.con.prepare_arguments(self.topic)

        T_values = [-1 + 2 * (r / (self.rounds - 1)) for r in range(self.rounds)]
        
        for T in T_values:
            logging.info(f"回合 {T_values.index(T) + 1}, T={T}")
            await self.pro.rebut(self.con.arguments, T)
            await self.con.rebut(self.pro.arguments, T)
        
        # pro_score, con_score = self.judge.evaluate(self.pro.arguments, self.con.arguments)
        # winner = "正方" if pro_score > con_score else "反方" if con_score > pro_score else "平手"
        # logging.info(f"最終勝者: {winner}")
        # return winner
        await self.api.close()

# 測試
if __name__ == "__main__":
    debate = DebateController("人工智慧應該被廣泛應用", rounds=2)
    asyncio.run(debate.start_debate())
    # print(f"勝者: {result}")
