#!/usr/bin/env python3
"""Prepare event-level training roots for the unmodified train_sar_unet.py.

Creates links only; never moves, modifies, or deletes the SAR, label, or split files.
Run from the FloodAI-Research project root.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

DATA_ROOT = Path("data/sen1floods11").resolve()
SOURCE = DATA_ROOT / "splits_event_level_v1"
DEST = DATA_ROOT / "event_level_roots"
EXPECTED = {
    "fold_01_india": (288, 69, 68),
    "fold_02_paraguay": (317, 42, 66),
    "fold_03_ghana": (347, 30, 48),
}


def ensure_link(dst: Path, src: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(f"Missing source: {src}")
    src = src.resolve()
    if dst.is_symlink():
        if dst.resolve() != src:
            raise RuntimeError(
                f"Existing link points elsewhere: {dst} -> {dst.resolve()}")
    elif dst.exists():
        raise RuntimeError(f"Refusing to replace an existing path: {dst}")
    else:
        dst.symlink_to(src, target_is_directory=src.is_dir())


def csv_count(path: Path) -> int:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return sum(1 for row in csv.reader(handle) if row and row[0].strip())


def main() -> None:
    for folder in ("S1Hand", "LabelHand"):
        if not (DATA_ROOT / folder).is_dir():
            raise FileNotFoundError(
                f"Missing dataset folder: {DATA_ROOT / folder}")

    bolivia = SOURCE / "flood_bolivia_data_LOCKED.csv"
    if not bolivia.is_file():
        raise FileNotFoundError(f"Missing locked Bolivia CSV: {bolivia}")
    if csv_count(bolivia) != 15:
        raise RuntimeError(
            "Locked Bolivia CSV does not contain the expected 15 rows")

    summaries = {}
    for fold, expected in EXPECTED.items():
        fold_src = SOURCE / fold
        for split, count in zip(("train", "valid", "test"), expected):
            csv_path = fold_src / f"flood_{split}_data.csv"
            if not csv_path.is_file():
                raise FileNotFoundError(f"Missing split CSV: {csv_path}")
            actual = csv_count(csv_path)
            if actual != count:
                raise RuntimeError(
                    f"Unexpected row count: {csv_path}: {actual} != {count}")

        root = DEST / fold
        (root / "splits").mkdir(parents=True, exist_ok=True)
        for folder in ("S1Hand", "LabelHand"):
            ensure_link(root / folder, DATA_ROOT / folder)
        for split in ("train", "valid", "test"):
            filename = f"flood_{split}_data.csv"
            ensure_link(root / "splits" / filename, fold_src / filename)
        # The existing inspect_splits() requires this CSV, but the trainer does not use it to fit/tune.
        ensure_link(root / "splits" / "flood_bolivia_data.csv", bolivia)
        summaries[fold] = {"train": expected[0], "valid": expected[1],
                           "test": expected[2], "bolivia_inspection_only": 15}
        print(
            f"{fold}: train={expected[0]} valid={expected[1]} test={expected[2]} bolivia=15 [inspection only]")
        print(
            f"  --data-root {root.relative_to(Path.cwd()) if root.is_relative_to(Path.cwd()) else root}")

    DEST.mkdir(parents=True, exist_ok=True)
    (DEST / "root_manifest.json").write_text(
        json.dumps({"source": str(SOURCE), "folds": summaries,
                   "note": "Symbolic links; source data unchanged"}, indent=2),
        encoding="utf-8",
    )
    print("\nPrepared linked data roots. Run --check-only before training.")


if __name__ == "__main__":
    main()
