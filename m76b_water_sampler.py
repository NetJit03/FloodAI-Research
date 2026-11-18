#!/usr/bin/env python3
"""M7.6B: TRAIN-only water-coverage sampling for frozen V2-B design.

Use with separately generated train_v2b_coverage.py. NO TEST, Bolivia, Thailand,
DEV VALID predictions or metrics are used to assign training sampling weights.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import torch
from torch.utils.data import WeightedRandomSampler

BINS = (
    'zero_water', 'water_0_to_1pct', 'water_1_to_10pct',
    'water_10_to_50pct', 'water_ge_50pct',
)
EXPECTED = {
    'dev_fold_01_usa': (174, 69, 'USA'),
    'dev_fold_02_sri_lanka': (201, 42, 'Sri-Lanka'),
    'dev_fold_03_spain': (213, 30, 'Spain'),
}
AUDIT = 'results/event_level_v2/m75d_v2b_design_audit/m75d_train_per_chip.csv'
FROZEN = 'results/event_level_v2/m76a_dg_design_freeze/m76a_v2b_design_frozen.json'


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def water_bin(fraction: float) -> str:
    if not math.isfinite(fraction) or not (0 <= fraction <= 1):
        raise ValueError(f'Invalid water fraction: {fraction}')
    if fraction == 0:
        return BINS[0]
    if fraction < .01:
        return BINS[1]
    if fraction < .1:
        return BINS[2]
    if fraction < .5:
        return BINS[3]
    return BINS[4]


def probability_for_bin(n: int, count_in_bin: int) -> float:
    if n < 5 or count_in_bin <= 0:
        raise ValueError('Full V2-B sampler requires all five nonempty bins')
    return 0.5 / n + 0.5 / (5.0 * count_in_bin)


def check_frozen(project_root: Path) -> dict:
    path = project_root / FROZEN
    if not path.is_file():
        raise FileNotFoundError(f'M7.6A FROZEN DESIGN missing: {path}; run M7.6A freeze/verify first')
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('status') != 'DESIGN_FROZEN_IMPLEMENTATION_PENDING':
        raise ValueError('M7.6A design does not have the expected frozen status')
    design = data.get('design', {})
    actual_fp = hashlib.sha256(json.dumps(design, sort_keys=True, ensure_ascii=False,
                                         separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    if data.get('design_fingerprint') != actual_fp:
        raise ValueError('M7.6A design fingerprint mismatch')
    t = design.get('treatment', {})
    if (tuple(t.get('strata', [])) != BINS or
        t.get('mixing_weight_uniform_images') != .5 or
        t.get('mixing_weight_uniform_strata') != .5 or
        t.get('sampling_draws_per_epoch') != 'N_train' or
        'replacement=True' not in t.get('v2b', '')):
        raise ValueError('Frozen M7.6A sampling design differs from this implementation')
    audit_path = project_root / AUDIT
    expected_sha = design.get('sources_sha256', {}).get(AUDIT)
    if not expected_sha or not audit_path.is_file() or sha256(audit_path) != expected_sha:
        raise ValueError('TRAIN-only M7.5D audit CSV differs from frozen M7.6A source; stop')
    if design.get('held_constant', {}).get('no_subset_limits') is not True:
        raise ValueError('Unexpected subset policy in design')
    return data


def train_plan(records, fold: str, root: Path) -> tuple[list[dict], dict]:
    frozen = check_frozen(root)
    if fold not in EXPECTED:
        raise ValueError(f'Unknown DEV fold: {fold}')
    n_train, n_val, val_event = EXPECTED[fold]
    spec = frozen['design']['folds'][fold]
    if (spec['train_count'], spec['valid_count'], spec['valid_event']) != (n_train, n_val, val_event):
        raise ValueError('Fold specification does not match frozen design')
    if len(records) != n_train:
        raise ValueError(f'Full TRAIN required for {fold}: expected {n_train}, got {len(records)}; no --max-train')
    names = [Path(x[0]).name for x in records]
    if len(set(names)) != len(names):
        raise ValueError('Duplicate TRAIN image names')
    events = [x[2] for x in records]
    if any(e == val_event for e in events):
        raise ValueError('TRAIN contains held-out VALID event: ' + val_event)
    with (root / AUDIT).open(newline='', encoding='utf-8') as f:
        audit = [r for r in csv.DictReader(f) if r['fold'] == fold]
    by_name = {r['image']: r for r in audit}
    if len(by_name) != n_train or set(by_name) != set(names):
        raise ValueError('TRAIN filenames differ from frozen M7.5D audit, or duplicate audit rows')
    counts = Counter(r['water_bin'] for r in audit)
    if {b: counts[b] for b in BINS} != spec['train_bin_counts'] or len(counts) != 5:
        raise ValueError('TRAIN bin counts differ from frozen M7.6A design')
    planned = []
    for idx, (name, event) in enumerate(zip(names, events)):
        record = by_name[name]
        if record['event'] != event:
            raise ValueError(f'TRAIN event mismatch in M7.5D audit: {name}')
        valid = int(record['valid_pixels']); water = int(record['gt_water_pixels'])
        frac = float(record['water_fraction']); water_class = record['water_bin']
        if not (0 <= water <= valid and valid > 0):
            raise ValueError(f'Invalid TRAIN water/valid pixel counts for {name}')
        if abs(water / valid - frac) > 1e-10 or water_bin(frac) != water_class:
            raise ValueError(f'TRAIN fraction/class mismatch for {name}')
        prob = probability_for_bin(n_train, counts[water_class])
        planned.append({
            'train_index': idx, 'image': name, 'event': event,
            'water_bin': water_class, 'water_fraction': frac,
            'valid_pixels': valid, 'water_pixels': water,
            'draw_probability': prob, 'expected_draws_per_epoch': n_train * prob,
        })
    total_prob = sum(r['draw_probability'] for r in planned)
    if not math.isclose(total_prob, 1.0, rel_tol=0, abs_tol=1e-12):
        raise ValueError(f'Sampler probabilities do not sum to 1: {total_prob}')
    for b in BINS:
        bin_mass = sum(r['draw_probability'] for r in planned if r['water_bin'] == b)
        expected_mass = .1 + .5 * counts[b] / n_train
        if not math.isclose(bin_mass, expected_mass, rel_tol=0, abs_tol=1e-12):
            raise ValueError(f'Wrong bin sampling mass for {b}')
    return planned, frozen


def save_csv(path: Path, rows: list[dict], fields: list[str]):
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader(); writer.writerows(rows)


def build_train_sampler(records, data_root: Path, output_dir: Path, seed: int,
                        project_root: Path | None = None, write_audit: bool = True):
    """Returns WeightedRandomSampler with seed-isolated torch Generator.

    TRAIN labels were scanned and hashed by M7.5D. This step only reads the
    frozen TRAIN audit and matches it to actual TRAIN manifest order.
    """
    root = Path(project_root or Path(__file__).resolve().parent).resolve()
    fold = Path(data_root).resolve().name
    planned, frozen = train_plan(records, fold, root)
    n = len(planned)
    weights = torch.tensor([r['draw_probability'] for r in planned], dtype=torch.double)
    gen = torch.Generator().manual_seed(int(seed))
    sampler = WeightedRandomSampler(weights=weights, num_samples=n,
                                    replacement=True, generator=gen)
    if write_audit:
        dest = Path(output_dir)
        dest.mkdir(parents=True, exist_ok=True)
        save_csv(dest / 'm76b_train_sampling_weights.csv', planned, list(planned[0]))
        groups = []
        for b in BINS:
            members = [r for r in planned if r['water_bin'] == b]
            groups.append({
                'bin': b, 'n_images': len(members),
                'natural_share': len(members) / n,
                'draw_probability_mass': sum(x['draw_probability'] for x in members),
                'expected_total_draws_per_epoch': sum(x['expected_draws_per_epoch'] for x in members),
                'expected_draws_per_image_per_epoch': members[0]['expected_draws_per_epoch'],
            })
        save_csv(dest / 'm76b_sampling_by_bin.csv', groups, list(groups[0]))
        # Probe uses a SEPARATE generator: it does not consume TRAIN RNG state.
        probe_gen = torch.Generator().manual_seed(int(seed))
        probe_rows = []
        for epoch in range(1, 4):
            indices = torch.multinomial(weights, n, replacement=True,
                                        generator=probe_gen).tolist()
            sample_counts = Counter(indices)
            for b in BINS:
                bin_ids = [i for i, r in enumerate(planned) if r['water_bin'] == b]
                probe_rows.append({'probe_epoch': epoch, 'bin': b,
                                   'draws': sum(sample_counts[i] for i in bin_ids),
                                   'unique_chips': sum(sample_counts[i] > 0 for i in bin_ids)})
        save_csv(dest / 'm76b_three_epoch_sampling_probe.csv', probe_rows, list(probe_rows[0]))
        trainer_file = root / 'train_v2b_coverage.py'
        manifest = {
            'status': 'M76B_TRAIN_ONLY_SAMPLER_AUDITED',
            'fold': fold, 'seed': int(seed), 'n_train': n,
            'num_samples_per_epoch': n, 'replacement': True,
            'sampler': '50% image-uniform + 50% five-bin-uniform',
            'design_fingerprint': frozen['design_fingerprint'],
            'frozen_design_sha256': sha256(root / FROZEN),
            'train_audit_sha256': sha256(root / AUDIT),
            'trainer_v2b_sha256': sha256(trainer_file) if trainer_file.is_file() else None,
            'no_test_data_or_metrics_used': True,
            'note': 'TRAIN full-chip label fractions (not cropped patch fractions); ' +
                    '3-epoch probe is illustrative, not an optimization criterion.',
        }
        (dest / 'm76b_sampler_manifest.json').write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        print(f'PASS M7.6B {fold}: n_train={n}, seed={seed}; 5 nonempty bins')
        for g in groups:
            print(f'  {g["bin"]:>19}: n={g["n_images"]:>3} '
                  f'P(bin)={g["draw_probability_mass"]:.4f} '
                  f'E[draws/chip]={g["expected_draws_per_image_per_epoch"]:.3f}')
        print('PASS: TRAIN-only frozen source/bin/weight audit; no VALID metrics or TEST used')
    return sampler


def self_test():
    assert [water_bin(x) for x in (0, 1e-5, .00999, .01, .0999, .1, .4999, .5, 1)] == [
        BINS[0], BINS[1], BINS[1], BINS[2], BINS[2], BINS[3], BINS[3], BINS[4], BINS[4]]
    counts = [1, 2, 3, 4, 5]; n = sum(counts)
    probs = [probability_for_bin(n, c) for c in counts for _ in range(c)]
    assert math.isclose(sum(probs), 1, rel_tol=0, abs_tol=1e-12)
    for c in counts:
        assert math.isclose(c * probability_for_bin(n, c), .1 + .5*c/n, abs_tol=1e-12)
    s1 = list(WeightedRandomSampler(torch.tensor(probs, dtype=torch.double), n, True,
                                    generator=torch.Generator().manual_seed(42)))
    s2 = list(WeightedRandomSampler(torch.tensor(probs, dtype=torch.double), n, True,
                                    generator=torch.Generator().manual_seed(42)))
    assert s1 == s2 and len(s1) == n
    assert max(s1) < n and min(s1) >= 0
    print('PASS M7.6B self-test: five bin boundaries, 50/50 masses, deterministic draws')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--self-test', action='store_true')
    p.add_argument('--audit-all', action='store_true')
    p.add_argument('--project-root', type=Path, default=Path('.'))
    p.add_argument('--seed', type=int, default=42)
    a = p.parse_args()
    if a.self_test:
        self_test(); return
    if not a.audit_all:
        p.error('Specify --self-test or --audit-all')
    root = a.project_root.resolve()
    # Import from exact ORIGINAL trainer to load TRAIN manifest only (not TEST).
    import sys
    sys.path.insert(0, str(root))
    from train_sar_unet import split_records
    for fold in EXPECTED:
        dr = root / 'data/sen1floods11/v2_development_roots' / fold
        records = split_records(dr, 'train')
        out = root / 'results/event_level_v2/m76b_implementation_audit' / fold
        build_train_sampler(records, dr, out, a.seed, project_root=root)
    print('PASS: all 3 V2-B folds audited without training')


if __name__ == '__main__':
    main()
