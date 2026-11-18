#!/usr/bin/env python3
"""M7.6A: freeze V2-B TRAIN-only sampling *design*, not an executable trainer.

Uses the prior M7.5D DEV/TRAIN audit and existing M7.0D frozen baseline.
Never reads historical TEST, Bolivia or Thailand; no training/inference.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

FOLDS = {
    'dev_fold_01_usa': (174, 69, 'USA'),
    'dev_fold_02_sri_lanka': (201, 42, 'Sri-Lanka'),
    'dev_fold_03_spain': (213, 30, 'Spain'),
}
BINS = ('zero_water', 'water_0_to_1pct', 'water_1_to_10pct',
        'water_10_to_50pct', 'water_ge_50pct')
SEEDS = (42, 123, 777)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def fingerprint(obj: dict) -> str:
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False,
                     separators=(',', ':'), allow_nan=False).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def load_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f'Missing M7.5D artifact: {path}')
    with path.open(newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def design(root: Path) -> dict:
    audit = root / 'results/event_level_v2/m75d_v2b_design_audit'
    baseline = root / 'results/event_level_v2/m70d_protocol_freeze/m70d_frozen_protocol.json'
    required = {
        'train': audit / 'm75d_train_per_chip.csv',
        'coverage': audit / 'm75d_coverage_by_fold.csv',
        'sensitivity': audit / 'm75d_sampling_sensitivity.csv',
    }
    if not baseline.is_file():
        raise FileNotFoundError(f'Frozen M7.0D baseline not found: {baseline}')
    prior = json.loads(baseline.read_text(encoding='utf-8'))
    if not isinstance(prior.get('fingerprint'), str) or len(prior['fingerprint']) != 64:
        raise ValueError('M7.0D baseline missing valid fingerprint')
    data = load_rows(required['train'])
    expected_memberships = sum(x[0] for x in FOLDS.values())
    if len(data) != expected_memberships:
        raise ValueError(f'M7.5D training memberships: expected {expected_memberships}, got {len(data)}')
    sums = {f: {b: 0 for b in BINS} for f in FOLDS}
    names = {f: set() for f in FOLDS}
    for r in data:
        fold = r['fold']; b = r['water_bin']; name = r['image']
        if fold not in FOLDS or b not in BINS:
            raise ValueError(f'Unexpected M7.5D fold/bin: {fold}/{b}')
        if name in names[fold]:
            raise ValueError(f'Duplicate TRAIN image in {fold}: {name}')
        names[fold].add(name)
        fraction = float(r['water_fraction'])
        if not 0 <= fraction <= 1:
            raise ValueError(f'Invalid water fraction for {name}')
        expected = ('zero_water' if fraction == 0 else
                    'water_0_to_1pct' if fraction < .01 else
                    'water_1_to_10pct' if fraction < .10 else
                    'water_10_to_50pct' if fraction < .50 else 'water_ge_50pct')
        if b != expected:
            raise ValueError(f'Fraction/bin mismatch for {name}: {fraction}, {b}')
        sums[fold][b] += 1
    if any(len(names[f]) != FOLDS[f][0] for f in FOLDS):
        raise ValueError('Unexpected fold TRAIN image counts')
    if any(not n for d in sums.values() for n in d.values()):
        raise ValueError('At least one training bin is empty; cannot run 5-bin sampler')
    coverage = load_rows(required['coverage'])
    if len(coverage) != 15:
        raise ValueError('Expected 3 folds x 5 coverage bins')
    for r in coverage:
        if int(r['n_images']) != sums[r['fold']][r['water_bin']]:
            raise ValueError('M7.5D coverage summary does not match train-by-chip CSV')
    sensitivity = load_rows(required['sensitivity'])
    if len(sensitivity) != 15:
        raise ValueError('Expected 15 sampler sensitivity rows')
    for r in sensitivity:
        fold, b = r['fold'], r['water_bin']
        n = FOLDS[fold][0]; nb = sums[fold][b]
        expected_exposures = .5 + n * .5 / (5 * nb)
        if abs(float(r['candidate_expected_draws_per_chip_per_epoch']) - expected_exposures) > 1e-7:
            raise ValueError(f'Candidate exposure mismatch: {fold}/{b}')
    return {
        'protocol': 'M7.6A_V2B_TRAIN_ONLY_WATER_COVERAGE_SAMPLER',
        'scope': 'EXPLORATORY DEVELOPMENT; design-only freeze; V2-B trainer not yet implemented',
        'baseline_m70d_fingerprint': prior['fingerprint'],
        'sources_sha256': {str(p.relative_to(root)): sha256_file(p)
                           for p in (baseline, *required.values())},
        'dataset': 'Sen1Floods11 hand-labeled VV/VH, 243 unique DEV chips, 7 DEV events',
        'folds': {f: {'train_count': x[0], 'valid_count': x[1], 'valid_event': x[2],
                      'train_bin_counts': sums[f]} for f, x in FOLDS.items()},
        'model': 'SmallUNet, 2 SAR bands (VV then VH), base_channels=16',
        'treatment': {
            'only_intended_change': 'TRAIN image-index sampling policy',
            'baseline': 'shuffle without replacement once per epoch',
            'v2b': 'WeightedRandomSampler(replacement=True, num_samples=N_train)',
            'draw_probability_for_image_i': '0.5 / N_train + 0.5 / (5 * N_bin(image_i))',
            'strata': list(BINS),
            'water_fraction_source': 'M7.5D TRAIN-only full-chip GT valid water / valid pixels',
            'mixing_weight_uniform_images': 0.5,
            'mixing_weight_uniform_strata': 0.5,
            'sampling_draws_per_epoch': 'N_train',
            'sampler_seed_policy': 'Torch generator controlled by each training seed',
            'augmentation': 'UNCHANGED baseline crop/flips/rotations; NO new radiometric jitter',
            'caution': 'With replacement can repeat rare images; full-chip bin != crop water fraction',
        },
        'held_constant': {
            'input': 'VV/VH in documented dB; no new data channels',
            'normalization_db': {'VV': [-35.0, 5.0], 'VH': [-40.0, 0.0]},
            'label': {'ignore': -1, 'land': 0, 'water': 1},
            'valid_mask': 'finite two-channel SAR AND label != -1; never mask land=0 as nodata',
            'architecture': 'SmallUNet base16',
            'loss': '0.5 masked BCE + 0.5 masked Dice',
            'optimizer': 'AdamW lr=0.0003 weight_decay=0.0001',
            'train_crop': 256, 'validation_full_chip': 512, 'batch_size': 2,
            'max_epochs': 25, 'early_stopping_patience': 6, 'threshold': 0.5,
            'checkpoint_selection': 'best VALIDATION event-level pixel-micro water IoU',
            'zero_union_iou': 'NaN',
            'seeds': list(SEEDS),
            'no_subset_limits': True,
        },
        'primary_metric': 'macro mean of 3 held-out DEV event-level pixel-micro water IoUs per seed',
        'secondary_metrics': ['IoU per DEV event', 'Water Recall', 'Water Precision',
                              'F1/Dice', 'paired difference by fold/seed', 'seed stability'],
        'hypothesis': 'TRAIN-only water-coverage sampling may improve cross-event water IoU/stability',
        'comparison_policy': 'Baseline/V2-A/V2-B same 3 DEV folds x 3 seeds; no TEST-based tuning',
        'test_policy': 'India/Paraguay/Ghana historical tests, Bolivia and Thailand excluded entirely',
        'interpretation': 'M7.5D and earlier DEV outcomes informed this candidate; not an untouched confirmatory test',
        'future_gate': 'Before full V2-B runs: implement sampler separately, unit-test and smoke-test, record trainer hash',
    }


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def self_test() -> None:
    for n in (10, 35, 200):
        bins = [1, 2, 3, 2, 2] if n == 10 else [n - 4, 1, 1, 1, 1]
        total = sum(count * (.5 / n + .5 / (5 * count)) for count in bins)
        assert abs(total - 1.0) < 1e-12
    assert fingerprint({'b': 2, 'a': 1}) == fingerprint({'a': 1, 'b': 2})
    print('PASS: M7.6A design formula and fingerprint self-test')


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=('prepare', 'freeze', 'verify'))
    p.add_argument('--project-root', type=Path, default=Path('.'))
    p.add_argument('--confirm-audit-reviewed', action='store_true')
    p.add_argument('--confirm-train-only-sampler', action='store_true')
    p.add_argument('--confirm-single-change', action='store_true')
    p.add_argument('--confirm-test-isolation', action='store_true')
    p.add_argument('--self-test', action='store_true')
    a = p.parse_args()
    if a.self_test:
        self_test(); return
    root = a.project_root.resolve()
    out = root / 'results/event_level_v2/m76a_dg_design_freeze'
    frozen_path = out / 'm76a_v2b_design_frozen.json'
    snapshot = design(root)
    design_hash = fingerprint(snapshot)
    if a.mode == 'prepare':
        if frozen_path.exists():
            print('NOTICE: already frozen; use verify (do not modify a frozen design)')
        else:
            write_json(out / 'm76a_design_proposed.json', snapshot)
        print('M7.6A proposed design fingerprint:', design_hash)
        print('TRAIN bin counts:', {f: d['train_bin_counts'] for f,d in snapshot['folds'].items()})
        print('STATUS: PREPARED, NOT FROZEN; read design before manual sign-off')
    elif a.mode == 'freeze':
        if frozen_path.exists():
            raise SystemExit('REFUSED: a frozen design already exists. Run verify; do not overwrite.')
        if not all((a.confirm_audit_reviewed, a.confirm_train_only_sampler,
                    a.confirm_single_change, a.confirm_test_isolation)):
            raise SystemExit('REFUSED: manual sign-offs missing; use all four --confirm-* flags after review')
        frozen = {'status': 'DESIGN_FROZEN_IMPLEMENTATION_PENDING',
                  'frozen_at_utc': datetime.now(timezone.utc).isoformat(),
                  'design_fingerprint': design_hash, 'design': snapshot}
        write_json(frozen_path, frozen)
        print('FROZEN DESIGN:', frozen_path)
        print('FINGERPRINT:', design_hash)
        print('NEXT: M7.6B separately implement and audit V2-B trainer before full training')
    else:
        if not frozen_path.is_file():
            raise FileNotFoundError('No frozen design file; run prepare then freeze')
        stored = json.loads(frozen_path.read_text(encoding='utf-8'))
        if stored.get('status') != 'DESIGN_FROZEN_IMPLEMENTATION_PENDING':
            raise ValueError('Unrecognized frozen design status')
        if stored['design_fingerprint'] != design_hash or stored['design'] != snapshot:
            raise ValueError('M7.6A design/frozen source fingerprint mismatch')
        print('PASS: M7.6A frozen design verified against M7.5D and M7.0D artifacts')
        print('FINGERPRINT:', design_hash)


if __name__ == '__main__':
    main()
