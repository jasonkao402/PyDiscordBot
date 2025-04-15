import asyncio
import json
import logging
from abc import ABC
from enum import Enum
from typing import List
import ollama_api as ollama_api
from flask import Flask, render_template
from flask_socketio import SocketIO
import asyncio
import numpy as np

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
    def __init__(self, name: str, topic, api: ollama_api.Ollama_API_Handler):
        self.name = name
        self.topic = topic
        self.team = Team.PRO if name == "正方" else Team.CON
        self.logger = debater_loggers[self.team]
        self.api = api
        self.round_score = 0
        self.total_score = 0
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
        response = response.content
        # print(response)
        response = response[response.find("[") : response.rfind("]")+1]
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
                "content": f'我{("反對" if self.team == Team.PRO else "支持")}「{self.topic}」，因為'
                + opponent_argument,
            },
            {
                "role": "user",
                "content": f'你正在參加一場辯論賽，要回饋對手的論點，請依照指示的對抗強度(範圍0~1, 0: 融合對方論點，尋找共識平衡點, 1: 質疑對方可行性與可靠性)回饋，目前對抗強度={T}',
            },
        ]
        response = await self.api.chat(messages)
        response = response.content
        self.memory.append(response)
        self.logger.info(f"{self.name} (T={T}) 反駁「{opponent_argument}」: {response}")


class Judge:
    """裁判評分系統"""

    def __init__(self, api: ollama_api.Ollama_API_Handler):
        self.api = api

    async def evaluate(self, arg: str):
        """根據可靠度和合理程度計算得分"""
        messages = [
            {
                "role": "user",
                "content": f"你是一位辯論賽評審，請先客觀分析選手應答，且根據你對於應答內容的分析，分別給出兩個整數(範圍0~10)，代表選手應答內容之可靠度和有效反駁程度\n選手回應:{arg}",
            }
        ]
        response_step1 = await self.api.chat(messages)
        jsonPrompt = [
            {
                "role": "system",
                "content": "given a review of a debate response from a judge, please extract the score and analysis from the review. The review is in Chinese. The json should contain the following fields: 'analysis', 'credibility', 'validity', e.g.:\n{\"analysis\": \"string\", \"credibility\": int, \"validity\": int}",
            },
            {
                "role": "user",
                "content": response_step1.content,
            },
        ]
        response_step2 = await self.api.chat(jsonPrompt)
        response_step2 = response_step2.content
        # print(json_response)
        parsed_response = response_step2[response_step2.find("```json") + 7 : response_step2.rfind("```")]
        print(parsed_response)
        json_response = json.loads(parsed_response)
            
        return json_response["analysis"], (json_response["credibility"], json_response["validity"])


class DebateController:
    """控制辯論過程"""

    def __init__(self, topic: str, rounds: int, prepare: int):
        self.topic = topic
        self.rounds = rounds
        self.prepare = prepare

    async def start_debate(self):
        logging.info(f"辯論主題: {self.topic}")
        self.api = ollama_api.Ollama_API_Handler()
        self.pro = Debater("正方", self.topic, self.api)
        self.con = Debater("反方", self.topic, self.api)
        self.judge = Judge(self.api)
        socketio.emit(
            "update_pro", {"text": "正方準備論點中... (請稍候)"}
        )
        socketio.emit(
            "update_con", {"text": "反方準備論點中... (請稍候)"}
        )
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
        # rounds = 

        for i in range(self.rounds):
            T = T_start / T_delta**i
            logging.info(f"回合 {i+1}/{self.rounds}, T={T}")
            socketio.emit(
                "update_judge", {"text": f"回合 {i+1}/{self.rounds}, T={T}"}
            )
            socketio.emit(
                "update_pro", {"text": f"回合 {i+1}/{self.rounds}"}
            )
            socketio.emit(
                "update_con", {"text": f"回合 {i+1}/{self.rounds}"}
            )
            for j, arg in enumerate(self.con.arguments):
                await self.pro.rebut(arg, T)
                socketio.emit(
                    "update_pro", {"text": f"論點 {j+1}/{self.prepare}\n{self.pro.memory[-1]}"}
                )
            for j, arg in enumerate(self.pro.arguments):
                await self.con.rebut(arg, T)
                socketio.emit(
                    "update_con", {"text": f"論點 {j+1}/{self.prepare}\n{self.con.memory[-1]}"}
                )
                
            # scores = np.zeros((len(self.pro.memory), 3))
            for team in [self.pro, self.con]:
                scores = np.zeros((len(team.memory), 3))
                for i, rebut in enumerate(team.memory):
                    analysis, (credibility, validity) = await self.judge.evaluate(rebut)
                    scores[i] = (credibility, validity, credibility * validity)
                    socketio.emit(
                        "update_judge", {"text": f"{team.name} {i+1}/{len(team.memory)}: {credibility}, {validity}, {analysis}"}
                    )
                team.round_score = np.sum(scores[:, 2])
                team.memory = []
                
            if self.pro.round_score > self.con.round_score:
                self.pro.total_score += 1
                socketio.emit(
                    "update_judge", {"text": f"正方: {self.pro.round_score}, 反方: {self.con.round_score}, 正方勝"}
                )
            elif self.pro.round_score < self.con.round_score:
                self.con.total_score += 1
                socketio.emit(
                    "update_judge", {"text": f"正方: {self.pro.round_score}, 反方: {self.con.round_score}, 反方勝"}
                )
            else:
                socketio.emit(
                    "update_judge", {"text": f"正方: {self.pro.round_score}, 反方: {self.con.round_score}, 平手"}
                )
        if self.pro.total_score > self.con.total_score:
            result = "正方勝"
        elif self.pro.total_score < self.con.total_score:
            result = "反方勝"
        else:
            result = "平手"
        socketio.emit(
            "update_judge", {"text": f"最終結果: {result}"}
        )
        logging.info(f"最終結果: {result}")
        await self.api.close()


@app.route("/")
def index():
    return render_template("index.html")

# @app.route("/api/end_debate", methods=["POST"])
# def user_exit():
    # data = request.get_json()
    # user_id = data.get("user_id")
    # print(f"使用者 {user_id} 離開頁面 (via Beacon)")
    # return '', 204

@socketio.on('start_debate')
def handle_start_debate(data):
    topic = data['topic']
    rounds = data['rounds']
    prepare_amount = data['prepare_amount']
    debate = DebateController(topic, rounds, prepare_amount)
    asyncio.run(debate.start_debate())
    
# 測試
if __name__ == "__main__":
    socketio.run(app, debug=True, port=5000)
    # topic = "台灣政府應在 2025 年前淘汰所有核電廠"
    # topic = "遊戲中上不去分完全歸因於玩家自身"
    # debate = DebateController(topic, rounds=3, prepare=2)
    # asyncio.run(debate.start_debate())
    # print(f"勝者: {result}")
