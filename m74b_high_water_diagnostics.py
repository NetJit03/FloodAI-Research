#!/usr/bin/env python3
"""M7.4B: read-only, VALID-only investigation of two Sri Lanka high-water chips.

- Uses three PRE-EXISTING V2 baseline checkpoints (seeds 42, 123, 777).
- Does not train, tune thresholds, alter normalization or write any input/checkpoint.
- Verifies selected-chip confusion counts against pre-existing M7.4 CSV.
- Never loads TEST / Bolivia / Thailand splits.

Run from the project root (where train_sar_unet.py lives):
  python m74b_high_water_diagnostics.py --self-test
  python m74b_high_water_diagnostics.py --device mps
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import math
from pathlib import Path

TARGETS = ("Sri-Lanka_845821_S1Hand.tif", "Sri-Lanka_534068_S1Hand.tif")
SEEDS = (42, 123, 777)
FOLD = "dev_fold_02_sri_lanka"
FIXED_THRESHOLD = .5


def read_csv(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, columns):
    with Path(path).open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def confusion(truth, pred, valid):
    import numpy as np
    truth, pred, valid = [np.asarray(x, dtype=bool)
                          for x in (truth, pred, valid)]
    return {"tp": int(np.count_nonzero(valid & truth & pred)),
            "tn": int(np.count_nonzero(valid & ~truth & ~pred)),
            "fp": int(np.count_nonzero(valid & ~truth & pred)),
            "fn": int(np.count_nonzero(valid & truth & ~pred))}


def probability_group_counts(values):
    import numpy as np
    a = np.asarray(values, dtype=np.float64)
    if a.size and (not np.isfinite(a).all() or np.any(a < 0) or np.any(a > 1)):
        raise ValueError("Invalid predicted probabilities")
    return [int(np.count_nonzero(a < .1)),
            int(np.count_nonzero((a >= .1) & (a < .3))),
            int(np.count_nonzero((a >= .3) & (a < .5))),
            int(np.count_nonzero(a >= .5))]


def maximum_grid_shift_pixels(src, label):
    import numpy as np
    if src.crs != label.crs or src.width != label.width or src.height != label.height:
        return math.inf
    reverse = ~label.transform
    coords = ((0, 0), (src.width, 0), (0, src.height),
              (src.width, src.height), (src.width / 2, src.height / 2))
    shifts = []
    for col, row in coords:
        x, y = src.transform * (col, row)
        lc, lr = reverse * (x, y)
        shifts.append(float(np.hypot(lc - col, lr - row)))
    return max(shifts)


def self_test():
    import numpy as np
    counts = confusion(np.array([[1, 1], [0, 0]]),
                       np.array([[1, 0], [1, 0]]),
                       np.ones((2, 2), bool))
    assert counts == {"tp": 1, "tn": 1, "fp": 1, "fn": 1}, counts
    assert probability_group_counts(
        [0.0, .1, .29, .3, .49, .5, 1.]) == [1, 2, 2, 2]
    assert sum(probability_group_counts([])) == 0
    print("PASS: M7.4B metrics, probability bins and fixed threshold self-test")


def check_raw_metadata(image_path, label_path):
    import numpy as np
    import rasterio
    with rasterio.open(image_path) as sar, rasterio.open(label_path) as lbl:
        if sar.count != 2 or lbl.count != 1:
            raise ValueError("Unexpected VV/VH or label band count")
        if sar.descriptions != (None, None) and tuple(sar.descriptions) != ("VV", "VH"):
            raise ValueError(
                f"Unexpected SAR channel descriptions: {sar.descriptions}")
        shift = maximum_grid_shift_pixels(sar, lbl)
        if not math.isfinite(shift) or shift > 0.05:
            raise ValueError(f"SAR/label grid mismatch: {shift:.5f} pixels")
        raw = sar.read(out_dtype=np.float32)
        labels = lbl.read(1)
        if not np.isin(labels, (-1, 0, 1)).all():
            raise ValueError(
                "Invalid label codes. Expected -1(ignore),0(land),1(water)")
        sar_finite = np.isfinite(raw).all(axis=0)
        if sar.nodata is not None and np.isfinite(sar.nodata):
            sar_finite &= np.all(raw != sar.nodata, axis=0)
        # IMPORTANT: DO NOT mask label 0 via metadata
        valid = (labels != -1) & sar_finite
        return {"grid_delta_px": shift,
                "label_nodata_metadata": str(lbl.nodata),
                "raw_shape": tuple(raw.shape),
                "labels": labels, "valid": valid}


def load_checkpoint(path, seed, device, DB_MIN, DB_MAX, SmallUNet, torch):
    import numpy as np
    if not path.is_file():
        raise FileNotFoundError(f"Missing checkpoint: {path}")
    ckpt = torch.load(path, map_location="cpu", weights_only=True)
    if ckpt.get("architecture") != "SmallUNet":
        raise ValueError(f"Wrong architecture: {path}")
    if int(ckpt.get("seed", -1)) != seed:
        raise ValueError(f"Checkpoint saved seed mismatch: {path}")
    if not math.isclose(float(ckpt.get("threshold", -.1)), FIXED_THRESHOLD, abs_tol=1e-12):
        raise ValueError("Frozen threshold must be exactly 0.5")
    if not (np.allclose(np.asarray(ckpt.get("db_min", [])).ravel(), DB_MIN.ravel()) and
            np.allclose(np.asarray(ckpt.get("db_max", [])).ravel(), DB_MAX.ravel())):
        raise ValueError(f"Frozen normalization mismatch: {path}")
    model = SmallUNet(int(ckpt["base_channels"]))
    model.load_state_dict(ckpt["model_state"], strict=True)
    model.to(device).eval()
    return model, ckpt


def plot_image(outpath, image_name, input_vv, groundtruth, valid, predictions):
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap, BoundaryNorm
    from matplotlib.patches import Patch

    fig, axs = plt.subplots(2, 4, figsize=(17.5, 8.4), constrained_layout=True)
    fig.suptitle(
        f"M7.4B - {image_name} | frozen threshold=0.50 | DEV VALID only", fontsize=13)
    disp_vv = np.ma.masked_where(~valid, input_vv)
    axs[0, 0].imshow(disp_vv, cmap="gray", vmin=0, vmax=1)
    axs[0, 0].set_title("Normalized VV (display)")
    truth_display = np.ma.masked_where(~valid, groundtruth.astype(float))
    cmap_gt = ListedColormap(["#cdd3d8", "#1987cf"])
    cmap_gt.set_bad("white")
    axs[1, 0].imshow(truth_display, cmap=cmap_gt, vmin=0,
                     vmax=1, interpolation="nearest")
    axs[1, 0].set_title(
        f"Ground truth | water={int(np.count_nonzero(groundtruth & valid)):,}")
    cm = ListedColormap(["#cdd3d8", "#20a36e", "#ee3434", "#ffb200"])
    cm.set_bad("white")
    n = BoundaryNorm([-.5, .5, 1.5, 2.5, 3.5], cm.N)
    last_im = None
    for j, seed in enumerate(SEEDS, start=1):
        p = predictions[seed]
        last_im = axs[0, j].imshow(np.ma.masked_where(
            ~valid, p), cmap="viridis", vmin=0, vmax=1)
        axs[0, j].set_title(f"Seed {seed} | P(water) [0,1]")
        water_pred = p >= FIXED_THRESHOLD
        err = np.full(groundtruth.shape, np.nan, dtype=float)
        err[valid & ~groundtruth & ~water_pred] = 0
        err[valid & groundtruth & water_pred] = 1
        err[valid & ~groundtruth & water_pred] = 2
        err[valid & groundtruth & ~water_pred] = 3
        axs[1, j].imshow(err, cmap=cm, norm=n, interpolation="nearest")
        c = confusion(groundtruth, water_pred, valid)
        iou = c["tp"] / (c["tp"]+c["fp"]+c["fn"]) if c["tp"] + \
            c["fp"]+c["fn"] else math.nan
        axs[1, j].set_title(
            f"Seed {seed} confusion | IoU={iou:.4f} | FN={c['fn']:,}")
    for ax in axs.ravel():
        ax.set_xticks([])
        ax.set_yticks([])
    fig.colorbar(last_im, ax=axs[0, 1:], shrink=.77,
                 pad=.015, label="P(water) [fixed scale]")
    fig.legend(handles=[Patch(color="#cdd3d8", label="TN / land"),
                        Patch(color="#20a36e", label="TP / water"),
                        Patch(color="#ee3434", label="FP"),
                        Patch(color="#ffb200", label="FN")],
               loc="lower center", ncol=4, bbox_to_anchor=(.5, -.015))
    fig.savefig(outpath, dpi=150, bbox_inches="tight")
    plt.close(fig)


def run(args):
    import numpy as np
    import torch
    from train_sar_unet import (
        SarWaterDataset, SmallUNet, split_records, DB_MIN, DB_MAX)

    if args.data_root.name != FOLD:
        raise ValueError(
            f"Use ONLY V2 Sri Lanka development root ending in {FOLD}; received {args.data_root}")
    if not args.data_root.is_dir():
        raise FileNotFoundError(
            f"Missing development data root: {args.data_root}")
    if not args.m74_csv.is_file():
        raise FileNotFoundError(
            f"M7.4 per-image CSV missing: {args.m74_csv}. Run M7.4 --inspect-images first")
    if args.device == "mps" and not torch.backends.mps.is_available():
        raise RuntimeError("MPS unavailable; rerun with --device cpu")
    device = "mps" if args.device == "auto" and torch.backends.mps.is_available() else (
             "cpu" if args.device == "auto" else args.device)

    # deliberately NEVER request test/bolivia
    records = split_records(args.data_root, "valid")
    if len(records) != 42:
        raise ValueError(
            f"Expected 42 Sri Lanka VALID images, found {len(records)}")
    indexed = {path.name: (i, path, lbl)
               for i, (path, lbl, _event) in enumerate(records)}
    for name in TARGETS:
        if name not in indexed:
            raise ValueError(
                f"Selected image not found in Sri Lanka validation CSV: {name}")

    prior = {}
    for r in read_csv(args.m74_csv):
        if r.get("fold") == FOLD and r.get("image") in TARGETS:
            key = (int(r["seed"]), r["image"])
            if key in prior:
                raise ValueError(f"Duplicate M7.4 CSV reference: {key}")
            prior[key] = r
    if len(prior) != 6:
        raise ValueError(
            f"Expected 6 matching (2 images x 3 seeds) records in M7.4 CSV; found {len(prior)}")

    dataset = SarWaterDataset(records, augment=False)
    inputs, labels, masks, metadata = {}, {}, {}, {}
    for name in TARGETS:
        idx, path, label_path = indexed[name]
        meta = check_raw_metadata(path, label_path)
        image, label, valid = dataset[idx]
        truth = label[0].numpy() >= .5
        v = valid[0].numpy().astype(bool)
        if not np.array_equal(v, meta["valid"]) or not np.array_equal(truth, meta["labels"] == 1):
            raise ValueError(
                f"Ground-truth/valid mask disagrees with frozen trainer: {name}")
        inputs[name] = image.unsqueeze(0)
        labels[name] = truth
        masks[name] = v
        metadata[name] = meta
        print(f"PASS {name}: DEV VALID; grid delta={meta['grid_delta_px']:.8f}px; "
              f"water pixels={int(np.count_nonzero(truth & v)):,}; "
              f"valid={int(v.sum()):,}; label metadata nodata={meta['label_nodata_metadata']}")

    # Ensure all prerequisites are valid before output is written.
    models = {}
    for seed in SEEDS:
        cp = args.results_root / \
            f"baseline_seed{seed}" / FOLD / "best_sar_unet.pt"
        model, ckpt = load_checkpoint(
            cp, seed, device, DB_MIN, DB_MAX, SmallUNet, torch)
        models[seed] = (model, cp, ckpt)
        print(
            f"PASS checkpoint seed={seed}, epoch={ckpt['epoch']}, threshold=.50")
    outdir = args.output_dir
    outdir.mkdir(parents=True, exist_ok=True)
    all_predictions = {name: {} for name in TARGETS}
    rows, groups, checks = [], [], []
    bins = ("p_lt_0_1", "p_0_1_to_0_3", "p_0_3_to_0_5", "p_ge_0_5")

    for seed in SEEDS:
        model, cp, ckpt = models[seed]
        with torch.inference_mode():
            for name in TARGETS:
                x = inputs[name].to(device)
                logits = model(x)
                p = torch.sigmoid(logits)[0, 0].cpu().numpy()
                if not np.isfinite(p[masks[name]]).all():
                    raise ValueError(
                        f"Non-finite probabilities: {name}, seed {seed}")
                truth, mask = labels[name], masks[name]
                pred = p >= FIXED_THRESHOLD
                c = confusion(truth, pred, mask)
                old = prior[seed, name]
                mismatches = {k: (c[k], int(old[k]))
                              for k in c if c[k] != int(old[k])}
                if int(mask.sum()) != int(old["valid_pixels"]):
                    mismatches["valid_pixels"] = (
                        int(mask.sum()), int(old["valid_pixels"]))
                if mismatches:
                    raise ValueError(f"M7.4 count mismatch for {name}, seed {seed}: {mismatches}. "
                                     "Check frozen script, checkpoint and data versions; do not tune.")
                all_predictions[name][seed] = p
                water = p[mask & truth]
                land = p[mask & ~truth]
                union = c["tp"]+c["fp"]+c["fn"]
                rows.append({"image": name, "seed": seed,
                             "valid_pixels": int(mask.sum()), "gt_water_pixels": int(water.size),
                             "water_fraction_gt": float(water.size/mask.sum()),
                             "tp": c["tp"], "tn": c["tn"], "fp": c["fp"], "fn": c["fn"],
                             "iou": c["tp"]/union if union else math.nan,
                             "recall": c["tp"]/(c["tp"]+c["fn"]) if c["tp"]+c["fn"] else math.nan,
                             "mean_p_gt_water": float(water.mean()) if water.size else math.nan,
                             "median_p_gt_water": float(np.median(water)) if water.size else math.nan,
                             "fraction_gt_water_p_lt_0_1": float(np.mean(water < .1)) if water.size else math.nan,
                             "checkpoint_epoch": int(ckpt["epoch"]),
                             "checkpoint_path": str(cp)})
                for trueclass, values in (("water", water), ("land", land)):
                    bcounts = probability_group_counts(values)
                    for bname, count in zip(bins, bcounts):
                        groups.append({"image": name, "seed": seed, "gt_class": trueclass,
                                       "probability_bin": bname, "pixels": count,
                                       "class_fraction": count/len(values) if len(values) else math.nan})
                checks.append({"image": name, "seed": seed, "m74_counts_match": True,
                               "grid_delta_px": metadata[name]["grid_delta_px"]})
                print(f"PASS matching M7.4: seed={seed} image={name} "
                      f"IoU={rows[-1]['iou']:.4f} FN={c['fn']:,} GT-water p<0.1={rows[-1]['fraction_gt_water_p_lt_0_1']:.1%}")
        del model
        if device == "mps":
            torch.mps.empty_cache()

    write_csv(outdir / "m74b_image_seed_diagnostics.csv", rows, list(rows[0]))
    write_csv(outdir / "m74b_probability_groups.csv", groups, list(groups[0]))
    write_csv(outdir / "m74b_consistency_checks.csv", checks, list(checks[0]))
    for name in TARGETS:
        short = name.replace("_S1Hand.tif", "")
        plot_image(outdir / f"m74b_{short}_comparison.png", name,
                   inputs[name].numpy()[0, 0], labels[name], masks[name], all_predictions[name])

    # Read-only artifacts allow independent review of selected probability maps.
    np.savez_compressed(outdir / "m74b_selected_probs.npz", **{
        name.replace("_S1Hand.tif", "") + f"_seed{seed}": all_predictions[name][seed].astype(np.float32)
        for name in TARGETS for seed in SEEDS
    })
    report = ["# M7.4B — Sri Lanka high-water failure diagnostics", "",
              "**Scope:** retrospective, development VALID only. No retraining, model selection, threshold search or calibration.",
              "No historical TEST, Bolivia or Thailand data used.",
              "Frozen threshold: **0.50**; probability scale identical for all plots.",
              "All six image/seed confusion rows match existing M7.4 audit CSV.", "",
              "| Image | Seed | GT-water pixels | GT-water fraction | IoU | FN | GT water with P<0.1 |",
              "|---|---:|---:|---:|---:|---:|---:|"]
    for r in sorted(rows, key=lambda x: (x["image"], x["seed"])):
        report.append(f"| {r['image']} | {r['seed']} | {r['gt_water_pixels']:,} | "
                      f"{r['water_fraction_gt']:.1%} | {r['iou']:.4f} | {r['fn']:,} | "
                      f"{r['fraction_gt_water_p_lt_0_1']:.1%} |")
    report += ["", "## Interpretation guardrails", "",
               "- Do not remove the two chips or seed 777 from primary results.",
               "- This targeted diagnosis is a follow-up to observed development variation; it is not an independent final test.",
               "- Probability comparison is descriptive; it does not prove a causal failure mechanism.",
               "- Label 0 is valid land even if TIFF metadata states NoData=0; check geographic imagery before alleging label error.",
               "- Keep frozen trainer, evaluator, source TIFFs, manifests and checkpoints unchanged.",
               "- Source-file freeze verification can be run separately with m70d_freeze_protocol.py verify.", ""]
    (outdir / "m74b_report.md").write_text("\n".join(report), encoding="utf-8")
    print(f"\nSAVED: {outdir}")
    print("PASS: M7.4B retrospective comparison completed. No weights, threshold or inputs modified.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--data-root", type=Path,
                        default=Path("data/sen1floods11/v2_development_roots/dev_fold_02_sri_lanka"))
    parser.add_argument("--results-root", type=Path,
                        default=Path("results/event_level_v2"))
    parser.add_argument("--m74-csv", type=Path, default=Path(
        "results/event_level_v2/m74_stability_diagnostics/m74_development_validation_per_image.csv"))
    parser.add_argument("--output-dir", type=Path,
                        default=Path("results/event_level_v2/m74b_high_water_diagnostics"))
    parser.add_argument("--device", choices=("auto",
                        "cpu", "mps"), default="auto")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    else:
        run(args)


if __name__ == "__main__":
    main()
