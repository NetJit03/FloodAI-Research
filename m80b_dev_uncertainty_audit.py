#!/usr/bin/env python3
"""M8.0B: Read-only DEV uncertainty reliability / error audit.

No model fitting, no inference, no threshold tuning, no TEST access.
Requires only M8.0A DEV CSV, manifest and selected preview NPZ files.
The nine NPZ images are deliberately selected examples, NOT representative samples.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

EVENTS = ("USA", "Sri-Lanka", "Spain")
EXPECTED_FOLDS = {
    "USA": ("dev_fold_01_usa", 69),
    "Sri-Lanka": ("dev_fold_02_sri_lanka", 42),
    "Spain": ("dev_fold_03_spain", 30),
}
REQUIRED_ARRAYS = (
    "p_water", "predictive_entropy_bits", "expected_entropy_bits",
    "mutual_information_bits", "variance", "valid", "gt_water",
)
IMAGE_METRICS = (
    ("mean_mutual_information_bits", "mean MI (bits)"),
    ("mean_predictive_entropy_bits", "mean predictive entropy (bits)"),
    ("mean_probability_variance", "mean ensemble variance"),
)
BIN_COUNT = 15
EPS = 1e-9


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for data in iter(lambda: f.read(1 << 20), b""):
            h.update(data)
    return h.hexdigest()


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def as_float(x) -> float:
    try:
        return float(x)
    except (ValueError, TypeError):
        return float("nan")


def clean(v):
    if isinstance(v, dict):
        return {k: clean(x) for k, x in v.items()}
    if isinstance(v, list):
        return [clean(x) for x in v]
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        return float(v) if math.isfinite(float(v)) else None
    return v


def csv_write(path: Path, rows: list[dict], fields: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(clean(rows))


def ranks_with_ties(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    order = np.argsort(x, kind="mergesort")
    sorted_x = x[order]
    ends = np.r_[np.flatnonzero(np.diff(sorted_x) != 0), len(x)-1]
    result = np.empty(len(x), dtype=np.float64)
    start = 0
    for end in ends:
        result[order[start:end+1]] = (start + end) / 2.0 + 1.0
        start = end + 1
    return result


def spearman(x, y) -> tuple[float, int]:
    a = np.asarray(x, dtype=np.float64)
    b = np.asarray(y, dtype=np.float64)
    ok = np.isfinite(a) & np.isfinite(b)
    a, b = a[ok], b[ok]
    if len(a) < 3 or np.unique(a).size < 2 or np.unique(b).size < 2:
        return float("nan"), int(len(a))
    ar, br = ranks_with_ties(a), ranks_with_ties(b)
    return float(np.corrcoef(ar, br)[0, 1]), int(len(a))


def audit_m80a(input_dir: Path) -> tuple[list[dict], list[dict], dict]:
    mp = input_dir / "m80a_manifest.json"
    ip = input_dir / "m80a_dev_per_image.csv"
    ep = input_dir / "m80a_dev_by_event.csv"
    for p in (mp, ip, ep):
        if not p.is_file():
            raise FileNotFoundError(f"Missing M8.0A input: {p}")
    manifest = json.loads(mp.read_text(encoding="utf-8"))
    if manifest.get("status") != "COMPLETE_3_FOLD_DEV_ONLY" or manifest.get("no_fitting") is not True:
        raise ValueError(
            "Expected a complete, no-fitting 3-fold DEV M8.0A manifest")
    if manifest.get("no_threshold_search") is not True or manifest.get("no_recalibration") is not True:
        raise ValueError(
            "M8.0A manifest does not confirm frozen probability policy")
    if not math.isclose(float(manifest.get("threshold", -1)), .5, abs_tol=1e-12):
        raise ValueError("M8.0A threshold must be fixed at 0.5")
    images, event_rows = read_csv(ip), read_csv(ep)
    if len(images) != 141 or len(event_rows) != 3:
        raise ValueError(
            f"Expected 141 full DEV images and 3 events, got {len(images)}, {len(event_rows)}")
    seen = set()
    for r in images:
        event = r["validation_event"]
        if event not in EXPECTED_FOLDS or r["fold"] != EXPECTED_FOLDS[event][0]:
            raise ValueError(f"Unexpected DEV fold/event: {r}")
        key = (event, r["image"])
        if key in seen:
            raise ValueError(f"Duplicate DEV image: {key}")
        seen.add(key)
        values = [int(r[k]) for k in ("tp", "tn", "fp", "fn")]
        n = int(r["valid_pixels"])
        if sum(values) != n or values[0] + values[3] != int(r["gt_water_pixels"]):
            raise ValueError(f"Confusion matrix inconsistent: {key}")
        if int(r["n_members"]) != 3:
            raise ValueError(f"Expected three ensemble members: {key}")
        u = values[0] + values[2] + values[3]
        iou_calc = values[0] / u if u else float("nan")
        iou_csv = as_float(r["iou"])
        if not (math.isclose(iou_calc, iou_csv, abs_tol=1e-8) or (math.isnan(iou_calc) and math.isnan(iou_csv))):
            raise ValueError(f"IoU disagreement: {key}")
    for event in EVENTS:
        subset = [r for r in images if r["validation_event"] == event]
        if len(subset) != EXPECTED_FOLDS[event][1]:
            raise ValueError(f"Incomplete DEV event: {event}: {len(subset)}")
        er = next(
            (r for r in event_rows if r["validation_event"] == event), None)
        if er is None or str(er["full_validation"]).lower() != "true":
            raise ValueError(f"Incomplete M8.0A event summary: {event}")
        for field in ("tp", "tn", "fp", "fn", "valid_pixels", "gt_water_pixels"):
            if sum(int(r[field]) for r in subset) != int(er[field]):
                raise ValueError(
                    f"Event summary mismatch for {event}, {field}")
    return images, event_rows, manifest


def image_level(images: list[dict]) -> tuple[list[dict], list[dict]]:
    diagnostics = []
    correlations = []
    for r in images:
        n = int(r["valid_pixels"])
        water = int(r["gt_water_pixels"])
        errors = int(r["fp"]) + int(r["fn"])
        diagnostics.append({
            "event": r["validation_event"], "image": r["image"],
            "valid_pixels": n, "gt_water_pixels": water,
            "gt_water_fraction": as_float(r["gt_water_fraction"]),
            "error_rate": errors / n, "miss_rate": int(r["fn"]) / water if water else float("nan"),
            "iou": as_float(r["iou"]), "brier": as_float(r["brier"]),
            **{metric: as_float(r[metric]) for metric, _ in IMAGE_METRICS},
        })
    # Within-event Spearman only; pixel/sample correlation must not be mistaken for independent tests.
    for event in EVENTS:
        subset = [x for x in diagnostics if x["event"] == event]
        for name, _ in IMAGE_METRICS:
            for outcome in ("error_rate", "miss_rate", "iou", "brier"):
                coef, n = spearman([x[name] for x in subset], [
                                   x[outcome] for x in subset])
                correlations.append({"event": event, "uncertainty": name,
                                     "outcome": outcome, "spearman_rho": coef,
                                     "n_images_defined": n,
                                     "note": "descriptive; no event-independent inferential test"})
    return diagnostics, correlations


def load_selected_npzs(input_dir: Path, full_images: list[dict], expected_n=9):
    directory = input_dir / "previews"
    available = sorted(directory.glob("dev_fold_*/*_ensemble.npz"))
    if len(available) != expected_n:
        raise ValueError(
            f"Expected {expected_n} selected DEV preview NPZ, found {len(available)}")
    index = {(x["fold"], x["image"]): x for x in full_images}
    for path in available:
        fold = path.parent.name
        stem = path.name.removesuffix("_ensemble.npz")
        row = index.get((fold, stem + ".tif"))
        if row is None:
            raise ValueError(f"Preview not in DEV full image table: {path}")
        with np.load(path, allow_pickle=False) as pack:
            if set(REQUIRED_ARRAYS) - set(pack.files):
                raise ValueError(f"Missing arrays in {path}")
            arrays = {key: pack[key] for key in REQUIRED_ARRAYS}
        dims = arrays["valid"].shape
        if len(dims) != 2 or any(a.shape != dims for a in arrays.values()):
            raise ValueError(f"Shape mismatch in {path}")
        valid = arrays["valid"].astype(bool)
        gt = arrays["gt_water"].astype(bool)
        p = arrays["p_water"]
        if not np.isfinite(p[valid]).all() or np.any((p[valid] < 0) | (p[valid] > 1)):
            raise ValueError(f"Invalid P(water) in {path}")
        for key in ("predictive_entropy_bits", "expected_entropy_bits", "mutual_information_bits", "variance"):
            if not np.isfinite(arrays[key][valid]).all():
                raise ValueError(f"Non-finite uncertainty in {path} / {key}")
        pred = p >= .5
        tp = np.count_nonzero(valid & gt & pred)
        tn = np.count_nonzero(valid & ~gt & ~pred)
        fp = np.count_nonzero(valid & ~gt & pred)
        fn = np.count_nonzero(valid & gt & ~pred)
        for key, got in (("tp", tp), ("tn", tn), ("fp", fp), ("fn", fn),
                         ("valid_pixels", np.count_nonzero(valid))):
            if int(row[key]) != got:
                raise ValueError(
                    f"NPZ disagrees with per-image CSV: {path}, {key}: {got} != {row[key]}")
        yield path, row, arrays


def pixel_level(input_dir: Path, images: list[dict]):
    sample_rows = []
    bins = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    # Qualitative sample only; sampled images were chosen for previews and case inspection.
    for path, row, data in load_selected_npzs(input_dir, images):
        valid = data["valid"].astype(bool)
        gt = data["gt_water"].astype(bool)[valid]
        p = data["p_water"][valid].astype(np.float64)
        ent = data["predictive_entropy_bits"][valid].astype(np.float64)
        mi = data["mutual_information_bits"][valid].astype(np.float64)
        pred = p >= .5
        error = pred != gt
        fn = gt & ~pred
        n = len(p)
        k_top = max(1, int(math.ceil(n * 0.1)))
        low_prob_missed = int(np.count_nonzero(gt & (p < .1)))
        # Capture of all wrong pixels in a predeclared top 10% uncertainty ranking.

        def capture_and_enrichment(score):
            top = np.argpartition(score, n - k_top)[n - k_top:]
            selected_err = int(np.count_nonzero(error[top]))
            total_err = int(np.count_nonzero(error))
            if total_err == 0:
                return float("nan"), float("nan"), 0
            capture = selected_err / total_err
            enrichment = (selected_err / k_top) / (total_err / n)
            return capture, enrichment, selected_err
        ent_cap, ent_lift, ent_num = capture_and_enrichment(ent)
        mi_cap, mi_lift, mi_num = capture_and_enrichment(mi)
        sample_rows.append({
            "event": row["validation_event"], "image": row["image"],
            "pixels": n, "gt_water": int(gt.sum()), "errors": int(error.sum()),
            "false_negatives": int(fn.sum()), "fn_p_lt_0_1": low_prob_missed,
            "gt_water_p_lt_0_1_fraction": low_prob_missed / int(gt.sum()) if int(gt.sum()) else float("nan"),
            "fn_p_lt_0_1_fraction_of_fn": low_prob_missed / int(fn.sum()) if int(fn.sum()) else float("nan"),
            "entropy_top10pct_error_capture": ent_cap, "entropy_top10pct_error_enrichment": ent_lift,
            "entropy_top10pct_errors": ent_num,
            "mi_top10pct_error_capture": mi_cap, "mi_top10pct_error_enrichment": mi_lift,
            "mi_top10pct_errors": mi_num,
            "top10pct_pixels": k_top,
            "mean_entropy": float(ent.mean()), "mean_mi": float(mi.mean()),
        })
        # Equal-width confidence bins pooled BY EVENT over the 3 selected images.
        bindex = np.minimum((p * BIN_COUNT).astype(np.int32), BIN_COUNT-1)
        for b in range(BIN_COUNT):
            mask = bindex == b
            if not np.any(mask):
                continue
            agg = bins[row["validation_event"]][b]
            agg["n"] += int(mask.sum())
            agg["p_sum"] += float(p[mask].sum())
            agg["water_sum"] += int(gt[mask].sum())
            agg["error_sum"] += int(error[mask].sum())
    bins_rows, event_summaries = [], []
    for event in EVENTS:
        ece_sum = 0.0
        total_n = sum(v["n"] for v in bins[event].values())
        for b in range(BIN_COUNT):
            agg = bins[event][b]
            n = int(agg["n"])
            mean_p = agg["p_sum"]/n if n else float("nan")
            observed = agg["water_sum"]/n if n else float("nan")
            risk = agg["error_sum"]/n if n else float("nan")
            if n:
                ece_sum += n / total_n * abs(mean_p - observed)
            bins_rows.append({"event": event, "bin": b + 1,
                              "p_lower": b/BIN_COUNT, "p_upper": (b+1)/BIN_COUNT,
                              "n_pixels": n, "mean_p": mean_p,
                              "observed_water_fraction": observed, "error_rate": risk})
        subset = [r for r in sample_rows if r["event"] == event]
        if len(subset) != 3:
            raise ValueError(
                f"Expected 3 pixel selected previews in {event}, got {len(subset)}")
        total_water = sum(r["gt_water"] for r in subset)
        total_errors = sum(r["errors"] for r in subset)
        total_fn = sum(r["false_negatives"] for r in subset)
        top_count = sum(r["top10pct_pixels"] for r in subset)
        e_top = sum(r["entropy_top10pct_errors"] for r in subset)
        m_top = sum(r["mi_top10pct_errors"] for r in subset)
        total_low = sum(r["fn_p_lt_0_1"] for r in subset)
        event_summaries.append({
            "event": event, "n_selected_images": len(subset), "valid_pixels_selected": total_n,
            "gt_water_selected": total_water, "errors_selected": total_errors,
            "false_negatives_selected": total_fn,
            "p_lt_0_1_on_gt_water_fraction": total_low/total_water if total_water else float("nan"),
            "p_lt_0_1_on_fn_fraction": total_low/total_fn if total_fn else float("nan"),
            "selected_ece_15_bins": ece_sum,
            "entropy_top10pct_error_capture": e_top/total_errors if total_errors else float("nan"),
            "mi_top10pct_error_capture": m_top/total_errors if total_errors else float("nan"),
            "entropy_top10pct_error_enrichment": (e_top/top_count)/(total_errors/total_n) if total_errors else float("nan"),
            "mi_top10pct_error_enrichment": (m_top/top_count)/(total_errors/total_n) if total_errors else float("nan"),
        })
    return sample_rows, bins_rows, event_summaries


def save_figures(out: Path, diag: list[dict], binned: list[dict], events: list[dict]):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.4), sharey=True)
    for ax, event in zip(axes, EVENTS):
        z = [r for r in diag if r["event"] == event]
        ax.scatter([r["mean_mutual_information_bits"] for r in z],
                   [r["error_rate"] for r in z], alpha=.8, s=20)
        ax.set_title(f"{event} ({len(z)} images)")
        ax.set_xlabel("Mean MI (bits / image)")
        ax.grid(alpha=.2)
    axes[0].set_ylabel("Pixel error rate / image")
    fig.suptitle(
        "M8.0B DEV only: image-level disagreement vs error (not causal)")
    fig.tight_layout()
    fig.savefig(out/"m80b_image_error_vs_mi.png", dpi=150)
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), sharex=True, sharey=True)
    for ax, event in zip(axes, EVENTS):
        z = [r for r in binned if r["event"] == event and r["n_pixels"] > 0]
        ax.plot([0, 1], [0, 1], ls="--", color="gray", lw=1.3)
        ax.plot([r["mean_p"] for r in z], [r["observed_water_fraction"] for r in z],
                marker="o", markersize=4)
        ax.set_title(f"{event} — selected 3 images")
        ax.set_xlabel("Mean predicted P(water)")
        ax.set_aspect("equal", adjustable="box")
        ax.grid(alpha=.25)
    axes[0].set_ylabel("Observed surface-water fraction")
    fig.suptitle("M8.0B sample-only reliability (15 fixed bins; NOT full DEV)")
    fig.tight_layout()
    fig.savefig(out/"m80b_selected_reliability.png", dpi=150)
    plt.close(fig)

    x = np.arange(3)
    fig, ax = plt.subplots(figsize=(9, 5.2))
    a = [z["entropy_top10pct_error_capture"] for z in events]
    b = [z["mi_top10pct_error_capture"] for z in events]
    ax.bar(x-.18, a, width=.35, label="Predictive entropy")
    ax.bar(x+.18, b, width=.35, label="Mutual information")
    ax.axhline(.10, ls="--", color="gray",
               label="10% random-pixel expectation")
    ax.set_xticks(x, EVENTS)
    ax.set_ylim(0, 1)
    ax.set_ylabel(
        "Share of all wrong pixels found in top-10%-uncertainty pixels")
    ax.set_title("M8.0B selected preview images only (3 per DEV event)")
    ax.legend(loc="best")
    ax.grid(axis="y", alpha=.2)
    fig.tight_layout()
    fig.savefig(out/"m80b_selected_error_capture.png", dpi=150)
    plt.close(fig)


def make_report(out: Path, manifest: dict, diag: list[dict], corr: list[dict], events: list[dict]):
    lines = [
        "# M8.0B — DEV Uncertainty Reliability & Error Audit",
        "", "**Status:** DESCRIPTIVE_DEV_ONLY — No model fitting, recalibration, threshold search or independent TEST.",
        "", f"- M8.0A source protocol fingerprint: `{manifest['frozen_baseline_fingerprint']}`",
        "- Whole-DEV image-level descriptive analysis: **141/141 validation chips from 3 events**.",
        "- Pixel-level analyses: **9 specifically selected preview chips (3 per event)**; **not an unbiased sample**.",
        "- Prediction rule remains P(water) >= 0.50. UQ values were not used to optimize any decision threshold.",
        "- Pixel correlations do not imply independent samples because pixels within and across chips are spatially correlated.",
        "", "## A. Event-level image correlations (within each DEV event)",
        "", "Spearman rank correlation. Negative rho for IoU means higher UQ coincides with lower IoU; sign may differ by event.",
        "", "| Event | Mean MI vs image error rate | Mean entropy vs image error rate | Mean MI vs image IoU |",
        "|---|---:|---:|---:|",
    ]
    def find(e, uncertainty, outcome): return next(
        r["spearman_rho"] for r in corr if r["event"] == e and r["uncertainty"] == uncertainty and r["outcome"] == outcome)

    def num(v): return f"{v:+.3f}" if math.isfinite(v) else "undefined"
    for e in EVENTS:
        lines.append(f"| {e} | {num(find(e, 'mean_mutual_information_bits', 'error_rate'))} | {num(find(e, 'mean_predictive_entropy_bits', 'error_rate'))} | {num(find(e, 'mean_mutual_information_bits', 'iou'))} |")
    lines.extend([
        "", "Do **not** pool the three events and claim that image-level MI is a causal or universally reliable error predictor. Mean UQ is affected by water prevalence and the location of boundaries.",
        "", "## B. Selected nine-preview pixel-level audit (NOT the full validation population)",
        "", "Top-10%-UQ capture is the share of all wrongly predicted pixels found after ranking pixels by an uncertainty score and selecting only its highest 10% within each preview image.",
        "**10% is fixed in advance, not optimized.** Error enrichment compares the top-10% error rate to the image(s)' overall error rate.",
        "", "| Event | Selected ECE (15 bins) | Entropy top-10% error capture | MI top-10% error capture | GT water with P<0.1 |",
        "|---|---:|---:|---:|---:|",
    ])
    for x in events:
        lines.append(f"| {x['event']} | {x['selected_ece_15_bins']:.4f} | {x['entropy_top10pct_error_capture']:.1%} | {x['mi_top10pct_error_capture']:.1%} | {x['p_lt_0_1_on_gt_water_fraction']:.1%} |")
    lines.extend([
        "", "Selected ECE is a pixel-weighted reliability summary from **nine selected cases**, not full-DEV ECE and not a guarantee of calibrated individual decisions.",
        "High error-capture can result from focusing on boundaries; low MI can coincide with confidently wrong predictions, so visualize false-negative regions as well.",
        "", "## C. Boundaries and reporting constraints",
        "", "- **Cannot infer full 141-image pixel-level ECE/AUROC** from the 9 stored NPZ previews. Full pixel-level statements require rerunning fixed-checkpoint DEV-only inference over all 141 images, preserving original model/threshold.",
        "- **Cannot conclude UQ helps safely reject or deploy predictions** on independent geography without a new untouched labeled event.",
        "- The reported correlations are descriptive (no p-values or confidence intervals as if pixels were independent).",
        "- The 9 previews were selected non-randomly; do not generalize their ECE/error-capture to the complete dataset.",
        "- M8.0B uses no India/Paraguay/Ghana TEST, Bolivia, or Thailand data, and does not change M7.6A design or V2-B method.",
        "", "## D. Recommended next research step",
        "", "Return to **M7.6B**: implement the previously frozen TRAIN-only water-coverage sampler in a separate trainer, unit-test its sampling probabilities and masking rules, then smoke-test without accessing TEST. Next M7.6C: train 3 folds × 3 seeds; M7.6D: compare paired DEV results under frozen settings.",
        "", "## Output files", "",
        "- `m80b_image_level_correlations.csv`, `m80b_image_level_diagnostics.csv` — 141 DEV images",
        "- `m80b_selected_preview_by_image.csv`, `m80b_selected_preview_by_event.csv` — 9 selected previews",
        "- `m80b_selected_reliability_bins.csv` — event-level sampled reliability curves",
        "- `m80b_image_error_vs_mi.png`, `m80b_selected_reliability.png`, `m80b_selected_error_capture.png` — figures",
        "- `m80b_manifest.json` — source hashes and provenance", "",
    ])
    (out/"m80b_report.md").write_text("\n".join(lines), encoding="utf-8")


def self_test():
    rho, n = spearman([1, 2, 2, 4], [2, 4, 4, 8])
    assert abs(rho-1) < 1e-12 and n == 4
    rho, n = spearman([0, 1, 2, 3], [3, 2, 1, 0])
    assert abs(rho+1) < 1e-12
    rho, n = spearman([1, 1], [2, 3])
    assert math.isnan(rho)
    # Fixed 15-bin policy: p=1 must fall in final bin.
    assert min(int(1.0 * BIN_COUNT), BIN_COUNT-1) == BIN_COUNT-1
    print("PASS M8.0B: rank-with-ties, missing-value handling and fixed probability bins")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input-dir", type=Path,
                   default=Path("results/event_level_v2/m80a_dev_ensemble_uq"))
    p.add_argument("--output-dir", type=Path,
                   default=Path("results/event_level_v2/m80b_dev_uncertainty_audit"))
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args()
    if a.self_test:
        self_test()
        return
    inp = a.input_dir.resolve()
    out = a.output_dir.resolve()
    if inp == out or inp.is_relative_to(out) or out.is_relative_to(inp):
        raise ValueError(
            "Input and output directories must be separate, non-overlapping paths")
    images, events0, manifest = audit_m80a(inp)
    diag, corr = image_level(images)
    cases, reliability, sample_event = pixel_level(inp, images)
    out.mkdir(parents=True, exist_ok=True)
    csv_write(out/"m80b_image_level_diagnostics.csv",
              diag, list(diag[0].keys()))
    csv_write(out/"m80b_image_level_correlations.csv",
              corr, list(corr[0].keys()))
    csv_write(out/"m80b_selected_preview_by_image.csv",
              cases, list(cases[0].keys()))
    csv_write(out/"m80b_selected_preview_by_event.csv",
              sample_event, list(sample_event[0].keys()))
    csv_write(out/"m80b_selected_reliability_bins.csv",
              reliability, list(reliability[0].keys()))
    save_figures(out, diag, reliability, sample_event)
    make_report(out, manifest, diag, corr, sample_event)
    files = [inp/x for x in ("m80a_manifest.json",
                             "m80a_dev_per_image.csv", "m80a_dev_by_event.csv")]
    files += sorted((inp/"previews").glob("dev_fold_*/*_ensemble.npz"))
    provenance = {
        "status": "DESCRIPTIVE_DEV_ONLY", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "input_dir": str(inp), "input_file_sha256": {str(f.relative_to(inp)): sha256_file(f) for f in files},
        "frozen_baseline_fingerprint": manifest["frozen_baseline_fingerprint"],
        "n_dev_images": len(images), "n_sample_npzs": len(cases),
        "events": list(EVENTS), "threshold": .5,
        "sample_selection": "3 selected M8.0A previews per event, not random, NOT representative",
        "probability_bins": BIN_COUNT, "uncertainty_top_fraction": .10,
        "no_training": True, "no_inference": True, "no_recalibration": True,
        "no_hyperparameter_selection": True,
        "accessed_splits": ["DEV VALID (from stored M8.0A files)"],
        "never_used": ["historical TEST", "Bolivia", "Thailand"],
        "warning": "Do not extrapolate pixel-level results from selected 9 NPZ to 141 DEV images",
    }
    (out/"m80b_manifest.json").write_text(json.dumps(clean(provenance),
                                                     indent=2, ensure_ascii=False, allow_nan=False)+"\n", encoding="utf-8")
    print("=== M8.0B READ-ONLY DEV UNCERTAINTY AUDIT ===")
    print(
        f"PASS full image-level validation: {len(images)} / 141 images, 3 events")
    print(f"PASS selected pixel NPZ validation: {len(cases)} / 9 cases")
    for e in EVENTS:
        mierr = next(c["spearman_rho"] for c in corr if c["event"] == e and c["uncertainty"]
                     == "mean_mutual_information_bits" and c["outcome"] == "error_rate")
        se = next(x for x in sample_event if x["event"] == e)
        print(
            f"{e:12} image-level MI-vs-error Spearman={mierr:+.3f}; selected ECE={se['selected_ece_15_bins']:.4f}; top10 MI error capture={se['mi_top10pct_error_capture']:.1%}")
    print("SAVED:", out)
    print("No training, TEST inference, threshold tuning or recalibration.")


if __name__ == "__main__":
    main()
