#!/usr/bin/env python3
"""Thailand pilot inference with a frozen Sen1Floods11 SAR-only checkpoint.

Purpose: visualise P(water) and measure how much UNOSAT flood reference is
classified as water. UNOSAT flood/non-flood labels are NOT the same target as
Sen1Floods11 water/non-water labels; this script deliberately does not compute
IoU/precision/accuracy against UNOSAT as if it were equivalent ground truth.

Run from FloodAI-Research root, alongside train_sar_unet.py:
    python evaluate_thailand_pilot.py \
      --checkpoint results/sar_unet_baseline_v1/best_sar_unet.pt

Requirements: torch, rasterio, numpy, matplotlib.
"""
from __future__ import annotations
from train_sar_unet import SmallUNet
from rasterio.transform import guard_transform
import torch
import rasterio
import numpy as np
import matplotlib.pyplot as plt

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')


def get_device(requested):
    if requested != 'auto':
        if requested == 'mps' and not torch.backends.mps.is_available():
            raise RuntimeError('MPS not available in this environment')
        return requested
    if torch.backends.mps.is_available():
        return 'mps'
    return 'cuda' if torch.cuda.is_available() else 'cpu'


def read_mask_aligned(path, raster):
    with rasterio.open(path) as src:
        if (src.width, src.height) != (raster.width, raster.height):
            raise ValueError(
                f'{path}: shape differs from SAR; align grids first')
        if src.crs != raster.crs or not src.transform.almost_equals(raster.transform):
            raise ValueError(
                f'{path}: CRS or transform differs from SAR; align grids first')
        return src.read(1)


def starts(length, tile, step):
    if length <= tile:
        return [0]
    seq = list(range(0, length - tile + 1, step))
    last = length - tile
    if seq[-1] != last:
        seq.append(last)
    return seq


@torch.inference_mode()
def infer_tiled(model, input_img, valid_img, tile_size, overlap, device):
    if tile_size <= overlap or tile_size % 16:
        raise ValueError('tile_size must be > overlap and divisible by 16')
    _, h, w = input_img.shape
    pad_y = max(0, tile_size - h)
    pad_x = max(0, tile_size - w)
    x = np.pad(input_img, ((0, 0), (0, pad_y), (0, pad_x)), mode='reflect')
    mask = np.pad(valid_img, ((0, pad_y), (0, pad_x)),
                  mode='constant', constant_values=False)
    _, hh, ww = x.shape
    win = np.outer(np.hanning(tile_size), np.hanning(
        tile_size)).astype(np.float32)
    win = 0.05 + 0.95 * win  # positive weights at outer image boundaries
    sums = np.zeros((hh, ww), dtype=np.float32)
    weights = np.zeros((hh, ww), dtype=np.float32)
    n_tiles = 0
    step = tile_size - overlap
    for top in starts(hh, tile_size, step):
        for left in starts(ww, tile_size, step):
            if not mask[top:top+tile_size, left:left+tile_size].any():
                continue
            patch = np.ascontiguousarray(
                x[:, top:top+tile_size, left:left+tile_size])
            logits = model(torch.from_numpy(patch[None]).to(device))
            p = torch.sigmoid(logits)[0, 0].cpu().numpy()
            sums[top:top+tile_size, left:left+tile_size] += p * win
            weights[top:top+tile_size, left:left+tile_size] += win
            n_tiles += 1
    probs = np.full((h, w), np.nan, dtype=np.float32)
    ok = valid_img & (weights[:h, :w] > 0)
    probs[ok] = sums[:h, :w][ok] / weights[:h, :w][ok]
    return probs, n_tiles


