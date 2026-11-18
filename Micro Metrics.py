
import csv
from pathlib import Path
from collections import defaultdict

path = Path(
    "results/event_level_v1/fold_03_ghana/"
    "evaluation/test_per_image.csv"
)

with path.open(newline="") as f:
    records = list(csv.DictReader(f))

groups = defaultdict(list)


def water_group(fraction):
    if fraction < 0.01:
        return "A: Very Low (<1%)"
    elif fraction < 0.05:
        return "B: Low (1-5%)"
    elif fraction < 0.20:
        return "C: Medium (5-20%)"
    return "D: High (>=20%)"


for row in records:
    tp = int(row["tp"])
    fn = int(row["fn"])
    valid = int(row["valid_pixels"])

    if valid <= 0:
        continue

    gt_fraction = (tp + fn) / valid
    groups[water_group(gt_fraction)].append(row)

print("=== GHANA WATER FRACTION ANALYSIS ===")

for group in [
    "A: Very Low (<1%)",
    "B: Low (1-5%)",
    "C: Medium (5-20%)",
    "D: High (>=20%)"
]:
    rows = groups[group]

    tp = sum(int(r["tp"]) for r in rows)
    fp = sum(int(r["fp"]) for r in rows)
    fn = sum(int(r["fn"]) for r in rows)

    iou = tp / (tp + fp + fn) if tp + fp + fn else float("nan")
    recall = tp / (tp + fn) if tp + fn else float("nan")
    precision = tp / (tp + fp) if tp + fp else float("nan")

    print(f"\n{group}")
    print("Images:", len(rows))
    print("GT Water Pixels:", tp + fn)
    print("False Negatives:", fn)
    print("Micro IoU:", round(iou, 4))
    print("Micro Recall:", round(recall, 4))
    print("Micro Precision:", round(precision, 4))

print("\n=== MOST MISSED WATER PIXELS ===")
top_fn = sorted(
    records,
    key=lambda r: int(r["fn"]),
    reverse=True
)

for row in top_fn[:10]:
    print(
        row["name"],
        "| FN:", row["fn"],
        "| Recall:", row["recall"],
        "| IoU:", row["iou"]
    )
