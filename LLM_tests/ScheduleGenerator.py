import asyncio
import json
from typing import List
import ollama_api as ollama_api
import asyncio
import numpy as np
from datetime import datetime, timedelta, timezone
# from pytz import timezone

TIME_ZONE = timezone(timedelta(hours=8), name="Asia/Taipei")

class Event:
    def __init__(self, start_time: datetime, end_time: datetime, what_to_do: str, interaction_target: str):
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
        return f"{self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')}: {self.what_to_do} (Target: {self.interaction_target})"
    
def list_events(events: List[Event]):
    """將事件列表轉換為字符串格式"""
    return "\n".join(str(event) for event in events)

class ScheduleManager:
    def __init__(self, api: ollama_api.Ollama_API_Handler):
        self.api = api
        self.today_schedule_text = ""
        self.today_todo_list : List[Event] = [] 

        self.yesterday_schedule_text = ""
        self.yesterday_todo_list : List[Event] = []

        self.name = ""
        self.personality = ""
        self.behavior = ""
        self.start_time = datetime.now(TIME_ZONE)
        self.internal_time = datetime.now(TIME_ZONE)
        self.schedule_doing_update_interval = 300 
        
    def initialize(
        self,
        name: str = "伊莉亞",
        personality: str = "個性活潑外向的女大學生，主修資訊工程",
        behavior: str = "喜歡探索在地美食，學習新知識和技能，做白日夢",
        interval: int = 600,
    ):
        """初始化日程系统"""
        self.name = name
        self.behavior = behavior
        self.schedule_doing_update_interval = interval
        self.personality = personality
        self.start_time = datetime.now(TIME_ZONE)
        self.internal_time = datetime.now(TIME_ZONE)
        
    def construct_daytime_prompt(self, target_date: datetime):
        date_str = target_date.strftime("%Y-%m-%d")
        weekday = target_date.strftime("%A")

        prompt = f"You are {self.name}, {self.personality}, {self.behavior}."
        if self.yesterday_schedule_text:
            prompt += f"Your plan yesterday was: {self.yesterday_schedule_text}\n"
        prompt += f"Please generate the schedule for {date_str} ({weekday}), which is today, based on your personal traits, behavior habits, and yesterday's plan.\n"
        prompt += "Plan your schedule, including what you do throughout the day, from waking up to sleeping, any discoveries and thoughts, be specific, detailed, and precise to each hour (%H:%M). Remember to include the start time and end time.\n"
        prompt += "Please provide me today's schedule in json format with four following fields: start_time, end_time, what_to_do, and interaction_target. Make it realistic, not exaggerated, from waking up to sleeping, and do not output any other content:"
        
        return prompt
    
    def get_task_at(self, reference_time: datetime = None):
        """獲取當前活動"""
        reference_time = reference_time or datetime.now(TIME_ZONE)
        # parsed_schedule = self.parse_schedule_text(self.today_schedule_text)
        for item in self.today_todo_list:
            start = item.start_time
            end = item.end_time
            if start <= reference_time < end:
                return item
        return Event(
            start_time=reference_time,
            end_time=reference_time + timedelta(minutes=30),
            what_to_do="放鬆休息",
            interaction_target="自己",
        )
        
    def get_task_in_interval(self, start_time: datetime, end_time: datetime) -> List[Event]:
        """獲取在指定時間範圍內的任務"""
        tasks = []
        for item in self.today_todo_list:
            if item.start_time >= start_time:
                if item.end_time <= end_time:
                    tasks.append(item)
                else:
                    tasks.append(item)
                    break
        return tasks

    
    def construct_doing_prompt(self, time: datetime, mind_thinking: str = ""):
        now_time = time.strftime("%H:%M")
        previous_doing = self.get_task_in_interval(self.internal_time - timedelta(hours=3), self.internal_time)
        
        prompt = f"你是{self.name}，{self.personality}，{self.behavior}\n"
        today_schedule = list_events(self.today_todo_list)
        prompt += f"你今天的日程是：{today_schedule}\n"
        if previous_doing:
            time_diff = self.internal_time - previous_doing[-1].start_time
            print(f"{self.internal_time} - {previous_doing[-1].start_time} = {time_diff.seconds // 60} minutes")
            previous_doing = list_events(previous_doing)
            previous_doing = f"你之前做了的事情是：{previous_doing}，从之前到现在已经过去了 {time_diff.seconds // 60} 分钟了，\n"
            prompt += previous_doing
        if mind_thinking:
            prompt += f"你脑子里在想：{mind_thinking}，\n"
        prompt += f"结合你的个人特点和行为习惯,注意关注你今天的日程安排和想法安排你接下来做什么，现实一点，不要浮夸"
        prompt += "安排你接下来做什么，具体一些，详细一些\n"
        prompt += f"直接返回你现在{now_time}在做的事情，注意是当前时间，不要输出其他内容："
        return prompt
    
    def parse_schedule_text(self, schedule_text: str) -> List[Event]:
        """解析日程文本"""
        today_date = datetime.now(TIME_ZONE).date()
        
        # print(parsed_response)
        json_response = json.loads(schedule_text)
        schedule_list = []
        checklist = ["start_time", "end_time", "what_to_do", "interaction_target"]
        for schedule in json_response:
            # fail safe
            if all(key in schedule for key in checklist):
                # check time format
                try:
                    start_time = datetime.combine(today_date, datetime.strptime(schedule["start_time"], "%H:%M").time(), TIME_ZONE)
                    end_time = datetime.combine(today_date, datetime.strptime(schedule["end_time"], "%H:%M").time(), TIME_ZONE)
                except ValueError:
                    continue
                # check time range
                if start_time >= end_time:
                    continue
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
        """生成日程"""
        # self.today_schedule_text = ""
        # self.today_done_list = []

        self.start_time = datetime.now(TIME_ZONE)
        prompt = self.construct_daytime_prompt(self.start_time)
        response = await self.api.chat([{"role": "user", "content": prompt}])
        
        parse_txt = response.content
        self.today_schedule_text = parse_txt[parse_txt.find("```json") + 7 : parse_txt.rfind("```")]
        print(self.today_schedule_text)
    
    async def reflect_on_day(self):
        prompt  = f"You are {self.name}, {self.personality}, {self.behavior}."
        prompt += f"回顧今天的日程：{self.today_schedule_text}，你完成了{list_events(self.today_todo_list)}"
        prompt += "請在你的日記上簡單紀錄今天的成就、收穫與心情。"
        response = await self.api.chat([{"role": "user", "content": prompt}])
        print(f"夜間反思記錄：\n{response.content}")

