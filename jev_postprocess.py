from __future__ import annotations

import ast
import pathlib

import matplotlib.lines as mlines
import matplotlib.pyplot as plt

from jev_scoring import JevAPI

log_jev = pathlib.Path("./jev_outputs/scoring_jev_000_100.txt").read_text(encoding="utf-8")
# format: 400. {'memorable': 0.431, 'type': 'opinion', 'decision_impact': 2.104}
data = []
counter = 1
for line in log_jev.splitlines():
    # parse the line to extract the scoring result
    score_str = line.split(". ", 1)[1]
    # score_str = score_str.rsplit("'token_usage'", 1)[0] + "}"
    # print(f"Parsing line {counter}: {score_str}")

    try:
        score_dict: dict = ast.literal_eval(score_str)  # Convert string representation of dict to actual dict
    except (IndexError, SyntaxError):
        print(f"Error parsing line: {line}")
    else:
        memorable = score_dict.get("memorable", -1)
        # type_ = score_dict.get("type", "none")
        intent = score_dict.get("intent", "none")
        topic = score_dict.get("topic", "none")
        decision_impact = score_dict.get("decision_impact", -1)

        counter += 1
        data.append({"memorable": memorable, "intent": intent, "topic": topic, "decision_impact": decision_impact})


topics = list(JevAPI.criteria_topic.keys())
intents = list(JevAPI.criteria_intent.keys())

# 顏色對應 Topic
topic_colors = dict(zip(
        topics, plt.get_cmap("tab10")(range(len(topics))), strict=False
    ))

# 形狀對應 Intent
marker_styles = ["o", "s", "^", "D", "v", "P", "X", "*"]
intent_markers = {
    intent: marker_styles[i % len(marker_styles)]
    for i, intent in enumerate(intents)
}

plt.figure(figsize=(11, 6))

for topic in topics:
    for intent in intents:
        x = [
            item["memorable"]
            for item in data
            if item.get("topic") == topic and item.get("intent") == intent
        ]
        y = [
            item["decision_impact"]
            for item in data
            if item.get("topic") == topic and item.get("intent") == intent
        ]

        if x:
            plt.scatter(
                x,
                y,
                color=topic_colors[topic],
                marker=intent_markers[intent],
                alpha=0.8,
                s=60,
            )

plt.xlabel("Memorable")
plt.ylabel("Decision Impact")
plt.title("Jev Scoring Results")

# 建立兩個獨立的 Legend：一個代表 Topic（顏色），一個代表 Intent（形狀）
topic_handles = [
    mlines.Line2D(
        [],
        [],
        color=topic_colors[t],
        marker="o",
        linestyle="None",
        markersize=8,
        label=t,
    )
    for t in topics
]
intent_handles = [
    mlines.Line2D(
        [],
        [],
        color="gray",
        marker=intent_markers[i],
        linestyle="None",
        markersize=8,
        label=i,
    )
    for i in intents
]

leg1 = plt.legend(
    handles=topic_handles,
    title="Topics (Color)",
    bbox_to_anchor=(1.05, 1),
    loc="upper left",
)
plt.gca().add_artist(leg1)
plt.legend(
    handles=intent_handles,
    title="Intents (Shape)",
    bbox_to_anchor=(1.05, 0.45),
    loc="upper left",
)

plt.tight_layout()
plt.show()
