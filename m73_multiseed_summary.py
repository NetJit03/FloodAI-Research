#!/usr/bin/env python3
"""M7.3: read-only summary of 3-fold x 3-seed V2 baseline validation.

Requires Python standard library and PyTorch (for checkpoint verification).
Matplotlib is optional for one visualization.
Does NOT train, evaluate test events, select hyperparameters or change checkpoints.
"""
import argparse
import csv
import math
from pathlib import Path
import statistics
import sys

FOLDS = {
    'dev_fold_01_usa': ('USA', 174, 69),
    'dev_fold_02_sri_lanka': ('Sri Lanka', 201, 42),
    'dev_fold_03_spain': ('Spain', 213, 30),
}
SEEDS = (42, 123, 777)


def read_csv(path):
    with path.open(newline='', encoding='utf-8') as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise ValueError(f'Empty CSV: {path}')
    return rows


def write_csv(path, rows, fields):
    with path.open('w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def nfmt(x, digits=4):
    return f'{x:.{digits}f}'


def summarize(root, out, skip_plots=False):
    try:
        import torch
    except ImportError:
        raise SystemExit('PyTorch is required to verify all 9 checkpoint epochs. Activate your project .venv.')

    data = []
    for seed in SEEDS:
        for fold, (event, train_count, valid_count) in FOLDS.items():
            folder = root / f'baseline_seed{seed}' / fold
            history_path = folder / 'history.csv'
            checkpoint_path = folder / 'best_sar_unet.pt'
            if not history_path.is_file() or not checkpoint_path.is_file():
                raise FileNotFoundError(f'Missing history/checkpoint: {folder}')
            rows = read_csv(history_path)
            valid_rows = []
            for r in rows:
                if 'val_iou' not in r or 'epoch' not in r:
                    raise ValueError(f'Unexpected history columns: {history_path}')
                score = float(r['val_iou'])
                if math.isfinite(score):
                    valid_rows.append((int(r['epoch']), score, r))
            if not valid_rows:
                raise ValueError(f'No finite IoU in {history_path}')
            best_epoch, best_iou, best_row = max(valid_rows, key=lambda r: r[1])
            checkpoint = torch.load(checkpoint_path, map_location='cpu', weights_only=True)
            ck_epoch = int(checkpoint['epoch'])
            ck_iou = float(checkpoint.get('validation_metrics', {}).get('iou', float('nan')))
            if ck_epoch != best_epoch or not math.isclose(ck_iou, best_iou, rel_tol=0, abs_tol=1e-5):
                raise ValueError(f'Checkpoint/history mismatch at {folder}: epoch {ck_epoch} vs {best_epoch}, IoU {ck_iou} vs {best_iou}')
            if int(checkpoint.get('seed', -1)) != seed:
                raise ValueError(f'Seed mismatch in checkpoint: {folder}')
            if int(checkpoint.get('train_count', -1)) != train_count or int(checkpoint.get('valid_count', -1)) != valid_count:
                raise ValueError(f'Data counts mismatch: {folder}')
            if float(checkpoint.get('threshold', -1)) != 0.5:
                raise ValueError(f'Expected frozen threshold 0.5: {folder}')
            record = {
                'seed': seed, 'fold': fold, 'validation_event': event,
                'train_images': train_count, 'valid_images': valid_count,
                'epochs_completed': len(rows), 'best_epoch': best_epoch,
                'best_val_iou': best_iou,
                'best_val_f1': float(best_row['val_f1']),
                'best_val_recall': float(best_row['val_recall']),
                'best_val_precision': float(best_row['val_precision']),
                'best_val_loss': float(best_row['val_loss']),
                'checkpoint_path': str(checkpoint_path),
            }
            data.append(record)
            print(f"PASS seed={seed} event={event}: epoch={best_epoch} IoU={best_iou:.5f}")

    by_event = []
    for event in ('USA', 'Sri Lanka', 'Spain'):
        vals = [r['best_val_iou'] for r in data if r['validation_event'] == event]
        by_event.append({'validation_event': event, 'n_seeds': len(vals),
                         'mean_iou': statistics.mean(vals), 'sample_sd_iou': statistics.stdev(vals),
                         'min_iou': min(vals), 'max_iou': max(vals), 'range_iou': max(vals)-min(vals)})
    by_seed = []
    for seed in SEEDS:
        vals = [r['best_val_iou'] for r in data if r['seed'] == seed]
        by_seed.append({'seed': seed, 'n_events': len(vals), 'macro_mean_iou': statistics.mean(vals)})
    across_seeds = [r['macro_mean_iou'] for r in by_seed]
    overall_mean = statistics.mean(across_seeds)
    overall_sd = statistics.stdev(across_seeds)

    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / 'm73_run_summary.csv', data, list(data[0]))
    write_csv(out / 'm73_event_summary.csv', by_event, list(by_event[0]))
    write_csv(out / 'm73_seed_summary.csv', by_seed, list(by_seed[0]))

    lines = [
        '# M7.3 — Multi-Seed Baseline Validation Summary', '',
        '- Source: fixed V2 development folds, full runs of SmallUNet baseline.',
        '- Seeds: 42, 123, 777; selection by best VALIDATION micro water IoU per fold.',
        '- No TEST or Bolivia or Thailand data were evaluated here.',
        '- Different seeds of the same development events are not independent geographic samples.',
        '- SD uses sample standard deviation (ddof=1), with n=3.', '',
        '## Best validation IoU per fold and seed', '',
        '| Event | Seed 42 | Seed 123 | Seed 777 | Mean | Sample SD |',
        '|---|---:|---:|---:|---:|---:|',
    ]
    for ev in by_event:
        event = ev['validation_event']
        vals = [next(r['best_val_iou'] for r in data if r['validation_event']==event and r['seed']==seed) for seed in SEEDS]
        lines.append(f"| {event} | {' | '.join(nfmt(v) for v in vals)} | {nfmt(ev['mean_iou'])} | {nfmt(ev['sample_sd_iou'])} |")
    lines += ['', '## Macro average across validation events, per seed', '',
              '| Seed | Macro mean validation IoU |', '|---|---:|']
    lines += [f"| {r['seed']} | {nfmt(r['macro_mean_iou'])} |" for r in by_seed]
    lines += ['', f'**Across-seed mean of the three macro means:** {overall_mean:.4f}',
              f'**Across-seed sample SD of macro means:** {overall_sd:.4f}', '',
              '## Interpretation constraints', '',
              '- A single poorly performing seed on Sri Lanka is evidence of seed sensitivity in this setup, not proof of domain shift or its cause.',
              '- Keep all nine runs, including outliers. Do not select/drop seeds on the basis of these validation metrics.',
              '- Before comparing V1 and V2, use identical folds, random seeds, and frozen evaluation policy.',
              '- Fresh independent event-level held-out data are required for a definitive generalization claim.', '']
    (out / 'm73_results.md').write_text('\n'.join(lines), encoding='utf-8')

    if not skip_plots:
        try:
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(8.4, 4.7))
            for seed in SEEDS:
                values = [next(r['best_val_iou'] for r in data if r['seed']==seed and r['validation_event']==event)
                          for event in ('USA', 'Sri Lanka', 'Spain')]
                ax.plot(('USA', 'Sri Lanka', 'Spain'), values, marker='o', label=f'Seed {seed}')
            ax.set_ylim(0, 1)
            ax.set_ylabel('Best validation water IoU')
            ax.set_title('M7.3: baseline stability across seeds and development events')
            ax.grid(alpha=0.2)
            ax.legend()
            fig.tight_layout()
            fig.savefig(out / 'm73_multiseed_iou.png', dpi=180)
            plt.close(fig)
        except ImportError:
            print('NOTE: matplotlib not installed, skipping PNG plot')
    print(f'\nM7.3 macro across seeds: {overall_mean:.4f} ± {overall_sd:.4f} (sample SD)')
    print('Saved reports in:', out)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--results-root', type=Path, default=Path('results/event_level_v2'))
    p.add_argument('--output-dir', type=Path, default=Path('results/event_level_v2/m73_multiseed_summary'))
    p.add_argument('--skip-plots', action='store_true')
    args = p.parse_args()
    summarize(args.results_root, args.output_dir, args.skip_plots)


if __name__ == '__main__':
    main()
