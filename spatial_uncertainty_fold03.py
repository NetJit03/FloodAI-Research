#!/usr/bin/env python3
"""M6.4B retrospective spatial diagnostics of a FIXED Fold-3 SAR U-Net.

No fitting, threshold tuning, or evaluation-driven model selection occurs.
Run from the FloodAI-Research project root beside train_sar_unet.py.
"""
from __future__ import annotations
from train_sar_unet import SarWaterDataset, SmallUNet, DB_MIN, DB_MAX, split_records
import torch
import numpy as np
from matplotlib.patches import Patch
from matplotlib.colors import ListedColormap, BoundaryNorm
import matplotlib.pyplot as plt

import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use('Agg')


def args_parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkpoint', type=Path,
                   default=Path('results/event_level_v1/fold_03_ghana/best_sar_unet.pt'))
    p.add_argument('--data-root', type=Path,
                   default=Path('data/sen1floods11/event_level_roots/fold_03_ghana'))
    p.add_argument('--split', choices=['valid', 'test'], default='test')
    p.add_argument('--stems', nargs='+',
                   default=['Ghana_868803', 'Ghana_1033830', 'Ghana_313799'])
    p.add_argument('--output-dir', type=Path,
                   default=Path('results/event_level_v1/spatial_uncertainty_fold03'))
    p.add_argument(
        '--device', choices=['auto', 'mps', 'cuda', 'cpu'], default='auto')
    return p.parse_args()


def device_choice(preference):
    if preference == 'auto':
        return 'mps' if torch.backends.mps.is_available() else ('cuda' if torch.cuda.is_available() else 'cpu')
    if preference == 'mps' and not torch.backends.mps.is_available():
        raise RuntimeError('MPS was requested but is not available')
    if preference == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('CUDA was requested but is not available')
    return preference


def mask_plot(ax, data, valid, **kwargs):
    return ax.imshow(np.ma.masked_where(~valid, data), interpolation='nearest', **kwargs)


def save_visualization(path, stem, vv, truth, valid, prob, pred, entropy, low_confident_fn, threshold):
    fig, axs = plt.subplots(2, 3, figsize=(15, 10), constrained_layout=True)
    fig.suptitle(
        f'{stem} | fixed checkpoint, threshold={threshold:.2f} | diagnostics only', fontsize=13)

    ax = axs[0, 0]
    mask_plot(ax, vv, valid, cmap='gray', vmin=0, vmax=1)
    ax.set_title('Normalized Sentinel-1 VV (input)')

    ax = axs[0, 1]
    cmap_gt = ListedColormap(['#d0d6dc', '#1584c5'])
    mask_plot(ax, truth.astype(np.uint8), valid,
              cmap=cmap_gt, vmin=-.5, vmax=1.5)
    ax.set_title('Ground truth: land=gray, water=blue')

    ax = axs[0, 2]
    im = mask_plot(ax, prob, valid, cmap='viridis', vmin=0, vmax=1)
    fig.colorbar(im, ax=ax, fraction=.045, pad=.03)
    ax.set_title('Predicted P(water)')

    ax = axs[1, 0]
    im = mask_plot(ax, entropy, valid, cmap='magma', vmin=0, vmax=1)
    fig.colorbar(im, ax=ax, fraction=.045, pad=.03)
    ax.set_title('Binary predictive entropy (normalized)')

    ax = axs[1, 1]
    confusion = np.zeros_like(prob, dtype=np.uint8)  # TN
    confusion[valid & pred & truth] = 1                # TP
    confusion[valid & pred & ~truth] = 2               # FP
    confusion[valid & ~pred & truth] = 3               # FN
    cmap_confusion = ListedColormap(
        ['#cad2da', '#12a45c', '#f0444a', '#f6b600'])
    norm = BoundaryNorm(np.arange(-.5, 4.5), cmap_confusion.N)
    mask_plot(ax, confusion, valid, cmap=cmap_confusion, norm=norm)
    ax.legend(handles=[Patch(color=c, label=s) for c, s in [
        ('#cad2da', 'TN'), ('#12a45c', 'TP'), ('#f0444a', 'FP'), ('#f6b600', 'FN')
    ]], ncol=4, loc='lower center', bbox_to_anchor=(.5, -.15), fontsize=9)
    ax.set_title('Confusion map at fixed threshold')

    ax = axs[1, 2]
    mask_plot(ax, vv, valid, cmap='gray', vmin=0, vmax=1)
    overlay = np.ma.masked_where(~low_confident_fn, np.ones_like(prob))
    ax.imshow(overlay, cmap=ListedColormap(
        ['#ffe300']), vmin=.5, vmax=1.5, alpha=.82, interpolation='nearest')
    ax.set_title('Ground-truth water with P(water) < 0.1')

    for ax in axs.flat:
        ax.set_xticks([])
        ax.set_yticks([])
    fig.savefig(path, dpi=175, bbox_inches='tight')
    plt.close(fig)


