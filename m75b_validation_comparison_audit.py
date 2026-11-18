#!/usr/bin/env python3
"""M7.5B: read-only, development-only, paired validation audit.

Inputs: results/event_level_v2/{baseline_seed*,v2a_eventbalanced_seed*}/dev_fold_*/
Reads only history.csv, run_config.json (if present) and best checkpoint files.
Never opens test, Bolivia, Thailand or source TIFFs. Does not fit or select models.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

FOLDS = (
    ("dev_fold_01_usa", "USA", 174, 69),
    ("dev_fold_02_sri_lanka", "Sri Lanka", 201, 42),
    ("dev_fold_03_spain", "Spain", 213, 30),
)
DEFAULT_SEEDS = (42, 123, 777)
HISTORY_NAMES = ("history.csv", "training_history.csv")
IOU_NAMES = ("val_iou", "validation_iou", "val_water_iou")
SELECTION_EPS = 1e-5
HARD_TOL = 2e-4


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda: f.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def find_file(folder: Path, names: tuple[str, ...]) -> Path | None:
    for name in names:
        p = folder / name
        if p.is_file():
            return p
    return None


def get_checkpoint(folder: Path) -> Path | None:
    selected = find_file(
        folder, ("best_sar_unet.pt", "best_model.pt", "best_checkpoint.pt"))
    if selected is not None:
        return selected
    options = sorted(folder.glob("best*.pt"))
    return options[0] if len(options) == 1 else None


def read_csv(path: Path) -> tuple[list[dict], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader), list(reader.fieldnames or [])


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def fmt(value: object, n: int = 5) -> str:
    return f"{value:.{n}f}" if isinstance(value, float) and math.isfinite(value) else str(value)


def val_from(d: dict, names: tuple[str, ...]) -> object:
    for key in names:
        if key in d:
            return d[key]
    return None


def read_checkpoint(path: Path, mode: str, warnings: list[str], errors: list[str]) -> dict:
    if mode == "skip":
        warnings.append(
            "Checkpoint metadata NOT examined (--checkpoint-metadata skip)")
        return {}
    try:
        import torch  # Optional in environments that only aggregate CSVs.
    except ImportError:
        msg = "PyTorch unavailable: checkpoint bytes hashed, metadata not inspected"
        (errors if mode == "require" else warnings).append(msg)
        return {}
    try:
        c = torch.load(path, map_location="cpu", weights_only=True)
        if not isinstance(c, dict):
            errors.append("Checkpoint is not a dictionary")
            return {}
        keys = ("epoch", "seed", "base_channels", "threshold", "train_count", "valid_count",
                "architecture", "db_min", "db_max", "validation_metrics", "label_scheme")
        return {key: c[key] for key in keys if key in c}
    except Exception as exc:
        errors.append(
            f"Cannot safely inspect checkpoint with torch.load(weights_only=True): {type(exc).__name__}: {str(exc)[:180]}")
        return {}


def check_param(where: str, name: str, actual: object, expected: object, warnings: list[str], errors: list[str], tol: float = 1e-9) -> None:
    if actual is None:
        warnings.append(f"{where}: {name} missing; cannot verify")
        return
    try:
        good = math.isclose(float(actual), float(
            expected), rel_tol=tol, abs_tol=tol)
    except (ValueError, TypeError):
        good = actual == expected
    if not good:
        errors.append(f"{where}: {name}={actual!r}; expected {expected!r}")


def inspect_run(root: Path, folder_name: str, seed: int, fold: tuple, method: str, mode: str) -> dict:
    fold_name, event, n_train, n_valid = fold
    folder = root / folder_name / fold_name
    errors: list[str] = []
    warnings: list[str] = []
    data = {
        "method": method, "event": event, "fold": fold_name, "seed": seed,
        "folder": str(folder), "expected_train": n_train, "expected_valid": n_valid,
        "history_path": "", "checkpoint_path": "", "checkpoint_sha256": "",
        "history_sha256": "", "config_sha256": "", "config_path": "",
        "epochs_run": "", "best_epoch": "", "best_iou": math.nan,
        "status": "", "errors": errors, "warnings": warnings,
    }
    if not folder.is_dir():
        errors.append(f"Missing run directory: {folder}")
        data["status"] = "ERROR"
        return data
    history = find_file(folder, HISTORY_NAMES)
    if history is None:
        errors.append("Missing history.csv")
        data["status"] = "ERROR"
        return data
    data["history_path"] = str(history)
    data["history_sha256"] = sha256(history)
    try:
        rows, fields = read_csv(history)
        iou_field = next((name for name in IOU_NAMES if name in fields), None)
        if not iou_field or "epoch" not in fields:
            raise ValueError(
                f"History must contain epoch and val_iou-like column; found {fields}")
        if not rows:
            raise ValueError("Empty history CSV")
        epoch_iou = []
        for row in rows:
            epoch = int(row["epoch"])
            iou = float(row[iou_field])
            if not math.isfinite(iou) or not (0 <= iou <= 1):
                raise ValueError(f"Invalid IoU at epoch={epoch}: {iou}")
            epoch_iou.append((epoch, iou))
        observed_epochs = [r[0] for r in epoch_iou]
        if observed_epochs != list(range(1, len(rows) + 1)):
            errors.append(
                f"History epochs not consecutively 1..N: {observed_epochs}")
        if len(rows) > 25:
            errors.append(
                f"Epoch count {len(rows)} exceeds frozen max epochs=25")
        selected_epoch, selected_iou = epoch_iou[0]
        for epoch, iou in epoch_iou[1:]:
            if iou > selected_iou + SELECTION_EPS:
                selected_epoch, selected_iou = epoch, iou
        data.update({"epochs_run": len(rows), "best_epoch": selected_epoch,
                    "best_iou": selected_iou, "history_iou_field": iou_field})
    except Exception as exc:
        errors.append(f"Cannot parse history: {exc}")

    checkpoint = get_checkpoint(folder)
    if checkpoint is None:
        errors.append(
            "Best checkpoint missing (expected best_sar_unet.pt or unique best*.pt)")
    else:
        data["checkpoint_path"] = str(checkpoint)
        data["checkpoint_sha256"] = sha256(checkpoint)
        ck = read_checkpoint(checkpoint, mode, warnings, errors)
        for field, expected in (("epoch", data["best_epoch"]), ("seed", seed),
                                ("base_channels", 16), ("train_count", n_train),
                                ("valid_count", n_valid), ("threshold", 0.5)):
            if expected != "":
                check_param("checkpoint", field, ck.get(
                    field), expected, warnings, errors)
        if "architecture" in ck and ck["architecture"] != "SmallUNet":
            errors.append(
                f"checkpoint: unexpected architecture {ck['architecture']!r}")
        db_min = ck.get("db_min")
        db_max = ck.get("db_max")
        if db_min is not None and list(db_min) != [-35.0, -40.0]:
            errors.append(
                f"checkpoint: db_min={db_min} inconsistent with frozen protocol")
        if db_max is not None and list(db_max) != [5.0, 0.0]:
            errors.append(
                f"checkpoint: db_max={db_max} inconsistent with frozen protocol")
        label_scheme = ck.get("label_scheme")
        if isinstance(label_scheme, dict) and (label_scheme.get("ignore") != -1 or label_scheme.get("water") != 1):
            errors.append("checkpoint: label scheme unexpected")
        ck_iou = ck.get("validation_metrics", {})
        if isinstance(ck_iou, dict) and "iou" in ck_iou and math.isfinite(data["best_iou"]):
            if abs(float(ck_iou["iou"]) - data["best_iou"]) > HARD_TOL:
                errors.append(
                    f"checkpoint: stored validation IoU {ck_iou['iou']} differs from history-selected {data['best_iou']:.8f}")
        else:
            warnings.append(
                "checkpoint: stored validation IoU not available for cross-check")

    config = folder / "run_config.json"
    if not config.is_file():
        warnings.append(
            "run_config.json missing: some full-run parameters cannot be confirmed")
    else:
        data["config_path"] = str(config)
        data["config_sha256"] = sha256(config)
        try:
            cfg = json.loads(config.read_text(encoding="utf-8"))
            if not isinstance(cfg, dict):
                raise ValueError("Expected object/dict")
            for name, expected in (("seed", seed), ("epochs", 25), ("batch_size", 2),
                                   ("crop_size", 256), ("base_channels", 16),
                                   ("lr", 0.0003), ("patience", 6)):
                check_param("config", name, cfg.get(
                    name), expected, warnings, errors)
            for name in ("max_train", "max_val"):
                if name in cfg and cfg[name] not in (0, None):
                    errors.append(
                        f"config: {name}={cfg[name]!r} (subset run; NOT full training)")
            if method == "v2a":
                marker = json.dumps(cfg, ensure_ascii=False).lower()
                if not any(term in marker for term in ("eventbalanced", "event_balanced", "event-balanced", "event balance")):
                    warnings.append(
                        "V2-A event-balanced sampler not explicitly identifiable in run_config; inspect trainer source")
        except Exception as exc:
            errors.append(f"Cannot parse run_config.json: {exc}")

    data["status"] = "ERROR" if errors else (
        "PASS_WITH_WARNINGS" if warnings else "PASS")
    return data


def group_mean(values: list[float]) -> float:
    return statistics.mean(values) if values else math.nan


def sample_sd(values: list[float]) -> float:
    return statistics.stdev(values) if len(values) >= 2 else math.nan


def aggregate(audits: list[dict], seeds: tuple[int, ...]) -> tuple[list[dict], list[dict], list[dict]]:
    lookup = {(a["method"], a["seed"], a["fold"]): a for a in audits}
    pairs: list[dict] = []
    for seed in seeds:
        for fold_name, event, _, _ in FOLDS:
            base = lookup[("baseline", seed, fold_name)]
            v2a = lookup[("v2a", seed, fold_name)]
            valid = base["status"] != "ERROR" and v2a["status"] != "ERROR"
            b = base["best_iou"] if valid else math.nan
            v = v2a["best_iou"] if valid else math.nan
            pairs.append({
                "fold": fold_name, "event": event, "seed": seed,
                "baseline_iou": b, "v2a_iou": v, "paired_delta": v - b if valid else math.nan,
                "baseline_epoch": base["best_epoch"], "v2a_epoch": v2a["best_epoch"],
                "baseline_epochs_run": base["epochs_run"], "v2a_epochs_run": v2a["epochs_run"],
                "baseline_status": base["status"], "v2a_status": v2a["status"],
                "paired_complete": valid,
            })
    by_seed, by_event = [], []
    for seed in seeds:
        subset = [p for p in pairs if p["seed"]
                  == seed and p["paired_complete"]]
        full = len(subset) == len(FOLDS)
        by_seed.append({"seed": seed, "n_events": len(subset), "complete": full,
                        "baseline_macro_iou": group_mean([p["baseline_iou"] for p in subset]) if full else math.nan,
                        "v2a_macro_iou": group_mean([p["v2a_iou"] for p in subset]) if full else math.nan,
                        "paired_macro_delta": group_mean([p["paired_delta"] for p in subset]) if full else math.nan})
    for _, event, _, _ in FOLDS:
        subset = [p for p in pairs if p["event"]
                  == event and p["paired_complete"]]
        by_event.append({"event": event, "n_seeds": len(subset),
                         "baseline_mean_iou": group_mean([p["baseline_iou"] for p in subset]),
                         "v2a_mean_iou": group_mean([p["v2a_iou"] for p in subset]),
                         "mean_paired_delta": group_mean([p["paired_delta"] for p in subset]),
                         "paired_delta_sample_sd": sample_sd([p["paired_delta"] for p in subset])})
    return pairs, by_seed, by_event


def create_plot(pairs: list[dict], output: Path) -> str:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return "Plot skipped: matplotlib unavailable"
    complete = [p for p in pairs if p["paired_complete"]]
    if not complete:
        return "Plot skipped: no complete pairs"
    fig, ax = plt.subplots(figsize=(10, 5.5))
    names = [f"{p['event']} / seed {p['seed']}" for p in complete]
    y = list(range(len(complete)))
    ax.axvline(0, linestyle="--", linewidth=1, color="0.4")
    for yi, p in zip(y, complete):
        delta = p["paired_delta"]
        ax.hlines(yi, 0, delta, lw=2)
        ax.scatter(delta, yi, s=40)
    ax.set_yticks(y, names)
    ax.invert_yaxis()
    ax.set_xlabel("V2-A minus Baseline: paired DEV validation water IoU")
    ax.set_title("M7.5B: Per-fold and per-seed paired DEV differences")
    ax.grid(axis="x", alpha=0.2)
    fig.tight_layout()
    fig.savefig(output, dpi=160)
    plt.close(fig)
    return str(output)


def report_markdown(audits: list[dict], pairs: list[dict], by_seed: list[dict], by_event: list[dict],
                    results_root: Path, plot_result: str) -> str:
    issues = [a for a in audits if a["errors"]]
    incomplete = [p for p in pairs if not p["paired_complete"]]
    complete_seeds = [s for s in by_seed if s["complete"]]
    full = not issues and not incomplete and len(complete_seeds) == 3
    status = "COMPLETE_WITH_WARNINGS" if full and any(a["warnings"] for a in audits) else (
        "COMPLETE" if full else "INCOMPLETE_DO_NOT_INTERPRET")
    lines = ["# M7.5B — Paired DEV Validation Audit", "", f"- Status: **{status}**",
             f"- Results root: `{results_root}`", "- Methods: Baseline small U-Net vs V2-A event-balanced sampling",
             "- Scope: **DEVELOPMENT VALIDATION ONLY** (USA, Sri Lanka, Spain), no TEST or Bolivia/Thailand opened",
             "- Unit of comparison: matched fold × random seed (9 paired runs); all metrics are water IoU",
             "- Selection reconstructed from history: retain first epoch with IoU improvement > 1e-5; max 25 epochs",
             "- Prespecified binary decision threshold: 0.5; not tuned here", "",
             "## Fold × seed pairing", "", "| Event | Seed | Baseline IoU | V2-A IoU | Delta | Epochs B/V2A | Complete |", "|---|---:|---:|---:|---:|---|---|"]
    for p in pairs:
        lines.append(f"| {p['event']} | {p['seed']} | {fmt(p['baseline_iou'])} | {fmt(p['v2a_iou'])} | {fmt(p['paired_delta'])} | {p['baseline_epoch']}/{p['v2a_epoch']} | {p['paired_complete']} |")
    lines += ["", "## Macro (equal weighting for three development events)", "",
              "| Seed | Baseline macro IoU | V2-A macro IoU | Paired delta | Complete |",
              "|---:|---:|---:|---:|---|"]
    for s in by_seed:
        lines.append(
            f"| {s['seed']} | {fmt(s['baseline_macro_iou'])} | {fmt(s['v2a_macro_iou'])} | {fmt(s['paired_macro_delta'])} | {s['complete']} |")
    if full:
        b = [s["baseline_macro_iou"] for s in complete_seeds]
        v = [s["v2a_macro_iou"] for s in complete_seeds]
        d = [s["paired_macro_delta"] for s in complete_seeds]
        lines += ["", f"**Across-seed mean macro IoU:** Baseline **{group_mean(b):.6f}**, V2-A **{group_mean(v):.6f}**, paired delta **{group_mean(d):+.6f}**.",
                  f"**Sample SD across seed-level macros:** Baseline {sample_sd(b):.6f}, V2-A {sample_sd(v):.6f}, paired delta {sample_sd(d):.6f}."]
    lines += ["", "## Event-level means over matched seeds", "",
              "| Event | Baseline | V2-A | Mean paired delta | N seeds |", "|---|---:|---:|---:|---:|"]
    for e in by_event:
        lines.append(
            f"| {e['event']} | {fmt(e['baseline_mean_iou'])} | {fmt(e['v2a_mean_iou'])} | {fmt(e['mean_paired_delta'])} | {e['n_seeds']} |")
    lines += ["", "## Checkpoint and configuration integrity", "",
              "| Method | Event | Seed | Status | Errors | Warnings |", "|---|---|---:|---|---:|---:|"]
    for a in audits:
        lines.append(
            f"| {a['method']} | {a['event']} | {a['seed']} | {a['status']} | {len(a['errors'])} | {len(a['warnings'])} |")
    for a in audits:
        if a["errors"] or a["warnings"]:
            lines += ["",
                      f"### {a['method']} / {a['event']} / seed {a['seed']}"]
            lines += [f"- ERROR: {x}" for x in a["errors"]]
            lines += [f"- CHECK MANUALLY: {x}" for x in a["warnings"]]
    lines += ["", "## Scientific interpretation and limits", "",
              "1. These are **DEV** comparisons only; not independent TEST performance, not an unbiased generalization estimate and not a causal mechanism test.",
              "2. Seeds share the same underlying validation event; 9 runs are **not nine independent geographic events**. Avoid formal significance claims from treating them as independent.",
              "3. Event-balanced sampling is the intended change. If checkpoint/config metadata or source review does not establish all other controls, mark the comparison as only *partially audited*.",
              "4. Checkpoint metadata inspection uses safe `torch.load(weights_only=True)` only. A missing field yields a warning; a mismatch yields an error. Warnings require manual source review.",
              "5. No historical India/Paraguay/Ghana TEST, Bolivia, Thai pilot, or held-out labels were accessed. Preserve those boundaries for future independent evaluation.",
              "6. Do not choose a new threshold, hyperparameter, or model based on historical TEST results. Record this audit as DEV-only evidence.",
              "", f"- Figure: {plot_result}", ""]
    return "\n".join(lines)


def main_audit(args: argparse.Namespace) -> int:
    seeds = tuple(args.seeds)
    if len(seeds) != 3 or len(set(seeds)) != 3:
        raise SystemExit(
            "M7.5B requires three distinct seeds (frozen default 42 123 777)")
    results_root = args.results_root.resolve()
    out = args.output_dir.resolve()
    # Input is fixed to dev folders. Resist accidental output-on-source overwrite.
    if out == results_root or out in [results_root / x for x in ("baseline_seed42", "v2a_eventbalanced_seed42")]:
        raise SystemExit(
            "Output directory must be separate from training input directories")
    out.mkdir(parents=True, exist_ok=True)
    audits = []
    for method, template in (("baseline", args.baseline_template), ("v2a", args.v2a_template)):
        for seed in seeds:
            for fold in FOLDS:
                record = inspect_run(results_root, template.format(
                    seed=seed), seed, fold, method, args.checkpoint_metadata)
                audits.append(record)
                status = record["status"]
                print(
                    f"{status:19s} {method:8s} {fold[1]:10s} seed={seed} best_epoch={record['best_epoch']} IoU={fmt(record['best_iou'])}", flush=True)
    pairs, by_seed, by_event = aggregate(audits, seeds)
    write_csv(out / "m75b_paired_fold_seed.csv", pairs,
              ["fold", "event", "seed", "baseline_iou", "v2a_iou", "paired_delta", "baseline_epoch", "v2a_epoch",
               "baseline_epochs_run", "v2a_epochs_run", "baseline_status", "v2a_status", "paired_complete"])
    write_csv(out / "m75b_seed_macro.csv", by_seed,
              ["seed", "n_events", "complete", "baseline_macro_iou", "v2a_macro_iou", "paired_macro_delta"])
    write_csv(out / "m75b_event_summary.csv", by_event,
              ["event", "n_seeds", "baseline_mean_iou", "v2a_mean_iou", "mean_paired_delta", "paired_delta_sample_sd"])
    plot_result = create_plot(pairs, out / "m75b_pair_deltas.png")
    json_output = {"created_utc": datetime.now(timezone.utc).isoformat(), "scope": "DEV VALID ONLY",
                   "selection_eps": SELECTION_EPS, "seeds": seeds, "folds": [f[0] for f in FOLDS], "audits": audits,
                   "pairs": pairs, "seed_macro": by_seed, "event_summary": by_event}
    (out / "m75b_audit.json").write_text(json.dumps(json_output,
                                                    ensure_ascii=False, indent=2, allow_nan=True), encoding="utf-8")
    (out / "m75b_report.md").write_text(report_markdown(audits, pairs,
                                                        by_seed, by_event, results_root, plot_result), encoding="utf-8")
    all_complete = all(p["paired_complete"] for p in pairs)
    print("\n=== M7.5B PAIRED DEV RESULTS ===")
    if all_complete:
        b = [s["baseline_macro_iou"] for s in by_seed]
        v = [s["v2a_macro_iou"] for s in by_seed]
        d = [s["paired_macro_delta"] for s in by_seed]
        print(
            f"Baseline DEV macro IoU: {group_mean(b):.6f} ± {sample_sd(b):.6f} seed SD")
        print(
            f"V2-A DEV macro IoU:    {group_mean(v):.6f} ± {sample_sd(v):.6f} seed SD")
        print(f"Paired macro delta:    {group_mean(d):+.6f} (V2-A - baseline)")
    else:
        print("INCOMPLETE: one or more matched runs could not be inspected.")
    failures = sum(bool(a["errors"]) for a in audits)
    warnings = sum(len(a["warnings"]) for a in audits)
    print(
        f"Audit runs: {len(audits)} | error runs: {failures} | manual-review warnings: {warnings}")
    print(f"Saved: {out}")
    print("No TEST, Bolivia, or Thailand data accessed. No training performed.")
    return 2 if failures or not all_complete else 0


def self_test() -> int:
    # Synthetic validation histories only. No actual project data accessed.
    b = {"USA": [0.52888, 0.53673, 0.54936], "Sri Lanka": [
        0.70651, 0.70107, 0.38909], "Spain": [0.69395, 0.71763, 0.70574]}
    v = {"USA": [0.54423, 0.52468, 0.54525], "Sri Lanka": [
        0.68012, 0.57917, 0.38657], "Spain": [0.69104, 0.71699, 0.71318]}
    with tempfile.TemporaryDirectory(prefix="m75b_selftest_") as tmp:
        root = Path(tmp) / "results"
        out = Path(tmp) / "audit"
        for method, template, scores in (("baseline", "baseline_seed{seed}", b), ("v2a", "v2a_eventbalanced_seed{seed}", v)):
            for i, seed in enumerate(DEFAULT_SEEDS):
                for fold, event, _, _ in FOLDS:
                    p = root / template.format(seed=seed) / fold
                    p.mkdir(parents=True)
                    write_csv(p / "history.csv", [{"epoch": 1, "val_iou": scores[event][i]-0.015},
                                                  {"epoch": 2, "val_iou": scores[event][i]}], ["epoch", "val_iou"])
                    (p / "best_sar_unet.pt").write_bytes(b"synthetic fixture; never load")
                    cfg = {"seed": seed, "epochs": 25, "batch_size": 2, "crop_size": 256,
                           "base_channels": 16, "lr": 0.0003, "patience": 6, "max_train": 0,
                           "max_val": 0, "method": "event_balanced" if method == "v2a" else "baseline"}
                    (p / "run_config.json").write_text(json.dumps(cfg))
        args = argparse.Namespace(results_root=root, output_dir=out, seeds=list(DEFAULT_SEEDS),
                                  baseline_template="baseline_seed{seed}", v2a_template="v2a_eventbalanced_seed{seed}", checkpoint_metadata="skip")
        assert main_audit(args) == 0
        rows, _ = read_csv(out / "m75b_seed_macro.csv")
        d = group_mean([float(r["paired_macro_delta"]) for r in rows])
        assert abs(d - (-0.01641444444444445)) < 5e-6, d
        # Negative test: missing one history must fail (do not silently ignore).
        (root / "v2a_eventbalanced_seed42" /
         "dev_fold_01_usa" / "history.csv").unlink()
        assert main_audit(args) == 2
    print("PASS: M7.5B synthetic self-test; correctly detects missing history and preserves paired arithmetic")
    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--results-root", type=Path,
                   default=Path("results/event_level_v2"))
    p.add_argument("--baseline-template",
                   default="baseline_seed{seed}", help="folder template beneath results root")
    p.add_argument(
        "--v2a-template", default="v2a_eventbalanced_seed{seed}", help="folder template beneath results root")
    p.add_argument("--output-dir", type=Path,
                   default=Path("results/event_level_v2/m75b_validation_comparison_audit"))
    p.add_argument("--seeds", nargs="+", type=int, default=list(DEFAULT_SEEDS))
    p.add_argument("--checkpoint-metadata", choices=["auto", "require", "skip"], default="auto",
                   help="auto: inspect safely if PyTorch installed; require: demand inspection; skip: files/hash only")
    p.add_argument("--self-test", action="store_true",
                   help="uses only temporary synthetic fixtures")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        sys.exit(self_test() if args.self_test else main_audit(args))
    except (OSError, ValueError) as exc:
        print(f"M7.5B ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
