#!/usr/bin/env python3
"""M8.0A: DEV-VALIDATION-only three-seed Deep Ensemble UQ (Baseline).

Reads ONLY: v2_development_roots/<fold>/splits/flood_train_data.csv,
            v2_development_roots/<fold>/splits/flood_valid_data.csv,
            associated SAR/GT via train_sar_unet.SarWaterDataset,
            and baseline_seed{42,123,777}/<fold>/best_sar_unet.pt.
NEVER loads official TEST, Bolivia, Thailand or their metrics.
No model training, threshold tuning or recalibration.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from train_sar_unet import DB_MAX, DB_MIN, SmallUNet, SarWaterDataset, split_records

SEEDS = (42, 123, 777)
FOLD_INFO = {
    'dev_fold_01_usa': {'event': 'USA', 'train': 174, 'valid': 69},
    'dev_fold_02_sri_lanka': {'event': 'Sri-Lanka', 'train': 201, 'valid': 42},
    'dev_fold_03_spain': {'event': 'Spain', 'train': 213, 'valid': 30},
}
SRI_LANKA_CASES = ('Sri-Lanka_534068', 'Sri-Lanka_845821', 'Sri-Lanka_713926')
EPS = 1e-7


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1_048_576), b''):
            h.update(b)
    return h.hexdigest()


def entropy(p: np.ndarray) -> np.ndarray:
    q = np.clip(np.asarray(p, dtype=np.float64), EPS, 1 - EPS)
    return -(q * np.log(q) + (1 - q) * np.log1p(-q)) / math.log(2.0)


def uncertainty(probabilities: np.ndarray) -> tuple[np.ndarray, ...]:
    """Return pbar, predictive entropy, expected entropy, MI, variance.

    All entropy in bits (binary maximum = 1 bit); variance in raw probability^2.
    probabilities shape: (n_members, H, W).
    """
    if probabilities.ndim != 3 or probabilities.shape[0] < 2:
        raise ValueError('Need >=2 ensemble members of shape [M,H,W]')
    p = probabilities.astype(np.float64, copy=False)
    if not np.isfinite(p).all() or (p < 0).any() or (p > 1).any():
        raise ValueError('Ensemble member probabilities must be finite and in [0,1]')
    pbar = p.mean(axis=0)
    predictive = entropy(pbar)
    expected = entropy(p).mean(axis=0)
    # Jensen inequality guarantees MI >= 0; small negatives are numeric noise.
    mi = np.maximum(predictive - expected, 0.0)
    var = p.var(axis=0, ddof=0)
    return tuple(x.astype(np.float32) for x in (pbar, predictive, expected, mi, var))


def json_safe(value):
    """Replace NaN/Inf with null in a strict JSON audit manifest."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    return value


def safe_ratio(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator else float('nan')


def scores(tp: int, tn: int, fp: int, fn: int) -> dict:
    return {
        'iou': safe_ratio(tp, tp + fp + fn),  # empty union must be NaN
        'f1': safe_ratio(2 * tp, 2 * tp + fp + fn),
        'precision': safe_ratio(tp, tp + fp),
        'recall': safe_ratio(tp, tp + fn),
    }


def choose_device(requested: str) -> str:
    if requested == 'auto':
        if torch.backends.mps.is_available():
            return 'mps'
        return 'cuda' if torch.cuda.is_available() else 'cpu'
    if requested == 'mps' and not torch.backends.mps.is_available():
        raise RuntimeError('MPS requested but not available')
    if requested == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('CUDA requested but not available')
    return requested


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)


def require_frozen_protocol(project_root: Path) -> str:
    path = project_root / 'results/event_level_v2/m70d_protocol_freeze/m70d_frozen_protocol.json'
    if not path.is_file():
        raise FileNotFoundError('Missing M7.0D frozen protocol. Run M7.0D verify before M8.0A.')
    content = json.loads(path.read_text(encoding='utf-8'))
    fp = content.get('fingerprint', '')
    if not isinstance(fp, str) or len(fp) != 64:
        raise ValueError('M7.0D frozen protocol has no valid fingerprint')
    return fp


