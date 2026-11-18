#!/usr/bin/env python3
"""Exploratory SAR distribution comparison for event-disjoint Sen1Floods11 folds.

Reads the event-level split CSVs, checks SAR/label alignment, and samples pixel
values for descriptive distributions. Does not train, tune, or evaluate a model.

Label convention: 0=land, 1=water, -1=ignore. Some Sen1Floods11 GeoTIFFs
incorrectly advertise nodata=0; those pixels MUST NOT be excluded on that basis.
"""
from __future__ import annotations
import rasterio
import numpy as np
import matplotlib.pyplot as plt

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

SPLITS = ("train", "valid", "test")
BANDS = ("vv", "vh")
CLASSES = ("land", "water")


def locate_records(root: Path, split: str) -> list[tuple[str, Path, Path]]:
    csv_path = root / "splits" / f"flood_{split}_data.csv"
    if not csv_path.is_file():
        raise FileNotFoundError(f"Missing split file: {csv_path}")
    records = []
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        for lineno, row in enumerate(reader, start=1):
            if not row or all(not c.strip() for c in row):
                continue
            filenames = [Path(c.strip().strip(
                '"').strip("'")).name for c in row]
            sar_names = [
                name for name in filenames if name.endswith("_S1Hand.tif")]
            if not sar_names:
                # Header lines such as image,label are allowed.
                if lineno == 1:
                    continue
                raise ValueError(
                    f"Cannot find _S1Hand.tif in {csv_path}:{lineno}: {row!r}")
            sar_name = sar_names[0]
            stem = sar_name.removesuffix("_S1Hand.tif")
            label_matches = [
                name for name in filenames if name.endswith("_LabelHand.tif")]
            label_name = label_matches[0] if label_matches else stem + \
                "_LabelHand.tif"
            sar_path = root / "S1Hand" / sar_name
            label_path = root / "LabelHand" / label_name
            records.append((stem, sar_path, label_path))
    if not records:
        raise ValueError(f"No SAR chip paths found in {csv_path}")
    return records


def max_grid_shift_in_pixels(sar: rasterio.io.DatasetReader, lbl: rasterio.io.DatasetReader) -> float:
    if (sar.width, sar.height) != (lbl.width, lbl.height) or sar.crs != lbl.crs:
        return float("inf")
    # Same CRS; compare corresponding pixel center/corners using SAR pixel sizes.
    pts = ((0, 0), (sar.width, 0), (0, sar.height),
           (sar.width, sar.height), (sar.width / 2, sar.height / 2))
    px_x = np.hypot(sar.transform.a, sar.transform.d)
    px_y = np.hypot(sar.transform.b, sar.transform.e)
    denom = max(min(px_x, px_y), 1e-15)
    return max(
        float(np.hypot(*(np.asarray(sar.transform * (col, row)) -
                         np.asarray(lbl.transform * (col, row))))) / denom
        for col, row in pts
    )


def median(x: np.ndarray) -> float:
    return float(np.median(x)) if x.size else float("nan")


def choose(arr: np.ndarray, rng: np.random.Generator, cap: int) -> np.ndarray:
    if arr.size <= cap:
        return arr.astype(np.float32, copy=True)
    indices = rng.choice(arr.size, size=cap, replace=False)
    return arr[indices].astype(np.float32, copy=True)


def event_of(stem: str) -> str:
    prefix = stem.split("_", 1)[0]
    return "Cambodia" if prefix == "Mekong" else prefix


def write_rows(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def chart_distributions(path: Path, event_arrays: dict, rng: np.random.Generator,
                        max_per_event: int) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(13, 8), constrained_layout=True)
    colors = {"train": "#4063a0", "valid": "#dc9229", "test": "#178b83"}
    for i, band in enumerate(BANDS):
        for j, cls in enumerate(CLASSES):
            ax = axes[i, j]
            arrays_by_split: dict[str, list[np.ndarray]] = defaultdict(list)
            for (split, event, k_band, k_cls), chunks in event_arrays.items():
                if k_band != band or k_cls != cls or not chunks:
                    continue
                combined = np.concatenate(chunks)
                arrays_by_split[split].append(
                    choose(combined, rng, max_per_event))
            for split in SPLITS:
                items = arrays_by_split.get(split, [])
                if not items:
                    continue
                values = np.concatenate(items)
                if values.size:
                    ax.hist(values, bins=65, density=True, alpha=0.42,
                            color=colors[split], label=f"{split}: {len(items)} event(s)")
            ax.set_title(f"{band.upper()} — Ground-truth {cls}")
            ax.set_xlabel(
                "Raw SAR TIFF value (confirm units and preprocessing)")
            ax.set_ylabel("Sampled pixel density")
            ax.legend(fontsize=8)
    fig.suptitle(
        "Fold 3: Class-conditional SAR distributions (exploratory)", fontsize=14)
    fig.savefig(path, dpi=160)
    plt.close(fig)