def save_tif(path, array, src_profile, *, nodata, dtype):
    profile = src_profile.copy()
    profile.update(driver='GTiff', count=1, dtype=dtype, nodata=nodata,
                   compress='deflate', predictor=3 if dtype == 'float32' else 1)
    with rasterio.open(path, 'w', **profile) as dst:
        dst.write(array.astype(dtype), 1)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkpoint', type=Path,
                   default=Path('results/sar_unet_baseline_v1/best_sar_unet.pt'))
    p.add_argument('--sar', type=Path, default=Path(
        'data/thailand_external/2021_10_05/sar/Thailand_S1_VV_VH_Sigma0dB.tif'))
    p.add_argument('--reference', type=Path, default=Path(
        'data/thailand_external/2021_10_05/masks/thailand_flood_reference.tif'))
    p.add_argument('--valid-mask', type=Path, default=Path(
        'data/thailand_external/2021_10_05/masks/thailand_valid_mask.tif'))
    p.add_argument('--diagnostic-valid-mask', type=Path, default=Path(
        'data/thailand_external/2021_10_05/masks/thailand_valid_excluding_jrc_permanent.tif'))
    p.add_argument('--output-dir', type=Path,
                   default=Path('results/sar_unet_baseline_v1/thailand_pilot'))
    p.add_argument('--tile-size', type=int, default=256)
    p.add_argument('--overlap', type=int, default=64)
    p.add_argument(
        '--device', choices=['auto', 'mps', 'cpu', 'cuda'], default='auto')
    a = p.parse_args()
    device = get_device(a.device)
    checkpoint = torch.load(
        a.checkpoint, map_location='cpu', weights_only=True)
    if checkpoint.get('architecture') != 'SmallUNet':
        raise ValueError('Checkpoint is not SmallUNet')
    model = SmallUNet(base=int(checkpoint['base_channels']))
    model.load_state_dict(checkpoint['model_state'], strict=True)
    model = model.to(device).eval()
    threshold = float(checkpoint['threshold'])
    db_min = np.asarray(checkpoint['db_min'], dtype=np.float32)[:, None, None]
    db_max = np.asarray(checkpoint['db_max'], dtype=np.float32)[:, None, None]

    with rasterio.open(a.sar) as src:
        if src.count != 2:
            raise ValueError(f'Expected 2 SAR bands VV,VH; found {src.count}')
        sar = src.read(out_dtype='float32')
        valid_image = (src.read_masks(1) > 0) & (
            src.read_masks(2) > 0) & np.isfinite(sar).all(axis=0)
        if src.nodata is not None and np.isfinite(src.nodata):
            valid_image &= np.all(sar != src.nodata, axis=0)
        profile = src.profile.copy()
        reference = read_mask_aligned(a.reference, src)
        valid_reference = read_mask_aligned(a.valid_mask, src).astype(bool)
        if a.diagnostic_valid_mask.is_file():
            valid_excl = read_mask_aligned(
                a.diagnostic_valid_mask, src).astype(bool)
        else:
            valid_excl = None

    x = np.nan_to_num(sar, nan=-40.0, posinf=5.0, neginf=-40.0)
    x = (np.clip(x, db_min, db_max)-db_min)/(db_max-db_min)
    x[:, ~valid_image] = 0
    probs, n_tiles = infer_tiled(
        model, x, valid_image, a.tile_size, a.overlap, device)
    pred = (probs >= threshold) & valid_image
    a.output_dir.mkdir(parents=True, exist_ok=True)
    save_tif(a.output_dir/'thailand_water_probability.tif',
             np.where(valid_image, probs, -9999.0), profile, nodata=-9999, dtype='float32')
    save_tif(a.output_dir/'thailand_predicted_water_mask.tif',
             np.where(valid_image, pred.astype(np.uint8), 255), profile, nodata=255, dtype='uint8')

    def diagnosis(mask, name):
        valid = (mask & valid_image & np.isin(reference, [0, 1]))
        flooded = valid & (reference == 1)
        non_flooded = valid & (reference == 0)
        return {'name': name,
                'reference_valid_pixels': int(valid.sum()),
                'unosat_flood_pixels': int(flooded.sum()),
                'flood_reference_detection_rate': float(pred[flooded].mean()) if flooded.any() else None,
                'predicted_water_fraction_in_nonflood_reference': float(pred[non_flooded].mean()) if non_flooded.any() else None,
                'predicted_water_fraction_in_valid_area': float(pred[valid].mean()) if valid.any() else None}
    report = {'checkpoint': str(a.checkpoint), 'sar': str(a.sar), 'device': device,
              'epoch': checkpoint.get('epoch'), 'threshold_from_checkpoint': threshold,
              'tiles_inferred': n_tiles, 'sar_valid_pixels': int(valid_image.sum()),
              'notes': ['Model predicts all surface water; UNOSAT labels detected flood only.',
                        'Agreement is a diagnostic, not validated accuracy/IoU or a fair cross-country comparison.',
                        'No weights or thresholds were tuned using Thailand.'],
              'diagnostics': [diagnosis(valid_reference, 'original_unosat_valid_mask')]}
    if valid_excl is not None:
        report['diagnostics'].append(
            diagnosis(valid_excl, 'excluding_jrc_2020_permanent_and_nodata'))
    (a.output_dir/'thailand_pilot_diagnostics.json').write_text(json.dumps(report,
                                                                           indent=2, ensure_ascii=False))

    # 4 panels without inventing independent ground truth.
    vv = np.ma.masked_where(~valid_image, sar[0])
    refviz = np.ma.masked_where(
        ~valid_reference, np.where(reference == 1, 1, 0))
    pm = np.ma.masked_where(~valid_image, probs)
    overlay = np.zeros((*pred.shape, 4), dtype=np.float32)
    overlay[valid_image & pred] = (
        0.0, 0.65, 0.9, 0.4)  # predicted surface water
    overlay[valid_reference & (reference == 1)] = (
        1.0, 0.35, 0.1, 0.55)  # UNOSAT flood
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    axes[0, 0].imshow(vv, cmap='gray', vmin=-25, vmax=0)
    axes[0, 0].set_title('Sentinel-1 VV (dB)')
    axes[0, 1].imshow(refviz, cmap='Blues', vmin=0, vmax=1)
    axes[0, 1].set_title('UNOSAT detected-flood reference')
    im = axes[1, 0].imshow(pm, cmap='viridis', vmin=0, vmax=1)
    axes[1, 0].set_title('Model P(surface water)')
    fig.colorbar(im, ax=axes[1, 0], fraction=.046, pad=.04)
    axes[1, 1].imshow(vv, cmap='gray', vmin=-25, vmax=0)
    axes[1, 1].imshow(overlay)
    axes[1, 1].set_title('Blue=model water; orange=UNOSAT flood')
    for ax in axes.flat:
        ax.set_xticks([])
        ax.set_yticks([])
    fig.suptitle(
        'Thailand pilot: diagnostic comparison only (NOT comparable ground truth)', fontsize=12)
    fig.tight_layout()
    fig.savefig(a.output_dir/'thailand_pilot_comparison.png',
                dpi=130, bbox_inches='tight')
    plt.close(fig)

    print('Checkpoint:', a.checkpoint)
    print('Checkpoint epoch:', checkpoint.get('epoch'),
          '| device:', device, '| fixed threshold:', threshold)
    print('Tiling:', a.tile_size, 'overlap:',
          a.overlap, 'tiles used:', n_tiles)
    print('SAR valid pixels:', int(valid_image.sum()))
    for d in report['diagnostics']:
        print('\n', d['name'])
        for k, v in d.items():
            if k != 'name':
                print(' ', k, ':', v)
    print('\nSaved outputs to:', a.output_dir)
    print('IMPORTANT: These are DIAGNOSTIC reference-agreement measures, NOT Water-IoU or Flood-IoU.')


if __name__ == '__main__':
    main()