def validation_records(data_root: Path, fold: str):
    root = data_root / fold
    tr = split_records(root, 'train')
    va = split_records(root, 'valid')
    cfg = FOLD_INFO[fold]
    if len(tr) != cfg['train'] or len(va) != cfg['valid']:
        raise ValueError(f'{fold}: TRAIN/VALID counts do not match frozen protocol')
    tr_events = {r[2] for r in tr}
    va_events = {r[2] for r in va}
    if va_events != {cfg['event']} or cfg['event'] in tr_events:
        raise ValueError(f'{fold}: event leakage or unexpected held-out validation event')
    if {p[0].name for p in tr} & {p[0].name for p in va}:
        raise ValueError(f'{fold}: duplicate chip names across TRAIN and VALID')
    return va


def load_members(project_root: Path, fold: str, device: str):
    models, manifests = [], []
    cfg = FOLD_INFO[fold]
    for seed in SEEDS:
        path = project_root / ('results/event_level_v2/'
                               f'baseline_seed{seed}/{fold}/best_sar_unet.pt')
        if not path.is_file():
            raise FileNotFoundError(f'Missing baseline checkpoint: {path}')
        checkpoint = torch.load(path, map_location='cpu', weights_only=True)
        if checkpoint.get('architecture') != 'SmallUNet':
            raise ValueError(f'{path}: architecture mismatch')
        if int(checkpoint.get('seed', -1)) != seed:
            raise ValueError(f'{path}: checkpoint seed mismatch')
        if int(checkpoint.get('train_count', -1)) != cfg['train']:
            raise ValueError(f'{path}: train_count mismatch')
        if int(checkpoint.get('valid_count', -1)) != cfg['valid']:
            raise ValueError(f'{path}: valid_count mismatch')
        if int(checkpoint.get('base_channels', -1)) != 16:
            raise ValueError(f'{path}: base_channels mismatch')
        if not np.allclose(checkpoint.get('db_min', []), DB_MIN.ravel()) or \
                not np.allclose(checkpoint.get('db_max', []), DB_MAX.ravel()):
            raise ValueError(f'{path}: VV/VH dB normalization mismatch')
        if not np.isclose(float(checkpoint.get('threshold', -1)), .5):
            raise ValueError(f'{path}: threshold mismatch')
        label = checkpoint.get('label_scheme') or {}
        if label.get('ignore') != -1 or label.get('water') != 1 or \
                label.get('non_water') != 0:
            raise ValueError(f'{path}: label scheme mismatch')
        model = SmallUNet(base=16)
        model.load_state_dict(checkpoint['model_state'], strict=True)
        model.to(device).eval()
        models.append(model)
        manifests.append({
            'fold': fold, 'event': cfg['event'], 'seed': seed,
            'epoch': checkpoint.get('epoch'), 'train_count': checkpoint['train_count'],
            'valid_count': checkpoint['valid_count'],
            'checkpoint': str(path.relative_to(project_root)),
            'checkpoint_sha256': sha256_file(path),
            'checkpoint_val_iou': (checkpoint.get('validation_metrics') or {}).get('iou'),
        })
    return models, manifests


def save_preview(path: Path, x: np.ndarray, gt: np.ndarray, valid: np.ndarray,
                 pred: np.ndarray, prob: np.ndarray, ent: np.ndarray,
                 mi: np.ndarray, variance: np.ndarray) -> None:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 3, figsize=(13.5, 8.5))
    v = np.where(valid, x[0], np.nan)
    g = np.full(gt.shape, np.nan, dtype=np.float32)
    g[valid] = gt[valid].astype(np.float32)
    panels = [
        (v, 'VV normalized input', 'gray', 0, 1),
        (g, 'Surface-water GT (1=water)', 'Blues', 0, 1),
        (np.where(valid, prob, np.nan), 'Ensemble P(water)', 'viridis', 0, 1),
        (np.where(valid, pred.astype(float), np.nan), 'Prediction (threshold=0.50)', 'Blues', 0, 1),
        (np.where(valid, ent, np.nan), 'Predictive entropy (bits)', 'magma', 0, 1),
        (np.where(valid, mi, np.nan), 'Ensemble MI / disagreement (bits)', 'magma', 0, 1),
    ]
    for ax, (arr, name, cmap, lo, hi) in zip(axes.flat, panels):
        im = ax.imshow(arr, vmin=lo, vmax=hi, cmap=cmap)
        ax.set_title(name, fontsize=11)
        ax.set_xticks([]); ax.set_yticks([])
        fig.colorbar(im, ax=ax, fraction=.045, pad=.02)
    fig.suptitle('M8.0A DEV VALID ONLY — no recalibration, no independent test', fontsize=13)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130)
    plt.close(fig)


