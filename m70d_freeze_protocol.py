#!/usr/bin/env python3
"""M7.0D: audit, freeze, and verify a Sen1Floods11 V2 development protocol.

No training or evaluation runs. Does not modify the input images, original CSVs,
trainer, evaluator, or previously saved checkpoints. Requires manual sign-off for
provenance, coding conventions, and data-use policy before freezing.
"""

from __future__ import annotations

import argparse
import ast
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

EXPECTED_EVENTS = {
    "Mekong": 30, "Nigeria": 18, "Pakistan": 28, "Somalia": 26,
    "Spain": 30, "Sri-Lanka": 42, "USA": 69,
}
FOLDS = {
    "dev_fold_01_usa": {"train": 174, "valid": 69, "valid_event": "USA"},
    "dev_fold_02_sri_lanka": {"train": 201, "valid": 42, "valid_event": "Sri-Lanka"},
    "dev_fold_03_spain": {"train": 213, "valid": 30, "valid_event": "Spain"},
}
RESERVED_EVENTS = {"India", "Paraguay", "Ghana", "Bolivia"}
EXPECTED_DEFAULTS = {
    "--epochs": 25,
    "--batch-size": 2,
    "--crop-size": 256,
    "--base-channels": 16,
    "--lr": 0.0003,
    "--patience": 6,
    "--seed": 42,
    "--max-train": 0,
    "--max-val": 0,
}


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path.resolve())


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(4 * 1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def need(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def read_csv(path: Path) -> list[tuple[str, str]]:
    need(path.is_file(), f"Missing split CSV: {path}")
    output: list[tuple[str, str]] = []
    with path.open(newline="", encoding="utf-8-sig") as fh:
        for row in csv.reader(fh):
            if not row or not any(x.strip() for x in row):
                continue
            need(len(row) >= 2, f"Malformed row in {path}: {row!r}")
            img, label = row[0].strip(), row[1].strip()
            need(img.endswith("_S1Hand.tif"), f"Unexpected SAR filename: {img}")
            need(label == img.removesuffix("_S1Hand.tif") + "_LabelHand.tif",
                 f"Unmatched SAR/label pair: {img} vs {label}")
            need(Path(img).name == img and Path(label).name == label,
                 f"Expected plain filenames, not directory paths: {row}")
            output.append((img, label))
    return output


def ast_defaults(tree: ast.AST) -> dict[str, object]:
    found = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "add_argument" or not node.args:
            continue
        if not isinstance(node.args[0], ast.Constant) or not isinstance(node.args[0].value, str):
            continue
        arg = node.args[0].value
        for kw in node.keywords:
            if kw.arg == "default":
                try:
                    found[arg] = ast.literal_eval(kw.value)
                except (ValueError, TypeError, SyntaxError):
                    found[arg] = "<not literal>"
    return found


def subscript_name(node: ast.AST, var: str, key: str) -> bool:
    return (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
            and node.value.id == var and isinstance(node.slice, ast.Constant)
            and node.slice.value == key)


def validate_code(trainer: Path, evaluator: Path) -> dict:
    need(trainer.is_file(), f"Trainer missing: {trainer}")
    need(evaluator.is_file(), f"Evaluator missing: {evaluator}")
    t_tree = ast.parse(trainer.read_text(encoding="utf-8"), filename=str(trainer))
    e_tree = ast.parse(evaluator.read_text(encoding="utf-8"), filename=str(evaluator))
    defaults = ast_defaults(t_tree)
    for option, value in EXPECTED_DEFAULTS.items():
        need(option in defaults, f"Trainer missing explicit default for {option}")
        need(defaults[option] == value,
             f"Trainer {option}: found {defaults[option]!r}, expected {value!r}")

    # Check structure of the user's requested empty-union IoU policy.
    union_found = False
    iou_expression = None
    for node in ast.walk(t_tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "union":
                    expr = ast.unparse(node.value).replace(" ", "")
                    if expr == "tp+fp+fn":
                        union_found = True
                if subscript_name(target, "totals", "iou"):
                    iou_expression = ast.unparse(node.value)
    need(union_found, "Cannot verify trainer assignment: union = tp + fp + fn")
    need(iou_expression is not None, "Cannot find trainer totals['iou'] assignment")
    compact = re.sub(r"\s+", "", iou_expression).replace('"', "'")
    need(compact == "tp/unionifunionelsefloat('nan')",
         f"Trainer IoU is not the expected NaN-on-empty-union formula: {iou_expression}")

    eval_metrics = [n for n in ast.walk(e_tree) if isinstance(n, ast.FunctionDef) and n.name == "metrics"]
    safe_div = [n for n in ast.walk(e_tree) if isinstance(n, ast.FunctionDef) and n.name == "safe_div"]
    need(eval_metrics and safe_div, "Cannot find evaluator metrics()/safe_div() source")
    metrics_src = ast.unparse(eval_metrics[0]).replace(" ", "")
    safe_src = ast.unparse(safe_div[0]).replace(" ", "").replace('"', "'")
    need("safe_div(tp,tp+fp+fn)" in metrics_src,
         "Evaluator water IoU must use safe_div(tp, tp+fp+fn)")
    need("float('nan')" in safe_src,
         "Evaluator safe_div must return NaN when denominator is zero")

    trainer_src = trainer.read_text(encoding="utf-8")
    need("valid = (y != -1) & valid_image" in trainer_src or
         re.search(r"valid\s*=\s*\(y\s*!=\s*-1\)\s*&\s*valid_image", trainer_src),
         "Could not confirm label 0 is retained and only -1 is ignored")
    need("DB_MIN" in trainer_src and "DB_MAX" in trainer_src,
         "Trainer normalization constants not found")

    return {
        "trainer_defaults": {key: defaults[key] for key in EXPECTED_DEFAULTS},
        "trainer_iou_expression": iou_expression,
        "evaluator_iou_policy": "safe_div(tp,tp+fp+fn); zero denominator yields NaN",
        "label_policy": "label=-1 ignored; label=0 land; label=1 water; finite SAR required",
        "code_checks": "PASS: syntactic checks only; manual review still required",
    }


def build_protocol(root: Path, code_check: dict) -> dict:
    return {
        "protocol_id": "M7.0D_Sen1Floods11_V2_Development_Baseline",
        "scope": "development protocol freeze; NOT training or independent testing",
        "task": "binary surface-water segmentation from two-channel Sentinel-1 SAR",
        "source_dataset": "Sen1Floods11 hand-labeled SAR/label pairs, local data root",
        "inputs": ["VV", "VH"],
        "target_labels": {"ignore": -1, "land": 0, "water": 1},
        "valid_pixel_policy": "label!=-1 AND both SAR bands finite; do not discard land=0 based on label nodata metadata",
        "normalization_presets_db": {"VV": [-35.0, 5.0], "VH": [-40.0, 0.0]},
        "normalization_note": "Fixed presets; confirm TIFF provenance and units manually; do not fit ranges on TEST",
        "development_inventory": {"unique_pairs": 243, "events": EXPECTED_EVENTS},
        "folds": {name: {"train": cfg["train"], "valid": cfg["valid"],
                         "validation_event": cfg["valid_event"]} for name, cfg in FOLDS.items()},
        "reserved": {
            "historical_explored_tests": ["India", "Paraguay", "Ghana"],
            "historical_holdout": "Bolivia: NOT pristine independent confirmation",
            "thailand": "Diagnostic pilot only until aligned, independently validated GT exists",
            "test_and_bolivia_csvs": "empty compatibility stubs in all V2 dev roots",
        },
        "training": {
            "architecture": "SmallUNet, 2 input bands, base channels 16",
            "epochs_max": 25,
            "batch_size": 2,
            "train_crop_size": 256,
            "optimizer": "AdamW, weight decay 1e-4",
            "lr": 0.0003,
            "patience": 6,
            "seeds_for_future_runs": [42, 123, 777],
            "train_augmentations": "random crop, horizontal/vertical flip and 90-degree rotations",
            "eval_augmentation": "none; full-size 512x512 image",
            "loss": "masked 0.5*BCEWithLogits + 0.5*soft Dice loss",
            "development_fold_checkpoint_selection": "best VALID micro water IoU; patience on VALID IoU",
            "candidate_model_selection": "mean of event-level VALID water IoU across 3 development folds; decide before examining new TEST",
            "maximum_samples": "full fold train/valid; do not use --max-train or --max-val for full runs",
        },
        "evaluation": {
            "fixed_threshold": 0.5,
            "micro_water_iou": "sum(TP)/(sum(TP)+sum(FP)+sum(FN)); if denominator 0, NaN",
            "per_image_iou": "IoU NaN if GT-water and predicted-water union is empty; report count of NaN images",
            "metrics": ["water IoU", "F1/Dice", "precision", "recall", "Brier", "ECE", "NLL"],
            "reporting": "event-level scores; pixel values are spatially correlated; no image-as-event claims",
            "test_policy": "no TEST threshold fitting, calibration, hyperparameter selection or method selection",
        },
        "code_check": code_check,
        "method_comparison_policy": "V1 and V2 must be retrained on identical V2 development folds/seeds before comparison",
    }


def collect(root: Path, roots_dir: Path, trainer: Path, evaluator: Path) -> dict:
    code_checks = validate_code(trainer, evaluator)
    source_paths = {"trainer": trainer.resolve(), "evaluator": evaluator.resolve()}
    fingerprint_files: dict[str, Path] = dict(source_paths)
    all_unique: dict[str, tuple[Path, Path]] = {}
    fold_report = {}
    for fold, spec in FOLDS.items():
        folder = roots_dir / fold
        need(folder.is_dir(), f"Missing development fold root: {folder}")
        records_by_split = {}
        for split in ("train", "valid", "test", "bolivia"):
            csv_path = folder / "splits" / f"flood_{split}_data.csv"
            records = read_csv(csv_path)
            fingerprint_files[f"split/{fold}/{split}"] = csv_path
            records_by_split[split] = records
            expected = spec[split] if split in ("train", "valid") else 0
            need(len(records) == expected,
                 f"{fold} {split}: found {len(records)}, expected {expected}")
            for img, label in records:
                sar_path = folder / "S1Hand" / img
                lbl_path = folder / "LabelHand" / label
                need(sar_path.is_file(), f"Missing SAR: {sar_path}")
                need(lbl_path.is_file(), f"Missing label: {lbl_path}")
                if img in all_unique:
                    old_sar, old_lbl = all_unique[img]
                    need(old_sar.resolve() == sar_path.resolve() and old_lbl.resolve() == lbl_path.resolve(),
                         f"Same filename refers to distinct files across folds: {img}")
                else:
                    all_unique[img] = (sar_path, lbl_path)
        train_names = {x[0] for x in records_by_split["train"]}
        valid_names = {x[0] for x in records_by_split["valid"]}
        need(len(train_names) == len(records_by_split["train"]), f"Duplicate train chips in {fold}")
        need(len(valid_names) == len(records_by_split["valid"]), f"Duplicate valid chips in {fold}")
        need(not (train_names & valid_names), f"Image leakage across train/valid in {fold}")
        train_event = Counter(n.split("_", 1)[0] for n in train_names)
        valid_event = Counter(n.split("_", 1)[0] for n in valid_names)
        need(set(valid_event) == {spec["valid_event"]},
             f"Wrong validation event in {fold}: {dict(valid_event)}")
        expected_train = set(EXPECTED_EVENTS) - {spec["valid_event"]}
        need(set(train_event) == expected_train,
             f"Missing/unexpected train events in {fold}: {dict(train_event)}")
        for ev, count in train_event.items():
            need(count == EXPECTED_EVENTS[ev], f"Count mismatch {fold} {ev}: {count}")
        need(valid_event[spec["valid_event"]] == EXPECTED_EVENTS[spec["valid_event"]],
             f"Validation count mismatch {fold}")
        need(not (set(train_event) | set(valid_event)) & RESERVED_EVENTS,
             f"Historical test/holdout leaked into {fold}")
        fold_report[fold] = {"train": len(train_names), "valid": len(valid_names),
                             "valid_event": spec["valid_event"], "train_events": dict(sorted(train_event.items()))}

    need(len(all_unique) == 243, f"Development inventory found {len(all_unique)} unique chips (need 243)")
    counts = Counter(img.split("_", 1)[0] for img in all_unique)
    need(dict(counts) == EXPECTED_EVENTS, f"Development event inventory mismatch: {dict(counts)}")

    old_snapshot = root / "results/event_level_v1/m65d3_freeze_preflight/m65d3_proposed_config_snapshot.json"
    old_hash = None
    if old_snapshot.is_file():
        try:
            old_hash = json.loads(old_snapshot.read_text(encoding="utf-8")).get("trainer_sha256")
        except (ValueError, OSError):
            pass

    # Hash each unique SAR/label file one time, not 3x for repeated development folds.
    for img, (sar, label) in all_unique.items():
        fingerprint_files[f"data/S1Hand/{img}"] = sar
        fingerprint_files[f"data/LabelHand/{label.name}"] = label
    hashes = {}
    for identifier, path in sorted(fingerprint_files.items()):
        hashes[identifier] = {"path": rel(path, root), "sha256": sha(path), "size_bytes": path.stat().st_size}

    fingerprint = hashlib.sha256(json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"fingerprint": fingerprint,
            "source_root": rel(root, root),
            "roots_dir": rel(roots_dir, root),
            "code": code_checks,
            "folds": fold_report,
            "unique_pairs": len(all_unique),
            "hashes": hashes,
            "old_audited_trainer_sha256": old_hash,
            "trainer_changed_since_m65d3": (old_hash is not None and old_hash != hashes["trainer"]["sha256"]),
            "protocol": build_protocol(root, code_checks)}


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def report_md(data: dict, *, frozen: bool) -> str:
    p = data["protocol"]
    source = data.get("audited_at") or data.get("frozen_at")
    return f"""# M7.0D — {'FROZEN' if frozen else 'AUDITED, NOT FROZEN'} baseline protocol

- Status: **{'FROZEN (manual sign-offs + fingerprint match)' if frozen else 'AUDIT PASSED; MANUAL REVIEW REQUIRED'}**
- Recorded at (UTC): {source}
- SHA-256 fingerprint: `{data['fingerprint']}`
- Trainer SHA-256: `{data['hashes']['trainer']['sha256']}`
- Evaluator SHA-256: `{data['hashes']['evaluator']['sha256']}`
- Trainer hash changed since M6.5D-3: **{data['trainer_changed_since_m65d3']}** (expected if IoU code was edited; inspect the change)

## Frozen development folds

| Fold | Train | Valid | Validation event |
|---|---:|---:|---|
""" + "\n".join(
        f"| {k} | {v['train']} | {v['valid']} | {v['valid_event']} |" for k, v in data["folds"].items()
    ) + f"""

## Method and policy

- Source: Sen1Floods11 hand-labeled pairs; **243 unique chips / 7 events**
- Input: VV/VH; output: surface-water probability and fixed-threshold mask
- Label semantics: `-1` ignore; `0` land; `1` water; finite SAR required; label nodata metadata MUST NOT erase land=0
- Fixed VV range: {p['normalization_presets_db']['VV']} dB; VH range: {p['normalization_presets_db']['VH']} dB
- Training: max 25 epochs, batch 2, crop 256, SmallUNet base 16, AdamW learning rate 0.0003, patience 6
- Future seeds: 42, 123, 777 (each fold trained separately); **no --max-train/--max-val** for full runs
- Checkpoint selected ONLY using VALID micro water IoU; 0.5 threshold fixed
- Empty-union IoU: NaN, not 1.0; report count of undefined per-image IoU
- Primary method comparison: macro average of three validation-event IoUs
- Historical India / Paraguay / Ghana test events excluded from V2 development; Bolivia already inspected, not pristine
- Thailand: diagnostic pilot; not a comparable test without aligned independent surface-water GT
- No TEST-based fitting, threshold tuning, recalibration or architecture selection
- V1 versus V2: train both on identical V2 folds and seeds
- Cryptographic hashes record exact inputs. They do not, by themselves, validate label quality or measurement units.

## Manual sign-offs

1. Confirm original official data provenance, local TIFF conversion history, VV/VH order, and dB numeric units.
2. Compare trainer and evaluator, especially fixed normalization, valid pixel policy, and zero-union IoU NaN behavior.
3. Confirm TRAIN-only augmentation, validation-only early stopping, full fold runs, selection rule, seeds, threshold and output policy.
4. Confirm no India/Paraguay/Ghana, Bolivia or Thai data were used for V2 development/tuning.
5. After any source/CSV/TIFF edits, **a new protocol version, re-audit and re-freeze are necessary**.

## Limitation

A frozen protocol is not a final model or independent test. This script does **not** train or evaluate any model.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["audit", "freeze", "verify"])
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--roots-dir", type=Path, default=Path("data/sen1floods11/v2_development_roots"))
    parser.add_argument("--trainer", type=Path, default=Path("train_sar_unet.py"))
    parser.add_argument("--evaluator", type=Path, default=Path("evaluate_sar_unet.py"))
    parser.add_argument("--output-dir", type=Path, default=Path("results/event_level_v2/m70d_protocol_freeze"))
    parser.add_argument("--confirm-tiff-provenance", action="store_true")
    parser.add_argument("--confirm-code-policy", action="store_true")
    parser.add_argument("--confirm-evaluation-policy", action="store_true")
    parser.add_argument("--confirm-test-isolation", action="store_true")
    args = parser.parse_args()
    root = args.project_root.resolve()
    resolve = lambda path: path.resolve() if path.is_absolute() else root / path
    output = resolve(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    audit_file = output / "m70d_audit.json"
    frozen_file = output / "m70d_frozen_protocol.json"

    print(f"M7.0D {args.mode.upper()} | streaming SHA-256 over 243 unique SAR+label pairs ...", flush=True)
    current = collect(root, resolve(args.roots_dir), resolve(args.trainer), resolve(args.evaluator))
    if args.mode == "audit":
        current["audited_at"] = datetime.now(timezone.utc).isoformat()
        write_json(audit_file, current)
        (output / "m70d_audit_report.md").write_text(report_md(current, frozen=False), encoding="utf-8")
        print("PASS: 3 event-disjoint development folds and 243 unique pairs")
        print("PASS: trainer/evaluator IoU zero-union semantics matched expected patterns")
        if current["trainer_changed_since_m65d3"]:
            print("NOTICE: trainer SHA differs from the older M6.5D-3 snapshot (expected after your IoU edit)")
        print("SAVED:", audit_file)
        print("STATUS: AUDITED, NOT FROZEN. Review the report and source before freeze.")
    elif args.mode == "freeze":
        need(audit_file.is_file(), "Run 'audit' first, and manually review the report")
        need(not frozen_file.exists(), f"Already frozen: {frozen_file}; use verify or create a versioned directory")
        audit = json.loads(audit_file.read_text(encoding="utf-8"))
        need(audit["fingerprint"] == current["fingerprint"],
             "Input hashes changed since audit. Re-run audit and review changes before freezing")
        approvals = {
            "tiff_provenance_reviewed": args.confirm_tiff_provenance,
            "trainer_and_preprocessing_code_reviewed": args.confirm_code_policy,
            "evaluation_and_empty_union_policy_reviewed": args.confirm_evaluation_policy,
            "historical_tests_excluded_and_no_test_tuning": args.confirm_test_isolation,
        }
        need(all(approvals.values()),
             "Manual sign-off flags required: --confirm-tiff-provenance --confirm-code-policy "
             "--confirm-evaluation-policy --confirm-test-isolation")
        current["frozen_at"] = datetime.now(timezone.utc).isoformat()
        current["manual_signoff"] = approvals
        write_json(frozen_file, current)
        (output / "m70d_frozen_protocol.md").write_text(report_md(current, frozen=True), encoding="utf-8")
        print("FROZEN:", frozen_file)
        print("FINGERPRINT:", current["fingerprint"])
        print("NEXT: verify, then full 3-fold baseline training with no --max-* limits")
    else:
        need(frozen_file.is_file(), f"Not yet frozen: {frozen_file}")
        frozen = json.loads(frozen_file.read_text(encoding="utf-8"))
        need(current["fingerprint"] == frozen["fingerprint"],
             "DRIFT DETECTED: code, splits, or TIFF bytes differ from frozen protocol")
        need(current["protocol"] == frozen["protocol"], "Protocol policy drift detected")
        print("PASS: frozen protocol matches all current code, splits and TIFF checksums")
        print("FINGERPRINT:", current["fingerprint"])


if __name__ == "__main__":
    try:
        main()
    except (ValueError, FileNotFoundError, OSError, SyntaxError) as exc:
        print("FAIL:", exc, file=sys.stderr)
        sys.exit(1)
