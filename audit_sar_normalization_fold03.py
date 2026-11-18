#!/usr/bin/env python3
"""Exploratory, read-only audit of the fixed VV/VH normalization in Fold 3.

Matches train_sar_unet.py normalization:
VV: [-35, +5], VH: [-40, 0]; finite SAR values with any finite
SAR NoData sentinel removed; label -1 excluded, 0=land, 1=water.

No model fitting, inference, checkpoint modification or threshold tuning.
Usage:
  python audit_sar_normalization_fold03.py \
    --data-root data/sen1floods11/event_level_roots/fold_03_ghana \
    --output-dir results/event_level_v1/normalization_audit_fold03
"""

import argparse
import csv
from collections import Counter, defaultdict
from contextlib import ExitStack
from pathlib import Path

import numpy as np
import rasterio

DB_LIMITS = {"VV": (-35.0, 5.0), "VH": (-40.0, 0.0)}
SPLITS = ("train", "valid", "test")
CSV_FIELDS = [
    "split", "event", "image", "polarization", "class", "n_pixels",
    "below_min", "above_max", "clipped_total", "pct_below_min",
    "pct_above_max", "pct_clipped_total", "raw_min", "raw_max"
]


def safe_pct(num, den):
    return 100.0 * num / den if den else float("nan")


def normalized_event(stem):
    prefix = stem.split("_")[0]
    return "Cambodia" if prefix == "Mekong" else prefix


def records(root, split):
    file = root / "splits" / f"flood_{split}_data.csv"
    if not file.exists():
        raise FileNotFoundError(f"Split CSV missing: {file}")
    items = []
    with file.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.reader(f):
            if not row or not any(cell.strip() for cell in row):
                continue
            if len(row) < 2:
                raise ValueError(
                    f"Expected SAR,label columns in {file}: {row}")
            sarname, labelname = Path(
                row[0].strip()).name, Path(row[1].strip()).name
            if not (sarname.endswith("_S1Hand.tif") and labelname.endswith("_LabelHand.tif")):
                # Accept header row (if present), not arbitrary bad records.
                if sarname.lower() in {"image", "image_path", "sar", "s1hand"}:
                    continue
                raise ValueError(f"Unexpected filenames in {file}: {row}")
            prefix = sarname.removesuffix("_S1Hand.tif")
            if labelname != prefix + "_LabelHand.tif":
                raise ValueError(f"Mismatched SAR/Label pair in {file}: {row}")
            image = root / "S1Hand" / sarname
            label = root / "LabelHand" / labelname
            if not image.is_file() or not label.is_file():
                raise FileNotFoundError(f"Files missing: {image} | {label}")
            items.append((prefix, image, label))
    if not items:
        raise ValueError(f"No records for {split} in {file}")
    return items


def check_grid(sar, lbl, name):
    if sar.width != lbl.width or sar.height != lbl.height or sar.crs != lbl.crs:
        raise ValueError(f"GRID MISMATCH (shape/CRS): {name}")
    delta = ~sar.transform * lbl.transform
    points = [(0, 0), (sar.width, 0), (0, sar.height), (sar.width, sar.height)]
    displacements = [np.hypot(*(np.array(delta * (c, r)) - [c, r]))
                     for c, r in points]
    if max(displacements) > 0.05:
        raise ValueError(
            f"GRID MISMATCH ({max(displacements):.5g} pixels): {name}")


def make_row(split, event, name, pol, cls, vals, low, high):
    n = int(vals.size)
    below = int(np.count_nonzero(vals < low))
    above = int(np.count_nonzero(vals > high))
    return dict(split=split, event=event, image=name, polarization=pol,
                **{"class": cls}, n_pixels=n, below_min=below, above_max=above,
                clipped_total=below + above,
                pct_below_min=safe_pct(below, n),
                pct_above_max=safe_pct(above, n),
                pct_clipped_total=safe_pct(below + above, n),
                raw_min=float(vals.min()) if n else float("nan"),
                raw_max=float(vals.max()) if n else float("nan"))


def aggregate(rows, keys):
    counts = defaultdict(lambda: Counter())
    for row in rows:
        key = tuple(row[k] for k in keys)
        for name in ("n_pixels", "below_min", "above_max", "clipped_total"):
            counts[key][name] += row[name]
    out = []
    for key, v in sorted(counts.items()):
        record = dict(zip(keys, key))
        record.update({n: int(v[n]) for n in (
            "n_pixels", "below_min", "above_max", "clipped_total")})
        n = v["n_pixels"]
        record.update(pct_below_min=safe_pct(v["below_min"], n),
                      pct_above_max=safe_pct(v["above_max"], n),
                      pct_clipped_total=safe_pct(v["clipped_total"], n))
        out.append(record)
    return out


def write_csv(path, rows, fields):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row.get(field)
                         for field in fields} for row in rows)


