"""Check JRC 2020 water classes against Thailand UNOSAT flood-reference masks.
Run in FloodAI-Research root: python check_thailand_jrc_alignment.py
Does NOT overwrite the original reference or validity masks.
"""
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import rasterio
from rasterio.warp import reproject, Resampling
from matplotlib.colors import ListedColormap, BoundaryNorm

ROOT = Path('data/thailand_external/2021_10_05')
MASKS = ROOT / 'masks'
JRC_FILE = MASKS / 'Phimai_JRC2020_WaterClass.tif'
REFERENCE_FILE = MASKS / 'thailand_flood_reference.tif'
VALID_FILE = MASKS / 'thailand_valid_mask.tif'

if not JRC_FILE.exists():
    alternatives = list(ROOT.rglob('*JRC*WaterClass*.tif'))
    if len(alternatives) == 1:
        JRC_FILE = alternatives[0]
    else:
        raise FileNotFoundError(
            f'Cannot find {JRC_FILE}. Move the downloaded JRC GeoTIFF there, '
            f'or inspect these candidates: {alternatives}'
        )
for p in [REFERENCE_FILE, VALID_FILE]:
    if not p.exists():
        raise FileNotFoundError(f'Missing file: {p}')

with rasterio.open(REFERENCE_FILE) as r, rasterio.open(VALID_FILE) as v:
    if r.crs != v.crs or r.transform != v.transform or r.shape != v.shape:
        raise ValueError(
            'UNOSAT reference and validity mask are not on same grid')
    ref = r.read(1)
    valid = v.read(1).astype(bool) & (ref != 255)
    profile = r.profile.copy()
    dst_transform, dst_crs = r.transform, r.crs
    dst_shape = r.shape

with rasterio.open(JRC_FILE) as src:
    if src.crs is None:
        raise ValueError('JRC image missing CRS; cannot align')
    jrc = np.zeros(dst_shape, dtype=np.uint8)
    reproject(
        source=rasterio.band(src, 1), destination=jrc,
        src_transform=src.transform, src_crs=src.crs,
        dst_transform=dst_transform, dst_crs=dst_crs,
        src_nodata=src.nodata, dst_nodata=0,
        resampling=Resampling.nearest,
    )
    print('JRC source shape:', src.shape,
          '| resolution:', src.res, '| CRS:', src.crs)

print('Reference grid:', dst_shape, '| CRS:', dst_crs)
print('Original valid pixels:', int(valid.sum()))
print('Original flood pixels:', int(((ref == 1) & valid).sum()))

names = {0: 'No data',
         1: 'Not water (2020)', 2: 'Seasonal (2020)', 3: 'Permanent (2020)'}
print('\nJRC/UNOSAT OVERLAP — among original valid pixels')
for c, name in names.items():
    selected = valid & (jrc == c)
    n = int(selected.sum())
    flood_n = int((selected & (ref == 1)).sum())
    print(f'JRC {c} {name}: {n:,} pixels; UNOSAT flood overlap: {flood_n:,}')

# Diagnostic-only mask; this is NOT a new ground-truth classification.
eval_valid = valid & (jrc != 0) & (jrc != 3)
print('\nAfter excluding JRC NoData and 2020 permanent water (diagnostic):')
print('  valid pixels:', int(eval_valid.sum()))
print('  flood pixels:', int((eval_valid & (ref == 1)).sum()))
print('  excluded pixels:', int((valid & ~eval_valid).sum()))

out_profile = profile.copy()
out_profile.update(driver='GTiff', count=1, dtype='uint8',
                   compress='lzw', nodata=0)
with rasterio.open(MASKS / 'jrc2020_on_sar_grid.tif', 'w', **out_profile) as ds:
    ds.write(jrc, 1)
with rasterio.open(MASKS / 'thailand_valid_excluding_jrc_permanent.tif', 'w', **out_profile) as ds:
    ds.write(eval_valid.astype('uint8'), 1)

sar_paths = sorted((ROOT / 'sar').glob('*.tif'))
if sar_paths:
    with rasterio.open(sar_paths[0]) as s:
        if s.shape == dst_shape and s.transform == dst_transform and s.crs == dst_crs:
            vv = s.read(1).astype('float32')
            vv[~np.isfinite(vv) | (vv <= -999)] = np.nan
        else:
            vv = None
else:
    vv = None

fig, axes = plt.subplots(1, 3, figsize=(15, 5), constrained_layout=True)
if vv is not None:
    axes[0].imshow(vv, cmap='gray', vmin=-25, vmax=0)
    axes[0].set_title('Sentinel-1 VV (dB)')
else:
    axes[0].imshow(valid, cmap='gray')
    axes[0].set_title('Original validity mask')

flood_display = np.ma.masked_where(~valid, ref)
axes[1].imshow(flood_display, cmap=ListedColormap(
    ['#bbbbbb', '#198ed2']), vmin=0, vmax=1)
axes[1].set_title('UNOSAT reference (blue=flood)')

jrc_colors = ['#555555', '#eeeeee', '#70c5ea', '#1d4ed8']
axes[2].imshow(jrc, cmap=ListedColormap(jrc_colors),
               norm=BoundaryNorm([-0.5, 0.5, 1.5, 2.5, 3.5], 4))
axes[2].contour((ref == 1) & valid, levels=[0.5],
                colors=['#e34c43'], linewidths=0.6)
axes[2].set_title('JRC 2020 (blue=water) + UNOSAT flood outline')
for ax in axes:
    ax.axis('off')

output = Path('results/figures/thailand_jrc_2020_overlap.png')
output.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(output, dpi=160)
plt.close(fig)
print('\nSaved figure:', output)
print('Saved aligned JRC:', MASKS / 'jrc2020_on_sar_grid.tif')
print('Saved diagnostic mask:', MASKS /
      'thailand_valid_excluding_jrc_permanent.tif')
print('NOTE: do not treat UNOSAT flood labels as full surface-water ground truth.')
