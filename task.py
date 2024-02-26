import pandas as pd
from datetime import datetime
import os

# cd to file 
abspath = os.path.abspath(__file__)
os.chdir(os.path.dirname(abspath))
data = pd.read_csv('task.csv')

# 获取当前时间
current_time = datetime.now()

# 遍历数据行
for index, row in data.iterrows():
    start_time_str = row['開始時間']
    end_time_str = row['停止時間']
    activity = row['事項']
    target_person = row['目標人物']
    
    # 解析日期时间字符串为 datetime 对象
    start_time = datetime.strptime(start_time_str, '%H:%M')
    end_time = datetime.strptime(end_time_str, '%H:%M')
    
    # 将日期部分设置为当前日期，以便进行比较
    start_time = start_time.replace(year=current_time.year, month=current_time.month, day=current_time.day)
    end_time = end_time.replace(year=current_time.year, month=current_time.month, day=current_time.day)
    
    # 如果当前时间在活动开始和结束之间，则打印通知
    if start_time <= current_time <= end_time:
        print(f"通知：活动 '{activity}' 开始了，目标人物：{target_person}")
    elif current_time > end_time:
        print(f"通知：活动 '{activity}' 已结束，目标人物：{target_person}")
