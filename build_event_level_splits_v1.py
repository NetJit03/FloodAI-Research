#!/usr/bin/env python3
"""Create fixed, event-disjoint SAR-only research splits from verified Sen1Floods11.

Only uses the Python standard library. The official and verified CSVs are never modified.

Design: Three prespecified source-event experiments, each using 8 events to
train, 1 event to validate, and 1 event to test. Bolivia remains a separate
locked external holdout and is not used in any training/validation fold.

Run from the FloodAI-Research project root:
    python build_event_level_splits_v1.py
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SOURCE = Path("data/sen1floods11/splits_verified")
DEST = Path("data/sen1floods11/splits_event_level_v1")

# Selected in advance, not based on scores from the new experiments.
FOLDS = [
    ("fold_01_india", "India", "USA"),
    ("fold_02_paraguay", "Paraguay", "Sri-Lanka"),
    ("fold_03_ghana", "Ghana", "Spain"),
]
EXPECTED_COUNTS = {"train": 251, "valid": 86, "test": 88, "bolivia": 15}
EXPECTED_EVENTS = {
    "Cambodia", "Ghana", "India", "Nigeria", "Pakistan",
    "Paraguay", "Somalia", "Spain", "Sri-Lanka", "USA",
}


def event_from_filename(filename: str) -> str:
    image = Path(filename).name
    if not image.endswith("_S1Hand.tif"):
        raise ValueError(f"Unexpected SAR image filename: {filename!r}")
    prefix = image.split("_", 1)[0]
    return "Cambodia" if prefix == "Mekong" else prefix


def load_csv(path: Path) -> list[list[str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing input split: {path}")
    with path.open("r", newline="", encoding="utf-8-sig") as file:
        rows = [row for row in csv.reader(
            file) if any(cell.strip() for cell in row)]
    # Most Sen1Floods11 split files have no header. Allow a conventional header.
    if rows and not Path(rows[0][0]).name.endswith("_S1Hand.tif"):
        first = rows[0][0].strip().lower()
        if first in {"sar", "image", "sar_filename", "image_path", "s1", "sar_file"}:
            rows.pop(0)
        else:
            raise ValueError(f"Unexpected first row in {path}: {rows[0]}")
    for i, row in enumerate(rows, start=1):
        if len(row) < 2:
            raise ValueError(f"Missing label filename at {path}:{i}: {row}")
        sar = Path(row[0]).name
        label = Path(row[1]).name
        if not sar.endswith("_S1Hand.tif") or not label.endswith("_LabelHand.tif"):
            raise ValueError(f"Unexpected pair at {path}:{i}: {row}")
        if sar.removesuffix("_S1Hand.tif") != label.removesuffix("_LabelHand.tif"):
            raise ValueError(f"Mismatched SAR/label pair at {path}:{i}: {row}")
    return rows


def write_csv(path: Path, rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        csv.writer(file).writerows(rows)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def names(rows: list[list[str]]) -> set[str]:
    return {Path(row[0]).name for row in rows}


def main() -> None:
    original = {}
    for name, expected in EXPECTED_COUNTS.items():
        path = SOURCE / f"flood_{name}_data.csv"
        original[name] = load_csv(path)
        if len(original[name]) != expected:
            raise ValueError(
                f"{name} has {len(original[name])} rows, expected {expected}. "
                "Check the verified split files before continuing."
            )

    all_rows = [row for subset in original.values() for row in subset]
    all_names = [Path(row[0]).name for row in all_rows]
    if len(set(all_names)) != len(all_names):
        raise ValueError("Duplicate SAR chips across verified splits")

    source_rows = original["train"] + original["valid"] + original["test"]
    by_event = Counter(event_from_filename(row[0]) for row in source_rows)
    if set(by_event) != EXPECTED_EVENTS:
        raise ValueError(f"Unexpected source events: {sorted(by_event)}")
    if any(event_from_filename(row[0]) != "Bolivia" for row in original["bolivia"]):
        raise ValueError("Bolivia holdout contains another event")

    DEST.mkdir(parents=True, exist_ok=True)
    write_csv(DEST / "flood_bolivia_data_LOCKED.csv", original["bolivia"])

    fold_summaries = []
    for fold_id, test_event, valid_event in FOLDS:
        if test_event == valid_event:
            raise ValueError(f"Fold {fold_id}: same validation/test event")
        if test_event not in by_event or valid_event not in by_event:
            raise ValueError(f"Fold {fold_id}: unknown test/validation event")

        parts = {
            "train": [row for row in source_rows if event_from_filename(row[0]) not in {test_event, valid_event}],
            "valid": [row for row in source_rows if event_from_filename(row[0]) == valid_event],
            "test": [row for row in source_rows if event_from_filename(row[0]) == test_event],
        }
        # Reproducible ordering, independent of order in official CSV files.
        for subset in parts.values():
            subset.sort(key=lambda row: Path(row[0]).name)

        event_sets = {split: {event_from_filename(
            row[0]) for row in rows} for split, rows in parts.items()}
        for left, right in [("train", "valid"), ("train", "test"), ("valid", "test")]:
            if event_sets[left] & event_sets[right]:
                raise AssertionError(
                    f"{fold_id}: events overlap between {left}/{right}")
            if names(parts[left]) & names(parts[right]):
                raise AssertionError(
                    f"{fold_id}: chips overlap between {left}/{right}")
        if sum(len(rows) for rows in parts.values()) != len(source_rows):
            raise AssertionError(
                f"{fold_id}: source sample loss or duplication")
        if len(event_sets["train"]) != 8 or len(event_sets["valid"]) != 1 or len(event_sets["test"]) != 1:
            raise AssertionError(f"{fold_id}: wrong event-group counts")

        fold_dir = DEST / fold_id
        output_hashes = {}
        for name, rows in parts.items():
            path = fold_dir / f"flood_{name}_data.csv"
            write_csv(path, rows)
            output_hashes[path.name] = sha256_file(path)
        # This is intentionally not a validation/test selection resource.
        bolivia_path = fold_dir / "flood_bolivia_data_LOCKED.csv"
        write_csv(bolivia_path, original["bolivia"])
        output_hashes[bolivia_path.name] = sha256_file(bolivia_path)

        summary = {
            "fold": fold_id,
            "test_event": test_event,
            "validation_event": valid_event,
            "training_events": sorted(event_sets["train"]),
            "image_counts": {key: len(rows) for key, rows in parts.items()},
            "bolivia_locked_images": len(original["bolivia"]),
            "event_overlap": False,
            "chip_overlap": False,
            "output_sha256": output_hashes,
            "note": "Do not use this fold's test event or Bolivia for training, validation, early stopping, or threshold selection.",
        }
        (fold_dir / "manifest.json").write_text(json.dumps(summary,
                                                           indent=2, ensure_ascii=False), encoding="utf-8")
        fold_summaries.append(summary)
        counts = summary["image_counts"]
        print(
            f"{fold_id}: train={counts['train']} (8 events), valid={counts['valid']} ({valid_event}), test={counts['test']} ({test_event}); Bolivia=15 LOCKED; event overlap=0")

    final = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source": str(SOURCE),
        "verified_input_counts": {name: len(rows) for name, rows in original.items()},
        "source_event_counts": dict(sorted(by_event.items())),
        "folds": fold_summaries,
        "research_protocol": [
            "Prespecify architecture, preprocessing, loss, training budget and threshold-selection rules.",
            "Train a fresh model per fold; choose checkpoint and threshold using only that fold's validation event.",
            "Report fixed-model performance on each fold's held-out source event, separately from Bolivia and Thailand.",
            "Bolivia is a previously examined holdout, not a newly blinded external test.",
            "Thailand Phimai is a diagnostic pilot with non-equivalent UNOSAT flood reference, not a surface-water IoU test.",
        ],
    }
    (DEST / "experiment_protocol.json").write_text(json.dumps(final,
                                                              indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"Source event samples: {len(source_rows)} / Bolivia held aside: {len(original['bolivia'])}")
    print(f"Saved event-disjoint fold CSVs to: {DEST}")
    print("IMPORTANT: Your current train_sar_unet.py may still read the OFFICIAL split files.")
    print("Do not start training until its split-directory path is explicitly set and verified.")


if __name__ == "__main__":
    main()
