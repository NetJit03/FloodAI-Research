#!/usr/bin/env python3
"""M6.5D-2: safely link V2 development folds to existing Sen1Floods11 TIFFs.

Creates three isolated training data roots with symlinks to source S1Hand/LabelHand,
and copies only approved train/valid manifests.  Empty test/bolivia CSVs are
compatibility stubs for the older train_sar_unet.py split inspector; they do NOT
contain test samples.  No training is performed unless you separately run it.
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

FOLDS = {
    "dev_fold_01_usa": {"train": 174, "valid": 69, "valid_event": "USA"},
    "dev_fold_02_sri_lanka": {"train": 201, "valid": 42, "valid_event": "Sri-Lanka"},
    "dev_fold_03_spain": {"train": 213, "valid": 30, "valid_event": "Spain"},
}
DEV_EVENTS = {"Mekong", "Nigeria", "Pakistan",
              "Somalia", "Spain", "Sri-Lanka", "USA"}
EXCLUDED_EVENTS = {"India", "Paraguay",
                   "Ghana", "Bolivia", "Thailand", "Colombia"}


def read_manifest(path: Path) -> list[tuple[str, str]]:
    if not path.is_file():
        raise RuntimeError(f"Missing manifest: {path}")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = [row for row in csv.reader(
            handle) if row and any(x.strip() for x in row)]
    # Infer whether a header is present from the first row's filenames.
    if rows and (len(rows[0]) < 2 or not all('.tif' in col.lower() for col in rows[0][:2])):
        rows = rows[1:]
    result = []
    for idx, row in enumerate(rows, 1):
        if len(row) < 2 or not all('.tif' in col.lower() for col in row[:2]):
            raise RuntimeError(f"Malformed row {idx} in {path}: {row!r}")
        result.append((row[0].strip(), row[1].strip()))
    return result


def event_of(filename: str) -> str:
    return Path(filename).name.split('_', 1)[0]


def assert_file_pair(source: Path, image: str, label: str) -> None:
    image_file = source / 'S1Hand' / Path(image).name
    label_file = source / 'LabelHand' / Path(label).name
    if not image_file.is_file() or not label_file.is_file():
        raise RuntimeError(
            f"Missing source TIFF pair: {image_file} | {label_file}")
    stem = image_file.name.removesuffix('_S1Hand.tif')
    label_stem = label_file.name.removesuffix('_LabelHand.tif')
    if stem != label_stem:
        raise RuntimeError(
            f"SAR / label filename mismatch: {image_file.name}, {label_file.name}")


def safe_symlink(dst: Path, target: Path) -> None:
    if dst.is_symlink():
        if dst.resolve() != target.resolve():
            raise RuntimeError(
                f"Unsafe existing symlink: {dst} points to {dst.resolve()}")
    elif dst.exists():
        raise RuntimeError(f"Destination exists and is not a symlink: {dst}")
    else:
        dst.symlink_to(target.resolve(), target_is_directory=True)


def safe_copy_text(dst: Path, contents: bytes) -> None:
    if dst.exists():
        if dst.read_bytes() != contents:
            raise RuntimeError(
                f"Existing file differs; refuse to overwrite: {dst}")
    else:
        dst.write_bytes(contents)


def prepare(source: Path, manifests: Path, output: Path) -> list[dict]:
    source = source.resolve()
    manifests = manifests.resolve()
    output = output.resolve()
    for folder in ('S1Hand', 'LabelHand'):
        if not (source / folder).is_dir():
            raise RuntimeError(
                f"Source TIFF directory missing: {source / folder}")
    # Check all folds BEFORE touching destination paths.
    checks: list[dict] = []
    for name, spec in FOLDS.items():
        folder = manifests / name
        tr = folder / 'flood_train_data.csv'
        va = folder / 'flood_valid_data.csv'
        train_rows = read_manifest(tr)
        valid_rows = read_manifest(va)
        if len(train_rows) != spec['train'] or len(valid_rows) != spec['valid']:
            raise RuntimeError(
                f"{name}: count mismatch (train={len(train_rows)}, valid={len(valid_rows)})")
        train_names = [Path(r[0]).name for r in train_rows]
        valid_names = [Path(r[0]).name for r in valid_rows]
        if len(train_names) != len(set(train_names)) or len(valid_names) != len(set(valid_names)):
            raise RuntimeError(f"{name}: duplicate chips within split")
        if set(train_names) & set(valid_names):
            raise RuntimeError(
                f"{name}: duplicate SAR chips across train and valid")
        train_events = {event_of(f) for f in train_names}
        valid_events = {event_of(f) for f in valid_names}
        if train_events & valid_events:
            raise RuntimeError(
                f"{name}: event overlap {train_events & valid_events}")
        if train_events | valid_events != DEV_EVENTS:
            raise RuntimeError(
                f"{name}: unexpected development events {train_events | valid_events}")
        if valid_events != {spec['valid_event']}:
            raise RuntimeError(
                f"{name}: unexpected validation event(s) {valid_events}")
        if (train_events | valid_events) & EXCLUDED_EVENTS:
            raise RuntimeError(
                f"{name}: blocked V1 test/holdout event detected")
        for image, label in train_rows + valid_rows:
            assert_file_pair(source, image, label)
        checks.append({
            'fold': name, 'train': len(train_rows), 'valid': len(valid_rows),
            'train_events': sorted(train_events), 'valid_events': sorted(valid_events),
            'source_train_csv': str(tr), 'source_valid_csv': str(va),
        })
    # Materialize only linked directories and CSV manifests, never TIFF copies.
    output.mkdir(parents=True, exist_ok=True)
    for record in checks:
        name = record['fold']
        root = output / name
        root.mkdir(parents=True, exist_ok=True)
        safe_symlink(root / 'S1Hand', source / 'S1Hand')
        safe_symlink(root / 'LabelHand', source / 'LabelHand')
        split_dir = root / 'splits'
        split_dir.mkdir(parents=True, exist_ok=True)
        for split in ('train', 'valid'):
            src = manifests / name / f'flood_{split}_data.csv'
            safe_copy_text(split_dir / src.name, src.read_bytes())
        # These are 0-byte *compatibility stubs*, NOT evaluation data.
        # Old inspect_splits(root) unconditionally asks for test/bolivia CSVs.
        for split in ('test', 'bolivia'):
            safe_copy_text(split_dir / f'flood_{split}_data.csv', b'')
        record['data_root'] = str(root)
    report = {
        'status': 'DEV_ROOTS_PREPARED_NOT_TRAINED',
        'source_data_root': str(source),
        'manifest_root': str(manifests),
        'output_root': str(output),
        'warning': 'test/bolivia CSVs are EMPTY compatibility stubs. Do NOT evaluate on these folders.',
        'folds': checks,
    }
    safe_copy_text(output / 'm65d_dev_roots_report.json',
                   (json.dumps(report, indent=2) + '\n').encode())
    return checks


def self_test() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        source = base / 'source'
        (source / 'S1Hand').mkdir(parents=True)
        (source / 'LabelHand').mkdir()
        manifest_dir = base / 'manifests'
        catalog = {"Mekong": 30, "Nigeria": 18, "Pakistan": 28, "Somalia": 26,
                   "Spain": 30, "Sri-Lanka": 42, "USA": 69}
        chips = {}
        for event, count in catalog.items():
            chips[event] = []
            for i in range(count):
                stem = f'{event}_{i:06d}'
                sar = stem + '_S1Hand.tif'
                lbl = stem + '_LabelHand.tif'
                (source / 'S1Hand' / sar).touch()
                (source / 'LabelHand' / lbl).touch()
                chips[event].append((sar, lbl))
        for name, spec in FOLDS.items():
            target = manifest_dir / name
            target.mkdir(parents=True)
            valid = chips[spec['valid_event']]
            train = [r for e, pairs in chips.items() if e != spec['valid_event']
                     for r in pairs]
            for split, records in [('train', train), ('valid', valid)]:
                with (target / f'flood_{split}_data.csv').open('w', newline='') as f:
                    csv.writer(f).writerows(records)
        checks = prepare(source, manifest_dir, base / 'output')
        assert len(checks) == 3
        for item in checks:
            root = Path(item['data_root'])
            assert (root / 'S1Hand').is_symlink()
            assert (root / 'LabelHand').is_symlink()
            assert (root / 'splits' / 'flood_test_data.csv').read_bytes() == b''
        print('PASS: M6.5D-2 linked roots self-test (243-chip synthetic fixture)')


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-root', type=Path, default=Path('data/sen1floods11'))
    p.add_argument('--manifests-dir', type=Path, default=Path(
        'results/event_level_v1/m65d_protocol_preflight/proposed_dev_manifests'))
    p.add_argument('--output-dir', type=Path,
                   default=Path('data/sen1floods11/v2_development_roots'))
    p.add_argument('--trainer', type=Path, default=Path('train_sar_unet.py'))
    p.add_argument('--run-check-only', action='store_true',
                   help='Calls existing train_sar_unet.py with --check-only for every fold; does not train')
    p.add_argument('--self-test', action='store_true')
    args = p.parse_args()
    if args.self_test:
        self_test()
        return 0
    try:
        checks = prepare(args.data_root, args.manifests_dir, args.output_dir)
        print('=== M6.5D-2: V2 DEVELOPMENT ROOTS ===')
        for record in checks:
            print(f"PASS {record['fold']}: train={record['train']} valid={record['valid']} "
                  f"validation={','.join(record['valid_events'])}")
            print('  --data-root', record['data_root'])
        print('PASS: source TIFFs and source manifests remain untouched')
        print('NOTE: test and bolivia CSVs in each root are EMPTY compatibility stubs')
        print('NOTE: V1 test events India/Paraguay/Ghana are NOT in training or validation')
        if args.run_check_only:
            if not args.trainer.is_file():
                raise RuntimeError(f"Missing trainer script: {args.trainer}")
            for record in checks:
                cmd = [sys.executable, str(
                    args.trainer), '--data-root', record['data_root'], '--check-only']
                print('CHECK-ONLY:', ' '.join(cmd), flush=True)
                completed = subprocess.run(cmd, check=False)
                if completed.returncode != 0:
                    raise RuntimeError(
                        f"Check-only failed for {record['fold']} (exit {completed.returncode}). No training was attempted.")
            print('PASS: --check-only completed successfully for all three folds')
        else:
            print('NEXT: rerun with --run-check-only to validate the existing trainer')
        return 0
    except (RuntimeError, OSError, ValueError) as exc:
        print('ERROR:', exc, file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
