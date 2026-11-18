#!/usr/bin/env python3
"""Train a small SAR-only U-Net on Sen1Floods11 hand-labeled data.

Design:
- Loads GeoTIFFs lazily, safe for laptops with 8 GB unified memory.
- Official train/valid splits; Bolivia and official test NEVER used to fit/tune.
- Train on random 256-pixel crops at native pixel resolution.
- Validate on full-resolution (512x512) images, batch size 1.
- Ignore label -1 and invalid SAR pixels in loss and metrics.
- Apply the SAME fixed channel-wise dB normalization at inference.

Run:
  python train_sar_unet.py --check-only
  python train_sar_unet.py --epochs 1 --max-train 12 --max-val 6
  python train_sar_unet.py --epochs 25 --batch-size 2 --crop-size 256

No external data is uploaded by this script.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from collections import Counter
from pathlib import Path

import numpy as np
import rasterio
import torch
from torch import nn
from torch.nn import functional as F
from torch.utils.data import Dataset, DataLoader

# Preset transform (Sigma0 dB) to be reused verbatim at inference.
# This is a STARTING preset, not a train-optimized normalizer.
DB_MIN = np.array([-35.0, -40.0], dtype=np.float32)[:, None, None]   # VV, VH
DB_MAX = np.array([5.0, 0.0], dtype=np.float32)[:, None, None]


def split_records(root: Path, split: str) -> list[tuple[Path, Path, str]]:
    csv_path = root / 'splits' / f'flood_{split}_data.csv'
    if not csv_path.is_file():
        raise FileNotFoundError(f'Missing split: {csv_path}')
    rows = []
    with csv_path.open(newline='') as f:
        for line in csv.reader(f):
            if not line:
                continue
            if len(line) < 2:
                raise ValueError(f'Bad CSV row in {csv_path}: {line}')
            image = root / 'S1Hand' / line[0].strip()
            label = root / 'LabelHand' / line[1].strip()
            if not image.is_file() or not label.is_file():
                raise FileNotFoundError(
                    f'Missing SAR or label in {csv_path}: {image}, {label}')
            if not image.name.endswith('_S1Hand.tif') or not label.name.endswith('_LabelHand.tif'):
                raise ValueError(
                    f'Unexpected filenames in {csv_path}: {image.name}, {label.name}')
            if image.name.replace('_S1Hand.tif', '') != label.name.replace('_LabelHand.tif', ''):
                raise ValueError(
                    f'Unmatched image/label: {image.name}, {label.name}')
            rows.append((image, label, image.name.split('_')[0]))
    return rows


def inspect_splits(root: Path):
    splits = {n: split_records(root, n)
              for n in ('train', 'valid', 'test', 'bolivia')}
    for name, rows in splits.items():
        counts = dict(Counter(r[2] for r in rows))
        print(f'{name:>7}: {len(rows):>3} files | sites: {counts}')
    names = {s: {r[0].name for r in rows} for s, rows in splits.items()}
    for i, s1 in enumerate(names):
        for s2 in list(names)[i+1:]:
            overlap = names[s1] & names[s2]
            if overlap:
                raise RuntimeError(
                    f'LEAKAGE: {s1} and {s2} have {len(overlap)} duplicated chips')
    print('PASS: No duplicate SAR chips across official CSV splits.')
    print('NOTE: Different chips from the same flood event can still occur across train/valid/test.')
    img_path, lab_path, _ = splits['train'][0]
    with rasterio.open(img_path) as src:
        print('Example SAR:', img_path.name, 'shape=',
              (src.count, src.height, src.width), 'dtype=', src.dtypes)
        if src.count != 2:
            raise ValueError('Expected VV and VH as 2 bands, in this order')
    with rasterio.open(lab_path) as src:
        lab = src.read(1)
        vals = np.unique(lab)
        print('Example label:', lab_path.name, 'shape=',
              lab.shape, 'unique=', vals.tolist())
        if not set(vals.tolist()).issubset({-1, 0, 1}):
            raise ValueError('Unexpected label values outside -1, 0, 1')
    return splits


class SarWaterDataset(Dataset):
    def __init__(self, records, crop_size=256, augment=False):
        self.records = list(records)
        self.crop_size = crop_size if augment else None
        self.augment = augment

    def __len__(self):
        return len(self.records)

    def __getitem__(self, idx):
        image_path, label_path, _event = self.records[idx]
        with rasterio.open(image_path) as src:
            if src.count != 2:
                raise ValueError(f'Not two bands: {image_path}')
            x = src.read(out_dtype=np.float32)
            valid_image = np.isfinite(x).all(axis=0)
            if src.nodata is not None and np.isfinite(src.nodata):
                valid_image &= np.all(x != src.nodata, axis=0)
        with rasterio.open(label_path) as src:
            y = src.read(1).astype(np.int16)
        if y.shape != x.shape[-2:]:
            raise ValueError(
                f'Image and label shapes differ: {image_path}, {label_path}')
        if not np.isin(y, (-1, 0, 1)).all():
            raise ValueError(f'Label has unexpected codes: {label_path}')
        valid = (y != -1) & valid_image
        # Normalize fixed dB ranges. Invalid SAR values map to zero after masking.
        x = np.nan_to_num(x, nan=-40.0, posinf=5.0, neginf=-40.0)
        x = np.clip(x, DB_MIN, DB_MAX)
        x = (x-DB_MIN)/(DB_MAX-DB_MIN)
        x[:, ~valid_image] = 0.0
        target = (y == 1).astype(np.float32)

        if self.augment:
            _, h, w = x.shape
            k = self.crop_size
            if min(h, w) < k:
                raise ValueError(f'Crop {k} larger than SAR tile {h}x{w}')
            r = random.randint(0, h-k)
            c = random.randint(0, w-k)
            x = x[:, r:r+k, c:c+k]
            target = target[r:r+k, c:c+k]
            valid = valid[r:r+k, c:c+k]
            if random.random() < .5:
                x = np.flip(x, axis=2)
                target = np.flip(target, axis=1)
                valid = np.flip(valid, axis=1)
            if random.random() < .5:
                x = np.flip(x, axis=1)
                target = np.flip(target, axis=0)
                valid = np.flip(valid, axis=0)
            rotation = random.randint(0, 3)
            x = np.rot90(x, rotation, axes=(1, 2))
            target = np.rot90(target, rotation)
            valid = np.rot90(valid, rotation)
        return (torch.from_numpy(np.ascontiguousarray(x)),
                torch.from_numpy(np.ascontiguousarray(target[None])),
                torch.from_numpy(np.ascontiguousarray(valid[None])))


def conv_block(c_in, c_out):
    return nn.Sequential(nn.Conv2d(c_in, c_out, 3, padding=1, bias=False),
                         nn.GroupNorm(4, c_out), nn.ReLU(inplace=True),
                         nn.Conv2d(c_out, c_out, 3, padding=1, bias=False),
                         nn.GroupNorm(4, c_out), nn.ReLU(inplace=True))


class SmallUNet(nn.Module):
    def __init__(self, base=16):
        super().__init__()
        if base % 4:
            raise ValueError('base must be divisible by 4')
        b = base
        self.e1 = conv_block(2, b)
        self.e2 = conv_block(b, 2*b)
        self.e3 = conv_block(2*b, 4*b)
        self.e4 = conv_block(4*b, 8*b)
        self.mid = conv_block(8*b, 16*b)
        self.pool = nn.MaxPool2d(2)
        self.d4 = conv_block(16*b+8*b, 8*b)
        self.d3 = conv_block(8*b+4*b, 4*b)
        self.d2 = conv_block(4*b+2*b, 2*b)
        self.d1 = conv_block(2*b+b, b)
        self.out = nn.Conv2d(b, 1, 1)

    def decode(self, x, skip, block):
        x = F.interpolate(
            x, size=skip.shape[-2:], mode='bilinear', align_corners=False)
        return block(torch.cat((x, skip), dim=1))

    def forward(self, x):
        a = self.e1(x)
        b = self.e2(self.pool(a))
        c = self.e3(self.pool(b))
        d = self.e4(self.pool(c))
        m = self.mid(self.pool(d))
        x = self.decode(m, d, self.d4)
        x = self.decode(x, c, self.d3)
        x = self.decode(x, b, self.d2)
        x = self.decode(x, a, self.d1)
        return self.out(x)


def masked_bce_dice(logits, y, valid):
    valid = valid.to(dtype=logits.dtype)
    n = valid.sum().clamp_min(1.0)
    bce = (F.binary_cross_entropy_with_logits(
        logits, y, reduction='none')*valid).sum()/n
    p = torch.sigmoid(logits)*valid
    t = y*valid
    dice = 1.0-(2.0*(p*t).sum()+1.0)/(p.sum()+t.sum()+1.0)
    return .5*bce+.5*dice


@torch.no_grad()
def evaluate(model, loader, device, threshold=.5):
    model.eval()
    totals = {'tp': 0, 'tn': 0, 'fp': 0, 'fn': 0, 'loss': 0.0, 'batches': 0}
    for x, y, v in loader:
        x, y, v = x.to(device), y.to(device), v.to(device)
        logits = model(x)
        loss = masked_bce_dice(logits, y, v)
        pred = torch.sigmoid(logits) >= threshold
        truth = y >= .5
        valid = v.bool()
        totals['tp'] += int((pred & truth & valid).sum().item())
        totals['tn'] += int((~pred & ~truth & valid).sum().item())
        totals['fp'] += int((pred & ~truth & valid).sum().item())
        totals['fn'] += int((~pred & truth & valid).sum().item())
        totals['loss'] += float(loss.item())
        totals['batches'] += 1
    tp, fp, fn = totals['tp'], totals['fp'], totals['fn']
    union = tp+fp+fn
    totals['iou'] = tp/union if union else float('nan')
    totals['f1'] = (2*tp)/(2*tp+fp+fn) if 2*tp+fp+fn else 1.0
    totals['recall'] = tp/(tp+fn) if tp+fn else float('nan')
    totals['precision'] = tp/(tp+fp) if tp+fp else float('nan')
    totals['loss'] /= max(totals['batches'], 1)
    return totals


def seed_all(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--data-root', type=Path, default=Path('data/sen1floods11'))
    p.add_argument('--output-dir', type=Path, default=Path('results/sar_unet'))
    p.add_argument('--epochs', type=int, default=25)
    p.add_argument('--batch-size', type=int, default=2)
    p.add_argument('--crop-size', type=int, default=256)
    p.add_argument('--base-channels', type=int, default=16)
    p.add_argument('--lr', type=float, default=3e-4)
    p.add_argument('--patience', type=int, default=6)
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--max-train', type=int, default=0,
                   help='Development only: use N training samples')
    p.add_argument('--max-val', type=int, default=0,
                   help='Development only: use N validation samples')
    p.add_argument('--check-only', action='store_true')
    p.add_argument('--device', choices=('auto', 'mps',
                   'cpu', 'cuda'), default='auto')
    a = p.parse_args()
    if a.batch_size < 1 or a.crop_size < 32 or a.epochs < 1:
        p.error('batch-size>=1, crop-size>=32, epochs>=1 required')
    seed_all(a.seed)
    splits = inspect_splits(a.data_root)
    train_recs = splits['train'][:a.max_train] if a.max_train else splits['train']
    val_recs = splits['valid'][:a.max_val] if a.max_val else splits['valid']
    if not train_recs or not val_recs:
        raise RuntimeError('Empty train or validation split')
    if a.check_only:
        x, y, v = SarWaterDataset(
            train_recs, crop_size=a.crop_size, augment=True)[0]
        print('Train sample shapes:', x.shape, y.shape, v.shape)
        print('Train sample valid pixels:', int(v.sum()),
              'water pixels:', int((y.bool() & v).sum()))
        print('PASS: File paths, bands, labels, normalization and data loader sample.')
        return
    if a.device == 'auto':
        device = 'mps' if torch.backends.mps.is_available() else (
            'cuda' if torch.cuda.is_available() else 'cpu')
    else:
        device = a.device
    print('Device:', device)
    if a.max_train or a.max_val:
        print(
            'WARNING: SUBSET RUN — do not report these metrics as final research results.')
    train = DataLoader(SarWaterDataset(train_recs, a.crop_size, True), batch_size=a.batch_size,
                       shuffle=True, num_workers=0, pin_memory=False)
    valid = DataLoader(SarWaterDataset(val_recs, augment=False), batch_size=1,
                       shuffle=False, num_workers=0, pin_memory=False)
    model = SmallUNet(a.base_channels).to(device)
    print('Parameters:', sum(p.numel() for p in model.parameters()))
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=a.lr, weight_decay=1e-4)
    a.output_dir.mkdir(parents=True, exist_ok=True)
    best = -1.0
    bad = 0
    history_path = a.output_dir/'history.csv'
    with history_path.open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['epoch', 'train_loss', 'val_loss',
                        'val_iou', 'val_f1', 'val_recall', 'val_precision'])
        for epoch in range(1, a.epochs+1):
            model.train()
            total = 0.0
            for x, y, v in train:
                x, y, v = x.to(device), y.to(device), v.to(device)
                optimizer.zero_grad(set_to_none=True)
                logits = model(x)
                loss = masked_bce_dice(logits, y, v)
                loss.backward()
                optimizer.step()
                total += float(loss.item())
            train_loss = total/max(len(train), 1)
            metric = evaluate(model, valid, device)
            writer.writerow([epoch, train_loss, metric['loss'], metric['iou'],
                            metric['f1'], metric['recall'], metric['precision']])
            f.flush()
            print(
                f"Epoch {epoch:02d} | train loss {train_loss:.4f} | val loss {metric['loss']:.4f} | IoU {metric['iou']:.4f} | F1 {metric['f1']:.4f} | Recall {metric['recall']:.4f}", flush=True)
            if metric['iou'] > best+1e-5:
                best = metric['iou']
                bad = 0
                ckpt = {'model_state': model.state_dict(),
                        'architecture': 'SmallUNet', 'base_channels': a.base_channels,
                        'db_min': [-35.0, -40.0], 'db_max': [5.0, 0.0],
                        'label_scheme': {'ignore': -1, 'non_water': 0, 'water': 1},
                        'threshold': .5, 'epoch': epoch, 'validation_metrics': metric,
                        'seed': a.seed, 'train_count': len(train_recs), 'valid_count': len(val_recs)}
                torch.save(ckpt, a.output_dir/'best_sar_unet.pt')
            else:
                bad += 1
                if bad >= a.patience:
                    print(
                        f'Early stopping after {a.patience} epochs without improved validation IoU.')
                    break
    config = {**vars(a), 'data_root': str(a.data_root), 'output_dir': str(a.output_dir),
              'device': device, 'db_min': [-35, -40], 'db_max': [5, 0],
              'warning': 'Do not use Thai UNOSAT detected-flood labels as Sen1Floods11 surface-water GT.'}
    (a.output_dir/'run_config.json').write_text(json.dumps(config,
                                                           indent=2, ensure_ascii=False))
    print('Saved best model:', a.output_dir/'best_sar_unet.pt')
    print('Saved history:', history_path)
    print('Best validation IoU:', round(best, 5))
    print('NOTE: This does NOT evaluate Bolivia, official test or Thailand yet.')


if __name__ == '__main__':
    main()
