#!/usr/bin/env python3
"""M6.5A: reproducible baseline performance summary (read-only on existing results).

Inputs:
  results/event_level_v1/cross_event_reliability/cross_event_reliability_summary.csv
  results/event_level_v1/fold_XX_*/evaluation/evaluation_summary.csv (optional QA)

Outputs:
  results/event_level_v1/m65a_baseline_summary/
    m65a_event_comparison.csv
    m65a_baseline_summary.md
    m65a_performance_comparison.png
    m65a_validation_log.txt

No model training, threshold adjustment, or checkpoint modifications occur.
"""
from __future__ import annotations
import argparse
import csv
import math
from pathlib import Path

EVENTS = [
    {"event": "India", "fold": "fold_01_india", "train": 288,
        "valid": 69, "test": 68, "val_event": "USA"},
    {"event": "Paraguay", "fold": "fold_02_paraguay", "train": 317,
        "valid": 42, "test": 66, "val_event": "Sri-Lanka"},
    {"event": "Ghana", "fold": "fold_03_ghana", "train": 347,
        "valid": 30, "test": 48, "val_event": "Spain"},
]
REQUIRED = {
    "held_out_event", "n_images", "iou", "precision", "recall", "brier", "nll", "ece", "fn_p_lt_0_1_share_of_gt_water"
}
FIELDS = [
    "fold", "train_event_count", "n_train", "validation_event", "n_valid", "test_event", "n_test",
    "iou", "f1_derived", "precision", "recall", "brier", "nll", "ece",
    "gt_water_p_lt_0_1_fraction", "fn_p_lt_0_1_fraction_of_all_fn"
]


