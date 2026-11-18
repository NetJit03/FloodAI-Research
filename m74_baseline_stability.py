#!/usr/bin/env python3
"""M7.4: Read-only diagnostics of V2 *development validation* checkpoints.

No training, fitting, threshold selection, test access, or frozen-file edits.
"""
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from statistics import mean, stdev

FOLDS = {
    "dev_fold_01_usa": "USA",
    "dev_fold_02_sri_lanka": "Sri Lanka",
    "dev_fold_03_spain": "Spain",
}
DEFAULT_SEEDS = (42, 123, 777)


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def as_float(value):
    try:
        x = float(value)
        return x if math.isfinite(x) else math.nan
    except (TypeError, ValueError):
        return math.nan


def safe_ratio(numerator, denominator):
    return numerator / denominator if denominator else math.nan


def format_num(num, digits=4):
    return f"{num:.{digits}f}" if math.isfinite(num) else "NaN"


def write_csv(path, records, columns):
    with Path(path).open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        writer.writerows(records)


def import_torch_and_model():
    import numpy as np
    import torch
    from train_sar_unet import (SarWaterDataset, SmallUNet, split_records,
                                DB_MIN, DB_MAX)
    return np, torch, SarWaterDataset, SmallUNet, split_records, DB_MIN, DB_MAX


def summary_history(root, seeds):
    rows, checkpoints = [], []
    for fold, event in FOLDS.items():
        for seed in seeds:
            folder = root / f"baseline_seed{seed}" / fold
            hp, cp = folder / "history.csv", folder / "best_sar_unet.pt"
            if not hp.is_file() or not cp.is_file():
                raise FileNotFoundError(
                    f"Missing history/checkpoint: {folder}")
            raw = read_csv(hp)
            if not raw:
                raise ValueError(f"Empty history: {hp}")
            required = {"epoch", "train_loss", "val_loss",
                        "val_iou", "val_f1", "val_recall", "val_precision"}
            absent = required - set(raw[0])
            if absent:
                raise ValueError(
                    f"Missing history columns in {hp}: {sorted(absent)}")
            for r in raw:
                item = {"fold": fold, "event": event, "seed": seed,
                        "epoch": int(r["epoch"])}
                item.update({k: as_float(r[k]) for k in required - {"epoch"}})
                rows.append(item)
            candidates = [r for r in rows if r["fold"] ==
                          fold and r["seed"] == seed and math.isfinite(r["val_iou"])]
            if not candidates:
                raise ValueError(f"No finite val IoU in {hp}")
            # Matches trainer: strict improvement > 1e-5; logs selected epoch.
            selected = candidates[0]
            for r in candidates[1:]:
                if r["val_iou"] > selected["val_iou"] + 1e-5:
                    selected = r
            checkpoints.append(
                {**selected, "epochs_run": len(raw), "checkpoint_path": str(cp)})
    return rows, checkpoints


def check_checkpoints(checkpoints):
    _, torch, _, _, _, _, _ = import_torch_and_model()
    for c in checkpoints:
        checkpoint = torch.load(c["checkpoint_path"],
                                map_location="cpu", weights_only=True)
        c["saved_epoch"] = int(checkpoint["epoch"])
        c["saved_seed"] = int(checkpoint["seed"])
        c["fixed_threshold"] = float(checkpoint.get("threshold", .5))
        vm = checkpoint.get("validation_metrics", {})
        c["saved_validation_iou"] = float(vm.get("iou", math.nan))
        ok = (c["saved_epoch"] == c["epoch"] and
              c["saved_seed"] == c["seed"] and
              math.isclose(c["fixed_threshold"], .5) and
              math.isclose(c["saved_validation_iou"], c["val_iou"], abs_tol=1e-4))
        if not ok:
            raise ValueError(
                f"Checkpoint/history mismatch: {c['checkpoint_path']}: {c}")
        print(
            f"PASS {c['event']:10s} seed={c['seed']:3d}: epoch={c['epoch']:2d}, IoU={c['val_iou']:.5f}")


