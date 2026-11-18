#!/usr/bin/env python3
"""Diagnostic SAR change analysis for Phimai 2021 (not flood ground truth).

Run from ~/Projects/FloodAI-Research after exporting the July and September S1
VV/VH GeoTIFFs to data/thailand_external/2021_10_05/sar/.

Output: per-category delta-VV/VH statistics and diagnostic maps. No model fitting.
"""
from pathlib import Path
import argparse
import csv
import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling
import matplotlib.pyplot as plt


def read_float(src, band):
    a = src.read(band, masked=True).astype("float32").filled(np.nan)
    a[~np.isfinite(a) | (a <= -9990)] = np.nan
    return a


def before_on_event_grid(path, event):
    with rasterio.open(path) as src:
        if src.count < 2:
            raise ValueError(
                f"Expected VV/VH (2 bands) in {path}; got {src.count}")
        if src.crs is None or event.crs is None:
            raise ValueError("Missing georeferencing")
        aligned = (src.width == event.width and src.height == event.height
                   and src.crs == event.crs
                   and src.transform.almost_equals(event.transform))
        result = []
        for band in [1, 2]:
            value = read_float(src, band)
            if aligned:
                result.append(value)
            else:
                dst = np.full((event.height, event.width),
                              np.nan, dtype="float32")
                reproject(
                    source=value, destination=dst,
                    src_transform=src.transform, src_crs=src.crs,
                    src_nodata=np.nan, dst_transform=event.transform,
                    dst_crs=event.crs, dst_nodata=np.nan,
                    resampling=Resampling.bilinear,
                )
                result.append(dst)
    return result


def aligned_mask(path, event):
    with rasterio.open(path) as src:
        if (src.width != event.width or src.height != event.height or
                src.crs != event.crs or
                not src.transform.almost_equals(event.transform)):
            raise ValueError(f"Mask grid does not match event SAR: {path}")
        return src.read(1)


def describe(values):
    if not values.size:
        return {"n": 0, "p10_db": "", "median_db": "", "p90_db": "",
                "pct_delta_vv_le_minus3": ""}
    return dict(n=int(values.size),
                p10_db=round(float(np.percentile(values, 10)), 3),
                median_db=round(float(np.median(values)), 3),
                p90_db=round(float(np.percentile(values, 90)), 3),
                pct_delta_vv_le_minus3=round(float(100*np.mean(values <= -3)), 2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path,
                        default=Path("data/thailand_external/2021_10_05"))
    parser.add_argument("--pilot", type=Path,
                        default=Path("results/sar_unet_baseline_v1/thailand_pilot"))
    args = parser.parse_args()
    sar_dir = args.root / "sar"
    event_path = sar_dir / "Thailand_S1_VV_VH_Sigma0dB.tif"
    before_files = {
        "Oct_minus_Jul13": sar_dir / "Thailand_S1_20210713_VV_VH.tif",
        "Oct_minus_Sep11": sar_dir / "Thailand_S1_20210911_VV_VH.tif",
    }
    ref_path = args.root / "masks/thailand_flood_reference.tif"
    valid_path = args.root / "masks/thailand_valid_mask.tif"
    pred_path = args.pilot / "thailand_predicted_water_mask.tif"
    required = [event_path, *before_files.values(), ref_path,
                valid_path, pred_path]
    missing = [str(f) for f in required if not f.is_file()]
    if missing:
        raise FileNotFoundError("Missing files:\n  " + "\n  ".join(missing))
    args.pilot.mkdir(parents=True, exist_ok=True)
    with rasterio.open(event_path) as event:
        if event.count != 2:
            raise ValueError("Expected 2 event bands, VV and VH")
        during_vv = read_float(event, 1)
        during_vh = read_float(event, 2)
        ref = aligned_mask(ref_path, event)
        valid_ref = aligned_mask(valid_path, event)
        pred = aligned_mask(pred_path, event)
        # Labels correspond to different concepts. Groups describe agreement,
        # NOT TP/FP/FN or accuracy against independent surface-water truth.
        valid = ((valid_ref == 1) & np.isin(ref, [0, 1]) &
                 np.isin(pred, [0, 1]) & np.isfinite(during_vv) &
                 np.isfinite(during_vh))
        groups = {
            "green_UNOSAT_flood_and_model_water": valid & (ref == 1) & (pred == 1),
            "red_UNOSAT_flood_not_model_water": valid & (ref == 1) & (pred == 0),
            "yellow_model_water_outside_UNOSAT": valid & (ref == 0) & (pred == 1),
            "gray_neither": valid & (ref == 0) & (pred == 0),
        }
        print("Event SAR:", event_path.name,
              "shape:", (event.height, event.width))
        print("Valid comparison pixels:", int(valid.sum()))
        print("Group pixels:", {k: int(m.sum()) for k, m in groups.items()})
        output = []
        figures = []
        for label, path in before_files.items():
            bvv, bvh = before_on_event_grid(path, event)
            dvv = during_vv - bvv
            dvh = during_vh - bvh
            complete = valid & np.isfinite(dvv) & np.isfinite(dvh)
            print(f"\n=== {label} ===")
            print("Pixels with both dates (VV & VH):", int(complete.sum()))
            if complete.sum() == 0:
                raise RuntimeError(
                    f"No matching valid before/during pixels: {path}")
            for band_label, delta in [("VV", dvv), ("VH", dvh)]:
                for group_label, gm in groups.items():
                    pixels = delta[complete & gm]
                    stat = describe(pixels)
                    output.append({"comparison": label, "polarization": band_label,
                                   "group": group_label, **stat})
                    print(f"{band_label} | {group_label}: n={stat['n']} "
                          f"median={stat['median_db']} dB, "
                          f"p10={stat['p10_db']}, p90={stat['p90_db']}, "
                          f"share<=-3dB={stat['pct_delta_vv_le_minus3']}%")
                clipped = np.ma.masked_where(~complete, delta)
                figures.append((label, band_label, clipped))
    csv_path = args.pilot / "sar_change_by_disagreement_group.csv"
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(output[0]))
        writer.writeheader()
        writer.writerows(output)
    fig, axes = plt.subplots(2, 2, figsize=(13, 10), constrained_layout=True)
    for ax, (lbl, polarization, arr) in zip(axes.flat, figures):
        img = ax.imshow(arr, cmap="RdBu_r", vmin=-6, vmax=6)
        ax.set_title(f"{lbl.replace('_', ' ')}  Δ{polarization} (dB)")
        ax.axis("off")
    fig.colorbar(img, ax=axes, shrink=0.7, label="After − Before (dB)")
    png_path = args.pilot / "sar_change_vv_vh.png"
    fig.savefig(png_path, dpi=160)
    plt.close(fig)
    print("\nSaved:", csv_path)
    print("Saved:", png_path)
    print("NOTE: These are SAR backscatter-change diagnostics, not independent flood labels.")


if __name__ == "__main__":
    main()