def plot_events(event_rows, output_dir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    for pol in ("VV", "VH"):
        rows = [r for r in event_rows if r["polarization"]
                == pol and r["class"] == "evaluable"]
        rows.sort(key=lambda r: (SPLITS.index(r["split"]), r["event"]))
        if not rows:
            continue
        y = np.arange(len(rows))
        fig, ax = plt.subplots(figsize=(10, max(4.5, 0.52 * len(rows))))
        below = np.array([r["pct_below_min"] for r in rows])
        above = np.array([r["pct_above_max"] for r in rows])
        ax.barh(y, below, label="Below lower bound")
        ax.barh(y, above, left=below, label="Above upper bound")
        ax.set_yticks(y, [f"{r['split']}: {r['event']}" for r in rows])
        ax.invert_yaxis()
        ax.set_xlabel("Clipped share of evaluable pixels (%)")
        low, high = DB_LIMITS[pol]
        ax.set_title(
            f"Fold 3: {pol} clipping by event (range [{low:g}, {high:g}])")
        ax.legend()
        ax.grid(axis="x", alpha=0.25)
        fig.tight_layout()
        target = output_dir / f"{pol.lower()}_clipping_by_event.png"
        fig.savefig(target, dpi=170)
        plt.close(fig)
        print("Saved figure:", target)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-root", type=Path,
                    default=Path("data/sen1floods11/event_level_roots/fold_03_ghana"))
    ap.add_argument("--output-dir", type=Path,
                    default=Path("results/event_level_v1/normalization_audit_fold03"))
    a = ap.parse_args()
    per_image = []
    all_records = {}
    for split in SPLITS:
        all_records[split] = records(a.data_root, split)
    event_sets = {split: {normalized_event(name) for name, *_ in recs}
                  for split, recs in all_records.items()}
    for i, s1 in enumerate(SPLITS):
        for s2 in SPLITS[i+1:]:
            common = event_sets[s1] & event_sets[s2]
            if common:
                raise ValueError(f"EVENT LEAKAGE: {s1}/{s2}: {sorted(common)}")
    print("=== FOLD 3 NORMALIZATION / CLIPPING AUDIT ===")
    print("Ranges:", DB_LIMITS)
    print("Split sizes:", {s: len(v) for s, v in all_records.items()})
    print("Independent events:", {s: sorted(v) for s, v in event_sets.items()})
    for split, recs in all_records.items():
        for i, (name, sar_path, label_path) in enumerate(recs, 1):
            with rasterio.open(sar_path) as sar, rasterio.open(label_path) as label:
                check_grid(sar, label, name)
                if sar.count != 2 or label.count != 1:
                    raise ValueError(f"Unexpected band count: {name}")
                x = sar.read(out_dtype="float32")
                y = label.read(1)
                if not np.isin(y, [-1, 0, 1]).all():
                    raise ValueError(f"Unexpected label class: {name}")
                valid_sar = np.isfinite(x).all(axis=0)
                if sar.nodata is not None and np.isfinite(sar.nodata):
                    valid_sar &= (x != sar.nodata).all(axis=0)
                # The actual model treats label 0=land, label 1=water, -1=ignore,
                # regardless of a conflicting label TIFF NoData=0 metadata flag.
                evaluable = valid_sar & (y != -1)
                masks = {"evaluable": evaluable,
                         "land": evaluable & (y == 0),
                         "water": evaluable & (y == 1)}
                event = normalized_event(name)
                for bandidx, pol in enumerate(("VV", "VH")):
                    low, high = DB_LIMITS[pol]
                    for cls, mask in masks.items():
                        per_image.append(make_row(split, event, name, pol, cls,
                                                  x[bandidx][mask], low, high))
            if i % 50 == 0 or i == len(recs):
                print(f"{split}: audited {i}/{len(recs)} chips")
    a.output_dir.mkdir(parents=True, exist_ok=True)
    event_rows = aggregate(
        per_image, ["split", "event", "polarization", "class"])
    split_rows = aggregate(per_image, ["split", "polarization", "class"])
    group_fields = ["n_pixels", "below_min", "above_max", "clipped_total",
                    "pct_below_min", "pct_above_max", "pct_clipped_total"]
    paths = [
        (a.output_dir / "clipping_per_image.csv", per_image, CSV_FIELDS),
        (a.output_dir / "clipping_by_event.csv", event_rows,
         ["split", "event", "polarization", "class"] + group_fields),
        (a.output_dir / "clipping_by_split.csv", split_rows,
         ["split", "polarization", "class"] + group_fields),
    ]
    for path, rows, fields in paths:
        write_csv(path, rows, fields)
        print("Saved:", path)
    print("\n=== PER-SPLIT CLIPPING (EVALUABLE PIXELS) ===")
    for row in split_rows:
        if row["class"] == "evaluable":
            print(f"{row['split']:5} {row['polarization']}: "
                  f"n={row['n_pixels']:,}, below={row['pct_below_min']:.3f}%, "
                  f"above={row['pct_above_max']:.3f}%, "
                  f"total={row['pct_clipped_total']:.3f}%")
    print("\n=== WATER / LAND CLASS-SPECIFIC CLIPPING ===")
    for row in split_rows:
        if row["class"] in ("water", "land"):
            print(f"{row['split']:5} {row['polarization']} {row['class']:5}: "
                  f"n={row['n_pixels']:,}, total={row['pct_clipped_total']:.3f}%")
    plot_events(event_rows, a.output_dir)
    print("\nNOTE: Descriptive audit only. Keep test results separate from model tuning.")
    print("NOTE: These shares count input values strictly BELOW/ABOVE fixed clipping bounds.")
    print("NOTE: 'evaluable' excludes SAR invalid and label -1; label NoData metadata=0 is ignored.")


if __name__ == "__main__":
    main()
