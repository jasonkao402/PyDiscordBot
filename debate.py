import asyncio
import json
import logging
from abc import ABC
from enum import Enum
from typing import List, Tuple
import ollama_api

class Team(Enum):
    PRO = 1
    CON = 2


# 設置 Logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
debater_loggers = {
    Team.PRO: logging.getLogger("ProDebater"),
    Team.CON: logging.getLogger("ConDebater"),
}
judge_logger = logging.getLogger("Judge")

debate_handlers = {
    Team.PRO: logging.FileHandler(
        "debate_output/debater_pro.log", mode="w", encoding="utf-8"
    ),
    Team.CON: logging.FileHandler(
        "debate_output/debater_con.log", mode="w", encoding="utf-8"
    ),
}
judge_handler = logging.FileHandler(
    "debate_output/judge.log", mode="w", encoding="utf-8"
)

formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

for logger, handler in zip(debater_loggers.values(), debate_handlers.values()):
    handler.setFormatter(formatter)
    logger.addHandler(handler)

judge_handler.setFormatter(formatter)
judge_logger.addHandler(judge_handler)


class Debater(ABC):
    def __init__(self, name: str, topic, api: ollama_api.OllamaAPIHandler):
        self.name = name
        self.topic = topic
        self.team = Team.PRO if name == "正方" else Team.CON
        self.logger = debater_loggers[self.team]
        self.api = api
        self.arguments = []
        self.memory = []

    async def prepare_arguments(self, num_args: int = 5):
        messages = [
            {
                "role": "user",
                "content": f'你正在參加一場辯論賽，請提供{num_args}個{("支持" if self.team == Team.PRO else "反對")}「{self.topic}」的論點, 論點為字串，格式使用 python list format, 範例: ["論點1", "論點2", ...]',
            }
        ]
        response = await self.api.chat(messages)
        response = response["message"]["content"]
        # print(response)
        response = response[response.find("[") : response.find("]") + 1]
        parsed_response = json.loads(response)
        self.arguments.extend(parsed_response)
        for i, arg in enumerate(self.arguments, 1):
            self.logger.info(f"{self.name} 準備論點 {i:2d}: {arg}")

    async def rebut(self, opponent_arguments: List[str], T: float):
        T = round(T, 3)
        for arg in opponent_arguments:
            messages = [
                {
                    "role": "assistant",
                    "content": f'我{("支持" if self.team == Team.PRO else "反對")}「{self.topic}」，因為' + ', '.join(self.arguments),
                },
                {
                    "role": "user",
                    "content": f'你正在參加一場辯論賽，你{("支持" if self.team == Team.PRO else "反對")}「{self.topic}」，要回饋對手的論點: {arg}\n請依照指示的對抗強度(範圍0~1, 0: 融合對方論點，尋找共識平衡點, 1: 儘可能質疑對方可行性與可靠性)回饋，目前對抗強度={T}',
                }
            ]
            response = await self.api.chat(messages)
            response = response["message"]["content"]
            self.memory.append(response)
            self.logger.info(f"{self.name} (T={T}) 反駁「{arg}」: {response}")


class Judge:
    """裁判評分系統"""

    def __init__(self, api: ollama_api.OllamaAPIHandler):
        self.api = api

    async def evaluate(self, args: List[str]):
        """根據可靠度和合理程度計算得分"""
        scores = [0] * len(args)
        for i, arg in enumerate(args):
            messages = [
                {
                    "role": "user",
                    "content": f"你是一位辯論賽評審，請依照markdown格式寫評論，先客觀分析選手應答於「# 客觀分析」下方，根據你的分析，對於應答內容的可靠度和有效反駁程度，計算選手得分於「# 評審給分」下方，格式為單行兩個數字，範圍0~10，以逗號分隔，例如: 7,6\n選手回應:{arg}",
                }
            ]
            response = await self.api.chat(messages)
            response = response["message"]["content"]
            parsed_analysis = response[response.find("# 客觀分析") + 7 : response.find("# 評審給分")]
            parsed_score = response[response.find("# 評審給分") + 7 :]
            judge_logger.info(f"客觀分析 {i:2d}: {parsed_analysis}")
            judge_logger.info(f"評審給分 {i:2d}: {parsed_score}")
            # scores[i] = response
        return scores


class DebateController:
    """控制辯論過程"""

    def __init__(self, topic: str, rounds: int, prepare: int = 3):
        self.topic = topic
        self.rounds = rounds
        self.prepare = prepare
        
    async def start_debate(self):
        logging.info(f"辯論主題: {self.topic}")
        self.api = ollama_api.OllamaAPIHandler()
        self.pro = Debater("正方", self.topic, self.api)
        self.con = Debater("反方", self.topic, self.api)
        self.judge = Judge(self.api)
        await self.pro.prepare_arguments(self.prepare)
        await self.con.prepare_arguments(self.prepare)

        # 0.9 to 0 in
        T_start = 0.9
        T_delta = 2
        rounds = range(self.rounds)

        for i in rounds:
            T = T_start / T_delta ** i
            logging.info(f"回合 {i+1}/{self.rounds}, T={T}")
            await self.pro.rebut(self.con.arguments, T)
            await self.con.rebut(self.pro.arguments, T)

            pro_score = await self.judge.evaluate(self.pro.memory)
            con_score = await self.judge.evaluate(self.con.memory)
            self.pro.memory = []
            self.con.memory = []
        # winner = "正方" if pro_score > con_score else "反方" if con_score > pro_score else "平手"
        # logging.info(f"最終勝者: {winner}")
        # return winner
        await self.api.close()


# 測試
if __name__ == "__main__":
    # topic = "台灣政府應在 2025 年前淘汰所有核電廠"
    topic = "遊戲中上不去分完全歸因於玩家自身"
    debate = DebateController(topic, rounds=3, prepare=2)
    asyncio.run(debate.start_debate())
    # print(f"勝者: {result}")
