from __future__ import annotations

import ast
import pathlib
import textwrap

import pandas as pd
import plotly.express as px

jev_output_dir = pathlib.Path("./jev_outputs")
target_file = "scoring_jev_000_030.txt"
log_jev = jev_output_dir / target_file
target_file_stem = log_jev.stem
log_jev = log_jev.read_text(encoding="utf-8")

data = []
for line in log_jev.splitlines():
    if not line.strip() or ". " not in line:
        continue

    # 直接抓取行首的原始 ID (例如 "400")
    raw_id, score_str = line.split(". ", 1)

    try:
        score_dict: dict = ast.literal_eval(score_str)
    except (IndexError, SyntaxError):
        print(f"Error parsing line: {raw_id}")
        continue

    # 將長文字每 40 字元自動換行，避免懸浮視窗太寬
    u_text = "<br>".join(textwrap.wrap(str(score_dict.get("u", "")), width=40))
    a_text = "<br>".join(textwrap.wrap(str(score_dict.get("a", ""))[:120], width=40))

    data.append({
        "id": f"#{int(raw_id):03d}",
        "memorable": score_dict.get("memorable", -1),
        "intent": score_dict.get("intent", "none"),
        "topic": score_dict.get("topic", "none"),
        "decision_impact": score_dict.get("decision_impact", -1),
        "user_prompt": u_text,
        "ai_reply": a_text,
    })

df = pd.DataFrame(data)

# 一行畫出互動式散佈圖（自動處理顏色與形狀的雙 Legend）
fig = px.scatter(
    df,
    x="memorable",
    y="decision_impact",
    color="topic",
    symbol="intent",
    hover_name="id",  # 懸浮標題直接顯示 #001, #002
    hover_data={
        "memorable": ":.3f",
        "decision_impact": ":.3f",
        "topic": True,
        "intent": True,
        "user_prompt": True,  # 懸浮直接看使用者講了什麼！
        "ai_reply": True,
    },
    title=f"Jev Scoring Results ({target_file_stem}) (Interactive)",
    width=1200,
    height=700,
)

# 調整點的大小與透明度
fig.update_traces(marker={"size": 11, "opacity": 0.85, "line": {"width": 0.5, "color": "DarkSlateGrey"}})

# [加碼] 畫出我們剛剛討論的過濾門檻參考線 (Memorable = 0.55, Impact = 1.70)
fig.add_vline(x=0.55, line_width=1, line_dash="dash", line_color="red", annotation_text="Memorable Gate (0.55)")
fig.add_hline(y=1.70, line_width=1, line_dash="dash", line_color="red", annotation_text="Impact Gate (1.70)")

# fig.write_html(f"jev_interactive_{target_file_stem}.html")
fig.show()
