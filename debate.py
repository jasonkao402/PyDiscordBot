import asyncio
import json
import logging
from abc import ABC
from enum import Enum
from typing import List
import ollama_api
from flask import Flask, render_template
from flask_socketio import SocketIO
import asyncio


class Team(Enum):
    PRO = 1
    CON = 2
    JUDGE = 3


# 設置 Logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
debater_loggers = {
    Team.PRO: logging.getLogger("ProDebater"),
    Team.CON: logging.getLogger("ConDebater"),
    Team.JUDGE: logging.getLogger("Judge"),
}
# judge_logger = logging.getLogger("Judge")

debate_handlers = {
    Team.PRO: logging.FileHandler(
        "debate_output/debater_pro.log", mode="w", encoding="utf-8"
    ),
    Team.CON: logging.FileHandler(
        "debate_output/debater_con.log", mode="w", encoding="utf-8"
    ),
    Team.JUDGE: logging.FileHandler(
        "debate_output/judge.log", mode="w", encoding="utf-8"
    ),
}
# judge_handler = logging.FileHandler(
#     "debate_output/judge.log", mode="w", encoding="utf-8"
# )

formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

for logger, handler in zip(debater_loggers.values(), debate_handlers.values()):
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# judge_handler.setFormatter(formatter)
# judge_logger.addHandler(judge_handler)
app = Flask(__name__)
socketio = SocketIO(app, async_mode="threading")

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

    async def rebut(self, opponent_argument: str, T: float):
        T = round(T, 3)
        messages = [
            {
                "role": "assistant",
                "content": f'我{("支持" if self.team == Team.PRO else "反對")}「{self.topic}」，因為'
                + ", ".join(self.arguments),
            },
            {
                "role": "user",
                "content": f'你正在參加一場辯論賽，你{("支持" if self.team == Team.PRO else "反對")}「{self.topic}」，要回饋對手的論點: {opponent_argument}\n請依照指示的對抗強度(範圍0~1, 0: 融合對方論點，尋找共識平衡點, 1: 儘可能質疑對方可行性與可靠性)回饋，目前對抗強度={T}',
            },
        ]
        response = await self.api.chat(messages)
        response = response["message"]["content"]
        self.memory.append(response)
        self.logger.info(f"{self.name} (T={T}) 反駁「{opponent_argument}」: {response}")


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
                    "content": f"你是一位辯論賽評審，請先客觀分析選手應答，且根據你對於應答內容的分析，分別給出兩個整數(範圍0~10)，代表選手應答內容之可靠度和有效反駁程度\n選手回應:{arg}",
                }
            ]
            
            response = await self.api.chat(messages)
            jsonPrompt = [
                {
                    "role": "system",
                    "content": f"given a review of a debate response from a judge, please extract the score and analysis from the review. The review is in Chinese. The json should contain the following fields: 'analysis', 'credibility', 'validity', e.g.:\n{{\"analysis\": \"\", \"credibility\": 0, \"validity\": 0}}",
                },
                {
                    "role": "user",
                    "content": response["message"]["content"],
                },
            ]
            json_response = await self.api.chat(jsonPrompt)
            json_response = json_response["message"]["content"]
            print(json_response)
            # json_parsed_response = json.loads(json_response)
            # print(json_parsed_response)
            # response = response["message"]["content"]
            # parsed_analysis = response[
                # response.find("# 客觀分析") + 7 : response.find("# 評審給分")
            # ]
            # parsed_score = response[response.find("# 評審給分") + 7 :]
            # judge_logger.info(f"客觀分析 {i:2d}: {parsed_analysis}")
            # judge_logger.info(f"評審給分 {i:2d}: {parsed_score}")
            # scores[i] = response
        return scores


class DebateController:
    """控制辯論過程"""

    def __init__(self, topic: str, rounds: int, prepare: int):
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
        for arg in self.pro.arguments:
            socketio.emit(
                "update_pro", {"text": arg}
            )
        for arg in self.con.arguments:
            socketio.emit(
                "update_con", {"text": arg}
            )
        T_start = 0.9
        T_delta = 2
        rounds = range(self.rounds)

        for i in rounds:
            T = T_start / T_delta**i
            logging.info(f"回合 {i+1}/{self.rounds}, T={T}")
            for arg in self.pro.arguments:
                await self.pro.rebut(arg, T)
                socketio.emit(
                    "update_pro", {"text": self.pro.memory[-1]}
                )
            for arg in self.con.arguments:
                await self.con.rebut(arg, T)
                socketio.emit(
                    "update_con", {"text": self.con.memory[-1]}
                )
                
            # await self.pro.rebut(self.con.arguments, T)
            # await self.con.rebut(self.pro.arguments, T)

            pro_score = await self.judge.evaluate(self.pro.memory)
            con_score = await self.judge.evaluate(self.con.memory)
            self.pro.memory = []
            self.con.memory = []
        # winner = "正方" if pro_score > con_score else "反方" if con_score > pro_score else "平手"
        # logging.info(f"最終勝者: {winner}")
        # return winner
        await self.api.close()


@app.route("/")
def index():
    return render_template("index.html")

@socketio.on("start_debate")
def handle_start_debate():
    topic = "台灣政府應在 2025 年前淘汰所有核電廠"
    rounds = 3
    prepare = 2
    debate = DebateController(topic, rounds=rounds, prepare=prepare)
    asyncio.run(debate.start_debate())
    
# 測試
if __name__ == "__main__":
    socketio.run(app, debug=True, port=5000)
    # topic = "台灣政府應在 2025 年前淘汰所有核電廠"
    # topic = "遊戲中上不去分完全歸因於玩家自身"
    # debate = DebateController(topic, rounds=3, prepare=2)
    # asyncio.run(debate.start_debate())
    # print(f"勝者: {result}")
