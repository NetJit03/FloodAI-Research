#!/usr/bin/env python3
"""Reproduce M7.6D DEV-only analysis from the user's 27 history CSVs.
No test files, Bolivia files or Thailand data are accessed.
Requires Python standard library and matplotlib only for PNG output.
"""
from __future__ import annotations
from pathlib import Path
from io import StringIO
import csv, json, math, statistics as stats, zipfile, sys
from collections import defaultdict

ZIP_PATH=Path(sys.argv[1]) if len(sys.argv)>1 else Path('/mnt/data/m76d_dev_comparison.zip')
OUT=Path(sys.argv[2]) if len(sys.argv)>2 else Path('/mnt/data/m76d_results')
OUT.mkdir(parents=True, exist_ok=True)
MODELS=['baseline','v2a_eventbalanced','v2b_coverage']
LABELS={'baseline':'Baseline U-Net','v2a_eventbalanced':'V2-A Event-balanced','v2b_coverage':'V2-B Coverage'}
SEEDS=[42,123,777]
EVENTS=[('dev_fold_01_usa','USA'),('dev_fold_02_sri_lanka','Sri Lanka'),('dev_fold_03_spain','Spain')]
FIELDS=['epoch','train_loss','val_loss','val_iou','val_f1','val_recall','val_precision']
rows=[]
histories={}
configs_ok=[]
checks=[]
with zipfile.ZipFile(ZIP_PATH,'r') as z:
    names=set(z.namelist())
    for model in MODELS:
        for seed in SEEDS:
            for fold,event in EVENTS:
                base=f'results/event_level_v2/{model}_seed{seed}/{fold}/'
                histpath=base+'history.csv'
                if histpath not in names: raise RuntimeError(f'Missing required history: {histpath}')
                seq=[]
                with StringIO(z.read(histpath).decode('utf-8-sig')) as s:
                    reader=csv.DictReader(s)
                    if reader.fieldnames != FIELDS: raise ValueError(f'Unexpected headers {histpath}: {reader.fieldnames}')
                    for r in reader:
                        entry={k:(int(v) if k=='epoch' else float(v)) for k,v in r.items()}
                        if any(not math.isfinite(v) for v in entry.values()): raise ValueError(f'Non-finite values in {histpath}')
                        if not all(0<=entry[k]<=1 for k in ['val_iou','val_f1','val_recall','val_precision']):
                            raise ValueError(f'Unreasonable metric in {histpath}')
                        seq.append(entry)
                if not seq or [v['epoch'] for v in seq] != list(range(1,len(seq)+1)):
                    raise ValueError(f'Non-sequential epoch history: {histpath}')
                # Trainer best-epoch rule: strict improvement >1e-5; compute explicitly.
                bestval=-1.0; best=None
                for ep in seq:
                    if ep['val_iou']>bestval+1e-5:
                        bestval=ep['val_iou']; best=ep
                assert best is not None
                if seq[-1]['epoch']-best['epoch']!=6:
                    checks.append({'path':histpath,'issue':f'early stopping offset {seq[-1]["epoch"]-best["epoch"]}, not six'})
                row={'model':model,'method':LABELS[model],'seed':seed,'event':event,'fold':fold,
                     'epochs_run':len(seq),'selected_epoch':best['epoch'],
                     'val_iou':best['val_iou'],'val_f1':best['val_f1'],
                     'val_precision':best['val_precision'],'val_recall':best['val_recall'],
                     'val_loss':best['val_loss'],'history_path':histpath}
                rows.append(row)
                histories[(model,seed,event)]=seq
                cp=base+'run_config.json'
                if cp in names:
                    c=json.loads(z.read(cp))
                    good=(c.get('seed')==seed and c.get('max_train')==0 and c.get('max_val')==0
                       and c.get('epochs')==25 and c.get('patience')==6 and c.get('crop_size')==256
                       and c.get('batch_size')==2 and c.get('base_channels')==16 and abs(c.get('lr')-0.0003)<1e-12)
                    if not good: checks.append({'path':cp,'issue':'Unexpected run-config setting'})
                    configs_ok.append(cp)

