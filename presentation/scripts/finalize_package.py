#!/usr/bin/env python3
"""Write the reading guide, claim registry, and human-readable verification report."""
from pathlib import Path
import csv
import json

P=Path(__file__).resolve().parents[1]
E=P/'evidence'
d=json.loads((E/'verification_summary.json').read_text())
if d['failed']:raise SystemExit('Cannot finalize: evidence checks failed')
if d['cpu_preview_inference']!=9:raise SystemExit('Run build_presentation_evidence.py --recheck-previews first')
def csvrows(name):return list(csv.DictReader((E/name).open()))
rasters=csvrows('verified_rasters.csv')
cpu=csvrows('cpu_preview_recheck.csv')
sources={r['path']:r for r in csvrows('source_manifest.csv')}
index=json.loads((E/'slide_index.json').read_text())
metrics=csvrows('verified_metrics.csv')

# Sources are root-relative. CSV output includes a selector and aggregation meaning.
claims=[
('C01','Input VV/VH; per-pixel surface water; fixed threshold 0.50','VERIFIED_CODE_AND_METADATA','train_sar_unet.py','SarWaterDataset; SmallUNet; evaluate; checkpoint threshold','Task scope; no forecasting claim'),
('C02','Sen1Floods11 labels and dataset background','PRIMARY_DOCUMENTATION','https://github.com/cloudtostreet/Sen1Floods11','README Dataset Information; docs/README.md Hand Labeled Data Folder','446/4385 are documented dataset categories, not V2 training counts'),
('C03','243 unique development pairs from 7 event prefixes','VERIFIED_RAW_SPLITS','presentation/evidence/verified_rasters.csv','unique image; event counts','Mekong30,Nigeria18,Pakistan28,Somalia26,Spain30,Sri-Lanka42,USA69'),
('C04','TRAIN/VALID counts 174/69, 201/42, 213/30; event-disjoint','VERIFIED_RAW_SPLITS','presentation/evidence/verified_splits.csv','all 3 rows; underlying 12 split CSVs in source_manifest','Three held-out events, not full 7-fold CV'),
('C05','Historical tests and Bolivia excluded from V2 roots','VERIFIED_SPLITS_AND_DOCUMENTED_HISTORY','results/event_level_v2/m70d_protocol_freeze/m70d_frozen_protocol.json','protocol.reserved; empty test/bolivia CSVs; train/valid membership','Byte/membership checks cannot prove all past human decisions'),
('C06','Actual SmallUNet base16 and 1,963,953 parameters','VERIFIED_CODE_AND_27_STATES','train_sar_unet.py','conv_block; SmallUNet; 27 strict state_dict loads in verified_runs','Different implementation details from original U-Net paper'),
('C07','Shared training settings and train-crop/full-validation policy','VERIFIED_CONFIG_CODE_AND_METADATA','presentation/evidence/verified_runs.csv','27 checkpoint+config paths; train_sar_unet.py loss/optimizer/dataset','Maximum25 epochs, actual runs 7–16; early-stop patience6'),
('C08','Baseline shuffle without replacement once per epoch','VERIFIED_CODE','train_sar_unet.py','main DataLoader shuffle=True, no sampler','Augmentation redraws still occur each epoch'),
('C09','V2-A equal event probability in expectation, replacement sampling','VERIFIED_CODE_CONFIG_EXPOSURE','train_v2a_eventbalanced.py','calculate_weights; TrackedBalancedSampler; sampled_events_by_epoch.csv','Not exactly equal event draws in every epoch'),
('C10','V2-B 50% image-uniform + 50% five-bin-uniform, replacement','VERIFIED_CODE_AND_RAW_GT_WEIGHTS','m76b_water_sampler.py','water_bin; probability_for_bin; all 9 train_sampling_weights files','Full-chip coverage, not crop fraction; bin masses not all equal'),
('C11','27 full-fold runs = 3 methods x 3 seeds x 3 folds','VERIFIED_27_CHECKPOINTS','presentation/evidence/verified_runs.csv','27 unique method/seed/fold rows; histories/configs','27 runs, one architecture'),
('C12','Event pixel-micro IoU then mean events and seeds; sample SD','RECOMPUTED','presentation/evidence/verified_seed_macros.csv','3-event mean within seed; sample SD over 3 seed macros','Error bars are not confidence intervals; union0 means NaN'),
('C13','Macro DEV IoU Baseline .6143, V2-A .5979, V2-B .5879','RECOMPUTED_FROM_27_CHECKPOINT_COUNTS','presentation/evidence/verified_models.csv','macro_dev_iou; seed_macro_sample_sd; delta_vs_baseline','Descriptive DEV comparison, no significance claim'),
('C14','Event heterogeneity and Sri Lanka seed sensitivity','RECOMPUTED','presentation/evidence/verified_events.csv','mean_iou/sample_sd; verified_runs Sri-Lanka seed42/123/777','Associational finding, not causal country effect'),
('C15','Sri-Lanka_534068 water98.14%, IoU .9917/.9859/.2267','VERIFIED_CASE_AND_RAW_GT','presentation/evidence/verified_high_water_cases.csv','image=Sri-Lanka_534068_S1Hand.tif; all 3 seeds','Selected case, not population representation'),
('C16','Baseline-only ensemble, 3 seeds within each fold','VERIFIED_MEMBERS_AND_HASHES','results/event_level_v2/m80a_dev_ensemble_uq/m80a_members.csv','9 member rows = 3 per fold; checkpoint_sha256','Do not combine methods or checkpoints across folds'),
('C17','Baseline Ensemble Macro DEV IoU .6483; difference +.0340','RECOMPUTED_FROM_141_RECORDS','presentation/evidence/verified_ensemble_events.csv','mean over 3 event iou values; compare verified_models baseline','Mean(single IoU) and IoU(mean probabilities) are different estimands'),
('C18','Full Ensemble/UQ summaries cover 141 DEV images','VERIFIED_MEMBERSHIP_MASKS_AND_AGGREGATES','results/event_level_v2/m80a_dev_ensemble_uq/m80a_dev_per_image.csv','69USA+42Sri-Lanka+30Spain; valid-pixel-weighted UQ/Brier means','Not full fresh inference replication on 141 in this audit'),
('C19','Pixel error-capture from 9 selected previews only','INDEPENDENT_ARRAY_RECOMPUTATION','presentation/evidence/verified_selected_uq_events.csv','per-image ceil(0.1*Nvalid); rank UQ; pool captured FP+FN / all FP+FN','Selection bias; no extrapolation to full141 or new events'),
('C20','Entropy and MI do not guarantee detection of all errors','FORMULA_AND_SELECTED_DIAGNOSTICS','m80a_dev_ensemble_uq.py','entropy; uncertainty = H(mean p)-mean H(member); selected capture values','MI is disagreement proxy, not exact error probability'),
('C21','Current principal evidence is development validation','DOCUMENTED_EVIDENCE_SCOPE','results/event_level_v2/m70d_protocol_freeze/m70d_frozen_protocol.json','protocol.training.development_fold_checkpoint_selection; evaluation.test_policy','No independent final-V2 test established by this package'),
('C22','Thailand remains pilot pending aligned verified surface-water GT','DOCUMENTED_LIMITATION','results/event_level_v2/m70d_protocol_freeze/m70d_frozen_protocol.json','protocol.reserved.thailand; manuscript context provided by user','No new Thailand-reference audit here; no Thailand numerical score'),
('C23','Local band names VV/VH; dB documented; TIFF units absent','VERIFIED_METADATA_AND_PRIMARY_DOCS','presentation/evidence/verified_rasters.csv','band_descriptions; band_units; frozen manual_signoff','Local download/conversion not compared byte-for-byte against remote archive'),
('C24','27 checkpoint metadata checks and nine CPU preview rechecks','NEW_LOCAL_AUDIT','presentation/evidence/verification_summary.json','verified_runs; checks; cpu_preview_recheck','No new training; only nine previews inferred afresh'),
('C25','Earlier narrative files include stale status/typo','DIRECT_SOURCE_COMPARISON','results/event_level_v2/m81_integrated_dev_evidence/m81_report_th.md','section6 uses Indonesia; protocol/splits use India; README pre-training status','Do not copy historical next-step instructions as current facts')]
registry=[]
for cid,claim,status,src,selector,scope in claims:
    pages=[s['file'] for s in index if cid in s['claims']]
    registry.append(dict(claim_id=cid,claim=claim,status=status,slides=';'.join(pages),source=src,
                         selector=selector,interpretation_limit=scope,
                         source_sha256=sources.get(src,{}).get('sha256','see verified source_manifest or generated evidence')))
