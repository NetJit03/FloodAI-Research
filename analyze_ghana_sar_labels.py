#!/usr/bin/env python3
"""Exploratory (read-only) comparison of raw SAR VV/VH values vs Sen1Floods11 labels.

Purpose: understand class-conditional SAR distributions for selected Ghana cases.
This script never modifies the model, thresholds, ground-truth labels or original data.
The figures are descriptive and cannot independently validate the labels.
"""
from __future__ import annotations
import rasterio
import numpy as np
import matplotlib.pyplot as plt

import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

DEFAULT_IDS = (
    "Ghana_868803",   # largest FN count
    "Ghana_1033830",  # second-largest FN count
    "Ghana_313799",   # near-zero recall example
    "Ghana_866994",   # comparatively well-segmented control
)


def describe(values: np.ndarray) -> dict:
    if not len(values):
        return {"n": 0, "p10": float("nan"), "median": float("nan"), "p90": float("nan")}
    q10, med, q90 = np.percentile(values, [10, 50, 90])
    return {"n": int(values.size), "p10": float(q10), "median": float(med), "p90": float(q90)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path,
                        default=Path("data/sen1floods11"))
    parser.add_argument("--output-dir", type=Path,
                        default=Path("results/event_level_v1/ghana_sar_diagnostics"))
    parser.add_argument("--images", nargs="+", default=list(DEFAULT_IDS),
                        help="Image stems, e.g. Ghana_868803")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(len(args.images), 2, figsize=(
        13, 3.4 * len(args.images)), squeeze=False)
    output_rows = []

    for idx, stem in enumerate(args.images):
        sar_path = args.data_root / "S1Hand" / f"{stem}_S1Hand.tif"
        label_path = args.data_root / "LabelHand" / f"{stem}_LabelHand.tif"
        for path in (sar_path, label_path):
            if not path.exists():
                raise FileNotFoundError(
                    f"Cannot find {path}. Run from FloodAI-Research project root and check --data-root.")

        with rasterio.open(sar_path) as ds:
            if ds.count != 2:
                raise ValueError(
                    f"Expected VV + VH (2 bands): {sar_path}, got {ds.count}")
            sar = ds.read().astype("float64")
            sar_nodata = ds.nodata
            sar_crs, sar_transform = ds.crs, ds.transform
        with rasterio.open(label_path) as ds:
            if ds.count != 1:
                raise ValueError(f"Expected single-band label: {label_path}")
            label = ds.read(1)
            if ds.crs != sar_crs or ds.transform != sar_transform:
                raise ValueError(f"SAR/label grid mismatch: {stem}")

        if sar.shape[1:] != label.shape:
            raise ValueError(f"SAR/label shape mismatch: {stem}")
        if not np.isin(np.unique(label), [-1, 0, 1]).all():
            raise ValueError(
                f"Unexpected label values for {stem}: {np.unique(label)}")

        finite = np.isfinite(sar).all(axis=0)
        if sar_nodata is not None and np.isfinite(sar_nodata):
            finite &= (sar != sar_nodata).all(axis=0)
        usable = finite & np.isin(label, [0, 1])
        wet = usable & (label == 1)
        dry = usable & (label == 0)
        n_valid = int(usable.sum())
        n_wet = int(wet.sum())
        n_dry = int(dry.sum())
        print(f"\n{stem}: evaluable={n_valid:,} water={n_wet:,} ({100 * n_wet / n_valid if n_valid else float('nan'):.2f}%) land={n_dry:,}")
        if n_valid == 0:
            raise ValueError(f"No valid pixels in {stem}")

        for band_idx, band in enumerate(("VV", "VH")):
            ax = axes[idx, band_idx]
            water_values = sar[band_idx, wet]
            land_values = sar[band_idx, dry]
            wt_stats, ld_stats = describe(water_values), describe(land_values)
            diff = wt_stats["median"] - ld_stats["median"]
            print(
                f"  {band} median water={wt_stats['median']:.3f}, land={ld_stats['median']:.3f}, delta={diff:+.3f} (raw TIFF units)")
            for class_name, stats in (("water", wt_stats), ("land", ld_stats)):
                output_rows.append({
                    "image": stem, "band": band, "class": class_name,
                    "evaluable_pixels": n_valid, "water_fraction": n_wet / n_valid,
                    "n": stats["n"], "p10": stats["p10"],
                    "median": stats["median"], "p90": stats["p90"],
                    "water_minus_land_median": diff,
                })

            if n_wet and n_dry:
                combined = np.concatenate([water_values, land_values])
                lo, hi = np.percentile(combined, [1, 99])
                if lo >= hi:
                    lo, hi = float(np.min(combined)), float(np.max(combined))
                if lo < hi:
                    bins = np.linspace(lo, hi, 65)
                    ax.hist(land_values, bins=bins, density=True,
                            alpha=0.5, label="Label 0: land", color="gray")
                    ax.hist(water_values, bins=bins, density=True,
                            alpha=0.5, label="Label 1: water", color="tab:blue")
                else:
                    ax.text(0.5, 0.5, "Constant SAR values",
                            transform=ax.transAxes, ha="center")
            else:
                ax.text(0.5, 0.5, "Only one labeled class",
                        transform=ax.transAxes, ha="center")
            ax.set_title(
                f"{stem} — {band}\nWater − land median: {diff:+.2f}", fontsize=10)
            ax.set_xlabel("Raw SAR TIFF values (verify units/preprocessing)")
            ax.set_ylabel("Pixel density")
            ax.grid(alpha=0.15)
            if idx == 0 and n_wet and n_dry:
                ax.legend(fontsize=9)

    fig.suptitle(
        "Ghana: raw VV/VH distributions by Ground Truth class (exploratory)", fontsize=14)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    plot_path = args.output_dir / "ghana_class_conditional_sar.png"
    fig.savefig(plot_path, dpi=160, bbox_inches="tight")
    plt.close(fig)

    csv_path = args.output_dir / "ghana_class_conditional_sar.csv"
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(output_rows[0]))
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"\nSaved CSV: {csv_path}\nSaved figure: {plot_path}")
    print("NOTE: This analysis uses existing test labels for error diagnosis only. Do not tune a model using these test results.")


if __name__ == "__main__":
    main()
