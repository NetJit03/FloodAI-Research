#!/usr/bin/env python3
"""Prepare reproducible Sen1Floods11 hand-labeled splits excluding zero-label chips.

Does NOT alter official CSV files. Keeps valid all-land samples (label 0).
Run from the FloodAI-Research project root:
    python prepare_audited_splits.py
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path("data/sen1floods11")
SOURCE = ROOT / "splits"
TARGET = ROOT / "splits_audited"
SPLITS = {
    "train": "flood_train_data.csv",
    "valid": "flood_valid_data.csv",
    "test": "flood_test_data.csv",
    "bolivia": "flood_bolivia_data.csv",
}


def usable_labels(filename: str) -> int:
    label_path = ROOT / "LabelHand" / Path(filename).name
    if not label_path.exists():
        raise FileNotFoundError(f"Label missing: {label_path}")
    with rasterio.open(label_path) as src:
        labels = src.read(1)
    return int(np.count_nonzero((labels == 0) | (labels == 1)))


def main() -> None:
    TARGET.mkdir(parents=True, exist_ok=True)
    skipped = []
    summaries = {}
    for split, filename in SPLITS.items():
        src_path = SOURCE / filename
        if not src_path.exists():
            raise FileNotFoundError(f"Split file missing: {src_path}")
        with src_path.open(newline="", encoding="utf-8-sig") as f:
            rows = [row for row in csv.reader(
                f) if any(cell.strip() for cell in row)]
        retained = []
        headers = []
        for row in rows:
            if len(row) < 2:
                raise ValueError(
                    f"Expected >=2 columns in {src_path}: {row!r}")
            # Keep an optional header without trying to interpret it as a filename.
            if not row[0].strip().lower().endswith(".tif"):
                if retained:
                    raise ValueError(
                        f"Unexpected non-image row in {src_path}: {row!r}")
                headers.append(row)
                continue
            n_valid = usable_labels(row[1].strip())
            if n_valid == 0:
                skipped.append({
                    "split": split,
                    "sar_image": Path(row[0].strip()).name,
                    "label_image": Path(row[1].strip()).name,
                    "reason": "no valid ground-truth pixels (label 0 or 1)",
                })
            else:
                retained.append(row)
        out_path = TARGET / filename
        with out_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerows(headers + retained)
        n_images = len(rows) - len(headers)
        summaries[split] = {
            "original": n_images,
            "retained": len(retained),
            "excluded": n_images - len(retained),
            "output": str(out_path),
        }
        print(f"{split:8s} {n_images:3d} original | {len(retained):3d} retained | {n_images - len(retained)} excluded")
    with (TARGET / "excluded_zero_label_images.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["split", "sar_image", "label_image", "reason"])
        writer.writeheader()
        writer.writerows(skipped)
    with (TARGET / "split_summary.json").open("w", encoding="utf-8") as f:
        json.dump({"splits": summaries, "excluded": skipped},
                  f, ensure_ascii=False, indent=2)
    print(f"\nTotal excluded: {len(skipped)}")
    print(f"Created filtered copies in: {TARGET}")
    print("Official split files remain unchanged.")
    print("NOTE: filtering zero-label chips does NOT make splits event-independent.")


if __name__ == "__main__":
    main()
