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


def inspect_grid(sar_ds, label_ds, stem: str, tolerance_pixels: float = 0.05) -> bool:
    """Report actual GeoTIFF grid metadata and accept only negligible differences.

    True  = grids match up to a small sub-pixel metadata rounding difference.
    False = not safe to claim coordinate alignment without further investigation.
    No reprojection, pixel shifts, or changes to source data are performed.
    """
    same_shape = (sar_ds.width, sar_ds.height) == (
        label_ds.width, label_ds.height)
    print(f"\n=== GRID CHECK: {stem} ===")
    print(
        f"SAR:   shape={sar_ds.height}x{sar_ds.width} bands={sar_ds.count}, CRS={sar_ds.crs}")
    print(
        f"LABEL: shape={label_ds.height}x{label_ds.width} bands={label_ds.count}, CRS={label_ds.crs}")
    print(f"SAR transform:   {tuple(sar_ds.transform)[:6]}")
    print(f"LABEL transform: {tuple(label_ds.transform)[:6]}")
    print(f"SAR bounds:   {tuple(sar_ds.bounds)}")
    print(f"LABEL bounds: {tuple(label_ds.bounds)}")
    print(f"Same size: {same_shape}; Same CRS: {sar_ds.crs == label_ds.crs}")

    if not same_shape:
        print("GRID STATUS: FAIL (different raster dimensions)")
        return False
    if sar_ds.crs is None or label_ds.crs is None:
        print("GRID STATUS: UNVERIFIED (missing CRS; cannot prove geospatial alignment)")
        return False
    if sar_ds.crs != label_ds.crs:
        print("GRID STATUS: FAIL (different coordinate reference systems)")
        return False

    try:
        inverse_sar = ~sar_ds.transform
        # The same labelled pixel corner should map to the same fractional SAR pixel.
        corner_pixels = [(0, 0), (sar_ds.width, 0), (0, sar_ds.height),
                         (sar_ds.width, sar_ds.height),
                         (sar_ds.width / 2, sar_ds.height / 2)]
        shifts = []
        for col, row in corner_pixels:
            x, y = label_ds.transform * (col, row)
            sar_col, sar_row = inverse_sar * (x, y)
            shifts.append(((sar_col - col) ** 2 + (sar_row - row) ** 2) ** 0.5)
        max_delta_px = max(shifts)
    except (ZeroDivisionError, ValueError, OverflowError) as exc:
        print(f"GRID STATUS: UNVERIFIED (invalid transform: {exc})")
        return False

    print(
        f"Maximum corresponding-corner/center displacement: {max_delta_px:.9f} SAR pixels")
    print(f"Pre-set tolerance: {tolerance_pixels:g} pixel")
    if max_delta_px <= tolerance_pixels:
        print("GRID STATUS: PASS (same dimensions, CRS, and within sub-pixel tolerance)")
        return True
    print("GRID STATUS: STOP (different geospatial grids; do NOT ignore/warp labels blindly)")
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path,
                        default=Path("data/sen1floods11"))
    parser.add_argument("--output-dir", type=Path,
                        default=Path("results/event_level_v1/ghana_sar_diagnostics"))
    parser.add_argument("--images", nargs="+", default=list(DEFAULT_IDS),
                        help="Image stems, e.g. Ghana_868803")
    parser.add_argument("--diagnose-only", action="store_true",
                        help="Print grid diagnostics for all selected images without making plots")
    parser.add_argument("--grid-tolerance-pixels", type=float, default=0.05,
                        help="Max corner/center displacement in SAR pixels allowed for rounding-only mismatch (default: 0.05)")
    args = parser.parse_args()
    if args.grid_tolerance_pixels < 0 or args.grid_tolerance_pixels > 0.1:
        parser.error(
            "Tolerance must be between 0 and 0.1 pixel; larger mismatches require separate alignment audit")

    if not args.diagnose_only:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        fig, axes = plt.subplots(len(args.images), 2, figsize=(
            13, 3.4 * len(args.images)), squeeze=False)
    else:
        fig, axes = None, None
    failed_grid_ids = []
    output_rows = []

    for idx, stem in enumerate(args.images):
        sar_path = args.data_root / "S1Hand" / f"{stem}_S1Hand.tif"
        label_path = args.data_root / "LabelHand" / f"{stem}_LabelHand.tif"
        for path in (sar_path, label_path):
            if not path.exists():
                raise FileNotFoundError(
                    f"Cannot find {path}. Run from FloodAI-Research project root and check --data-root.")

        with rasterio.open(sar_path) as sar_ds, rasterio.open(label_path) as label_ds:
            if sar_ds.count != 2:
                raise ValueError(
                    f"Expected VV + VH (2 bands): {sar_path}, got {sar_ds.count}")
            if label_ds.count != 1:
                raise ValueError(f"Expected single-band label: {label_path}")
            grid_ok = inspect_grid(
                sar_ds, label_ds, stem, args.grid_tolerance_pixels)
            if not grid_ok:
                failed_grid_ids.append(stem)
                if args.diagnose_only:
                    continue
                raise ValueError(
                    f"Alignment not verified: {stem}. Run with --diagnose-only and share the GRID CHECK output. No source data were modified.")
            if args.diagnose_only:
                continue
            sar = sar_ds.read().astype("float64")
            sar_nodata = sar_ds.nodata
            label = label_ds.read(1)

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

    if args.diagnose_only:
        print("\n=== DIAGNOSTIC SUMMARY ===")
        if failed_grid_ids:
            print("Images requiring an alignment audit:",
                  ", ".join(failed_grid_ids))
            print(
                "STOP: Do not interpret label-conditioned SAR distributions for these images yet.")
        else:
            print("All selected image grids match within the configured small tolerance.")
        return

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
