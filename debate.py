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
    def __init__(self, name: str, api: ollama_api.OllamaAPIHandler):
        self.name = name
        self.team = Team.PRO if name == "正方" else Team.CON
        self.logger = debater_loggers[self.team]
        self.api = api
        self.arguments = []
        self.memory = []

    async def prepare_arguments(self, topic: str, num_args: int = 5):
        messages = [
            {
                "role": "user",
                "content": f'你正在參加一場辯論賽，請提供{num_args}個{("支持" if self.team == Team.PRO else "反對")}「{topic}」的論點, 論點為字串，格式使用 python list format, 範例: ["論點1", "論點2", ...]',
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
        for arg in opponent_arguments:
            messages = [
                {
                    "role": "user",
                    "content": f"你正在參加一場辯論賽，要反駁對手的論點，強度 {T} ({'0: 無所不用其極地反駁對方，1: 尋找共識'}): {arg}",
                }
            ]
            response = await self.api.chat(messages)
            response = response["message"]["content"]
            self.logger.info(f"{self.name} (T={T}) 反駁「{arg}」:\n {response}")


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
                    "content": f"你是一位裁判，請評分論點: {arg}",
                }
            ]
            response = await self.api.chat(messages)
            response = response["message"]["content"]
            scores[i] = response
        return scores


class DebateController:
    """控制辯論過程"""

    def __init__(self, topic: str, rounds: int):
        self.topic = topic
        self.rounds = rounds

    async def start_debate(self):
        logging.info(f"辯論主題: {self.topic}")
        self.api = ollama_api.OllamaAPIHandler()
        self.pro = Debater("正方", self.api)
        self.con = Debater("反方", self.api)
        self.judge = Judge(self.api)
        await self.pro.prepare_arguments(self.topic, 4)
        await self.con.prepare_arguments(self.topic, 4)

        # T_values = [-1 + 2 * (r / (self.rounds - 1)) for r in range(self.rounds)]

        # for T in T_values:
        #     logging.info(f"回合 {T_values.index(T) + 1}, T={T}")
        #     await self.pro.rebut(self.con.arguments, T)
        #     await self.con.rebut(self.pro.arguments, T)

        # pro_score, con_score = self.judge.evaluate(self.pro.arguments, self.con.arguments)
        # winner = "正方" if pro_score > con_score else "反方" if con_score > pro_score else "平手"
        # logging.info(f"最終勝者: {winner}")
        # return winner
        await self.api.close()


# 測試
if __name__ == "__main__":
    debate = DebateController("大考作文評分廢除人工閱卷批改，改由語言模型給分", rounds=3)
    asyncio.run(debate.start_debate())
    # print(f"勝者: {result}")
