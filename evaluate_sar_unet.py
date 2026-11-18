#!/usr/bin/env python3
"""Evaluate an ALREADY-TRAINED Sen1Floods11 SmallUNet, without fitting or tuning.

Requires train_sar_unet.py in the same directory. Saves micro-aggregated metrics,
site-level and per-image reports, and reproducible prediction previews.

Usage (from FloodAI-Research project root):
    python evaluate_sar_unet.py \
      --checkpoint results/sar_unet_baseline_v1/best_sar_unet.pt \
      --data-root data/sen1floods11 \
      --output-dir results/sar_unet_baseline_v1/evaluation

Both official test and Bolivia are evaluated at the fixed checkpoint threshold
(usually 0.5); do not choose a new threshold using test results.
"""
from __future__ import annotations
from train_sar_unet import (
    SmallUNet, SarWaterDataset, masked_bce_dice, split_records, DB_MIN, DB_MAX
)
from torch.utils.data import DataLoader
import torch
import numpy as np
from matplotlib.patches import Patch
from matplotlib.colors import ListedColormap
import matplotlib.pyplot as plt

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")


def pick_device(selection: str) -> str:
    if selection != 'auto':
        if selection == 'mps' and not torch.backends.mps.is_available():
            raise RuntimeError('MPS requested but unavailable')
        if selection == 'cuda' and not torch.cuda.is_available():
            raise RuntimeError('CUDA requested but unavailable')
        return selection
    if torch.backends.mps.is_available():
        return 'mps'
    if torch.cuda.is_available():
        return 'cuda'
    return 'cpu'


def safe_div(a: int | float, b: int | float) -> float:
    return float(a / b) if b else float('nan')


def metrics(counts: dict) -> dict:
    tp, tn, fp, fn = [counts[k] for k in ('tp', 'tn', 'fp', 'fn')]
    return {
        'iou': safe_div(tp, tp+fp+fn),
        'f1': safe_div(2*tp, 2*tp+fp+fn),
        'precision': safe_div(tp, tp+fp),
        'recall': safe_div(tp, tp+fn),
        'accuracy': safe_div(tp+tn, tp+tn+fp+fn),
        'water_fraction_gt': safe_div(tp+fn, tp+tn+fp+fn),
        'water_fraction_pred': safe_div(tp+fp, tp+tn+fp+fn),
        'brier_score': safe_div(counts['brier_sum'], counts['valid_pixels']),
    }


def finite_mean(vals):
    vals = [float(v) for v in vals if math.isfinite(float(v))]
    return sum(vals)/len(vals) if vals else float('nan')


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def save_preview(path: Path, name: str, x: np.ndarray, y: np.ndarray,
                 valid: np.ndarray, prob: np.ndarray, threshold: float):
    """VV normalized for display; labels drawn only for valid pixels."""
    prediction = prob >= threshold
    truth = y.astype(bool)
    mask = np.ma.masked_where(~valid, truth.astype('uint8'))
    pred_mask = np.ma.masked_where(~valid, prediction.astype('uint8'))

    # Green: correct water, red: false alarm, orange: missed water, transparent: correct land.
    errors = np.zeros((*truth.shape, 4), dtype=np.float32)
    errors[valid & prediction & truth] = [0.15, 0.82, 0.42, 0.65]
    errors[valid & prediction & ~truth] = [1.00, 0.15, 0.19, 0.75]
    errors[valid & ~prediction & truth] = [1.00, 0.68, 0.07, 0.80]
    vv = np.ma.masked_where(~valid, x[0])

    fig, ax = plt.subplots(2, 2, figsize=(10, 9))
    fig.suptitle(f'{name}  |  fixed threshold = {threshold:.2f}', fontsize=12)
    ax[0, 0].imshow(vv, cmap='gray', vmin=0, vmax=1)
    ax[0, 0].set_title('Input VV (normalized for display)')
    cmap = ListedColormap(['#cccccc', '#168bcf'])
    cmap.set_bad('white')
    ax[0, 1].imshow(mask, cmap=cmap, vmin=-.5, vmax=1.5)
    ax[0, 1].set_title('Sen1Floods11 Ground Truth')
    ax[1, 0].imshow(pred_mask, cmap=cmap, vmin=-.5, vmax=1.5)
    ax[1, 0].set_title('Model predicted water (thresholded)')
    ax[1, 1].imshow(vv, cmap='gray', vmin=0, vmax=1)
    ax[1, 1].imshow(errors)
    ax[1, 1].set_title('Errors over input VV')
    ax[1, 1].legend(handles=[
        Patch(color='#26d16b', label='True positive (water)'),
        Patch(color='#ff262f', label='False positive'),
        Patch(color='#ffad12', label='False negative'),
    ], loc='lower center', bbox_to_anchor=(.5, -.12), ncol=1, fontsize=8)
    for a in ax.flat:
        a.set_xticks([])
        a.set_yticks([])
    fig.tight_layout(rect=(0, .02, 1, .96))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=120, bbox_inches='tight')
    plt.close(fig)


