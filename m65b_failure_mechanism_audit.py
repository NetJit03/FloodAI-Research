#!/usr/bin/env python3
"""M6.5B | Retrospective failure-mechanism evidence audit.

Reads existing CSV artifacts. Does NOT train, tune thresholds, or modify existing files.
Built for the FloodAI-Research event_level_v1 directory.
"""
from __future__ import annotations

import argparse
import csv
import math
import statistics
from collections import Counter
from pathlib import Path


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Required CSV not found: {path}")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"CSV is empty: {path}")
    return rows


def number(value, default=float("nan")) -> float:
    try:
        v = float(value)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


def pct(value: float, digits=2) -> str:
    return f"{100 * value:.{digits}f}%" if math.isfinite(value) else "N/A"


def fmt(value: float, digits=4) -> str:
    return f"{value:.{digits}f}" if math.isfinite(value) else "N/A"


def require_columns(rows, columns, name):
    absent = sorted(set(columns) - set(rows[0]))
    if absent:
        raise ValueError(
            f"{name}: missing columns {absent}; available={list(rows[0])}")


def write_csv(path: Path, rows: list[dict[str, object]]):
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", type=Path,
                        default=Path("results/event_level_v1"))
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    root = args.results_root
    out = args.output_dir or root / "m65b_failure_mechanism_audit"
    out.mkdir(parents=True, exist_ok=True)

    cross_path = root / "cross_event_reliability/cross_event_reliability_summary.csv"
    sep_path = root / "ghana_sar_diagnostics/ghana_all_image_sar_separability.csv"
    clip_path = root / "normalization_audit_fold03/clipping_by_event.csv"
    cal_path = root / "calibration_fold03/calibration_by_split.csv"
    spatial_path = root / "spatial_uncertainty_fold03/spatial_uncertainty_selected_images.csv"

    cross = read_csv(cross_path)
    sep = read_csv(sep_path)
    clip = read_csv(clip_path)
    require_columns(cross, ["held_out_event", "n_images", "iou", "precision", "recall",
                            "brier", "nll", "ece", "fn_p_lt_0_1_share_of_gt_water"], "cross-event")
    require_columns(sep, ["image", "water_pixels", "land_pixels", "vv_delta", "vh_delta",
                          "recall", "water_fraction"], "Ghana separability")
    require_columns(clip, ["split", "event", "polarization", "class", "n_pixels",
                           "pct_clipped_total"], "clipping")

    events = {r["held_out_event"].strip().lower(): r for r in cross}
    expected = ("india", "paraguay", "ghana")
    missing = set(expected) - set(events)
    if missing:
        raise ValueError(f"Cross-event summary missing: {sorted(missing)}")

    overview = []
    for name in expected:
        r = events[name]
        recall = number(r["recall"])
        high_gt = number(r["fn_p_lt_0_1_share_of_gt_water"])
        fn_share = high_gt / (1 - recall) if 0 <= recall < 1 else float("nan")
        overview.append({
            "held_out_event": name.title(),
            "n_images": int(number(r["n_images"])),
            "iou": r["iou"], "precision": r["precision"],
            "recall": r["recall"], "brier": r["brier"],
            "nll": r["nll"], "ece": r["ece"],
            "gt_water_p_lt_0_1_fraction": r["fn_p_lt_0_1_share_of_gt_water"],
            "fn_p_lt_0_1_fraction_of_all_fn_derived": fmt(fn_share, 6),
        })
    write_csv(out / "m65b_cross_event_evidence.csv", overview)

    vv = [number(r["vv_delta"]) for r in sep]
    vh = [number(r["vh_delta"]) for r in sep]
    valid_pairs = [(r, a, b) for r, a, b in zip(sep, vv, vh)
                   if math.isfinite(a) and math.isfinite(b)]
    n_vv_negative = sum(a < 0 for _, a, _ in valid_pairs)
    n_vh_negative = sum(b < 0 for _, _, b in valid_pairs)
    n_vv_positive = sum(a > 0 for _, a, _ in valid_pairs)
    n_vh_positive = sum(b > 0 for _, _, b in valid_pairs)
    med_vv = statistics.median(
        a for _, a, _ in valid_pairs) if valid_pairs else float("nan")
    med_vh = statistics.median(
        b for _, _, b in valid_pairs) if valid_pairs else float("nan")
    zero_class = [r for r in sep if number(
        r["water_pixels"]) == 0 or number(r["land_pixels"]) == 0]

    # The calibration CSV belongs to Fold 3 (Spain VALID, Ghana TEST), not all folds.
    calibrations = read_csv(cal_path) if cal_path.is_file() else []
    spatial = read_csv(spatial_path) if spatial_path.is_file() else []
    clip_filtered = []
    for r in clip:
        if r["class"].strip().lower() != "evaluable":
            continue
        clip_filtered.append({
            "fold": "03", "split": r["split"], "event": r["event"],
            "polarization": r["polarization"],
            "n_pixels": r["n_pixels"],
            "pct_clipped_total": r["pct_clipped_total"],
        })
    write_csv(out / "m65b_fold03_clipping_evidence.csv", clip_filtered)

    clip_by_key = {(r["event"].strip().lower(
    ), r["polarization"].strip().upper()): r for r in clip_filtered}
    ghana_vv = clip_by_key.get(("ghana", "VV"))
    ghana_vh = clip_by_key.get(("ghana", "VH"))

    # Descriptive notes only. Different checkpoints and different held-out events.
    lines = [
        "# M6.5B — Failure Mechanism Evidence Audit",
        "",
        "**Scope:** retrospective diagnostics based on pre-existing fold-specific test outputs. "
        "No retraining, threshold search, recalibration or model selection was performed.",
        "",
        "## A. Cross-event metrics (three different model checkpoints)",
        "",
        "| Event | n | IoU | Recall | ECE | Brier | NLL | GT water P<0.1 | FN with P<0.1 / all FN |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in overview:
        lines.append(
            f"| {item['held_out_event']} | {item['n_images']} | {fmt(number(item['iou']))} | "
            f"{fmt(number(item['recall']))} | {fmt(number(item['ece']))} | "
            f"{fmt(number(item['brier']))} | {fmt(number(item['nll']))} | "
            f"{pct(number(item['gt_water_p_lt_0_1_fraction']))} | "
            f"{pct(number(item['fn_p_lt_0_1_fraction_of_all_fn_derived']))} |"
        )
    lines.extend([
        "",
        "ECE/Brier/NLL summarize all evaluable pixels. Low global error does not imply "
        "good water recall, especially when land is prevalent.",
        "",
        "## B. Ghana SAR class separation (only chips containing both classes)",
        "",
        f"- Rows in separability file: **{len(sep)}**; rows with finite VV/VH gaps: **{len(valid_pairs)}**.",
        f"- VV median(water) − median(land): median across usable chips = **{fmt(med_vv, 3)}** raw TIFF units.",
        f"- VH median(water) − median(land): median across usable chips = **{fmt(med_vh, 3)}** raw TIFF units.",
        f"- VV negative / positive median gap chips: **{n_vv_negative} / {n_vv_positive}**.",
        f"- VH negative / positive median gap chips: **{n_vh_negative} / {n_vh_positive}**.",
        f"- Rows with a missing comparison class in the separability file: **{len(zero_class)}**. "
        "A separate audit is needed to explain excluded chips; a single-class chip can still "
        "be useful for segmentation evaluation.",
        "- SAR intensity separation here is label-conditional and descriptive, not a causal explanation of errors.",
        "",
        "## C. Fold 3 normalization clipping (evaluable pixels)",
        "",
        "Percentages below are the **CSV's percentage-point values** (not unit fractions).",
        "",
        "| Event | Split | Pol. | Evaluable pixels | Clipped (%) |",
        "|---|---|---|---:|---:|",
    ])
    for r in sorted(clip_filtered, key=lambda x: (x["split"], x["event"], x["polarization"])):
        lines.append(f"| {r['event']} | {r['split']} | {r['polarization']} | {r['n_pixels']} | "
                     f"{fmt(number(r['pct_clipped_total']), 4)} |")
    if ghana_vv and ghana_vh:
        lines.extend([
            "",
            f"- Ghana VV clipped: **{fmt(number(ghana_vv['pct_clipped_total']), 4)}%**; "
            f"Ghana VH clipped: **{fmt(number(ghana_vh['pct_clipped_total']), 4)}%**.",
            "- A small aggregate clipping share would make pervasive clipping an unlikely "
            "sole explanation for Ghana's recall gap, but does not rule out local effects.",
        ])
    lines.extend([
        "",
        "## D. Fold 3 calibration and spatial uncertainty inventory",
        "",
        f"- Calibration by split: **{'found: ' + str(len(calibrations)) + ' rows' if calibrations else 'missing'}**.",
        f"- Spatial selected-image metrics: **{'found: ' + str(len(spatial)) + ' rows' if spatial else 'missing'}**.",
    ])
    if calibrations:
        for r in calibrations:
            lines.append(
                f"- {r.get('split', 'unknown')}: Recall {fmt(number(r.get('recall')))}, "
                f"ECE {fmt(number(r.get('ece')))}, "
                f"Brier {fmt(number(r.get('brier')))}"
            )
    lines.extend([
        "- Single-model binary predictive entropy is low when P(water) is near 0 **or** 1. "
        "It cannot identify confidently wrong predictions without additional evidence.",
        "- Inspect stored spatial maps for where false negatives co-occur with low entropy; "
        "do not infer coverage from only three selected images.",
        "",
        "## E. Interpretive limits and next research steps",
        "",
        "1. Each held-out event was evaluated by a different checkpoint trained on a different set "
        "of source events. Differences are descriptive, not a controlled causal estimate of domain shift.",
        "2. These TEST findings are already examined. Do not optimize thresholds, preprocessing "
        "ranges, model choice or hyperparameters from them.",
        "3. New method candidates should be motivated by the literature and validated on "
        "independent development events. Reserve untouched events for final confirmation.",
        "4. Re-check label conventions, SAR finite masks and pixel grids when interpreting "
        "specific failure regions.",
        "5. Ground-truth 'water' is surface water, not necessarily newly inundated land.",
        "",
        "## Inputs inspected",
        "",
        f"- `{cross_path}`",
        f"- `{sep_path}`",
        f"- `{clip_path}`",
        f"- `{cal_path}` (optional)",
        f"- `{spatial_path}` (optional)",
        "",
    ])
    report = out / "m65b_evidence_audit.md"
    report.write_text("\n".join(lines), encoding="utf-8")

    print("=== M6.5B EVIDENCE AUDIT ===")
    for r in overview:
        print(f"{r['held_out_event']:9s} | IoU={float(r['iou']):.4f} | "
              f"Recall={float(r['recall']):.4f} | ECE={float(r['ece']):.4f} | "
              f"GT water p<0.1={pct(number(r['gt_water_p_lt_0_1_fraction']))} | "
              f"FN fraction with p<0.1={pct(number(r['fn_p_lt_0_1_fraction_of_all_fn_derived']))}")
    print(
        f"Ghana separability: {len(sep)} rows; {len(valid_pairs)} finite both-class comparisons")
    print(
        f"Ghana median gaps: VV={fmt(med_vv, 3)}, VH={fmt(med_vh, 3)} raw TIFF units")
    if ghana_vv and ghana_vh:
        print(
            f"Ghana clipping: VV={ghana_vv['pct_clipped_total']}%, VH={ghana_vh['pct_clipped_total']}%")
    print(
        f"Optional: calibration={len(calibrations)} rows; spatial metrics={len(spatial)} rows")
    print(f"Saved: {report}")
    print(f"Saved: {out / 'm65b_cross_event_evidence.csv'}")
    print(f"Saved: {out / 'm65b_fold03_clipping_evidence.csv'}")
    print("NOTE: TEST diagnostics only; no hyperparameter selection or causal claim.")


if __name__ == "__main__":
    main()
