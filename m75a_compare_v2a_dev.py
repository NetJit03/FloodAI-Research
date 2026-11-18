#!/usr/bin/env python3
"""Compare all 9 V2-A validation checkpoints to frozen V1 baseline; NEVER TEST."""
from __future__ import annotations
import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
import torch
from m75a_preflight import EVENT_BY_FOLD, SEEDS, load_baseline


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--v2-root',type=Path,default=Path('results/event_level_v2'))
    p.add_argument('--baseline-csv',type=Path,
                   default=Path(__file__).resolve().parent/'m74c_baseline_reference.csv')
    p.add_argument('--output-dir',type=Path,default=Path('results/event_level_v2/m75a_v2a_comparison'))
    a=p.parse_args()
    baseline={(r['event'],int(r['seed'])):float(r['micro_iou']) for r in load_baseline(a.baseline_csv)}
    output=[]
    missing=[]
    for seed in SEEDS:
        for fold,event in EVENT_BY_FOLD.items():
            loc=a.v2_root/f'v2a_eventbalanced_seed{seed}'/fold
            ckpt=loc/'best_sar_unet.pt'
            history=loc/'history.csv'
            config=loc/'run_config_v2a.json'
            if not all(x.is_file() for x in (ckpt,history,config)):
                missing.append(str(loc));continue
            meta=json.loads(config.read_text())
            if meta.get('smoke') or meta.get('fold')!=fold or int(meta.get('seed',-1))!=seed:
                raise RuntimeError(f'Wrong metadata or subset run: {loc}')
            checkpoint=torch.load(ckpt, map_location='cpu', weights_only=True)
            if checkpoint.get('experiment')!='M7.5A_V2A_eventbalanced' or checkpoint.get('smoke'):
                raise RuntimeError(f'Not a full V2-A checkpoint: {ckpt}')
            with history.open(newline='') as f: rows=list(csv.DictReader(f))
            ep=int(checkpoint['epoch']); matches=[r for r in rows if int(r['epoch'])==ep]
            if len(matches)!=1: raise RuntimeError(f'No checkpoint epoch in history: {loc}')
            value=float(matches[0]['val_iou'])
            if not math.isclose(value,float(checkpoint['validation_metrics']['iou']),abs_tol=1e-7):
                raise RuntimeError('Checkpoint/history IoU mismatch: '+str(loc))
            ref=baseline[(event,seed)]
            output.append({'event':event,'fold':fold,'seed':seed,'v1_iou':ref,
                           'v2a_iou':value,'delta':value-ref,'best_epoch':ep})
    if missing:
        print(f'NOT READY: {len(missing)}/9 full V2-A checkpoint folders missing.')
        for folder in missing: print('  ',folder)
        print('No comparison reported; first train all 9 DEV-only V2-A runs.')
        return
    grouped=defaultdict(list)
    for r in output: grouped[r['seed']].append(r)
    per_seed=[]
    for seed in SEEDS:
        records=grouped[seed]
        per_seed.append({'seed':seed,
           'baseline_macro':statistics.mean(r['v1_iou'] for r in records),
           'v2a_macro':statistics.mean(r['v2a_iou'] for r in records),
           'paired_delta':statistics.mean(r['delta'] for r in records)})
    base_mean=statistics.mean(r['baseline_macro'] for r in per_seed)
    v2_mean=statistics.mean(r['v2a_macro'] for r in per_seed)
    v2_sd=statistics.stdev(r['v2a_macro'] for r in per_seed)
    print(f'Baseline DEV macro IoU: {base_mean:.5f}')
    print(f'V2-A DEV macro IoU: {v2_mean:.5f} ± {v2_sd:.5f} sample SD across 3 seeds')
    print(f'Paired mean delta: {v2_mean-base_mean:+.5f} (DESCRIPTIVE, NOT independent TEST)')
    a.output_dir.mkdir(parents=True,exist_ok=True)
    with (a.output_dir/'m75a_paired_fold_seed.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(output[0]));w.writeheader();w.writerows(output)
    with (a.output_dir/'m75a_macro_by_seed.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(per_seed[0]));w.writeheader();w.writerows(per_seed)
    (a.output_dir/'m75a_comparison_summary.json').write_text(json.dumps({
        'status':'DEV_VALID_ONLY','baseline_mean':base_mean,'v2a_mean':v2_mean,
        'v2a_sample_sd':v2_sd,'paired_mean_delta':v2_mean-base_mean,
        'limitation':'Exploratory; existing DEV events used for hypothesis generation. Independent confirmation required.'},indent=2))
    print('Saved DEV comparison in',a.output_dir)

if __name__=='__main__':main()
