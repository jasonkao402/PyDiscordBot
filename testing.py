import csv
import itertools

sco = []
with open('./scoreboard/score.csv', mode='r', encoding='utf-8-sig') as FILE:
    data = csv.reader(FILE)
    next(data)
    sco = sorted(data, key=lambda item: int(item[1]), reverse=True)
print(sco)
top5 = enumerate(itertools.islice(sco, 0, 3))

fmt = '\n'.join(f"[Rank {r+1}] {(i[0])} ({i[1]}pt) : \"{i[2]}\"" for r,i in top5)
print(fmt)