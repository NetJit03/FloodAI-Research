"""Inspect locally downloaded Sen1Floods11 v1.1 hand-labeled data.
Place this script in the FloodAI-Research project root and run:
    python check_sen1floods11.py
"""
from collections import Counter
from pathlib import Path
import csv

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data' / 'sen1floods11'
SAR = DATA / 'S1Hand'
LABEL = DATA / 'LabelHand'
SPLITS = DATA / 'splits'


def ids(folder: Path, suffix: str) -> set[str]:
    return {p.name.removesuffix(suffix) for p in folder.glob(f'*{suffix}')}


def main() -> None:
    if not (SAR.is_dir() and LABEL.is_dir() and SPLITS.is_dir()):
        raise SystemExit(f'Missing data folders. Expected {DATA}')

    sar_ids = ids(SAR, '_S1Hand.tif')
    label_ids = ids(LABEL, '_LabelHand.tif')
    shared_ids = sorted(sar_ids & label_ids)

    print('=== FILE PAIRING ===')
    print('SAR images:', len(sar_ids))
    print('Label images:', len(label_ids))
    print('Matched SAR/Label pairs:', len(shared_ids))
    print('SAR without labels:', len(sar_ids - label_ids))
    print('Labels without SAR:', len(label_ids - sar_ids))
    if not shared_ids:
        raise SystemExit('No matching pairs. Check file names and folders.')
    print('\n=== SPLIT FILES ===')
    for split_path in sorted(SPLITS.glob('*.csv')):
        with split_path.open(newline='', encoding='utf-8-sig') as f:
            rows = [r for r in csv.reader(f) if any(x.strip() for x in r)]
        print(f'\n{split_path.name}: {len(rows)} nonempty rows')
        for row in rows[:2]:
            print('  sample row:', row)

    print('\n=== IMAGE / LABEL CONTENT ===')
    sample_id = shared_ids[0]
    with rasterio.open(SAR / f'{sample_id}_S1Hand.tif') as src:
        image = src.read()
        print('SAR shape (bands, H, W):', image.shape)
        print('SAR dtype:', image.dtype, '| CRS:', src.crs)
        print('SAR bounds:', src.bounds)
    with rasterio.open(LABEL / f'{sample_id}_LabelHand.tif') as src:
        label = src.read(1)
        print('Label shape (H, W):', label.shape)
        print('Label dtype:', label.dtype, '| CRS:', src.crs)
    uniques, counts = np.unique(label, return_counts=True)
    print('Label values/counts:', dict(zip(uniques.tolist(), counts.tolist())))
    print('Approx. source locations by filename prefix:', dict(Counter(k.split('_')[0] for k in shared_ids)))
    valid = np.isin(label, [0, 1])
    if valid.any():
        print(f'Water fraction among labeled pixels: {(label[valid] == 1).mean():.2%}')

    fig, ax = plt.subplots(1, 3, figsize=(12, 4))
    for band, name, a in zip(image[:2], ['VV (dB)', 'VH (dB)'], ax[:2]):
        finite = band[np.isfinite(band)]
        if finite.size:
            lo, hi = np.percentile(finite, [2, 98])
            a.imshow(band, cmap='gray', vmin=float(lo), vmax=float(hi) if hi > lo else float(lo + 1))
        a.set_title(name)
        a.axis('off')
    cmap = ListedColormap(['#d9d9d9', '#087cbb'])
    cmap.set_bad('#f0a54b')
    ax[2].imshow(np.ma.masked_where(~valid, label), cmap=cmap, vmin=0, vmax=1, interpolation='nearest')
    ax[2].set_title('Ground truth (gray=land, blue=water)')
    ax[2].axis('off')
    fig.suptitle(sample_id, fontsize=11)
    fig.tight_layout()
    out = ROOT / 'results' / 'figures' / 'first_sen1floods11_sample.png'
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=160, bbox_inches='tight')
    plt.close(fig)
    print('\nSaved preview:', out)
    print('Orange = ignore / no data.')


if __name__ == '__main__':
    main()
