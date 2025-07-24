import asyncio
import json
from typing import List
import ollama
from ollama import AsyncClient, ChatResponse
from ollama_api import load_config, replyDict
import asyncio
import numpy as np
from datetime import datetime, timedelta, timezone

# from pytz import timezone

TIME_ZONE = timezone(timedelta(hours=8), name="Asia/Taipei")


class Event:
    def __init__(
        self,
        start_time: datetime,
        end_time: datetime,
        what_to_do: str,
        interaction_target: str,
    ):
        self.start_time = start_time
        self.end_time = end_time
        self.what_to_do = what_to_do
        self.interaction_target = interaction_target

    @property
    def duration(self):
        return self.end_time - self.start_time

    def __repr__(self):
        return f"Event({self.start_time}, {self.end_time}, {self.what_to_do}, {self.interaction_target})"

    def __str__(self):
        return f"{self.start_time.strftime('%H:%M')}→{self.end_time.strftime('%H:%M')}: {self.what_to_do} (Target: {self.interaction_target})"


def list_events(events: List[Event]):
    """將事件列表轉換為字符串格式"""
    return "\n".join(str(event) for event in events)


class ScheduleManager:
    def __init__(self):
        self.config = load_config()
        self.api = AsyncClient(self.config["linkBase"])
        self.today_schedule_text = ""
        self.today_todo_list: List[Event] = []

        self.yesterday_schedule_text = ""
        self.yesterday_todo_list: List[Event] = []

        self.name = ""
        self.personality = ""
        self.behavior = ""
        self.start_time = datetime.now(TIME_ZONE)
        self.internal_time = datetime.now(TIME_ZONE)
        self.schedule_doing_update_interval = 300

    def initialize(
        self,
        name: str = "伊莉亞",
        # personality: str = "懂得享受人生的攝影師女孩",
        # behavior: str = "喜歡到處拍照，做白日夢",
        personality: str = "熟悉日本名古屋美食和景點的攝影師女孩",
        behavior: str = "擅長規劃旅遊行程",
        interval: int = 600,
    ):
        """初始化日程系統"""
        self.name = name
        self.behavior = behavior
        self.schedule_doing_update_interval = interval
        self.personality = personality
        self.start_time = datetime.now(TIME_ZONE)
        self.internal_time = datetime.now(TIME_ZONE)

    def build_schedule_prompt(self, target_date: datetime):
        """構建日程生成prompt"""
        target_date = target_date or self.internal_time
        date_str = target_date.strftime("%Y-%m-%d")
        weekday = target_date.strftime("%A")

        prompt = f"You are {self.name}, {self.personality}, {self.behavior}."
        if self.yesterday_schedule_text:
            prompt += f"Your plan yesterday was: {self.yesterday_schedule_text}\n"
        prompt += f"Please generate the schedule for {date_str} ({weekday}), which is today, based on your personal traits, habits, and yesterday's plan.\n"
        prompt += "Plan your schedule, including what you do throughout the day, from waking up to sleeping, be specific, detailed, and precise to each hour (%H:%M).\n"
        prompt += "Remember to include the start time and end time. Include tools/appliances as interaction_target if they’re central to the activity.\n"
        prompt += "Please provide me today's schedule in json format with four following fields: start_time, end_time, what_to_do, and interaction_target. Make it realistic, not exaggerated, from waking up to sleeping, and do not output any other content:"

        return prompt

    def get_task_at(self, reference_time: datetime = None):
        """獲取當前活動"""
        reference_time = reference_time or self.internal_time
        print(f"reference_time: {reference_time}")
        # parsed_schedule = self.parse_schedule_text(self.today_schedule_text)
        for item in self.today_todo_list:
            start = item.start_time
            end = item.end_time
            if start <= reference_time < end:
                return item
        return Event(
            start_time=reference_time,
            end_time=reference_time + timedelta(minutes=30),
            what_to_do="放鬆休息睡個覺",
            interaction_target="自己",
        )

    def get_task_in_interval(
        self, range_start: datetime, range_end: datetime
    ) -> List[Event]:
        """獲取在指定時間範圍內的任務"""
        tasks = []
        for event in self.today_todo_list:
            if event.start_time <= range_end and event.end_time >= range_start:
                tasks.append(event)

        return tasks

    def build_current_task_prompt(
        self, reference_time: datetime, mind_thinking: str = ""
    ):
        """構建當前狀態prompt"""
        reference_time = reference_time or self.internal_time
        now_time = reference_time.strftime("%H:%M")
        # range of recall
        look_back, look_forward = timedelta(hours=2), timedelta(hours=2)
        prev_doing = self.get_task_in_interval(
            reference_time - look_back, reference_time
        )
        next_doing = self.get_task_in_interval(
            reference_time, reference_time + look_forward
        )
        prompt = f"你是{self.name}，{self.personality}，{self.behavior}\n"

        if prev_doing:
            time_diff = reference_time - prev_doing[-1].start_time
            prev_doing = list_events(prev_doing[1:])
            prev_doing = f"你之前完成的事情是：{prev_doing}，從之前到現在已經過去了 {time_diff.seconds // 60} 分鐘了，\n"
            print(f"previous doing: {prev_doing}")
            prompt += prev_doing

        if len(next_doing) > 1:
            time_diff = next_doing[1].start_time - reference_time
            next_doing = list_events(next_doing)
            next_doing = f"你接下來要做的事情是：{next_doing}，從現在到接下來的事情還有 {time_diff.seconds // 60} 分鐘，\n"
            print(f"next doing: {next_doing}")
            prompt += next_doing

        prompt += f"當前時間：{reference_time.strftime('%H:%M')}, 當前活動：{self.get_task_at(reference_time)}"
        if mind_thinking:
            prompt += f"你在想：{mind_thinking}，\n"
        prompt += (
            f"結合你的個人特點和行為習慣，具體一些，詳細一些，考慮你今天的安排和想法"
        )
        prompt += (
            f"直接返回你現在{now_time}在做的事情，注意是當前時間，不要輸出其他內容:"
        )
        return prompt

    def parse_schedule_text(self, schedule_text: str) -> List[Event]:
        """解析日程文本"""
        today_date = self.internal_time.date()

        # print(parsed_response)
        json_response = json.loads(schedule_text)
        schedule_list = []
        checklist = ["start_time", "end_time", "what_to_do", "interaction_target"]
        for schedule in json_response["schedule"]:
            # fail safe
            # print(f"Processing schedule: {schedule}")
            if all(key in schedule for key in checklist):
                # check time format
                try:
                    start_time = datetime.combine(
                        today_date,
                        datetime.strptime(schedule["start_time"], "%H:%M").time(),
                        TIME_ZONE,
                    )
                    end_time = datetime.combine(
                        today_date,
                        datetime.strptime(schedule["end_time"], "%H:%M").time(),
                        TIME_ZONE,
                    )
                    # check time range, cross day
                    if start_time >= end_time:
                        end_time += timedelta(days=1)

                except ValueError:
                    print(
                        f"時間格式錯誤：{schedule['start_time']} 或 {schedule['end_time']}"
                    )
                    continue

                finally:
                    schedule_list.append(
                        Event(
                            start_time=start_time,
                            end_time=end_time,
                            what_to_do=schedule["what_to_do"],
                            interaction_target=schedule["interaction_target"],
                        )
                    )
        return schedule_list

    async def spawn_schedule(self):
        """生成日程，並將其存儲在 today_schedule_text 中"""
        # self.today_schedule_text = ""
        # self.today_done_list = []

        # self.start_time = datetime.now(TIME_ZONE)
        prompt = self.build_schedule_prompt(self.internal_time)
        chat_options = self.config["chatParams"]
        chat_options["num_predict"] = 2000
        chat_options["temperature"] = 0.1
        response = await self.api.chat(
            self.config["modelChat"],
            [{"role": "user", "content": prompt}],
            format="json",
            options=chat_options,
        )

        parse_txt = response.message.content
        print(f"生成的日程：\n{parse_txt}")
        # self.today_schedule_text = parse_txt[parse_txt.find("```jsons") + 7 : parse_txt.rfind("```")]
        # print(self.today_schedule_text)

    async def react_to_task(self, status_prompt):
        """對當前任務進行反應"""
        chat_options = self.config["chatParams"]
        status = await self.api.chat(
            self.config["modelChat"],
            [{"role": "user", "content": status_prompt}],
            options=chat_options,
        )
        return status

    async def reflect_on_day(self):
        chat_options = self.config["chatParams"]
        chat_options["num_predict"] = 1000
        prompt = f"You are {self.name}, {self.personality}, {self.behavior}."
        prompt += f"回顧今天的日程：{self.today_schedule_text}，你完成了{list_events(self.today_todo_list)}"
        prompt += "請在你的日記上簡單紀錄今天的成就、收穫與心情。"
        response = await self.api.chat(
            self.config["modelChat"],
            [{"role": "user", "content": prompt}],
            options=chat_options,
        )
        print(f"夜間反思記錄：\n{response.message.content}")


