#!/usr/bin/env python3
"""M6.5D-3: read-only V2 data QA and proposed experiment snapshot.

Run after m65d_prepare_dev_roots.py --run-check-only passes.
Never trains, tunes or reads historical/final-test labels.
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

FOLDS = {
    "dev_fold_01_usa": (174, 69, "USA"),
    "dev_fold_02_sri_lanka": (201, 42, "Sri-Lanka"),
    "dev_fold_03_spain": (213, 30, "Spain"),
}
EVENTS = {"Mekong", "Nigeria", "Pakistan", "Somalia", "Spain", "Sri-Lanka", "USA"}
BANNED = {"India", "Paraguay", "Ghana", "Bolivia", "Colombia", "Thailand"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def rows_of(path: Path):
    if not path.is_file():
        raise ValueError(f"Missing CSV {path}")
    with path.open(newline="", encoding="utf-8-sig") as f:
        rows = [r for r in csv.reader(f) if r and any(v.strip() for v in r)]
    if rows and (len(rows[0]) < 2 or not all(c.strip().lower().endswith('.tif') for c in rows[0][:2])):
        rows = rows[1:]
    for r in rows:
        if len(r) < 2:
            raise ValueError(f"Bad CSV row {r!r} in {path}")
        yield Path(r[0].strip()).name, Path(r[1].strip()).name


def event_of(filename):
    return filename.split("_", 1)[0]


def same_grid(sar, lbl, tolerance=0.05):
    if sar.crs != lbl.crs or sar.width != lbl.width or sar.height != lbl.height:
        return False
    # Compare positions of selected SAR pixel centers in units of LABEL pixels.
    inv = ~lbl.transform
    for col, row in ((0.5, 0.5), (sar.width-0.5, sar.height-0.5),
                     (sar.width/2, sar.height/2), (sar.width-0.5, 0.5), (0.5, sar.height-0.5)):
        wx, wy = sar.transform * (col, row)
        c2, r2 = inv * (wx, wy)
        if float(np.hypot(c2-col, r2-row)) > tolerance:
            return False
    return True


def read_one(source, sar_name, lbl_name):
    a = source / "S1Hand" / sar_name
    b = source / "LabelHand" / lbl_name
    stem = sar_name.removesuffix("_S1Hand.tif")
    if not sar_name.endswith("_S1Hand.tif") or lbl_name != stem + "_LabelHand.tif":
        raise ValueError(f"Mismatched filenames: {sar_name} | {lbl_name}")
    if not a.is_file() or not b.is_file():
        raise ValueError(f"Missing TIFF pair {a}, {b}")
    with rasterio.open(a) as sar, rasterio.open(b) as lbl:
        if sar.count != 2 or lbl.count != 1 or not same_grid(sar, lbl):
            raise ValueError(f"Invalid bands or grid: {stem}")
        if sar.crs is None:
            raise ValueError(f"Missing CRS: {stem}")
        x = sar.read(out_dtype="float32")
        y = lbl.read(1)
        if not np.isin(y, [-1, 0, 1]).all():
            raise ValueError(f"Unknown label codes in {stem}: {np.unique(y)}")
        # Label 0 MUST remain land, even if TIFF metadata incorrectly specifies nodata=0.
        finite = np.isfinite(x).all(axis=0)
        if sar.nodata is not None and np.isfinite(sar.nodata):
            finite &= np.all(x != sar.nodata, axis=0)
        valid = finite & np.isin(y, [0, 1])
        if not valid.any():
            raise ValueError(f"No evaluable SAR/label pixels: {stem}")
        water = int((valid & (y == 1)).sum())
        land = int((valid & (y == 0)).sum())
        return {
            "image": sar_name, "event": event_of(sar_name), "height": sar.height,
            "width": sar.width, "valid_pixels": int(valid.sum()),
            "water_pixels": water, "land_pixels": land,
            "label_ignore_pixels": int((y == -1).sum()),
            "sar_nonfinite_pixels": int((~np.isfinite(x).all(axis=0)).sum()),
            "label_metadata_nodata": str(lbl.nodata),
            "crs": str(sar.crs),
        }


def argparse_defaults(trainer):
    tree = ast.parse(trainer.read_text(encoding="utf-8"))
    out = {}
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call) or not isinstance(n.func, ast.Attribute) or n.func.attr != "add_argument":
            continue
        flags = [a.value for a in n.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
        long_flags = [s for s in flags if s.startswith("--")]
        if not long_flags:
            continue
        kw = next((k.value for k in n.keywords if k.arg == "default"), None)
        if kw is None:
            continue
        try:
            value = ast.literal_eval(kw)
        except (ValueError, TypeError, SyntaxError):
            continue
        out[long_flags[0].removeprefix("--")] = value
    return out


def execute(source, roots, trainer, output):
    source, roots, trainer = source.resolve(), roots.resolve(), trainer.resolve()
    if not trainer.is_file():
        raise ValueError(f"Missing trainer: {trainer}")
    event_catalog = defaultdict(set)
    pairs = {}
    hashes = {}
    fold_summary = []
    for fold, (expected_train, expected_valid, expected_event) in FOLDS.items():
        root = roots / fold
        if (root / "S1Hand").resolve() != (source / "S1Hand").resolve() or (root / "LabelHand").resolve() != (source / "LabelHand").resolve():
            raise ValueError(f"Source TIFF links do not resolve to expected folders: {fold}")
        splits = root / "splits"
        tr_path, va_path = splits / "flood_train_data.csv", splits / "flood_valid_data.csv"
        tr, va = list(rows_of(tr_path)), list(rows_of(va_path))
        if len(tr) != expected_train or len(va) != expected_valid:
            raise ValueError(f"Unexpected counts in {fold}: train={len(tr)} valid={len(va)}")
        tnames = {a for a, _ in tr}
        vnames = {a for a, _ in va}
        if len(tnames) != len(tr) or len(vnames) != len(va) or tnames & vnames:
            raise ValueError(f"Duplicate chips in {fold}")
        tevents = {event_of(a) for a, _ in tr}
        vevents = {event_of(a) for a, _ in va}
        if vevents != {expected_event} or tevents & vevents or tevents | vevents != EVENTS:
            raise ValueError(f"Wrong event membership in {fold}: {tevents=} {vevents=}")
        if (tevents | vevents) & BANNED:
            raise ValueError(f"Historical test/holdout leakage in {fold}")
        for reserved in ("test", "bolivia"):
            if list(rows_of(splits / f"flood_{reserved}_data.csv")):
                raise ValueError(f"The {reserved} compatibility stub is NOT empty in {fold}")
        for sar_name, label_name in tr + va:
            if sar_name in pairs and pairs[sar_name] != label_name:
                raise ValueError(f"Inconsistent label mapping: {sar_name}")
            pairs[sar_name] = label_name
            event_catalog[event_of(sar_name)].add(sar_name)
        hashes[f"{fold}/train"] = sha256(tr_path)
        hashes[f"{fold}/valid"] = sha256(va_path)
        fold_summary.append({"fold": fold, "train": len(tr), "valid": len(va),
                             "train_events": sorted(tevents), "valid_events": sorted(vevents)})

    if len(pairs) != 243 or set(event_catalog) != EVENTS:
        raise ValueError(f"Incorrect development inventory ({len(pairs)} unique chips; events {set(event_catalog)})")
    audits = [read_one(source, sar_name, lbl_name) for sar_name, lbl_name in sorted(pairs.items())]
    counts = Counter(a["event"] for a in audits)
    nodata_metadata_zero = sum(a["label_metadata_nodata"] in ("0.0", "0") for a in audits)

    cli = argparse_defaults(trainer)
    required_defaults = {"epochs": 25, "batch-size": 2, "crop-size": 256,
                         "base-channels": 16, "lr": 3e-4, "patience": 6, "seed": 42}
    defaults_check = {k: {"expected": v, "found": cli.get(k), "matches": cli.get(k) == v}
                      for k, v in required_defaults.items()}
    # Existing source shows initial fixed normalization in earlier screenshots; source verification remains a gate.
    report = {
        "status": "AUDITED_PROPOSED_NOT_FROZEN",
        "note": "No model trained. This is NOT independent ground-truth validation.",
        "unique_development_chips": len(pairs), "development_events": dict(sorted(counts.items())),
        "folds": fold_summary, "total_valid_pixels": sum(a["valid_pixels"] for a in audits),
        "total_water_pixels": sum(a["water_pixels"] for a in audits),
        "label_metadata_nodata_zero_count": nodata_metadata_zero,
        "label_rule": {"ignore": -1, "land": 0, "water": 1,
                       "important": "Land 0 is valid even if label metadata mistakenly says nodata=0."},
        "proposed_normalization": {"VV": [-35.0, 5.0], "VH": [-40.0, 0.0],
                                   "status": "VERIFY_TIFF_UNITS_AND_TRAINER_SOURCE"},
        "proposed_training_defaults": defaults_check,
        "trainer_sha256": sha256(trainer), "split_sha256": hashes,
        "threshold_proposed": 0.5, "primary_selection_metric_proposed": "macro_mean_water_iou_across_three_dev_val_events",
        "future_seeds_proposed": [42, 123, 777],
        "historical_tests": "India/Paraguay/Ghana excluded from dev; not pristine for independent confirmation",
        "thai_pilot": "diagnostic only; no comparable water-IoU without aligned, validated GT",
    }
    output.mkdir(parents=True, exist_ok=True)
    csvpath = output / "m65d3_all_dev_chips_audit.csv"
    with csvpath.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(audits[0]))
        writer.writeheader()
        writer.writerows(audits)
    (output / "m65d3_proposed_config_snapshot.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("=== M6.5D-3 FULL DATA AUDIT ===")
    print("PASS: 3 event-disjoint fold manifests and reserved test stubs")
    print(f"PASS: {len(pairs)}/243 unique SAR/label pairs audited (bands, grids, finite masks, label codes)")
    print("Events:", ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    print("Valid pixels:", report["total_valid_pixels"], "| water pixels:", report["total_water_pixels"])
    if nodata_metadata_zero:
        print(f"NOTE: label nodata metadata = 0 in {nodata_metadata_zero} TIFF(s); land=0 remained valid")
    for k, d in defaults_check.items():
        print(f"TRAINER DEFAULT: --{k}: actual={d['found']!r} expected={d['expected']!r} match={d['matches']}")
    if not all(d["matches"] for d in defaults_check.values()):
        print("WARNING: Not all trainer defaults match screenshots; verify before freeze")
    print("Saved:", csvpath)
    print("Saved:", output / "m65d3_proposed_config_snapshot.json")
    print("STATUS: AUDITED, NOT YET FROZEN. Verify preprocessing, SAR units, model code and final evaluation policy.")


def self_test():
    with tempfile.TemporaryDirectory() as directory:
        p = Path(directory)
        (p / "S1Hand").mkdir()
        (p / "LabelHand").mkdir()
        a = p / "S1Hand" / "USA_1_S1Hand.tif"
        b = p / "LabelHand" / "USA_1_LabelHand.tif"
        xf = np.zeros((2, 8, 8), dtype=np.float32)
        xf[:, 0, 0] = np.nan
        yy = np.zeros((8, 8), dtype=np.int16)
        yy[1:4, 1:4] = 1
        yy[7, 7] = -1
        kwargs = dict(driver="GTiff", height=8, width=8, crs="EPSG:4326", transform=from_origin(5, 10, 0.01, 0.01))
        with rasterio.open(a, "w", count=2, dtype="float32", **kwargs) as f: f.write(xf)
        with rasterio.open(b, "w", count=1, dtype="int16", nodata=0, **kwargs) as f: f.write(yy, 1)
        d = read_one(p, a.name, b.name)
        assert d['valid_pixels'] == 62 and d['water_pixels'] == 9 and d['land_pixels'] == 53, d
        print("PASS: M6.5D-3 class masks, metadata NoData=0 handling, and raster-grid fixture")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-root", type=Path, default=Path("data/sen1floods11"))
    p.add_argument("--roots-dir", type=Path, default=Path("data/sen1floods11/v2_development_roots"))
    p.add_argument("--trainer", type=Path, default=Path("train_sar_unet.py"))
    p.add_argument("--output-dir", type=Path, default=Path("results/event_level_v1/m65d3_freeze_preflight"))
    p.add_argument("--self-test", action="store_true")
    args = p.parse_args()
    if args.self_test:
        self_test()
    else:
        execute(args.data_root, args.roots_dir, args.trainer, args.output_dir)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError, rasterio.errors.RasterioError) as exc:
        raise SystemExit(f"ERROR (no training performed): {exc}")