def inspect_images(checkpoints, data_roots, output_dir, device_choice):
    np, torch, Dataset, Model, split_records, DB_MIN, DB_MAX = import_torch_and_model()
    if device_choice == "auto":
        device_choice = "mps" if torch.backends.mps.is_available() else "cpu"
    if device_choice == "mps" and not torch.backends.mps.is_available():
        raise RuntimeError("MPS unavailable; use --device cpu")
    device = torch.device(device_choice)
    all_rows = []
    micro = []
    for c in checkpoints:
        data_root = data_roots / c["fold"]
        if not data_root.is_dir():
            raise FileNotFoundError(
                f"Expected dev root not found: {data_root}")
        records = split_records(data_root, "valid")
        dataset = Dataset(records, augment=False)
        ckpt = torch.load(c["checkpoint_path"],
                          map_location="cpu", weights_only=True)
        if not (np.allclose(np.asarray(ckpt["db_min"]).ravel(), np.asarray(DB_MIN).ravel()) and
                np.allclose(np.asarray(ckpt["db_max"]).ravel(), np.asarray(DB_MAX).ravel())):
            raise ValueError(f"Normalization mismatch: {c['checkpoint_path']}")
        if ckpt.get("architecture") != "SmallUNet":
            raise ValueError(
                f"Unexpected checkpoint architecture: {c['checkpoint_path']}")
        net = Model(int(ckpt["base_channels"]))
        net.load_state_dict(ckpt["model_state"], strict=True)
        net.to(device).eval()
        threshold = float(ckpt.get("threshold", .5))
        if not math.isclose(threshold, .5):
            raise ValueError("Threshold differs from frozen value 0.5")
        counts = {"tp": 0, "tn": 0, "fp": 0, "fn": 0}
        with torch.inference_mode():
            for idx, (image, label, valid) in enumerate(dataset):
                logits = net(image.unsqueeze(0).to(device))
                probs = torch.sigmoid(logits)[0, 0].cpu().numpy()
                truth = label[0].numpy() > .5
                mask = valid[0].numpy().astype(bool)
                prediction = probs >= threshold
                tp = int(np.count_nonzero(mask & truth & prediction))
                tn = int(np.count_nonzero(mask & ~truth & ~prediction))
                fp = int(np.count_nonzero(mask & ~truth & prediction))
                fn = int(np.count_nonzero(mask & truth & ~prediction))
                for key, val in zip(("tp", "tn", "fp", "fn"), (tp, tn, fp, fn)):
                    counts[key] += val
                path = records[idx][0]
                all_rows.append({
                    "fold": c["fold"], "event": c["event"], "seed": c["seed"],
                    "image": Path(path).name, "valid_pixels": int(mask.sum()),
                    "gt_water_pixels": tp + fn, "pred_water_pixels": tp + fp,
                    "tp": tp, "tn": tn, "fp": fp, "fn": fn,
                    "iou": safe_ratio(tp, tp + fp + fn),
                    "recall": safe_ratio(tp, tp + fn),
                    "precision": safe_ratio(tp, tp + fp),
                })
        iou = safe_ratio(counts["tp"], counts["tp"]+counts["fp"]+counts["fn"])
        isclose = math.isclose(iou, c["val_iou"], abs_tol=2e-4)
        micro.append({"event": c["event"], "seed": c["seed"], "n_images": len(records),
                      "micro_iou": iou, "checkpoint_val_iou": c["val_iou"], "matches": isclose})
        print(f"DEV VALID ONLY: {c['event']:10s} seed={c['seed']:3d} "
              f"n={len(records):2d} reconstructed IoU={iou:.5f} matches history={isclose}")
        if not isclose:
            print(
                "WARNING: discrepancy: investigate preprocessing, count policy, or execution environment")
    write_csv(output_dir / "m74_development_validation_per_image.csv", all_rows,
              ["fold", "event", "seed", "image", "valid_pixels", "gt_water_pixels",
               "pred_water_pixels", "tp", "tn", "fp", "fn", "iou", "recall", "precision"])
    write_csv(output_dir / "m74_development_validation_micro.csv", micro,
              ["event", "seed", "n_images", "micro_iou", "checkpoint_val_iou", "matches"])
    # Sri Lanka: pair identical image names across seeds and rank the most variable cases.
    by_image = {}
    for r in all_rows:
        if r["event"] == "Sri Lanka":
            by_image.setdefault(r["image"], {})[r["seed"]] = r
    comparison = []
    for name, grp in sorted(by_image.items()):
        if not all(s in grp for s in (42, 123, 777)):
            continue
        old = [grp[s]["iou"]
               for s in (42, 123) if math.isfinite(grp[s]["iou"])]
        comparison.append({"image": name, "gt_water_pixels": grp[42]["gt_water_pixels"],
                           "iou_42": grp[42]["iou"], "iou_123": grp[123]["iou"],
                           "iou_777": grp[777]["iou"],
                           "drop_from_42_123_mean": mean(old)-grp[777]["iou"] if old and math.isfinite(grp[777]["iou"]) else math.nan,
                           "recall_777": grp[777]["recall"],
                           "fn_777": grp[777]["fn"]})
    comparison.sort(key=lambda r: (not math.isfinite(
        r["drop_from_42_123_mean"]), -r["drop_from_42_123_mean"] if math.isfinite(r["drop_from_42_123_mean"]) else 0))
    write_csv(output_dir / "m74_sri_lanka_image_comparison.csv", comparison,
              ["image", "gt_water_pixels", "iou_42", "iou_123", "iou_777", "drop_from_42_123_mean", "recall_777", "fn_777"])
    return micro, comparison


