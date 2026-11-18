#!/usr/bin/env python3
"""Exploratory radiometric diagnostics for all held-out Ghana Sen1Floods11 chips.

Uses existing fixed-threshold inference metrics. This does NOT train or tune a model.
Run from the FloodAI-Research repository root.
"""
import argparse
import csv
from pathlib import Path
import warnings

import numpy as np
import rasterio
import matplotlib.pyplot as plt

FOCUS = {"Ghana_868803", "Ghana_1033830", "Ghana_313799", "Ghana_866994"}


def grid_displacement_px(sar, labels):
    if sar.crs != labels.crs or sar.width != labels.width or sar.height != labels.height:
        return float("inf")
    pts = ((0, 0), (sar.width / 2, sar.height / 2), (sar.width, sar.height))
    distance = []
    inv = ~sar.transform
    for x, y in pts:
        lon, lat = labels.transform * (x, y)
        col, row = inv * (lon, lat)
        distance.append(float(np.hypot(col - x, row - y)))
    return max(distance)


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-root", type=Path,
                    default=Path("data/sen1floods11"))
    ap.add_argument("--metrics-csv", type=Path, default=Path(
        "results/event_level_v1/fold_03_ghana/evaluation/test_per_image.csv"))
    ap.add_argument("--output-dir", type=Path,
                    default=Path("results/event_level_v1/ghana_sar_diagnostics"))
    ap.add_argument("--grid-tolerance-px", type=float, default=0.05)
    ap.add_argument("--max-samples-per-class", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=42)
    return ap.parse_args()


def approximate_low_water_auc(water, land, rng, sample_size):
    """Estimate P(WATER intensity < LAND intensity); 0.5 is uninformative.

    Diagnostic only; NOT the model ROC AUC. Ties contribute 0.5.
    """
    if len(water) == 0 or len(land) == 0:
        return float("nan")
    if len(water) > sample_size:
        water = rng.choice(water, size=sample_size, replace=False)
    if len(land) > sample_size:
        land = rng.choice(land, size=sample_size, replace=False)
    land_sorted = np.sort(land)
    n_greater = len(land_sorted) - \
        np.searchsorted(land_sorted, water, side="right")
    n_equal = np.searchsorted(land_sorted, water, side="right") - \
        np.searchsorted(land_sorted, water, side="left")
    return float(np.mean((n_greater + 0.5 * n_equal) / len(land_sorted)))


def main():
    a = parse_args()
    a.output_dir.mkdir(parents=True, exist_ok=True)
    with a.metrics_csv.open(newline="", encoding="utf-8-sig") as f:
        original = list(csv.DictReader(f))
    if not original:
        raise SystemExit(f"No metric rows found in {a.metrics_csv}")
    needed = {"name", "tp", "fp", "fn", "valid_pixels", "iou", "recall"}
    absent = needed.difference(original[0])
    if absent:
        raise SystemExit(f"Missing columns in metrics CSV: {sorted(absent)}")
    rng = np.random.default_rng(a.seed)
    out = []
    skipped = []
    for i, metric in enumerate(original, 1):
        filename = Path(metric["name"]).name
        stem = filename.removesuffix("_S1Hand.tif")
        if stem == filename:
            skipped.append((filename, "unexpected image filename"))
            continue
        image_path = a.data_root / "S1Hand" / filename
        label_path = a.data_root / "LabelHand" / (stem + "_LabelHand.tif")
        if not image_path.is_file() or not label_path.is_file():
            skipped.append((filename, "missing SAR or label"))
            continue
        with rasterio.open(image_path) as sar, rasterio.open(label_path) as lbl:
            distance = grid_displacement_px(sar, lbl)
            if distance > a.grid_tolerance_px:
                skipped.append(
                    (filename, f"grid mismatch (max displacement {distance:.6g} px)"))
                continue
            if sar.count != 2 or lbl.count != 1:
                skipped.append((filename, "unexpected number of bands"))
                continue
            x = sar.read()
            y = lbl.read(1)
            valid = (np.isfinite(x).all(axis=0) & np.isin(y, [0, 1]))

            if sar.nodata is not None and np.isfinite(sar.nodata):
                valid &= (x != sar.nodata).all(axis=0)

