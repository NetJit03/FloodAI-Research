#!/usr/bin/env python3
"""M6.4A: Fixed-checkpoint, retrospective calibration diagnostics for Sen1Floods11.

Run from the FloodAI-Research repository root, alongside train_sar_unet.py.
This script NEVER trains, fits calibration parameters, or selects a threshold.

Example:
    python audit_sar_calibration_fold03.py \
      --checkpoint results/event_level_v1/fold_03_ghana/best_sar_unet.pt \
      --data-root data/sen1floods11/event_level_roots/fold_03_ghana \
      --splits valid test \
      --output-dir results/event_level_v1/calibration_fold03
"""
from __future__ import annotations
from train_sar_unet import DB_MAX, DB_MIN, SarWaterDataset, SmallUNet, split_records
from torch.utils.data import DataLoader
import torch
import numpy as np
import matplotlib.pyplot as plt

import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")


FN_GROUPS = ((0.0, 0.1, "p < 0.1"),
             (0.1, 0.3, "0.1 <= p < 0.3"),
             (0.3, 0.5, "0.3 <= p < 0.5"))


def device_for(setting: str) -> str:
    if setting == "auto":
        if torch.backends.mps.is_available():
            return "mps"
        return "cuda" if torch.cuda.is_available() else "cpu"
    if setting == "mps" and not torch.backends.mps.is_available():
        raise RuntimeError("MPS is unavailable; try --device cpu")
    if setting == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable; try --device cpu")
    return setting


