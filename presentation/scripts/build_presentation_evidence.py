#!/usr/bin/env python3
"""Rebuild presentation evidence without changing experiment files or fitting models.

Run from the project root:
  MPLCONFIGDIR=/private/tmp/floodai-mpl .venv/bin/python presentation/scripts/build_presentation_evidence.py
Optional: --recheck-previews repeats CPU inference on the nine stored DEV previews.
Only presentation/ is written. Historical TEST and Thailand rasters are not read.
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import statistics as st
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import Counter

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'presentation'
EVIDENCE = OUT / 'evidence'
FIGURES = OUT / 'assets/figures'
R = ROOT / 'results/event_level_v2'
FOLDS = {'dev_fold_01_usa': ('USA', 174, 69),
         'dev_fold_02_sri_lanka': ('Sri-Lanka', 201, 42),
         'dev_fold_03_spain': ('Spain', 213, 30)}
METHODS = ['baseline', 'v2a_eventbalanced', 'v2b_coverage']
SEEDS = [42, 123, 777]
EXPECTED = {'Mekong': 30, 'Nigeria': 18, 'Pakistan': 28, 'Somalia': 26,
            'Spain': 30, 'Sri-Lanka': 42, 'USA': 69}
checks, sources, metrics = [], {}, []


def relative(p):
    return str(Path(p).resolve().relative_to(ROOT))


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def source(p):
    p = Path(p).resolve()
    key = relative(p)
    if key not in sources:
        sources[key] = {'path': key, 'sha256': sha(p), 'size_bytes': p.stat().st_size}
    return p


def read_json(p):
    return json.loads(source(p).read_text())


def read_csv(p):
    with source(p).open(newline='') as f:
        return list(csv.DictReader(f))


def write_csv(p, rows):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        p.write_text('')
        return
    with p.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def check(name, good, detail=''):
    checks.append({'check': name, 'status': 'PASS' if bool(good) else 'FAIL', 'detail': str(detail)})


def close(a, b, tol=1e-10):
    return math.isclose(float(a), float(b), abs_tol=tol, rel_tol=0)


def add_metric(metric_id, value, unit, scope, n, path, selector, formula):
    metrics.append(dict(metric_id=metric_id, value=value, display=f'{value:.4f}' if isinstance(value, float) else value,
                        unit=unit, scope=scope, sample_size=n, source=relative(path),
                        selector=selector, calculation=formula))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--recheck-previews', action='store_true')
    args = ap.parse_args()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('MPLCONFIGDIR', '/private/tmp/floodai-mpl')
    sys.path.insert(0, str(ROOT))
    import numpy as np
    import torch
    import rasterio
    import train_sar_unet as trainer
    torch.set_num_threads(2)
    source(ROOT / 'train_sar_unet.py')
    source(ROOT / 'train_v2a_eventbalanced.py')
    source(ROOT / 'train_v2b_coverage.py')
    source(ROOT / 'm76b_water_sampler.py')
    source(ROOT / 'm80a_dev_ensemble_uq.py')
    source(ROOT / 'm80b_dev_uncertainty_audit.py')
    for p in [ROOT/'README_START_HERE_TH.md',R/'m81_integrated_dev_evidence/m81_report_th.md',
              R/'m80b_dev_uncertainty_audit/m80b_report.md',R/'m70d_protocol_freeze/m70d_frozen_protocol.md']:
        source(p)
    base_ast=ast.parse((ROOT/'train_sar_unet.py').read_text())
    b_ast=ast.parse((ROOT/'train_v2b_coverage.py').read_text())
    for name in ['SarWaterDataset','SmallUNet','conv_block','masked_bce_dice','evaluate','seed_all']:
        a=next(n for n in base_ast.body if getattr(n,'name',None)==name)
        b=next(n for n in b_ast.body if getattr(n,'name',None)==name)
        check('baseline_v2b_same_code_'+name,ast.dump(a)==ast.dump(b))
    print('Auditing frozen files and development split membership...', flush=True)

    frozen = read_json(R / 'm70d_protocol_freeze/m70d_frozen_protocol.json')
    frozen_rows = []
    for key, spec in frozen['hashes'].items():
        path = ROOT / spec['path']
        actual = sources.get(relative(path), {}).get('sha256') or sha(path)
        frozen_rows.append(dict(identifier=key, path=spec['path'], expected_sha256=spec['sha256'],
                                actual_sha256=actual, match=(actual == spec['sha256'])))
    check('frozen_500_file_hashes', all(r['match'] for r in frozen_rows), f'{sum(r["match"] for r in frozen_rows)}/{len(frozen_rows)}')
    for r in frozen_rows:
        sources[r['path']] = {'path': r['path'], 'sha256': r['actual_sha256'], 'size_bytes': (ROOT/r['path']).stat().st_size}
    fp = hashlib.sha256(json.dumps(frozen['hashes'], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    check('frozen_fingerprint_internal', fp == frozen['fingerprint'], fp)
    check('recorded_manual_signoffs', all(frozen['manual_signoff'].values()), frozen['frozen_at'])
    write_csv(EVIDENCE / 'frozen_file_checks.csv', frozen_rows)

    unique, split_rows = {}, []
    roots = ROOT / 'data/sen1floods11/v2_development_roots'
    fold_records = {}
    for fold, (event, nt, nv) in FOLDS.items():
        parts = {}
        for split in ['train', 'valid', 'test', 'bolivia']:
            p = source(roots/fold/'splits'/f'flood_{split}_data.csv')
            with p.open(newline='') as f:
                rows = [row for row in csv.reader(f) if row]
            parts[split] = rows
            check(f'{fold}_{split}_count', len(rows) == {'train': nt, 'valid': nv}.get(split, 0), len(rows))
        train_ids, valid_ids = ({x[0] for x in parts[k]} for k in ['train', 'valid'])
        train_events = {n.split('_')[0] for n in train_ids}
        valid_events = {n.split('_')[0] for n in valid_ids}
        check(f'{fold}_disjoint', not train_ids & valid_ids and not train_events & valid_events)
        check(f'{fold}_events', valid_events == {event} and train_events == set(EXPECTED)-{event})
        check(f'{fold}_no_duplicates', len(train_ids) == nt and len(valid_ids) == nv)
        fold_records[fold] = parts
        split_rows.append(dict(fold=fold, validation_event=event, train_count=nt, valid_count=nv,
                               test_stub_count=len(parts['test']), bolivia_stub_count=len(parts['bolivia']),
                               train_events=';'.join(sorted(train_events))))
        for image, label in parts['train'] + parts['valid']:
            check(f'paired_name_{fold}_{image}', image.replace('_S1Hand.tif', '') == label.replace('_LabelHand.tif', ''))
            unique[image] = ((roots/fold/'S1Hand'/image).resolve(), (roots/fold/'LabelHand'/label).resolve())
    check('development_inventory', Counter(n.split('_')[0] for n in unique) == EXPECTED, len(unique))
    write_csv(EVIDENCE/'verified_splits.csv', split_rows)

    data_rows = []
    raw_index = {}
    for image, (im, lab) in sorted(unique.items()):
        source(im); source(lab)
        with rasterio.open(im) as src:
            x = src.read()
            valid_sar = np.isfinite(x).all(axis=0)
            if src.nodata is not None and np.isfinite(src.nodata):
                valid_sar &= np.all(x != src.nodata, axis=0)
            imspec = (src.crs, src.transform, src.width, src.height)
            desc = str(src.descriptions)
            units = str(src.units)
            nodata = src.nodata
        with rasterio.open(lab) as src:
            y = src.read(1)
            labspec = (src.crs, src.transform, src.width, src.height)
            label_nodata = src.nodata
        valid = valid_sar & (y != -1)
        # GeoTIFF affine coefficients differ at floating-point roundoff scale.
        # Compare all four corner positions in pixel units; never demand bit equality.
        corners=[(0,0),(512,0),(0,512),(512,512)]
        pixel_scale=min(abs(imspec[1].a),abs(imspec[1].e))
        max_grid_delta=max(max(abs(a-b) for a,b in zip(imspec[1]*xy,labspec[1]*xy)) for xy in corners)/pixel_scale
        aligned=imspec[0]==labspec[0] and imspec[2:]==labspec[2:] and max_grid_delta<1e-6
        good = x.shape == (2, 512, 512) and y.shape == (512, 512) and np.isin(y, [-1, 0, 1]).all() and aligned and desc=="('VV', 'VH')"
        check(f'raster_{image}', good, f'max corner displacement={max_grid_delta:.3g} pixels; tolerance=1e-6 pixels')
        row = dict(image=image, event=image.split('_')[0], valid_pixels=int(valid.sum()),
                   water_pixels=int(((y == 1)&valid).sum()), land_pixels=int(((y == 0)&valid).sum()),
                   ignored_label_pixels=int((y == -1).sum()), invalid_sar_pixels=int((~valid_sar).sum()),
                   sar_nodata=nodata, label_nodata=label_nodata, band_descriptions=desc, band_units=units,
                   grid_aligned=aligned, grid_bit_identical=imspec==labspec,max_grid_delta_pixels=max_grid_delta,
                   labels=';'.join(map(str,np.unique(y))),
                   sar_path=relative(im), label_path=relative(lab))
        data_rows.append(row)
        raw_index[image] = row
    write_csv(EVIDENCE/'verified_rasters.csv', data_rows)
    print('Auditing all 27 checkpoints/configs/histories...', flush=True)
    runs = []
    states = {}
    for method in METHODS:
        for seed in SEEDS:
            for fold, (event, nt, nv) in FOLDS.items():
                run = R/f'{method}_seed{seed}'/fold
                hp, cp = run/'history.csv', run/'best_sar_unet.pt'
                hist = read_csv(hp)
                config = read_json(run/('run_config_v2a.json' if method=='v2a_eventbalanced' else 'run_config.json'))
                c = torch.load(source(cp), map_location='cpu', weights_only=True)
                best, bestval = None, -1.
                for ep in hist:
                    v = float(ep['val_iou'])
                    if math.isfinite(v) and v > bestval + 1e-5:
                        best, bestval = ep, v
                mt = c['validation_metrics']
                tp, fp_, fn = (int(mt[k]) for k in ['tp','fp','fn'])
                iou = tp/(tp+fp_+fn)
                config_good = (config.get('epochs',config.get('max_epochs')) == 25
                               and config['batch_size']==2 and config['crop_size']==256
                               and config['base_channels']==16 and config['patience']==6
                               and config.get('lr',config.get('learning_rate'))==0.0003
                               and config['seed']==seed and not config.get('max_train',0)
                               and not config.get('max_val',0) and not config.get('smoke',False))
                expected_model = trainer.SmallUNet(16)
                expected_model.load_state_dict(c['model_state'], strict=True)
                check(f'finite_weights_{method}_{seed}_{fold}',all(torch.isfinite(v).all().item() for v in c['model_state'].values()))
                nparams = sum(p.numel() for p in expected_model.parameters())
                good = (c['architecture']=='SmallUNet' and c['base_channels']==16 and c['seed']==seed
                        and c['train_count']==nt and c['valid_count']==nv and mt['batches']==nv
                        and c['epoch']==int(best['epoch']) and close(iou,bestval)
                        and close(iou,mt['iou']) and c['threshold']==.5
                        and c['db_min']==[-35,-40] and c['db_max']==[5,0]
                        and c['label_scheme']=={'ignore':-1,'non_water':0,'water':1}
                        and nparams==1963953 and config_good)
                for field, value in [('f1',2*tp/(2*tp+fp_+fn)),('recall',tp/(tp+fn)),('precision',tp/(tp+fp_))]:
                    good = good and close(value,mt[field]) and close(value,best['val_'+field])
                # Verify actual early-stopping record, not merely a configured maximum.
                good = good and [int(ep['epoch']) for ep in hist]==list(range(1,len(hist)+1))
                good = good and (len(hist)==25 or len(hist)-int(best['epoch'])==6)
                check(f'checkpoint_{method}_{seed}_{fold}',good,f'epoch={c["epoch"]}; IoU={iou}')
                if method=='v2a_eventbalanced':
                    check(f'v2a_source_{seed}_{fold}',config['train_source_sha256']==sha(ROOT/'train_sar_unet.py') and config['v2_source_sha256']==sha(ROOT/'train_v2a_eventbalanced.py'))
                    exposure = read_csv(run/'sampled_events_by_epoch.csv')
                    check(f'v2a_draws_{seed}_{fold}',all(sum(int(row['sampled_count']) for row in exposure if int(row['epoch'])==int(ep['epoch']))==nt for ep in hist))
                elif method=='v2b_coverage':
                    sampler = read_json(run/'m76b_sampler_manifest.json')
                    designp=source(R/'m76a_dg_design_freeze/m76a_v2b_design_frozen.json')
                    auditp=source(R/'m75d_v2b_design_audit/m75d_train_per_chip.csv')
                    check(f'v2b_source_{seed}_{fold}',sampler['trainer_v2b_sha256']==sha(ROOT/'train_v2b_coverage.py') and sampler['frozen_design_sha256']==sha(designp) and sampler['train_audit_sha256']==sha(auditp) and sampler['seed']==seed and sampler['n_train']==nt and sampler['replacement'] is True and sampler['num_samples_per_epoch']==nt)
                    source(run/'m76b_train_sampling_weights.csv')
                runs.append(dict(method=method,seed=seed,fold=fold,event=event,train_count=nt,valid_count=nv,
                                 trained_epochs=len(hist),checkpoint_epoch=c['epoch'],iou=iou,
                                 recall=mt['recall'],precision=mt['precision'],f1=mt['f1'],parameters=nparams,
                                 checkpoint_sha256=sha(cp),history=relative(hp),checkpoint=relative(cp),
                                 status='PASS' if good else 'FAIL'))
                if method=='baseline': states[(fold,seed)] = c['model_state']
    write_csv(EVIDENCE/'verified_runs.csv',runs)
    models, events, seed_macros = [], [], []
    for method in METHODS:
        macros=[]
        for seed in SEEDS:
            val=st.mean(r['iou'] for r in runs if r['method']==method and r['seed']==seed)
            macros.append(val)
            seed_macros.append(dict(method=method,seed=seed,macro_dev_iou=val))
        avg, sd = st.mean(macros),st.stdev(macros)
        models.append(dict(method=method,macro_dev_iou=avg,seed_macro_sample_sd=sd))
        add_metric(method+'_macro',avg,'IoU','DEV_ONLY','3 events x 3 seeds',R/f'{method}_seed42'/next(iter(FOLDS))/'history.csv',f'verified_runs method={method}','mean_seed(mean_3_event(IoU)); 27 source paths in verified_runs.csv')
        add_metric(method+'_sd',sd,'IoU','DEV_ONLY','3 seed macro scores',R/f'{method}_seed42'/next(iter(FOLDS))/'history.csv',f'verified_seed_macros method={method}','sample SD (ddof=1) of the 3 seed macro scores')
        for fold,(event,_,_) in FOLDS.items():
            v=[r['iou'] for r in runs if r['method']==method and r['fold']==fold]
            events.append(dict(method=method,event=event,mean_iou=st.mean(v),sample_sd=st.stdev(v)))
    for row in models: row['delta_vs_baseline']=row['macro_dev_iou']-models[0]['macro_dev_iou']
    old=read_csv(R/'m81_integrated_dev_evidence/m81_models.csv')
    check('m81_model_numbers',all(close(a['macro_dev_iou'],b['mean_of_seed_macro_dev_iou']) and close(a['seed_macro_sample_sd'],b['sd_across_three_seed_macros']) for a,b in zip(models,old)))
    write_csv(EVIDENCE/'verified_models.csv',models)
    write_csv(EVIDENCE/'verified_events.csv',events)
    write_csv(EVIDENCE/'verified_seed_macros.csv',seed_macros)

    print('Checking 141 ensemble rows and nine stored pixel arrays...', flush=True)
    ensemble_dir=R/'m80a_dev_ensemble_uq'
    imgs=read_csv(ensemble_dir/'m80a_dev_per_image.csv')
    full=read_csv(ensemble_dir/'m80a_dev_by_event.csv')
    manifest=read_json(ensemble_dir/'m80a_manifest.json')
    members=read_csv(ensemble_dir/'m80a_members.csv')
    check('ensemble_member_identity',len(members)==9 and all(sha(ROOT/m['checkpoint'])==m['checkpoint_sha256'] for m in members))
    check('ensemble_source_hash',sha(ROOT/'m80a_dev_ensemble_uq.py')==manifest['source_script_sha256'])
    check('ensemble_complete',len(imgs)==141 and manifest['status']=='COMPLETE_3_FOLD_DEV_ONLY')
    for fold,(event,_,nv) in FOLDS.items():
        sub=[r for r in imgs if r['fold']==fold]
        summary=next(r for r in full if r['fold']==fold)
        check(f'ensemble_{fold}_membership',len(sub)==nv and len({r['image'] for r in sub})==nv and {r['image'] for r in sub}=={r[0] for r in fold_records[fold]['valid']})
        for row in sub:
            tp,tn,fp_,fn=(int(row[k]) for k in ['tp','tn','fp','fn'])
            union=tp+fp_+fn
            raw=raw_index[row['image']]
            good=(tp+tn+fp_+fn==int(row['valid_pixels'])==raw['valid_pixels']
                  and tp+fn==int(row['gt_water_pixels'])==raw['water_pixels']
                  and int(row['n_members'])==3)
            good=good and (close(tp/union,row['iou']) if union else math.isnan(float(row['iou'])))
            check('ensemble_row_'+row['image'],good)
        for k in ['tp','tn','fp','fn','valid_pixels','gt_water_pixels','fn_p_lt_0_1_count']:
            check(f'ensemble_sum_{fold}_{k}',sum(int(r[k]) for r in sub)==int(summary[k]))
        for k in ['brier','mean_predictive_entropy_bits','mean_member_entropy_bits','mean_mutual_information_bits','mean_probability_variance']:
            value=sum(float(r[k])*int(r['valid_pixels']) for r in sub)/int(summary['valid_pixels'])
            check(f'ensemble_weighted_{fold}_{k}',close(value,summary[k],1e-8))
        check(f'ensemble_iou_{fold}',close(float(summary['tp'])/(int(summary['tp'])+int(summary['fp'])+int(summary['fn'])),summary['iou']))
        check(f'ensemble_mi_{fold}',close(float(summary['mean_predictive_entropy_bits'])-float(summary['mean_member_entropy_bits']),summary['mean_mutual_information_bits'],1e-7))
    ensemble_macro=st.mean(float(r['iou']) for r in full)
    check('ensemble_macro',close(ensemble_macro,manifest['macro_iou_3_dev_events']))
    add_metric('ensemble_macro',ensemble_macro,'IoU','DEV_ONLY','3 events; 141 chips',ensemble_dir/'m80a_dev_by_event.csv','all 3 rows, iou','unweighted mean over 3 event-level IoUs')
    add_metric('ensemble_delta',ensemble_macro-models[0]['macro_dev_iou'],'IoU points','DESCRIPTIVE_DEV_ONLY','different estimands',ensemble_dir/'m80a_dev_by_event.csv','ensemble macro minus baseline seed-mean macro','IoU(mean probabilities) compared with mean(IoU), no significance claim')
    write_csv(EVIDENCE/'verified_ensemble_events.csv',full)

    # Independently rederive stored-array confusion, uncertainty and top-10% capture.
    # No call to the previous M8.0B aggregation code is needed.
    selected=[]
    re_inference=[]
    case_reference=read_csv(R/'m74b_high_water_diagnostics/m74b_image_seed_diagnostics.csv')
    for path in sorted((ensemble_dir/'previews').glob('dev_fold_*/*.npz')):
        source(path)
        fold=path.parent.name
        image=path.name.removesuffix('_ensemble.npz')+'.tif'
        row=next(r for r in imgs if r['fold']==fold and r['image']==image)
        with np.load(path,allow_pickle=False) as data:
            arrays={k:data[k] for k in data.files}
        v=arrays['valid'].astype(bool)
        y=arrays['gt_water'][v].astype(bool)
        p=arrays['p_water'][v].astype(np.float64)
        ent=arrays['predictive_entropy_bits'][v].astype(np.float64)
        mi=arrays['mutual_information_bits'][v].astype(np.float64)
        expected=arrays['expected_entropy_bits'][v].astype(np.float64)
        pred=p>=.5
        err=pred!=y
        counts={'tp':int((pred&y).sum()),'tn':int((~pred&~y).sum()),'fp':int((pred&~y).sum()),'fn':int((~pred&y).sum())}
        q=np.clip(p,1e-7,1-1e-7)
        recomputed_ent=-(q*np.log2(q)+(1-q)*np.log2(1-q))
        check('npz_counts_'+image,all(counts[k]==int(row[k]) for k in counts))
        check('npz_entropy_'+image,np.max(abs(ent-recomputed_ent))<2e-6)
        check('npz_mi_'+image,np.max(abs(mi-np.maximum(ent-expected,0)))<2e-7)
        check('npz_brier_'+image,close(float(((p-y)**2).mean()),row['brier'],1e-10))
        k=max(1,math.ceil(len(p)*.1))
        top_ent=np.argpartition(ent,len(p)-k)[len(p)-k:]
        top_mi=np.argpartition(mi,len(p)-k)[len(p)-k:]
        selected.append(dict(event=row['validation_event'],image=image,valid_pixels=len(p),errors=int(err.sum()),top10_pixels=k,
                             entropy_top10_errors=int(err[top_ent].sum()),mi_top10_errors=int(err[top_mi].sum()),
                             entropy_capture=float(err[top_ent].sum()/err.sum()),mi_capture=float(err[top_mi].sum()/err.sum())))
        if args.recheck_previews:
            print('CPU recheck:',image,flush=True)
            rec=next(r for r in trainer.split_records(roots/fold,'valid') if r[0].name==image)
            x_t,y_t,v_t=trainer.SarWaterDataset([rec],augment=False)[0]
            check('npz_gt_valid_'+image,np.array_equal(v_t.numpy()[0],v) and np.array_equal(y_t.numpy()[0]>=.5,arrays['gt_water']))
            probs=[]
            for seed in SEEDS:
                model=trainer.SmallUNet(16)
                model.load_state_dict(states[(fold,seed)],strict=True)
                model.eval()
                with torch.inference_mode():
                    probs.append(torch.sigmoid(model(x_t.unsqueeze(0))).numpy()[0,0])
                ref=next((r for r in case_reference if r['image']==image and int(r['seed'])==seed),None)
                if ref is not None:
                    gt_full=y_t.numpy()[0]>=.5
                    pr=probs[-1]>=.5
                    counts_new={'tp':int((pr & gt_full & v).sum()),'tn':int((~pr & ~gt_full & v).sum()),
                                'fp':int((pr & ~gt_full & v).sum()),'fn':int((~pr & gt_full & v).sum())}
                    check(f'cpu_highwater_case_{image}_{seed}',all(counts_new[k]==int(ref[k]) for k in counts_new))
            stack=np.stack(probs).astype(np.float64)
            newp=np.mean(stack,axis=0).astype(np.float32)
            diff=float(np.max(abs(newp[v]-arrays['p_water'][v])))
            flips=int(np.count_nonzero((newp[v]>=.5)!=(arrays['p_water'][v]>=.5)))
            def h(prob):
                q=np.clip(prob,1e-7,1-1e-7)
                return -(q*np.log2(q)+(1-q)*np.log2(1-q))
            fresh_ent=h(stack.mean(axis=0))
            fresh_expected=h(stack).mean(axis=0)
            fresh_mi=np.maximum(fresh_ent-fresh_expected,0)
            fresh_variance=stack.var(axis=0)
            uq_diff={key:float(np.max(abs(arr[v]-arrays[key][v]))) for key,arr in [
                ('predictive_entropy_bits',fresh_ent),('expected_entropy_bits',fresh_expected),
                ('mutual_information_bits',fresh_mi),('variance',fresh_variance)]}
            re_inference.append(dict(image=image,fold=fold,max_probability_abs_difference=diff,threshold_disagreements=flips,
                                     max_entropy_abs_difference=uq_diff['predictive_entropy_bits'],
                                     max_member_entropy_abs_difference=uq_diff['expected_entropy_bits'],
                                     max_mi_abs_difference=uq_diff['mutual_information_bits'],
                                     max_variance_abs_difference=uq_diff['variance'],device='cpu',stored_device='mps'))
            check('cpu_preview_probability_'+image,diff<1e-4 and flips==0,f'max_abs={diff}; threshold flips={flips}')
            check('cpu_preview_uncertainty_'+image,max(uq_diff.values())<1e-5,str(uq_diff))
    write_csv(EVIDENCE/'verified_selected_uq_images.csv',selected)
    if args.recheck_previews: write_csv(EVIDENCE/'cpu_preview_recheck.csv',re_inference)
    selected_events=[]
    old_selected=read_csv(R/'m80b_dev_uncertainty_audit/m80b_selected_preview_by_event.csv')
    for event in ['USA','Sri-Lanka','Spain']:
        sub=[r for r in selected if r['event']==event]
        total_err=sum(r['errors'] for r in sub)
        e=sum(r['entropy_top10_errors'] for r in sub)/total_err
        m=sum(r['mi_top10_errors'] for r in sub)/total_err
        prior=next(r for r in old_selected if r['event']==event)
        check('selected_capture_'+event,len(sub)==3 and close(e,prior['entropy_top10pct_error_capture']) and close(m,prior['mi_top10pct_error_capture']))
        selected_events.append(dict(event=event,n_selected=3,total_errors=total_err,entropy_capture=e,mi_capture=m,scope='SELECTED_9_ONLY'))
    write_csv(EVIDENCE/'verified_selected_uq_events.csv',selected_events)
    audit_manifest=read_json(R/'m80b_dev_uncertainty_audit/m80b_manifest.json')
    check('m80b_input_hashes',all(sha(ensemble_dir/k)==v for k,v in audit_manifest['input_file_sha256'].items()))

    # Verify actual water fractions and all 9 per-run TRAIN-only coverage plans.
    weights_rows=[]
    for seed in SEEDS:
        for fold,(event,nt,nv) in FOLDS.items():
            path=R/f'v2b_coverage_seed{seed}'/fold/'m76b_train_sampling_weights.csv'
            plan=read_csv(path)
            def water_bin(f):
                return 'zero_water' if f==0 else 'water_0_to_1pct' if f<.01 else 'water_1_to_10pct' if f<.1 else 'water_10_to_50pct' if f<.5 else 'water_ge_50pct'
            bins=Counter(water_bin(raw_index[r['image']]['water_pixels']/raw_index[r['image']]['valid_pixels']) for r in plan)
            good=len(plan)==nt and {r['image'] for r in plan}=={r[0] for r in fold_records[fold]['train']}
            for r in plan:
                raw=raw_index[r['image']]
                fraction=raw['water_pixels']/raw['valid_pixels']
                b=water_bin(fraction)
                good=good and close(fraction,r['water_fraction']) and b==r['water_bin'] and close(float(r['draw_probability']),.5/nt+.5/(5*bins[b]))
            check(f'coverage_weights_{seed}_{fold}',good)
            if seed==42:
                for b,n in bins.items():weights_rows.append(dict(fold=fold,water_bin=b,n_chips=n,draw_probability_mass=.5*n/nt+.1))
    write_csv(EVIDENCE/'verified_coverage_bins.csv',weights_rows)

    case=read_csv(R/'m74b_high_water_diagnostics/m74b_image_seed_diagnostics.csv')
    for c in case:
        raw=raw_index[c['image']]
        tp,fp_,fn=(int(c[k]) for k in ['tp','fp','fn'])
        check('case_'+c['image']+'_'+c['seed'],int(c['gt_water_pixels'])==raw['water_pixels'] and close(raw['water_pixels']/raw['valid_pixels'],c['water_fraction_gt']) and close(tp/(tp+fp_+fn),c['iou']))
    write_csv(EVIDENCE/'verified_high_water_cases.csv',case)
    source(ROOT/'data/sen1floods11/metadata/Sen1Floods11_Metadata.geojson')

    print('Building data charts and copying selected source figures...',flush=True)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':13,'axes.spines.top':False,'axes.spines.right':False,'savefig.bbox':'tight'})
    colors=['#24679B','#D28B39','#2E8B74']
    fig,ax=plt.subplots(figsize=(9,4.7))
    vals=[r['macro_dev_iou'] for r in models]
    ax.bar(['Baseline','V2-A','V2-B'],vals,yerr=[r['seed_macro_sample_sd'] for r in models],capsize=7,color=colors,width=.55)
    for i,v in enumerate(vals):ax.text(i,v+.072,f'{v:.4f}',ha='center',fontweight='bold')
    ax.set_ylim(0,.85);ax.set_ylabel('Macro DEV water IoU');ax.set_title('Sampling comparison on development validation')
    fig.text(.5,-.015,'Error bars: sample SD across 3 seed macro scores. 3 events. DEV only.',ha='center',fontsize=11)
    fig.savefig(FIGURES/'01_sampling_macro_iou.png',dpi=220);plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,4.7))
    xs=np.arange(3)
    for j,method in enumerate(METHODS):
        ev=[next(r for r in events if r['method']==method and r['event']==e) for e in ['USA','Sri-Lanka','Spain']]
        ax.bar(xs+(j-1)*.25,[r['mean_iou'] for r in ev],width=.24,yerr=[r['sample_sd'] for r in ev],capsize=3,color=colors[j],label=['Baseline','V2-A','V2-B'][j])
    ax.set_xticks(xs,['USA','Sri Lanka','Spain']);ax.set_ylim(0,.9);ax.set_ylabel('Event DEV water IoU');ax.legend(ncol=3,loc='upper left');ax.set_title('Event scores and variability across three seeds')
    fig.text(.5,-.015,'Error bars: sample SD across 3 seeds within each event. DEV only.',ha='center',fontsize=11)
    fig.savefig(FIGURES/'02_event_iou.png',dpi=220);plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,4.7))
    for j,method in enumerate(METHODS):
        v=[next(r['iou'] for r in runs if r['method']==method and r['seed']==s and r['event']=='Sri-Lanka') for s in SEEDS]
        ax.plot(range(3),v,'o-',label=['Baseline','V2-A','V2-B'][j],color=colors[j],linewidth=2)
    ax.set_xticks(range(3),list(map(str,SEEDS)));ax.set_xlabel('Random seed (categorical)');ax.set_ylabel('Sri Lanka DEV water IoU');ax.set_ylim(0,.85);ax.legend();ax.set_title('Sri Lanka sensitivity to training seed')
    fig.savefig(FIGURES/'03_sri_lanka_seeds.png',dpi=220);plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,4.7))
    single=[next(r['mean_iou'] for r in events if r['method']=='baseline' and r['event']==e) for e in ['USA','Sri-Lanka','Spain']]
    ens=[float(r['iou']) for r in full]
    ax.bar(xs-.17,single,.34,label='Mean of 3 single-model IoUs',color=colors[0]);ax.bar(xs+.17,ens,.34,label='IoU of probability ensemble',color=colors[2])
    for i,(a,b) in enumerate(zip(single,ens)):
        ax.text(i-.17,a+.012,f'{a:.4f}',ha='center',fontsize=11);ax.text(i+.17,b+.012,f'{b:.4f}',ha='center',fontsize=11)
    ax.set_xticks(xs,['USA','Sri Lanka','Spain']);ax.set_ylim(0,.9);ax.set_ylabel('DEV water IoU');ax.legend(loc='upper left',fontsize=10);ax.set_title('Baseline single models and three-seed ensemble')
    fig.text(.5,-.015,'Descriptive comparison of different estimands. No independent TEST.',ha='center',fontsize=11)
    fig.savefig(FIGURES/'04_ensemble_comparison.png',dpi=220);plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,4.7))
    ax.bar(xs-.17,[100*r['entropy_capture'] for r in selected_events],.34,label='Predictive entropy',color=colors[0]);ax.bar(xs+.17,[100*r['mi_capture'] for r in selected_events],.34,label='Mutual information',color=colors[1])
    ax.set_xticks(xs,['USA','Sri Lanka','Spain']);ax.set_ylim(0,100);ax.set_ylabel('Errors captured (%)');ax.legend();ax.set_title('Top 10% uncertainty per image: selected previews only')
    fig.text(.5,-.015,'9 selected images, 3 per event. Pooled captured errors / pooled errors.',ha='center',fontsize=11)
    fig.savefig(FIGURES/'05_selected_error_capture.png',dpi=220);plt.close(fig)
    copied={
        '06_sri_lanka_learning_curves.png':R/'m74_stability_diagnostics/m74_dev_fold_02_sri_lanka_training_curves.png',
        '07_sri_lanka_seed_failure.png':R/'m74b_high_water_diagnostics/m74b_Sri-Lanka_534068_comparison.png',
        '11_input_vv_vh_gt.png':R/'m75d_v2b_design_audit/Sri-Lanka_713926_inputs_gt.png'}
    figrows=[]
    for dest,origin in copied.items():
        source(origin);shutil.copy2(origin,FIGURES/dest)
        check('figure_copy_'+dest,sha(origin)==sha(FIGURES/dest))
        figrows.append(dict(figure='assets/figures/'+dest,kind='byte-identical source figure',source=relative(origin),source_sha256=sha(origin),output_sha256=sha(FIGURES/dest),scope='DEV_ONLY',note='Selected example; not representative'))
    # Render numerical results as scientific plots with legible color scales.
    # These plots use stored NPZ data, not image editing or synthetic reconstruction.
    uq_examples=[('08_sri_lanka_ensemble_uq.png','dev_fold_02_sri_lanka','Sri-Lanka_534068'),
                 ('09_usa_ensemble_uq.png','dev_fold_01_usa','USA_1010394'),
                 ('10_spain_ensemble_uq.png','dev_fold_03_spain','Spain_1167260')]
    for dest,fold,stem in uq_examples:
        npz=ensemble_dir/'previews'/fold/(stem+'_S1Hand_ensemble.npz')
        with np.load(npz,allow_pickle=False) as data:
            ar={k:data[k] for k in data.files}
        valid=ar['valid'].astype(bool)
        rec=next(r for r in trainer.split_records(roots/fold,'valid') if r[0].name==stem+'_S1Hand.tif')
        x,_,_=trainer.SarWaterDataset([rec],augment=False)[0]
        plots=[(x.numpy()[0],'VV input (normalized)','gray','Scaled VV'),
               (ar['gt_water'].astype(float),'Surface-water ground truth','Blues','Water label'),
               (ar['p_water'],'Ensemble P(water)','viridis','Probability'),
               ((ar['p_water']>=.5).astype(float),'Prediction at threshold 0.50','Blues','Water label'),
               (ar['predictive_entropy_bits'],'Predictive entropy','magma','Bits'),
               (ar['mutual_information_bits'],'Ensemble disagreement (MI)','magma','Bits')]
        fig,axs=plt.subplots(2,3,figsize=(14,9),layout='constrained')
        for ax,(array,title,cmap_name,bar_label) in zip(axs.flat,plots):
            cmap=plt.get_cmap(cmap_name).copy();cmap.set_bad('#BDBDBD')
            artist=ax.imshow(np.ma.masked_where(~valid,array),cmap=cmap,vmin=0,vmax=1,interpolation='nearest')
            ax.set_title(title,fontsize=13);ax.set_axis_off()
            cb=fig.colorbar(artist,ax=ax,shrink=.76,pad=.025)
            cb.set_label(bar_label,fontsize=10);cb.ax.tick_params(labelsize=9)
        fig.suptitle(f'{stem}: selected DEV example, Baseline three-seed ensemble\nGray = ignored/invalid pixels. Surface-water label: 0 land, 1 water. All scales fixed 0–1.',fontsize=15)
        fig.savefig(FIGURES/dest,dpi=180);plt.close(fig)
        figrows.append(dict(figure='assets/figures/'+dest,kind='rendered stored-array scientific figure',source='../'+relative(npz),source_sha256=sha(npz),output_sha256=sha(FIGURES/dest),scope='SELECTED_DEV_EXAMPLE',note='Arrays unchanged; normalized VV from '+relative(rec[0])+'; masks from NPZ; fixed 0–1 color scales'))
    for name,origin in [('01_sampling_macro_iou.png','evidence/verified_models.csv'),('02_event_iou.png','evidence/verified_events.csv'),('03_sri_lanka_seeds.png','evidence/verified_runs.csv'),('04_ensemble_comparison.png','evidence/verified_ensemble_events.csv'),('05_selected_error_capture.png','evidence/verified_selected_uq_events.csv')]:
        figrows.append(dict(figure='assets/figures/'+name,kind='recomputed data chart',source=origin,source_sha256=sha(OUT/origin),output_sha256=sha(FIGURES/name),scope='SELECTED_9_ONLY' if name.startswith('05') else 'DEV_ONLY',note='Generated by scripts/build_presentation_evidence.py'))
    write_csv(OUT/'assets/figure_sources.csv',sorted(figrows,key=lambda r:r['figure']))
    # Extend the numerical registry to cover the tables and examples in the slide pack.
    for row in runs:
        add_metric(f"run_{row['method']}_{row['seed']}_{row['event']}",row['iou'],'IoU','DEV_ONLY',row['valid_count'],ROOT/row['checkpoint'],'validation_metrics.tp/fp/fn','TP/(TP+FP+FN); checkpoint selected with improvement >1e-5')
    for row in events:
        add_metric(f"event_{row['method']}_{row['event']}",row['mean_iou'],'IoU','DEV_ONLY','3 seeds',EVIDENCE/'verified_runs.csv',f"method={row['method']}; event={row['event']}",'mean over 3 seed IoUs')
    for row in full:
        for key in ['iou','recall','brier','mean_predictive_entropy_bits','mean_mutual_information_bits','fn_p_lt_0_1_share_of_gt_water']:
            add_metric(f"ensemble_{row['validation_event']}_{key}",float(row[key]),'bits' if 'bits' in key else 'ratio','DEV_ONLY',row['n_images'],ensemble_dir/'m80a_dev_by_event.csv',f"validation_event={row['validation_event']}; {key}",'event totals or valid-pixel-weighted means; see verification checks')
    for row in selected_events:
        for key in ['entropy_capture','mi_capture']:
            add_metric(f"selected_{row['event']}_{key}",row[key],'fraction of errors','SELECTED_9_ONLY',3,EVIDENCE/'verified_selected_uq_images.csv',f"event={row['event']}",'sum errors captured in per-image top10% / sum all errors in 3 selected images')
    for row in case:
        add_metric(f"case_{row['image']}_{row['seed']}",float(row['iou']),'IoU','SELECTED_CASE',1,R/'m74b_high_water_diagnostics/m74b_image_seed_diagnostics.csv',f"image={row['image']}; seed={row['seed']}",'TP/(TP+FP+FN)')
    write_csv(EVIDENCE/'verified_metrics.csv',metrics)
    write_csv(EVIDENCE/'checks.csv',checks)
    write_csv(EVIDENCE/'source_manifest.csv',sorted(sources.values(),key=lambda r:r['path']))
    summary=dict(checked_at_bangkok=datetime.now(ZoneInfo('Asia/Bangkok')).isoformat(),
                 checks=len(checks),passed=sum(c['status']=='PASS' for c in checks),failed=[c for c in checks if c['status']=='FAIL'],
                 frozen_files=len(frozen_rows),unique_dev_chips=len(unique),runs=len(runs),ensemble_images=len(imgs),
                 selected_npz=len(selected),cpu_preview_inference=len(re_inference),model_metrics=models,ensemble_macro=ensemble_macro,
                 limitations=['Full 141-chip ensemble inference was not repeated; raw masks/counts and aggregations checked.',
                              'No new training. No historical TEST or Thailand inference.',
                              'Frozen hashes prove byte identity to local record, not independent label truth or untouched TEST.',
                              'Official dataset documents VV/VH dB; local TIFF band units are not necessarily populated.',
                              'No statistical significance or causal claim; selected previews are not representative.'])
    (EVIDENCE/'verification_summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({**{k:summary[k] for k in ['checks','passed','runs','ensemble_images','selected_npz','cpu_preview_inference']},'failed_count':len(summary['failed']),'first_failures':summary['failed'][:5]},indent=2),flush=True)
    if summary['failed']:return 1
    return 0


if __name__=='__main__':
    raise SystemExit(main())
