#!/usr/bin/env python3
"""M7.5A read-only preflight of M7.4C baseline evidence and V2 DEV split CSVs."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import statistics
import subprocess
import sys
from collections import Counter
from pathlib import Path

EVENT_BY_FOLD = {'dev_fold_01_usa':'USA', 'dev_fold_02_sri_lanka':'Sri Lanka',
                 'dev_fold_03_spain':'Spain'}
SIZES = {'dev_fold_01_usa':(174,69), 'dev_fold_02_sri_lanka':(201,42),
         'dev_fold_03_spain':(213,30)}
HIST_TEST = {'India','Paraguay','Ghana','Bolivia'}
SEEDS = (42,123,777)


def load_baseline(path):
    with path.open(newline='') as f: records=list(csv.DictReader(f))
    selected=[r for r in records if r.get('stratum')=='ALL']
    expect={(event,seed) for event in EVENT_BY_FOLD.values() for seed in SEEDS}
    actual={(r['event'], int(r['seed'])) for r in selected}
    if actual!=expect or len(selected)!=9:
        raise RuntimeError('Baseline CSV must include exactly 9 distinct DEV event×seed metrics')
    for r in selected:
        if (int(r['n_images']) != dict(zip(EVENT_BY_FOLD.values(), [69,42,30]))[r['event']] or
            float(r['micro_iou']) < 0 or float(r['micro_iou']) > 1):
            raise RuntimeError('Baseline image-count or IoU mismatch')
    return selected


def parse_manifest(path):
    with path.open(newline='') as f:
        rows=[r for r in csv.reader(f) if r]
    if any(len(r)<2 for r in rows):
        raise RuntimeError('Expected 2-column manifest: ' + str(path))
    imgs=[r[0].strip() for r in rows]
    if len(imgs)!=len(set(imgs)):
        raise RuntimeError('Duplicate filename within ' + str(path))
    events={name.split('_')[0] for name in imgs}
    return imgs, events


def check_roots(roots_dir):
    reports=[]
    for fold, (n_train,n_valid) in SIZES.items():
        root=roots_dir/fold
        tr, trev=parse_manifest(root/'splits'/'flood_train_data.csv')
        va, vaev=parse_manifest(root/'splits'/'flood_valid_data.csv')
        test, _=parse_manifest(root/'splits'/'flood_test_data.csv')
        bolivia, _=parse_manifest(root/'splits'/'flood_bolivia_data.csv')
        if len(tr)!=n_train or len(va)!=n_valid or test or bolivia:
            raise RuntimeError(f'Unexpected fold sizes or nonempty TEST/Bolivia stub: {fold}')
        if set(tr)&set(va) or trev&vaev or (trev|vaev)&HIST_TEST:
            raise RuntimeError(f'Duplicate or leaked held-out events in {fold}')
        expected=EVENT_BY_FOLD[fold]
        if vaev!={expected.replace('Sri Lanka','Sri-Lanka')}:
            raise RuntimeError(f'Unexpected validation event in {fold}: {vaev}')
        reports.append({'fold':fold,'train_images':len(tr),'valid_images':len(va),
                        'train_events':sorted(trev),'valid_events':sorted(vaev),
                        'heldout_test_count':len(test),'bolivia_count':len(bolivia)})
    return reports


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline-csv',type=Path,
                   default=Path(__file__).resolve().parent/'m74c_baseline_reference.csv')
    p.add_argument('--roots-dir',type=Path,default=None,
                   help='Optional: data/sen1floods11/v2_development_roots')
    p.add_argument('--verify-frozen',action='store_true',
                   help='Run local m70d_freeze_protocol.py verify (read-only)')
    p.add_argument('--out-dir',type=Path,default=Path('results/event_level_v2/m75a_design_preflight'))
    p.add_argument('--self-test',action='store_true')
    a=p.parse_args()
    if a.self_test:
        from train_v2a_eventbalanced import self_test
        self_test()
        print('PASS preflight self-test')
        return
    if a.verify_frozen:
        checker=Path('m70d_freeze_protocol.py')
        if not checker.is_file(): raise FileNotFoundError('Run from project root with m70d_freeze_protocol.py')
        subprocess.run([sys.executable, str(checker),'verify','--project-root','.'],check=True)
    baseline=load_baseline(a.baseline_csv)
    by_seed={seed: statistics.mean(float(r['micro_iou']) for r in baseline if int(r['seed'])==seed)
             for seed in SEEDS}
    print('Baseline per-seed macro DEV event IoU:',{str(k):round(v,5) for k,v in by_seed.items()})
    print('Mean:',round(statistics.mean(by_seed.values()),5),
          '| Sample SD:',round(statistics.stdev(by_seed.values()),5))
    roots=[]
    if a.roots_dir is not None:
        roots=check_roots(a.roots_dir)
        for f in roots:
            print('PASS DEV fold',f['fold'],'train:',f['train_images'],'valid:',f['valid_images'])
    out={'status':'DESIGN_READY_V2A_NOT_TRAINED','main_change':'event-balanced training sampling only',
         'primary_metric':'mean across 3 events of pixel-micro VALID IoU, then mean across 3 seeds',
         'seeds':SEEDS,'baseline_macro_by_seed':by_seed,
         'baseline_mean':statistics.mean(by_seed.values()),
         'baseline_seed_sample_sd':statistics.stdev(by_seed.values()),
         'folds':roots,'prior_test_status':'do not use for experiment selection'}
    a.out_dir.mkdir(parents=True,exist_ok=True)
    (a.out_dir/'m75a_preflight_summary.json').write_text(json.dumps(out,indent=2,ensure_ascii=False))
    print('PASS M7.5A: baseline reference validated. No TEST opened.')
    print('Saved:',a.out_dir/'m75a_preflight_summary.json')

if __name__=='__main__':main()