def read_csv(path: Path):
    if not path.is_file():
        raise FileNotFoundError(f"Missing required file: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        return r.fieldnames or [], list(r)


def nfloat(row, name):
    try:
        val = float(row[name])
    except (KeyError, TypeError, ValueError) as ex:
        raise ValueError(f"Invalid field {name}: {row.get(name)!r}") from ex
    if not math.isfinite(val):
        raise ValueError(f"Non-finite {name}: {val}")
    return val


def pretty(x, d=4):
    return f"{x:.{d}f}"


def write_barplot(rows, out: Path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return "SKIP figure: matplotlib not installed. (pip install matplotlib)"
    metrics = [
        ("iou", "Water IoU", False),
        ("f1_derived", "Water F1 (Dice)", False),
        ("precision", "Water precision", False),
        ("recall", "Water recall", False),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(11, 7.5), constrained_layout=True)
    fig.suptitle(
        "M6.5A — Event-disjoint test performance (3 fold-specific checkpoints)", fontsize=13)
    labels = [r["test_event"] for r in rows]
    for ax, (key, title, _) in zip(axes.flat, metrics):
        values = [r[key] for r in rows]
        ax.bar(labels, values)
        ax.set_ylim(0, 1)
        ax.set_title(title)
        ax.set_ylabel("Score")
        ax.grid(axis="y", alpha=0.2)
        for i, v in enumerate(values):
            ax.text(i, v + 0.018, f"{v:.3f}",
                    ha="center", va="bottom", fontsize=10)
    fig.savefig(out, dpi=180, facecolor="white",
                transparent=False, bbox_inches="tight")
    plt.close(fig)
    return f"Created: {out}"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results-root", type=Path,
                   default=Path("results/event_level_v1"))
    p.add_argument("--input-csv", type=Path, default=None)
    p.add_argument("--output-dir", type=Path, default=None)
    a = p.parse_args()
    inp = a.input_csv or a.results_root / "cross_event_reliability" / \
        "cross_event_reliability_summary.csv"
    outdir = a.output_dir or a.results_root / "m65a_baseline_summary"
    cols, input_rows = read_csv(inp)
    missing = REQUIRED - set(cols)
    if missing:
        raise ValueError(
            f"Missing M6.4C columns: {sorted(missing)}. Found: {cols}")
    lookup = {}
    for row in input_rows:
        ev = row["held_out_event"].strip().lower()
        if ev in lookup:
            raise ValueError(f"Duplicate held_out_event: {ev}")
        lookup[ev] = row
    expected = {x["event"].lower() for x in EVENTS}
    if set(lookup) != expected:
        raise ValueError(
            f"Events do not match expected 3 folds; found {sorted(lookup)}, expected {sorted(expected)}")

    results = []
    notes = [
        f"Source: {inp}", "Fixed threshold: 0.5 (from prior model/checkpoint logs; verify in checkpoint if needed)"]
    print("=== M6.5A: Three-fold baseline performance ===")
    for spec in EVENTS:
        row = lookup[spec["event"].lower()]
        n = int(row["n_images"])
        if n != spec["test"]:
            raise ValueError(
                f"Test count mismatch: {spec['event']} expected {spec['test']}, got {n}")
        metrics = {k: nfloat(row, k)
                   for k in REQUIRED - {"held_out_event", "n_images"}}
        iou, precision, recall = metrics["iou"], metrics["precision"], metrics["recall"]
        f1 = 2 * iou / (1 + iou) if iou >= 0 else float("nan")
        fn_share_gt = metrics["fn_p_lt_0_1_share_of_gt_water"]
        all_fn_share_gt = 1 - recall
        fn_share_of_fn = fn_share_gt / \
            all_fn_share_gt if all_fn_share_gt > 0 else float("nan")
        if not (0 <= fn_share_gt <= all_fn_share_gt + 1e-6):
            raise ValueError(
                f"FN probability group inconsistency: {spec['event']}")
        r = dict(
            fold=spec["fold"], train_event_count=8, n_train=spec["train"],
            validation_event=spec["val_event"], n_valid=spec["valid"],
            test_event=spec["event"], n_test=n,
            iou=iou, f1_derived=f1, precision=precision, recall=recall,
            brier=metrics["brier"], nll=metrics["nll"], ece=metrics["ece"],
            gt_water_p_lt_0_1_fraction=fn_share_gt,
            fn_p_lt_0_1_fraction_of_all_fn=fn_share_of_fn)
        results.append(r)
        print(
            f"{spec['event']:9s} test={n:2d} IoU={iou:.4f} F1={f1:.4f} Precision={precision:.4f} Recall={recall:.4f}")
        summary_path = a.results_root / \
            spec["fold"] / "evaluation" / "evaluation_summary.csv"
        if summary_path.exists():
            _, verify_rows = read_csv(summary_path)
            candidates = [s for s in verify_rows if s.get(
                "split", "").strip().lower() == "test"]
            if len(candidates) != 1:
                raise ValueError(
                    f"Expected one TEST row in {summary_path}, got {len(candidates)}")
            v = candidates[0]
            for key in ("iou", "precision", "recall"):
                diff = abs(nfloat(v, key) - r[key])
                if diff > 0.001:
                    raise ValueError(
                        f"QA FAIL {spec['event']} {key}: M6.4C {r[key]:.6f} != previous eval {v[key]}")
            if "f1" in v and abs(nfloat(v, "f1") - f1) > 0.001:
                raise ValueError(
                    f"QA FAIL {spec['event']} F1 differs from IoU-derived F1")
            if "n_images" in v and int(v["n_images"]) != n:
                raise ValueError(
                    f"QA FAIL {spec['event']} image count differs from eval CSV")
            notes.append(f"PASS prior TEST metric consistency: {summary_path}")
        else:
            notes.append(
                f"WARN previous evaluation_summary.csv unavailable (not cross-checked): {summary_path}")

    outdir.mkdir(parents=True, exist_ok=True)
    csv_path = outdir / "m65a_event_comparison.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(results)

    best_iou = max(results, key=lambda r: r["iou"])
    worst_iou = min(results, key=lambda r: r["iou"])
    best_recall = max(results, key=lambda r: r["recall"])
    md = [
        "# M6.5A — Baseline Event-Level Performance Summary",
        "",
        "**Study design:** Three event-disjoint test folds, each evaluated with its own independently trained Small U-Net checkpoint and fixed classification threshold 0.5. The fold comparisons are descriptive; the trained models and validation events are different.",
        "",
        "## Dataset partitions",
        "",
        "| Fold | Train images | Validation event (n) | Test event (n) | Bolivia external holdout |",
        "|---|---:|---|---|---|",
    ]
    for r in results:
        md.append(f"| {r['fold']} | {r['n_train']} | {r['validation_event']} ({r['n_valid']}) | {r['test_event']} ({r['n_test']}) | 15 (not used for model selection) |")
    md += [
        "", "## Test segmentation results", "",
        "| Held-out event | IoU | F1 (derived) | Precision | Recall |",
        "|---|---:|---:|---:|---:|",
    ]
    for r in results:
        md.append(
            f"| {r['test_event']} | {pretty(r['iou'])} | {pretty(r['f1_derived'])} | {pretty(r['precision'])} | {pretty(r['recall'])} |")
    md += [
        "", "## Supplementary probability diagnostics", "",
        "| Event | Brier ↓ | NLL ↓ | ECE ↓ | GT water with P(water)<0.1 ↓ | Low-P portion of FN ↓ |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        md.append(f"| {r['test_event']} | {pretty(r['brier'], 5)} | {pretty(r['nll'], 5)} | {pretty(r['ece'], 5)} | {r['gt_water_p_lt_0_1_fraction']:.1%} | {r['fn_p_lt_0_1_fraction_of_all_fn']:.1%} |")
    md += [
        "", "## Findings (descriptive only)", "",
        f"- **{best_iou['test_event']}** has the highest observed test IoU ({best_iou['iou']:.4f}) and **{best_recall['test_event']}** the highest recall ({best_recall['recall']:.4f}).",
        f"- **{worst_iou['test_event']}** has the lowest test IoU ({worst_iou['iou']:.4f}) and substantial missed ground-truth water.",
        "- Better whole-image probability scores (Brier/NLL/ECE) do not necessarily imply better water recall, particularly with many land pixels.",
        "- Results are observational; they do not isolate geography from changes in training events, selected checkpoint, or ground-truth distribution.",
        "", "## Reproducibility / interpretation boundaries", "",
        "1. Do not select hyperparameters, adjust thresholds, or calibrate based on these already inspected TEST events.",
        "2. Each TEST event belongs to a separate fold-specific checkpoint; do not pool pixels as if a single model had been evaluated on all three events.",
        "3. The count of 15 Bolivia holdout images is retained in each fold but is not added to these per-fold TEST scores.",
        "4. Thailand pilot agreement with UNOSAT is NOT equivalent to independently verified water/land test labels.",
        "5. F1 is derived using the binary micro relation F1 = 2*IoU/(1+IoU), not re-estimated from independent model inference.",
        "6. The train/validation counts and event labels shown here are taken from previously supplied fold logs; the script cross-checks test metrics against evaluation_summary.csv when those files exist.",
        "", "## Suggested figure", "", "![Comparison](m65a_performance_comparison.png)", "",
    ]
    md_path = outdir / "m65a_baseline_summary.md"
    md_path.write_text("\n".join(md), encoding="utf-8")
    notes_path = outdir / "m65a_validation_log.txt"
    notes_path.write_text("\n".join(notes) + "\n", encoding="utf-8")
    figure_note = write_barplot(
        results, outdir / "m65a_performance_comparison.png")
    print("\nSaved:")
    print(" ", csv_path)
    print(" ", md_path)
    print(" ", notes_path)
    print(" ", figure_note)
    for line in notes[2:]:
        print(line)
    print("Important: TEST results are for descriptive evaluation only; do not tune using them.")


if __name__ == "__main__":
    main()