async def simulate_schedule_generator():

    schedule_manager = ScheduleManager()
    schedule_manager.initialize()
    # await schedule_manager.spawn_schedule()
    # with open(f"schedule_{schedule_manager.internal_time.strftime('%Y%m%d')}.json", "w", encoding='utf8') as f:
        # f.write(schedule_manager.today_schedule_text)

    with open("schedule_20250724.json", "r", encoding="utf8") as f:
        schedule_manager.today_schedule_text = f.read()

    schedule_manager.today_todo_list = schedule_manager.parse_schedule_text(
        schedule_manager.today_schedule_text
    )
    list_events(schedule_manager.today_todo_list)
    # oldtime = datetime.now(TIME_ZONE)
    while True:
        oldtime = schedule_manager.internal_time
        # 1 step = 90 min simulation
        schedule_manager.internal_time += timedelta(minutes=90)
        # next day
        if schedule_manager.internal_time.day != oldtime.day:
            # print("今天的日程已經結束，開始反思今天的日程")
            # await schedule_manager.reflect_on_day()
            # await schedule_manager.spawn_schedule()
            schedule_manager.today_todo_list = schedule_manager.parse_schedule_text(
                schedule_manager.today_schedule_text
            )

        current = schedule_manager.get_task_at(schedule_manager.internal_time)
        print(
            f"當前時間：{schedule_manager.internal_time.strftime('%H:%M')}, 當前活動：{current}"
        )
        mind_injection = input("請輸入當前想法：")
        status_prompt = schedule_manager.build_current_task_prompt(
            schedule_manager.internal_time, mind_injection
        )
        status = await schedule_manager.react_to_task(status_prompt)
        print(f"當前狀態：{status.message.content}")
        # await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(simulate_schedule_generator())