def evaluate_split(model, records, split: str, device: str,
                   threshold: float, outdir: Path, npreviews: int) -> dict:
    dataset = SarWaterDataset(records, augment=False)
    loader = DataLoader(dataset, batch_size=1, shuffle=False,
                        num_workers=0, pin_memory=False)
    selected = set()
    if npreviews > 0:
        selected = {int(round(j)) for j in np.linspace(
            0, len(dataset)-1, min(npreviews, len(dataset)))}

    totals = dict.fromkeys(('tp', 'tn', 'fp', 'fn', 'valid_pixels'), 0)
    totals['brier_sum'] = 0.0
    losses = []
    rows = []
    by_site = defaultdict(lambda: dict(
        tp=0, tn=0, fp=0, fn=0, valid_pixels=0, brier_sum=0.0, n_images=0))

    print(f'\n=== {split.upper()} : {len(records)} images ===', flush=True)
    model.eval()
    with torch.inference_mode():
        for idx, ((x, y, v), (image_path, _label_path, site)) in enumerate(zip(loader, records)):
            if int(v.sum()) == 0:
                raise RuntimeError(f'No evaluable pixels in {image_path.name}')
            x_device = x.to(device)
            logits = model(x_device)
            probabilities = torch.sigmoid(logits).cpu().numpy()[0, 0]
            loss = float(masked_bce_dice(
                logits, y.to(device), v.to(device)).item())
            losses.append(loss)
            y_np = y.numpy()[0, 0] > 0.5
            v_np = v.numpy()[0, 0].astype(bool)
            x_np = x.numpy()[0]
            pr = probabilities >= threshold
            c = {
                'tp': int(np.count_nonzero(pr & y_np & v_np)),
                'tn': int(np.count_nonzero(~pr & ~y_np & v_np)),
                'fp': int(np.count_nonzero(pr & ~y_np & v_np)),
                'fn': int(np.count_nonzero(~pr & y_np & v_np)),
                'valid_pixels': int(v_np.sum()),
                'brier_sum': float(np.square(probabilities[v_np]-y_np[v_np]).sum(dtype=np.float64)),
            }
            for k in c:
                totals[k] += c[k]
                by_site[site][k] += c[k]
            by_site[site]['n_images'] += 1
            rows.append({'split': split, 'name': image_path.name, 'site_prefix': site,
                         **{k: c[k] for k in ('tp', 'tn', 'fp', 'fn', 'valid_pixels')},
                         'val_loss': loss, **metrics(c)})
            if idx in selected:
                preview_name = f'{split}_{idx:03d}_{image_path.stem}.png'
                save_preview(outdir/'previews'/preview_name, image_path.stem,
                             x_np, y_np, v_np, probabilities, threshold)
            if (idx+1) % 20 == 0 or idx == len(dataset)-1:
                print(f'  processed {idx+1}/{len(dataset)}', flush=True)

    per_image_path = outdir/f'{split}_per_image.csv'
    fields = ['split', 'name', 'site_prefix', 'valid_pixels', 'tp', 'tn', 'fp', 'fn', 'val_loss',
              'iou', 'f1', 'precision', 'recall', 'accuracy', 'water_fraction_gt',
              'water_fraction_pred', 'brier_score']
    write_csv(per_image_path, rows, fields)
    per_site = []
    for site, counts in sorted(by_site.items()):
        per_site.append({'site_prefix': site, 'n_images': counts['n_images'],
                         'valid_pixels': counts['valid_pixels'],
                         **{k: counts[k] for k in ('tp', 'tn', 'fp', 'fn')}, **metrics(counts)})
    write_csv(outdir/f'{split}_per_site.csv', per_site,
              ['site_prefix', 'n_images', 'valid_pixels', 'tp', 'tn', 'fp', 'fn',
               'iou', 'f1', 'precision', 'recall', 'accuracy', 'water_fraction_gt',
               'water_fraction_pred', 'brier_score'])
    micro = metrics(totals)
    print(f"  IoU={micro['iou']:.4f} | F1={micro['f1']:.4f} | "
          f"Recall={micro['recall']:.4f} | Precision={micro['precision']:.4f} | "
          f"Brier={micro['brier_score']:.4f}")
    return {'split': split, 'n_images': len(records), 'n_site_prefixes': len(by_site),
            'aggregate_counts': totals, 'micro_metrics': micro,
            'mean_image_iou_nonempty_union': finite_mean(r['iou'] for r in rows),
            'mean_site_iou': finite_mean(s['iou'] for s in per_site),
            'mean_image_loss': finite_mean(losses),
            'images_with_zero_gt_water': sum((r['tp']+r['fn']) == 0 for r in rows),
            'images_with_zero_union': sum((r['tp']+r['fn']+r['fp']) == 0 for r in rows)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkpoint', type=Path,
                   default=Path('results/sar_unet_baseline_v1/best_sar_unet.pt'))
    p.add_argument('--data-root', type=Path, default=Path('data/sen1floods11'))
    p.add_argument('--output-dir', type=Path,
                   default=Path('results/sar_unet_baseline_v1/evaluation'))
    p.add_argument('--splits', nargs='+',
                   choices=['test', 'bolivia'], default=['test', 'bolivia'])
    p.add_argument(
        '--device', choices=['auto', 'cpu', 'mps', 'cuda'], default='auto')
    p.add_argument('--previews-per-split', type=int, default=3)
    args = p.parse_args()

    if not args.checkpoint.is_file():
        p.error(f'Checkpoint not found: {args.checkpoint}')
    device = pick_device(args.device)
    checkpoint = torch.load(
        args.checkpoint, map_location='cpu', weights_only=True)
    if checkpoint.get('architecture') != 'SmallUNet':
        raise ValueError('Checkpoint architecture is not SmallUNet')
    base = int(checkpoint['base_channels'])
    threshold = float(checkpoint.get('threshold', .5))
    if not (0 < threshold < 1):
        raise ValueError('Invalid checkpoint threshold')
    stored_min = np.asarray(checkpoint.get(
        'db_min', [-35, -40]), dtype=float).ravel()
    stored_max = np.asarray(checkpoint.get(
        'db_max', [5, 0]), dtype=float).ravel()
    if not (np.allclose(stored_min, DB_MIN.ravel()) and np.allclose(stored_max, DB_MAX.ravel())):
        raise ValueError(
            'Checkpoint normalization != train_sar_unet.py normalization')
    model = SmallUNet(base)
    model.load_state_dict(checkpoint['model_state'], strict=True)
    model.to(device).eval()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print('Checkpoint:', args.checkpoint)
    print('Selected epoch:', checkpoint.get('epoch'))
    print('Device:', device)
    print('Fixed threshold (from checkpoint):', threshold)
    print('Model fit or tuning: NONE')
    results = []
    for split in args.splits:
        records = split_records(args.data_root, split)
        if not records:
            raise RuntimeError(f'Empty split: {split}')
        results.append(evaluate_split(model, records, split, device, threshold,
                                      args.output_dir, args.previews_per_split))
    summary = {
        'model_checkpoint': str(args.checkpoint),
        'model_epoch': checkpoint.get('epoch'),
        'fixed_threshold': threshold,
        'normalization_db_min': stored_min.tolist(),
        'normalization_db_max': stored_max.tolist(),
        'device': device,
        'note': 'No model fitting. Bolivia is one held-out geographic event. Official test and training contain chips from shared event sites. Neither is Thailand external validation.',
        'results': results
    }
    (args.output_dir/'evaluation_summary.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=True))
    write_csv(args.output_dir/'evaluation_summary.csv', [
        {'split': r['split'], 'n_images': r['n_images'], **r['micro_metrics']}
        for r in results],
        ['split', 'n_images', 'iou', 'f1', 'precision', 'recall', 'accuracy',
         'water_fraction_gt', 'water_fraction_pred', 'brier_score'])
    print('\nSaved:', args.output_dir/'evaluation_summary.csv')
    print('Saved:', args.output_dir/'evaluation_summary.json')
    print('Saved per-image/per-site CSV and preview PNGs in:', args.output_dir)
    print('NOTE: Do not select a new threshold using these test results.')


if __name__ == '__main__':
    main()