# Do not exclude valid class IDs 0 or 1
# just because they appear in NoData metadata.
            if (lbl.nodata is not None and np.isfinite(lbl.nodata) and lbl.nodata not in (0, 1)):
                valid &= (y != lbl.nodata)
                valid &= (y != lbl.nodata)
            water_mask = valid & (y == 1)
            land_mask = valid & (y == 0)
            nw, nl = int(water_mask.sum()), int(land_mask.sum())
            if nw == 0 or nl == 0:
                skipped.append(
                    (filename, f"missing comparison class (water={nw}, land={nl})"))
                continue
            item = {
                "image": stem,
                "valid_pixels": int(valid.sum()),
                "water_pixels": nw,
                "land_pixels": nl,
                "water_fraction": nw / int(valid.sum()),
                "iou": float(metric["iou"]),
                "recall": float(metric["recall"]),
                "tp": int(metric["tp"]),
                "fp": int(metric["fp"]),
                "fn": int(metric["fn"]),
                "grid_delta_px": distance,
            }
            for band_idx, band in enumerate(("vv", "vh")):
                w = x[band_idx][water_mask]
                l = x[band_idx][land_mask]
                item[f"{band}_water_median"] = float(np.median(w))
                item[f"{band}_land_median"] = float(np.median(l))
                item[f"{band}_delta"] = item[f"{band}_water_median"] - \
                    item[f"{band}_land_median"]
                item[f"{band}_low_water_auc"] = approximate_low_water_auc(
                    w, l, rng, a.max_samples_per_class)
            out.append(item)
        if i % 10 == 0 or i == len(original):
            print(f"Processed {i}/{len(original)} metrics rows")
    if not out:
        raise SystemExit(f"No usable chips. Issues: {skipped[:8]}")
    output_csv = a.output_dir / "ghana_all_image_sar_separability.csv"
    with output_csv.open("w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(out[0]))
        wr.writeheader()
        wr.writerows(out)
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), layout="constrained")
    for ax, band in zip(axes, ("vv", "vh")):
        delta = [r[f"{band}_delta"] for r in out]
        recall = [r["recall"] for r in out]
        scat = ax.scatter(delta, recall, c=[
                          r["water_fraction"] for r in out], cmap="viridis", s=45, alpha=0.85)
        ax.axvline(0, color="gray", linestyle="--", linewidth=1)
        ax.set_xlabel(
            f"{band.upper()} median(water) − median(land) [raw TIFF units]")
        ax.set_ylabel("Fixed-model recall")
        ax.set_title(f"Ghana test: {band.upper()} separation vs recall")
        ax.grid(alpha=0.15)
        for r in out:
            if r["image"] in FOCUS:
                ax.annotate(r["image"].replace("Ghana_", ""), (r[f"{band}_delta"], r["recall"]), fontsize=8, xytext=(
                    3, 4), textcoords="offset points")
    fig.colorbar(
        scat, ax=axes, label="GT water fraction among valid pixels", shrink=0.88)
    output_fig = a.output_dir / "ghana_sar_separation_vs_recall.png"
    fig.savefig(output_fig, dpi=160)
    plt.close(fig)
    print(f"Usable chips: {len(out)}/{len(original)}; skipped: {len(skipped)}")
    for band in ("vv", "vh"):
        positive = sum(r[f"{band}_delta"] > 0 for r in out)
        negative = sum(r[f"{band}_delta"] < 0 for r in out)
        inverted_auc = sum(r[f"{band}_low_water_auc"] < 0.5 for r in out)
        print(f"{band.upper()}: positive median water-land gap {positive}; negative {negative}; low-water AUC < 0.5 for {inverted_auc} images")
    print("Saved:", output_csv)
    print("Saved:", output_fig)
    if skipped:
        issue_file = a.output_dir / "ghana_sar_separation_skipped.csv"
        with issue_file.open("w", newline="") as f:
            wr = csv.writer(f)
            wr.writerow(["image", "reason"])
            wr.writerows(skipped)
        print("WARNING: inspect skips in", issue_file)
    print("NOTE: These are retrospective TEST diagnostics; do not tune a new model using the test labels or test metrics.")


if __name__ == "__main__":
    main()
