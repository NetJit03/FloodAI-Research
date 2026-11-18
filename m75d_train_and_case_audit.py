#!/usr/bin/env python3
"""M7.5D - DEVELOPMENT-ONLY train water-coverage and Sri Lanka case audit.

This is read-only. It NEVER opens TEST/Bolivia/Thailand split files, trains,
selects a checkpoint, searches thresholds, or changes a frozen protocol.

Dependencies for a full run: numpy, rasterio, matplotlib (optional plotting).
The M7.5C per-image CSV is a previously-generated DEV validation diagnostic.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

FOLDS = {
    'dev_fold_01_usa': (174, 69, 'USA'),
    'dev_fold_02_sri_lanka': (201, 42, 'Sri-Lanka'),
    'dev_fold_03_spain': (213, 30, 'Spain'),
}
CASES = ('Sri-Lanka_534068_S1Hand.tif',
         'Sri-Lanka_845821_S1Hand.tif',
         'Sri-Lanka_713926_S1Hand.tif')
SEEDS = (42, 123, 777)
EXCLUDED_EVENTS = {'India', 'Paraguay', 'Ghana', 'Bolivia', 'Thailand'}


def bucket(frac: float) -> str:
    if frac == 0:
        return 'zero_water'
    if frac < 0.01:
        return 'water_0_to_1pct'
    if frac < 0.10:
        return 'water_1_to_10pct'
    if frac < 0.50:
        return 'water_10_to_50pct'
    return 'water_ge_50pct'


def read_rows(path: Path) -> list[dict]:
    if not path.is_file():
        raise FileNotFoundError(f'Missing required M7.5C file: {path}')
    with path.open(newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def write_rows(path: Path, rows: list[dict], fields: list[str]):
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)


def manifest(root: Path, split: str):
    """Read only TRAIN or VALID CSV. No general split probing."""
    if split not in {'train', 'valid'}:
        raise ValueError('Only TRAIN and DEV VALID can be read')
    csvfile = root / 'splits' / f'flood_{split}_data.csv'
    if not csvfile.is_file():
        raise FileNotFoundError(csvfile)
    items = []
    with csvfile.open(newline='', encoding='utf-8-sig') as f:
        for i, row in enumerate(csv.reader(f), 1):
            if not row:
                continue
            if len(row) < 2:
                raise ValueError(f'{csvfile}:{i}: needs two columns')
            img, lab = Path(row[0].strip()).name, Path(row[1].strip()).name
            if not (img.endswith('_S1Hand.tif') and lab.endswith('_LabelHand.tif')):
                raise ValueError(
                    f'{csvfile}:{i}: unexpected TIFF names: {img}, {lab}')
            if img.removesuffix('_S1Hand.tif') != lab.removesuffix('_LabelHand.tif'):
                raise ValueError(
                    f'{csvfile}:{i}: image-label names do not match')
            event = img.split('_')[0]
            if event in EXCLUDED_EVENTS:
                raise RuntimeError(
                    f'STOP: historical TEST/holdout event found in {split}: {img}')
            p_img, p_lab = root/'S1Hand'/img, root/'LabelHand'/lab
            if not (p_img.is_file() and p_lab.is_file()):
                raise FileNotFoundError(
                    f'Missing TRAIN/DEV TIFF: {p_img} | {p_lab}')
            items.append((img, lab, event, p_img, p_lab))
    return items


def get_gt_stats(img_path, lab_path, *, with_sar_stats=False):
    import numpy as np
    import rasterio
    with rasterio.open(img_path) as sar, rasterio.open(lab_path) as labels:
        if sar.count != 2 or labels.count != 1:
            raise ValueError(f'Unexpected band count: {img_path}')
        if sar.width != labels.width or sar.height != labels.height:
            raise ValueError(f'Shape mismatch: {img_path}')
        if sar.crs != labels.crs or any(abs(a-b) > 1e-6 for a, b in zip(sar.transform, labels.transform)):
            raise ValueError(f'Grid mismatch: {img_path}')
        raw = sar.read(out_dtype='float32')
        gt = labels.read(1)
        if not np.isin(gt, (-1, 0, 1)).all():
            raise ValueError(f'Unexpected GT labels: {lab_path}')
        valid_sar = np.isfinite(raw).all(axis=0)
        if sar.nodata is not None and np.isfinite(sar.nodata):
            valid_sar &= (raw != sar.nodata).all(axis=0)
        # IMPORTANT: do NOT use label metadata nodata=0; land=0 is valid.
        valid = valid_sar & (gt != -1)
        n_valid = int(valid.sum())
        if not n_valid:
            raise ValueError(f'Zero valid pixels: {img_path}')
        nw = int((valid & (gt == 1)).sum())
        nl = int((valid & (gt == 0)).sum())
        record = dict(valid_pixels=n_valid, gt_water_pixels=nw, gt_land_pixels=nl,
                      water_fraction=nw/n_valid, water_bin=bucket(nw/n_valid))
        if with_sar_stats:
            for k, channel in enumerate(('vv', 'vh')):
                w = raw[k][valid & (gt == 1)]
                l = raw[k][valid & (gt == 0)]
                record[f'{channel}_water_median'] = float(
                    np.median(w)) if w.size else float('nan')
                record[f'{channel}_land_median'] = float(
                    np.median(l)) if l.size else float('nan')
                record[f'{channel}_water_minus_land'] = (
                    record[f'{channel}_water_median'] - record[f'{channel}_land_median'])
        return record


def plot_input_triptych(img, label, output):
    import numpy as np
    import rasterio
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib.colors import ListedColormap, BoundaryNorm
    except ImportError:
        print('WARNING: matplotlib missing; skipping optional case plots')
        return
    with rasterio.open(img) as src, rasterio.open(label) as src_lab:
        x = src.read(out_dtype='float32')
        y = src_lab.read(1)
        valid = np.isfinite(x).all(axis=0) & (y != -1)
        if src.nodata is not None and np.isfinite(src.nodata):
            valid &= (x != src.nodata).all(axis=0)
    fig, axs = plt.subplots(1, 3, figsize=(12, 4.1), constrained_layout=True)
    for k, (lo, hi, title) in enumerate(((-35, 5, 'VV, fixed dB window'), (-40, 0, 'VH, fixed dB window'))):
        arr = np.clip(x[k], lo, hi)
        axs[k].imshow(np.ma.masked_where(~valid, arr),
                      cmap='gray', vmin=lo, vmax=hi)
        axs[k].set_title(title)
    # Codes 0=land; 1=water; 2=invalid. No metadata nodata=0 filtering.
    show = np.where(~valid, 2, y)
    cmap = ListedColormap(['#d3d9df', '#1e88c9', '#ffffff'])
    axs[2].imshow(show, cmap=cmap, norm=BoundaryNorm(
        [-.5, .5, 1.5, 2.5], cmap.N))
    axs[2].set_title('Ground truth: gray=land, blue=water')
    for a in axs:
        a.set_axis_off()
    fig.suptitle(
        f'DEV ONLY: {Path(img).stem} | no inference or threshold search', fontsize=12)
    fig.savefig(output, dpi=150, bbox_inches='tight')
    plt.close(fig)


def plot_case_metrics(rows, case, out):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        return
    r = [x for x in rows if x['image'] == case]
    fig, ax = plt.subplots(figsize=(8, 4.6))
    x = np.arange(3)
    w = .37
    for k, method in enumerate(('baseline', 'v2a')):
        vals = [float(next(a['recall'] for a in r if a['method']
                      == method and int(a['seed']) == s)) for s in SEEDS]
        ax.bar(x+(k-.5)*w, vals, width=w, label=method)
    ax.set_xticks(x, list(map(str, SEEDS)))
    ax.set_xlabel('Seed')
    ax.set_ylabel('Water recall')
    ax.set_ylim(0, 1.05)
    ax.legend()
    ax.grid(axis='y', alpha=.2)
    ax.set_title(f'{case} — DEV-only existing-checkpoint recall')
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def evidence_check(rows, pairs):
    if len(rows) != 252 or len(pairs) != 126:
        raise RuntimeError(
            f'M7.5C counts unexpected: per_image={len(rows)} paired={len(pairs)}')
    by_key = {(r['method'], int(r['seed']), r['image']): r for r in rows}
    if len(by_key) != 252:
        raise RuntimeError('Duplicate per-image key found')
    names = {r['image'] for r in rows}
    if len(names) != 42 or not set(CASES).issubset(names):
        raise RuntimeError('Incorrect DEV-validation image inventory in M7.5C')
    if {r['method'] for r in rows} != {'baseline', 'v2a'} or {int(r['seed']) for r in rows} != set(SEEDS):
        raise RuntimeError(
            'M7.5C methods/seeds differ from frozen analysis scope')
    return by_key


def self_test():
    assert bucket(0) == 'zero_water'
    assert bucket(.009) == 'water_0_to_1pct'
    assert bucket(.01) == 'water_1_to_10pct'
    assert bucket(.10) == 'water_10_to_50pct'
    assert bucket(.5) == 'water_ge_50pct'
    assert abs(.5/2 + .5/4 - .375) < 1e-9
    print('PASS M7.5D self-test: bins and probabilities; no project data accessed')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--self-test', action='store_true')
    p.add_argument('--project-root', type=Path, default=Path('.'))
    p.add_argument('--roots-dir', type=Path,
                   default=Path('data/sen1floods11/v2_development_roots'))
    p.add_argument('--m75c-dir', type=Path,
                   default=Path('results/event_level_v2/m75c_sri_lanka_failure_analysis'))
    p.add_argument('--output-dir', type=Path,
                   default=Path('results/event_level_v2/m75d_v2b_design_audit'))
    p.add_argument('--no-plots', action='store_true')
    a = p.parse_args()
    if a.self_test:
        self_test()
        return
    root = a.project_root.expanduser().resolve()

    def resolve(path): return path.resolve(
    ) if path.is_absolute() else (root/path).resolve()
    roots, prior, out = map(resolve, (a.roots_dir, a.m75c_dir, a.output_dir))
    # Verify prior evidence and held-out DEV names before opening any data.
    prior_rows = read_rows(prior/'m75c_per_image.csv')
    pairs = read_rows(prior/'m75c_paired_per_image.csv')
    by_key = evidence_check(prior_rows, pairs)
    out.mkdir(parents=True, exist_ok=True)
    print('M7.5D — READ-ONLY, DEV ONLY; no TEST/Bolivia/Thailand data access')
    print('Verified M7.5C: 42 Sri Lanka DEV images x 3 seeds x 2 methods')
    all_training = []
    files = {}
    sri_valid = {}
    for fold, (expected_train, expected_valid, valid_event) in FOLDS.items():
        loc = roots/fold
        train = manifest(loc, 'train')
        valid = manifest(loc, 'valid')
        if (len(train), len(valid)) != (expected_train, expected_valid):
            raise RuntimeError(
                f'Unexpected frozen split counts for {fold}: {len(train)}, {len(valid)}')
        if {x[2] for x in valid} != {valid_event}:
            raise RuntimeError(f'Validation event mismatch in {fold}')
        if set(x[0] for x in train) & set(x[0] for x in valid):
            raise RuntimeError(
                f'Train/DEV validation duplicate image in {fold}')
        if {x[2] for x in train} & {x[2] for x in valid}:
            raise RuntimeError(f'Train/DEV validation event overlap in {fold}')
        all_training.extend((fold, x) for x in train)
        for x in train:
            files.setdefault(x[0], x)
        if fold == 'dev_fold_02_sri_lanka':
            sri_valid = {x[0]: x for x in valid}
        print(
            f'PASS {fold}: TRAIN={len(train)} DEV VALID={len(valid)}; isolated={valid_event}')
    if len(files) != 243:
        raise RuntimeError(
            f'Expected 243 unique TRAIN/DEV-pool chips, found {len(files)}')
    if not set(CASES).issubset(sri_valid):
        raise RuntimeError('Missing target cases in Sri Lanka DEV VALID')
    # Read 243 unique images once (cache), not 588 duplicate reads or TEST files.
    stats = {}
    for i, (image, (im, lab, event, pi, pl)) in enumerate(sorted(files.items()), 1):
        stats[image] = get_gt_stats(pi, pl)
        if i % 50 == 0 or i == len(files):
            print(f'GT coverage: {i}/243 unique DEV-pool chips')
    rows = []
    for fold, (im, lab, event, pi, pl) in all_training:
        rows.append(dict(fold=fold, event=event, image=im, **stats[im]))
    write_rows(out/'m75d_train_per_chip.csv', rows,
               ['fold', 'event', 'image', 'valid_pixels', 'gt_water_pixels', 'gt_land_pixels', 'water_fraction', 'water_bin'])
    bins = ['zero_water', 'water_0_to_1pct', 'water_1_to_10pct',
            'water_10_to_50pct', 'water_ge_50pct']
    coverage = []
    sampling = []
    for fold, (expected_train, _, _) in FOLDS.items():
        frows = [r for r in rows if r['fold'] == fold]
        c = Counter(r['water_bin'] for r in frows)
        groups = [b for b in bins if c[b]]
        K = len(groups)
        for b in bins:
            n = c[b]
            coverage.append(dict(fold=fold, water_bin=b,
                            n_images=n, share_images=n/len(frows)))
            if n:
                # Candidate ONLY: a 50/50 mixture of uniform and equal nonempty-stratum probabilities.
                # Not frozen, not implemented for training, and may oversample rare cases.
                sampling.append(dict(fold=fold, water_bin=b, n_images=n,
                                     uniform_group_probability=n/len(frows),
                                     candidate_group_probability=.5 *
                                     (n/len(frows))+.5/K,
                                     candidate_per_chip_probability=.5 /
                                     len(frows)+.5/(K*n),
                                     candidate_expected_draws_per_chip_per_epoch=len(frows)*(.5/len(frows)+.5/(K*n))))
    write_rows(out/'m75d_coverage_by_fold.csv', coverage,
               ['fold', 'water_bin', 'n_images', 'share_images'])
    write_rows(out/'m75d_sampling_sensitivity.csv', sampling,
               ['fold', 'water_bin', 'n_images', 'uniform_group_probability', 'candidate_group_probability',
                'candidate_per_chip_probability', 'candidate_expected_draws_per_chip_per_epoch'])
    case_raw = []
    case_metrics = []
    for name in CASES:
        image, lab, event, pi, pl = sri_valid[name]
        s = get_gt_stats(pi, pl, with_sar_stats=True)
        sample = by_key[('baseline', 42, name)]
        if (s['valid_pixels'] != int(sample['valid_pixels']) or
                s['gt_water_pixels'] != int(sample['gt_water_pixels'])):
            raise RuntimeError(f'STOP: local GT/mask disagrees with M7.5C for {name}. '
                               'Check imagery, dataset version, finite mask and label conventions.')
        case_raw.append(dict(image=name, **s))
        for seed in SEEDS:
            for method in ('baseline', 'v2a'):
                x = by_key[(method, seed, name)]
                case_metrics.append({**x, 'gt_check': 'MATCH'})
        if not a.no_plots:
            plot_input_triptych(
                pi, pl, out/(name.removesuffix('_S1Hand.tif')+'_inputs_gt.png'))
            plot_case_metrics(prior_rows, name, out /
                              (name.removesuffix('_S1Hand.tif')+'_recall.png'))
    write_rows(out/'m75d_case_sar_stats.csv', case_raw,
               ['image', 'valid_pixels', 'gt_water_pixels', 'gt_land_pixels', 'water_fraction', 'water_bin',
                'vv_water_median', 'vv_land_median', 'vv_water_minus_land',
                'vh_water_median', 'vh_land_median', 'vh_water_minus_land'])
    write_rows(out/'m75d_case_metrics_verified.csv', case_metrics,
               list(case_metrics[0].keys()))
    summary = ['# M7.5D — V2-B design audit (DEV ONLY)', '',
               '**Status: DATA AUDIT COMPLETE; MODEL V2-B DESIGN NOT YET FROZEN.**',
               'No model fitting, no checkpoint selection, no threshold search and no TEST/Bolivia/Thailand access.',
               'All case metrics are reused from M7.5C (existing checkpoints and threshold 0.5).',
               '', '## TRAIN-only water-coverage inventory', '',
               '| Development fold | Train images | Zero water | (0,1%) | [1%,10%) | [10%,50%) | >=50% |',
               '|---|---:|---:|---:|---:|---:|---:|']
    for fold, (ntrain, _, _) in FOLDS.items():
        c = Counter(r['water_bin'] for r in rows if r['fold'] == fold)
        summary.append(
            '| ' + ' | '.join([fold, str(ntrain)]+[str(c[b]) for b in bins])+' |')
    summary.extend(['', '### Notes on image-based sampling',
                    '- Full-chip water coverage can differ from water coverage in randomly cropped 256x256 patches.',
                    '- Rare water-coverage bins might be excessively repeated by a class-balanced sampler with replacement.',
                    '- Candidate mixture probabilities are diagnostics ONLY, not authorization to modify the frozen baseline.',
                    '- Check how many unique images appear in >=50% water before deciding whether the sampling hypothesis is practical.',
                    '', '## Sri Lanka three-case DEV audit', '',
                    '| Image | GT-water % | VV water-land median gap (TIFF units) | VH gap (TIFF units) |',
                    '|---|---:|---:|---:|'])
    for r in case_raw:
        summary.append(
            f"| {r['image']} | {100*r['water_fraction']:.2f}% | {r['vv_water_minus_land']:.3f} | {r['vh_water_minus_land']:.3f} |")
    summary.extend(['', 'M7.5C prediction diagnostics for the three cases:', '',
                    '| Case | Method | Seed | Water recall | IoU | Predicted-water % | FP | FN |',
                    '|---|---|---:|---:|---:|---:|---:|---:|'])
    for r in case_metrics:
        summary.append(
            f"| {r['image']} | {r['method']} | {r['seed']} | {float(r['recall']):.4f} | {float(r['iou']):.4f} | {100*float(r['pred_water_fraction']):.2f}% | {r['fp']} | {r['fn']} |")
    summary.extend(['', '## Proposed V2-B decision gate (manual sign-off required)',
                    '1. Inspect train-by-fold counts and rare-bin expected repeat exposures. If >=50%-water bins are extremely small, do not over-weight them without safeguards.',
                    '2. Inspect the three GT/VV/VH figures and verify masks, SAR units/order and any suspicious image-label patterns.',
                    '3. Re-check V2-A source/actual checkpoint provenance; the earlier M7.5C manifest noted missing run_config.json for 3 V2-A checkpoints.',
                    '4. Decide exactly ONE training change. Candidate: predeclared water-coverage-aware image sampler; keep baseline architecture, loss, normalization, optimizer, folds, seeds and threshold fixed.',
                    '5. Freeze a separate V2-B protocol BEFORE new training. Evaluate on 3 DEV validation events x seeds 42/123/777. Historical TEST/Bolivia/Thailand remain excluded.',
                    '', '**Limitations:** Observed training coverage and case correlations are not causal identification. These same DEV events informed the method and cannot be called untouched confirmatory testing.',
                    'Ground-truth surface water is not automatically newly inundated flood water.', ''])
    (out/'m75d_report.md').write_text('\n'.join(summary), encoding='utf-8')
    manifest_out = {'status': 'DEV_AUDITED_NOT_FROZEN', 'n_unique_dev_chips': len(files),
                    'n_train_memberships': len(rows),
                    'folds': {f: {'train': tr, 'valid': va, 'validation_event': ev} for f, (tr, va, ev) in FOLDS.items()},
                    'cases': list(CASES), 'm75c_per_image_source': str(prior/'m75c_per_image.csv'),
                    'test_accessed': False, 'model_trained': False,
                    'fixed_threshold_from_m75c': 0.5,
                    'candidate_sampler': 'UNFROZEN diagnostic only'}
    (out/'m75d_manifest.json').write_text(json.dumps(manifest_out, indent=2), encoding='utf-8')
    print('\nPASS: 243 unique DEV chips; per-fold TRAIN coverage; 3 Sri Lanka case GT checks matched M7.5C')
    print('Saved:', out)
    for fold in FOLDS:
        c = Counter(r['water_bin'] for r in rows if r['fold'] == fold)
        print(f"{fold}: "+', '.join(f'{b}={c[b]}' for b in bins))
    print('STATUS: M7.5D audited, V2-B method NOT YET FROZEN; NO model trained or TEST accessed')


if __name__ == '__main__':
    main()