by={(r['model'],r['seed'],r['event']):r for r in rows}
macro=[]
for model in MODELS:
    for seed in SEEDS:
        subset=[by[(model,seed,e)] for _,e in EVENTS]
        macro.append({'model':model,'method':LABELS[model],'seed':seed,
          'macro_val_iou':stats.mean(r['val_iou'] for r in subset),
          'macro_val_f1':stats.mean(r['val_f1'] for r in subset),
          'macro_val_recall':stats.mean(r['val_recall'] for r in subset),
          'macro_val_precision':stats.mean(r['val_precision'] for r in subset)})
macro_by={(r['model'],r['seed']):r for r in macro}
summary=[]
for model in MODELS:
    vals=[macro_by[(model,s)]['macro_val_iou'] for s in SEEDS]
    basevals=[macro_by[('baseline',s)]['macro_val_iou'] for s in SEEDS]
    diffs=[v-b for v,b in zip(vals,basevals)]
    summary.append({'model':model,'method':LABELS[model], 'mean_macro_val_iou':stats.mean(vals),
                    'sample_sd_across_seed_macro':stats.stdev(vals),'min_macro':min(vals),
                    'max_macro':max(vals),'paired_mean_delta_vs_baseline':stats.mean(diffs),
                    'delta_seed42':diffs[0],'delta_seed123':diffs[1],'delta_seed777':diffs[2]})
by_event=[]
for model in MODELS:
    for _,event in EVENTS:
        grp=[by[(model,s,event)] for s in SEEDS]
        base=[by[('baseline',s,event)] for s in SEEDS]
        diffs=[a['val_iou']-b['val_iou'] for a,b in zip(grp,base)]
        v=[r['val_iou'] for r in grp]
        by_event.append({'model':model,'method':LABELS[model], 'event':event,
         'mean_val_iou':stats.mean(v),'sd_val_iou_across_seeds':stats.stdev(v),
         'range_val_iou_across_seeds':max(v)-min(v),
         'mean_val_f1':stats.mean(r['val_f1'] for r in grp),
         'mean_val_precision':stats.mean(r['val_precision'] for r in grp),
         'mean_val_recall':stats.mean(r['val_recall'] for r in grp),
         'mean_delta_vs_baseline':stats.mean(diffs),
         'delta_seed42':diffs[0],'delta_seed123':diffs[1],'delta_seed777':diffs[2]})

