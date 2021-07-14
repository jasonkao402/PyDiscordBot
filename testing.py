import csv
import itertools

sco = []
with open('./scoreboard/score.csv', mode='r', encoding='utf-8-sig') as FILE:
    data = csv.reader(FILE)
    sco = sorted(data, key=lambda i: int(i[1]), reverse=True)
print(sco)

top5 = enumerate(itertools.islice(sco, 0, 3), start=1)
fmt = '\n'.join(f"[Rank {r}] {(i[0])} ({i[1]}pt) : \"{i[2]}\"" for r, i in top5)
print(fmt)

d = {int(i[0]):(int(i[1]),i[2]) for i in sco}
USER = 456456456
MSG = "loli loli"
d[USER] = (d[USER][0]+1, MSG)
USER = 0
MSG = "loli loli"
d[USER] = ((d[USER][0]+1 if USER in d else 1), MSG)
print([[k, v[0], v[1]]for k,v in d.items()])
sco = [[k, v[0], v[1]]for k,v in d.items()]

top5 = enumerate(itertools.islice(sco, 0, 3), start=1)
fmt = '\n'.join(f"[Rank {r}] {(i[0])} ({i[1]}pt) : \"{i[2]}\"" for r, i in top5)
print(fmt)

with open('./scoreboard/output.csv', 'w+', newline='', encoding='utf-8-sig') as output:
    # 以空白分隔欄位，建立 CSV 檔寫入器
    writer = csv.writer(output, delimiter=',')
    for i in sco:
        print(i)
        writer.writerow(i)