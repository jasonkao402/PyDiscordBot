from ScheduleGenerator import ScheduleManager
import os
import asyncio

async def simulate_schedule_generator():
    schedule_manager = ScheduleManager()
    schedule_manager.initialize(name="優咪")
    # schedule_manager.build_schedule_prompt()
    await schedule_manager.spawn_schedule()
    with open("schedule.json", "w+", encoding='utf8') as f:
        f.write(schedule_manager.today_schedule_text)
        
if __name__ == "__main__":
    asyncio.run(simulate_schedule_generator())