def chart_events(path: Path, summaries: list[dict]) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13, max(5, len(summaries) * .39)),
                             constrained_layout=True)
    orders = sorted(summaries, key=lambda r: (
        SPLITS.index(r["split"]), r["event"]))
    labels = [f'{r["split"]}: {r["event"]}' for r in orders]
    colors = {"train": "#4063a0", "valid": "#dc9229", "test": "#178b83"}
    for ax, band in zip(axes, BANDS):
        for y, row in enumerate(orders):
            delta = row[f"{band}_water_minus_land_median"]
            if not np.isnan(delta):
                ax.scatter(delta, y, s=50, c=colors[row["split"]])
        ax.axvline(0, color="0.45", linewidth=1, linestyle="--")
        ax.set_title(f"{band.upper()} median(water) − median(land)")
        ax.set_yticks(range(len(labels)), labels)
        ax.set_xlabel("Raw SAR TIFF units")
        ax.grid(axis="x", alpha=.15)
        ax.invert_yaxis()
    fig.suptitle(
        "Per-event SAR separation — class-conditional sampled medians", fontsize=13)
    fig.savefig(path, dpi=160)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-root", type=Path,
                    default=Path("data/sen1floods11/event_level_roots/fold_03_ghana"))
    ap.add_argument("--output-dir", type=Path,
                    default=Path("results/event_level_v1/cross_domain_fold03"))
    ap.add_argument("--sample-per-chip-class", type=int, default=800)
    ap.add_argument("--max-samples-per-event", type=int, default=3000)
    ap.add_argument("--grid-tolerance-px", type=float, default=0.05)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    if args.sample_per_chip_class < 1 or args.max_samples_per_event < 1:
        ap.error("Sample limits must be positive")
    outdir = args.output_dir
    outdir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.seed)

    split_records = {s: locate_records(args.data_root, s) for s in SPLITS}
    print("=== FOLD 3 SPLITS ===")
    for split, rows in split_records.items():
        print(
            f"{split}: {len(rows)} chips; events: {sorted({event_of(r[0]) for r in rows})}")
    names_by_split = {s: {r[0] for r in rows}
                      for s, rows in split_records.items()}
    for i, a in enumerate(SPLITS):
        for b in SPLITS[i + 1:]:
            overlap = names_by_split[a] & names_by_split[b]
            if overlap:
                raise ValueError(
                    f"Duplicate chip names across {a}/{b}: {sorted(overlap)[:4]}")
    events_by_split = {s: {event_of(r[0]) for r in rows}
                       for s, rows in split_records.items()}
    for i, a in enumerate(SPLITS):
        for b in SPLITS[i + 1:]:
            overlap = events_by_split[a] & events_by_split[b]
            if overlap:
                raise ValueError(
                    f"Event leakage between {a}/{b}: {sorted(overlap)}")
    print("PASS: No event overlap across train/valid/test in this fold.")

    chip_rows = []
    bad_rows = []
    # Sampled pixel values are keyed per event, band, class; chips are bounded.
    event_arrays: dict[tuple[str, str, str, str],
                       list[np.ndarray]] = defaultdict(list)
    total = sum(map(len, split_records.values()))
    done = 0

    for split in SPLITS:
        for stem, sar_path, label_path in split_records[split]:
            done += 1
            event = event_of(stem)
            if not sar_path.is_file() or not label_path.is_file():
                bad_rows.append({"split": split, "event": event,
                                "image": stem, "reason": "missing SAR or label"})
                continue
            try:
                with rasterio.open(sar_path) as sar, rasterio.open(label_path) as lbl:
                    if sar.count != 2 or lbl.count != 1:
                        bad_rows.append(
                            {"split": split, "event": event, "image": stem, "reason": "unexpected band count"})
                        continue
                    shift = max_grid_shift_in_pixels(sar, lbl)
                    if shift > args.grid_tolerance_px:
                        bad_rows.append(
                            {"split": split, "event": event, "image": stem, "reason": f"grid shift {shift:.6g} px"})
                        continue
                    x = sar.read().astype(np.float32)
                    y = lbl.read(1)
                    valid = np.isfinite(x).all(axis=0) & np.isin(y, (0, 1))
                    if sar.nodata is not None and np.isfinite(sar.nodata):
                        valid &= (x != sar.nodata).all(axis=0)
                    # IMPORTANT: label nodata=0 conflicts with the known land class.
                    # Respect explicit nonclass nodata sentinels but never remove class 0 or 1.
                    if lbl.nodata is not None and np.isfinite(lbl.nodata) and lbl.nodata not in (0, 1):
                        valid &= y != lbl.nodata
                    n_valid = int(valid.sum())
                    if n_valid == 0:
                        bad_rows.append(
                            {"split": split, "event": event, "image": stem, "reason": "no evaluable pixels"})
                        continue
                    water = valid & (y == 1)
                    land = valid & (y == 0)
                    n_water, n_land = int(water.sum()), int(land.sum())
                    item = {"split": split, "event": event, "image": stem,
                            "grid_displacement_px": shift,
                            "valid_pixels": n_valid, "water_pixels": n_water,
                            "land_pixels": n_land, "ignore_or_invalid_pixels": y.size - n_valid,
                            "water_fraction_valid": n_water / n_valid}
                    for idx, band in enumerate(BANDS):
                        for cls, mask in (("land", land), ("water", water)):
                            values = x[idx][mask]
                            item[f"{band}_{cls}_median"] = median(values)
                            if values.size:
                                event_arrays[(split, event, band, cls)].append(
                                    choose(values, rng, args.sample_per_chip_class))
                        wmed = item[f"{band}_water_median"]
                        lmed = item[f"{band}_land_median"]
                        item[f"{band}_water_minus_land_median"] = wmed - lmed
                    chip_rows.append(item)
            except (OSError, rasterio.errors.RasterioError, ValueError) as exc:
                bad_rows.append({"split": split, "event": event,
                                "image": stem, "reason": str(exc)[:300]})
            if done % 50 == 0 or done == total:
                print(f"Read {done}/{total} chips")

    chip_fields = ["split", "event", "image", "grid_displacement_px", "valid_pixels",
                   "water_pixels", "land_pixels", "ignore_or_invalid_pixels", "water_fraction_valid"]
    for band in BANDS:
        chip_fields += [f"{band}_land_median",
                        f"{band}_water_median", f"{band}_water_minus_land_median"]
    write_rows(outdir / "sar_chip_summary.csv", chip_rows, chip_fields)
    write_rows(outdir / "sar_skipped_chips.csv", bad_rows,
               ["split", "event", "image", "reason"])

    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in chip_rows:
        grouped[(r["split"], r["event"])].append(r)
    summaries = []
    for (split, event), rows in sorted(grouped.items(), key=lambda e: (SPLITS.index(e[0][0]), e[0][1])):
        nvalid = sum(r["valid_pixels"] for r in rows)
        nwater = sum(r["water_pixels"] for r in rows)
        item = {"split": split, "event": event, "n_chips": len(rows),
                "valid_pixels": nvalid, "water_pixels": nwater,
                "water_fraction_pooled": nwater / nvalid if nvalid else float("nan"),
                "mean_chip_water_fraction": float(np.mean([r["water_fraction_valid"] for r in rows]))}
        for band in BANDS:
            for cls in CLASSES:
                chunks = event_arrays.get((split, event, band, cls), [])
                a = np.concatenate(chunks) if chunks else np.array(
                    [], dtype=np.float32)
                sample = choose(
                    a, rng, args.max_samples_per_event) if a.size else a
                item[f"{band}_{cls}_sample_count"] = int(sample.size)
                item[f"{band}_{cls}_median_sample"] = median(sample)
            item[f"{band}_water_minus_land_median"] = (
                item[f"{band}_water_median_sample"] - item[f"{band}_land_median_sample"])
        summaries.append(item)
    event_fields = ["split", "event", "n_chips", "valid_pixels", "water_pixels",
                    "water_fraction_pooled", "mean_chip_water_fraction"]
    for band in BANDS:
        for cls in CLASSES:
            event_fields.extend(
                [f"{band}_{cls}_sample_count", f"{band}_{cls}_median_sample"])
        event_fields.append(f"{band}_water_minus_land_median")
    write_rows(outdir / "sar_event_summary.csv", summaries, event_fields)
    chart_distributions(outdir / "sar_distributions_by_split.png", event_arrays, rng,
                        args.max_samples_per_event)
    chart_events(outdir / "sar_water_land_delta_by_event.png", summaries)

    print("\n=== COVERAGE ===")
    for split in SPLITS:
        requested = len(split_records[split])
        usable = sum(r["split"] == split for r in chip_rows)
        failures = requested - usable
        print(f"{split}: {usable}/{requested} processed; {failures} skipped")
    print("\n=== PER EVENT ===")
    for r in summaries:
        print(f'{r["split"]:5s} {r["event"]:12s} chips={r["n_chips"]:3d} '
              f'water_frac={r["water_fraction_pooled"]:6.2%} '
              f'VV_delta={r["vv_water_minus_land_median"]:+7.3f} '
              f'VH_delta={r["vh_water_minus_land_median"]:+7.3f}')
    print(f"\nSaved to: {outdir}")
    print("Files: sar_chip_summary.csv, sar_event_summary.csv, sar_skipped_chips.csv,")
    print("       sar_distributions_by_split.png, sar_water_land_delta_by_event.png")
    print("NOTE: Diagnostic distributions only. Not model normalization or evidence of causality.")
    print("NOTE: Raw units must be verified and model input normalization audited separately.")
    print("NOTE: The training pool combines 8 events; inspect per-event rows, not just pooled plots.")


if __name__ == "__main__":
    main()
