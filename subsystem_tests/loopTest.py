import asyncio
import random
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta, timezone

TZ_TW = timezone(timedelta(hours = 8))

with open('talkTest.txt', 'r', encoding='utf-8') as f:
    talkList = f.readlines()
    
def find_exceeding_times(rate_parameter, num_simulations=1000, num_events_per_simulation=50, threshold=60):
    # Generate exponential random variables
    time_points = np.random.exponential(60/rate_parameter, (num_simulations, num_events_per_simulation))
    time_points = np.round(time_points, 3)
    
    # Calculate cumulative sum along each row
    cumulative_times = np.cumsum(time_points, axis=1)
    
    # Find when the total time exceeds the threshold
    exceeding_times = np.argmax(cumulative_times > threshold, axis=1)
    
    return exceeding_times

async def message_sender():
    average_rate = 5

    rate_parameter = average_rate / 60

    total_messages = 0
    total_time = 0
    
    
    while total_time < 60:
        wait_time = random.expovariate(rate_parameter)
        total_time += wait_time

        if total_time >= 60 or total_messages == len(talkList)-1:
            break
        
        # await asyncio.sleep(wait_time)
        # 發送消息
        total_messages += 1
        output_string = f"{total_time:7.3f} {talkList[total_messages]}"
        print(output_string)

    print(f"Total messages sent: {total_messages}")

async def main():
    t = find_exceeding_times(25)
    plt.hist(t, alpha=0.75, edgecolor='black')
    plt.title('Distribution of Exceeding Times')
    plt.xlabel('Event Index')
    plt.ylabel('Probability Density')
    plt.show()
    
    await message_sender()
    
if __name__ == "__main__":
    asyncio.run(main())
    time_points = np.random.exponential(60/5, (10))
    time_points = np.round(time_points, 3)
    cumulative_times = np.cumsum(time_points)
    cur_time = datetime.now(timezone.utc)
    
    t = [cur_time + timedelta(seconds = i) for i in cumulative_times]
    for tt in t:
        print(tt.astimezone(TZ_TW).strftime("%H:%M:%S"))