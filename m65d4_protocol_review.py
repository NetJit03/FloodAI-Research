#!/usr/bin/env python3
"""M6.5D-4: read-only consistency check of the audited V2 protocol.

This is NOT a code-level proof of correctness, independent label validation,
or an evaluation of model performance. It never modifies source data or trainer.
"""
import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

FOLDS = ('dev_fold_01_usa', 'dev_fold_02_sri_lanka', 'dev_fold_03_spain')
EXPECTED_VALID = {'dev_fold_01_usa':'USA', 'dev_fold_02_sri_lanka':'Sri-Lanka', 'dev_fold_03_spain':'Spain'}

def digest(p: Path):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for part in iter(lambda: f.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()

def csv_images(path: Path):
    items=[]
    with path.open(newline='', encoding='utf-8-sig') as f:
        for row in csv.reader(f):
            if not row or not any(cell.strip() for cell in row):
                continue
            if len(row) < 2:
                raise ValueError(f'{path}: expected image,label columns; got {row!r}')
            name=Path(row[0].strip()).name
            if not name.endswith('_S1Hand.tif'):
                raise ValueError(f'{path}: unexpected SAR name {name!r}')
            items.append((name,Path(row[1].strip()).name,name.split('_',1)[0]))
    return items

def unique_events(pairs):
    return sorted({p[2] for p in pairs})

def self_test():
    assert unique_events([('Mekong_1_S1Hand.tif','', 'Mekong')]) == ['Mekong']
    assert hashlib.sha256(b'abc').hexdigest() == 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'
    print('PASS: M6.5D-4 protocol review parser and SHA-256 self-test')

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--self-test', action='store_true')
    p.add_argument('--snapshot', type=Path, default=Path('results/event_level_v1/m65d3_freeze_preflight/m65d3_proposed_config_snapshot.json'))
    p.add_argument('--roots-dir', type=Path, default=Path('data/sen1floods11/v2_development_roots'))
    p.add_argument('--trainer', type=Path, default=Path('train_sar_unet.py'))
    p.add_argument('--evaluator', type=Path, default=Path('evaluate_sar_unet.py'))
    p.add_argument('--output-dir', type=Path, default=Path('results/event_level_v1/m65d4_protocol_review'))
    a=p.parse_args()
    if a.self_test:
        self_test();return
    for path in (a.snapshot,a.trainer,a.roots_dir):
        if not path.exists():
            raise SystemExit(f'ERROR: not found: {path}')
    obj=json.loads(a.snapshot.read_text(encoding='utf-8'))
    checks=[]
    def record(name,passed,detail):
        checks.append({'check':name,'pass':bool(passed),'detail':detail})
        print(('PASS' if passed else 'FAIL')+f' {name}: {detail}')
    record('prior full audit', obj.get('unique_development_chips') == 243 and obj.get('status') == 'AUDITED_PROPOSED_NOT_FROZEN', 'snapshot reports 243 audited chips and still NOT FROZEN')
    actual=digest(a.trainer); expected=obj.get('trainer_sha256')
    record('trainer fingerprint', actual==expected, f'current={actual}, audited={expected}')
    expected_hashes=obj.get('split_sha256',{})
    all_events=set(); all_chips=set(); fold_report=[]
    for fold in FOLDS:
        root=a.roots_dir/fold
        tr,va=(root/'splits'/'flood_train_data.csv',root/'splits'/'flood_valid_data.csv')
        if not tr.is_file() or not va.is_file():
            record(f'{fold} CSVs',False, 'train/valid CSV missing');continue
        train=csv_images(tr); valid=csv_images(va)
        names_t={r[0] for r in train}; names_v={r[0] for r in valid}
        events_t=set(unique_events(train)); events_v=set(unique_events(valid))
        expected_counts={FOLDS[0]:(174,69),FOLDS[1]:(201,42),FOLDS[2]:(213,30)}[fold]
        record(f'{fold} row counts', (len(train),len(valid))==expected_counts, f'train={len(train)},valid={len(valid)}')
        record(f'{fold} event separation', not events_t.intersection(events_v) and events_v=={EXPECTED_VALID[fold]},f'val={sorted(events_v)}, train events={sorted(events_t)}')
        record(f'{fold} image separation', not names_t.intersection(names_v), f'cross-split duplicate names={len(names_t & names_v)}')
        for split,fp in [('train',tr),('valid',va)]:
            ref=expected_hashes.get(f'{fold}/{split}')
            record(f'{fold}/{split} fingerprint', ref is not None and digest(fp)==ref, 'matches audited manifest' if digest(fp)==ref else 'DIFFERS from audited manifest')
        for stub in ('test','bolivia'):
            file=root/'splits'/f'flood_{stub}_data.csv'
            # Compatibility stubs must be zero-byte or contain no data rows.
            record(f'{fold} {stub} stub empty',file.is_file() and len(list(csv.reader(file.open(newline=''))))==0 if file.is_file() else False, 'empty compatibility CSV required')
        all_events|=events_t|events_v
        all_chips|=names_t|names_v
        fold_report.append({'fold':fold,'train':len(train),'valid':len(valid),'train_events':sorted(events_t),'valid_events':sorted(events_v)})
    record('global development inventory',len(all_chips)==243 and len(all_events)==7 and all_events=={'Mekong','Nigeria','Pakistan','Somalia','Spain','Sri-Lanka','USA'},f'{len(all_chips)} unique images; {len(all_events)} events')
    record('historical TEST excluded',not {'India','Paraguay','Ghana','Bolivia'}.intersection(all_events),'no historical test/holdout events in dev')
    source=a.trainer.read_text(encoding='utf-8')
    eval_source=a.evaluator.read_text(encoding='utf-8') if a.evaluator.is_file() else ''
    excerpts=[]
    for label,src in [('TRAINER',source),('EVALUATOR',eval_source)]:
        excerpts.append(f'===== {label}: manual review snippets =====')
        for i,line in enumerate(src.splitlines(),1):
            if re.search(r'DB_MIN|DB_MAX|nodata|valid\s*=|masked_bce_dice|threshold|checkpoint|augmentation|crop_size|np\.clip|nan_to_num|sigmoid|patience',line,re.I):
                excerpts.append(f'{i}: {line[:220]}')
        excerpts.append('')
    a.output_dir.mkdir(parents=True,exist_ok=True)
    report={'status':'MECHANICAL_CHECKS_PASSED_MANUAL_REVIEW_REQUIRED' if all(c['pass'] for c in checks) else 'FAILED_REVIEW_REQUIRED','checks':checks,'folds':fold_report,'units_source':'Official Sen1Floods11 README: S1 VV/VH in dB; confirm local provenance before claiming local file units','manual_review_required':['Confirm local TIFFs originated from official Sen1Floods11 and were not unit-converted after download','Read trainer AND evaluator source to verify identical VV/VH order and normalization','Read trainer AND evaluator source for ignore=-1, land=0, water=1, valid finite SAR mask, no label nodata=0 exclusion','Confirm train-only augmentation, validation IoU selection, no TEST-based optimization','Freeze V2 protocols with checkpoint selection rule, seeds, threshold and evaluation policy']}
    (a.output_dir/'m65d4_mechanical_checks.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    (a.output_dir/'m65d4_source_review_snippets.txt').write_text('\n'.join(excerpts)+'\n',encoding='utf-8')
    print('STATUS:',report['status'])
    print('Saved:',a.output_dir/'m65d4_mechanical_checks.json')
    print('Saved:',a.output_dir/'m65d4_source_review_snippets.txt')
    if report['status'].startswith('FAILED'):
        sys.exit(2)

if __name__=='__main__':
    main()
