"""Analyse where the model predicts water outside UNOSAT's detected-flood map.

Run from FloodAI-Research project root:
    python check_thailand_disagreement_stats.py

Does not modify any input GeoTIFF, checkpoint, or model parameters.
"""
from pathlib import Path
import argparse
import csv
import numpy as np
import rasterio


def read_band(path):
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    with rasterio.open(path) as ds:
        arr = ds.read(1)
        grid = (ds.height, ds.width, ds.crs, ds.transform)
        nodata = ds.nodata
    return arr, grid, nodata


def check_grid(name, reference, candidate):
    ha, wa, crsa, tra = reference
    hb, wb, crsb, trb = candidate
    if (ha, wa, crsa) != (hb, wb, crsb) or not tra.almost_equals(trb):
        raise ValueError(
            f"Grid mismatch for {name}. Reproject to the SAR grid first.")


def count(mask):
    return int(np.count_nonzero(mask))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".",
                        help="FloodAI-Research project folder")
    args = parser.parse_args()
    root = Path(args.root)
    base = root / "data/thailand_external/2021_10_05"
    masks = base / "masks"
    out = root / "results/sar_unet_baseline_v1/thailand_pilot"

    reference, ref_grid, _ = read_band(masks / "thailand_flood_reference.tif")
    valid, valid_grid, _ = read_band(masks / "thailand_valid_mask.tif")
    pred, pred_grid, _ = read_band(out / "thailand_predicted_water_mask.tif")
    jrc, jrc_grid, _ = read_band(masks / "jrc2020_on_sar_grid.tif")
    for name, grid in [("valid", valid_grid), ("prediction", pred_grid), ("JRC", jrc_grid)]:
        check_grid(name, ref_grid, grid)

    # Same aligned and labeled area as previous comparison, without treating Ignore as dry.
    usable = ((valid == 1) & np.isin(reference, (0, 1))
              & np.isin(pred, (0, 1)))
    groups = {
        "both_flood_and_model_water": usable & (reference == 1) & (pred == 1),
        "unosat_flood_not_predicted_water": usable & (reference == 1) & (pred == 0),
        "model_water_outside_unosat_flood": usable & (reference == 0) & (pred == 1),
        "neither": usable & (reference == 0) & (pred == 0),
    }
    print("=== DISAGREEMENT COUNTS ===")
    for name, mask in groups.items():
        print(f"{name}: {count(mask):,}")
    print(f"Ignored / not evaluable: {count(~usable):,}")

    yellow = groups["model_water_outside_unosat_flood"]
    total_yellow = count(yellow)
    classes = {0: "NoData", 1: "Not water (2020)",
               2: "Seasonal water (2020)", 3: "Permanent water (2020)"}
    print("\n=== YELLOW PIXELS BY JRC 2020 CLASS ===")
    rows = []
    for value, label in classes.items():
        n = count(yellow & (jrc == value))
        pct = 100 * n / total_yellow if total_yellow else 0
        rows.append({"jrc_class": value, "jrc_label": label,
                     "yellow_pixels": n, "yellow_percent": round(pct, 3)})
        print(f"JRC {value} ({label}): {n:,} pixels ({pct:.2f}%)")
    remaining = count(yellow & ~np.isin(jrc, tuple(classes)))
    if remaining:
        print(f"Unexpected JRC categories: {remaining:,}")

    probability_path = out / "thailand_water_probability.tif"
    if probability_path.exists():
        prob, prob_grid, prob_nodata = read_band(probability_path)
        check_grid("probability", ref_grid, prob_grid)
        print("\n=== PROBABILITY DISTRIBUTION BY GROUP ===")
        for name, mask in groups.items():
            mask = mask & np.isfinite(prob)
            if prob_nodata is not None and np.isfinite(prob_nodata):
                mask &= prob != prob_nodata
            values = prob[mask]
            if values.size:
                p10, med, p90 = np.percentile(values, [10, 50, 90])
                print(f"{name}: p10={p10:.3f}, median={med:.3f}, "
                      f"p90={p90:.3f}, fraction>=0.9={(values >= 0.9).mean():.3f}")
    else:
        print("\nProbability GeoTIFF absent; skipped confidence diagnostics.")

    outfile = out / "yellow_jrc_breakdown.csv"
    outfile.parent.mkdir(parents=True, exist_ok=True)
    with outfile.open("w", newline="") as f:
        w = csv.DictWriter(
            f, fieldnames=["jrc_class", "jrc_label", "yellow_pixels", "yellow_percent"])
        w.writeheader()
        w.writerows(rows)
    print("\nSaved:", outfile)
    print("NOTE: JRC class 1 in 2020 does NOT prove that a pixel was dry in Oct 2021.")
    print("NOTE: Model water outside UNOSAT flood is not a confirmed false positive.")


if __name__ == "__main__":
    main()