def preview_selection(records: list[tuple], fold: str, n: int) -> set[int]:
    if n <= 0:
        return set()
    selected = []
    if fold == 'dev_fold_02_sri_lanka':
        for stem in SRI_LANKA_CASES:
            for i, (im, _, _) in enumerate(records):
                if im.name == stem + '_S1Hand.tif' and i not in selected:
                    selected.append(i)
                    break
            if len(selected) >= n:
                break
    if len(selected) < n:
        for i in np.linspace(0, len(records) - 1, num=min(len(records), n), dtype=int):
            if int(i) not in selected:
                selected.append(int(i))
    if len(selected) < n:
        selected.extend(i for i in range(len(records)) if i not in selected)
    return set(selected[:n])


def evaluate_fold(project_root: Path, data_root: Path, outdir: Path,
                  fold: str, device: str, max_images: int, n_previews: int):
    records = validation_records(data_root, fold)
    models, members = load_members(project_root, fold, device)
    cfg = FOLD_INFO[fold]
    n = min(max_images, len(records)) if max_images else len(records)
    if n == 0:
        raise ValueError('No VALID images')
    # Explicitly mark subset runs as incomplete, never merge them with full research results.
    if n < len(records):
        print(f'WARNING: SUBSET RUN {fold}: {n}/{len(records)}; NOT FULL VALIDATION')
    dataset = SarWaterDataset(records, augment=False)
    selected = preview_selection(records[:n], fold, n_previews)
    sums = {'tp': 0, 'tn': 0, 'fp': 0, 'fn': 0,
            'valid_pixels': 0, 'water_pixels': 0, 'brier_sum': 0.,
            'entropy_sum': 0., 'member_entropy_sum': 0.,
            'mi_sum': 0., 'variance_sum': 0., 'fn_p_lt_0_1': 0}
    images = []
    for i in range(n):
        img_path, _lab_path, event = records[i]
        x, y, valid = dataset[i]
        if x.shape[0] != 2 or tuple(y.shape) != tuple(valid.shape):
            raise ValueError(f'{img_path.name}: unexpected dataset tensor shapes')
        v_np = valid.numpy()[0].astype(bool)
        y_np = (y.numpy()[0] >= 0.5)
        if not v_np.any():
            raise ValueError(f'{img_path.name}: no evaluable pixels')
        tensor = x.unsqueeze(0).to(device)
        probs = []
        with torch.inference_mode():
            for model in models:
                p = torch.sigmoid(model(tensor)).cpu().numpy()[0, 0]
                probs.append(p)
        pstack = np.stack(probs, axis=0)
        pbar, ent, expected_ent, mi, variance = uncertainty(pstack)
        pr = pbar >= .5
        tp = int(np.count_nonzero(pr & y_np & v_np))
        tn = int(np.count_nonzero(~pr & ~y_np & v_np))
        fp = int(np.count_nonzero(pr & ~y_np & v_np))
        fn = int(np.count_nonzero(~pr & y_np & v_np))
        nf = int(v_np.sum())
        gt_n = int(np.count_nonzero(y_np & v_np))
        brier_sum = float(np.square(pbar[v_np].astype(np.float64) - y_np[v_np]).sum())
        fn_lt = int(np.count_nonzero((~pr) & y_np & v_np & (pbar < .1)))
        h_sum = float(ent[v_np].sum(dtype=np.float64))
        eh_sum = float(expected_ent[v_np].sum(dtype=np.float64))
        mi_sum = float(mi[v_np].sum(dtype=np.float64))
        var_sum = float(variance[v_np].sum(dtype=np.float64))
        s = scores(tp, tn, fp, fn)
        row = {
            'fold': fold, 'validation_event': event, 'image': img_path.name,
            'n_members': len(SEEDS), 'valid_pixels': nf, 'gt_water_pixels': gt_n,
            'gt_water_fraction': gt_n / nf,
            'tp': tp, 'tn': tn, 'fp': fp, 'fn': fn, **s,
            'brier': brier_sum / nf,
            'mean_predictive_entropy_bits': h_sum / nf,
            'mean_member_entropy_bits': eh_sum / nf,
            'mean_mutual_information_bits': mi_sum / nf,
            'mean_probability_variance': var_sum / nf,
            'fn_p_lt_0_1_count': fn_lt,
        }
        images.append(row)
        for k in ('tp', 'tn', 'fp', 'fn'):
            sums[k] += row[k]
        sums['valid_pixels'] += nf
        sums['water_pixels'] += gt_n
        for k, value in (('brier_sum', brier_sum), ('entropy_sum', h_sum),
                         ('member_entropy_sum', eh_sum), ('mi_sum', mi_sum),
                         ('variance_sum', var_sum), ('fn_p_lt_0_1', fn_lt)):
            sums[k] += value
        if i in selected:
            preview_path = outdir / 'previews' / fold / (img_path.stem + '_ensemble.png')
            save_preview(preview_path, x.numpy(), y_np, v_np, pr, pbar, ent, mi, variance)
            # Compressed arrays for the next M8.0B reliability stage (DEV-only).
            np.savez_compressed(preview_path.with_suffix('.npz'),
                                p_water=pbar, predictive_entropy_bits=ent,
                                expected_entropy_bits=expected_ent,
                                mutual_information_bits=mi,
                                variance=variance, valid=v_np, gt_water=y_np)
        if (i + 1) % 10 == 0 or i + 1 == n:
            print(f'  {fold}: {i+1}/{n} DEV VALID chips', flush=True)
    counts = scores(sums['tp'], sums['tn'], sums['fp'], sums['fn'])
    total = sums['valid_pixels']
    aggregate = {
        'fold': fold, 'validation_event': cfg['event'],
        'n_images': n, 'expected_images': cfg['valid'],
        'full_validation': (n == cfg['valid']),
        'valid_pixels': total, 'gt_water_pixels': sums['water_pixels'],
        'gt_water_fraction': sums['water_pixels'] / total,
        'tp': sums['tp'], 'tn': sums['tn'], 'fp': sums['fp'], 'fn': sums['fn'],
        **counts, 'brier': sums['brier_sum'] / total,
        'mean_predictive_entropy_bits': sums['entropy_sum'] / total,
        'mean_member_entropy_bits': sums['member_entropy_sum'] / total,
        'mean_mutual_information_bits': sums['mi_sum'] / total,
        'mean_probability_variance': sums['variance_sum'] / total,
        'fn_p_lt_0_1_count': sums['fn_p_lt_0_1'],
        'fn_p_lt_0_1_share_of_gt_water': sums['fn_p_lt_0_1'] / sums['water_pixels']
                                      if sums['water_pixels'] else float('nan'),
    }
    # Drop GPU objects as we go: only three checkpoints per fold are needed.
    del models
    if device == 'mps' and hasattr(torch.mps, 'empty_cache'):
        torch.mps.empty_cache()
    return images, aggregate, members