def write_rows(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def safe_div(a: float, b: float) -> float | None:
    return float(a / b) if b > 0 else None


def calc_metrics(tot: dict, bins: int) -> dict:
    n = int(tot["pixels"])
    if not n:
        raise ValueError("No evaluable pixels in split")
    counts = tot["bin_counts"]
    mean_conf = np.divide(tot["bin_sum_p"], counts,
                          out=np.zeros(bins, dtype=float), where=counts > 0)
    observed = np.divide(tot["bin_sum_y"], counts,
                         out=np.zeros(bins, dtype=float), where=counts > 0)
    ece = float(np.sum(counts * np.abs(observed - mean_conf)) / n)
    water = tot["tp"] + tot["fn"]
    return {
        "n_images": int(tot["images"]), "valid_pixels": n,
        "water_pixels": int(water), "water_fraction": float(water / n),
        "tp": int(tot["tp"]), "tn": int(tot["tn"]),
        "fp": int(tot["fp"]), "fn": int(tot["fn"]),
        "precision": safe_div(tot["tp"], tot["tp"] + tot["fp"]),
        "recall": safe_div(tot["tp"], water),
        "iou": safe_div(tot["tp"], tot["tp"] + tot["fp"] + tot["fn"]),
        "brier": float(tot["brier_sum"] / n),
        "nll": float(tot["nll_sum"] / n),
        "ece": ece,
        "mean_predicted_water_probability": float(tot["prob_sum"] / n),
    }


def calculate_split(model, root: Path, split: str, device: str,
                    threshold: float, bins: int) -> tuple[dict, list[dict], list[dict], list[dict]]:
    records = split_records(root, split)
    if not records:
        raise RuntimeError(f"Empty split: {split}")
    dataset = SarWaterDataset(records, augment=False)
    loader = DataLoader(dataset, batch_size=1, shuffle=False,
                        num_workers=0, pin_memory=False)
    tot = {
        "images": 0, "pixels": 0, "tp": 0, "tn": 0, "fp": 0, "fn": 0,
        "brier_sum": 0.0, "nll_sum": 0.0, "prob_sum": 0.0,
        "bin_counts": np.zeros(bins, dtype=np.int64),
        "bin_sum_p": np.zeros(bins, dtype=np.float64),
        "bin_sum_y": np.zeros(bins, dtype=np.float64),
    }
    per_image = []
    fn_counts = np.zeros(len(FN_GROUPS), dtype=np.int64)
    print(f"\n=== {split.upper()} : {len(dataset)} images ===", flush=True)
    model.eval()
    with torch.inference_mode():
        for idx, ((x, y, v), (image_path, _label_path, site)) in enumerate(zip(loader, records), start=1):
            valid = v.numpy().reshape(-1).astype(bool)
            n = int(valid.sum())
            if n == 0:
                print(
                    f"SKIP {image_path.name}: no evaluable pixels", flush=True)
                continue
            logits = model(x.to(device))
            p_all = torch.sigmoid(logits.float()).cpu().numpy().reshape(-1)
            y_all = (y.numpy().reshape(-1) > 0.5)
            if p_all.size != valid.size or y_all.size != valid.size:
                raise ValueError(
                    f"Prediction/label/valid mismatch: {image_path}")
            p = p_all[valid].astype(np.float64)
            truth = y_all[valid]
            if not np.isfinite(p).all():
                raise ValueError(f"Non-finite probabilities in {image_path}")
            pred = p >= threshold
            tp = int(np.count_nonzero(pred & truth))
            tn = int(np.count_nonzero(~pred & ~truth))
            fp = int(np.count_nonzero(pred & ~truth))
            fn = int(np.count_nonzero(~pred & truth))
            sq = float(np.square(p - truth.astype(float)).sum(dtype=np.float64))
            pc = np.clip(p, 1e-7, 1 - 1e-7)
            truth_float = truth.astype(np.float64)
            nll = float((-truth_float * np.log(pc) - (1.0 - truth_float)
                        * np.log1p(-pc)).sum(dtype=np.float64))
            ids = np.minimum((p * bins).astype(np.int32), bins - 1)
            tot["bin_counts"] += np.bincount(ids, minlength=bins)
            tot["bin_sum_p"] += np.bincount(ids, weights=p, minlength=bins)
            tot["bin_sum_y"] += np.bincount(ids,
                                            weights=truth.astype(float), minlength=bins)
            tot["images"] += 1
            tot["pixels"] += n
            tot["tp"] += tp
            tot["tn"] += tn
            tot["fp"] += fp
            tot["fn"] += fn
            tot["prob_sum"] += float(p.sum(dtype=np.float64))
            tot["brier_sum"] += sq
            tot["nll_sum"] += nll
            fn_p = p[truth & ~pred]
            for i, (lo, hi, _name) in enumerate(FN_GROUPS):
                fn_counts[i] += int(np.count_nonzero((fn_p >=
                                    lo) & (fn_p < hi)))
            per_image.append({
                "split": split, "site": site, "name": image_path.name,
                "valid_pixels": n, "water_pixels": tp + fn,
                "water_fraction": (tp + fn) / n,
                "tp": tp, "tn": tn, "fp": fp, "fn": fn,
                "iou": safe_div(tp, tp + fp + fn),
                "recall": safe_div(tp, tp + fn),
                "brier": sq / n, "nll": nll / n,
                "mean_probability": float(p.mean()),
            })
            if idx % 20 == 0 or idx == len(dataset):
                print(f"processed {idx}/{len(dataset)}", flush=True)

    metrics = calc_metrics(tot, bins)
    metrics["split"] = split
    bin_rows = []
    for b in range(bins):
        ct = int(tot["bin_counts"][b])
        bin_rows.append({
            "split": split, "bin": b + 1,
            "p_low": b / bins, "p_high": (b + 1) / bins,
            "n_pixels": ct, "mean_confidence": safe_div(tot["bin_sum_p"][b], ct),
            "observed_water_fraction": safe_div(tot["bin_sum_y"][b], ct),
        })
    fn_rows = []
    for i, (lo, hi, name) in enumerate(FN_GROUPS):
        fn_rows.append({
            "split": split, "probability_group": name,
            "n_fn_pixels": int(fn_counts[i]),
            "fraction_of_fn": safe_div(fn_counts[i], tot["fn"]),
            "fraction_of_gt_water": safe_div(fn_counts[i], tot["tp"] + tot["fn"]),
        })
    print(f"IoU={metrics['iou']:.4f}  Recall={metrics['recall']:.4f}  "
          f"ECE={metrics['ece']:.4f}  Brier={metrics['brier']:.4f}  "
          f"NLL={metrics['nll']:.4f}", flush=True)
    return metrics, per_image, bin_rows, fn_rows


def plot_reliability(bin_rows: list[dict], splits: list[str], output: Path) -> None:
    fig, axes = plt.subplots(1, len(splits), figsize=(6 * len(splits), 5),
                             squeeze=False, constrained_layout=True)
    for ax, split in zip(axes[0], splits):
        data = [r for r in bin_rows if r["split"]
                == split and r["n_pixels"] > 0]
        x = [r["mean_confidence"] for r in data]
        y = [r["observed_water_fraction"] for r in data]
        ax.plot([0, 1], [0, 1], "--", color="gray",
                label="Perfect calibration")
        ax.plot(x, y, "o-", label="Observed vs predicted")
        ax.set(xlim=(0, 1), ylim=(0, 1), xlabel="Mean predicted P(water)",
               ylabel="Observed fraction water", title=f"{split.upper()} reliability")
        ax.grid(alpha=0.25)
        ax.legend(loc="upper left")
    fig.suptitle(
        "Retrospective diagnostic only — fixed checkpoint; no recalibration")
    fig.savefig(output, dpi=170, bbox_inches="tight")
    plt.close(fig)


def plot_fn(fn_rows: list[dict], splits: list[str], output: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5), constrained_layout=True)
    x = np.arange(len(splits))
    bottom = np.zeros(len(splits), dtype=float)
    for group in FN_GROUPS:
        name = group[2]
        heights = np.array([next((r["fraction_of_fn"] for r in fn_rows
                                  if r["split"] == s and r["probability_group"] == name), 0)
                            or 0 for s in splits], dtype=float)
        ax.bar(x, heights * 100, bottom=bottom, label=name)
        bottom += heights * 100
    ax.set_xticks(x, splits)
    ax.set_ylabel("Share of false-negative water pixels (%)")
    ax.set_ylim(0, 100)
    ax.set_title("P(water) assigned to missed ground-truth water")
    ax.legend(title="Probability among FN")
    ax.grid(axis="y", alpha=0.2)
    fig.savefig(output, dpi=170, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--data-root", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--splits", nargs="+", choices=("valid",
                   "test", "bolivia"), default=["valid", "test"])
    p.add_argument("--device", choices=("auto", "cpu",
                   "mps", "cuda"), default="auto")
    p.add_argument("--bins", type=int, default=15)
    args = p.parse_args()
    if not args.checkpoint.is_file():
        p.error(f"Checkpoint not found: {args.checkpoint}")
    if not args.data_root.is_dir():
        p.error(f"Data root not found: {args.data_root}")
    if not 2 <= args.bins <= 100:
        p.error("--bins must be between 2 and 100")
    device = device_for(args.device)
    ckpt = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    if ckpt.get("architecture") != "SmallUNet":
        raise ValueError(
            f"Unexpected architecture: {ckpt.get('architecture')!r}")
    if not np.allclose(np.asarray(ckpt.get("db_min", [-35, -40]), dtype=float).ravel(),
                       np.asarray(DB_MIN).ravel()):
        raise ValueError(
            "Checkpoint DB_MIN is not consistent with training code")
    if not np.allclose(np.asarray(ckpt.get("db_max", [5, 0]), dtype=float).ravel(),
                       np.asarray(DB_MAX).ravel()):
        raise ValueError(
            "Checkpoint DB_MAX is not consistent with training code")
    threshold = float(ckpt.get("threshold", 0.5))
    if not np.isclose(threshold, 0.5):
        raise ValueError(
            "This FN grouping script expects the fixed checkpoint threshold 0.5")
    model = SmallUNet(int(ckpt["base_channels"]))
    model.load_state_dict(ckpt["model_state"], strict=True)
    model.to(device).eval()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    print("Checkpoint:", args.checkpoint)
    print("Checkpoint epoch:", ckpt.get("epoch"))
    print("Device:", device)
    print("Fixed threshold:", threshold)
    print("Calibration fitting or threshold selection: NONE")
    print("Data root:", args.data_root)

    all_summaries, all_images, all_bins, all_fn = [], [], [], []
    for split in args.splits:
        stats, images, bins, fn = calculate_split(
            model, args.data_root, split, device, threshold, args.bins)
        all_summaries.append(stats)
        all_images.extend(images)
        all_bins.extend(bins)
        all_fn.extend(fn)

    summary_fields = ["split", "n_images", "valid_pixels", "water_pixels", "water_fraction",
                      "tp", "tn", "fp", "fn", "precision", "recall", "iou",
                      "brier", "nll", "ece", "mean_predicted_water_probability"]
    image_fields = ["split", "site", "name", "valid_pixels", "water_pixels", "water_fraction",
                    "tp", "tn", "fp", "fn", "iou", "recall", "brier", "nll", "mean_probability"]
    bin_fields = ["split", "bin", "p_low", "p_high", "n_pixels",
                  "mean_confidence", "observed_water_fraction"]
    fn_fields = ["split", "probability_group", "n_fn_pixels",
                 "fraction_of_fn", "fraction_of_gt_water"]
    write_rows(args.output_dir / "calibration_by_split.csv",
               all_summaries, summary_fields)
    write_rows(args.output_dir / "calibration_per_image.csv",
               all_images, image_fields)
    write_rows(args.output_dir / "calibration_bins.csv", all_bins, bin_fields)
    write_rows(args.output_dir / "fn_probability_groups.csv", all_fn, fn_fields)
    plot_reliability(all_bins, args.splits, args.output_dir /
                     "reliability_diagram.png")
    plot_fn(all_fn, args.splits, args.output_dir /
            "fn_probability_breakdown.png")
    info = {
        "checkpoint": str(args.checkpoint), "epoch": ckpt.get("epoch"),
        "data_root": str(args.data_root), "threshold_fixed": threshold,
        "bins_equal_width": args.bins,
        "summary": all_summaries,
        "research_note": "Descriptive test-set error analysis only. No calibration fitting, threshold tuning, or model selection. Pixel-wise ECE may be dominated by non-water and spatial correlations."
    }
    (args.output_dir / "calibration_summary.json").write_text(
        json.dumps(info, indent=2, allow_nan=False), encoding="utf-8")
    print("\nSaved outputs to:", args.output_dir)
    print("- calibration_by_split.csv, calibration_per_image.csv, calibration_bins.csv")
    print("- fn_probability_groups.csv, calibration_summary.json")
    print("- reliability_diagram.png, fn_probability_breakdown.png")
    print("NOTE: These are retrospective diagnostics, NOT independently held-out tuning results.")


if __name__ == "__main__":
    main()