def write_csv(name, data):
    with (OUT/name).open('w', newline='', encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
write_csv('m76d_all_27_selected_epochs.csv', rows)
write_csv('m76d_macro_by_seed.csv',macro)
write_csv('m76d_model_summary.csv',summary)
write_csv('m76d_event_summary.csv',by_event)

# User-readable report: method-level ranking + precise caveats.
fm=lambda n: f'{n:.4f}'
report=['# M7.6D — DEV-only comparison and research decision','',
'**ขอบเขต**: วิเคราะห์เฉพาะ `history.csv` ที่ส่งมา ไม่มีการ Train ใหม่ ไม่มีการอ่าน TEST/Bolivia/Thailand และไม่มีการปรับเกณฑ์ threshold',
'',
'## 1. Input audit',
'- Histories ครบ **27/27** (3 methods × 3 seeds × 3 event-disjoint DEV validation folds)',
'- Run configurations **18/27**: Baseline 9/9, V2-B 9/9, V2-A 0/9 (ไม่ได้รวมมาใน ZIP)',
'- Checkpoint `.pt` **0/27** ใน ZIP; ตรวจสอบไฟล์ Checkpoint บนเครื่องต้นทางเพิ่มเติมก่อนยืนยันแบบครบวงจร',
'- ค่า Validation IoU, F1, Precision และ Recall มาจาก epoch ที่มี Validation IoU สูงสุดของแต่ละ Run; ใช้ checkpoint selection logic `> best + 1e-5`',
'- ตรวจ CSV ทั้ง 27 ชุด: epoch ต่อเนื่อง, ไม่มีค่า metric ที่ไม่ finite, และ early stopping หลัง best epoch 6 epochs',
'',
'## 2. Macro DEV validation IoU (equal weight to USA, Sri Lanka, Spain)',
'| Model | Mean across 3 seeds | Sample SD across seed-macro | Paired mean delta vs baseline |',
'|---|---:|---:|---:|']
for s in summary:
 report.append(f"| {s['method']} | {fm(s['mean_macro_val_iou'])} | {fm(s['sample_sd_across_seed_macro'])} | {s['paired_mean_delta_vs_baseline']:+.4f} |")
report+=['','**นิยาม**: สำหรับแต่ละ Seed คำนวณค่าเฉลี่ยของ *event-level pooled/pixel micro IoU* ทั้งสาม DEV events แล้วจึงเฉลี่ยและคำนวณ sample SD ข้าม 3 Seeds; ห้ามนำไปเรียกว่า TEST IoU',
'',
'## 3. Per-event mean IoU ± SD across three seeds',
'| Event | Baseline | V2-A | V2-B | V2-B minus Baseline |',
'|---|---:|---:|---:|---:|']
for _,event in EVENTS:
 r={t['model']:t for t in by_event if t['event']==event}
 report.append(f"| {event} | {fm(r['baseline']['mean_val_iou'])} ± {fm(r['baseline']['sd_val_iou_across_seeds'])} | {fm(r['v2a_eventbalanced']['mean_val_iou'])} ± {fm(r['v2a_eventbalanced']['sd_val_iou_across_seeds'])} | {fm(r['v2b_coverage']['mean_val_iou'])} ± {fm(r['v2b_coverage']['sd_val_iou_across_seeds'])} | {r['v2b_coverage']['mean_delta_vs_baseline']:+.4f} |")
report+=['',
'## 4. Sri Lanka — paired seed evidence',
'| Seed | Baseline | V2-A | V2-B | Δ V2-B vs Baseline |',
'|---:|---:|---:|---:|---:|']
for s in SEEDS:
 b=by[('baseline',s,'Sri Lanka')]['val_iou'];a=by[('v2a_eventbalanced',s,'Sri Lanka')]['val_iou'];v=by[('v2b_coverage',s,'Sri Lanka')]['val_iou']
 report.append(f'| {s} | {b:.4f} | {a:.4f} | {v:.4f} | {v-b:+.4f} |')
report+=['',
'- **Sri Lanka** มีความแปรปรวนระหว่าง Seeds มากกว่าสอง events อื่นในทั้งสามวิธี; ภาพรวมชี้ว่าการเปลี่ยนวิธี Sampling ยังไม่แก้ปัญหาแบบสม่ำเสมอ',
'- **V2-B** ช่วย Sri Lanka seed 777 แต่ลดลงมากสำหรับ seed 123; แปลผลว่าเกิดความไวต่อ seed/การฝึก ไม่ใช่หลักฐานเชิงสาเหตุว่า Sampling เป็นตัวการทั้งหมด',
'- **Spain** V2-B ดีขึ้นเล็กน้อยในทุก seed (paired delta เป็นบวก); **USA** แทบไม่ต่าง',
'',
'## 5. Decision for project scope',
'**Baseline U-Net ยังเป็นตัวอ้างอิง DEV ที่ดีที่สุดสำหรับงานปัจจุบัน** ตาม primary metric ที่กำหนดไว้ คือ macro average DEV-validation water IoU across 3 held-out development events; อย่าอ้างว่าเป็นผล Independent Test',
'',
'**V2-A และ V2-B เป็น negative/mixed research findings ที่ควรรายงาน** ไม่ควรเลือกเพียงผลดีที่สุดเฉพาะ seed หรือสรุปว่าการทำ DG สำเร็จ',
'',
'**แนะนำปิดการทดลอง Sampling เพิ่มเพื่อเตรียมส่งงาน**: ใช้ผล Baseline/V2-A/V2-B เป็นการศึกษา DG และเปลี่ยนไปจัดทำ UQ จาก Checkpoints ที่มี โดยแยก estimation ของ ensemble uncertainty จากการพิสูจน์ calibration บน independent test',
'',
'## 6. Methodological cautions',
'1. ชุด Validation ทั้งสามใช้เลือก Epoch และเปรียบเทียบ Method แล้ว จึงเป็น DEV เท่านั้น ไม่ใช่ pristine independent TEST',
'2. 3 seeds และ 3 DEV events มีจำนวนจำกัด; ค่า SD เป็น descriptive sample SD ไม่ใช่ confidence interval หรือหลักฐานนัยสำคัญทางสถิติ',
'3. `history.csv` ไม่มี counts/confusion matrices จึงไม่สามารถทำ independent reconstruction ของ IoU/Precision/Recall จาก pixel labels ได้',
'4. V2-A ไม่ได้แนบ `run_config.json` และไม่มี checkpoint `.pt` ใน ZIP; ตรวจ selected checkpoint epoch/seed/metadata และ source/config จากเครื่องผู้วิจัยก่อน freeze final results',
'5. ผลการศึกษานี้ไม่ได้ประเมินความแม่นยำบน Thailand ซึ่งยังไม่มี aligned validated surface-water ground truth',
'6. งานนี้เป็นการวัด **surface-water segmentation** ไม่ใช่ direct flood damage/prediction',
'',
'## 7. Reproducibility and next step',
'1. ตรวจ 27 checkpoints บน local ว่า epoch และ validation IoU ที่บันทึกตรงกับ selected rows (โดยไม่เปิด TEST)',
'2. ตรวจ config / frozen protocol สำหรับ V2-A และการเปลี่ยน method เฉพาะ sampling',
'3. ทำตาราง/ภาพ DEV comparison ในสไลด์และรายงาน โดยใช้ primary metric และระบุ no TEST touched',
'4. ดำเนิน UQ analysis ที่ DEV เท่านั้น แล้วเลือก narrative อย่างระมัดระวังก่อนส่งรายงาน',
'']
if checks:report+=['## Warnings',json.dumps(checks,indent=2,ensure_ascii=False)]
(OUT/'m76d_report_th.md').write_text('\n'.join(report),encoding='utf-8')

# Charts intentionally use matplotlib default palette; colors are not set.
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    eventnames=[e for _,e in EVENTS]
    fig,ax=plt.subplots(figsize=(10,5.5))
    for model in MODELS:
        g=[next(r for r in by_event if r['model']==model and r['event']==e) for e in eventnames]
        ax.errorbar(eventnames,[r['mean_val_iou'] for r in g],yerr=[r['sd_val_iou_across_seeds'] for r in g],label=LABELS[model],marker='o',capsize=4,linewidth=2)
    ax.set_ylim(0,0.9);ax.set_ylabel('DEV validation water IoU');ax.set_title('M7.6D: DEV IoU by event (mean +/- sample SD across seeds)');ax.legend();ax.grid(alpha=0.18);fig.tight_layout()
    fig.savefig(OUT/'m76d_iou_by_event.png',dpi=180);plt.close(fig)

    fig,ax=plt.subplots(figsize=(11,5.5))
    for model in MODELS[1:]:
        vals=[by[(model,s,e)]['val_iou']-by[('baseline',s,e)]['val_iou'] for _,e in EVENTS for s in SEEDS]
        x=[i + (0 if model==MODELS[1] else 0.16) for i in range(len(vals))]
        ax.scatter(x,vals,label=LABELS[model],s=60)
    labels=[f'{e}\nseed{s}' for _,e in EVENTS for s in SEEDS]
    ax.set_xticks([i+0.08 for i in range(len(labels))],labels,fontsize=9)
    ax.axhline(0,linestyle='--');ax.grid(axis='y',alpha=0.2);ax.set_ylabel('Paired DEV IoU delta vs baseline')
    ax.set_title('M7.6D: seed/event matched changes relative to baseline');ax.legend();fig.tight_layout()
    fig.savefig(OUT/'m76d_paired_deltas.png',dpi=180);plt.close(fig)
except ImportError:
    pass

assert not checks,checks
(OUT/'m76d_audit.json').write_text(json.dumps({
    'scope':'DEV VALIDATION ONLY, no TEST',
    'input_zip':ZIP_PATH.name,'histories':len(rows),'run_configs_present':len(configs_ok),
    'run_configs_missing_V2A':9,'checkpoints_in_zip':0,
    'all_history_headers_valid':True,'all_epochs_sequential':True,
    'all_finite':True,'early_stopping_offset_six':True,
    'selection_rule':'first epoch with validation IoU > previous best + 1e-5',
    'macro_policy':'equal average of 3 event IoUs per seed, then sample mean and SD across seeds',
    'independent_test_available':False
},indent=2,ensure_ascii=False),encoding='utf-8')

with zipfile.ZipFile('/mnt/data/m76d_analysis_results.zip','w',zipfile.ZIP_DEFLATED) as arc:
    for p in sorted(OUT.iterdir()):arc.write(p,arcname=p.name)
    arc.write(Path(__file__),arcname='m76d_analyze.py')
print('DONE, files:')
for p in sorted(OUT.iterdir()):print(p, p.stat().st_size)
print('ZIP /mnt/data/m76d_analysis_results.zip')