def self_test() -> None:
    p = np.array([[[.2, .5], [.8, 1.0]],
                  [[.2, .5], [.8, 1.0]],
                  [[.2, .5], [.8, 1.0]]], dtype=np.float32)
    avg, pred_ent, expected_ent, mi, var = uncertainty(p)
    assert np.allclose(mi, 0, atol=1e-6)
    assert np.allclose(var, 0, atol=1e-7)
    assert np.allclose(pred_ent, expected_ent, atol=1e-6)
    assert np.isfinite(pred_ent).all()
    q = np.array([[[0.1]], [[0.5]], [[0.9]]], dtype=np.float32)
    _avg, pe, ee, disagreement, vv = uncertainty(q)
    assert 0.0 < float(disagreement[0, 0]) < float(pe[0, 0])
    assert vv[0, 0] > 0
    assert math.isnan(scores(0, 100, 0, 0)['iou'])
    assert scores(5, 0, 2, 3)['iou'] == .5
    print('PASS: M8.0A entropy/MI/variance/empty-union IoU self-test')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, default=Path('.'))
    parser.add_argument('--fold', choices=('all', *FOLD_INFO), default='all')
    parser.add_argument('--device', choices=('auto', 'mps', 'cpu', 'cuda'), default='auto')
    parser.add_argument('--output-dir', type=Path,
                        default=Path('results/event_level_v2/m80a_dev_ensemble_uq'))
    parser.add_argument('--max-images', type=int, default=0,
                        help='DEV smoke-test only; 0 means full selected folds')
    parser.add_argument('--previews-per-fold', type=int, default=2)
    parser.add_argument('--preflight', action='store_true')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test(); return
    if args.max_images < 0 or args.previews_per_fold < 0:
        parser.error('--max-images and --previews-per-fold must be nonnegative')
    root = args.project_root.resolve()
    data = root / 'data/sen1floods11/v2_development_roots'
    if not data.is_dir():
        raise FileNotFoundError(f'Development roots not found: {data}')
    fingerprint = require_frozen_protocol(root)
    device = choose_device(args.device)
    selected_folds = list(FOLD_INFO) if args.fold == 'all' else [args.fold]
    outdir = (root / args.output_dir).resolve() if not args.output_dir.is_absolute() else args.output_dir
    if not outdir.is_relative_to(root):
        raise ValueError('Output directory must be INSIDE project root')
    print('=== M8.0A: DEV-VALID ONLY / BASELINE ENSEMBLE ===', flush=True)
    print('Baseline protocol fingerprint:', fingerprint)
    print('Device:', device)
    print('Folds:', selected_folds)
    all_images, all_folds, all_members = [], [], []
    for fold in selected_folds:
        records = validation_records(data, fold)
        print(f'{fold}: verified {len(records)} DEV VALID images; 3 seeds', flush=True)
        if args.preflight:
            _models, members = load_members(root, fold, 'cpu')
            del _models
            all_members.extend(members)
        else:
            image_rows, fold_row, members = evaluate_fold(root, data, outdir, fold,
                                                          device, args.max_images,
                                                          args.previews_per_fold)
            all_images.extend(image_rows)
            all_folds.append(fold_row)
            all_members.extend(members)
            print(f"  IoU={fold_row['iou']:.4f} Recall={fold_row['recall']:.4f} "
                  f"Mean MI={fold_row['mean_mutual_information_bits']:.4f} bits")
    if args.preflight:
        print(f'PASS: validated {len(all_members)} checkpoint files; no inference, no TEST')
        return
    if not all_images:
        raise RuntimeError('No validation images processed')
    image_fields = list(all_images[0].keys())
    fold_fields = list(all_folds[0].keys())
    write_csv(outdir / 'm80a_dev_per_image.csv', all_images, image_fields)
    write_csv(outdir / 'm80a_dev_by_event.csv', all_folds, fold_fields)
    write_csv(outdir / 'm80a_members.csv', all_members, list(all_members[0].keys()))
    complete = len(selected_folds) == 3 and all(row['full_validation'] for row in all_folds)
    # Do not present subset-run macro score as a full DEV metric.
    if complete:
        macro = float(np.nanmean([r['iou'] for r in all_folds]))
        print(f'Full 3-event DEV macro IoU (ensemble): {macro:.5f}')
    else:
        macro = None
        print('INCOMPLETE DEV selection: macro IoU not reported as full 3-event metric')
    result = {
        'status': 'COMPLETE_3_FOLD_DEV_ONLY' if complete else 'PARTIAL_DEV_ONLY',
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'method': 'Baseline SmallUNet Deep Ensemble, independent seeds within each fold',
        'seeds': list(SEEDS), 'folds': selected_folds, 'device': device,
        'threshold': 0.5, 'frozen_baseline_fingerprint': fingerprint,
        'macro_iou_3_dev_events': macro,
        'source_script': str(Path(__file__).name),
        'source_script_sha256': sha256_file(Path(__file__)),
        'entropy_units': 'bits (normalized binary entropy)',
        'mutual_information': 'H(mean p) - mean H(p_m); nonnegative numerical clamp',
        'variance_units': 'probability squared, ddof=0',
        'interpretation': 'ensemble disagreement proxy; NOT guaranteed calibrated risk or exact epistemic uncertainty',
        'evaluation': 'DEV validation only; same fold, 3 independent training seeds',
        'data_exclusion': 'India/Paraguay/Ghana TEST, Bolivia and Thailand NEVER accessed',
        'no_fitting': True, 'no_recalibration': True, 'no_threshold_search': True,
        'warning': 'DEV events previously inspected and used for model planning; not pristine independent tests',
        'per_event_results': all_folds,
    }
    (outdir / 'm80a_manifest.json').write_text(
        json.dumps(json_safe(result), indent=2, ensure_ascii=False, allow_nan=False) + '\n',
        encoding='utf-8')
    print('SAVED:', outdir)
    print('STATUS:', result['status'])
    print('NO historical TEST/Bolivia/Thailand accessed.')


if __name__ == '__main__':
    main()
