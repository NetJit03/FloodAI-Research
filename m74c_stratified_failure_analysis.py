#!/usr/bin/env python3
"""M7.4C: Read-only, descriptive full development-validation failure analysis.

Only consumes pre-existing M7.4 DEVELOPMENT VALIDATION CSVs.
Never reads original test/bolivia/Thai TIFFs, never loads checkpoints, never trains or tunes.
Python dependencies: matplotlib (already installed in the FloodAI virtual environment).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import math
from collections import defaultdict
from pathlib import Path

SEEDS = (42, 123, 777)
EVENTS = {'USA': 69, 'Sri Lanka': 42, 'Spain': 30}
BINS = ('0% water', '(0%, 1%)', '[1%, 5%)',
        '[5%, 20%)', '[20%, 90%)', '[90%, 100%]')
REQUIRED = {'fold', 'event', 'seed', 'image', 'valid_pixels', 'gt_water_pixels',
            'pred_water_pixels', 'tp', 'tn', 'fp', 'fn', 'iou', 'recall', 'precision'}
INT_COLS = ('valid_pixels', 'gt_water_pixels',
            'pred_water_pixels', 'tp', 'tn', 'fp', 'fn')
FLOAT_COLS = ('iou', 'recall', 'precision')


def read_rows(path):
    if not path.is_file():
        raise FileNotFoundError(
            'Required development-validation file not found: ' + str(path))
    with path.open(newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def fl(x):
    if x is None or str(x).strip().lower() in ('', 'none', 'null', 'nan'):
        return float('nan')
    return float(x)


def approx(x, y, tolerance=1e-7):
    return (math.isnan(x) and math.isnan(y)) or (math.isfinite(x) and math.isfinite(y) and abs(x - y) <= tolerance)


def ratio(x, y):
    return x / y if y else float('nan')


def finite_mean(seq):
    v = [v for v in seq if math.isfinite(v)]
    return sum(v)/len(v) if v else float('nan')


def band(frac):
    if frac == 0:
        return BINS[0]
    if frac < .01:
        return BINS[1]
    if frac < .05:
        return BINS[2]
    if frac < .20:
        return BINS[3]
    if frac < .90:
        return BINS[4]
    return BINS[5]


def write_csv(path, rows, columns):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def fmt(x, n=4):
    if x is None or not math.isfinite(float(x)):
        return 'undefined'
    return f'{float(x):.{n}f}'


def verify_and_enrich(raw):
    if not raw:
        raise ValueError('CSV is empty')
    missing = REQUIRED - raw[0].keys()
    if missing:
        raise ValueError('Missing required columns: ' + str(sorted(missing)))
    expected_size = sum(EVENTS.values())*len(SEEDS)
    if len(raw) != expected_size:
        raise ValueError(
            f'Expected {expected_size} rows for frozen V2 development validation; found {len(raw)}')
    found = defaultdict(dict)
    for r in raw:
        r = dict(r)
        r['seed'] = int(r['seed'])
        for c in INT_COLS:
            r[c] = int(r[c])
        for c in FLOAT_COLS:
            r[c] = fl(r[c])
        event, seed, img = r['event'], r['seed'], r['image']
        if event not in EVENTS or seed not in SEEDS:
            raise ValueError(
                f'Unexpected event/seed (protects development-only scope): {event}, {seed}')
        if img in found[(event, seed)]:
            raise ValueError(f'Duplicate image row {event}/{seed}/{img}')
        if any(r[c] < 0 for c in INT_COLS) or not r['valid_pixels']:
            raise ValueError('Invalid pixel counts ' + str((event, seed, img)))
        if (r['tp']+r['tn']+r['fp']+r['fn'] != r['valid_pixels']
            or r['tp']+r['fn'] != r['gt_water_pixels']
                or r['tp']+r['fp'] != r['pred_water_pixels']):
            raise ValueError(
                f'Confusion-matrix counts inconsistent for {event}/{seed}/{img}')
        denom = r['tp']+r['fp']+r['fn']
        expected_iou = ratio(r['tp'], denom)
        expected_rec = ratio(r['tp'], r['gt_water_pixels'])
        expected_prec = ratio(r['tp'], r['pred_water_pixels'])
        for col, exp in [('iou', expected_iou), ('recall', expected_rec), ('precision', expected_prec)]:
            if not approx(r[col], exp):
                raise ValueError(
                    f'{col} inconsistent for {event}/{seed}/{img}: {r[col]} versus {exp}')
        r['water_fraction'] = r['gt_water_pixels']/r['valid_pixels']
        r['water_percent'] = 100*r['water_fraction']
        r['stratum'] = band(r['water_fraction'])
        r['fn_pct_of_gt_water'] = ratio(100*r['fn'], r['gt_water_pixels'])
        r['empty_union'] = int(denom == 0)
        found[(event, seed)][img] = r
    for ev, n in EVENTS.items():
        for s in SEEDS:
            if len(found[(ev, s)]) != n:
                raise ValueError(
                    f'{ev} seed{s} has {len(found[(ev, s)])} images, expected {n}')
        ref = found[(ev, SEEDS[0])]
        for s in SEEDS[1:]:
            if set(ref) != set(found[(ev, s)]):
                raise ValueError(f'{ev} image sets mismatch across seeds')
            for img in ref:
                for field in ['valid_pixels', 'gt_water_pixels']:
                    if ref[img][field] != found[(ev, s)][img][field]:
                        raise ValueError(
                            f'{ev}/{img} GT {field} differs across seeds')
    return found


def summarize(rows, event, seed, stratum):
    counts = {f'{c}_pixels': sum(r[c] for r in rows)
              for c in ('tp', 'tn', 'fp', 'fn')}
    tp, fp, fn = counts['tp_pixels'], counts['fp_pixels'], counts['fn_pixels']
    valid = sum(r['valid_pixels'] for r in rows)
    gt = sum(r['gt_water_pixels'] for r in rows)
    return dict(event=event, seed=seed, stratum=stratum, n_images=len(rows),
                n_images_zero_gt=sum(r['gt_water_pixels'] == 0 for r in rows),
                n_images_empty_union=sum(r['empty_union'] for r in rows),
                valid_pixels=valid, gt_water_pixels=gt, water_fraction=ratio(
                    gt, valid),
                predicted_water_pixels=sum(
                    r['pred_water_pixels'] for r in rows),
                **counts, micro_iou=ratio(tp, tp+fp+fn),
                micro_recall=ratio(tp, tp+fn), micro_precision=ratio(tp, tp+fp),
                macro_image_iou=finite_mean([r['iou'] for r in rows]),
                macro_image_recall=finite_mean([r['recall'] for r in rows]))


def safe_ax_label(s):
    return s.replace('Sri-Lanka_', '').replace('_S1Hand.tif', '')


def plot_group(data, value_key, title, filename, outdir):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(11, 5.5))
    usebins = BINS[1:]
    for seed in SEEDS:
        lookup = {r['stratum']: r[value_key]
                  for r in data if r['seed'] == seed}
        y = [lookup.get(b, float('nan')) for b in usebins]
        ax.plot(range(len(usebins)), y, marker='o',
                linewidth=2, label=f'Seed {seed}')
    ax.set_xticks(range(len(usebins)), usebins)
    ax.set_ylim(0, 1.02)
    ax.set_ylabel('Micro '+('water IoU' if value_key ==
                  'micro_iou' else 'water recall'))
    ax.set_title(title+'\nDevelopment validation only; 0.50 threshold')
    ax.grid(alpha=.20)
    ax.legend()
    fig.tight_layout()
    fig.savefig(outdir/filename, dpi=180)
    plt.close(fig)


def plot_paired(rows, outdir):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    positives = [r for r in rows if r['event'] == 'Sri Lanka' and r['gt_water_pixels'] > 0
                 and math.isfinite(r['delta_iou_777_minus_mean42_123'])]
    fig, ax = plt.subplots(figsize=(9.8, 6))
    ax.scatter([r['water_percent'] for r in positives],
               [r['delta_iou_777_minus_mean42_123'] for r in positives], alpha=.8)
    ax.axhline(0, color='gray', linestyle='--', linewidth=1)
    for r in sorted(positives, key=lambda x: x['delta_iou_777_minus_mean42_123'])[:3]:
        ax.annotate(safe_ax_label(r['image']),
                    (r['water_percent'], r['delta_iou_777_minus_mean42_123']),
                    xytext=(-46, 9), textcoords='offset points', fontsize=9)
    ax.set(xlabel='Ground-truth water share (%)',
           ylabel='Seed 777 IoU minus mean IoU of seeds 42/123',
           title='Sri Lanka: paired per-image IoU differences (DEV VALID only)')
    ax.grid(alpha=.2)
    fig.tight_layout()
    fig.savefig(outdir/'m74c_sri_lanka_paired_iou_gap.png', dpi=180)
    plt.close(fig)


def plot_fn(rows, outdir):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    sl = [r for r in rows if r['event'] == 'Sri Lanka']
    top = sorted(sl, key=lambda r: r['fn_777'], reverse=True)[:10][::-1]
    fig, ax = plt.subplots(figsize=(10, 6.5))
    names = [safe_ax_label(r['image']) for r in top]
    vals = [r['fn_777'] for r in top]
    ax.barh(names, vals)
    ax.set(xlabel='False-negative water pixels at fixed threshold 0.50',
           title='Sri Lanka: largest missed-water chips, seed 777 (DEV VALID)')
    ax.grid(axis='x', alpha=.2)
    fig.tight_layout()
    fig.savefig(outdir/'m74c_sri_lanka_seed777_fn_top10.png', dpi=180)
    plt.close(fig)


def write_report(path, all_summary, groups, paired, input_hash):
    lookup = {(r['event'], r['seed'], r['stratum']): r for r in groups}
    overall = {(r['event'], r['seed']): r for r in all_summary}
    sl = [r for r in paired if r['event'] == 'Sri Lanka']
    two = sorted(sl, key=lambda r: r['fn_777'], reverse=True)[:2]
    sl_total_fn = overall['Sri Lanka', 777]['fn_pixels']
    sl_gt = overall['Sri Lanka', 777]['gt_water_pixels']
    fn2 = sum(r['fn_777'] for r in two)
    gt2 = sum(r['gt_water_pixels'] for r in two)
    high_777 = lookup['Sri Lanka', 777, '[90%, 100%]']
    high_42 = lookup['Sri Lanka', 42, '[90%, 100%]']
    high_123 = lookup['Sri Lanka', 123, '[90%, 100%]']
    lines = [
        '# M7.4C — Full-Validation Stratified Failure Analysis',
        '',
        '**Scope:** Retrospective, descriptive analysis of the existing V2 *development-validation* per-image predictions.',
        '**No model trained/retrained, no checkpoint changed, no threshold tuning, no historical TEST / Bolivia / Thailand used.**',
        'All IoU/recall metrics are fixed-threshold (0.50) and use only evaluable pixels.',
        f'Input per-image CSV SHA-256: `{input_hash}`.',
        '', '## A. Full development-validation results (pixel-micro, 3 seeds per event)', '',
        '| Event | Images / seed | Seed | Water IoU | Recall | Precision | False negatives |',
        '|---|---:|---:|---:|---:|---:|---:|'
    ]
    for ev in EVENTS:
        for seed in SEEDS:
            r = overall[ev, seed]
            lines.append(
                f"| {ev} | {r['n_images']} | {seed} | {fmt(r['micro_iou'])} | {fmt(r['micro_recall'])} | {fmt(r['micro_precision'])} | {r['fn_pixels']:,} |")
    lines += ['', '## B. Stratification by ground-truth water fraction', '',
              'Fractions defined as `GT water pixels / valid pixels`. Six fixed diagnostic bins are used:',
              '`0%`; `(0%,1%)`; `[1%,5%)`; `[5%,20%)`; `[20%,90%)`; `[90%,100%]`.',
              'A 0%-water image has undefined water recall. If TP+FP+FN = 0, IoU is undefined (NaN), **not** 1.',
              'Stratum metrics below are **pixel-micro** (sum TP/FP/FN across images, then calculate ratios); this is different from averaging image IoUs.',
              '', '| Sri Lanka stratum | Images | Seed | Micro IoU | Micro recall | FN pixels |',
              '|---|---:|---:|---:|---:|---:|']
    for b in BINS:
        for seed in SEEDS:
            r = lookup['Sri Lanka', seed, b]
            lines.append(
                f"| {b} | {r['n_images']} | {seed} | {fmt(r['micro_iou'])} | {fmt(r['micro_recall'])} | {r['fn_pixels']:,} |")
    lines += ['', '## C. Critical high-water failure: Sri Lanka, seed 777', '',
              f'- Extreme-high-water stratum (`>=90%`): **{high_777["n_images"]} images**.',
              f'- Extreme-high-water micro recall: seed 42 **{fmt(high_42["micro_recall"])}**, seed 123 **{fmt(high_123["micro_recall"])}**, seed 777 **{fmt(high_777["micro_recall"])}**.',
              f'- The **two most FN-heavy images** contribute **{fn2:,}/{sl_total_fn:,} = {100*fn2/sl_total_fn:.2f}%** of all Sri Lanka seed-777 false negatives.',
              f'- Those two images contain **{gt2:,}/{sl_gt:,} = {100*gt2/sl_gt:.2f}%** of all evaluable Sri Lanka GT-water pixels.',
              '', '| Image | GT-water fraction | Seed42 recall | Seed123 recall | Seed777 recall | Seed777 FN |',
              '|---|---:|---:|---:|---:|---:|']
    for r in two:
        lines.append(
            f"| {r['image']} | {r['water_percent']:.2f}% | {fmt(r['recall_42'])} | {fmt(r['recall_123'])} | {fmt(r['recall_777'])} | {r['fn_777']:,} |")
    lines += ['',
              '**Interpretation:** Evidence of concentration of seed-777 under-detection in nearly fully flooded development-validation images. This is descriptive, not proof of a particular physical or training mechanism. Do not drop seed 777.',
              '', '## D. Important scientific interpretation limits', '',
              '- Only three independent **development validation events** (USA, Sri Lanka, Spain) are represented. Pixels and image chips within events are dependent; they are not independent events.',
              '- These data are already inspected during V2 development. Findings and any resulting model ideas are exploratory. A new untouched event is needed for confirmatory testing.',
              '- The severe Sri Lanka case is assessed within the same event and the same image IDs for all three seeds, which avoids mixing distinct image sets, but does not isolate a causal training mechanism.',
              '- `macro_image_iou` excludes undefined empty-union images. `micro_iou` weights by pixels, so large water-heavy images can dominate.',
              '- No per-pixel predictive probability or image-level SAR rasters are included here: this stage cannot support entropy, calibration, or SAR radiometry claims.',
              '- GT labels encode **surface water**, not necessarily newly inundated flood water.',
              '', '## E. Next controlled development steps', '',
              '1. Keep baseline protocol frozen and retain all 9 seed/checkpoint combinations.',
              '2. Specify Model V2 candidates using literature and development-validation diagnostics only (e.g., improved coverage of large contiguous water), not historical TEST.',
              '3. Train both baseline comparator and V2 with identical V2 folds/seeds and report event macro-IoU + sample SD across seeds.',
              '4. Use new independent, label-validated geographic events for a final confirmation; Thailand needs co-registered high-quality GT to calculate comparable IoU.',
              '', '## Output files', '',
              '- `m74c_stratum_metrics.csv`: per-event/per-seed/per-stratum pixel-micro and image-macro metrics.',
              '- `m74c_event_seed_metrics.csv`: whole-event pixel-micro metrics.',
              '- `m74c_paired_per_image.csv`: paired per-image comparisons of all three seeds.',
              '- `m74c_per_image_enriched.csv`: 423 original validation rows plus strata and counts.',
              '- `m74c_sri_lanka_seed777_ranked_cases.csv`: ranking of Sri Lanka failures by seed-777 missed water.',
              '- Four PNG figures for Sri Lanka and one CSV with input file checksums.',
              '', '---',
              'The script checks that each event contains identical images and GT across seeds, and that confusion matrices reconstruct the checkpoint-selected micro IoU.',
              ]
    path.write_text('\n'.join(lines)+'\n', encoding='utf-8')


def run(input_dir, outdir):
    input_dir, outdir = Path(input_dir), Path(outdir)
    # Deliberately whitelist ONLY these pre-existing DEV-VALID output files.
    path = input_dir/'m74_development_validation_per_image.csv'
    raw = read_rows(path)
    found = verify_and_enrich(raw)
    outdir.mkdir(parents=True, exist_ok=True)
    whole = []
    groups = []
    enriched = []
    for ev, n in EVENTS.items():
        for seed in SEEDS:
            rows = list(found[(ev, seed)].values())
            whole.append(summarize(rows, ev, seed, 'ALL'))
            enriched.extend(rows)
            for b in BINS:
                sub = [r for r in rows if r['stratum'] == b]
                groups.append(summarize(sub, ev, seed, b))
    # Cross-check reconstructed micro IoU against pre-existing M7.4 selected checkpoints.
    checkpoints = input_dir/'m74_selected_checkpoints.csv'
    cks = read_rows(checkpoints)
    if len(cks) != 9:
        raise ValueError('Expected 9 selected checkpoints')
    baseline = {(r['event'], int(r['seed'])): r for r in cks}
    for r in whole:
        c = baseline.get((r['event'], r['seed']))
        if c is None or not approx(r['micro_iou'], fl(c['val_iou'])) or fl(c['fixed_threshold']) != .5:
            raise ValueError('Checkpoint consistency FAIL for ' +
                             str((r['event'], r['seed'])))
    opt = input_dir/'m74_development_validation_micro.csv'
    if opt.exists():
        summaries = read_rows(opt)
        for r in summaries:
            actual = next(
                (a for a in whole if a['event'] == r['event'] and a['seed'] == int(r['seed'])), None)
            if actual is None or not approx(actual['micro_iou'], fl(r['micro_iou'])):
                raise ValueError('M7.4 micro summary consistency failure')
    paired = []
    for ev, n in EVENTS.items():
        images = sorted(found[(ev, 42)])
        for img in images:
            x = {s: found[(ev, s)][img] for s in SEEDS}
            base = x[42]
            iou_ref = finite_mean([x[42]['iou'], x[123]['iou']])
            rec_ref = finite_mean([x[42]['recall'], x[123]['recall']])
            available = [x[s]['iou']
                         for s in SEEDS if math.isfinite(x[s]['iou'])]
            paired.append(dict(event=ev, image=img, stratum=base['stratum'],
                               valid_pixels=base['valid_pixels'], gt_water_pixels=base['gt_water_pixels'],
                               water_fraction=base['water_fraction'], water_percent=base['water_percent'],
                               **{f'iou_{s}': x[s]['iou'] for s in SEEDS},
                               **{f'recall_{s}': x[s]['recall'] for s in SEEDS},
                               **{f'fp_{s}': x[s]['fp'] for s in SEEDS},
                               **{f'fn_{s}': x[s]['fn'] for s in SEEDS},
                               mean_iou_42_123=iou_ref,
                               delta_iou_777_minus_mean42_123=x[777]['iou']-iou_ref if math.isfinite(
                x[777]['iou']) and math.isfinite(iou_ref) else float('nan'),
                delta_recall_777_minus_mean42_123=x[777]['recall']-rec_ref if math.isfinite(
                    x[777]['recall']) and math.isfinite(rec_ref) else float('nan'),
                seed_iou_range=max(available)-min(available) if available else float('nan')))
    case = sorted(
        (r for r in paired if r['event'] == 'Sri Lanka'), key=lambda r: r['fn_777'], reverse=True)
    files = [('m74c_event_seed_metrics.csv', whole),
             ('m74c_stratum_metrics.csv', groups),
             ('m74c_per_image_enriched.csv', enriched),
             ('m74c_paired_per_image.csv', paired),
             ('m74c_sri_lanka_seed777_ranked_cases.csv', case)]
    for name, rows in files:
        write_csv(outdir/name, rows, list(rows[0].keys()))
    integrity = [dict(file=p.name, sha256=sha256(p))
                 for p in [path, checkpoints]+([opt] if opt.exists() else [])]
    write_csv(outdir/'m74c_input_checksums.csv', integrity, ['file', 'sha256'])
    sl_groups = [r for r in groups if r['event'] == 'Sri Lanka']
    plot_group(sl_groups, 'micro_iou', 'Sri Lanka: IoU by GT-water fraction',
               'm74c_sri_lanka_stratified_iou.png', outdir)
    plot_group(sl_groups, 'micro_recall', 'Sri Lanka: recall by GT-water fraction',
               'm74c_sri_lanka_stratified_recall.png', outdir)
    plot_paired(paired, outdir)
    plot_fn(paired, outdir)
    write_report(outdir/'m74c_report.md', whole, groups, paired, sha256(path))
    print('M7.4C PASS: all 423 DEV-VALID rows; 141 paired images; all 9 checkpoints; GT/count integrity.')
    for ev in EVENTS:
        print(ev, 'micro IoU:', ' | '.join(
            f'{s}: {next(x for x in whole if x["event"] == ev and x["seed"] == s)["micro_iou"]:.4f}' for s in SEEDS))
    sl = next(x for x in whole if x['event'] ==
              'Sri Lanka' and x['seed'] == 777)
    worst = sorted((r for r in paired if r['event'] == 'Sri Lanka'),
                   key=lambda r: r['fn_777'], reverse=True)[:2]
    print('Sri Lanka seed 777: two top-FN images account for %.2f%% of all FN' %
          (100*sum(r['fn_777'] for r in worst)/sl['fn_pixels']))
    print('Saved:', outdir.resolve())


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input-dir', type=Path,
                   default=Path('results/event_level_v2/m74_stability_diagnostics'))
    p.add_argument('--output-dir', type=Path,
                   default=Path('results/event_level_v2/m74c_stratified_failure'))
    a = p.parse_args()
    run(a.input_dir, a.output_dir)


if __name__ == '__main__':
    main()
