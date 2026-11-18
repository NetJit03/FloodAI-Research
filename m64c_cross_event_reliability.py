#!/usr/bin/env python3
"""M6.4C: retrospective, fixed-checkpoint reliability across held-out events.

Uses existing train_sar_unet.SarWaterDataset and SmallUNet to guarantee
identical preprocessing to the original experiments. No fitting or tuning.

Run from the FloodAI-Research project directory.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

FOLDS = {
    "fold_01_india": "India",
    "fold_02_paraguay": "Paraguay",
    "fold_03_ghana": "Ghana",
}

FIELDS_SUMMARY = [
    "fold", "held_out_event", "n_images", "valid_pixels", "water_pixels",
    "water_fraction", "predicted_water_fraction", "tp", "tn", "fp", "fn",
    "iou", "precision", "recall", "f1", "brier", "nll", "ece",
    "brier_water_only", "brier_land_only", "fn_p_lt_0_1",
    "fn_p_lt_0_1_share_of_fn", "fn_p_lt_0_1_share_of_gt_water",
    "threshold", "n_bins", "checkpoint_epoch", "checkpoint_sha256",
]


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def safe_ratio(a, b):
    return float(a / b) if b else float("nan")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def bin_stats(prob: np.ndarray, truth: np.ndarray, bins: int):
    idx = np.minimum((prob * bins).astype(np.int64), bins - 1)
    count = np.bincount(idx, minlength=bins)
    p_sum = np.bincount(idx, weights=prob, minlength=bins)
    y_sum = np.bincount(idx, weights=truth, minlength=bins)
    return count, p_sum, y_sum


def update_accumulator(acc, prob, truth, threshold, bins):
    """Both arrays must contain only evaluable pixels (1-dimensional)."""
    if not len(prob):
        return None
    pred = prob >= threshold
    gt = truth.astype(bool)
    tp = int(np.count_nonzero(pred & gt))
    tn = int(np.count_nonzero(~pred & ~gt))
    fp = int(np.count_nonzero(pred & ~gt))
    fn = int(np.count_nonzero(~pred & gt))
    very_low_fn = int(np.count_nonzero(gt & (prob < 0.1)))
    acc["tp"] += tp
    acc["tn"] += tn
    acc["fp"] += fp
    acc["fn"] += fn
    acc["valid_pixels"] += len(prob)
    acc["water_pixels"] += int(np.count_nonzero(gt))
    acc["predicted_water_pixels"] += int(np.count_nonzero(pred))
    acc["fn_p_lt_0_1"] += very_low_fn
    errors = (prob - truth) ** 2
    acc["brier_sum"] += float(np.sum(errors, dtype=np.float64))
    acc["brier_water_sum"] += float(np.sum(errors[gt], dtype=np.float64))
    acc["brier_land_sum"] += float(np.sum(errors[~gt], dtype=np.float64))
    clipped = np.clip(prob, 1e-7, 1 - 1e-7)
    acc["nll_sum"] += float(np.sum(
        -(truth * np.log(clipped) + (1 - truth) * np.log1p(-clipped)),
        dtype=np.float64,
    ))
    n, ps, ys = bin_stats(prob, truth, bins)
    acc["bin_count"] += n
    acc["bin_p_sum"] += ps
    acc["bin_y_sum"] += ys
    acc["fn_groups"][0] += very_low_fn
    acc["fn_groups"][1] += int(np.count_nonzero(gt &
                               (prob >= .1) & (prob < .3)))
    acc["fn_groups"][2] += int(np.count_nonzero(gt &
                               (prob >= .3) & (prob < threshold)))
    return dict(tp=tp, tn=tn, fp=fp, fn=fn, valid_pixels=len(prob),
                water_pixels=int(np.count_nonzero(gt)), very_low_fn=very_low_fn,
                brier=float(np.mean(errors)),
                nll=float(np.mean(-(truth * np.log(clipped) + (1 - truth) * np.log1p(-clipped)))))


def new_accumulator(bins):
    return dict(tp=0, tn=0, fp=0, fn=0, valid_pixels=0, water_pixels=0,
                predicted_water_pixels=0, fn_p_lt_0_1=0,
                brier_sum=0.0, brier_water_sum=0.0, brier_land_sum=0.0,
                nll_sum=0.0, bin_count=np.zeros(bins, dtype=np.int64),
                bin_p_sum=np.zeros(bins, dtype=np.float64),
                bin_y_sum=np.zeros(bins, dtype=np.float64),
                fn_groups=np.zeros(3, dtype=np.int64))


def summarize(fold, event, acc, threshold, bins, epoch, sha):
    tp, tn, fp, fn = [acc[k] for k in ("tp", "tn", "fp", "fn")]
    denom = acc["valid_pixels"]
    wc = acc["water_pixels"]
    bc = acc["bin_count"]
    occupied = bc > 0
    p_bar = np.divide(acc["bin_p_sum"], bc, out=np.zeros(bins), where=occupied)
    y_bar = np.divide(acc["bin_y_sum"], bc, out=np.zeros(bins), where=occupied)
    ece = float(np.sum(bc * np.abs(p_bar - y_bar)) / denom)
    summary = dict(
        fold=fold, held_out_event=event, n_images=acc["n_images"],
        valid_pixels=denom, water_pixels=wc, water_fraction=wc / denom,
        predicted_water_fraction=acc["predicted_water_pixels"] / denom,
        tp=tp, tn=tn, fp=fp, fn=fn,
        iou=safe_ratio(tp, tp + fp + fn),
        precision=safe_ratio(tp, tp + fp),
        recall=safe_ratio(tp, tp + fn),
        f1=safe_ratio(2 * tp, 2 * tp + fp + fn),
        brier=acc["brier_sum"] / denom,
        nll=acc["nll_sum"] / denom, ece=ece,
        brier_water_only=safe_ratio(acc["brier_water_sum"], wc),
        brier_land_only=safe_ratio(acc["brier_land_sum"], denom - wc),
        fn_p_lt_0_1=acc["fn_p_lt_0_1"],
        fn_p_lt_0_1_share_of_fn=safe_ratio(acc["fn_p_lt_0_1"], fn),
        fn_p_lt_0_1_share_of_gt_water=safe_ratio(acc["fn_p_lt_0_1"], wc),
        threshold=threshold, n_bins=bins, checkpoint_epoch=epoch,
        checkpoint_sha256=sha,
    )
    bins_rows = [dict(fold=fold, event=event, bin=i+1,
                      p_low=i/bins, p_high=(i+1)/bins,
                      n_pixels=int(bc[i]),
                      mean_predicted_p_water=float(p_bar[i]) if bc[i] else "",
                      observed_water_fraction=float(y_bar[i]) if bc[i] else "")
                 for i in range(bins)]
    fn_rows = [dict(fold=fold, event=event, probability_group=group,
                    n_fn_pixels=int(cnt), share_of_fn=safe_ratio(cnt, fn),
                    share_of_gt_water=safe_ratio(cnt, wc))
               for group, cnt in zip(("p < 0.1", "0.1 <= p < 0.3", "0.3 <= p < 0.5"),
                                     acc["fn_groups"])]
    return summary, bins_rows, fn_rows


def compare_with_existing(fold, summary):
    """Guard against accidental differences from original inference pipeline."""
    path = Path("results/event_level_v1") / fold / \
        "evaluation/evaluation_summary.csv"
    if not path.exists():
        print(f"  Baseline reproduction: no prior CSV at {path} (skipped)")
        return
    with path.open(newline="", encoding="utf-8") as f:
        orig = next((r for r in csv.DictReader(
            f) if r.get("split") == "test"), None)
    if not orig:
        print(f"  Baseline reproduction: no test row in {path} (skipped)")
        return
    for key in ("iou", "recall", "precision", "brier"):
        if key not in orig or not orig[key]:
            continue
        old = float(orig[key])
        new = float(summary[key])
        if abs(old - new) > 0.002:
            raise RuntimeError(
                f"Reproduction check FAILED for {fold} {key}: "
                f"existing={old:.6f}, new={new:.6f}. Do not compare "
                "calibration until preprocessing/checkpoint/splits match."
            )
    print("  PASS: original test metrics reproduced (tolerance 0.002)")


def device_from_arg(name, torch):
    if name == "auto":
        if torch.backends.mps.is_available():
            return "mps"
        if torch.cuda.is_available():
            return "cuda"
        return "cpu"
    if name == "mps" and not torch.backends.mps.is_available():
        raise RuntimeError("Requested mps, but MPS is unavailable")
    if name == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("Requested cuda, but CUDA is unavailable")
    return name


def run_fold(fold, event, device, args):
    import torch
    from train_sar_unet import SmallUNet, SarWaterDataset, split_records, DB_MIN, DB_MAX

    root = Path("data/sen1floods11/event_level_roots") / fold
    checkpoint_path = Path("results/event_level_v1") / \
        fold / "best_sar_unet.pt"
    if not root.is_dir():
        raise FileNotFoundError(f"Missing data root: {root}")
    if not checkpoint_path.is_file():
        raise FileNotFoundError(f"Missing model: {checkpoint_path}")
    checkpoint = torch.load(
        checkpoint_path, map_location="cpu", weights_only=True)
    if checkpoint.get("architecture") != "SmallUNet":
        raise ValueError(f"Unexpected architecture in {checkpoint_path}")
    ckpt_min = np.asarray(checkpoint.get(
        "db_min", [-35, -40]), dtype=np.float64).ravel()
    ckpt_max = np.asarray(checkpoint.get(
        "db_max", [5, 0]), dtype=np.float64).ravel()
    if (not np.allclose(ckpt_min, np.asarray(DB_MIN).ravel()) or
            not np.allclose(ckpt_max, np.asarray(DB_MAX).ravel())):
        raise ValueError(
            "Checkpoint normalization does not match dataset code")
    threshold = float(checkpoint.get("threshold", 0.5))
    if abs(threshold - 0.5) > 1e-6:
        raise ValueError("This script requires fixed checkpoint threshold 0.5")
    records = split_records(root, "test")
    if not records:
        raise ValueError(f"No test records for {fold}")
    expected_sizes = {"fold_01_india": 68,
                      "fold_02_paraguay": 66, "fold_03_ghana": 48}
    if len(records) != expected_sizes[fold]:
        raise RuntimeError(
            f"Unexpected {fold} test count: {len(records)} vs {expected_sizes[fold]}")
    seen_sites = {str(rec[2]) for rec in records}
    expected_site = {"India": "India",
                     "Paraguay": "Paraguay", "Ghana": "Ghana"}[event]
    if seen_sites != {expected_site}:
        raise RuntimeError(
            f"Test site mismatch! {seen_sites} != {{{expected_site}}}")

    model = SmallUNet(int(checkpoint["base_channels"]))
    model.load_state_dict(checkpoint["model_state"], strict=True)
    model.to(device).eval()
    dataset = SarWaterDataset(records, augment=False)
    acc = new_accumulator(args.bins)
    per_image = []
    print(
        f"\n=== {fold}: test={event}, images={len(dataset)}, device={device} ===", flush=True)
    with torch.inference_mode():
        for i, ((imgpath, _, _), sample) in enumerate(zip(records, dataset), 1):
            x, y, valid = sample
            logits = model(x.unsqueeze(0).to(device))
            prob = torch.sigmoid(logits).cpu().numpy()[0, 0]
            ground_truth = y.numpy()[0]
            mask = valid.numpy()[0].astype(bool)
            if not mask.any():
                raise RuntimeError(f"No evaluable pixels in {imgpath}")
            p = np.asarray(prob[mask], dtype=np.float64)
            gt = np.asarray(ground_truth[mask], dtype=np.float64)
            img_metrics = update_accumulator(acc, p, gt, threshold, args.bins)
            per_image.append(dict(
                fold=fold, event=event, image=Path(imgpath).name,
                valid_pixels=img_metrics["valid_pixels"],
                water_pixels=img_metrics["water_pixels"],
                tp=img_metrics["tp"], tn=img_metrics["tn"],
                fp=img_metrics["fp"], fn=img_metrics["fn"],
                recall=safe_ratio(
                    img_metrics["tp"], img_metrics["tp"] + img_metrics["fn"]),
                iou=safe_ratio(
                    img_metrics["tp"], img_metrics["tp"] + img_metrics["fp"] + img_metrics["fn"]),
                fn_p_lt_0_1=img_metrics["very_low_fn"],
                brier=img_metrics["brier"], nll=img_metrics["nll"],
            ))
            if i % 15 == 0 or i == len(dataset):
                print(f"  processed {i}/{len(dataset)}", flush=True)
    acc["n_images"] = len(dataset)
    summary, bins_rows, fn_rows = summarize(
        fold, event, acc, threshold, args.bins,
        checkpoint.get("epoch", ""), sha256_file(checkpoint_path),
    )
    compare_with_existing(fold, summary)
    print("  IoU={iou:.4f} Recall={recall:.4f} Brier={brier:.5f} NLL={nll:.5f} "
          "ECE={ece:.5f} FN<0.1 / GT-water={fn_p_lt_0_1_share_of_gt_water:.2%}".format(**summary))
    return summary, bins_rows, fn_rows, per_image


def create_plots(out_dir, summaries, all_bins):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axs = plt.subplots(1, len(summaries), figsize=(
        5 * len(summaries), 4.7), sharex=True, sharey=True)
    if len(summaries) == 1:
        axs = [axs]
    for ax, info in zip(axs, summaries):
        points = [r for r in all_bins if r["fold"]
                  == info["fold"] and r["n_pixels"] > 0]
        ax.plot([0, 1], [0, 1], "--", color="gray", label="Ideal calibration")
        ax.plot([r["mean_predicted_p_water"] for r in points],
                [r["observed_water_fraction"] for r in points], "o-", label="Observed")
        ax.set_title(f"{info['held_out_event']} (ECE={info['ece']:.3f})")
        ax.set_xlabel("Mean predicted P(water)")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.grid(alpha=0.2)
    axs[0].set_ylabel("Observed fraction of water")
    axs[0].legend(loc="upper left", fontsize=8)
    plt.style.use("default")
    plt.rcParams["text.color"] = "black"
    plt.rcParams["axes.labelcolor"] = "black"
    plt.rcParams["xtick.color"] = "black"
    plt.rcParams["ytick.color"] = "black"
    fig.suptitle("M6.4C — Event-holdout reliability (15 equal-width bins)")
    fig.tight_layout()
    fig.savefig(out_dir / "cross_event_reliability_diagram.png",
                dpi=180, facecolor="white", transparent=False)
    plt.close(fig)

    events = [s["held_out_event"] for s in summaries]
    fig, axs = plt.subplots(1, 3, figsize=(12, 3.9))
    for ax, metric, title in zip(
        axs, ("recall", "ece", "fn_p_lt_0_1_share_of_gt_water"),
        ("Water recall", "ECE (lower is better)", "GT water missed with P<0.1"),
    ):
        values = [s[metric] for s in summaries]
        bars = ax.bar(events, values)
        ax.set_title(title)
        ax.set_ylim(0, max(0.05, max(values) * 1.25))
        for bar, value in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, value, f"{value:.3f}",
                    ha="center", va="bottom", fontsize=9)
        ax.grid(axis="y", alpha=0.2)
    fig.suptitle(
        "M6.4C — Descriptive comparison across independent held-out events")
    fig.tight_layout()
    fig.savefig(out_dir / "cross_event_metric_comparison.png", dpi=180)
    plt.close(fig)


def self_test():
    arr_p = np.array([0.01, 0.15, 0.35, 0.8, 0.9], dtype=np.float64)
    arr_y = np.array([1, 1, 0, 1, 0], dtype=np.float64)
    acc = new_accumulator(5)
    res = update_accumulator(acc, arr_p, arr_y, 0.5, 5)
    assert (res["tp"], res["tn"], res["fp"], res["fn"]) == (1, 1, 1, 2)
    acc["n_images"] = 1
    sm, bins, fns = summarize("toy", "toy", acc, .5, 5, 0, "dummy")
    assert sum(r["n_pixels"] for r in bins) == 5
    assert sum(r["n_fn_pixels"] for r in fns) == 2
    assert np.isfinite(sm["ece"])
    print("PASS: built-in aggregation self-test")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--folds", nargs="+",
                    choices=list(FOLDS), default=list(FOLDS))
    ap.add_argument("--bins", type=int, default=15)
    ap.add_argument(
        "--device", choices=["auto", "cpu", "mps", "cuda"], default="auto")
    ap.add_argument("--output-dir", type=Path,
                    default=Path("results/event_level_v1/cross_event_reliability"))
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return
    if args.bins < 2 or args.bins > 100:
        ap.error("--bins must be between 2 and 100")
    import torch
    device = device_from_arg(args.device, torch)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summaries, bins_rows, fn_rows, image_rows = [], [], [], []
    for fold in args.folds:
        s, b, f, per_image = run_fold(fold, FOLDS[fold], device, args)
        summaries.append(s)
        bins_rows.extend(b)
        fn_rows.extend(f)
        image_rows.extend(per_image)
    write_csv(args.output_dir / "cross_event_reliability_summary.csv",
              summaries, FIELDS_SUMMARY)
    write_csv(args.output_dir / "cross_event_reliability_bins.csv", bins_rows,
              ["fold", "event", "bin", "p_low", "p_high", "n_pixels",
               "mean_predicted_p_water", "observed_water_fraction"])
    write_csv(args.output_dir / "cross_event_fn_probability_groups.csv", fn_rows,
              ["fold", "event", "probability_group", "n_fn_pixels", "share_of_fn", "share_of_gt_water"])
    write_csv(args.output_dir / "cross_event_per_image.csv", image_rows,
              ["fold", "event", "image", "valid_pixels", "water_pixels",
               "tp", "tn", "fp", "fn", "recall", "iou", "fn_p_lt_0_1", "brier", "nll"])
    create_plots(args.output_dir, summaries, bins_rows)
    (args.output_dir / "M64C_METHOD_NOTES.txt").write_text(
        "M6.4C: RETROSPECTIVE DIAGNOSTICS ONLY.\n"
        "Each event is scored using its own fold-specific checkpoint. Fold-specific "
        "training/validation composition differs; the graph is NOT a controlled "
        "same-model cross-event comparison.\n"
        "No model fitting, recalibration or threshold selection is performed. "
        "All event test sets have been inspected in earlier work: do NOT treat "
        "these as fresh untouched confirmatory test results for Model V2.\n"
        "IoU/recall and ECE are micro-aggregated over evaluable pixels per event. "
        "ECE uses equal-width probability bins with occupancy weighting; "
        "class imbalance can hide water-class errors.\n"
        "Ground-truth labels are the source dataset's labels; not independently "
        "field-validated labels. Pixelwise observations are spatially correlated.\n",
        encoding="utf-8")
    print(f"\nDONE. Files saved under: {args.output_dir.resolve()}")
    for s in summaries:
        print(f"  {s['held_out_event']:<10} IoU={s['iou']:.4f} "
              f"Recall={s['recall']:.4f} ECE={s['ece']:.4f} "
              f"Brier={s['brier']:.4f} NLL={s['nll']:.4f}")
    print("RESEARCH NOTE: This is a retrospective diagnostic; test events must not be used to tune V2.")


if __name__ == "__main__":
    main()
