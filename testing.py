import csv
import os

with open('./scoreboard/score.csv', mode='r', encoding='utf-8-sig') as FILE:
    data = csv.DictReader(FILE)
    line_count = 1
    for row in data:
        if line_count > 5:
            break
        print(f"[Rank {line_count}] {row['id']} ({row['score']}pt) : \"{row['last_msg']}\"")
        line_count += 1
    #print(len(data))