async def simulate_schedule_generator():
    api = ollama_api.Ollama_API_Handler()
    schedule_manager = ScheduleManager(api)
    schedule_manager.initialize()
    # await schedule_manager.spawn_schedule()
    # with open("schedule.json", "w", encoding='utf8') as f:
        # f.write(schedule_manager.today_schedule_text)
        
    with open("schedule.json", "r", encoding='utf8') as f:
        schedule_manager.today_schedule_text = f.read()
        
    schedule_manager.today_todo_list = schedule_manager.parse_schedule_text(schedule_manager.today_schedule_text)
    list_events(schedule_manager.today_todo_list)
    # oldtime = datetime.now(TIME_ZONE)
    while True:
        oldtime = schedule_manager.internal_time
        schedule_manager.internal_time += timedelta(seconds=schedule_manager.schedule_doing_update_interval*12)
        # next day
        if schedule_manager.internal_time.day != oldtime.day:
            await schedule_manager.reflect_on_day()
            await schedule_manager.spawn_schedule()
            schedule_manager.today_todo_list = schedule_manager.parse_schedule_text(schedule_manager.today_schedule_text)
            
        current = schedule_manager.get_task_at(schedule_manager.internal_time)
        print(f"當前時間：{schedule_manager.internal_time.strftime('%H:%M')}, 當前活動：{current}")
        status_prompt = schedule_manager.construct_doing_prompt(schedule_manager.internal_time)
        # print(f"當前狀態提示：{status_prompt}")
        status = await schedule_manager.api.chat([{"role": "user", "content": status_prompt}])
        print(f"當前狀態：{status.content}")
        await asyncio.sleep(10)
        
if __name__ == "__main__":
    asyncio.run(simulate_schedule_generator())