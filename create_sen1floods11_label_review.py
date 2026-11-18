#!/usr/bin/env python3
"""Create a reproducible visual label-review pack for Sen1Floods11.

Run from FloodAI-Research root:
  python create_sen1floods11_label_review.py

Reads the existing quality-audit CSV and the *verified* splits, then
renders three chips per event: low water fraction, high water fraction,
and high ignore fraction (or a distinct fallback). No source data modified.
Visual QC alone cannot independently verify the water labels.
"""
from __future__ import annotations
from matplotlib.patches import Patch
import rasterio
import numpy as np
import matplotlib.pyplot as plt

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # safe on headless Macs/terminals

SPLITS = ("train", "valid", "test", "bolivia")


def read_verified(root: Path):
    out = {}
    for split in SPLITS:
        p = root / "splits_verified" / f"flood_{split}_data.csv"
        if not p.exists():
            raise FileNotFoundError(f"Verified split not found: {p}")
        with p.open(newline="", encoding="utf-8-sig") as f:
            for row in csv.reader(f):
                if not row or not row[0].strip().endswith("_S1Hand.tif"):
                    continue
                if len(row) < 2:
                    raise ValueError(
                        f"Expected image/label pair in {p}: {row}")
                image_id = Path(row[0].strip()).name.removesuffix(
                    "_S1Hand.tif")
                if image_id in out:
                    raise ValueError(
                        f"Image ID duplicated in verified splits: {image_id}")
                out[image_id] = {"split": split, "sar": Path(row[0].strip()).name,
                                 "label": Path(row[1].strip()).name}
    return out


def read_quality(path: Path, verified: dict):
    if not path.exists():
        raise FileNotFoundError(
            f"Quality audit CSV missing: {path}. Run audit_sen1floods11_quality.py first.")
    groups = defaultdict(list)
    with path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            image_id = row["image_id"]
            if image_id not in verified:
                continue
            evaluable = int(row["evaluable_pixels"])
            if evaluable <= 0:
                raise ValueError(
                    f"Verified splits still include a zero-evaluable chip: {image_id}")
            h, w = int(row["height"]), int(row["width"])
            event = row["event"]
            groups[event].append({
                "event": event, "image_id": image_id,
                "split": verified[image_id]["split"],
                "sar": verified[image_id]["sar"],
                "label": verified[image_id]["label"],
                "water_fraction": float(row["water_fraction_evaluable"]),
                "ignore_fraction": int(row["ignore_pixels"]) / (h * w),
                "evaluable_pixels": evaluable,
            })
    found = {v["image_id"] for rows in groups.values() for v in rows}
    missing = sorted(set(verified) - found)
    if missing:
        raise ValueError(
            f"Missing audit rows for verified chips: {missing[:8]} (total {len(missing)})")
    return groups