def make_plots(history, selected, output_dir):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("Matplotlib unavailable: skipping plots")
        return
    for fold, event in FOLDS.items():
        fig, axs = plt.subplots(2, 2, figsize=(12, 8))
        for ax, field, title in zip(axs.flat,
                                    ("val_iou", "val_recall",
                                     "val_precision", "val_loss"),
                                    ("Water IoU", "Water Recall", "Water Precision", "Validation loss")):
            for seed in sorted({int(r["seed"]) for r in history}):
                points = sorted((r for r in history if r["seed"] == seed and r["fold"] == fold),
                                key=lambda r: r["epoch"])
                ax.plot([p["epoch"] for p in points], [p[field]
                        for p in points], marker="o", label=f"seed {seed}")
                pick = next(
                    p for p in selected if p["seed"] == seed and p["fold"] == fold)
                ax.scatter([pick["epoch"]], [pick[field]], s=110,
                           facecolors="none", edgecolors="black", linewidths=1.1)
            ax.set_title(title)
            ax.set_xlabel("Epoch")
            ax.grid(alpha=.2)
        axs[0, 0].legend()
        fig.suptitle(
            f"M7.4 Development validation | {event} | circles = selected epochs")
        fig.tight_layout()
        fig.savefig(output_dir / f"m74_{fold}_training_curves.png", dpi=150)
        plt.close(fig)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results-root", type=Path,
                   default=Path("results/event_level_v2"))
    p.add_argument("--dev-roots", type=Path,
                   default=Path("data/sen1floods11/v2_development_roots"))
    p.add_argument("--out", type=Path,
                   default=Path("results/event_level_v2/m74_stability_diagnostics"))
    p.add_argument("--seeds", type=int, nargs="+", default=list(DEFAULT_SEEDS))
    p.add_argument("--inspect-images", action="store_true",
                   help="Run frozen checkpoints on development validation images only")
    p.add_argument("--device", choices=("auto", "cpu", "mps"), default="auto")
    args = p.parse_args()
    if set(args.seeds) != set(DEFAULT_SEEDS) or len(args.seeds) != 3:
        p.error("For M7.4 frozen baseline, use exactly seeds 42 123 777")
    args.out.mkdir(parents=True, exist_ok=True)
    history, selected = summary_history(args.results_root, args.seeds)
    check_checkpoints(selected)
    write_csv(args.out / "m74_all_history.csv", history,
              ["fold", "event", "seed", "epoch", "train_loss", "val_loss", "val_iou", "val_f1", "val_recall", "val_precision"])
    write_csv(args.out / "m74_selected_checkpoints.csv", selected,
              ["fold", "event", "seed", "epoch", "epochs_run", "train_loss", "val_iou", "val_f1", "val_recall", "val_precision", "val_loss", "checkpoint_path", "saved_epoch", "saved_seed", "fixed_threshold", "saved_validation_iou"])
    make_plots(history, selected, args.out)
    by_event = {}
    for event in FOLDS.values():
        vals = [r["val_iou"] for r in selected if r["event"] == event]
        by_event[event] = {"mean": mean(
            vals), "sd": stdev(vals), "values": vals}
    lines = ["# M7.4 — Read-only development validation stability diagnostic", "",
             "- Status: checkpoint/history consistency checked; no training or parameter tuning.",
             "- Data isolation: only pre-existing V2 development folds; historical tests excluded.",
             "- Fixed classification threshold: 0.5 from checkpoints.", "",
             "| Validation event | IoU mean | Sample SD | seed 42 | seed 123 | seed 777 |",
             "|---|---:|---:|---:|---:|---:|"]
    for event, dat in by_event.items():
        a, b, c = dat["values"]
        lines.append(
            f"| {event} | {dat['mean']:.4f} | {dat['sd']:.4f} | {a:.4f} | {b:.4f} | {c:.4f} |")
    lines += ["", "## Observations", "",
              "- The Sri Lanka fold is unusually sensitive to training seed, primarily at seed 777.",
              "- IoU and recall fluctuations are descriptive; do not infer a causal mechanism from them alone.",
              "- All nine seeds/folds should remain in the report; do not exclude seed 777.",
              "- Selection remains VALID-only and fixed; do not revisit historical TEST for tuning."]
    if args.inspect_images:
        micro, compare = inspect_images(
            selected, args.dev_roots, args.out, args.device)
        lines += ["", "## Development validation per-image analysis", "",
                  "- Reconstructed micro IoU (same fixed checkpoint, same 0.5 threshold):", "",
                  "| Event | Seed | Images | IoU | Matches history |",
                  "|---|---:|---:|---:|---|"]
        for item in micro:
            lines.append(
                f"| {item['event']} | {item['seed']} | {item['n_images']} | {format_num(item['micro_iou'])} | {item['matches']} |")
        lines += ["", "- Top 10 Sri Lanka images with largest positive IoU gap from seeds 42/123 to 777 (GT-water images only):", "",
                  "| Image | GT water pixels | Mean(42,123) minus 777 IoU | Seed 777 recall |", "|---|---:|---:|---:|"]
        for item in [r for r in compare if r["gt_water_pixels"] > 0][:10]:
            lines.append(
                f"| {item['image']} | {item['gt_water_pixels']} | {format_num(item['drop_from_42_123_mean'])} | {format_num(item['recall_777'])} |")
    else:
        lines += ["", "## Next step", "",
                  "- Re-run with `--inspect-images` to reconstruct per-image predictions on development validation only."]
    (args.out / "m74_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Saved to {args.out}")
    print("Sri Lanka seed IoUs:", [format_num(x)
          for x in by_event["Sri Lanka"]["values"]])
    print("No TEST or Bolivia/Thailand data accessed.")


if __name__ == "__main__":
    main()
