#!/usr/bin/env python3
"""Read local checkpoint metadata only for 27 DEV-only runs (no TEST evaluation).
Run in FloodAI-Research project: python m76d_local_checkpoint_audit.py
Reads only user-created .pt files; never execute untrusted checkpoint files.
"""
from pathlib import Path
import csv, math
import torch

ROOT=Path('results/event_level_v2')
METHODS=['baseline','v2a_eventbalanced','v2b_coverage']
SEEDS=[42,123,777]
FOLDS=['dev_fold_01_usa','dev_fold_02_sri_lanka','dev_fold_03_spain']
TARGET=ROOT/'m76d_local_checkpoint_audit.csv'
results=[]
for model in METHODS:
    for seed in SEEDS:
        for fold in FOLDS:
            folder=ROOT/f'{model}_seed{seed}'/fold
            history=folder/'history.csv'
            checkpoint=folder/'best_sar_unet.pt'
            r={'model':model,'seed':seed,'fold':fold,'history_found':history.is_file(),
               'checkpoint_found':checkpoint.is_file(),'history_best_epoch':'',
               'checkpoint_epoch':'','history_best_iou':'','checkpoint_val_iou':'',
               'checkpoint_seed':'','threshold':'','status':''}
            try:
                if not history.is_file() or not checkpoint.is_file():
                    r['status']='MISSING_FILE'
                else:
                    with history.open(newline='') as f:
                        epochrows=list(csv.DictReader(f))
                    best=None; bestval=-1.0
                    for ep in epochrows:
                        v=float(ep['val_iou'])
                        if math.isfinite(v) and v>bestval+1e-5:
                            best=ep; bestval=v
                    if best is None:raise ValueError('No finite val_iou')
                    r['history_best_epoch']=int(best['epoch'])
                    r['history_best_iou']=bestval
                    # 'weights_only' restricts checkpoint content to safe built-ins and tensors.
                    ckpt=torch.load(checkpoint,map_location='cpu',weights_only=True)
                    r['checkpoint_epoch']=ckpt.get('epoch','')
                    r['checkpoint_seed']=ckpt.get('seed','')
                    r['threshold']=ckpt.get('threshold','')
                    metrics=ckpt.get('validation_metrics',{})
                    value=metrics.get('iou',None) if isinstance(metrics,dict) else None
                    if value is not None:r['checkpoint_val_iou']=float(value)
                    good=(r['checkpoint_epoch']==r['history_best_epoch'] and
                          r['checkpoint_seed']==seed and
                          r['threshold'] is not None and
                          math.isclose(float(r['threshold']),0.5,abs_tol=1e-9))
                    if value is not None:
                        good=good and math.isclose(float(value),bestval,rel_tol=0,abs_tol=1e-4)
                    r['status']='PASS' if good else 'CHECK_METADATA'
            except Exception as e:
                r['status']='ERROR: '+repr(e)
            print(f"{r['status']:<15} {model} seed={seed} {fold}")
            results.append(r)
TARGET.parent.mkdir(parents=True,exist_ok=True)
with TARGET.open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(results[0]));w.writeheader();w.writerows(results)
print(f"\nPASS {sum(r['status']=='PASS' for r in results)}/27 | Saved: {TARGET}")
print('Only local DEV checkpoints/histories accessed. No TEST, Bolivia or Thailand data accessed.')
