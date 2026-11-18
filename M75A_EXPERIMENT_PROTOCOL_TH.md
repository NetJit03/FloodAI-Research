# M7.5A — Model V2-A experiment design (development only)

**สถานะ: DESIGN READY / SOURCE CODE PREPARED / V2-A NOT YET TRAINED.**

## เป้าหมายการศึกษา

ทดสอบว่าการสุ่มตัวอย่างฝึกให้ **แต่ละเหตุการณ์มีมวลความน่าจะเป็นเท่ากัน** (event-balanced training sampling) ช่วยเพิ่มความสามารถแยกน้ำผิวดินบนเหตุการณ์พัฒนา (development-held-out events) และลดความแปรปรวนระหว่างเมล็ดสุ่ม (seeds) ได้หรือไม่ เมื่อเทียบกับ Baseline V1 ที่ Freeze ด้วย M7.0D แล้ว

ผล M7.4C: **Sri Lanka seed 777 มี water IoU 0.3891** ขณะที่ seed 42 และ 123 มี **0.7065 / 0.7011**. สองภาพที่มีน้ำจริงมากกว่า 90% มี recall รวม 0.1745 ใน seed 777 เทียบกับ 0.9953/0.9996 ในอีกสอง seeds. นี่เป็น **exploratory correlation** ไม่ใช่การพิสูจน์ว่าการสุ่มตัวอย่างไม่สมดุลเป็นต้นเหตุ

## Pre-registered V2-A hypothesis

- **H0:** การปรับเฉพาะ TRAIN event sampler ไม่เปลี่ยนค่าเฉลี่ย event-macro pixel-micro water IoU บน DEV validation เมื่อเทียบกับ Baseline ภายใต้ folds และ seeds เดียวกัน
- **H1 (exploratory):** Event-balanced sampling ช่วยเพิ่มค่าเฉลี่ยดังกล่าว; อาจลด seed instability ด้วย แต่ไม่มีการรับประกัน

## One and only one intended change

**Baseline:** ฝึกบน train images โดย `DataLoader(shuffle=True)` ซึ่งโอกาสเห็นแต่ละ event แปรตามจำนวนภาพ (e.g. 69 USA vs 18 Nigeria เมื่ออยู่ใน train)

**V2-A:** `WeightedRandomSampler`, replacement=True, ให้แต่ละ event มีโอกาสถูกเลือก 1/K ต่อหนึ่งการสุ่ม; น้ำหนักของภาพ i จาก event e คือ `1/(K * n_e)`; รวม `len(train)` draws ต่อ epoch. บันทึกจำนวนครั้งที่แต่ละ event ถูกเลือกใน `sampled_events_by_epoch.csv`

**ตรึงตาม Baseline**

- SAR 2 bands ตามลำดับ VV, VH; สองช่วง normalization VV=[-35,5], VH=[-40,0] dB
- labels -1=ignore, 0=land, 1=surface water, invalid SAR finite mask
- Random crop 256x256 และ flips/rotation เฉพาะ training, evaluation full 512x512
- SmallUNet base=16, loss 0.5 masked BCE + 0.5 masked Dice, AdamW weight_decay=1e-4
- Epochs=25 สูงสุด, batch_size=2, lr=0.0003, patience=6, threshold=0.5
- เลือก best checkpoint จาก **VALIDATION pixel-micro IoU** เท่านั้น; zero-union IoU=NaN
- Seeds: 42, 123, 777 และ 3 event-disjoint development folds เดิม; ไม่เปลี่ยนการแบ่งข้อมูล

## การแบ่งข้อมูล 3 Folds (V2)

| Fold | Train | Validation | ที่เก็บข้อมูล |
| --- | ---: | ---: | --- |
| dev_fold_01_usa | 174 | 69 USA | `data/sen1floods11/v2_development_roots/dev_fold_01_usa` |
| dev_fold_02_sri_lanka | 201 | 42 Sri Lanka | `data/sen1floods11/v2_development_roots/dev_fold_02_sri_lanka` |
| dev_fold_03_spain | 213 | 30 Spain | `data/sen1floods11/v2_development_roots/dev_fold_03_spain` |

Global Development Pool = 243 unique SAR/label pairs / 7 events. Each seed×fold yields separate model. The 3 folds are NOT 3 independent replications of the 243 images, and validation chips in each event are spatially related.

## Metrics and selection policy

**Primary:** สำหรับแต่ละ seed คำนวณ mean ของ 3 **event-level pixel-micro water IoU** จาก VALID; หลังจากนั้นรายงาน mean ± sample SD ข้าม 3 seeds และ paired difference เทียบ Baseline. ไม่ให้น้ำหนัก events ตามจำนวน pixels หรือ chips ในการคำนวณ mean ของ 3 events

**Secondary:** event-by-event recall, precision, F1, per-event stability, high-water (≥90%) and low-water strata on DEV only. **High-water strata are exploratory** because they were identified post-hoc during M7.4C.

**Predeclared descriptive success checks:** mean event-macro IoU gain ≥0.02 absolute and no event-mean IoU decrease >0.05 absolute. Failures must be reported, including seed 777. These are pragmatic exploratory gates, not tests of statistical significance.

`m75a_compare_v2a_dev.py` only compares 9 V2-A full checkpoints to M7.4C Baseline reference and intentionally refuses partial comparisons. V2-A high-water diagnostics require a separate DEV-only per-image evaluation stage after checkpoints are trained.

## Ethical / methodological constraints

- Historical India/Paraguay/Ghana **TEST**, Bolivia and Thailand: **excluded from V2 development** (also excluded from threshold/model selection). Some historical TEST events have already been inspected and cannot be described as untouched final independent testing.
- Do not change `train_sar_unet.py`, `evaluate_sar_unet.py`, `m70d_frozen_protocol.json`, or any source TIFF / split manifest; V2-A is a **separate training experiment**. Source checksum/fingerprint of V1 may remain unchanged after new V2 script is added, but `m70d_freeze_protocol.py verify` must still pass.
- Do not claim fully independent empirical evidence from existing 3 DEV validation events: the same DEV validation was used to diagnose and propose V2; true confirmation requires new unseen, independently labeled events.
- Surface-water GT is **not identical to newly inundated floodwater GT**. Thailand independent water IoU cannot be asserted without aligned and validated Thai reference labels.
- Reruns must use the same 3-fold seed policy. TRAIN sampler with replacement changes sample diversity per epoch, and this change is the treatment being studied.

## Status and next action

M7.5A creates an experiment specification, **an executable training candidate and local smoke/preflight**. It does **not** certify model improvement; only actual full runs can establish DEV comparisons.

Once V2-A is trained and results audited, M7.5B can do per-image high-water diagnostic of V2-A and (if scientifically justified) preregister a distinct V2-B candidate. Final independent evaluation requires new unseen labeled events.

## References

- Bonafilia D. et al. (2020), *Sen1Floods11: A Georeferenced Dataset to Train and Test Deep Learning Flood Algorithms for Sentinel-1*, CVPR Workshops, DOI 10.1109/CVPRW50498.2020.00113
- Sen1Floods11 official repository documentation: https://github.com/cloudtostreet/Sen1Floods11/blob/master/docs/README.md

Event-balanced sampling here is a **project-specific testable method choice**, not a claim that either cited paper demonstrated its benefit in this experiment.