def pick_examples(items: list, count: int):
    """Deterministic, distinct, varied selections; no test metrics or predictions used."""
    by_water = sorted(items, key=lambda x: (
        x["water_fraction"], x["image_id"]))
    by_ignore = sorted(
        items, key=lambda x: (-x["ignore_fraction"], x["image_id"]))
    choices, seen = [], set()

    def add(row, reason):
        if row["image_id"] not in seen and len(choices) < count:
            choices.append((row, reason))
            seen.add(row["image_id"])

    add(by_water[0], "lowest_water_fraction")
    add(by_water[-1], "highest_water_fraction")
    for row in by_ignore:
        if len(choices) >= count:
            break
        add(row, "highest_ignore_fraction")
    if len(choices) < count:
        mid = by_water[len(by_water) // 2]
        add(mid, "median_water_fraction")
    for row in by_water:
        add(row, "additional_distinct_sample")
    return choices


def stretch(channel: np.ndarray):
    valid = np.isfinite(channel)
    out = np.zeros(channel.shape, dtype=np.float32)
    if not valid.any():
        return out
    values = channel[valid]
    lo, hi = np.percentile(values, [2, 98])
    if hi <= lo + 1e-8:
        hi = lo + 1
    out[valid] = np.clip((channel[valid] - lo) / (hi - lo), 0, 1)
    return out


def visualize_chip(root: Path, item: dict):
    with rasterio.open(root / "S1Hand" / item["sar"]) as src:
        sar = src.read()
    with rasterio.open(root / "LabelHand" / item["label"]) as src:
        label = src.read(1)
    if sar.shape[0] != 2 or sar.shape[1:] != label.shape:
        raise ValueError(f"SAR/label shape mismatch for {item['image_id']}")
    vv, vh = stretch(sar[0]), stretch(sar[1])
    water, ignore = label == 1, label == -1
    # 0 = land gray, 1 = water blue, -1 = ignored orange
    mask_rgb = np.full((*label.shape, 3), (0.78, 0.81, 0.84), dtype=np.float32)
    mask_rgb[water] = (0.04, 0.47, 0.89)
    mask_rgb[ignore] = (0.99, 0.64, 0.20)
    overlay = np.repeat(vv[..., None], 3, axis=2)
    overlay[water] = 0.36 * overlay[water] + \
        0.64 * np.array([0.04, 0.47, 0.89])
    overlay[ignore] = 0.60 * overlay[ignore] + \
        0.40 * np.array([0.99, 0.64, 0.20])
    return vv, vh, mask_rgb, overlay


def save_sheet(root: Path, event: str, selected: list, out_path: Path):
    fig, axes = plt.subplots(len(selected), 4, figsize=(15, 3.7 * len(selected)),
                             squeeze=False, constrained_layout=True)
    for j, (item, reason) in enumerate(selected):
        images = visualize_chip(root, item)
        for k, (img, name) in enumerate(zip(images, ("VV (stretched)", "VH (stretched)",
                                                     "Ground-truth mask", "VV + labels"))):
            ax = axes[j, k]
            ax.imshow(img, cmap="gray" if k < 2 else None,
                      interpolation="nearest")
            ax.set_title(name, fontsize=10)
            ax.axis("off")
        axes[j, 0].set_title(
            f"{item['image_id']} | {item['split']} | {reason}\n"
            f"Water {100*item['water_fraction']:.1f}% (valid), "
            f"ignore {100*item['ignore_fraction']:.1f}% (all)\n"
            "VV (stretched)", fontsize=8.5,
        )
    fig.suptitle(f"Sen1Floods11 | {event} | Visual ground-truth review (NOT independent verification)",
                 fontsize=13)
    fig.legend(handles=[Patch(color="#caCFd6", label="land = 0"),
                        Patch(color="#0878e3", label="water = 1"),
                        Patch(color="#fca333", label="ignore = -1")],
               loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.02))
    fig.savefig(out_path, dpi=125, bbox_inches="tight")
    plt.close(fig)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data-root", default="data/sen1floods11")
    p.add_argument(
        "--audit-csv", default="results/data_audit/per_image_quality.csv")
    p.add_argument("--output-dir", default="results/label_review")
    p.add_argument("--per-event", type=int, default=3)
    args = p.parse_args()
    if args.per_event < 1:
        p.error("--per-event must be >=1")
    root, out = Path(args.data_root), Path(args.output_dir)
    verified = read_verified(root)
    groups = read_quality(Path(args.audit_csv), verified)
    out.mkdir(parents=True, exist_ok=True)
    selected_rows = []
    for event in sorted(groups):
        selected = pick_examples(groups[event], args.per_event)
        save_sheet(root, event, selected, out /
                   f"review_{event.replace(' ', '_')}.png")
        for item, reason in selected:
            selected_rows.append({
                "event": event, "split": item["split"], "image_id": item["image_id"],
                "reason_selected": reason,
                "water_fraction_evaluable": round(item["water_fraction"], 6),
                "ignore_fraction_all_pixels": round(item["ignore_fraction"], 6),
                "review_status": "NOT_REVIEWED", "review_confidence": "",
                "notes": "",
            })
        print(
            f"{event:13s} {len(groups[event]):3d} verified images | {len(selected)} examples | saved review_{event.replace(' ', '_')}.png")
    fields = list(selected_rows[0]) if selected_rows else []
    with (out / "review_checklist.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(selected_rows)
    with (out / "README_review.txt").open("w", encoding="utf-8") as f:
        f.write("VISUAL LABEL QC — Sen1Floods11\n"
                "Each row: VV, VH, Label (blue=water, gray=land, orange=ignore), overlay.\n"
                "Review on SAR alone only flags implausible/ambiguous boundaries; it is NOT independent verification.\n"
                "Open review_checklist.csv and set review_status to PASS / FLAG / UNCERTAIN.\n"
                "Log why a label looks implausible and any source data you checked; do not change the original labels.\n"
                "Review sampling is deliberately diverse, NOT random/representative.\n"
                "Reserve test images for QA only; do not tune a model using them.\n")
    print(
        f"\nVerified images: {len(verified)} | events: {len(groups)} | reviewed candidates: {len(selected_rows)}")
    print(f"Saved in: {out}")
    print("Next: open sheets and mark PASS / FLAG / UNCERTAIN in review_checklist.csv")


if __name__ == "__main__":
    main()