def main():
    a = args_parser()
    if not a.checkpoint.is_file():
        raise FileNotFoundError(f'Missing checkpoint: {a.checkpoint}')
    device = device_choice(a.device)
    ckpt = torch.load(a.checkpoint, map_location='cpu', weights_only=True)
    if ckpt.get('architecture') != 'SmallUNet':
        raise ValueError('Checkpoint architecture is not SmallUNet')
    mins = np.asarray(ckpt.get('db_min', [-35, -40]), dtype=float).ravel()
    maxs = np.asarray(ckpt.get('db_max', [5, 0]), dtype=float).ravel()
    if not np.allclose(mins, np.asarray(DB_MIN).ravel()) or not np.allclose(maxs, np.asarray(DB_MAX).ravel()):
        raise ValueError(
            'Checkpoint normalization differs from train_sar_unet.py')
    threshold = float(ckpt.get('threshold', .5))
    if not 0 < threshold < 1:
        raise ValueError('Invalid saved threshold')

    model = SmallUNet(int(ckpt['base_channels']))
    model.load_state_dict(ckpt['model_state'], strict=True)
    model.to(device).eval()

    records = split_records(a.data_root, a.split)
    if not records:
        raise ValueError('No split records found')
    dataset = SarWaterDataset(records, augment=False)
    stems = set(a.stems)
    indices = [i for i, (path, *_rest) in enumerate(records)
               if Path(path).name.removesuffix('_S1Hand.tif') in stems]
    found = {Path(records[i][0]).name.removesuffix(
        '_S1Hand.tif') for i in indices}
    missing = sorted(stems - found)
    if missing:
        raise ValueError(f'Requested stems not found in {a.split} split: {missing}. Available examples: '
                         f'{[Path(r[0]).name for r in records[:5]]}')

    a.output_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    print(f'Checkpoint: {a.checkpoint}\nSelected epoch: {ckpt.get("epoch")}\nSplit: {a.split}; '
          f'Device: {device}; fixed threshold: {threshold}; selected images: {len(indices)}')
    print('NO fitting, recalibration, or threshold selection.')
    with torch.inference_mode():
        for i in indices:
            stem = Path(records[i][0]).name.removesuffix('_S1Hand.tif')
            x, y, v = dataset[i]
            valid = v.numpy()[0].astype(bool)
            truth = y.numpy()[0] > .5
            if not valid.any():
                print(f'SKIP {stem}: no evaluable pixels')
                continue
            logits = model(x.unsqueeze(0).to(device))
            prob = torch.sigmoid(logits)[0, 0].detach().cpu().numpy()
            if prob.shape != valid.shape:
                raise ValueError(f'Output and label grids differ: {stem}')
            pred = prob >= threshold
            p_safe = np.clip(prob, 1e-7, 1 - 1e-7)
            entropy = -(p_safe * np.log2(p_safe) +
                        (1 - p_safe) * np.log2(1 - p_safe))
            fn = valid & truth & ~pred
            high_conf_fn = fn & (prob < .1)
            n_water = int((valid & truth).sum())
            n_fn = int(fn.sum())
            save_visualization(a.output_dir / f'{stem}_spatial_uncertainty.png', stem,
                               x[0].numpy(), truth, valid, prob, pred, entropy,
                               high_conf_fn, threshold)
            row = dict(split=a.split, image=stem, valid_pixels=int(valid.sum()),
                       ground_truth_water_pixels=n_water, false_negative_pixels=n_fn,
                       fn_p_below_0_1=int(high_conf_fn.sum()),
                       share_fn_p_below_0_1=(
                           int(high_conf_fn.sum()) / n_fn if n_fn else float('nan')),
                       share_water_missed_p_below_0_1=(
                           int(high_conf_fn.sum()) / n_water if n_water else float('nan')),
                       mean_entropy_valid=float(entropy[valid].mean()),
                       mean_entropy_fn=(float(entropy[fn].mean()) if n_fn else float('nan')))
            rows.append(row)
            print(f'{stem}: GT water={n_water}; FN={n_fn}; FN with P<0.1={row["fn_p_below_0_1"]}; '
                  f'FN fraction P<0.1={row["share_fn_p_below_0_1"]:.2%}; saved map')

    if not rows:
        raise RuntimeError('No images were analyzed')
    path = a.output_dir / 'spatial_uncertainty_selected_images.csv'
    with path.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f'Saved summary: {path}')
    print('Reminder: entropy close to 0 can mean either high confidence correct OR high confidence incorrect.')
    print('These are retrospective test diagnostics, not grounds to tune using Ghana.')


if __name__ == '__main__':
    main()
