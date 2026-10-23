from __future__ import annotations

import pathlib

# plot the data using matplotlib
import matplotlib.pyplot as plt

log_jev = pathlib.Path("scoring_jev_001_200.txt").read_text(encoding="utf-8")
# format: 400. {'memorable': 0.431658073458055, 'type': 'opinion', 'decision_impact': 2.104484180586282}
data = []
counter = 1
for line in log_jev.splitlines():
    # parse the line to extract the scoring result
    score_str = line.split(". ", 1)[1]
    try:
        score_dict = eval(score_str)  # Convert string representation of dict to actual dict
        memorable = score_dict.get("memorable", None)
        type_ = score_dict.get("type", None)
        decision_impact = score_dict.get("decision_impact", None)
        # print(f"{counter:03d}. Memorable: {memorable}, Type: {type_}, Decision Impact: {decision_impact}")
        counter += 1
    except (IndexError, SyntaxError):
        print(f"Error parsing line: {line}")
    data.append({
        "memorable": memorable,
        "type": type_,
        "decision_impact": decision_impact
    })


type_mapping = {
    "rules": 4,
    "correction": 3,
    "fact": 2,
    "opinion": 1,
    "casual": 0,
}
memorable_values = [item["memorable"] for item in data]
type_values = [type_mapping.get(item["type"], 0) for item in data]  # Default to 0 if type is unknown
decision_impact_values = [item["decision_impact"] for item in data]
xy = zip(memorable_values, decision_impact_values, strict=False)
plt.figure(figsize=(10, 6))
plt.scatter(memorable_values, decision_impact_values, c=type_values, label='Data Points')
plt.colorbar(label='Type (1: opinion, 2: fact, 3: correction, 4: rules)')
plt.xlabel('Memorable')
plt.ylabel('Decision Impact')
plt.title("Jev Scoring Results")
plt.legend()
plt.show()
