#!/usr/bin/env python3
"""Quality audit of Sen1Floods11 hand-labeled SAR chips (read-only).

Run from the FloodAI-Research project root:
    python audit_sen1floods11_quality.py

Outputs to results/data_audit/:
    per_image_quality.csv, per_split_summary.csv, per_event_summary.csv,
    potential_spatial_overlap.csv, audit_summary.json

No images or annotations are modified. Uses rasterio + numpy; low RAM.
Spatial overlap screening is based on georeferenced bounding boxes and is
NOT a proof that samples are duplicate or acquired in the same scene.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import transform_bounds

SPLITS = ("train", "valid", "test", "bolivia")
EXPECTED_SPLIT_COUNTS = {"train": 252, "valid": 89, "test": 90, "bolivia": 15}
LABEL_CLASSES = (-1, 0, 1)


def write_csv(path, rows, fieldnames):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def records_from_splits(root):
    records, seen_ids = [], {}
    issues = []
    for split in SPLITS:
        path = root / "splits" / f"flood_{split}_data.csv"
        if not path.is_file():
            issues.append(f"MISSING_SPLIT_FILE: {path}")
            continue
        with path.open(newline="", encoding="utf-8-sig") as f:
            for lineno, row in enumerate(csv.reader(f), 1):
                if not row or not any(x.strip() for x in row):
                    continue
                if len(row) < 2:
                    issues.append(f"INVALID_SPLIT_ROW: {path}:{lineno}")
                    continue
                sar_name, label_name = row[0].strip(), row[1].strip()
                if not sar_name.endswith("_S1Hand.tif") or not label_name.endswith("_LabelHand.tif"):
                    issues.append(
                        f"INVALID_FILENAMES: {split} {sar_name}, {label_name}")
                    continue
                image_id = sar_name.removesuffix("_S1Hand.tif")
                label_id = label_name.removesuffix("_LabelHand.tif")
                if image_id != label_id:
                    issues.append(
                        f"PAIR_NAME_MISMATCH: {split} {sar_name}, {label_name}")
                    continue
                if image_id in seen_ids:
                    issues.append(
                        f"DUPLICATED_IMAGE_ID: {image_id} splits={seen_ids[image_id]},{split}")
                else:
                    seen_ids[image_id] = split
                records.append({
                    "split": split, "event": "Cambodia" if image_id.startswith("Mekong_") else image_id.split("_")[0],
                    "image_id": image_id, "sar_file": root / "S1Hand" / sar_name,
                    "label_file": root / "LabelHand" / label_name,
                })
    return records, issues


def audit_one(r):
    row = {"split": r["split"], "event": r["event"], "image_id": r["image_id"],
           "sar_file": str(r["sar_file"]), "label_file": str(r["label_file"]),
           "height": "", "width": "", "sar_bands": "", "label_bands": "",
           "crs_equal": "", "transform_equal": "", "label_valid_pixels": "",
           "water_pixels": "", "nonwater_pixels": "", "ignore_pixels": "",
           "invalid_sar_pixels": "", "evaluable_pixels": "", "water_fraction_evaluable": "",
           "label_unknown_pixels": "", "all_ignore": False, "no_water_in_evaluable": False,
           "status": "OK", "flags": ""}
    flags = []
    if not r["sar_file"].is_file() or not r["label_file"].is_file():
        flags.append("MISSING_FILE")
        row.update(status="ERROR", flags=";".join(flags))
        return row, None
    try:
        with rasterio.open(r["sar_file"]) as s, rasterio.open(r["label_file"]) as l:
            row.update(height=s.height, width=s.width,
                       sar_bands=s.count, label_bands=l.count)
            if s.count != 2:
                flags.append("EXPECTED_2_SAR_BANDS")
            if l.count != 1:
                flags.append("EXPECTED_1_LABEL_BAND")
            if (s.width, s.height) != (l.width, l.height):
                flags.append("SHAPE_MISMATCH")
            if (s.width, s.height) != (512, 512):
                flags.append("UNEXPECTED_512_SHAPE")
            row["crs_equal"] = bool(s.crs is not None and s.crs == l.crs)
            row["transform_equal"] = bool(
                s.transform.almost_equals(l.transform))
            if not row["crs_equal"]:
                flags.append("CRS_MISMATCH_OR_MISSING")
            if not row["transform_equal"]:
                flags.append("GRID_TRANSFORM_MISMATCH")
            if s.count != 2 or l.count != 1 or (s.width, s.height) != (l.width, l.height):
                row.update(status="ERROR", flags=";".join(flags))
                return row, None
            sar = s.read(out_dtype=np.float32)
            label = l.read(1)
            invalid_sar = ~np.isfinite(sar).all(axis=0)
            if s.nodata is not None and np.isfinite(s.nodata):
                invalid_sar |= (sar == s.nodata).any(axis=0)
            valid_label = np.isin(label, [0, 1])
            valid_joint = valid_label & ~invalid_sar
            water_n = int(((label == 1) & valid_joint).sum())
            nonwater_n = int(((label == 0) & valid_joint).sum())
            evaluable = int(valid_joint.sum())
            unknown_n = int((~np.isin(label, LABEL_CLASSES)).sum())
            row.update(
                label_valid_pixels=int(valid_label.sum()),
                water_pixels=water_n, nonwater_pixels=nonwater_n,
                ignore_pixels=int((label == -1).sum()),
                invalid_sar_pixels=int(invalid_sar.sum()),
                evaluable_pixels=evaluable,
                water_fraction_evaluable=round(
                    water_n / evaluable, 6) if evaluable else "",
                label_unknown_pixels=unknown_n,
                all_ignore=bool(int(valid_label.sum()) == 0),
                no_water_in_evaluable=bool(evaluable > 0 and water_n == 0),
            )
            if unknown_n:
                flags.append("UNKNOWN_LABEL_CODES")
            if evaluable == 0:
                flags.append("ZERO_EVALUABLE_PIXELS")
            if evaluable > 0 and water_n == 0:
                flags.append("NO_WATER_REVIEW_ONLY")
            if evaluable and evaluable / (s.width * s.height) < 0.25:
                flags.append("LOW_VALID_FRACTION_REVIEW_ONLY")
            # Only bounds of the native chip: screening spatial overlap, not pixel duplication.
            bounds = None
            if s.crs is not None:
                try:
                    b = transform_bounds(
                        s.crs, "EPSG:4326", *s.bounds, densify_pts=5)
                    bounds = tuple(float(v) for v in b)
                except Exception:
                    flags.append("BBOX_CONVERSION_FAILED")
            row["status"] = "ERROR" if any(f in flags for f in (
                "CRS_MISMATCH_OR_MISSING", "GRID_TRANSFORM_MISMATCH", "UNKNOWN_LABEL_CODES"
            )) else ("REVIEW" if flags else "OK")
            row["flags"] = ";".join(flags)
            return row, bounds
    except Exception as exc:
        row.update(status="ERROR",
                   flags=f"READ_ERROR: {type(exc).__name__}: {str(exc)[:200]}")
        return row, None


def grouped_summary(rows, group_key):
    groups = defaultdict(list)
    for r in rows:
        groups[r[group_key]].append(r)
    output = []
    for group in sorted(groups):
        items = groups[group]
        valid = sum(int(r["evaluable_pixels"])
                    for r in items if r["evaluable_pixels"] != "")
        water = sum(int(r["water_pixels"])
                    for r in items if r["water_pixels"] != "")
        ignored = sum(int(r["ignore_pixels"])
                      for r in items if r["ignore_pixels"] != "")
        output.append({group_key: group, "images": len(items),
                       "evaluable_pixels": valid, "water_pixels": water,
                       "water_fraction": round(water / valid, 6) if valid else "",
                       "ignore_pixels": ignored,
                       "zero_evaluable_images": sum(int(r["evaluable_pixels"] == 0) for r in items),
                       "errors": sum(r["status"] == "ERROR" for r in items),
                       "review": sum(r["status"] == "REVIEW" for r in items)})
    return output


def intersects(a, b):
    xleft = max(a[0], b[0])
    xright = min(a[2], b[2])
    ylow = max(a[1], b[1])
    yhigh = min(a[3], b[3])
    if xleft >= xright or ylow >= yhigh:
        return 0.0
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return (xright - xleft) * (yhigh - ylow) / max(min(area_a, area_b), 1e-20)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-root", type=Path, default=Path("data/sen1floods11"))
    p.add_argument("--output-dir", type=Path,
                   default=Path("results/data_audit"))
    args = p.parse_args()
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    records, issues = records_from_splits(args.data_root)
    rows, boxes = [], []
    for i, r in enumerate(records, 1):
        audited, bounds = audit_one(r)
        rows.append(audited)
        if bounds is not None:
            boxes.append((r["image_id"], r["event"], r["split"], bounds))
        if i % 100 == 0:
            print(f"Audited {i}/{len(records)} images")
    counts = Counter(r["split"] for r in records)
    for split, count in EXPECTED_SPLIT_COUNTS.items():
        if counts[split] != count:
            issues.append(
                f"SPLIT_COUNT_MISMATCH: {split} actual={counts[split]} expected={count}")
    # Bounding-box overlap flags only for chips from the same event in different splits.
    # Same-event chips being near each other is not necessarily leakage; exact duplication is separate.
    overlaps = []
    for i, (id1, evt1, split1, a) in enumerate(boxes):
        for id2, evt2, split2, b in boxes[i + 1:]:
            if evt1 != evt2 or split1 == split2:
                continue
            fraction = intersects(a, b)
            if fraction > 0.01:
                overlaps.append({"event": evt1, "image_a": id1, "split_a": split1,
                                 "image_b": id2, "split_b": split2,
                                 "intersection_fraction_of_smaller_bbox": round(fraction, 5)})
    columns = ["split", "event", "image_id", "sar_file", "label_file", "height", "width",
               "sar_bands", "label_bands", "crs_equal", "transform_equal", "label_valid_pixels",
               "water_pixels", "nonwater_pixels", "ignore_pixels", "invalid_sar_pixels",
               "evaluable_pixels", "water_fraction_evaluable", "label_unknown_pixels",
               "all_ignore", "no_water_in_evaluable", "status", "flags"]
    write_csv(out / "per_image_quality.csv", rows, columns)
    for key in ("split", "event"):
        srows = grouped_summary(rows, key)
        write_csv(out / f"per_{key}_summary.csv", srows,
                  [key, "images", "evaluable_pixels", "water_pixels", "water_fraction",
                   "ignore_pixels", "zero_evaluable_images", "errors", "review"])
    write_csv(out / "potential_spatial_overlap.csv", overlaps,
              ["event", "image_a", "split_a", "image_b", "split_b",
               "intersection_fraction_of_smaller_bbox"])
    hard_errors = [r for r in rows if r["status"] == "ERROR"]
    no_pixels = [r for r in rows if r["evaluable_pixels"] == 0]
    report = {
        "dataset": "Sen1Floods11 HandLabeled SAR+Label", "split_counts": dict(counts),
        "image_pairs_audited": len(rows), "data_integrity_issues": issues,
        "image_read_or_grid_errors": [r["image_id"] + ": " + r["flags"] for r in hard_errors],
        "zero_evaluable_images": [{"image_id": r["image_id"], "split": r["split"]} for r in no_pixels],
        "potential_cross_split_bbox_overlaps": len(overlaps),
        "event_names_by_split": {s: sorted({r["event"] for r in rows if r["split"] == s}) for s in SPLITS},
        "readiness": "REQUIRES_FIX" if issues or hard_errors else "INTEGRITY_CHECK_PASSED_REVIEW_WARNINGS",
        "limitations": [
            "Cannot prove hand annotation correctness or semantic label quality.",
            "Bbox overlap screen is only a flag; does not prove leakage or duplication.",
            "Train/validation/test from the same event are not independent event-level holdouts.",
            "Zero-evaluable chips must not contribute segmentation metrics or supervised loss."
        ]
    }
    (out / "audit_summary.json").write_text(json.dumps(report,
                                                       ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n=== SEN1FLOODS11 QUALITY AUDIT ===")
    print("Pairs inspected:", len(rows), "; split counts:", dict(counts))
    print("Hard data issues:", len(issues),
          "; read/grid/label errors:", len(hard_errors))
    print("Zero evaluable images:", len(no_pixels), [
          (r["split"], r["image_id"]) for r in no_pixels])
    print("Potential same-event spatial overlaps across splits:", len(overlaps))
    print("Events in each split:", report["event_names_by_split"])
    print("Data integrity status:", report["readiness"])
    print("Saved reports to:", out)
    print("NOTE: Passing integrity checks does not independently validate ground-truth accuracy.")


if __name__ == "__main__":
    main()
