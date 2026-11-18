#!/usr/bin/env python3
"""M6.5D V2 experimental-protocol preflight: no training or modification of source splits.

Reads 3 existing event-level roots, confirms event disjointness and inventory,
then (only if all validation passes) writes *proposed* V2 development CSV manifests
under the chosen output directory. Existing data and checkpoints are never modified.

Expected project layout:
  data/sen1floods11/event_level_roots/fold_01_india/splits/flood_train_data.csv
  .../S1Hand/, .../LabelHand/ (usually symlinked to the source directories)

Usage:
  python m65d_preflight.py --data-root data/sen1floods11
  python m65d_preflight.py --self-test
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from collections import Counter, defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory

FOLDS = {
    'fold_01_india': {'train': 288, 'valid': 69, 'test': 68, 'bolivia': 15, 'valid_event': 'USA', 'test_event': 'India'},
    'fold_02_paraguay': {'train': 317, 'valid': 42, 'test': 66, 'bolivia': 15, 'valid_event': 'Sri-Lanka', 'test_event': 'Paraguay'},
    'fold_03_ghana': {'train': 347, 'valid': 30, 'test': 48, 'bolivia': 15, 'valid_event': 'Spain', 'test_event': 'Ghana'},
}
DEVELOPMENT_EVENTS = ('Cambodia', 'Nigeria', 'Pakistan',
                      'Somalia', 'Spain', 'Sri-Lanka', 'USA')
HISTORICAL_TESTS = ('India', 'Paraguay', 'Ghana')
VALIDATION_EVENTS = ('USA', 'Sri-Lanka', 'Spain')
ALIASES = {'Mekong': 'Cambodia',
           'Sri_Lanka': 'Sri-Lanka', 'Sri-Lanka': 'Sri-Lanka'}


def event_name(filename: str) -> str:
    p = Path(filename).name
    return ALIASES.get(p.split('_', 1)[0], p.split('_', 1)[0])


def strip_suffix(name: str, suffix: str) -> str:
    p = Path(name).name
    if not p.endswith(suffix):
        raise ValueError(
            f'Unexpected raster filename suffix: {p!r}; expected {suffix}')
    return p[:-len(suffix)]


def read_split_csv(path: Path) -> list[tuple[str, str]]:
    with path.open(newline='', encoding='utf-8-sig') as f:
        rdr = csv.reader(f)
        rows = []
        for i, raw in enumerate(rdr, 1):
            if not raw or all(not c.strip() for c in raw):
                continue
            if len(raw) < 2:
                raise ValueError(
                    f'{path}:{i}: expected at least image,label columns; got {raw!r}')
            image, label = raw[0].strip(), raw[1].strip()
            if i == 1 and image.lower() in {'image', 'images', 'image_path', 'sar', 'sar_path', 'filename'}:
                continue
            if not image or not label:
                raise ValueError(f'{path}:{i}: empty image/label')
            stem = strip_suffix(image, '_S1Hand.tif')
            label_stem = strip_suffix(label, '_LabelHand.tif')
            if stem != label_stem:
                raise ValueError(
                    f'{path}:{i}: SAR/label mismatch: {image} vs {label}')
            rows.append((Path(image).name, Path(label).name))
    return rows


def check_files(root: Path, records: list[tuple[str, str]], errors: list[str], max_examples: int = 5) -> None:
    missing = []
    for img, label in records:
        ip, lp = root/'S1Hand'/img, root/'LabelHand'/label
        if not ip.is_file() or not lp.is_file():
            missing.append((str(ip) if not ip.is_file() else '',
                           str(lp) if not lp.is_file() else ''))
    if missing:
        errors.append(
            f'{root}: {len(missing)} missing image/label pairs; first examples: {missing[:max_examples]}')


def check_fold(root: Path, expected: dict, verify_files: bool) -> tuple[dict, dict, list[str], list[str]]:
    errors, warnings = [], []
    split_rows: dict[str, list[tuple[str, str]]] = {}
    for split in ('train', 'valid', 'test', 'bolivia'):
        p = root/'splits'/f'flood_{split}_data.csv'
        if not p.is_file():
            errors.append(f'Missing CSV: {p}')
            split_rows[split] = []
            continue
        try:
            rows = read_split_csv(p)
        except (ValueError, OSError) as e:
            errors.append(str(e))
            rows = []
        split_rows[split] = rows
        if len(rows) != expected[split]:
            errors.append(
                f'{root.name}/{split}: expected {expected[split]} chips, got {len(rows)}')
        if verify_files:
            check_files(root, rows, errors)
    sets = {s: {r[0] for r in rows} for s, rows in split_rows.items()}
    for s in sets:
        if len(sets[s]) != len(split_rows[s]):
            errors.append(
                f'{root.name}/{s}: duplicate SAR filenames within split')
    for i, s1 in enumerate(sets):
        for s2 in list(sets)[i+1:]:
            x = sets[s1] & sets[s2]
            if x:
                errors.append(
                    f'{root.name}: same SAR filename in {s1} and {s2}: {sorted(x)[:5]}')
    events = {s: sorted({event_name(name) for name in names})
              for s, names in sets.items()}
    for i, s1 in enumerate(events):
        for s2 in list(events)[i+1:]:
            shared = set(events[s1]) & set(events[s2])
            if shared:
                errors.append(
                    f'{root.name}: EVENT LEAKAGE between {s1} and {s2}: {sorted(shared)}')
    for split, expected_event in [('valid', expected['valid_event']), ('test', expected['test_event']), ('bolivia', 'Bolivia')]:
        if events[split] != [expected_event]:
            errors.append(
                f'{root.name}/{split}: expected only {expected_event}, got {events[split]}')
    if len(events['train']) != 8:
        errors.append(
            f'{root.name}: expected 8 distinct train events, got {len(events["train"])}: {events["train"]}')
    # This is deliberately a metadata check only; actual raster-grid and label checks were completed in prior M6 stages.
    stats = {
        s: {'n_images': len(split_rows[s]), 'events': events[s]} for s in split_rows}
    return stats, split_rows, errors, warnings


def write_csv(path: Path, rows: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, lineterminator='\n')
        # same no-header schema as the original train_sar_unet.py
        writer.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data-root', type=Path,
                    default=Path('data/sen1floods11'))
    ap.add_argument('--output-dir', type=Path,
                    default=Path('results/event_level_v1/m65d_protocol_preflight'))
    ap.add_argument('--skip-file-check', action='store_true',
                    help='Useful for manifest-only checks, not sufficient to start training')
    ap.add_argument('--self-test', action='store_true')
    args = ap.parse_args()
    if args.self_test:
        with TemporaryDirectory() as tmp:
            p = Path(tmp)/'flood_train_data.csv'
            write_csv(p, [('Mekong_1_S1Hand.tif', 'Mekong_1_LabelHand.tif'),
                      ('Spain_2_S1Hand.tif', 'Spain_2_LabelHand.tif')])
            r = read_split_csv(p)
            assert len(r) == 2 and event_name(
                r[0][0]) == 'Cambodia' and event_name(r[1][0]) == 'Spain'
            assert strip_suffix(r[0][0], '_S1Hand.tif') == strip_suffix(
                r[0][1], '_LabelHand.tif')
        print('PASS: M6.5D parser/CSV writer self-test')
        return 0

    all_errors, all_warnings, checks, source_sets = [], [], {}, []
    print('=== M6.5D DATA PROTOCOL PREFLIGHT ===')
    for name, expected in FOLDS.items():
        root = args.data_root/'event_level_roots'/name
        stats, rows, errors, warnings = check_fold(
            root, expected, not args.skip_file_check)
        checks[name] = stats
        all_errors.extend(errors)
        all_warnings.extend(warnings)
        source = {im: label for split, rr in rows.items() if split !=
                  'bolivia' for im, label in rr}
        source_sets.append(source)
        for split in ('train', 'valid', 'test', 'bolivia'):
            st = stats[split]
            print(
                f'{name:<18} {split:<7} {st["n_images"]:>3} images | {", ".join(st["events"])}')
    if args.skip_file_check:
        all_warnings.append(
            'Skipped image/label existence checks: do not start training on this check alone')

    if source_sets:
        canonical = source_sets[0]
        for i, other in enumerate(source_sets[1:], 2):
            if other != canonical:
                all_errors.append(
                    f'Source samples differ between Fold 1 and Fold {i}: keys/labels are inconsistent')
        if len(canonical) != 425:
            all_errors.append(
                f'Expected 425 distinct non-Bolivia audited chips, got {len(canonical)}')
        by_event = defaultdict(list)
        for im, lab in canonical.items():
            by_event[event_name(im)].append((im, lab))
        all_events = set(by_event)
        expected_events = set(DEVELOPMENT_EVENTS) | set(HISTORICAL_TESTS)
        if all_events != expected_events:
            all_errors.append(
                f'Unexpected source event inventory: {sorted(all_events ^ expected_events)}')
        if len({k for k in by_event}) != 10:
            all_errors.append(
                f'Expected ten non-Bolivia events; got {len(by_event)}')
        development = {e: sorted(by_event.get(e, []))
                       for e in DEVELOPMENT_EVENTS}
        n_dev = sum(map(len, development.values()))
        if n_dev != 243:
            all_errors.append(
                f'Expected 243 dev chips (7 events) from reported logs; got {n_dev}')
    else:
        development = {}
        n_dev = 0

    if all_errors:
        print('\nFAILED PREFLIGHT: no proposed V2 split CSVs were written.')
        for e in all_errors[:30]:
            print('ERROR:', e)
        if len(all_errors) > 30:
            print(f'... plus {len(all_errors)-30} more errors')
        return 1

    args.output_dir.mkdir(parents=True, exist_ok=True)
    out = {
        'generated_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'source_root': str(args.data_root),
        'study_stage': 'M6.5D preflight; not a trained or evaluated V2',
        'design': 'Development events only. Historical V1 tests excluded from V2 dev training and model selection.',
        'three_original_folds': checks,
        'development_event_counts': {e: len(development[e]) for e in DEVELOPMENT_EVENTS},
        'n_development_chips': n_dev,
        'historically_inspected_test_events': list(HISTORICAL_TESTS),
        'bolivia_status': 'Not in three reported test sets, but previously inspected; not pristine prospective test',
        'thailand_status': 'Diagnostic pilot only; no independently validated surface-water ground truth',
        'warnings': all_warnings,
    }
    dev_folds = []
    for i, validation_event in enumerate(VALIDATION_EVENTS, 1):
        sub = args.output_dir/'proposed_dev_manifests' / \
            f'dev_fold_{i:02d}_{validation_event.lower().replace("-", "_")}'
        tr = sorted(r for ev, rr in development.items()
                    if ev != validation_event for r in rr)
        va = development[validation_event]
        assert not {r[0] for r in tr} & {r[0] for r in va}
        assert sum(map(len, (tr, va))) == n_dev
        write_csv(sub/'flood_train_data.csv', tr)
        write_csv(sub/'flood_valid_data.csv', va)
        dev_folds.append({'fold': sub.name, 'train_images': len(tr), 'validation_images': len(va),
                          'train_events': [e for e in DEVELOPMENT_EVENTS if e != validation_event],
                          'validation_event': validation_event,
                          'csv_dir': str(sub)})
    out['proposed_development_folds'] = dev_folds
    json_path = args.output_dir/'m65d_preflight.json'
    json_path.write_text(json.dumps(
        out, indent=2, ensure_ascii=False), encoding='utf-8')
    lines = ['# M6.5D Preflight — PROPOSED, NOT FINALIZED', '',
             f'- Source: `{args.data_root}`',
             '- Original three event-disjoint folds: **PASS** for CSV counts, no duplicate chips and no event overlap',
             f'- Development pool: **{n_dev} chips / 7 events**',
             '- Excluded from V2 development: India, Paraguay, Ghana (historical V1 test events)',
             '- Bolivia: pre-existing holdout, previously inspected (not pristine)',
             '- Thailand: diagnostic reference only, not a comparable test ground truth',
             '- No source CSV, TIFF, checkpoint, or original split modified.',
             '', '## Development event inventory', '']
    for e in DEVELOPMENT_EVENTS:
        lines.append(f'- {e}: {len(development[e])} chips')
    lines += ['', '## Proposed event-disjoint development folds', '']
    for f in dev_folds:
        lines.append(
            f'- {f["fold"]}: train {f["train_images"]} chips / 6 events; validate {f["validation_images"]} chips / {f["validation_event"]}')
    lines += ['', '## Methodological warnings', '',
              '- These 3 validation folds are intended for V2 model development, not final independent evaluation.',
              '- V1 and V2 must be retrained under identical V2 development splits before comparing methods fairly.',
              '- Do not choose V2 hyperparameters, thresholds or normalization from prior India/Paraguay/Ghana tests.',
              '- Final confirmation requires newly independent, appropriately labeled event(s).',
              '- Confirm SAR numeric units and valid masks before implementing radiometric augmentation.',
              '- The manifests need corresponding training data-root links and an explicit split loader; do NOT pass them directly as --data-root.',
              '- Report event-level results; pixels are spatially correlated and do not provide independent sample counts.',
              '']
    (args.output_dir/'m65d_preflight.md').write_text('\n'.join(lines), encoding='utf-8')
    print('\nPASS: 3 event-disjoint original fold manifests checked')
    print(f'PASS: V2 development inventory = {n_dev} chips, 7 events')
    for f in dev_folds:
        print(
            f'PROPOSED {f["fold"]}: train={f["train_images"]}, valid={f["validation_images"]} ({f["validation_event"]})')
    print('Saved:', json_path)
    print('Saved:', args.output_dir/'m65d_preflight.md')
    print('NOTE: this is DATA-PROTOCOL PREFLIGHT only: no model trained or evaluated.')
    print('NOTE: manifests are NOT ready as --data-root; they must be linked with S1Hand/LabelHand under a training root.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
