#!/usr/bin/env python3
"""M7.5C: Sri Lanka DEV-only paired per-image diagnostics (no training / no TEST).

Uses the EXISTING frozen V2 development split and six existing checkpoints.
Does not change checkpoints, hyperparameters, normalization, or thresholds.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

SEEDS = (42, 123, 777)
EVENT = "dev_fold_02_sri_lanka"
FIXED_THRESHOLD = 0.5
DB_MIN = (-35.0, -40.0)
DB_MAX = (5.0, 0.0)


def safe_div(n, d):
    return n / d if d else float('nan')


def scores(tp, fp, fn):
    return {"iou": safe_div(tp, tp + fp + fn),
            "recall": safe_div(tp, tp + fn),
            "precision": safe_div(tp, tp + fp)}


def write_csv(path, rows, columns):
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def finite_mean(values):
    vals = [float(x) for x in values if math.isfinite(float(x))]
    return statistics.mean(vals) if vals else float('nan')


def check_checkpoint(ckpt, path):
    if ckpt.get('architecture') != 'SmallUNet':
        raise ValueError(f"Unexpected architecture in {path}")
    base = int(ckpt['base_channels'])
    if base != 16:
        raise ValueError(f"Unexpected base_channels {base} in {path}")
    if abs(float(ckpt.get('threshold', FIXED_THRESHOLD)) - FIXED_THRESHOLD) > 1e-9:
        raise ValueError(f"Threshold not frozen at {FIXED_THRESHOLD}: {path}")
    for name, expected in [('db_min', DB_MIN), ('db_max', DB_MAX)]:
        got = [float(v) for v in ckpt.get(name, expected)]
        if len(got) != 2 or any(abs(a-b) > 1e-6 for a, b in zip(got, expected)):
            raise ValueError(f"Normalization {name} mismatch in {path}: {got}")
    return base


def water_group(fraction):
    if fraction == 0:
        return 'zero GT water'
    if fraction < 0.01:
        return '(0, 1%) GT water'
    if fraction < 0.10:
        return '[1%, 10%) GT water'
    return '>=10% GT water'


def evaluate_one(model, dataset, records, device, torch, np, method, seed):
    rows = []
    model.eval()
    with torch.inference_mode():
        for i in range(len(dataset)):
            x, y, valid = dataset[i]
            if x.ndim != 3 or x.shape[0] != 2:
                raise ValueError(
                    f"Unexpected SAR shape for image #{i}: {x.shape}")
            if y.shape != valid.shape:
                raise ValueError(f"Target / mask mismatch at index {i}")
            logits = model(x.unsqueeze(0).to(device))
            p = torch.sigmoid(logits).detach().cpu().numpy()[0, 0]
            truth = y.numpy()[0] > 0.5
            mask = valid.numpy()[0].astype(bool)
            if p.shape != truth.shape:
                raise ValueError(
                    f"Prediction / GT shape mismatch for image #{i}")
            n_valid = int(mask.sum())
            if n_valid == 0:
                raise ValueError(f"No evaluable pixels at image #{i}")
            pred = p >= FIXED_THRESHOLD
            tp = int(np.count_nonzero(pred & truth & mask))
            fp = int(np.count_nonzero(pred & ~truth & mask))
            fn = int(np.count_nonzero(~pred & truth & mask))
            tn = int(np.count_nonzero(~pred & ~truth & mask))
            water_n = tp + fn
            vals = scores(tp, fp, fn)
            image_name = Path(records[i][0]).name
            rows.append(dict(method=method, seed=seed, image=image_name,
                             valid_pixels=n_valid, gt_water_pixels=water_n,
                             water_fraction=water_n/n_valid,
                             pred_water_fraction=(tp+fp)/n_valid,
                             tp=tp, fp=fp, fn=fn, tn=tn,
                             iou=vals['iou'], recall=vals['recall'],
                             precision=vals['precision'],
                             brier=float(np.mean((p[mask]-truth[mask])**2)),
                             fn_prob_below_0_1=(int(np.count_nonzero(
                                 (p < 0.1) & ~pred & truth & mask)) / water_n)
                             if water_n else float('nan')))
            if (i+1) % 10 == 0 or i+1 == len(dataset):
                print(
                    f"{method} seed={seed}: {i+1}/{len(dataset)} DEV validation images", flush=True)
    return rows


def make_report(out, all_rows, pairs, checkpoints, configs_missing):
    lines = [
        '# M7.5C — Sri Lanka Per-Image Failure Analysis (DEV ONLY)',
        '',
        '**Scope:** Frozen Sri Lanka development validation (42 chips). Existing six checkpoints only.',
        '**No** model training, TEST/Bolivia/Thailand access, threshold search, or model selection on TEST.',
        '**Metric:** water-class IoU (undefined/NaN if no water in GT and prediction); recall undefined for zero GT-water images.',
        '**Comparison unit:** matched image within seed; repeated seeds/images are not independent events.',
        '',
        '## Aggregate performance from recomputed DEV pixels',
        '',
        '| Seed | Method | Valid images | Micro IoU | Micro Recall | Mean per-image IoU (defined only) |',
        '|---:|---|---:|---:|---:|---:|',
    ]
    for seed in SEEDS:
        for method in ('baseline', 'v2a'):
            r = [q for q in all_rows if q['seed']
                 == seed and q['method'] == method]
            sums = {c: sum(q[c] for q in r) for c in ('tp', 'fp', 'fn')}
            s = scores(**sums)
            lines.append(
                f"| {seed} | {method} | {len(r)} | {s['iou']:.5f} | {s['recall']:.5f} | {finite_mean(q['iou'] for q in r):.5f} |")
    lines.extend(['', '## Within-seed per-image deltas', '',
                  'Delta = V2-A IoU − Baseline IoU on the exact same image. NaN/undefined IoUs are not ranked.', ''])
    for seed in SEEDS:
        subset = [r for r in pairs if r['seed'] ==
                  seed and math.isfinite(r['iou_delta'])]
        subset.sort(key=lambda r: r['iou_delta'])
        lines.extend([f'### Seed {seed}', '', '| Image | GT-water % | Baseline IoU | V2-A IoU | Delta |',
                      '|---|---:|---:|---:|---:|'])
        for r in subset[:8]:
            lines.append(
                f"| {r['image']} | {100*r['water_fraction']:.2f}% | {r['baseline_iou']:.4f} | {r['v2a_iou']:.4f} | {r['iou_delta']:+.4f} |")
        lines.append('')
    lines.extend(['## Failure-stratification summary', '',
                  'Descriptive only. Each image is reused over three seeds; these are not independent geographic events.', '',
                  '| Method | Seed | GT-water group | Images | Mean defined per-image IoU | Mean defined recall |',
                  '|---|---:|---|---:|---:|---:|'])
    groups = sorted(set(water_group(r['water_fraction']) for r in all_rows))
    for method in ('baseline', 'v2a'):
        for seed in SEEDS:
            for group in groups:
                r = [x for x in all_rows if x['method'] == method and x['seed']
                     == seed and water_group(x['water_fraction']) == group]
                if not r:
                    continue
                lines.append(
                    f"| {method} | {seed} | {group} | {len(r)} | {finite_mean(x['iou'] for x in r):.4f} | {finite_mean(x['recall'] for x in r):.4f} |")
    lines.extend(['', '## Run provenance and limitations', '',
                  '- Checkpoints were reused unchanged with frozen threshold 0.5 and train_sar_unet.py preprocessing.',
                  '- Original frozen protocol must remain unchanged. Source-configuration verification is still manual where V2-A run_config.json is missing.',
                  f'- V2-A checkpoint folders without run_config.json: **{len(configs_missing)}** / 3 for Sri Lanka.',
                  '- Do not infer causality from group differences or Gradients/XAI; no XAI was run in this analysis.',
                  '- Proposed V2-B should be one change based on DEV evidence, followed by same 3 folds × 3 seeds and a frozen protocol.',
                  '- Keep historical TEST events out of development and reserve independent, appropriately labeled events for final evaluation.',
                  '', '## Checkpoints', ''])
    for name, path in checkpoints.items():
        lines.append(f'- `{name}`: `{path}`')
    (out/'m75c_report.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')


def plot_delta(out, paired):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        print('Matplotlib unavailable: skipping optional figure')
        return
    fig, ax = plt.subplots(figsize=(8, 5.5))
    for seed in SEEDS:
        subset = [r for r in paired if r['seed'] ==
                  seed and math.isfinite(r['iou_delta'])]
        ax.scatter([100*r['water_fraction'] for r in subset],
                   [r['iou_delta'] for r in subset], label=f'Seed {seed}', alpha=.65)
    ax.axhline(0, linestyle='--', linewidth=1)
    ax.set_xlabel('Ground-truth water share of evaluable pixels (%)')
    ax.set_ylabel('Per-image IoU difference: V2-A minus baseline')
    ax.set_title('Sri Lanka DEV — paired model changes (not independent TEST)')
    ax.legend()
    ax.grid(alpha=.2)
    fig.tight_layout()
    fig.savefig(out/'m75c_per_image_iou_deltas.png', dpi=150)
    plt.close(fig)


def self_test():
    assert scores(2, 1, 1)['iou'] == 0.5
    assert math.isnan(scores(0, 0, 0)['iou'])
    assert math.isnan(scores(0, 0, 0)['recall'])
    assert water_group(.001) == '(0, 1%) GT water'
    print('PASS: M7.5C basic metrics self-test; no data or checkpoints opened')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--self-test', action='store_true')
    p.add_argument('--project-root', type=Path, default=Path('.'))
    p.add_argument('--output-dir', type=Path,
                   default=Path('results/event_level_v2/m75c_sri_lanka_failure_analysis'))
    p.add_argument('--device', choices=('auto', 'cpu',
                   'mps', 'cuda'), default='auto')
    a = p.parse_args()
    if a.self_test:
        self_test()
        return
    import numpy as np
    import torch
    from train_sar_unet import SmallUNet, SarWaterDataset, split_records

    root = a.project_root.expanduser().resolve()
    data_root = root/'data/sen1floods11/v2_development_roots'/EVENT
    records = split_records(data_root, 'valid')
    if len(records) != 42:
        raise RuntimeError(
            f'Expected Sri Lanka DEV validation=42, found {len(records)}. STOP.')
    if any(str(r[2]).lower().replace('-', '') != 'srilanka' for r in records):
        raise RuntimeError(
            'Unexpected site in development validation records; STOP.')
    if a.device == 'auto':
        device = 'mps' if torch.backends.mps.is_available() else (
            'cuda' if torch.cuda.is_available() else 'cpu')
    else:
        device = a.device
    if device == 'mps' and not torch.backends.mps.is_available():
        raise RuntimeError('MPS not available')
    if device == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('CUDA not available')
    out = (root/a.output_dir).resolve() if not a.output_dir.is_absolute() else a.output_dir.resolve()
    out.mkdir(exist_ok=True, parents=True)
    dataset = SarWaterDataset(records, augment=False)
    all_rows = []
    checkpoints = {}
    configs_missing = []
    print(
        f'DEV validation only: 42 Sri Lanka chips; device={device}; fixed threshold=0.5')
    for seed in SEEDS:
        for method, folder in (('baseline', f'baseline_seed{seed}'),
                               ('v2a', f'v2a_eventbalanced_seed{seed}')):
            folder_path = root/'results/event_level_v2'/folder/EVENT
            checkpoint_path = folder_path/'best_sar_unet.pt'
            if not checkpoint_path.is_file():
                raise FileNotFoundError(
                    f'Missing checkpoint: {checkpoint_path}')
            checkpoint = torch.load(
                checkpoint_path, map_location='cpu', weights_only=True)
            base = check_checkpoint(checkpoint, checkpoint_path)
            if method == 'v2a' and not (folder_path/'run_config.json').is_file():
                configs_missing.append(str(folder_path))
            model = SmallUNet(base).to(device)
            model.load_state_dict(checkpoint['model_state'], strict=True)
            rows = evaluate_one(model, dataset, records,
                                device, torch, np, method, seed)
            all_rows.extend(rows)
            checkpoints[f'{method} seed={seed}'] = str(
                checkpoint_path.relative_to(root))
            del model, checkpoint
            if device == 'mps' and hasattr(torch.mps, 'empty_cache'):
                torch.mps.empty_cache()
            if device == 'cuda':
                torch.cuda.empty_cache()
    matched = defaultdict(dict)
    for row in all_rows:
        key = (row['seed'], row['image'])
        matched[key][row['method']] = row
    pairs = []
    for (seed, image), pair in sorted(matched.items()):
        if set(pair) != {'baseline', 'v2a'}:
            raise RuntimeError(f'Incomplete matching: {seed} / {image}')
        b, v = pair['baseline'], pair['v2a']
        if b['gt_water_pixels'] != v['gt_water_pixels'] or b['valid_pixels'] != v['valid_pixels']:
            raise RuntimeError(
                f'Ground truth changed across comparisons: {seed}/{image}')
        pairs.append(dict(seed=seed, image=image, valid_pixels=b['valid_pixels'],
                          gt_water_pixels=b['gt_water_pixels'], water_fraction=b['water_fraction'],
                          baseline_iou=b['iou'], v2a_iou=v['iou'],
                          iou_delta=v['iou']-b['iou'],
                          baseline_recall=b['recall'], v2a_recall=v['recall'],
                          recall_delta=v['recall']-b['recall'],
                          baseline_fp=b['fp'], v2a_fp=v['fp'], baseline_fn=b['fn'], v2a_fn=v['fn']))
    if len(pairs) != 42 * len(SEEDS):
        raise RuntimeError(
            f'Unexpected number of paired image records: {len(pairs)}')
    cols = ['method', 'seed', 'image', 'valid_pixels', 'gt_water_pixels', 'water_fraction', 'pred_water_fraction',
            'tp', 'fp', 'fn', 'tn', 'iou', 'recall', 'precision', 'brier', 'fn_prob_below_0_1']
    write_csv(out/'m75c_per_image.csv', all_rows, cols)
    write_csv(out/'m75c_paired_per_image.csv', pairs, list(pairs[0].keys()))
    make_report(out, all_rows, pairs, checkpoints, configs_missing)
    plot_delta(out, pairs)
    (out/'m75c_run_manifest.json').write_text(json.dumps({
        'status': 'DEV_ONLY', 'event': 'Sri Lanka', 'n_images': 42,
        'seeds': list(SEEDS), 'methods': ['baseline', 'v2a'],
        'threshold': FIXED_THRESHOLD, 'checkpoints': checkpoints,
        'v2a_missing_run_config': configs_missing,
        'test_accessed': False, 'model_trained': False,
    }, indent=2), encoding='utf-8')
    print(
        f'PASS: Saved {len(all_rows)} per-image records and {len(pairs)} pairs to {out}')
    print(
        f'WARNING: V2-A runs without run_config.json: {len(configs_missing)}. Audit source config manually.')
    print('No TEST/Bolivia/Thailand data accessed. No model fitted or tuned.')


if __name__ == '__main__':
    main()