with (E/'claims_and_sources.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(registry[0]));w.writeheader();w.writerows(registry)

maxgrid=max(float(r['max_grid_delta_pixels']) for r in rasters)
maxdiff=max(float(r['max_probability_abs_difference']) for r in cpu)
flips=sum(int(r['threshold_disagreements']) for r in cpu)
report=f'''# ผลการตรวจหลักฐานสำหรับสไลด์ FloodAI-Research

ตรวจล่าสุด (Asia/Bangkok): {d['checked_at_bangkok']}

ผลตัวเลขหลักตรงกับผลเดิม: Baseline 0.6143, V2-A 0.5979, V2-B 0.5879 และ Baseline Ensemble 0.6483 จึงใช้เนื้อหาเชิงผลลัพธ์เหล่านี้ได้โดยคงขอบเขต DEV Validation

## ขอบเขตการตรวจที่ทำใหม่

| ส่วน | วิธีตรวจ | ผล |
| --- | --- | --- |
| Frozen files | คำนวณ SHA-256 ของ code, split CSVs และ 243 คู่ SAR/GT แล้วเทียบ local freeze | {d['frozen_files']}/{d['frozen_files']} ตรงกัน |
| สถานะ freeze | อ่าน frozen JSON/Markdown และบันทึก manual sign-offs | มี frozen_at และ sign-offs ครบ 4 รายการ ไม่ใช้ audit_report เก่าแทน frozen record |
| Split membership | อ่านทุก TRAIN/VALID/test stub/Bolivia stub ของ 3 DEV folds | 243 unique pairs, 7 prefixes, event-disjoint, reserved groups ไม่อยู่ใน TRAIN/VALID |
| Raster | อ่าน arrays และ metadata ของ 243 คู่ ตรวจ shape, labels, grid และ valid masks | 2×512×512 SAR, 512×512 GT, labels อยู่ใน −1/0/1, band names VV/VH ทุกคู่ |
| Checkpoints | weights_only=True, state_dict strict load, finite weights, parameters, metadata, confusion counts, history epoch และ config | 27/27 ผ่าน ไม่มีการฝึกใหม่ |
| Code consistency | เทียบ AST ของ dataset/model/loss/evaluate/seed functions ระหว่าง Baseline กับ V2-B และตรวจ recorded source hashes | ฟังก์ชันหลักตรงกัน; V2-A import baseline implementation |
| Sampling | ตรวจ V2-A source/exposure logs และ V2-B manifests/weights เทียบ raw TRAIN GT | V2-B เป็น 50/50 mixture ไม่ใช่ห้ากลุ่มเท่ากันทั้งหมด |
| DG summaries | คำนวณ IoU จาก checkpoint TP/FP/FN แล้ว mean events/seeds และ Sample SD | ตรงตาราง M8.1 และตัวเลขที่แสดง |
| Ensemble 141 records | เทียบ membership กับ VALID, raw GT counts/masks, confusion identities และรวม event counts/Brier/UQ ใหม่ | 69/42/30 ภาพ ครบ 141, macro IoU ตรง manifest |
| Stored UQ arrays | อ่าน NPZ เก้าภาพด้วย allow_pickle=False คำนวณ confusion/Brier/Entropy/MI และ top10% capture ใหม่ | ตรง outputs เดิมภายใน tolerance ที่ระบุ |
| CPU re-inference | โหลด Baseline checkpoints 3 seeds ต่อ fold ทำนายภาพ previews ทั้ง 9 ใหม่ | max abs probability difference {maxdiff:.3g}; binary disagreements ที่ threshold0.50 = {flips} valid pixels |
| Figures | คัดลอก source PNG พร้อม SHA-256, สร้าง data charts และวาด UQ จาก stored NPZ พร้อม colorbars ที่อ่านได้ | 11 รูปพร้อม provenance |

มี automated checks ผ่าน {d['passed']}/{d['checks']} รายการ ตัวเลขจำนวน checks แสดงขอบเขตการตรวจ ไม่ใช่เปอร์เซ็นต์ความจริงของงานวิจัย

## รายละเอียดที่มีผลต่อการเขียนสไลด์

1. **Freeze มีอยู่จริง:** m70d_audit_report.md เป็นสถานะก่อน freeze ส่วน m70d_frozen_protocol.json/.md เป็นสถานะถัดมา คำกล่าวก่อนตรวจที่สงสัยว่าไม่มี freeze ปิดได้ด้วยไฟล์นี้และ byte hashes ที่ตรงกัน
2. **Checkpoint metadata พร้อมแล้ว:** เอกสาร M8.1 เดิมยังระบุให้ตรวจบน local แต่รอบนี้ตรวจ checkpoint/history/config ใหม่ครบ 27 ตัว ไม่ต้องนำข้อกังวลว่า package ขาด V2-A configs มาเป็นข้อจำกัดปัจจุบัน
3. **V2-B เป็น mixture:** P(i)=0.5/N+0.5/(5*N_bin(i)); bins ใช้ full-chip GT ของ TRAIN และสุ่มคืนตัวอย่าง จำนวน draws ต่อ epoch เท่ากับ N_train
4. **Checkpoint update มี tolerance:** โค้ดรับ epoch ใหม่เมื่อ IoU ดีขึ้นเกิน 1e-5 ไม่ได้ใช้การเลือก maximum แบบไม่สน tolerance
5. **7–16 epochs ที่รันจริง:** 25 คือค่าสูงสุด ไม่ใช่จำนวน epochs ที่ทุก run ฝึกครบ ตรวจ early stopping against history แล้ว
6. **หน่วยและ band order:** official README ระบุ VV/VH และ dB; TIFF descriptions ระบุ VV/VH จริง แต่ TIFF units เป็น None ทั้งคู่ทุกภาพ การมี sign-off ไม่แทนการตรวจ radiometric provenance ทุกขั้นอย่างอิสระ
7. **Grid tolerance:** affine coefficients บางตัวไม่เท่ากันแบบ bitwise แต่ความต่างตำแหน่งมุมภาพสูงสุด {maxgrid:.3g} pixels ต่ำกว่า tolerance 1e-6 pixels มาก ใช้ CRS/dimensions เดียวกัน ไม่ใช่ spatial misalignment ที่มีสาระสำคัญ
8. **Narrative typo และสถานะเก่า:** M8.1 ข้อจำกัดข้อหนึ่งเขียน Indonesia แต่ protocol/splits ระบุ India; README หลักบอก V2-A ยังไม่ฝึก; M8.0B มี next-step เก่าที่ให้ย้อนกลับไป implement V2-B ข้อความเหล่านี้ไม่ใช้กำหนดสถานะปัจจุบัน
9. **USA P<0.1:** ค่าเปอร์เซ็นต์ที่ปัดเป็น 0.00% ยังมี GT-water pixel จำนวน 1 พิกเซล ไม่ควรพูดว่าไม่มีเลย ชุดสไลด์หลักตัดตัวเลขนี้ออกเพราะไม่จำเป็นต่อคำตอบวิจัย

## สิ่งที่การตรวจนี้ยังไม่ครอบคลุม

- ไม่ได้ฝึกโมเดลใหม่ และไม่ได้ทำ inference ใหม่ทุก run × ทุก Validation image
- ผล Ensemble ทั้ง 141 ภาพตรวจจาก stored records เทียบ raw GT และการรวมใหม่; inference ใหม่ทำเฉพาะเก้า previews
- ไม่ได้ตรวจความจริงของ labels ทุกพิกเซลด้วยผู้เชี่ยวชาญ หรือดาวน์โหลดต้นฉบับ remote TIFF มาเทียบ local conversion ทุกขั้น
- ไม่ได้ทำ Historical TEST/Thailand inference และไม่อ้างว่าตรวจ local archive ทุกไฟล์หรือทุก zip อย่างละเอียด
- จำนวนเหตุการณ์ Validation สามเหตุการณ์และ seeds สามค่าไม่พอแทนการยืนยันผลข้ามภูมิภาคทั่วไป
- การมีเอกสาร freeze/hashes ไม่ได้พิสูจน์ประวัติการตัดสินใจของผู้วิจัยนอกบันทึก หรือรับรองข้อมูลปราศจาก label noise

## วิธีตรวจย้อนกลับ

- [claims_and_sources.csv](claims_and_sources.csv): 25 ข้อความหลัก, slide IDs, source และ selector
- [verified_metrics.csv](verified_metrics.csv): {len(metrics)} ค่าพร้อมหน่วย ขอบเขต และวิธีคำนวณ
- [verified_runs.csv](verified_runs.csv): checkpoints/histories ของ 27 runs
- [source_manifest.csv](source_manifest.csv): source path, size และ SHA-256
- [checks.csv](checks.csv): ผลแต่ละเงื่อนไข ไม่ควรตีความว่า PASS = งานถูกต้อง 100%
- [unresolved_questions_TH.md](unresolved_questions_TH.md): ข้อจำกัดที่ต้องคงไว้ในการสรุป

ข้อมูลบนสไลด์มีสถานะว่า “ตรวจตามหลักฐานและขอบเขตที่ระบุ” ไม่ใช้ข้อความรับรองความถูกต้อง 100%
'''
(E/'verification_report_TH.md').write_text(report)

guide='''# ภาพที่เตรียมสำหรับนำเสนอ

คัดภาพหลักให้แต่ละหน้ามีประเด็นเดียว กราฟ 01–05 สร้างใหม่จากตารางที่คำนวณซ้ำ ภาพ 06, 07, 11 คัดลอก PNG ต้นฉบับแบบไม่แก้พิกเซลและตรวจ SHA-256 ภาพ UQ 08–10 วาดจาก NPZ ผลเดิมพร้อม normalized VV ต้นทาง เพื่อให้ชื่อ panel และ colorbars อ่านได้ ค่าผลทำนาย/uncertainty ไม่ได้เปลี่ยน และไม่ใช้ภาพสังเคราะห์

| ไฟล์ | ใช้หน้า | เนื้อหาและวิธีใช้ |
| --- | --- | --- |
| [01_sampling_macro_iou.png](figures/01_sampling_macro_iou.png) | 07 | เปรียบเทียบ macro พร้อม Sample SD ของ seed macros |
| [02_event_iou.png](figures/02_event_iou.png) | 08 | Mean และ Sample SD ข้าม seeds ภายในแต่ละ event |
| [03_sri_lanka_seeds.png](figures/03_sri_lanka_seeds.png) | Appendix B | คะแนนทุก method ตาม seed ของ Sri Lanka |
| [04_ensemble_comparison.png](figures/04_ensemble_comparison.png) | 10 | Mean single-model IoU เทียบ IoU ของ Ensemble |
| [05_selected_error_capture.png](figures/05_selected_error_capture.png) | Appendix C | Capture เฉพาะเก้าภาพที่เลือก ต้องคง selected-only caption |
| [06_sri_lanka_learning_curves.png](figures/06_sri_lanka_learning_curves.png) | สำรอง | VALID IoU/Recall/Precision/Loss ตาม epoch ของ Baseline สาม seeds ใช้ตอบเรื่อง early stopping/variance |
| [07_sri_lanka_seed_failure.png](figures/07_sri_lanka_seed_failure.png) | 09 | SAR/GT/probability/confusion ของ Sri-Lanka_534068 ต้องคง legend |
| [08_sri_lanka_ensemble_uq.png](figures/08_sri_lanka_ensemble_uq.png) | 11 | ตัวอย่างหกช่อง VV/GT/P/prediction/Entropy/MI |
| [09_usa_ensemble_uq.png](figures/09_usa_ensemble_uq.png) | สำรอง | ตัวอย่าง USA เพิ่มเติม ไม่ต้องใส่ใน main ทั้งหมด |
| [10_spain_ensemble_uq.png](figures/10_spain_ensemble_uq.png) | สำรอง | ตัวอย่าง Spain เพิ่มเติม |
| [11_input_vv_vh_gt.png](figures/11_input_vv_vh_gt.png) | 02 | อินพุตสองแบนด์และ GT ของ Sri-Lanka_713926 |

ที่มาภาพและ hash: [figure_sources.csv](figure_sources.csv)

กราฟแกน Y เริ่มที่ 0 และระบุ DEV-only หรือ selected-only ชัดเจน ห้ามตัด caption ที่เปลี่ยนขอบเขตข้อสรุปเมื่อจัด PowerPoint ภาพหลายช่องควรใช้เต็มความกว้างสไลด์เพื่อให้อ่าน legend ได้ หากต้องการ native editable chart ให้ใช้ verified CSV ที่ระบุใน provenance โดยไม่อ่านค่ากลับจากรูป

ไม่มีภาพสังเคราะห์แทนผลวิจัย และไม่มีแผนภาพ U-Net ทั่วไปที่อ้างว่าเป็น architecture จริง หน้า 04 ใช้ตารางจากโค้ด actual implementation
'''
(P/'assets/FIGURE_GUIDE_TH.md').write_text(guide)

readme='''# FloodAI-Research: ชุดเตรียมสไลด์ภาษาไทย

ชุดทางเลือก A มี **12 สไลด์หลัก + 6 สไลด์สำรอง** พร้อมข้อความบนสไลด์ บทพูด รูปประกอบ แหล่งข้อมูล และขอบเขตการตีความ ยังไม่ได้สร้าง PowerPoint

ออกแบบเรื่องสำหรับ Preliminary Results วันที่ 19 พฤศจิกายน 2569 เวลาประมาณ 13 นาทีเป็นข้อเสนอที่ปรับได้ ชื่อและรหัสผู้จัดทำต้องเติมก่อนจัดหน้าจริง

## เริ่มอ่านตรงนี้

1. [แผนการเล่าเรื่องรายหน้า](slides/00_storyline_TH.md)
2. [เนื้อหาทุกหน้ารวมไฟล์เดียว](SLIDE_CONTENT_ALL_TH.md)
3. [ผลตรวจหลักฐานและจุดที่แก้ความเข้าใจเดิม](evidence/verification_report_TH.md)
4. [ภาพที่เลือกและวิธีใช้](assets/FIGURE_GUIDE_TH.md)
5. [เตรียมตอบคำถามอาจารย์](QA_PREPARATION_TH.md)

## วิธีนำไปทำสไลด์

เปิดไฟล์ใน slides/ ตามลำดับ แต่ละหน้ามีส่วน “ข้อความบนสไลด์” ที่พร้อมคัดลอก และ “บทพูดภาษาไทย” สำหรับ speaker notes ภาพอยู่ assets/figures/ ส่วนหลักฐานเก็บไว้ตรวจเองและตอบคำถาม

ใช้ตารางข้อมูลหรือภาพเป็นหลักต่อหน้า ลดข้อความที่ซ้ำกับภาพ เก็บคำว่า DEV Validation และ Selected 9 only ในหน้าที่เกี่ยวข้อง ไม่ต้องนำชื่อ milestone ภายในไปเล่าทุกขั้น หน้า 04 ใช้รายละเอียด Small U-Net จากโค้ดจริง

## ข้อมูลที่ตรวจย้อนกลับได้

- [ข้อกล่าวอ้างและแหล่งข้อมูล](evidence/claims_and_sources.csv)
- [ทะเบียนตัวเลขพร้อมหน่วย/selector/สูตร](evidence/verified_metrics.csv)
- [ผล 27 runs](evidence/verified_runs.csv), [ผลเฉลี่ยสามวิธี](evidence/verified_models.csv)
- [Split counts](evidence/verified_splits.csv), [ตรวจ raster 243 คู่](evidence/verified_rasters.csv)
- [Ensemble event summaries](evidence/verified_ensemble_events.csv), [selected UQ capture](evidence/verified_selected_uq_events.csv)
- [CPU recheck เก้าภาพ](evidence/cpu_preview_recheck.csv), [manifest แหล่งไฟล์](evidence/source_manifest.csv)
- [แหล่งอ้างอิงภายนอก](evidence/references_TH.md), [ข้อจำกัดที่ยังเหลือ](evidence/unresolved_questions_TH.md)

## การสร้างหลักฐานซ้ำ

รันจากโฟลเดอร์ FloodAI-Research โดยใช้ .venv ที่มี torch/rasterio/numpy/matplotlib อยู่แล้ว:

```bash
MPLCONFIGDIR=/private/tmp/floodai-mpl .venv/bin/python presentation/scripts/build_presentation_evidence.py --recheck-previews
python3 presentation/scripts/build_slide_markdown.py
python3 presentation/scripts/finalize_package.py
python3 presentation/scripts/validate_package.py
```

คำสั่งแรกอ่าน code, DEV splits, TIFF, checkpoints และผลเดิม แล้วเขียนผลตรวจ/กราฟเฉพาะ presentation/ มี inference ใหม่เก้าภาพบน CPU ไม่มี training หรือ Historical TEST/Thailand inference คำสั่งสร้าง Markdown จะเขียนทับไฟล์ที่สร้างใน presentation/ จึงควรเก็บสำเนาหากแก้ข้อความเองแล้ว

หากไม่ต้องการ inference ซ้ำ สามารถใช้คำสั่งแรกโดยไม่ใส่ --recheck-previews เพื่อตรวจ evidence บางส่วนได้ แต่การ finalize ชุดเต็มต้องรันพร้อม flag เพื่อไม่อ้างการตรวจจาก cache เก่า

## ขอบเขตที่ต้องคงไว้

คะแนนหลักเป็น Development Validation; ภาพตัวอย่างมี selection bias; ยังไม่ยืนยัน V2 บน Independent Final TEST และไม่รายงาน Thailand quantitative accuracy การตรวจชุดนี้เพิ่มความตรวจสอบย้อนกลับได้ โดยไม่ได้รับรอง labels หรือข้อสรุปวิจัยถูกต้อง 100%

การเปลี่ยนแปลงครั้งนี้อยู่ภายใน presentation/ ไม่แก้ code การทดลอง splits checkpoints หรือรายงานต้นทาง
'''
(P/'README_TH.md').write_text(readme)
print('Wrote claim registry, verification report, figure guide and README')
